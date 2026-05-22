#!/usr/bin/env python3
"""
cli.py — Unified `distill` command dispatcher.

Usage:
    distill scan    [--path .] [--model claude] [--top 20] [--cost]
    distill analyze [--path .] [--model claude]
    distill check   [--path .] [--model claude] [--max-pct 30] [--fail-on-waste]
    distill generate [--output .] [--model all] [--dry-run]
    distill version
"""

import sys
import argparse
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))


def cmd_scan(argv):
    from core.token_counter import scan_directory, print_report, CONTEXT_LIMITS
    p = argparse.ArgumentParser(prog="distill scan")
    p.add_argument("--path",     "-p", default=".")
    p.add_argument("--model",    "-m", default="claude")
    p.add_argument("--top",      "-t", type=int, default=20)
    p.add_argument("--cost",     "-c", action="store_true")
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
    p = argparse.ArgumentParser(prog="distill analyze")
    p.add_argument("--path",  "-p", default=".")
    p.add_argument("--model", "-m", default="claude")
    p.add_argument("--json",        action="store_true")
    p.add_argument("--fix",         action="store_true",
                   help="Auto-apply fixes (writes .llmignore / .claudeignore)")
    args = p.parse_args(argv)

    path = Path(args.path).resolve()
    patterns = analyze_directory(path, args.model)

    if args.json:
        print(json.dumps([{
            "name": p.name, "severity": p.severity,
            "tokens_wasted": p.tokens_wasted, "fix": p.fix,
            "auto_fixable": bool(p.llmignore_entries),
        } for p in patterns], indent=2))
        return 0

    print_analysis(patterns, str(path))

    if args.fix:
        added = apply_fixes(patterns, path)
        if added:
            print(f"\033[92m✓ Applied fixes — {added} entries added to .llmignore / .claudeignore\033[0m\n")
        else:
            print("  Nothing new to add (all entries already present).\n")

    return 0


def cmd_check(argv):
    from core.check import run_check
    p = argparse.ArgumentParser(prog="distill check")
    p.add_argument("--path",          "-p", default=".")
    p.add_argument("--model",         "-m", default="claude")
    p.add_argument("--max-pct",       "-x", type=float, default=30.0)
    p.add_argument("--fail-on-waste",       action="store_true")
    p.add_argument("--json",                action="store_true")
    args = p.parse_args(argv)

    path = Path(args.path).resolve()
    return run_check(
        path          = path,
        model         = args.model,
        max_pct       = args.max_pct,
        fail_on_waste = args.fail_on_waste,
        output_json   = args.json,
    )


def cmd_generate(argv):
    from scripts.generate_config import main as gen_main
    sys.argv = ["generate_config"] + argv
    gen_main()
    return 0


def cmd_version(_argv):
    from adapters import __version__
    print(f"distill {__version__}")
    return 0


COMMANDS = {
    "scan":     cmd_scan,
    "analyze":  cmd_analyze,
    "check":    cmd_check,
    "generate": cmd_generate,
    "version":  cmd_version,
}

HELP = """distill — token optimization toolkit

Commands:
  scan      Scan a directory and report token costs per file
  analyze   Detect waste patterns (lock files, generated code, etc.)
  check     Budget gate for CI — exits 1 if over context threshold
  generate  Auto-generate .llmignore, CLAUDE.md, and LLM configs
  version   Print version

Examples:
  distill scan --path ./my-project
  distill scan --path . --model gpt-4o --cost
  distill analyze --path ./my-project
  distill analyze --path ./my-project --fix
  distill check --path . --max-pct 30
  distill check --path . --max-pct 30 --fail-on-waste
  distill generate --output . --model all
"""


def main():
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
