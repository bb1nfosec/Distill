#!/usr/bin/env python3
"""
proxy.py — Runtime token interceptor + query optimizer.

Sits between any LLM tool (Claude Code, Cursor, custom apps) and the
Anthropic / OpenAI API. On every request it:

  1. Filters waste — strips lock files / build artifacts from tool results
  2. Injects prompt caching — adds cache_control to system prompt and large
     context blocks (Anthropic only). First call writes the cache, all
     subsequent calls read it — typically 50-90% cheaper on repeated context.
  3. Tracks actual token usage from API responses (not estimates).
  4. Passes through streaming SSE responses without buffering.
  5. Shows live session health in the console.
  6. Serves a local no-auth dashboard at /dashboard with real-time SSE updates.
  7. Persists every event to ~/.skim/events.db for the local dashboard.

Usage:
    skim proxy [--port 7474] [--path .] [--model claude] [--no-browser]

Then:
    export ANTHROPIC_BASE_URL=http://localhost:7474
    export OPENAI_BASE_URL=http://localhost:7474

Endpoints:
    GET  /health                → session stats JSON
    GET  /dashboard             → local no-auth dashboard (auto-opens in browser)
    GET  /skim/stream           → SSE stream of live events
    GET  /skim/data/*           → local analytics API (summary, daily, models, events)
    POST /v1/messages           → Anthropic Messages API
    POST /v1/chat/completions   → OpenAI Chat API
"""

import json
import os
import queue
import sys
import time
import warnings
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread, Timer

import urllib.request
import urllib.error

warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module=r"google\.api_core\._python_version_support",
)

sys.path.insert(0, str(Path(__file__).parent))

try:
    import local_store as _ls
    _LOCAL_STORE_OK = True
except ImportError:
    _LOCAL_STORE_OK = False

# ── Local dashboard HTML (served at /dashboard) ───────────────────────────
_DASHBOARD_PATH = Path(__file__).parent / "static" / "local_dashboard.html"
_DASHBOARD_HTML: bytes = b""

def _load_dashboard() -> None:
    global _DASHBOARD_HTML
    if _DASHBOARD_PATH.exists():
        _DASHBOARD_HTML = _DASHBOARD_PATH.read_bytes()
    else:
        _DASHBOARD_HTML = b"<h1>Dashboard not found</h1><p>core/static/local_dashboard.html missing.</p>"

# ── SSE subscriber list ───────────────────────────────────────────────────
_sse_clients: list[queue.Queue] = []
_sse_lock    = Lock()

def _sse_add(q: queue.Queue) -> None:
    with _sse_lock:
        _sse_clients.append(q)

def _sse_remove(q: queue.Queue) -> None:
    with _sse_lock:
        try:
            _sse_clients.remove(q)
        except ValueError:
            pass

def _sse_broadcast(event: dict) -> None:
    data = f"data: {json.dumps({**event, 'type': 'event'})}\n\n".encode()
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            try:
                _sse_clients.remove(q)
            except ValueError:
                pass

_WASTE_SIGNATURES = [
    ("package-lock.json", ['"lockfileVersion"',    '"resolved": "https://']),
    ("yarn.lock",         ["# yarn lockfile v1",   "resolved"]),
    ("pnpm-lock.yaml",    ["lockfileVersion:",      "resolution:"]),
    ("Cargo.lock",        ["@generated",            "[[package]]"]),
    ("poetry.lock",       ["@generated",            "[[package]]"]),
    ("composer.lock",     ['"content-hash":',       '"packages":']),
]


class _SessionState:
    def __init__(self):
        self.calls          = 0
        self.total_input    = 0
        self.total_output   = 0
        self.total_saved    = 0
        self.total_cached   = 0
        self._lock          = Lock()

    def record(self, inp: int, out: int, saved: int, cached: int = 0) -> None:
        with self._lock:
            self.calls        += 1
            self.total_input  += inp
            self.total_output += out
            self.total_saved  += saved
            self.total_cached += cached


