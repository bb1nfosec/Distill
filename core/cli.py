#!/usr/bin/env python3
"""
cli.py — Unified `skim` command dispatcher.

Usage:
    skim scan      [--path .] [--model claude] [--top 20]
    skim analyze   [--path .] [--model claude]
    skim check     [--path .] [--model claude] [--max-pct 30] [--fail-on-waste]
    skim fix       [--path .] [--min-severity high] [--dry-run]
    skim generate  [--output .] [--model all] [--dry-run]
    skim secrets   [--path .] [--fail]
    skim proxy     [--port 7474] [--path .] [--model claude]
    skim server    [--port 7475] [--host 127.0.0.1]
    skim audit     [--tail 50] [--json]
    skim config    init | show
    skim hooks     install | remove | status  [--path .]
    skim baseline  save | compare | list | delete  [--name v1.0]
    skim version
"""

import sys
import warnings
import argparse
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module=r"google\.api_core\._python_version_support",
)

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))


def _utf8_stdout():
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        elif hasattr(sys.stdout, 'buffer'):
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass


def cmd_scan(argv):
    from core.token_counter import scan_directory, print_report
    p = argparse.ArgumentParser(prog="skim scan")
    p.add_argument("--path",     "-p", default=".")
    p.add_argument("--model",    "-m", default="claude")
    p.add_argument("--top",      "-t", type=int, default=20)
    p.add_argument("--no-ignore",      action="store_true")
    p.add_argument("--json",           action="store_true")
    args = p.parse_args(argv)

    path = Path(args.path).resolve()
    print(f"Scanning {path}...", file=sys.stderr)
    results = scan_directory(path, args.model, respect_llmignore=not args.no_ignore)

    if args.json:
        import json
        print(json.dumps(results, indent=2))
        return 0

    print_report(results, args.model, top_n=args.top, show_cost=True)
    return 0


def cmd_analyze(argv):
    from core.context_analyzer import analyze_directory, print_analysis, apply_fixes
    import json
    p = argparse.ArgumentParser(prog="skim analyze")
    p.add_argument("--path",  "-p", default=".")
    p.add_argument("--model", "-m", default="claude")
    p.add_argument("--json",        action="store_true")
    p.add_argument("--fix",         action="store_true")
    args = p.parse_args(argv)

    path     = Path(args.path).resolve()
    patterns = analyze_directory(path, args.model)

    if args.json:
        print(json.dumps([{
            "name": pt.name, "severity": pt.severity,
            "tokens_wasted": pt.tokens_wasted, "fix": pt.fix,
            "auto_fixable": bool(pt.llmignore_entries),
        } for pt in patterns], indent=2))
        return 0

    print_analysis(patterns, str(path))

    if args.fix:
        added = apply_fixes(patterns, path)
        if added:
            print(f"\033[92m✓ Applied — {added} entries added to .llmignore / .claudeignore\033[0m\n")
        else:
            print("  Nothing new to add.\n")
    return 0


def cmd_check(argv):
    from core.check import run_check
    p = argparse.ArgumentParser(prog="skim check")
    p.add_argument("--path",          "-p", default=".")
    p.add_argument("--model",         "-m", default="claude")
    p.add_argument("--max-pct",       "-x", type=float, default=30.0)
    p.add_argument("--fail-on-waste",       action="store_true")
    p.add_argument("--json",                action="store_true")
    args = p.parse_args(argv)
    return run_check(
        path=Path(args.path).resolve(),
        model=args.model,
        max_pct=args.max_pct,
        fail_on_waste=args.fail_on_waste,
        output_json=args.json,
    )


def cmd_fix(argv):
    from core.fix import run_fix
    p = argparse.ArgumentParser(prog="skim fix")
    p.add_argument("--path",         "-p", default=".")
    p.add_argument("--model",        "-m", default="claude")
    p.add_argument("--dry-run",            action="store_true")
    p.add_argument("--min-severity", "-s", default="high",
                   choices=["high", "medium", "low"])
    args = p.parse_args(argv)
    return run_fix(Path(args.path).resolve(),
                   model=args.model, dry_run=args.dry_run,
                   min_severity=args.min_severity)


