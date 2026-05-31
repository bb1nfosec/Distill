"""
app.py — skim web server: dashboard + REST API.

Run:
    skim server [--port 7475] [--host 0.0.0.0]

Or with Docker:
    docker run -p 7475:7475 -e SKIM_ADMIN_EMAIL=you@corp.com ghcr.io/bb1nfosec/skim

Environment variables:
    SKIM_DB_PATH          Path to SQLite DB (default: ~/.skim/skim.db)
    SKIM_ADMIN_EMAIL      Auto-create admin user on first run
    SKIM_ADMIN_PASSWORD   Password for auto-created admin
    SKIM_JWT_SECRET       JWT signing secret (auto-generated if not set)
    SKIM_LDAP_URL         Enable LDAP auth (see server/auth.py for full config)
    SKIM_OIDC_*           Enable OIDC/OAuth2 (see server/auth.py for full config)
"""

import json
import os
import queue
import sys
import threading
from pathlib import Path
from functools import wraps

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

try:
    from flask import Flask, request, jsonify, redirect, render_template_string, session as flask_session
    from flask import send_from_directory
    _FLASK_OK = True
except ImportError:
    _FLASK_OK = False

from server.db import (
    connect, init_schema,
    create_user, get_user_by_email, get_user_by_id, list_users, delete_user,
    touch_last_login, purge_events,
    create_api_key, get_user_for_key, revoke_api_key,
    insert_event, stats_summary, stats_by_day, stats_by_user,
    stats_by_model, stats_by_hour, query_events, get_insights,
    set_budget, get_budget, list_budgets, delete_budget, check_budget,
    create_webhook, list_webhooks, delete_webhook,
    create_invite, get_invite, use_invite, list_invites,
    log_audit, get_audit_log,
)
from server.webhooks import fire as fire_webhooks
from server.auth import (
    issue_jwt, verify_jwt, hash_password, verify_password,
    ldap_authenticate, get_oidc_providers,
)

_STATIC = Path(__file__).parent / "static"

# ── SSE broadcast for server dashboard ───────────────────────────────────────
_srv_sse_clients: list[queue.Queue] = []
_srv_sse_lock    = threading.Lock()

def _srv_sse_broadcast(event: dict) -> None:
    data = f"data: {json.dumps({**event, 'type': 'event'})}\n\n".encode()
    with _srv_sse_lock:
        dead = []
        for q in _srv_sse_clients:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            try:
                _srv_sse_clients.remove(q)
            except ValueError:
                pass

# ── Login rate limiting (brute-force protection) ─────────────────────────────
# In-memory sliding window keyed by client IP. Each gunicorn worker keeps its
# own window; for strict org-wide limits, front with a shared store.
_login_hits: dict = {}
_login_lock = threading.Lock()
_LOGIN_MAX = int(os.environ.get("SKIM_LOGIN_MAX_ATTEMPTS", "10"))
_LOGIN_WINDOW = int(os.environ.get("SKIM_LOGIN_WINDOW_SEC", "300"))


def _rate_limited(ip: str) -> bool:
    import time as _t
    now = _t.time()
    with _login_lock:
        hits = [t for t in _login_hits.get(ip, []) if now - t < _LOGIN_WINDOW]
        hits.append(now)
        _login_hits[ip] = hits
        return len(hits) > _LOGIN_MAX


def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else (request.remote_addr or "unknown")


_PRICING = {
    "claude": 3.00, "claude-sonnet": 3.00, "claude-haiku": 0.80, "claude-opus": 15.00,
    "gpt-4o": 2.50, "gpt-4o-mini": 0.15,
    "gemini-1.5-pro": 1.25, "gemini-2.0-flash": 0.10,
    "ollama": 0.00,
}