_session    = _SessionState()
_print_lock = Lock()
_ticker_on  = True


# ── Event reporting (local store + SSE + optional remote server) ──────────────

def _report_local(event: dict) -> None:
    if _LOCAL_STORE_OK:
        try:
            _ls.record(event)
        except Exception:
            pass
    _sse_broadcast(event)


def _report_to_server(event: dict) -> None:
    _report_local(event)
    url   = os.environ.get("SKIM_SERVER_URL", "").rstrip("/")
    token = os.environ.get("SKIM_SERVER_TOKEN", "")
    if not url or not token:
        return
    try:
        data = json.dumps(event).encode()
        req  = urllib.request.Request(f"{url}/api/v1/events", data=data, method="POST")
        req.add_header("Content-Type",  "application/json")
        req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


def _report_bg(event: dict) -> None:
    Thread(target=_report_to_server, args=(event,), daemon=True).start()


# ── Token estimation ──────────────────────────────────────────────────────────

def _tok(text: str) -> int:
    try:
        import tiktoken
        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except ImportError:
        return max(1, len(text) // 4)


# ── Waste detection ───────────────────────────────────────────────────────────

def _detect_waste(content: str) -> tuple[bool, str]:
    for label, sigs in _WASTE_SIGNATURES:
        if all(s in content for s in sigs):
            return True, label
    return False, ""


def _filter_messages(messages: list) -> tuple[list, int]:
    """Strip known waste from tool_result blocks. Returns (filtered, tokens_saved)."""
    saved = 0
    out = []
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            out.append(msg)
            continue
        new_content = []
        for block in content:
            if (isinstance(block, dict)
                    and block.get("type") == "tool_result"
                    and isinstance(block.get("content"), str)
                    and len(block["content"]) > 1500):
                is_waste, label = _detect_waste(block["content"])
                if is_waste:
                    tok = _tok(block["content"])
                    saved += tok
                    new_content.append({
                        **block,
                        "content": (
                            f"[skim: stripped {label} ({tok:,} tokens). "
                            f"In .llmignore. Set SKIM_NO_FILTER=1 to disable.]"
                        ),
                    })
                    continue
            new_content.append(block)
        out.append({**msg, "content": new_content})
    return out, saved


# ── Prompt caching injection (Anthropic only) ─────────────────────────────────

def _inject_caching(body: dict) -> dict:
    """
    Transparently inject cache_control into system prompts and large context
    blocks. Uses Anthropic's prompt caching feature — first call incurs a
    25% write fee, all subsequent calls with the same content are free.

    Supports up to 4 cache breakpoints per request.
    """
    # 1. Cache the system prompt
    system = body.get("system")
    if isinstance(system, str) and len(system) > 100:
        body = {**body, "system": [
            {"type": "text", "text": system,
             "cache_control": {"type": "ephemeral"}}
        ]}
    elif isinstance(system, list) and system:
        # Already a list — ensure the last block has cache_control
        last = system[-1]
        if isinstance(last, dict) and not last.get("cache_control"):
            body = {**body, "system": system[:-1] + [
                {**last, "cache_control": {"type": "ephemeral"}}
            ]}

    # 2. Cache the two largest user messages (repeated context / file loads)
    messages = list(body.get("messages", []))
    candidates = [
        (i, len(msg.get("content", "")) if isinstance(msg.get("content"), str) else 0)
        for i, msg in enumerate(messages)
        if msg.get("role") == "user" and isinstance(msg.get("content"), str)
    ]
    for idx, _ in sorted(candidates, key=lambda x: -x[1])[:2]:
        msg = messages[idx]
        text = msg["content"]
        if len(text) > 500:   # only bother caching substantial content
            messages[idx] = {
                **msg,
                "content": [{
                    "type": "text", "text": text,
                    "cache_control": {"type": "ephemeral"},
                }],
            }
    if candidates:
        body = {**body, "messages": messages}

    return body


# ── Console output ────────────────────────────────────────────────────────────

BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
DIM    = "\033[2m"
NC     = "\033[0m"
ERASE  = "\033[2K\r"   # erase current line, return to start


def _fmt(n: int) -> str:
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}k"
    return str(n)