def cmd_generate(argv):
    from scripts.generate_config import main as gen_main
    sys.argv = ["generate_config"] + argv
    gen_main()
    return 0


def cmd_secrets(argv):
    from core.secrets_detector import scan_secrets, print_secrets_report
    p = argparse.ArgumentParser(prog="skim secrets")
    p.add_argument("--path", "-p", default=".")
    p.add_argument("--json",       action="store_true")
    p.add_argument("--fail",       action="store_true",
                   help="Exit 1 if findings exist (use in CI)")
    args = p.parse_args(argv)
    path = Path(args.path).resolve()
    from core.secrets_detector import scan_secrets, print_secrets_report
    import json
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
        return 1
    return 0


def cmd_proxy(argv):
    from core.proxy import serve
    from core.token_counter import CONTEXT_LIMITS
    p = argparse.ArgumentParser(prog="skim proxy",
        description="Runtime token interceptor — set ANTHROPIC_BASE_URL=http://localhost:PORT")
    p.add_argument("--port",       "-p", type=int, default=7474)
    p.add_argument("--host",             default="127.0.0.1")
    p.add_argument("--path",             default=".", help="Project root for .llmignore rules")
    p.add_argument("--model",      "-m", default="claude")
    p.add_argument("--no-filter",        action="store_true",
                   help="Disable waste filtering (passthrough only)")
    p.add_argument("--no-cache",         action="store_true",
                   help="Disable automatic prompt caching injection")
    p.add_argument("--no-browser",       action="store_true",
                   help="Do not auto-open the local dashboard in a browser")
    args = p.parse_args(argv)
    limit = CONTEXT_LIMITS.get(args.model, 200_000)
    serve(args.port, args.host, Path(args.path).resolve(), limit, args.model,
          args.no_filter, args.no_cache, args.no_browser)
    return 0


def cmd_server(argv):
    p = argparse.ArgumentParser(prog="skim server",
        description="Web dashboard + REST API for team token management")
    p.add_argument("--port", "-p", type=int, default=7475)
    p.add_argument("--host",        default="127.0.0.1")
    p.add_argument("--db",          default="")
    args = p.parse_args(argv)
    from server.app import main as server_main
    sys.argv = ["skim-server",
                f"--port={args.port}", f"--host={args.host}"] + (
        [f"--db={args.db}"] if args.db else [])
    server_main()
    return 0


def cmd_audit(argv):
    from core.audit import main as audit_main
    sys.argv = ["skim-audit"] + argv
    audit_main()
    return 0


def cmd_config(argv):
    from core.config import main as config_main
    sys.argv = ["skim-config"] + argv
    config_main()
    return 0


def cmd_hooks(argv):
    from core.hooks import main as hooks_main
    sys.argv = ["skim-hooks"] + argv
    hooks_main()
    return 0


def cmd_baseline(argv):
    from core.baseline import main as baseline_main
    sys.argv = ["skim-baseline"] + argv
    baseline_main()
    return 0


def cmd_version(_argv):
    from adapters import __version__
    print(f"skim {__version__}")
    return 0


