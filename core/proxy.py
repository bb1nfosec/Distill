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

Usage:
    skim proxy [--port 7474] [--path .] [--model claude]

Then:
    export ANTHROPIC_BASE_URL=http://localhost:7474
    export OPENAI_BASE_URL=http://localhost:7474

Endpoints:
    GET  /health                → session stats JSON
    POST /v1/messages           → Anthropic Messages API
    POST /v1/chat/completions   → OpenAI Chat API
"""

import json
import os
import sys
import time
import warnings
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Lock, Thread

import urllib.request
import urllib.error

warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module=r"google\.api_core\._python_version_support",
)

sys.path.insert(0, str(Path(__file__).parent))

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


# ── Server reporting (fire-and-forget) ────────────────────────────────────────

def _report_to_server(event: dict) -> None:
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

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        if n:
            try: return json.loads(self.rfile.read(n))
            except Exception: pass
        return {}

    def _send(self, code: int, body: bytes, ct: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type",   ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self): self._send(200, b"")

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
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
        else:
            self._send(404, b'{"error": "not found"}')

    def do_POST(self):
        path = self.path.split("?")[0]
        body = self._body()
        if path == "/v1/messages":
            self._anthropic(body)
        elif path == "/v1/chat/completions":
            self._openai(body)
        else:
            self._send(404, json.dumps({"error": f"unknown: {path}"}).encode())

    # ── Anthropic ─────────────────────────────────────────────────────────────

    def _anthropic(self, body: dict) -> None:
        api_key = (self.headers.get("x-api-key") or
                   os.environ.get("ANTHROPIC_API_KEY", ""))
        if not api_key:
            self._send(401, b'{"error": "ANTHROPIC_API_KEY not set"}')
            return

        t0 = time.time()

        # Filter waste
        no_filter = os.environ.get("SKIM_NO_FILTER") or self.no_filter
        if not no_filter:
            filtered_msgs, saved = _filter_messages(body.get("messages", []))
            body = {**body, "messages": filtered_msgs}
        else:
            saved = 0

        # Inject prompt caching
        no_cache = os.environ.get("SKIM_NO_CACHE") or self.no_cache
        if not no_cache:
            body = _inject_caching(body)

        streaming = body.get("stream", False)
        if streaming:
            self._anthropic_stream(body, api_key, saved, t0)
        else:
            self._anthropic_sync(body, api_key, saved, t0)

    def _anthropic_sync(self, body: dict, api_key: str, saved: int, t0: float) -> None:
        status, resp = self._call_anthropic(body, api_key, self.headers.get("anthropic-beta", ""))

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

    def _anthropic_stream(self, body: dict, api_key: str, saved: int, t0: float) -> None:
        url  = "https://api.anthropic.com/v1/messages"
        data = json.dumps(body).encode()
        req  = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type",      "application/json")
        req.add_header("x-api-key",         api_key)
        req.add_header("anthropic-version", "2023-06-01")
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

    def _call_anthropic(self, body: dict, api_key: str, beta: str = "") -> tuple[int, dict]:
        url  = "https://api.anthropic.com/v1/messages"
        data = json.dumps(body).encode()
        req  = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type",      "application/json")
        req.add_header("x-api-key",         api_key)
        req.add_header("anthropic-version", "2023-06-01")
        if beta:
            req.add_header("anthropic-beta", beta)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
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
            return e.code, json.loads(e.read())
        except Exception as e:
            return 500, {"error": str(e)}


# ── Server entry point ────────────────────────────────────────────────────────

def serve(
    port:          int  = 7474,
    host:          str  = "127.0.0.1",
    project_path:  Path = None,
    context_limit: int  = 200_000,
    model:         str  = "claude",
    no_filter:     bool = False,
    no_cache:      bool = False,
) -> None:
    global _ticker_on

    _ProxyHandler.context_limit = context_limit
    _ProxyHandler.model         = model
    _ProxyHandler.no_filter     = no_filter
    _ProxyHandler.no_cache      = no_cache

    server = HTTPServer((host, port), _ProxyHandler)

    W = 62
    proj     = str(project_path or Path(".").resolve())[:42]
    hp       = f"http://{host}:{port}"
    filt_c   = f"{RED}off{NC} (--no-filter)"   if no_filter else f"{GREEN}on{NC} — strips waste from tool results"
    cache_c  = f"{RED}off{NC} (--no-cache)"    if no_cache  else f"{GREEN}on{NC} — auto-injects prompt caching"
    filt_l   = "off (--no-filter)"             if no_filter else "on — strips waste from tool results"
    cache_l  = "off (--no-cache)"              if no_cache  else "on — auto-injects prompt caching"
    model_l  = f"{model}  ({context_limit:,} token limit)"

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
    line("listening", hp,       f"{CYAN}{hp}{NC}")
    line("model    ", model_l,  f"{model}  {DIM}({context_limit:,} token limit){NC}")
    line("project  ", proj,     f"{DIM}{proj}{NC}")
    line("filtering", filt_l,   filt_c)
    line("caching  ", cache_l,  cache_c)
    print(f"  {BOLD}├{'─'*W}┤{NC}")
    print(f"  {BOLD}│{NC}  {YELLOW}Claude Code / Cursor:{NC}{' '*(W-21)}{BOLD}│{NC}")
    cmd_line(f"export ANTHROPIC_BASE_URL={hp}", f"{CYAN}export ANTHROPIC_BASE_URL={hp}{NC}")
    print(f"  {BOLD}│{NC}{' '*(W+2)}{BOLD}│{NC}")
    print(f"  {BOLD}│{NC}  {YELLOW}OpenAI-compatible tools:{NC}{' '*(W-25)}{BOLD}│{NC}")
    cmd_line(f"export OPENAI_BASE_URL={hp}", f"{CYAN}export OPENAI_BASE_URL={hp}{NC}")
    print(f"  {BOLD}├{'─'*W}┤{NC}")
    footer = f"health  {hp}/health   Ctrl+C to stop"
    print(f"  {BOLD}│{NC}  {DIM}{footer}{NC}{' '*(W-2-len(footer))}{BOLD}│{NC}")
    print(f"  {BOLD}└{'─'*W}┘{NC}\n")

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