def _bar(used: int, limit: int, w: int = 20) -> str:
    pct  = min(used / max(limit, 1), 1.0)
    fill = int(pct * w)
    bar  = "█" * fill + "░" * (w - fill)
    c    = GREEN if pct < 0.5 else (YELLOW if pct < 0.8 else RED)
    return f"{c}{bar}{NC} {pct*100:.1f}%"


def _cost(inp: int, out: int) -> str:
    # claude-sonnet-4 rates (input $3/M, output $15/M)
    usd = (inp * 3 + out * 15) / 1_000_000
    return f"${usd:.4f}"


def _live_ticker(ctx_limit: int) -> None:
    """Daemon thread: redraws a single-line live status every 0.5s."""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    while _ticker_on:
        ts    = datetime.now().strftime("%H:%M:%S")
        calls = _session.calls
        saved = _session.total_saved
        cache = _session.total_cached
        inp   = _session.total_input
        out   = _session.total_output
        pct   = inp / max(ctx_limit, 1) * 100

        if calls == 0:
            status = f"{DIM}waiting for calls...{NC}"
        else:
            ctx_col = GREEN if pct < 50 else (YELLOW if pct < 80 else RED)
            status = (
                f"calls {BOLD}{calls}{NC}  "
                f"ctx {ctx_col}{pct:.1f}%{NC}  "
                f"saved {GREEN}{_fmt(saved)}{NC}  "
                f"cached {CYAN}{_fmt(cache)}{NC}  "
                f"cost {YELLOW}{_cost(inp, out)}{NC}"
            )

        spin = f"{CYAN}{frames[i % len(frames)]}{NC}"
        line = f"  {spin} {BOLD}LIVE{NC}  {ts}  {status}"

        with _print_lock:
            sys.stdout.write(f"{ERASE}{line}")
            sys.stdout.flush()

        i += 1
        time.sleep(0.5)

    sys.stdout.write(ERASE)
    sys.stdout.flush()


def _print_health(inp: int, out: int, saved: int, cached: int, ms: int,
                  ctx_limit: int) -> None:
    total = _session.total_input
    pct   = total / max(ctx_limit, 1)
    ts    = datetime.now().strftime("%H:%M:%S")

    extras = []
    if saved  > 0: extras.append(f"{GREEN}▼ stripped {_fmt(saved)}{NC}")
    if cached > 0: extras.append(f"{CYAN}◈ cached {_fmt(cached)}{NC}")

    with _print_lock:
        sys.stdout.write(ERASE)
        print(f"{BOLD}[skim]{NC} {ts}  call #{_session.calls}  {DIM}{ms}ms{NC}")
        print(f"  ctx  {_bar(total, ctx_limit)}  {DIM}{_fmt(total)}/{_fmt(ctx_limit)}{NC}")
        call_line = f"  in {_fmt(inp)}  out {_fmt(out)}  cost {_cost(inp, out)}"
        if extras:
            call_line += "   " + "  ".join(extras)
        print(call_line)
        if pct > 0.85:
            print(f"  {RED}{BOLD}⚠  {pct*100:.0f}% full — /compact NOW{NC}")
        elif pct > 0.65:
            print(f"  {YELLOW}→  {pct*100:.0f}% full — consider /compact soon{NC}")
        print()


# ── HTTP handler ──────────────────────────────────────────────────────────────