def cmd_admin(argv):
    """skim admin — manage users, budgets, keys, and webhooks via the skim server API."""
    import json
    import os
    import urllib.request
    import urllib.error

    server = os.environ.get("SKIM_SERVER_URL", "").rstrip("/")
    token  = os.environ.get("SKIM_SERVER_TOKEN", "")

    if not server or not token:
        print("Error: set SKIM_SERVER_URL and SKIM_SERVER_TOKEN first.", file=sys.stderr)
        print("  export SKIM_SERVER_URL=http://localhost:7475", file=sys.stderr)
        print("  export SKIM_SERVER_TOKEN=sk-skim-...", file=sys.stderr)
        return 1

    BOLD = "\033[1m"; CYAN = "\033[96m"; GREEN = "\033[92m"
    RED = "\033[91m"; NC = "\033[0m"; DIM = "\033[2m"

    def req(method, path, body=None):
        url  = f"{server}{path}"
        data = json.dumps(body).encode() if body else None
        r    = urllib.request.Request(url, data=data, method=method)
        r.add_header("Authorization", f"Bearer {token}")
        r.add_header("Content-Type",  "application/json")
        try:
            with urllib.request.urlopen(r, timeout=10) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read())
            except Exception:
                return e.code, {"error": str(e)}
        except Exception as e:
            return 0, {"error": str(e)}

    def ok(d): return f"{GREEN}✓{NC} {d}"
    def err(d): return f"{RED}✗{NC} {d}"

    if not argv:
        print(f"""
{BOLD}skim admin{NC} — manage the skim server

{BOLD}Usage:{NC}
  skim admin users list
  skim admin users invite --email X --role user --team engineering
  skim admin users delete <email>

  skim admin budget set --owner-type user --owner-id <user_id> --tokens 1000000 --period monthly
  skim admin budget set --owner-type team --owner-id engineering --usd 500
  skim admin budget list
  skim admin budget delete <id>

  skim admin keys list
  skim admin keys revoke <key-prefix>

  skim admin webhooks list
  skim admin webhooks add --url https://hooks.slack.com/... --channel slack
  skim admin webhooks delete <id>

  skim admin export --days 30 --out events.csv

  skim admin audit --days 30

{DIM}Reads SKIM_SERVER_URL + SKIM_SERVER_TOKEN from env{NC}
""")
        return 0

    sub = argv[0]

    # ── users ────────────────────────────────────────────────────────────────
    if sub == "users":
        action = argv[1] if len(argv) > 1 else "list"
        if action == "list":
            code, data = req("GET", "/api/v1/admin/users")
            if code != 200:
                print(err(data)); return 1
            users = data.get("users", [])
            print(f"\n{BOLD}  {'Email':<30} {'Name':<18} {'Team':<15} {'Role'}{NC}")
            print(f"  {'─'*30} {'─'*18} {'─'*15} {'─'*10}")
            for u in users:
                print(f"  {u.get('email',''):<30} {u.get('name',''):<18} {u.get('team',''):<15} {u.get('role','')}")
            print(f"\n  {len(users)} user(s)\n")

        elif action == "invite":
            p = argparse.ArgumentParser(prog="skim admin users invite")
            p.add_argument("--email",  required=True)
            p.add_argument("--role",   default="user", choices=["user","team_admin","admin"])
            p.add_argument("--team",   default="")
            args = p.parse_args(argv[2:])
            code, data = req("POST", "/api/v1/admin/invites",
                             {"email": args.email, "role": args.role, "team": args.team})
            if code not in (200, 201):
                print(err(data)); return 1
            print(ok(f"Invite created for {args.email}"))
            print(f"  {CYAN}{data.get('invite_url','')}{NC}\n")

        elif action == "delete":
            email = argv[2] if len(argv) > 2 else ""
            code, data = req("GET", "/api/v1/admin/users")
            user = next((u for u in data.get("users",[]) if u["email"] == email), None)
            if not user:
                print(err(f"User not found: {email}")); return 1
            code, data = req("DELETE", f"/api/v1/admin/users/{user['id']}")
            print(ok(f"Deleted {email}") if code == 200 else err(data))
        return 0

    # ── budget ────────────────────────────────────────────────────────────────
    elif sub == "budget":
        action = argv[1] if len(argv) > 1 else "list"
        if action == "list":
            code, data = req("GET", "/api/v1/admin/budgets")
            if code != 200:
                print(err(data)); return 1
            budgets = data.get("budgets", [])
            print(f"\n{BOLD}  {'ID':<5} {'Type':<8} {'Owner':<24} {'Tokens':>12} {'USD':>10} {'Period':<10} {'Alert%'}{NC}")
            print(f"  {'─'*5} {'─'*8} {'─'*24} {'─'*12} {'─'*10} {'─'*10} {'─'*6}")
            for b in budgets:
                print(f"  {b['id']:<5} {b['owner_type']:<8} {str(b.get('owner_id','global')):<24} "
                      f"{str(b.get('limit_tokens') or '—'):>12} {str(b.get('limit_usd') or '—'):>10} "
                      f"{b['period']:<10} {b['alert_pct']}%")
            print(f"\n  {len(budgets)} budget(s)\n")

        elif action == "set":
            p = argparse.ArgumentParser(prog="skim admin budget set")
            p.add_argument("--owner-type", default="user", choices=["user","team","global"])
            p.add_argument("--owner-id",   default=None)
            p.add_argument("--tokens",     type=int, default=None)
            p.add_argument("--usd",        type=float, default=None)
            p.add_argument("--period",     default="monthly", choices=["daily","weekly","monthly"])
            p.add_argument("--alert-pct",  type=float, default=80.0)
            args = p.parse_args(argv[2:])
            payload = {
                "owner_type": args.owner_type, "owner_id": args.owner_id,
                "limit_tokens": args.tokens, "limit_usd": args.usd,
                "period": args.period, "alert_pct": args.alert_pct,
            }
            code, data = req("POST", "/api/v1/admin/budgets", payload)
            print(ok(f"Budget set (id={data.get('budget',{}).get('id')})") if code in (200,201) else err(data))

        elif action == "delete":
            bid = argv[2] if len(argv) > 2 else ""
            code, data = req("DELETE", f"/api/v1/admin/budgets/{bid}")
            print(ok("Budget deleted") if code == 200 else err(data))
        return 0

    # ── keys ─────────────────────────────────────────────────────────────────
    elif sub == "keys":
        action = argv[1] if len(argv) > 1 else "list"
        if action == "list":
            code, data = req("GET", "/api/v1/auth/keys")
            if code != 200:
                print(err(data)); return 1
            keys = data.get("keys", [])
            print(f"\n{BOLD}  {'Key (prefix)':<20} {'Label':<18} {'Scope':<10} {'Expires':<24} {'Last used'}{NC}")
            print(f"  {'─'*20} {'─'*18} {'─'*10} {'─'*24} {'─'*20}")
            for k in keys:
                print(f"  {k['key'][:18]+'…':<20} {k.get('label',''):<18} "
                      f"{k.get('scope',''):<10} {k.get('expires_at','never'):<24} "
                      f"{k.get('last_used','never')}")
            print()

        elif action == "revoke":
            prefix = argv[2] if len(argv) > 2 else ""
            code, data = req("DELETE", f"/api/v1/auth/keys/{prefix}")
            print(ok("Key revoked") if code == 200 else err(data))
        return 0

    # ── webhooks ──────────────────────────────────────────────────────────────
    elif sub == "webhooks":
        action = argv[1] if len(argv) > 1 else "list"
        if action == "list":
            code, data = req("GET", "/api/v1/admin/webhooks")
            if code != 200:
                print(err(data)); return 1
            hooks = data.get("webhooks", [])
            print(f"\n{BOLD}  {'ID':<5} {'Channel':<8} {'Events':<36} {'URL'}{NC}")
            print(f"  {'─'*5} {'─'*8} {'─'*36} {'─'*40}")
            for h in hooks:
                print(f"  {h['id']:<5} {h['channel']:<8} {h['events']:<36} {h['url']}")
            print()

        elif action == "add":
            p = argparse.ArgumentParser(prog="skim admin webhooks add")
            p.add_argument("--url",     required=True)
            p.add_argument("--channel", default="http", choices=["http","slack"])
            p.add_argument("--events",  default="budget.warning,budget.exceeded")
            p.add_argument("--secret",  default="")
            args = p.parse_args(argv[2:])
            code, data = req("POST", "/api/v1/admin/webhooks",
                             {"url": args.url, "channel": args.channel,
                              "events": args.events, "secret": args.secret})
            print(ok(f"Webhook added (id={data.get('webhook',{}).get('id')})") if code in (200,201) else err(data))

        elif action == "delete":
            wid = argv[2] if len(argv) > 2 else ""
            code, data = req("DELETE", f"/api/v1/admin/webhooks/{wid}")
            print(ok("Webhook deleted") if code == 200 else err(data))
        return 0

    # ── export ────────────────────────────────────────────────────────────────
    elif sub == "export":
        p = argparse.ArgumentParser(prog="skim admin export")
        p.add_argument("--days", type=int, default=30)
        p.add_argument("--out",  default="skim-events.csv")
        args = p.parse_args(argv[1:])
        url  = f"{server}/api/v1/export/events.csv?days={args.days}"
        r    = urllib.request.Request(url)
        r.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                with open(args.out, "wb") as f:
                    f.write(resp.read())
            print(ok(f"Exported to {args.out}"))
        except Exception as e:
            print(err(str(e))); return 1
        return 0

    # ── audit ─────────────────────────────────────────────────────────────────
    elif sub == "audit":
        p = argparse.ArgumentParser(prog="skim admin audit")
        p.add_argument("--days",   type=int, default=30)
        p.add_argument("--action", default=None)
        args   = p.parse_args(argv[1:])
        path   = f"/api/v1/admin/audit?days={args.days}"
        if args.action:
            path += f"&action={args.action}"
        code, data = req("GET", path)
        if code != 200:
            print(err(data)); return 1
        entries = data.get("log", [])
        print(f"\n{BOLD}  {'Timestamp':<22} {'User':<28} {'Action':<22} {'Detail'}{NC}")
        print(f"  {'─'*22} {'─'*28} {'─'*22} {'─'*30}")
        for e in entries:
            ts = e.get("ts","")[:19].replace("T"," ")
            print(f"  {ts:<22} {e.get('email',''):<28} {e.get('action',''):<22} {e.get('detail') or ''}")
        print(f"\n  {len(entries)} entries\n")
        return 0

    print(f"Unknown admin command: {sub}\nRun 'skim admin' for help.", file=sys.stderr)
    return 1


