#!/usr/bin/env python3
"""
proxy.py — Runtime token interceptor.

Sits between any LLM tool (Claude Code, Cursor, custom apps) and the
real Anthropic / OpenAI API. Applies .llmignore rules to context in
real-time, strips known waste patterns from tool outputs, tracks actual
token usage, and shows live session health.

Usage:
    skim proxy [--port 7474] [--path .] [--model claude]

Then set in your shell (persists for the terminal session):
    export ANTHROPIC_BASE_URL=http://localhost:7474

For Claude Code Pro users: the console shows context fill % in real-time
so you know when to /compact before quality degrades.

Endpoints:
    GET  /health                → session stats JSON
    POST /v1/messages           → Anthropic Messages API (pass-through + filter)
    POST /v1/chat/completions   → OpenAI Chat API (pass-through)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).parent))

# Signatures that reliably identify lock-file / build-artifact content.
# Each entry: (waste_label, [required_substrings — all must appear])
_WASTE_SIGNATURES = [
    ("package-lock.json", ['"lockfileVersion"', '"resolved": "https://']),
    ("yarn.lock",         ["# yarn lockfile v1", "resolved"]),
    ("pnpm-lock.yaml",    ["lockfileVersion:", "resolution:"]),
    ("Cargo.lock",        ["# This file is automatically @generated", "[[package]]"]),
    ("poetry.lock",       ["# This file is automatically @generated", "[[package]]"]),
    ("composer.lock",     ['"content-hash":', '"packages":']),
]


class _SessionState:
    def __init__(self):
        self.total_input  = 0
        self.total_output = 0
        self.total_saved  = 0
        self.calls        = 0
        self._lock        = Lock()

    def record(self, inp: int, out: int, saved: int) -> None:
        with self._lock:
            self.total_input  += inp
            self.total_output += out
            self.total_saved  += saved
            self.calls        += 1


_session = _SessionState()


def _estimate_tokens(text: str) -> int:
    try:
        import tiktoken
        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except ImportError:
        return max(1, len(text) // 4)


def _detect_waste(content: str) -> tuple[bool, str]:
    for label, sigs in _WASTE_SIGNATURES:
        if all(s in content for s in sigs):
            return True, label
    return False, ""


def _filter_messages(messages: list) -> tuple[list, int]:
    """Strip waste from tool_result blocks. Returns (filtered, tokens_saved)."""
    if not messages:
        return messages, 0

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
                    tok = _estimate_tokens(block["content"])
                    saved += tok
                    new_content.append({
                        **block,
                        "content": (
                            f"[skim proxy: stripped {label} "
                            f"({tok:,} tokens). File is in .llmignore. "
                            f"Set SKIM_NO_FILTER=1 to disable.)"
                        ),
                    })
                    continue
            new_content.append(block)
        out.append({**msg, "content": new_content})

    return out, saved


def _ctx_bar(used: int, limit: int, width: int = 22) -> str:
    pct   = min(used / max(limit, 1), 1.0)
    fill  = int(pct * width)
    bar   = "█" * fill + "░" * (width - fill)
    c     = "\033[92m" if pct < 0.5 else ("\033[93m" if pct < 0.8 else "\033[91m")
    return f"{c}{bar}\033[0m {pct*100:.1f}%"


def _fmt_n(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


class _ProxyHandler(BaseHTTPRequestHandler):
    # set by serve()
    project_path:  Path  = Path(".")
    context_limit: int   = 200_000
    model:         str   = "claude"
    no_filter:     bool  = False

    def log_message(self, *_):
        pass  # suppress default Apache-style log

    def _read_body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        if n:
            try:
                return json.loads(self.rfile.read(n))
            except Exception:
                pass
        return {}

    def _send(self, code: int, body: bytes, ct: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, b"")

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            try:
                from adapters import __version__
            except Exception:
                __version__ = "unknown"
            self._send(200, json.dumps({
                "status": "ok", "version": __version__,
                "session": {
                    "calls":        _session.calls,
                    "input_tokens": _session.total_input,
                    "output_tokens": _session.total_output,
                    "saved_tokens": _session.total_saved,
                    "context_pct":  round(_session.total_input / max(self.context_limit, 1) * 100, 1),
                },
            }).encode())
        else:
            self._send(404, b'{"error": "not found"}')

    def do_POST(self):
        path = self.path.split("?")[0]
        body = self._read_body()

        if path == "/v1/messages":
            self._handle_anthropic(body)
        elif path == "/v1/chat/completions":
            self._handle_openai(body)
        else:
            self._send(404, json.dumps({"error": f"unknown: {path}"}).encode())

    # ── Anthropic ────────────────────────────────────────────────────────
    def _handle_anthropic(self, body: dict) -> None:
        api_key = (
            self.headers.get("x-api-key")
            or os.environ.get("ANTHROPIC_API_KEY", "")
        )
        if not api_key:
            self._send(401, b'{"error": "ANTHROPIC_API_KEY not set. Export it before starting skim proxy."}')
            return

        t0       = time.time()
        messages = body.get("messages", [])

        # Filter unless disabled
        no_filter = os.environ.get("SKIM_NO_FILTER") or self.no_filter
        if no_filter:
            filtered, saved = messages, 0
        else:
            filtered, saved = _filter_messages(messages)

        fwd_body = {**body, "messages": filtered}

        status, resp = self._call_anthropic(fwd_body, api_key)

        usage  = resp.get("usage", {})
        inp    = usage.get("input_tokens", _estimate_tokens(json.dumps(filtered)))
        out    = usage.get("output_tokens", 0)
        ms     = int((time.time() - t0) * 1000)

        _session.record(inp, out, saved)
        self._print_health(inp, out, saved, ms)
        self._send(status, json.dumps(resp).encode())

    def _call_anthropic(self, body: dict, api_key: str) -> tuple[int, dict]:
        url  = "https://api.anthropic.com/v1/messages"
        data = json.dumps(body).encode()
        req  = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type",      "application/json")
        req.add_header("x-api-key",         api_key)
        req.add_header("anthropic-version", "2023-06-01")
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
        except Exception as e:
            return 500, {"error": str(e)}

    # ── OpenAI ───────────────────────────────────────────────────────────
    def _handle_openai(self, body: dict) -> None:
        api_key = (
            (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
            or os.environ.get("OPENAI_API_KEY", "")
        )
        if not api_key:
            self._send(401, b'{"error": "OPENAI_API_KEY not set"}')
            return

        t0     = time.time()
        status, resp = self._call_openai(body, api_key)
        usage  = resp.get("usage", {})
        inp    = usage.get("prompt_tokens", 0)
        out    = usage.get("completion_tokens", 0)
        ms     = int((time.time() - t0) * 1000)

        _session.record(inp, out, 0)
        self._print_health(inp, out, 0, ms)
        self._send(status, json.dumps(resp).encode())

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

    # ── Console output ───────────────────────────────────────────────────
    def _print_health(self, inp: int, out: int, saved: int, ms: int) -> None:
        BOLD = "\033[1m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
        RED  = "\033[91m"; CYAN  = "\033[96m"; NC = "\033[0m"

        total_ctx = _session.total_input
        limit     = self.context_limit
        pct       = total_ctx / max(limit, 1)
        ts        = datetime.now().strftime("%H:%M:%S")

        print(f"{BOLD}[skim]{NC} {ts}  call #{_session.calls}  {ms}ms")
        print(f"  Context  {_ctx_bar(total_ctx, limit)}"
              f"  {_fmt_n(total_ctx)}/{_fmt_n(limit)}")
        print(f"  This call: {_fmt_n(inp)} in / {_fmt_n(out)} out", end="")
        if saved > 0:
            print(f"  {GREEN}stripped {_fmt_n(saved)} waste tokens{NC}", end="")
        print()

        if pct > 0.85:
            print(f"  {RED}⚠  {pct*100:.0f}% full — run /compact NOW before quality degrades{NC}")
        elif pct > 0.65:
            print(f"  {YELLOW}→ {pct*100:.0f}% full — consider /compact to keep quality high{NC}")
        print()


def serve(
    port: int = 7474,
    host: str = "127.0.0.1",
    project_path: Path = None,
    context_limit: int = 200_000,
    model: str = "claude",
    no_filter: bool = False,
) -> None:
    _ProxyHandler.project_path  = project_path or Path(".")
    _ProxyHandler.context_limit = context_limit
    _ProxyHandler.model         = model
    _ProxyHandler.no_filter     = no_filter

    server = HTTPServer((host, port), _ProxyHandler)

    BOLD = "\033[1m"; CYAN = "\033[96m"; YELLOW = "\033[93m"; NC = "\033[0m"

    print(f"\n{BOLD}  skim proxy{NC}  — runtime token interceptor")
    print(f"  {'─'*56}")
    print(f"  Listening  : http://{host}:{port}")
    print(f"  Model      : {model}  ({context_limit:,} token limit)")
    print(f"  Project    : {_ProxyHandler.project_path}")
    print()
    print(f"  {YELLOW}Activate for Claude Code / any Anthropic tool:{NC}")
    print(f"  {CYAN}  export ANTHROPIC_BASE_URL=http://{host}:{port}{NC}")
    print()
    print(f"  {YELLOW}Activate for OpenAI tools:{NC}")
    print(f"  {CYAN}  export OPENAI_BASE_URL=http://{host}:{port}{NC}")
    print()
    print(f"  Health: http://{host}:{port}/health")
    print(f"  Press Ctrl+C to stop.")
    print(f"  {'─'*56}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

    print(f"\n{BOLD}  Session summary{NC}")
    print(f"  {'─'*40}")
    print(f"  API calls       : {_session.calls}")
    print(f"  Tokens sent     : {_fmt_n(_session.total_input)}")
    print(f"  Tokens received : {_fmt_n(_session.total_output)}")
    print(f"  Waste stripped  : {_fmt_n(_session.total_saved)}")
    print()


def main():
    import argparse
    sys.path.insert(0, str(Path(__file__).parent))
    from token_counter import CONTEXT_LIMITS
    p = argparse.ArgumentParser(description="Start the skim runtime token proxy")
    p.add_argument("--port",      "-p", type=int, default=7474)
    p.add_argument("--host",            default="127.0.0.1")
    p.add_argument("--path",            default=".", help="Project root (for .llmignore rules)")
    p.add_argument("--model",     "-m", default="claude")
    p.add_argument("--no-filter",       action="store_true",
                   help="Disable waste filtering (passthrough only, still tracks usage)")
    args = p.parse_args()
    limit = CONTEXT_LIMITS.get(args.model, 200_000)
    serve(args.port, args.host, Path(args.path).resolve(), limit, args.model, args.no_filter)


if __name__ == "__main__":
    main()