class _ProxyHandler(BaseHTTPRequestHandler):
    context_limit: int  = 200_000
    model:         str  = "claude"
    no_filter:     bool = False
    no_cache:      bool = False

    def log_message(self, *_): pass

    def _raw_body(self) -> bytes:
        n = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(n) if n else b""

    def _body(self) -> dict:
        raw = self._raw_body()
        try:
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    def _send(self, code: int, body: bytes, ct: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type",   ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        # Local dashboard
        if path == "/dashboard":
            self._send(200, _DASHBOARD_HTML, "text/html; charset=utf-8")
            return

        # Redirect root to dashboard
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/dashboard")
            self.end_headers()
            return

        # SSE live event stream
        if path == "/skim/stream":
            self._sse_stream()
            return

        # Local analytics data API (no auth — localhost only)
        if path.startswith("/skim/data/"):
            self._local_data(path, self.path)
            return

        # Health check
        if path == "/health":
            try:
                from adapters import __version__
            except Exception:
                __version__ = "0.2.0"
            self._send(200, json.dumps({
                "status":  "ok",
                "version": __version__,
                "session": {
                    "calls":         _session.calls,
                    "input_tokens":  _session.total_input,
                    "output_tokens": _session.total_output,
                    "saved_tokens":  _session.total_saved,
                    "cached_tokens": _session.total_cached,
                    "context_pct":   round(_session.total_input / max(self.context_limit, 1) * 100, 1),
                },
            }).encode())
            return

        self._passthrough("GET")

    def _sse_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type",  "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection",    "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        q: queue.Queue = queue.Queue(maxsize=50)
        _sse_add(q)
        try:
            # Send initial heartbeat so browser knows connection is alive
            self.wfile.write(b":ok\n\n")
            self.wfile.flush()
            while True:
                try:
                    data = q.get(timeout=25)
                    self.wfile.write(data)
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b":heartbeat\n\n")
                    self.wfile.flush()
        except Exception:
            pass
        finally:
            _sse_remove(q)

    def _local_data(self, path: str, full_path: str) -> None:
        if not _LOCAL_STORE_OK:
            self._send(503, b'{"error":"local_store not available"}')
            return

        from urllib.parse import urlparse, parse_qs
        qs   = parse_qs(urlparse(full_path).query)
        days = int(qs.get("days",  ["30"])[0])
        lim  = int(qs.get("limit", ["200"])[0])

        endpoint = path.removeprefix("/skim/data/").split("/")[0]
        try:
            if endpoint == "summary":
                data = _ls.summary(days)
            elif endpoint == "daily":
                data = _ls.by_day(days)
            elif endpoint == "hourly":
                data = _ls.by_hour(days)
            elif endpoint == "models":
                data = _ls.by_model(days)
            elif endpoint == "events":
                data = _ls.recent_events(days, lim)
            else:
                self._send(404, b'{"error":"unknown endpoint"}')
                return
            self._send(200, json.dumps(data).encode())
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}).encode())

    def do_POST(self):
        path = self.path.split("?")[0]
        raw  = self._raw_body()
        if path == "/v1/messages":
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {}
            self._anthropic(body)
        elif path == "/v1/chat/completions":
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {}
            self._openai(body)
        else:
            self._passthrough("POST", raw)

    def _passthrough(self, method: str, raw: bytes = b"") -> None:
        """Transparently forward any unrecognised path to the real upstream API."""
        plan, credential = self._auth_type()
        openai_auth = (self.headers.get("Authorization") or "").strip()
        openai_key  = openai_auth.removeprefix("Bearer ").strip() or os.environ.get("OPENAI_API_KEY", "")

        if plan:
            upstream = "https://api.anthropic.com"
        elif openai_key:
            upstream = "https://api.openai.com"
        else:
            self._send(404, json.dumps({"error": f"no upstream for {self.path}"}).encode())
            return

        url = upstream + self.path
        req = urllib.request.Request(url, data=raw or None, method=method)
        ct  = self.headers.get("Content-Type", "application/json")
        req.add_header("Content-Type", ct)
        if plan == "apikey":
            req.add_header("x-api-key", credential)
            req.add_header("anthropic-version", self.headers.get("anthropic-version", "2023-06-01"))
            beta = self.headers.get("anthropic-beta", "")
            if beta:
                req.add_header("anthropic-beta", beta)
        elif plan == "oauth":
            req.add_header("Authorization", credential)
            req.add_header("anthropic-version", self.headers.get("anthropic-version", "2023-06-01"))
        elif openai_key:
            req.add_header("Authorization", f"Bearer {openai_key}")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
                self.send_response(r.status)
                self.send_header("Content-Type",   r.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type",   "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._send(502, json.dumps({"error": str(e)}).encode())

    # ── Anthropic ─────────────────────────────────────────────────────────────

    def _auth_type(self) -> tuple[str, str]:
        """
        Detect which Anthropic plan the caller is on.
        Returns ('apikey', key) for API key plans, ('oauth', bearer) for Pro/OAuth plans,
        or ('', '') if no valid auth is present.
        Extend this method to support future plan types (enterprise SSO, team tokens, etc.).
        """
        api_key = self.headers.get("x-api-key") or os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            return "apikey", api_key
        auth = (self.headers.get("Authorization") or "").strip()
        if auth.startswith("Bearer "):
            return "oauth", auth
        return "", ""

    def _anthropic(self, body: dict) -> None:
        plan, credential = self._auth_type()
        if not plan:
            self._send(401, b'{"error": "No Anthropic auth: set ANTHROPIC_API_KEY (API plan) or start via Claude Pro login (OAuth plan)"}')
            return

        t0 = time.time()

        # Waste filtering — all plans benefit
        no_filter = os.environ.get("SKIM_NO_FILTER") or self.no_filter
        if not no_filter:
            filtered_msgs, saved = _filter_messages(body.get("messages", []))
            body = {**body, "messages": filtered_msgs}
        else:
            saved = 0

        # Prompt caching injection — API key plan only
        # Pro/OAuth plan has its own caching layer; injecting cache_control breaks it
        no_cache = os.environ.get("SKIM_NO_CACHE") or self.no_cache
        if not no_cache and plan == "apikey":
            body = _inject_caching(body)

        streaming = body.get("stream", False)
        if streaming:
            self._anthropic_stream(body, plan, credential, saved, t0)
        else:
            self._anthropic_sync(body, plan, credential, saved, t0)

    def _anthropic_sync(self, body: dict, plan: str, credential: str, saved: int, t0: float) -> None:
        status, resp = self._call_anthropic(body, plan, credential, self.headers.get("anthropic-beta", ""))

        usage  = resp.get("usage", {})
        inp    = usage.get("input_tokens",         0)
        out    = usage.get("output_tokens",         0)
        cached = usage.get("cache_read_input_tokens", 0)
        ms     = int((time.time() - t0) * 1000)

        _session.record(inp, out, saved, cached)
        _print_health(inp, out, saved, cached, ms, self.context_limit)
        _report_bg({
            "provider": "anthropic", "model": body.get("model", "claude"),
            "input_tokens": inp, "output_tokens": out,
            "saved_tokens": saved, "cached_tokens": cached,
            "cost_usd": (inp * 3 + out * 15) / 1_000_000,
            "latency_ms": ms, "session_id": id(_session),
        })
        self._send(status, json.dumps(resp).encode())

    def _anthropic_stream(self, body: dict, plan: str, credential: str, saved: int, t0: float) -> None:
        url  = "https://api.anthropic.com/v1/messages"
        data = json.dumps(body).encode()
        req  = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type",      "application/json")
        req.add_header("anthropic-version", "2023-06-01")
        if plan == "apikey":
            req.add_header("x-api-key", credential)
        else:
            req.add_header("Authorization", credential)
        beta = self.headers.get("anthropic-beta", "")
        if beta:
            req.add_header("anthropic-beta", beta)

        self.send_response(200)
        self.send_header("Content-Type",  "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection",    "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        inp = out = cached = 0
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for raw in resp:
                    self.wfile.write(raw)
                    self.wfile.flush()
                    if raw.startswith(b"data: ") and raw.strip() != b"data: [DONE]":
                        try:
                            ev = json.loads(raw[6:])
                            t  = ev.get("type", "")
                            if t == "message_start":
                                u = ev.get("message", {}).get("usage", {})
                                inp    = u.get("input_tokens",              0)
                                cached = u.get("cache_read_input_tokens",   0)
                            elif t == "message_delta":
                                out = ev.get("usage", {}).get("output_tokens", 0)
                        except Exception:
                            pass
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read())
            except Exception:
                err_body = {"message": str(e)}
            err = f'data: {json.dumps({"type":"error","error":err_body,"status":e.code})}\n\n'
            try:
                self.wfile.write(err.encode()); self.wfile.flush()
            except Exception:
                pass
        except Exception as e:
            err = f'data: {json.dumps({"type":"error","error":str(e)})}\n\n'
            try:
                self.wfile.write(err.encode()); self.wfile.flush()
            except Exception:
                pass

        ms = int((time.time() - t0) * 1000)
        _session.record(inp, out, saved, cached)
        _print_health(inp, out, saved, cached, ms, self.context_limit)
        _report_bg({
            "provider": "anthropic", "model": body.get("model", "claude"),
            "input_tokens": inp, "output_tokens": out,
            "saved_tokens": saved, "cached_tokens": cached,
            "cost_usd": (inp * 3 + out * 15) / 1_000_000,
            "latency_ms": ms, "session_id": id(_session),
        })

    def _call_anthropic(self, body: dict, plan: str, credential: str, beta: str = "") -> tuple[int, dict]:
        url  = "https://api.anthropic.com/v1/messages"
        data = json.dumps(body).encode()
        req  = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type",      "application/json")
        req.add_header("anthropic-version", "2023-06-01")
        if plan == "apikey":
            req.add_header("x-api-key", credential)
        else:
            req.add_header("Authorization", credential)
        if beta:
            req.add_header("anthropic-beta", beta)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read())
            except Exception:
                return e.code, {"error": {"type": "http_error", "message": str(e)}}
        except Exception as e:
            return 500, {"error": str(e)}

    # ── OpenAI ────────────────────────────────────────────────────────────────

    def _openai(self, body: dict) -> None:
        api_key = (
            (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
            or os.environ.get("OPENAI_API_KEY", "")
        )
        if not api_key:
            self._send(401, b'{"error": "OPENAI_API_KEY not set"}')
            return

        t0 = time.time()
        streaming = body.get("stream", False)

        if streaming:
            self._openai_stream(body, api_key, t0)
        else:
            status, resp = self._call_openai(body, api_key)
            usage  = resp.get("usage", {})
            inp    = usage.get("prompt_tokens",     0)
            out    = usage.get("completion_tokens", 0)
            ms     = int((time.time() - t0) * 1000)
            _session.record(inp, out, 0, 0)
            _print_health(inp, out, 0, 0, ms, self.context_limit)
            _report_bg({
                "provider": "openai", "model": body.get("model", "gpt-4o"),
                "input_tokens": inp, "output_tokens": out,
                "cost_usd": (inp * 2.5 + out * 10) / 1_000_000,
                "latency_ms": ms, "session_id": id(_session),
            })
            self._send(status, json.dumps(resp).encode())

    def _openai_stream(self, body: dict, api_key: str, t0: float) -> None:
        url  = "https://api.openai.com/v1/chat/completions"
        data = json.dumps(body).encode()
        req  = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type",  "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")

        self.send_response(200)
        self.send_header("Content-Type",  "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection",    "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        inp = out = 0
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for raw in resp:
                    self.wfile.write(raw)
                    self.wfile.flush()
                    if raw.startswith(b"data: ") and raw.strip() != b"data: [DONE]":
                        try:
                            ev = json.loads(raw[6:])
                            u  = ev.get("usage") or {}
                            if u:
                                inp = u.get("prompt_tokens",     inp)
                                out = u.get("completion_tokens", out)
                        except Exception:
                            pass
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read())
            except Exception:
                err_body = {"message": str(e)}
            err = f'data: {json.dumps({"error": err_body, "status": e.code})}\n\n'
            try:
                self.wfile.write(err.encode()); self.wfile.flush()
            except Exception:
                pass
        except Exception as e:
            err = f'data: {json.dumps({"error": str(e)})}\n\n'
            try:
                self.wfile.write(err.encode()); self.wfile.flush()
            except Exception:
                pass

        ms = int((time.time() - t0) * 1000)
        _session.record(inp, out, 0, 0)
        _print_health(inp, out, 0, 0, ms, self.context_limit)
        _report_bg({
            "provider": "openai", "model": body.get("model", "gpt-4o"),
            "input_tokens": inp, "output_tokens": out,
            "cost_usd": (inp * 2.5 + out * 10) / 1_000_000,
            "latency_ms": ms, "session_id": id(_session),
        })

    def _call_openai(self, body: dict, api_key: str) -> tuple[int, dict]:
        url  = "https://api.openai.com/v1/chat/completions"
        data = json.dumps(body).encode()
        req  = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type",  "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read())
            except Exception:
                return e.code, {"error": {"type": "http_error", "message": str(e)}}
        except Exception as e:
            return 500, {"error": str(e)}