COMMANDS = {
    "scan":     cmd_scan,
    "analyze":  cmd_analyze,
    "check":    cmd_check,
    "fix":      cmd_fix,
    "generate": cmd_generate,
    "secrets":  cmd_secrets,
    "proxy":    cmd_proxy,
    "server":   cmd_server,
    "audit":    cmd_audit,
    "config":   cmd_config,
    "hooks":    cmd_hooks,
    "baseline": cmd_baseline,
    "admin":    cmd_admin,
    "version":  cmd_version,
}

HELP = """skim — LLM token runtime & optimization toolkit

Static analysis:
  scan       Audit token costs per file across your codebase
  analyze    Detect waste patterns (lock files, build artifacts, etc.)
  check      CI budget gate — exits 1 if over context threshold
  fix        Auto-write .llmignore rules — shows before/after savings
  generate   Generate .llmignore, .skimrc, and LLM configs
  secrets    Scan for leaked credentials before they reach an LLM

Runtime (the missing layer):
  proxy      Runtime interceptor — sit between your tool and the LLM API
             Set: export ANTHROPIC_BASE_URL=http://localhost:7474
             Strips waste in real-time, shows live context fill %

Dashboard & team:
  server     Web dashboard + REST API (login, charts, team usage)
             Set: export SKIM_ADMIN_EMAIL=you@org.com before first run

Operations:
  audit      View the operation audit log (~/.skim/audit.log)
  config     Manage .skimrc configuration file
  hooks      Install / remove git pre-commit budget gate
  baseline   Save & compare token count snapshots for regression detection
  version    Print version

Examples:
  skim scan --path ./my-project
  skim fix --path . --min-severity medium
  skim proxy --port 7474 --path .      # then: export ANTHROPIC_BASE_URL=http://localhost:7474
  skim server --port 7475              # then: open http://localhost:7475/dashboard
  skim secrets --path . --fail         # use in CI to block leaked keys
  skim hooks install --max-pct 30
  skim baseline save --name pre-refactor
  skim baseline compare --name pre-refactor
"""


def main():
    _utf8_stdout()
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(HELP)
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}\n\n{HELP}", file=sys.stderr)
        sys.exit(1)

    exit_code = COMMANDS[cmd](sys.argv[2:])
    sys.exit(exit_code or 0)


if __name__ == "__main__":
    main()
