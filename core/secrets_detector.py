#!/usr/bin/env python3
"""
secrets_detector.py — Scan for leaked credentials before they reach an LLM.

Checks for API keys, tokens, private keys, and high-entropy strings that
should never appear in a codebase that an AI is reading.

Usage:
    skim secrets [--path .] [--json] [--fail]
"""

import os
import re
import math
import sys
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))


@dataclass
class SecretFinding:
    file: str
    line: int
    type: str
    severity: str  # "critical" | "high" | "medium"
    snippet: str   # redacted


# (label, severity, compiled_regex)
_PATTERNS = [
    ("Anthropic API Key",    "critical", re.compile(r'sk-ant-api0[0-9]-[A-Za-z0-9_\-]{90,}')),
    ("OpenAI API Key",       "critical", re.compile(r'sk-[A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20}')),
    ("OpenAI Project Key",   "critical", re.compile(r'sk-proj-[A-Za-z0-9_\-]{48,}')),
    ("AWS Access Key ID",    "critical", re.compile(r'AKIA[0-9A-Z]{16}')),
    ("GitHub PAT (classic)", "critical", re.compile(r'ghp_[A-Za-z0-9]{36}')),
    ("GitHub PAT (fine)",    "critical", re.compile(r'github_pat_[A-Za-z0-9_]{82}')),
    ("GitHub Actions Token", "critical", re.compile(r'ghs_[A-Za-z0-9]{36}')),
    ("Stripe Live Key",      "critical", re.compile(r'sk_live_[A-Za-z0-9]{24,}')),
    ("Google API Key",       "high",     re.compile(r'AIza[0-9A-Za-z_\-]{35}')),
    ("Slack Bot Token",      "high",     re.compile(r'xoxb-[0-9]+-[0-9]+-[A-Za-z0-9]+')),
    ("Slack User Token",     "high",     re.compile(r'xoxp-[0-9]+-[0-9]+-[0-9]+-[A-Za-z0-9]+')),
    ("Private Key Block",    "critical", re.compile(r'-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----')),
    ("JWT Token",            "medium",   re.compile(r'eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}')),
    ("Generic Password",     "medium",   re.compile(r'(?i)(?:password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\'<>{}\[\]]{8,}')),
    ("Generic Secret",       "medium",   re.compile(r'(?i)(?:secret|api_key|api_secret|access_token|auth_token)\s*[=:]\s*["\']?[A-Za-z0-9_\-/+]{16,}["\']?')),
]

_SKIP_EXT = {
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp', '.mp4',
    '.mp3', '.wav', '.woff', '.woff2', '.ttf', '.zip', '.tar', '.gz',
    '.pyc', '.so', '.dll', '.exe', '.db', '.pdf', '.lock', '.bin',
}
_SKIP_DIR = {
    'node_modules', '.git', 'dist', 'build', '__pycache__',
    '.venv', 'venv', 'env', '.mypy_cache', 'coverage', '.distill',
}


def _redact(s: str) -> str:
    if len(s) <= 8:
        return "***"
    return s[:6] + "..." + f"[+{len(s)-6} chars]"


def scan_secrets(path: Path) -> list[SecretFinding]:
    findings: list[SecretFinding] = []

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIR and not d.startswith('.')]
        rp = Path(root)

        for fname in files:
            fp = rp / fname
            if fp.suffix.lower() in _SKIP_EXT:
                continue
            try:
                sz = fp.stat().st_size
                if sz == 0 or sz > 2_000_000:
                    continue
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except (PermissionError, OSError):
                continue

            rel = str(fp.relative_to(path))
            for lineno, line in enumerate(text.splitlines(), 1):
                for label, sev, pat in _PATTERNS:
                    m = pat.search(line)
                    if m:
                        findings.append(SecretFinding(
                            file=rel, line=lineno,
                            type=label, severity=sev,
                            snippet=_redact(m.group(0)),
                        ))

    return sorted(findings, key=lambda f: {"critical": 0, "high": 1, "medium": 2}[f.severity])


def print_secrets_report(findings: list[SecretFinding], path: str) -> None:
    RED = "\033[91m"; YELLOW = "\033[93m"; GREEN = "\033[92m"
    BOLD = "\033[1m"; CYAN = "\033[96m"; NC = "\033[0m"

    print(f"\n{BOLD}{'─'*62}{NC}")
    print(f"{BOLD}  skim secrets — Credential Scanner{NC}")
    print(f"  Path: {path}")
    print(f"{'─'*62}")

    if not findings:
        print(f"  {GREEN}✓ No secrets detected.{NC}")
        print(f"{'─'*62}\n")
        return

    crit = sum(1 for f in findings if f.severity == "critical")
    high = sum(1 for f in findings if f.severity == "high")
    med  = sum(1 for f in findings if f.severity == "medium")

    print(f"  {RED}{BOLD}FOUND {len(findings)} potential secret(s){NC}")
    print(f"  Critical: {crit}  High: {high}  Medium: {med}\n")

    sev_color = {"critical": RED, "high": RED, "medium": YELLOW}
    for f in findings:
        c = sev_color[f.severity]
        print(f"  {c}{BOLD}[{f.severity.upper()}]{NC}  {CYAN}{f.file}:{f.line}{NC}")
        print(f"    Type   : {f.type}")
        print(f"    Sample : {f.snippet}")
        print()

    print(f"  {BOLD}Action required:{NC}")
    print(f"  1. Rotate any exposed credentials immediately.")
    print(f"  2. Add to .gitignore: .env, *.pem, *.key, secrets.*")
    print(f"  3. Use environment variables or a vault.")
    print(f"{'─'*62}\n")


def main():
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    p = argparse.ArgumentParser(description="Scan for leaked credentials in a codebase")
    p.add_argument("--path", "-p", default=".", help="Directory to scan")
    p.add_argument("--json",        action="store_true")
    p.add_argument("--fail",        action="store_true", help="Exit 1 if findings exist")
    args = p.parse_args()

    path = Path(args.path).resolve()
    findings = scan_secrets(path)

    if args.json:
        print(json.dumps([{
            "file": f.file, "line": f.line,
            "type": f.type, "severity": f.severity,
            "snippet": f.snippet,
        } for f in findings], indent=2))
    else:
        print_secrets_report(findings, str(path))

    if args.fail and findings:
        sys.exit(1)


if __name__ == "__main__":
    main()
