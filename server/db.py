"""
db.py — SQLite data layer for skim server.

Schema is written to be forward-compatible with PostgreSQL.
All timestamps are UTC ISO strings.
"""

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB = Path.home() / ".skim" / "skim.db"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path = None) -> sqlite3.Connection:
    """
    Return a new SQLite connection for the caller.
    WAL mode allows concurrent reads and serialises writes safely —
    each Flask request thread gets its own connection, no shared-state bugs.
    Callers are responsible for closing when done (Flask teardown handles this).
    """
    p = db_path or _DEFAULT_DB
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id            TEXT PRIMARY KEY,
        email         TEXT UNIQUE NOT NULL,
        name          TEXT,
        team          TEXT,
        role          TEXT NOT NULL DEFAULT 'user',
        password_hash TEXT,
        created_at    TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS api_keys (
        key        TEXT PRIMARY KEY,
        user_id    TEXT REFERENCES users(id) ON DELETE CASCADE,
        label      TEXT,
        scope      TEXT NOT NULL DEFAULT 'ingest',
        created_at TEXT NOT NULL,
        expires_at TEXT,
        last_used  TEXT
    );

    CREATE TABLE IF NOT EXISTS events (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        ts             TEXT NOT NULL,
        user_id        TEXT,
        session_id     TEXT,
        provider       TEXT,
        model          TEXT,
        input_tokens   INTEGER DEFAULT 0,
        output_tokens  INTEGER DEFAULT 0,
        saved_tokens   INTEGER DEFAULT 0,
        cached_tokens  INTEGER DEFAULT 0,
        cost_usd       REAL    DEFAULT 0,
        project_path   TEXT,
        latency_ms     INTEGER DEFAULT 0,
        command        TEXT,
        extra          TEXT
    );

    CREATE TABLE IF NOT EXISTS budgets (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_type   TEXT NOT NULL DEFAULT 'user',
        owner_id     TEXT,
        limit_tokens INTEGER,
        limit_usd    REAL,
        period       TEXT NOT NULL DEFAULT 'monthly',
        alert_pct    REAL NOT NULL DEFAULT 80.0,
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS webhooks (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    TEXT REFERENCES users(id) ON DELETE CASCADE,
        url        TEXT NOT NULL,
        channel    TEXT NOT NULL DEFAULT 'http',
        events     TEXT NOT NULL DEFAULT 'budget.warning,budget.exceeded',
        secret     TEXT NOT NULL DEFAULT '',
        active     INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS invites (
        token      TEXT PRIMARY KEY,
        email      TEXT NOT NULL,
        role       TEXT NOT NULL DEFAULT 'user',
        team       TEXT NOT NULL DEFAULT '',
        created_by TEXT REFERENCES users(id),
        expires_at TEXT NOT NULL,
        used_at    TEXT
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        ts            TEXT NOT NULL,
        user_id       TEXT,
        email         TEXT,
        action        TEXT NOT NULL,
        resource_type TEXT,
        resource_id   TEXT,
        detail        TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_events_ts      ON events(ts);
    CREATE INDEX IF NOT EXISTS idx_events_user    ON events(user_id);
    CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
    CREATE INDEX IF NOT EXISTS idx_audit_ts       ON audit_log(ts);
    CREATE INDEX IF NOT EXISTS idx_audit_action   ON audit_log(action);
    """)
    # Forward-compatible column migrations
    def _cols(table):
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    ev = _cols("events")
    if "cached_tokens" not in ev:
        conn.execute("ALTER TABLE events ADD COLUMN cached_tokens INTEGER DEFAULT 0")
    ak = _cols("api_keys")
    if "scope"      not in ak:
        conn.execute("ALTER TABLE api_keys ADD COLUMN scope TEXT NOT NULL DEFAULT 'ingest'")
    if "expires_at" not in ak:
        conn.execute("ALTER TABLE api_keys ADD COLUMN expires_at TEXT")
    bg = _cols("budgets")
    if "updated_at" not in bg:
        conn.execute("ALTER TABLE budgets ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
    us = _cols("users")
    if "last_login" not in us:
        conn.execute("ALTER TABLE users ADD COLUMN last_login TEXT")
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

def delete_user(conn, user_id: str) -> None:
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()


def touch_last_login(conn, user_id: str) -> None:
    conn.execute("UPDATE users SET last_login=? WHERE id=?", (_ts(), user_id))
    conn.commit()


def purge_events(conn, older_than_days: int) -> int:
    """Delete events older than N days. Returns rows removed.
    Enterprise data-retention / compliance control."""
    cur = conn.execute(
        "DELETE FROM events WHERE datetime(ts) < datetime('now', ?, 'utc')",
        (f"-{older_than_days} days",),
    )
    conn.commit()
    return cur.rowcount


# ── API keys ─────────────────────────────────────────────────────────────────

def create_api_key(conn, user_id: str, label: str = "",
                   scope: str = "ingest", expires_days: int = None) -> str:
    key        = "sk-skim-" + uuid.uuid4().hex
    expires_at = None
    if expires_days:
        from datetime import timedelta
        expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat()
    conn.execute(
        "INSERT INTO api_keys (key,user_id,label,scope,created_at,expires_at) "
        "VALUES (?,?,?,?,?,?)",
        (key, user_id, label, scope, _ts(), expires_at),
    )
    conn.commit()
    return key


def revoke_api_key(conn, key: str) -> None:
    conn.execute("DELETE FROM api_keys WHERE key=?", (key,))
    conn.commit()


def get_user_for_key(conn, key: str, required_scope: str = None):
    row = conn.execute(
        "SELECT u.*, k.scope, k.expires_at FROM users u "
        "JOIN api_keys k ON k.user_id=u.id WHERE k.key=?",
        (key,)
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    # Check expiry
    if d.get("expires_at"):
        try:
            if datetime.fromisoformat(d["expires_at"]) < datetime.now(timezone.utc):
                return None  # expired
        except Exception:
            pass
    # Check scope
    if required_scope:
        scope = d.get("scope", "ingest")
        if scope != "admin" and scope != required_scope:
            return None  # insufficient scope
    conn.execute("UPDATE api_keys SET last_used=? WHERE key=?", (_ts(), key))
    conn.commit()
    return d


# ── Events ───────────────────────────────────────────────────────────────────

def insert_event(conn, event: dict) -> int:
    r = conn.execute(
        "INSERT INTO events "
        "(ts, user_id, session_id, provider, model, input_tokens, output_tokens, "
        " saved_tokens, cached_tokens, cost_usd, project_path, latency_ms, command, extra) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            event.get("ts", _ts()),
            event.get("user_id"),
            event.get("session_id"),
            event.get("provider", "anthropic"),
            event.get("model", ""),
            event.get("input_tokens", 0),
            event.get("output_tokens", 0),
            event.get("saved_tokens", 0),
            event.get("cached_tokens", 0),
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
    params  = [f"-{days} days"]
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


def stats_summary(conn, days: int = 7, user_id: str = None) -> dict:
    where  = ["datetime(ts) >= datetime('now', ?, 'utc')"]
    params = [f"-{days} days"]
    if user_id:
        where.append("user_id=?")
        params.append(user_id)
    sql = f"""
    SELECT
        COUNT(*)               AS total_calls,
        COALESCE(SUM(input_tokens),  0) AS total_input,
        COALESCE(SUM(output_tokens), 0) AS total_output,
        COALESCE(SUM(saved_tokens),  0) AS total_saved,
        COALESCE(SUM(cost_usd),      0) AS total_cost,
        COALESCE(AVG(input_tokens),  0) AS avg_input
    FROM events
    WHERE {' AND '.join(where)}
    """
    row = conn.execute(sql, params).fetchone()
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
        COALESCE(u.name, e.user_id, 'anonymous')  AS user_name,
        COALESCE(u.email, '')                      AS email,
        COALESCE(u.team, '')                       AS team,
        COUNT(*)                                   AS calls,
        COALESCE(SUM(e.input_tokens),  0)          AS input_tokens,
        COALESCE(SUM(e.output_tokens), 0)          AS output_tokens,
        COALESCE(SUM(e.saved_tokens),  0)          AS saved_tokens,
        COALESCE(SUM(e.cached_tokens), 0)          AS cached_tokens,
        ROUND(COALESCE(SUM(e.cost_usd), 0), 4)    AS cost_usd,
        ROUND(COALESCE(AVG(e.latency_ms), 0), 0)  AS avg_latency_ms
    FROM events e
    LEFT JOIN users u ON u.id = e.user_id
    WHERE datetime(e.ts) >= datetime('now', ?, 'utc')
    GROUP BY e.user_id
    ORDER BY input_tokens DESC
    LIMIT 20
    """
    rows = [dict(r) for r in conn.execute(sql, [f"-{days} days"]).fetchall()]
    for r in rows:
        inp   = r["input_tokens"] or 1
        saved = r["saved_tokens"] or 0
        cache = r["cached_tokens"] or 0
        r["waste_pct"]     = round(saved / inp * 100, 1)
        r["cache_hit_pct"] = round(cache / inp * 100, 1)
    return rows


def get_insights(conn, days: int = 30) -> list[dict]:
    """Generate org-level optimization recommendations from event patterns."""
    insights = []
    period   = f"-{days} days"

    # 1. Org-wide waste rate
    row = conn.execute("""
        SELECT COALESCE(SUM(input_tokens),0) AS inp,
               COALESCE(SUM(saved_tokens),0) AS saved,
               COALESCE(SUM(cost_usd),0)     AS cost
        FROM events WHERE datetime(ts) >= datetime('now', ?, 'utc')
    """, [period]).fetchone()
    if row and row["inp"] > 0:
        waste_pct = row["saved"] / row["inp"] * 100
        if waste_pct < 20:
            saved_usd = row["inp"] * 0.03 / 1000 * 0.3  # est 30% more savings possible
            insights.append({
                "severity": "high",
                "title":    "Low waste filtering rate",
                "detail":   f"Only {waste_pct:.0f}% of tokens are being stripped. "
                            f"Run `skim fix --path .` on each project — "
                            f"estimated additional savings: ${saved_usd:.2f}/period.",
                "action":   "skim fix --path . --min-severity medium",
            })

    # 2. Cache hit rate
    row = conn.execute("""
        SELECT COALESCE(SUM(input_tokens),0)  AS inp,
               COALESCE(SUM(cached_tokens),0) AS cached
        FROM events WHERE datetime(ts) >= datetime('now', ?, 'utc')
    """, [period]).fetchone()
    if row and row["inp"] > 0:
        cache_pct = row["cached"] / row["inp"] * 100
        if cache_pct < 30:
            insights.append({
                "severity": "medium",
                "title":    f"Cache hit rate is low ({cache_pct:.0f}%)",
                "detail":   "Team average prompt cache hit rate is below 30%. "
                            "A shared CLAUDE.md with system prompt content will "
                            "dramatically increase hits — target is 60%+.",
                "action":   "skim generate --output . --model claude",
            })

    # 3. Top wasting users
    users = conn.execute("""
        SELECT COALESCE(u.name, e.user_id, 'unknown') AS name,
               SUM(e.input_tokens)                    AS inp,
               SUM(e.saved_tokens)                    AS saved,
               ROUND(SUM(e.cost_usd), 2)              AS cost
        FROM events e LEFT JOIN users u ON u.id = e.user_id
        WHERE datetime(e.ts) >= datetime('now', ?, 'utc')
          AND e.saved_tokens > 0
        GROUP BY e.user_id
        ORDER BY saved DESC LIMIT 3
    """, [period]).fetchall()
    for u in users:
        if u["inp"] and u["saved"] / u["inp"] > 0.5:
            monthly = u["cost"] * (30 / days) if days > 0 else 0
            insights.append({
                "severity": "medium",
                "title":    f"{u['name']} has high per-session waste",
                "detail":   f"Over {u['saved']/u['inp']*100:.0f}% of their tokens are "
                            f"waste — mostly lock files or build artifacts. "
                            f"At their rate, fix saves ~${monthly:.2f}/month.",
                "action":   "skim fix --path <their-project>",
            })

    # 4. Users not connected to proxy
    total_users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    active = conn.execute("""
        SELECT COUNT(DISTINCT user_id) AS n FROM events
        WHERE datetime(ts) >= datetime('now', ?, 'utc')
    """, [period]).fetchone()["n"]
    if total_users > 1 and active < total_users:
        dark = total_users - active
        insights.append({
            "severity": "low",
            "title":    f"{dark} team member{'s' if dark>1 else ''} not using the proxy",
            "detail":   f"{dark} of {total_users} registered users have no activity "
                        f"in the last {days} days — they're paying full rate with no "
                        f"waste stripping or caching.",
            "action":   "Share: export ANTHROPIC_BASE_URL=http://skim.corp:7474",
        })

    return insights


def stats_by_model(conn, days: int = 30) -> list[dict]:
    sql = """
    SELECT
        COALESCE(model, 'unknown')       AS model,
        COUNT(*)                         AS calls,
        COALESCE(SUM(input_tokens),  0)  AS input_tokens,
        COALESCE(SUM(output_tokens), 0)  AS output_tokens,
        COALESCE(SUM(saved_tokens),  0)  AS saved_tokens,
        COALESCE(SUM(cached_tokens), 0)  AS cached_tokens,
        ROUND(COALESCE(SUM(cost_usd),    0), 4)  AS cost_usd,
        ROUND(COALESCE(AVG(latency_ms),  0), 0)  AS avg_latency_ms
    FROM events
    WHERE datetime(ts) >= datetime('now', ?, 'utc')
    GROUP BY model
    ORDER BY input_tokens DESC
    """
    rows = [dict(r) for r in conn.execute(sql, [f"-{days} days"]).fetchall()]
    for r in rows:
        inp = r["input_tokens"] or 1
        r["cache_hit_pct"] = round((r["cached_tokens"] or 0) / inp * 100, 1)
        r["waste_pct"]     = round((r["saved_tokens"]  or 0) / inp * 100, 1)
    return rows


def stats_by_hour(conn, days: int = 7) -> list[dict]:
    sql = """
    SELECT
        substr(ts,1,13)         AS hour,
        COUNT(*)                AS calls,
        COALESCE(SUM(input_tokens), 0) AS input_tokens,
        ROUND(SUM(cost_usd), 6) AS cost_usd
    FROM events
    WHERE datetime(ts) >= datetime('now', ?, 'utc')
    GROUP BY hour ORDER BY hour
    """
    return [dict(r) for r in conn.execute(sql, [f"-{days} days"]).fetchall()]


# ── Budgets ───────────────────────────────────────────────────────────────────

_PERIOD_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}


def set_budget(conn, owner_type: str, owner_id: str, limit_tokens: int = None,
               limit_usd: float = None, period: str = "monthly",
               alert_pct: float = 80.0) -> dict:
    now = _ts()
    existing = conn.execute(
        "SELECT id FROM budgets WHERE owner_type=? AND owner_id IS ?",
        (owner_type, owner_id)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE budgets SET limit_tokens=?,limit_usd=?,period=?,alert_pct=?,updated_at=? "
            "WHERE owner_type=? AND owner_id IS ?",
            (limit_tokens, limit_usd, period, alert_pct, now, owner_type, owner_id),
        )
    else:
        conn.execute(
            "INSERT INTO budgets (owner_type,owner_id,limit_tokens,limit_usd,period,alert_pct,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (owner_type, owner_id, limit_tokens, limit_usd, period, alert_pct, now, now),
        )
    conn.commit()
    return get_budget(conn, owner_type, owner_id)


def get_budget(conn, owner_type: str, owner_id: str = None) -> dict | None:
    row = conn.execute(
        "SELECT * FROM budgets WHERE owner_type=? AND owner_id IS ?",
        (owner_type, owner_id)
    ).fetchone()
    return dict(row) if row else None


def list_budgets(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT b.*, u.email, u.name FROM budgets b "
        "LEFT JOIN users u ON b.owner_type='user' AND b.owner_id=u.id "
        "ORDER BY b.owner_type, b.created_at"
    ).fetchall()]


def delete_budget(conn, budget_id: int) -> None:
    conn.execute("DELETE FROM budgets WHERE id=?", (budget_id,))
    conn.commit()


def get_period_usage(conn, user_id: str, team: str = None,
                     period: str = "monthly") -> dict:
    days   = _PERIOD_DAYS.get(period, 30)
    cutoff = f"-{days} days"
    # User-level usage
    row = conn.execute("""
        SELECT COALESCE(SUM(input_tokens),0) AS tokens,
               COALESCE(SUM(cost_usd),0)     AS cost
        FROM events
        WHERE user_id=? AND datetime(ts) >= datetime('now', ?, 'utc')
    """, (user_id, cutoff)).fetchone()
    return dict(row) if row else {"tokens": 0, "cost": 0.0}


def check_budget(conn, user_id: str, team: str = None,
                 estimated_tokens: int = 0) -> dict:
    """
    Returns {"allowed": bool, "reason": str, "pct_used": float,
             "remaining_tokens": int, "remaining_usd": float}
    Checks user budget first, then team budget, then global.
    """
    user     = get_user_by_id(conn, user_id)
    team_id  = team or (user.get("team") if user else None)

    for btype, bid in [("user", user_id), ("team", team_id), ("global", None)]:
        if not bid and btype == "team":
            continue
        budget = get_budget(conn, btype, bid if btype != "global" else None)
        if not budget:
            continue
        usage = get_period_usage(conn, user_id, team_id, budget["period"])
        used_tokens = usage["tokens"]
        used_usd    = usage["cost"]

        if budget["limit_tokens"] and used_tokens + estimated_tokens > budget["limit_tokens"]:
            pct = min((used_tokens / budget["limit_tokens"]) * 100, 100)
            return {
                "allowed": False,
                "reason": f"{btype} token budget exceeded ({pct:.0f}% used)",
                "pct_used": pct,
                "remaining_tokens": max(0, budget["limit_tokens"] - used_tokens),
                "remaining_usd": None,
                "budget_type": btype,
            }
        if budget["limit_usd"] and used_usd >= budget["limit_usd"]:
            pct = min((used_usd / budget["limit_usd"]) * 100, 100)
            return {
                "allowed": False,
                "reason": f"{btype} cost budget exceeded (${used_usd:.4f} / ${budget['limit_usd']:.2f})",
                "pct_used": pct,
                "remaining_tokens": None,
                "remaining_usd": max(0.0, budget["limit_usd"] - used_usd),
                "budget_type": btype,
            }

        # Warning threshold (return allowed=True but include pct)
        pct = 0.0
        if budget["limit_tokens"] and budget["limit_tokens"] > 0:
            pct = (used_tokens / budget["limit_tokens"]) * 100
        elif budget["limit_usd"] and budget["limit_usd"] > 0:
            pct = (used_usd / budget["limit_usd"]) * 100

        rem_tok = (budget["limit_tokens"] - used_tokens) if budget["limit_tokens"] else None
        rem_usd = (budget["limit_usd"] - used_usd)      if budget["limit_usd"]    else None
        return {
            "allowed": True,
            "reason": "ok",
            "pct_used": round(pct, 1),
            "remaining_tokens": rem_tok,
            "remaining_usd": rem_usd,
            "at_warning": pct >= budget["alert_pct"],
            "budget_type": btype,
        }

    return {"allowed": True, "reason": "no budget set", "pct_used": 0.0}


# ── Webhooks ─────────────────────────────────────────────────────────────────

def create_webhook(conn, user_id: str, url: str, channel: str = "http",
                   events: str = "budget.warning,budget.exceeded",
                   secret: str = "") -> dict:
    conn.execute(
        "INSERT INTO webhooks (user_id,url,channel,events,secret,active,created_at) "
        "VALUES (?,?,?,?,?,1,?)",
        (user_id, url, channel, events, secret, _ts()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM webhooks WHERE rowid=last_insert_rowid()").fetchone()
    return dict(row)


def list_webhooks(conn, user_id: str = None) -> list[dict]:
    if user_id:
        rows = conn.execute("SELECT * FROM webhooks WHERE user_id=? ORDER BY created_at", (user_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM webhooks ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def delete_webhook(conn, webhook_id: int) -> None:
    conn.execute("DELETE FROM webhooks WHERE id=?", (webhook_id,))
    conn.commit()


def get_active_webhooks(conn, event_type: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM webhooks WHERE active=1 AND events LIKE ?",
        (f"%{event_type}%",)
    ).fetchall()
    return [dict(r) for r in rows]


# ── Invites ───────────────────────────────────────────────────────────────────

def create_invite(conn, email: str, role: str = "user", team: str = "",
                  created_by: str = None, expires_days: int = 7) -> dict:
    from datetime import timedelta
    token      = uuid.uuid4().hex
    expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat()
    conn.execute(
        "INSERT INTO invites (token,email,role,team,created_by,expires_at) VALUES (?,?,?,?,?,?)",
        (token, email, role, team, created_by, expires_at),
    )
    conn.commit()
    return {"token": token, "email": email, "role": role, "team": team, "expires_at": expires_at}


def get_invite(conn, token: str) -> dict | None:
    row = conn.execute("SELECT * FROM invites WHERE token=?", (token,)).fetchone()
    if not row:
        return None
    d = dict(row)
    if d.get("used_at"):
        return None  # already used
    try:
        if datetime.fromisoformat(d["expires_at"]) < datetime.now(timezone.utc):
            return None  # expired
    except Exception:
        pass
    return d


def use_invite(conn, token: str) -> None:
    conn.execute("UPDATE invites SET used_at=? WHERE token=?", (_ts(), token))
    conn.commit()


def list_invites(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT i.*, u.email AS invited_by_email FROM invites i "
        "LEFT JOIN users u ON i.created_by=u.id ORDER BY i.expires_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


# ── Audit log ─────────────────────────────────────────────────────────────────

def log_audit(conn, user_id: str = None, email: str = None, action: str = "",
              resource_type: str = None, resource_id: str = None,
              detail: str = None) -> None:
    try:
        conn.execute(
            "INSERT INTO audit_log (ts,user_id,email,action,resource_type,resource_id,detail) "
            "VALUES (?,?,?,?,?,?,?)",
            (_ts(), user_id, email, action, resource_type, resource_id, detail),
        )
        conn.commit()
    except Exception:
        pass  # audit failure must never break the main flow


def get_audit_log(conn, days: int = 30, action: str = None,
                  limit: int = 200) -> list[dict]:
    params = [f"-{days} days"]
    where  = ["datetime(ts) >= datetime('now', ?, 'utc')"]
    if action:
        where.append("action LIKE ?")
        params.append(f"%{action}%")
    sql = (
        "SELECT * FROM audit_log WHERE " + " AND ".join(where)
        + " ORDER BY ts DESC LIMIT ?"
    )
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]
