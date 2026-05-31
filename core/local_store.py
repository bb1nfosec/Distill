"""
local_store.py — Thread-safe local SQLite event store for skim proxy.

Stores every intercepted API call to ~/.skim/events.db so the embedded
local dashboard can read it with zero server setup required.
"""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB = Path.home() / ".skim" / "events.db"
_local      = threading.local()


def _conn(db_path: Path) -> sqlite3.Connection:
    key  = str(db_path)
    conn = getattr(_local, key, None)
    if conn is None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        setattr(_local, key, conn)
    return conn


def init(db_path: Path = None) -> None:
    p = db_path or _DEFAULT_DB
    _conn(p).executescript("""
    CREATE TABLE IF NOT EXISTS events (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        ts            TEXT    NOT NULL,
        provider      TEXT    DEFAULT '',
        model         TEXT    DEFAULT '',
        input_tokens  INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        saved_tokens  INTEGER DEFAULT 0,
        cached_tokens INTEGER DEFAULT 0,
        cost_usd      REAL    DEFAULT 0,
        latency_ms    INTEGER DEFAULT 0,
        plan          TEXT    DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_local_ts ON events(ts);
    """)
    _conn(p).commit()


def record(event: dict, db_path: Path = None) -> None:
    p  = db_path or _DEFAULT_DB
    ts = datetime.now(timezone.utc).isoformat()
    _conn(p).execute(
        "INSERT INTO events (ts,provider,model,input_tokens,output_tokens,"
        "saved_tokens,cached_tokens,cost_usd,latency_ms,plan) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            ts,
            event.get("provider", ""),
            event.get("model", ""),
            int(event.get("input_tokens",  0)),
            int(event.get("output_tokens", 0)),
            int(event.get("saved_tokens",  0)),
            int(event.get("cached_tokens", 0)),
            float(event.get("cost_usd",    0.0)),
            int(event.get("latency_ms",    0)),
            event.get("plan", ""),
        ),
    )
    _conn(p).commit()


def summary(days: int = 30, db_path: Path = None) -> dict:
    p   = db_path or _DEFAULT_DB
    row = _conn(p).execute("""
        SELECT
            COUNT(*)                        AS total_calls,
            COALESCE(SUM(input_tokens),  0) AS total_input,
            COALESCE(SUM(output_tokens), 0) AS total_output,
            COALESCE(SUM(saved_tokens),  0) AS total_saved,
            COALESCE(SUM(cached_tokens), 0) AS total_cached,
            COALESCE(SUM(cost_usd),      0) AS total_cost,
            COALESCE(AVG(latency_ms),    0) AS avg_latency,
            COALESCE(AVG(input_tokens),  0) AS avg_input
        FROM events
        WHERE datetime(ts) >= datetime('now', ?, 'utc')
    """, (f"-{days} days",)).fetchone()
    return dict(row) if row else {}


def by_day(days: int = 30, db_path: Path = None) -> list[dict]:
    p    = db_path or _DEFAULT_DB
    rows = _conn(p).execute("""
        SELECT
            substr(ts,1,10)         AS day,
            COUNT(*)                AS calls,
            COALESCE(SUM(input_tokens),  0) AS input_tokens,
            COALESCE(SUM(saved_tokens),  0) AS saved_tokens,
            COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
            ROUND(SUM(cost_usd), 6) AS cost_usd
        FROM events
        WHERE datetime(ts) >= datetime('now', ?, 'utc')
        GROUP BY day ORDER BY day
    """, (f"-{days} days",)).fetchall()
    return [dict(r) for r in rows]


def by_hour(days: int = 7, db_path: Path = None) -> list[dict]:
    p    = db_path or _DEFAULT_DB
    rows = _conn(p).execute("""
        SELECT
            substr(ts,1,13)         AS hour,
            COUNT(*)                AS calls,
            COALESCE(SUM(input_tokens), 0) AS input_tokens,
            ROUND(SUM(cost_usd), 6) AS cost_usd
        FROM events
        WHERE datetime(ts) >= datetime('now', ?, 'utc')
        GROUP BY hour ORDER BY hour
    """, (f"-{days} days",)).fetchall()
    return [dict(r) for r in rows]


def by_model(days: int = 30, db_path: Path = None) -> list[dict]:
    p    = db_path or _DEFAULT_DB
    rows = _conn(p).execute("""
        SELECT
            COALESCE(model, 'unknown')       AS model,
            COALESCE(provider, '')           AS provider,
            COUNT(*)                         AS calls,
            COALESCE(SUM(input_tokens),  0)  AS input_tokens,
            COALESCE(SUM(output_tokens), 0)  AS output_tokens,
            COALESCE(SUM(saved_tokens),  0)  AS saved_tokens,
            COALESCE(SUM(cached_tokens), 0)  AS cached_tokens,
            ROUND(COALESCE(SUM(cost_usd), 0), 6)   AS cost_usd,
            ROUND(COALESCE(AVG(latency_ms), 0), 0)  AS avg_latency_ms
        FROM events
        WHERE datetime(ts) >= datetime('now', ?, 'utc')
        GROUP BY model ORDER BY input_tokens DESC
    """, (f"-{days} days",)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        inp = d["input_tokens"] or 1
        d["cache_hit_pct"] = round(d["cached_tokens"] / inp * 100, 1)
        d["waste_pct"]     = round(d["saved_tokens"]  / inp * 100, 1)
        result.append(d)
    return result


def recent_events(days: int = 7, limit: int = 200, db_path: Path = None) -> list[dict]:
    p    = db_path or _DEFAULT_DB
    rows = _conn(p).execute(
        "SELECT * FROM events "
        "WHERE datetime(ts) >= datetime('now', ?, 'utc') "
        "ORDER BY ts DESC LIMIT ?",
        (f"-{days} days", limit),
    ).fetchall()
    return [dict(r) for r in rows]