# ── HTTP server with address reuse ────────────────────────────────────────────

class _ReuseHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads      = True


# ── Server entry point ────────────────────────────────────────────────────────

def serve(
    port:          int  = 7474,
    host:          str  = "127.0.0.1",
    project_path:  Path = None,
    context_limit: int  = 200_000,
    model:         str  = "claude",
    no_filter:     bool = False,
    no_cache:      bool = False,
    no_browser:    bool = False,
) -> None:
    global _ticker_on

    # Init local event store and load dashboard HTML
    if _LOCAL_STORE_OK:
        try:
            _ls.init()
        except Exception:
            pass
    _load_dashboard()

    _ProxyHandler.context_limit = context_limit
    _ProxyHandler.model         = model
    _ProxyHandler.no_filter     = no_filter
    _ProxyHandler.no_cache      = no_cache

    try:
        server = _ReuseHTTPServer((host, port), _ProxyHandler)
    except OSError as e:
        print(f"\n  {RED}✗ Cannot bind to {host}:{port} — {e}{NC}")
        print(f"  {DIM}Is another instance running? Try: skim proxy --port {port + 1}{NC}\n")
        return

    W = 62
    proj      = str(project_path or Path(".").resolve())[:42]
    hp        = f"http://{host}:{port}"
    dash_url  = f"{hp}/dashboard"
    filt_c    = f"{RED}off{NC} (--no-filter)"   if no_filter else f"{GREEN}on{NC} — strips waste from tool results"
    cache_c   = f"{RED}off{NC} (--no-cache)"    if no_cache  else f"{GREEN}on{NC} — auto-injects prompt caching"
    filt_l    = "off (--no-filter)"             if no_filter else "on — strips waste from tool results"
    cache_l   = "off (--no-cache)"              if no_cache  else "on — auto-injects prompt caching"
    model_l   = f"{model}  ({context_limit:,} token limit)"

    def line(label: str, plain: str, colored: str) -> None:
        pad = W - 2 - len(label) - 2 - len(plain)
        print(f"  {BOLD}│{NC}  {DIM}{label}{NC}  {colored}{' '*max(pad,0)}{BOLD}│{NC}")

    def cmd_line(plain: str, colored: str) -> None:
        pad = W - 4 - len(plain)
        print(f"  {BOLD}│{NC}    {colored}{' '*max(pad,0)}{BOLD}│{NC}")

    try:
        from adapters import __version__ as _ver
    except Exception:
        _ver = "0.3.0"

    print(f"\n  {BOLD}┌{'─'*W}┐{NC}")
    print(f"  {BOLD}│{NC}  {CYAN}{BOLD}skim{NC} {DIM}v{_ver}{NC}  — runtime token proxy{' '*(W-32-len(_ver))}{BOLD}│{NC}")
    print(f"  {BOLD}├{'─'*W}┤{NC}")
    line("listening", hp,        f"{CYAN}{hp}{NC}")
    line("dashboard", dash_url,  f"{CYAN}{dash_url}{NC}")
    line("model    ", model_l,   f"{model}  {DIM}({context_limit:,} token limit){NC}")
    line("project  ", proj,      f"{DIM}{proj}{NC}")
    line("filtering", filt_l,    filt_c)
    line("caching  ", cache_l,   cache_c)
    print(f"  {BOLD}├{'─'*W}┤{NC}")
    print(f"  {BOLD}│{NC}  {YELLOW}Claude Code / Cursor:{NC}{' '*(W-21)}{BOLD}│{NC}")
    cmd_line(f"export ANTHROPIC_BASE_URL={hp}", f"{CYAN}export ANTHROPIC_BASE_URL={hp}{NC}")
    print(f"  {BOLD}│{NC}{' '*(W+2)}{BOLD}│{NC}")
    print(f"  {BOLD}│{NC}  {YELLOW}OpenAI-compatible tools:{NC}{' '*(W-25)}{BOLD}│{NC}")
    cmd_line(f"export OPENAI_BASE_URL={hp}", f"{CYAN}export OPENAI_BASE_URL={hp}{NC}")
    print(f"  {BOLD}├{'─'*W}┤{NC}")
    footer = f"Ctrl+C to stop   data → ~/.skim/events.db"
    print(f"  {BOLD}│{NC}  {DIM}{footer}{NC}{' '*(W-2-len(footer))}{BOLD}│{NC}")
    print(f"  {BOLD}└{'─'*W}┘{NC}\n")

    if not no_browser:
        Timer(1.5, lambda: webbrowser.open(dash_url)).start()

    _ticker_on = True
    ticker = Thread(target=_live_ticker, args=(context_limit,), daemon=True)
    ticker.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _ticker_on = False
        ticker.join(timeout=1)
        server.server_close()

    usd_total = (_session.total_input * 3 + _session.total_output * 15) / 1_000_000
    saved_usd = _session.total_saved * 3 / 1_000_000

    print(f"\n  {BOLD}Session summary{NC}  {DIM}───────────────────────────────{NC}")
    print(f"  API calls       {BOLD}{_session.calls}{NC}")
    print(f"  Tokens in/out   {_fmt(_session.total_input)} / {_fmt(_session.total_output)}")
    print(f"  Est. cost       {YELLOW}{_cost(_session.total_input, _session.total_output)}{NC}")
    print(f"  Waste stripped  {GREEN}{_fmt(_session.total_saved)} tokens  (saved ~${saved_usd:.4f}){NC}")
    print(f"  Cache hits      {CYAN}{_fmt(_session.total_cached)} tokens{NC}")
    print()


def main():
    import argparse
    sys.path.insert(0, str(Path(__file__).parent))
    from token_counter import CONTEXT_LIMITS
    p = argparse.ArgumentParser(description="Start the skim runtime token proxy")
    p.add_argument("--port",      "-p", type=int, default=7474)
    p.add_argument("--host",            default="127.0.0.1")
    p.add_argument("--path",            default=".", help="Project root for .llmignore rules")
    p.add_argument("--model",     "-m", default="claude")
    p.add_argument("--no-filter",       action="store_true")
    p.add_argument("--no-cache",        action="store_true",
                   help="Disable automatic prompt caching injection")
    args = p.parse_args()
    limit = CONTEXT_LIMITS.get(args.model, 200_000)
    serve(args.port, args.host, Path(args.path).resolve(), limit,
          args.model, args.no_filter, args.no_cache)


if __name__ == "__main__":
    main()