def create_app(db_path: Path = None) -> "Flask":
    if not _FLASK_OK:
        raise ImportError("Flask not installed. Run: pip install 'skim-llm[web]'")

    app = Flask(__name__, static_folder=str(_STATIC), static_url_path="/static")
    app.secret_key = os.environ.get("SKIM_JWT_SECRET", os.urandom(32).hex())

    # Per-request connection via Flask g — new connection each request,
    # closed on teardown. WAL mode serialises concurrent writes safely.
    def get_db():
        from flask import g as _g
        if "db" not in _g:
            _g.db = connect(db_path)
        return _g.db

    @app.teardown_appcontext
    def close_db(exc=None):
        from flask import g as _g
        db_conn = _g.pop("db", None)
        if db_conn:
            db_conn.close()

    # Initialise schema on first connection
    _init_conn = connect(db_path)
    init_schema(_init_conn)
    _init_conn.close()

    # Auto-create admin on first run
    admin_email = os.environ.get("SKIM_ADMIN_EMAIL", "")
    if admin_email:
        _setup_conn = connect(db_path)
        if not get_user_by_email(_setup_conn, admin_email):
            pw = os.environ.get("SKIM_ADMIN_PASSWORD", "changeme")
            create_user(_setup_conn, admin_email, name="Admin", role="admin",
                        password_hash=hash_password(pw))
        _setup_conn.close()

    # ── Auth helpers ──────────────────────────────────────────────────────

    def _current_user():
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            if token.startswith("sk-skim-"):
                return get_user_for_key(get_db(), token)
            claims = verify_jwt(token)
            if claims:
                return get_user_by_id(get_db(), claims.get("sub", ""))
        return None

    def require_auth(f):
        @wraps(f)
        def wrapper(*a, **kw):
            user = _current_user()
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            request.user = user
            return f(*a, **kw)
        return wrapper

    def require_admin(f):
        @wraps(f)
        def wrapper(*a, **kw):
            user = _current_user()
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            if user.get("role") != "admin":
                return jsonify({"error": "Forbidden — admin required"}), 403
            request.user = user
            return f(*a, **kw)
        return wrapper

    def require_team_admin(f):
        """Allows admin and team_admin roles."""
        @wraps(f)
        def wrapper(*a, **kw):
            user = _current_user()
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            if user.get("role") not in ("admin", "team_admin"):
                return jsonify({"error": "Forbidden — team admin required"}), 403
            request.user = user
            return f(*a, **kw)
        return wrapper

    # ── Dashboard ─────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return redirect("/dashboard")

    @app.route("/dashboard")
    def dashboard():
        return send_from_directory(_STATIC, "dashboard.html")

    @app.route("/login")
    def login_page():
        providers = list(get_oidc_providers().keys())
        return send_from_directory(_STATIC, "login.html")

    # ── Auth API ──────────────────────────────────────────────────────────

    @app.route("/api/v1/auth/login", methods=["POST"])
    def login():
        ip = _client_ip()
        if _rate_limited(ip):
            return jsonify({"error": "Too many login attempts. Try again later."}), 429

        data  = request.get_json(silent=True) or {}
        email = data.get("email", "").strip()
        pw    = data.get("password", "")

        # LDAP first
        ldap_user = ldap_authenticate(email.split("@")[0], pw)
        if ldap_user:
            user = get_user_by_email(get_db(), ldap_user["email"])
            if not user:
                user = create_user(get_db(), ldap_user["email"], name=ldap_user["name"])
            token = issue_jwt({"sub": user["id"], "email": user["email"], "role": user["role"]})
            return jsonify({"token": token, "user": _safe_user(user)})

        # Local password
        user = get_user_by_email(get_db(), email)
        if not user or not verify_password(pw, user.get("password_hash", "")):
            return jsonify({"error": "Invalid credentials"}), 401

        token = issue_jwt({"sub": user["id"], "email": user["email"], "role": user["role"]})
        db = get_db()
        touch_last_login(db, user["id"])
        log_audit(db, user["id"], user["email"], "auth.login", detail=f"ip={ip}")
        return jsonify({"token": token, "user": _safe_user(user)})

    @app.route("/api/v1/auth/me")
    @require_auth
    def me():
        return jsonify({"user": _safe_user(request.user)})

    @app.route("/api/v1/auth/keys", methods=["GET", "POST"])
    @require_auth
    def api_keys():
        db = get_db()
        if request.method == "POST":
            data        = request.get_json(silent=True) or {}
            label       = data.get("label", "")
            scope       = data.get("scope", "ingest")
            expires_days = data.get("expires_days")
            if scope == "admin" and request.user["role"] != "admin":
                return jsonify({"error": "Only org admins can create admin-scoped keys"}), 403
            key = create_api_key(db, request.user["id"], label, scope, expires_days)
            log_audit(db, request.user["id"], request.user.get("email"),
                      "auth.key_created", "api_key", key[:12], f"scope={scope}")
            return jsonify({"key": key, "label": label, "scope": scope}), 201
        rows = db.execute(
            "SELECT key, label, scope, created_at, expires_at, last_used "
            "FROM api_keys WHERE user_id=?",
            (request.user["id"],)
        ).fetchall()
        return jsonify({"keys": [dict(r) for r in rows]})

    @app.route("/api/v1/auth/keys/<key_prefix>", methods=["DELETE"])
    @require_auth
    def revoke_key(key_prefix):
        db  = get_db()
        row = db.execute(
            "SELECT * FROM api_keys WHERE key LIKE ? AND user_id=?",
            (key_prefix + "%", request.user["id"])
        ).fetchone()
        if not row:
            if request.user["role"] == "admin":
                row = db.execute("SELECT * FROM api_keys WHERE key LIKE ?",
                                 (key_prefix + "%",)).fetchone()
        if not row:
            return jsonify({"error": "Key not found"}), 404
        revoke_api_key(db, row["key"])
        log_audit(db, request.user["id"], request.user.get("email"),
                  "auth.key_revoked", "api_key", row["key"][:12])
        return jsonify({"revoked": True})

    @app.route("/api/v1/auth/oidc/providers")
    def oidc_providers():
        return jsonify({"providers": list(get_oidc_providers().keys())})

    # ── Stats API ─────────────────────────────────────────────────────────

    @app.route("/api/v1/stats/summary")
    @require_auth
    def stats_summary_route():
        days = int(request.args.get("days", 7))
        uid  = None if request.user["role"] == "admin" else request.user["id"]
        data = stats_summary(get_db(), days, user_id=uid)
        return jsonify(data)

    @app.route("/api/v1/stats/daily")
    @require_auth
    def stats_daily():
        days = int(request.args.get("days", 30))
        return jsonify({"data": stats_by_day(get_db(), days)})

    @app.route("/api/v1/stats/by-user")
    @require_team_admin
    def stats_by_user_route():
        days = int(request.args.get("days", 30))
        data = stats_by_user(get_db(), days)
        # team_admin sees only their own team
        if request.user["role"] == "team_admin" and request.user.get("team"):
            data = [r for r in data if r.get("team") == request.user["team"]]
        return jsonify({"data": data})

    @app.route("/api/v1/stats/by-model")
    @require_auth
    def stats_by_model_route():
        days = int(request.args.get("days", 30))
        return jsonify({"data": stats_by_model(get_db(), days)})

    @app.route("/api/v1/stats/hourly")
    @require_auth
    def stats_hourly_route():
        days = int(request.args.get("days", 7))
        return jsonify({"data": stats_by_hour(get_db(), days)})

    @app.route("/api/v1/insights")
    @require_auth
    def insights_route():
        if request.user["role"] != "admin":
            return jsonify({"error": "Admin only"}), 403
        days = int(request.args.get("days", 30))
        return jsonify({"insights": get_insights(get_db(), days), "days": days})

    # ── Events ingestion (from proxy) ─────────────────────────────────────

    @app.route("/api/v1/events", methods=["POST"])
    @require_auth
    def ingest_event():
        data = request.get_json(silent=True) or {}
        data.setdefault("user_id", request.user["id"])
        model   = data.get("model", "claude")
        inp_tok = data.get("input_tokens", 0)
        rate    = _PRICING.get(model, 2.50)
        data.setdefault("cost_usd", inp_tok / 1_000_000 * rate)
        db  = get_db()
        eid = insert_event(db, data)
        _srv_sse_broadcast({**data, "id": eid})
        # Check budget thresholds and fire webhooks
        try:
            uid    = request.user["id"]
            team   = request.user.get("team")
            result = check_budget(db, uid, team)
            if result.get("at_warning") and not result.get("allowed") is False:
                fire_webhooks(db, "budget.warning", {
                    "user": request.user.get("email", uid),
                    "team": team, "pct_used": result["pct_used"],
                    "budget_type": result.get("budget_type"),
                })
            elif not result.get("allowed", True):
                fire_webhooks(db, "budget.exceeded", {
                    "user": request.user.get("email", uid),
                    "team": team, "reason": result.get("reason"),
                })
        except Exception:
            pass
        return jsonify({"id": eid}), 201

    @app.route("/skim/stream")
    @require_auth
    def sse_stream():
        from flask import Response, stream_with_context
        q: queue.Queue = queue.Queue(maxsize=50)
        with _srv_sse_lock:
            _srv_sse_clients.append(q)

        def generate():
            try:
                yield ":ok\n\n"
                while True:
                    try:
                        data = q.get(timeout=25)
                        yield data.decode()
                    except queue.Empty:
                        yield ":heartbeat\n\n"
            except GeneratorExit:
                pass
            finally:
                with _srv_sse_lock:
                    try:
                        _srv_sse_clients.remove(q)
                    except ValueError:
                        pass

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.route("/api/v1/events")
    @require_auth
    def list_events():
        days   = int(request.args.get("days", 7))
        limit  = min(int(request.args.get("limit", 100)), 500)
        offset = int(request.args.get("offset", 0))
        uid    = None if request.user["role"] == "admin" else request.user["id"]
        events = query_events(get_db(), days=days, user_id=uid, limit=limit, offset=offset)
        return jsonify({"events": events, "count": len(events)})

    # ── Registration via invite ───────────────────────────────────────────────

    @app.route("/invite/<token>")
    def invite_page(token):
        return send_from_directory(_STATIC, "invite.html")

    @app.route("/api/v1/auth/register", methods=["POST"])
    def register():
        data  = request.get_json(silent=True) or {}
        token = data.get("token", "").strip()
        name  = data.get("name",  "").strip()
        pw    = data.get("password", "")
        db    = get_db()
        inv   = get_invite(db, token)
        if not inv:
            return jsonify({"error": "Invalid or expired invite"}), 400
        if get_user_by_email(db, inv["email"]):
            return jsonify({"error": "Email already registered"}), 409
        if not pw or len(pw) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        user = create_user(db, inv["email"], name=name, team=inv["team"],
                           role=inv["role"], password_hash=hash_password(pw))
        use_invite(db, token)
        log_audit(db, user["id"], user["email"], "user.created",
                  "invite", token, f"role={inv['role']}")
        jwt = issue_jwt({"sub": user["id"], "email": user["email"], "role": user["role"]})
        return jsonify({"token": jwt, "user": _safe_user(user)}), 201

    @app.route("/api/v1/admin/invites", methods=["GET", "POST"])
    @require_admin
    def admin_invites():
        db = get_db()
        if request.method == "POST":
            data  = request.get_json(silent=True) or {}
            email = data.get("email", "").strip()
            if not email:
                return jsonify({"error": "email required"}), 400
            inv      = create_invite(db, email,
                                     role=data.get("role", "user"),
                                     team=data.get("team", ""),
                                     created_by=request.user["id"])
            base_url = request.host_url.rstrip("/")
            inv["invite_url"] = f"{base_url}/invite/{inv['token']}"
            log_audit(db, request.user["id"], request.user.get("email"),
                      "user.invited", "invite", inv["token"], f"→ {email}")
            return jsonify(inv), 201
        return jsonify({"invites": list_invites(db)})

    # ── Budget API ────────────────────────────────────────────────────────────

    @app.route("/api/v1/budget/check", methods=["POST"])
    @require_auth
    def budget_check():
        data   = request.get_json(silent=True) or {}
        uid    = data.get("user_id") or request.user["id"]
        tokens = int(data.get("input_tokens", 0))
        result = check_budget(get_db(), uid, estimated_tokens=tokens)
        if not result.get("allowed", True):
            return jsonify(result), 429
        return jsonify(result)

    @app.route("/api/v1/admin/budgets", methods=["GET"])
    @require_admin
    def admin_list_budgets():
        return jsonify({"budgets": list_budgets(get_db())})

    @app.route("/api/v1/admin/budgets", methods=["POST"])
    @require_admin
    def admin_set_budget():
        db   = get_db()
        data = request.get_json(silent=True) or {}
        b    = set_budget(db,
            owner_type   = data.get("owner_type", "user"),
            owner_id     = data.get("owner_id"),
            limit_tokens = data.get("limit_tokens"),
            limit_usd    = data.get("limit_usd"),
            period       = data.get("period", "monthly"),
            alert_pct    = float(data.get("alert_pct", 80)),
        )
        log_audit(db, request.user["id"], request.user.get("email"),
                  "budget.created", "budget", str(b.get("id")),
                  f"{data.get('owner_type')}:{data.get('owner_id')}")
        return jsonify({"budget": b}), 201

    @app.route("/api/v1/admin/budgets/<int:budget_id>", methods=["DELETE"])
    @require_admin
    def admin_delete_budget(budget_id):
        db = get_db()
        delete_budget(db, budget_id)
        log_audit(db, request.user["id"], request.user.get("email"),
                  "budget.deleted", "budget", str(budget_id))
        return jsonify({"deleted": True})

    # ── Webhook API ───────────────────────────────────────────────────────────

    @app.route("/api/v1/admin/webhooks", methods=["GET"])
    @require_admin
    def admin_list_webhooks():
        return jsonify({"webhooks": list_webhooks(get_db())})

    @app.route("/api/v1/admin/webhooks", methods=["POST"])
    @require_admin
    def admin_create_webhook():
        db   = get_db()
        data = request.get_json(silent=True) or {}
        url  = data.get("url", "").strip()
        if not url:
            return jsonify({"error": "url required"}), 400
        wh = create_webhook(db, request.user["id"],
            url     = url,
            channel = data.get("channel", "http"),
            events  = data.get("events", "budget.warning,budget.exceeded"),
            secret  = data.get("secret", ""),
        )
        log_audit(db, request.user["id"], request.user.get("email"),
                  "webhook.created", "webhook", str(wh.get("id")), url)
        return jsonify({"webhook": wh}), 201

    @app.route("/api/v1/admin/webhooks/<int:webhook_id>", methods=["DELETE"])
    @require_admin
    def admin_delete_webhook(webhook_id):
        db = get_db()
        delete_webhook(db, webhook_id)
        log_audit(db, request.user["id"], request.user.get("email"),
                  "webhook.deleted", "webhook", str(webhook_id))
        return jsonify({"deleted": True})

    # ── Export API ────────────────────────────────────────────────────────────

    @app.route("/api/v1/export/events.csv")
    @require_auth
    def export_events_csv():
        import csv, io
        db    = get_db()
        days  = int(request.args.get("days", 30))
        uid   = None if request.user["role"] == "admin" else request.user["id"]
        rows  = query_events(db, days=days, user_id=uid, limit=10000)
        buf   = io.StringIO()
        if rows:
            w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        from flask import Response
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=skim-events-{days}d.csv"},
        )

    @app.route("/api/v1/export/summary.json")
    @require_auth
    def export_summary_json():
        import datetime as _dt
        db   = get_db()
        days = int(request.args.get("days", 30))
        uid  = None if request.user["role"] == "admin" else request.user["id"]
        return jsonify({
            "generated_at": _dt.datetime.utcnow().isoformat() + "Z",
            "period_days":  days,
            "summary":      stats_summary(db, days, user_id=uid),
            "by_day":       stats_by_day(db, days),
            "by_model":     stats_by_model(db, days),
        })

    # ── Audit API ─────────────────────────────────────────────────────────────

    @app.route("/api/v1/admin/audit")
    @require_admin
    def admin_audit():
        days   = int(request.args.get("days", 30))
        action = request.args.get("action")
        limit  = min(int(request.args.get("limit", 200)), 1000)
        return jsonify({"log": get_audit_log(get_db(), days, action, limit)})

    @app.route("/api/v1/admin/purge", methods=["POST"])
    @require_admin
    def admin_purge():
        data       = request.get_json(silent=True) or {}
        older_than = int(data.get("older_than_days", 90))
        if older_than < 1:
            return jsonify({"error": "older_than_days must be >= 1"}), 400
        db      = get_db()
        removed = purge_events(db, older_than)
        log_audit(db, request.user["id"], request.user.get("email"),
                  "data.purged", "events", None, f"removed={removed} older_than={older_than}d")
        return jsonify({"removed": removed, "older_than_days": older_than})

    # ── Admin API ─────────────────────────────────────────────────────────────

    @app.route("/api/v1/admin/users")
    @require_admin
    def admin_list_users():
        users = list_users(get_db())
        return jsonify({"users": [_safe_user(u) for u in users]})

    @app.route("/api/v1/admin/users", methods=["POST"])
    @require_admin
    def admin_create_user():
        db   = get_db()
        data = request.get_json(silent=True) or {}
        if not data.get("email"):
            return jsonify({"error": "email required"}), 400
        pw   = data.get("password", "")
        user = create_user(
            db,
            email=data["email"],
            name=data.get("name", ""),
            team=data.get("team", ""),
            role=data.get("role", "user"),
            password_hash=hash_password(pw) if pw else "",
        )
        log_audit(db, request.user["id"], request.user.get("email"),
                  "user.created", "user", user["id"], data["email"])
        return jsonify({"user": _safe_user(user)}), 201

    @app.route("/api/v1/admin/users/<user_id>", methods=["DELETE"])
    @require_admin
    def admin_delete_user(user_id):
        db = get_db()
        u  = get_user_by_id(db, user_id)
        if not u:
            return jsonify({"error": "User not found"}), 404
        delete_user(db, user_id)
        log_audit(db, request.user["id"], request.user.get("email"),
                  "user.deleted", "user", user_id, u.get("email"))
        return jsonify({"deleted": True})

    @app.route("/api/v1/health")
    def health():
        try:
            from adapters import __version__
        except Exception:
            __version__ = "unknown"
        return jsonify({"status": "ok", "version": __version__})

    return app


