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
    connect, init_schema, create_user, get_user_by_email, get_user_by_id,
    create_api_key, get_user_for_key, insert_event,
    stats_summary, stats_by_day, stats_by_user, stats_by_model, stats_by_hour,
    query_events, get_insights,
)
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
        return jsonify({"token": token, "user": _safe_user(user)})

    @app.route("/api/v1/auth/me")
    @require_auth
    def me():
        return jsonify({"user": _safe_user(request.user)})

    @app.route("/api/v1/auth/keys", methods=["GET", "POST"])
    @require_auth
    def api_keys():
        if request.method == "POST":
            data  = request.get_json(silent=True) or {}
            label = data.get("label", "")
            key   = create_api_key(get_db(), request.user["id"], label)
            return jsonify({"key": key, "label": label}), 201
        # GET — list keys (masked)
        rows = get_db().execute(
            "SELECT key, label, created_at, last_used FROM api_keys WHERE user_id=?",
            (request.user["id"],)
        ).fetchall()
        return jsonify({"keys": [dict(r) for r in rows]})

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
    @require_auth
    def stats_by_user_route():
        if request.user["role"] != "admin":
            return jsonify({"error": "Admin only"}), 403
        days = int(request.args.get("days", 30))
        return jsonify({"data": stats_by_user(get_db(), days)})

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
        model    = data.get("model", "claude")
        inp_tok  = data.get("input_tokens", 0)
        rate     = _PRICING.get(model, 2.50)
        data.setdefault("cost_usd", inp_tok / 1_000_000 * rate)
        eid = insert_event(get_db(), data)
        _srv_sse_broadcast({**data, "id": eid})
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

    # ── Admin API ─────────────────────────────────────────────────────────

    @app.route("/api/v1/admin/users")
    @require_admin
    def admin_list_users():
        from server.db import list_users
        users = list_users(get_db())
        return jsonify({"users": [_safe_user(u) for u in users]})

    @app.route("/api/v1/admin/users", methods=["POST"])
    @require_admin
    def admin_create_user():
        data = request.get_json(silent=True) or {}
        if not data.get("email"):
            return jsonify({"error": "email required"}), 400
        pw = data.get("password", "")
        user = create_user(
            get_db(),
            email=data["email"],
            name=data.get("name", ""),
            team=data.get("team", ""),
            role=data.get("role", "user"),
            password_hash=hash_password(pw) if pw else "",
        )
        return jsonify({"user": _safe_user(user)}), 201

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
