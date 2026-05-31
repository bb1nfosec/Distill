#!/usr/bin/env python3
"""
audit.py — Append-only usage event log.

Writes every skim operation to ~/.skim/audit.log (JSONL) and optionally
to a central skim server for team-level dashboards.

Usage:
    skim audit [--tail 50] [--json] [--clear]
"""

import getpass
import json
import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

AUDIT_DIR  = Path.home() / ".skim"
AUDIT_FILE = AUDIT_DIR / "audit.log"


def _ensure_dir() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def record(
    command: str,
    path: str        = "",
    model: str       = "",
    result: str      = "",
    tokens_before: int = 0,
    tokens_after:  int = 0,
    extra: dict      = None,
) -> None:
    _ensure_dir()
    entry = {
        "ts":            datetime.now(timezone.utc).isoformat(),
        "user":          getpass.getuser(),
        "command":       command,
        "path":          str(path),
        "model":         model,
        "result":        result,
        "tokens_before": tokens_before,
        "tokens_after":  tokens_after,
        "saved_tokens":  max(0, tokens_before - tokens_after),
    }
    if extra:
        entry.update(extra)
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # Optionally ship to central skim server
    server = os.environ.get("SKIM_SERVER_URL", "")
    token  = os.environ.get("SKIM_SERVER_TOKEN", "")
    if server and token:
        _ship(server, token, entry)


def _ship(server_url: str, token: str, entry: dict) -> None:
    import urllib.request
    try:
        data = json.dumps(entry).encode()
        req  = urllib.request.Request(
            f"{server_url.rstrip('/')}/api/v1/events",
            data=data, method="POST",
        )
        req.add_header("Content-Type",  "application/json")
        req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=3) as r:
            r.read()
    except Exception:
        pass  # never let audit shipping break the main command


def read_entries(tail: int = None) -> list[dict]:
    if not AUDIT_FILE.exists():
        return []
    entries = []
    with open(AUDIT_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries[-tail:] if tail else entries


def clear_log() -> None:
    if AUDIT_FILE.exists():
        AUDIT_FILE.unlink()


def print_audit_report(entries: list[dict]) -> None:
    BOLD = "\033[1m"; NC = "\033[0m"; CYAN = "\033[96m"

    print(f"\n{BOLD}{'─'*72}{NC}")
    print(f"{BOLD}  skim audit — Operation Log{NC}")
    print(f"  Log: {AUDIT_FILE}")
    print(f"{'─'*72}")

    if not entries:
        print("  No entries yet.")
        print(f"{'─'*72}\n")
        return

    print(f"  {BOLD}{'Timestamp':<22} {'User':<12} {'Command':<10} {'Result':<8} {'Saved':>8}{NC}")
    print(f"  {'─'*22} {'─'*12} {'─'*10} {'─'*8} {'─'*8}")
    for e in entries:
        ts     = e.get("ts", "")[:19].replace("T", " ")
        user   = e.get("user", "")[:11]
        cmd    = e.get("command", "")[:9]
        result = e.get("result", "")[:7]
        saved  = e.get("saved_tokens", 0)
        saved_str = f"{saved:,}" if saved else "-"
        print(f"  {ts:<22} {user:<12} {cmd:<10} {result:<8} {saved_str:>8}")

    print(f"\n  {len(entries)} entries   File: {AUDIT_FILE}")
    print(f"{'─'*72}\n")


def main():
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    p = argparse.ArgumentParser(description="View skim audit log")
    p.add_argument("--tail",  "-n", type=int, default=50)
    p.add_argument("--json",        action="store_true")
    p.add_argument("--clear",       action="store_true", help="Clear the log")
    args = p.parse_args()

    if args.clear:
        clear_log()
        print("Audit log cleared.")
        return

    entries = read_entries(tail=args.tail)
    if args.json:
        print(json.dumps(entries, indent=2))
    else:
        print_audit_report(entries)


if __name__ == "__main__":
    main()
