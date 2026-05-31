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
    p.add_argument("--port",      "-p", type=int, default=7474)
    p.add_argument("--host",            default="127.0.0.1")
    p.add_argument("--path",            default=".", help="Project root for .llmignore rules")
    p.add_argument("--model",     "-m", default="claude")
    p.add_argument("--no-filter",       action="store_true",
                   help="Disable waste filtering (passthrough only)")
    p.add_argument("--no-cache",        action="store_true",
                   help="Disable automatic prompt caching injection")
    args = p.parse_args(argv)
    limit = CONTEXT_LIMITS.get(args.model, 200_000)
    serve(args.port, args.host, Path(args.path).resolve(), limit, args.model,
          args.no_filter, args.no_cache)
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