def _safe_user(u: dict) -> dict:
    return {k: v for k, v in u.items() if k != "password_hash"}


def main():
    import argparse
    p = argparse.ArgumentParser(description="Start the skim web server")
    p.add_argument("--port", "-p", type=int, default=7475)
    p.add_argument("--host",        default="127.0.0.1",
                   help="Set to 0.0.0.0 to expose on all interfaces")
    p.add_argument("--db",          default="",
                   help="SQLite DB path (default: ~/.skim/skim.db)")
    args = p.parse_args()

    if not _FLASK_OK:
        print("Flask not installed. Run: pip install 'skim-llm[web]'", file=sys.stderr)
        sys.exit(1)

    db_path = Path(args.db).resolve() if args.db else None
    app     = create_app(db_path)

    BOLD="\033[1m"; CYAN="\033[96m"; YELLOW="\033[93m"; GREEN="\033[92m"
    DIM="\033[2m"; NC="\033[0m"
    W   = 62
    hp  = f"http://{args.host}:{args.port}"
    adm = os.environ.get("SKIM_ADMIN_EMAIL", "(set SKIM_ADMIN_EMAIL to auto-create admin)")

    def row(label, plain, colored):
        pad = W - 2 - len(label) - 2 - len(plain)
        print(f"  {BOLD}│{NC}  {DIM}{label}{NC}  {colored}{' '*max(pad,0)}{BOLD}│{NC}")

    def cmd(plain, colored):
        pad = W - 4 - len(plain)
        print(f"  {BOLD}│{NC}    {colored}{' '*max(pad,0)}{BOLD}│{NC}")

    print(f"\n  {BOLD}┌{'─'*W}┐{NC}")
    print(f"  {BOLD}│{NC}  {CYAN}{BOLD}skim server{NC} {DIM}v0.3.0{NC}  — org token intelligence{' '*(W-41)}{BOLD}│{NC}")
    print(f"  {BOLD}├{'─'*W}┤{NC}")
    row("dashboard", f"{hp}/dashboard",        f"{CYAN}{hp}/dashboard{NC}")
    row("api      ", f"{hp}/api/v1/health",    f"{DIM}{hp}/api/v1/health{NC}")
    row("admin    ", adm,                      f"{YELLOW}{adm}{NC}")
    print(f"  {BOLD}├{'─'*W}┤{NC}")
    print(f"  {BOLD}│{NC}  {YELLOW}Connect proxy to this server:{NC}{' '*(W-29)}{BOLD}│{NC}")
    cmd(f"export SKIM_SERVER_URL={hp}",      f"{CYAN}export SKIM_SERVER_URL={hp}{NC}")
    cmd( "export SKIM_SERVER_TOKEN=<key>",  f"{CYAN}export SKIM_SERVER_TOKEN={DIM}<generate in Settings>{NC}")
    print(f"  {BOLD}├{'─'*W}┤{NC}")
    footer = "Ctrl+C to stop"
    print(f"  {BOLD}│{NC}  {DIM}{footer}{NC}{' '*(W-2-len(footer))}{BOLD}│{NC}")
    print(f"  {BOLD}└{'─'*W}┘{NC}\n")

    # Prefer gunicorn for production; fall back to Flask dev server with warning
    try:
        from gunicorn.app.base import BaseApplication

        class _GApp(BaseApplication):
            def __init__(self, application, options=None):
                self.application = application
                self.options = options or {}
                super().__init__()
            def load_config(self):
                for k, v in self.options.items():
                    self.cfg.set(k, v)
            def load(self):
                return self.application

        _GApp(app, {
            "bind":    f"{args.host}:{args.port}",
            "workers": 4,
            "worker_class": "sync",
            "timeout": 120,
        }).run()
    except ImportError:
        print(
            f"\n  {YELLOW}⚠  Flask dev server — NOT for production.{NC}\n"
            f"  For production: pip install gunicorn && "
            f"gunicorn 'server.app:create_app()' -b {args.host}:{args.port} -w 4\n",
            file=sys.stderr,
        )
        app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
