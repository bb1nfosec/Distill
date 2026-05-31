#!/usr/bin/env python3
"""
baseline.py — Token count snapshots for regression detection.

Save a baseline at any point, then compare future state against it
to catch PRs or deployments that bloat the LLM context.

Usage:
    skim baseline save    [--name v1.0] [--path .]
    skim baseline compare [--name v1.0] [--path .]
    skim baseline list    [--path .]
    skim baseline delete  --name v1.0  [--path .]
"""

import getpass
import json
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

_DIR  = ".skim"
_FILE = "baselines.json"


def _load(project: Path) -> dict:
    f = project / _DIR / _FILE
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save(project: Path, data: dict) -> None:
    d = project / _DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / _FILE).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def save_baseline(project: Path, name: str, model: str = "claude") -> None:
    from token_counter import scan_directory, CONTEXT_LIMITS

    results = scan_directory(project, model, respect_llmignore=True)
    total_tok  = sum(r["tokens"]   for r in results)
    total_cost = sum(r["cost_usd"] for r in results)
    limit      = CONTEXT_LIMITS.get(model, 200_000)

    data = _load(project)
    data[name] = {
        "ts":           datetime.now(timezone.utc).isoformat(),
        "user":         getpass.getuser(),
        "model":        model,
        "total_tokens": total_tok,
        "total_files":  len(results),
        "context_pct":  round(total_tok / limit * 100, 2),
        "cost_usd":     round(total_cost, 6),
        "top_files":    [{"path": r["path"], "tokens": r["tokens"]} for r in results[:10]],
    }
    _save(project, data)

    GREEN = "\033[92m"; BOLD = "\033[1m"; NC = "\033[0m"
    print(f"\n{BOLD}  skim baseline save{NC}")
    print(f"  {'─'*44}")
    print(f"  {GREEN}✓ Saved '{name}'{NC}")
    print(f"  Tokens  : {total_tok:,}")
    print(f"  Files   : {len(results)}")
    print(f"  Context : {data[name]['context_pct']}%")
    print(f"  Cost    : ${total_cost:.4f}/session")
    print(f"  Written : {project / _DIR / _FILE}")
    print()


def compare_baseline(project: Path, name: str, model: str = "claude") -> int:
    from token_counter import scan_directory, CONTEXT_LIMITS

    data = _load(project)
    if name not in data:
        print(f"  Baseline '{name}' not found. Run: skim baseline save --name {name}", file=sys.stderr)
        return 1

    snap    = data[name]
    results = scan_directory(project, model, respect_llmignore=True)
    now_tok = sum(r["tokens"] for r in results)
    limit   = CONTEXT_LIMITS.get(model, 200_000)
    delta   = now_tok - snap["total_tokens"]
    sign    = "+" if delta >= 0 else ""

    RED = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
    BOLD = "\033[1m"; NC = "\033[0m"
    dc = RED if delta > 0 else GREEN

    print(f"\n{BOLD}  skim baseline compare — '{name}'{NC}")
    print(f"  {'─'*52}")
    print(f"  Snapshot : {snap['ts'][:19]} by {snap.get('user','?')}")
    print(f"  {'─'*52}")
    print(f"  {'':20} {'Baseline':>12}  {'Now':>12}  {'Delta':>12}")
    print(f"  {'─'*52}")
    print(f"  {'Tokens':<20} {snap['total_tokens']:>12,}  {now_tok:>12,}  "
          f"{dc}{sign}{delta:>12,}{NC}")
    print(f"  {'Files':<20} {snap['total_files']:>12}  {len(results):>12}")
    print(f"  {'Context %':<20} {snap['context_pct']:>11.1f}%  "
          f"{now_tok/limit*100:>11.1f}%")

    if delta > 5000:
        print(f"\n  {RED}⚠  Regression: +{delta:,} tokens since baseline.{NC}")
        print(f"  Run: skim analyze  to find new waste.")
        return 1
    elif delta < -1000:
        print(f"\n  {GREEN}✓ Improvement: {abs(delta):,} tokens removed.{NC}")
    else:
        print(f"\n  {GREEN}✓ Within tolerance.{NC}")
    print()
    return 0


def list_baselines(project: Path) -> None:
    data = _load(project)
    BOLD = "\033[1m"; CYAN = "\033[96m"; NC = "\033[0m"
    print(f"\n{BOLD}  skim baseline list{NC}")
    print(f"  {'─'*62}")
    if not data:
        print("  No baselines. Run: skim baseline save --name <name>")
        print()
        return
    print(f"  {BOLD}{'Name':<24} {'Date':<22} {'Tokens':>10} {'Ctx%':>6}{NC}")
    print(f"  {'─'*24} {'─'*22} {'─'*10} {'─'*6}")
    for n, s in sorted(data.items(), key=lambda x: x[1]["ts"]):
        ts = s["ts"][:19].replace("T", " ")
        print(f"  {CYAN}{n:<24}{NC} {ts:<22} {s['total_tokens']:>10,} {s['context_pct']:>5.1f}%")
    print()


def delete_baseline(project: Path, name: str) -> None:
    data = _load(project)
    if name not in data:
        print(f"  Baseline '{name}' not found.", file=sys.stderr)
        return
    del data[name]
    _save(project, data)
    print(f"  Deleted '{name}'.")


def main():
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    p = argparse.ArgumentParser(description="Save and compare token baselines")
    sub = p.add_subparsers(dest="action")

    save = sub.add_parser("save")
    save.add_argument("--name", "-n", default="default")
    save.add_argument("--path", "-p", default=".")
    save.add_argument("--model", "-m", default="claude")

    cmp = sub.add_parser("compare")
    cmp.add_argument("--name", "-n", default="default")
    cmp.add_argument("--path", "-p", default=".")
    cmp.add_argument("--model", "-m", default="claude")

    ls = sub.add_parser("list")
    ls.add_argument("--path", "-p", default=".")

    dl = sub.add_parser("delete")
    dl.add_argument("--name", "-n", required=True)
    dl.add_argument("--path", "-p", default=".")

    args = p.parse_args()
    if not args.action:
        p.print_help()
        return

    path = Path(getattr(args, "path", ".")).resolve()
    if args.action == "save":
        save_baseline(path, args.name, args.model)
    elif args.action == "compare":
        sys.exit(compare_baseline(path, args.name, args.model))
    elif args.action == "list":
        list_baselines(path)
    elif args.action == "delete":
        delete_baseline(path, args.name)


if __name__ == "__main__":
    main()
