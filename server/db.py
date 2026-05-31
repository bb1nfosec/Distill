"""
db.py — SQLite data layer for skim server.

Schema is written to be forward-compatible with PostgreSQL.
All timestamps are UTC ISO strings.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB = Path.home() / ".skim" / "skim.db"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path = None) -> sqlite3.Connection:
    p = db_path or _DEFAULT_DB
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id         TEXT PRIMARY KEY,
        email      TEXT UNIQUE NOT NULL,
        name       TEXT,
        team       TEXT,
        role       TEXT NOT NULL DEFAULT 'user',
        password_hash TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS api_keys (
        key        TEXT PRIMARY KEY,
        user_id    TEXT REFERENCES users(id) ON DELETE CASCADE,
        label      TEXT,
        created_at TEXT NOT NULL,
        last_used  TEXT
    );

    CREATE TABLE IF NOT EXISTS events (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        ts            TEXT NOT NULL,
        user_id       TEXT,
        session_id    TEXT,
        provider      TEXT,
        model         TEXT,
        input_tokens  INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        saved_tokens  INTEGER DEFAULT 0,
        cost_usd      REAL    DEFAULT 0,
        project_path  TEXT,
        latency_ms    INTEGER DEFAULT 0,
        command       TEXT,
        extra         TEXT
    );

    CREATE TABLE IF NOT EXISTS budgets (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_type  TEXT NOT NULL,   -- 'user' | 'team' | 'global'
        owner_id    TEXT,
        limit_tokens INTEGER,
        limit_usd   REAL,
        period      TEXT DEFAULT 'monthly',
        alert_pct   REAL DEFAULT 80.0,
        created_at  TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_events_ts      ON events(ts);
    CREATE INDEX IF NOT EXISTS idx_events_user    ON events(user_id);
    CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
    """)
    conn.commit()


# ── Users ────────────────────────────────────────────────────────────────────

def create_user(conn, email: str, name: str = "", team: str = "",
                role: str = "user", password_hash: str = "") -> dict:
    uid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO users (id, email, name, team, role, password_hash, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uid, email, name, team, role, password_hash, _ts()),
    )
    conn.commit()
    return get_user_by_id(conn, uid)


def get_user_by_email(conn, email: str):
    row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(conn, uid: str):
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


def list_users(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()]


# ── API keys ─────────────────────────────────────────────────────────────────

def create_api_key(conn, user_id: str, label: str = "") -> str:
    key = "sk-skim-" + uuid.uuid4().hex
    conn.execute(
        "INSERT INTO api_keys (key, user_id, label, created_at) VALUES (?, ?, ?, ?)",
        (key, user_id, label, _ts()),
    )
    conn.commit()
    return key


def get_user_for_key(conn, key: str):
    row = conn.execute(
        "SELECT u.* FROM users u JOIN api_keys k ON k.user_id=u.id WHERE k.key=?",
        (key,)
    ).fetchone()
    if row:
        conn.execute("UPDATE api_keys SET last_used=? WHERE key=?", (_ts(), key))
        conn.commit()
        return dict(row)
    return None


# ── Events ───────────────────────────────────────────────────────────────────

def insert_event(conn, event: dict) -> int:
    r = conn.execute(
        "INSERT INTO events "
        "(ts, user_id, session_id, provider, model, input_tokens, output_tokens, "
        " saved_tokens, cost_usd, project_path, latency_ms, command, extra) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            event.get("ts", _ts()),
            event.get("user_id"),
            event.get("session_id"),
            event.get("provider", "anthropic"),
            event.get("model", ""),
            event.get("input_tokens", 0),
            event.get("output_tokens", 0),
            event.get("saved_tokens", 0),
            event.get("cost_usd", 0),
            event.get("project_path", ""),
            event.get("latency_ms", 0),
            event.get("command", ""),
            json.dumps(event.get("extra")) if event.get("extra") else None,
        ),
    )
    conn.commit()
    return r.lastrowid


def query_events(conn, days: int = 30, user_id: str = None,
                 limit: int = 500, offset: int = 0) -> list[dict]:
    from_ts = datetime.now(timezone.utc).isoformat()[:-6]
    params  = [f"{days} days"]
    where   = ["datetime(ts) >= datetime('now', ?, 'utc')"]
    if user_id:
        where.append("user_id=?")
        params.append(user_id)
    sql = (
        "SELECT * FROM events WHERE "
        + " AND ".join(where)
        + " ORDER BY ts DESC LIMIT ? OFFSET ?"
    )
    params += [limit, offset]
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def stats_summary(conn, days: int = 7) -> dict:
    sql = """
    SELECT
        COUNT(*)               AS total_calls,
        COALESCE(SUM(input_tokens),  0) AS total_input,
        COALESCE(SUM(output_tokens), 0) AS total_output,
        COALESCE(SUM(saved_tokens),  0) AS total_saved,
        COALESCE(SUM(cost_usd),      0) AS total_cost,
        COALESCE(AVG(input_tokens),  0) AS avg_input
    FROM events
    WHERE datetime(ts) >= datetime('now', ?, 'utc')
    """
    row = conn.execute(sql, [f"-{days} days"]).fetchone()
    return dict(row) if row else {}


def stats_by_day(conn, days: int = 30) -> list[dict]:
    sql = """
    SELECT
        substr(ts, 1, 10)        AS day,
        COUNT(*)                 AS calls,
        SUM(input_tokens)        AS input_tokens,
        SUM(saved_tokens)        AS saved_tokens,
        ROUND(SUM(cost_usd), 4)  AS cost_usd
    FROM events
    WHERE datetime(ts) >= datetime('now', ?, 'utc')
    GROUP BY day
    ORDER BY day
    """
    return [dict(r) for r in conn.execute(sql, [f"-{days} days"]).fetchall()]


def stats_by_user(conn, days: int = 30) -> list[dict]:
    sql = """
    SELECT
        COALESCE(u.name, e.user_id, 'anonymous') AS user_name,
        COALESCE(u.team, '')                      AS team,
        COUNT(*)                                  AS calls,
        SUM(e.input_tokens)                       AS input_tokens,
        ROUND(SUM(e.cost_usd), 4)                 AS cost_usd
    FROM events e
    LEFT JOIN users u ON u.id = e.user_id
    WHERE datetime(e.ts) >= datetime('now', ?, 'utc')
    GROUP BY e.user_id
    ORDER BY input_tokens DESC
    LIMIT 20
    """
    return [dict(r) for r in conn.execute(sql, [f"-{days} days"]).fetchall()]


def stats_by_model(conn, days: int = 30) -> list[dict]:
    sql = """
    SELECT
        COALESCE(model, 'unknown') AS model,
        COUNT(*)                   AS calls,
        SUM(input_tokens)          AS input_tokens,
        ROUND(SUM(cost_usd), 4)    AS cost_usd
    FROM events
    WHERE datetime(ts) >= datetime('now', ?, 'utc')
    GROUP BY model
    ORDER BY input_tokens DESC
    """
    return [dict(r) for r in conn.execute(sql, [f"-{days} days"]).fetchall()]
