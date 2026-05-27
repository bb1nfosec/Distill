#!/usr/bin/env python3
"""
check.py — Budget gate for CI pipelines.

Exits 0 if the repo is within budget, 1 if over.
Use in CI to prevent context bloat from landing.

Usage:
    python3 core/check.py --path . --max-pct 30
    python3 core/check.py --path . --max-pct 50 --model gpt-4o
    python3 core/check.py --path . --max-pct 30 --fail-on-waste

GitHub Actions example:
    - name: Token budget check
      run: python3 core/check.py --path . --max-pct 30
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from token_counter import (
    scan_directory, estimate_cost, format_number, format_cost,
    CONTEXT_LIMITS, PRICING
)
from context_analyzer import analyze_directory


def run_check(
    path: Path,
    model: str = "claude",
    max_pct: float = 30.0,
    fail_on_waste: bool = False,
    output_json: bool = False,
    strict: bool = False,
    overhead_pct: float = 0,
    overhead_fixed: int = 0,
) -> int:
    """
    Returns 0 (pass) or 1 (fail).
    Prints a compact CI-friendly report.
    """
    RED   = "\033[91m"; YELLOW = "\033[93m"; GREEN = "\033[92m"
    BOLD  = "\033[1m";  NC     = "\033[0m"

    if strict:
        try:
            import tiktoken  # noqa: F401
        except ImportError:
            msg = "tiktoken is not installed and --strict mode requires accurate token counting."
            if output_json:
                print(json.dumps({"error": msg, "passed": False}))
            else:
                print(f"\n  {RED}✗ STRICT MODE ERROR:{NC} {msg}")
                print(f"  Install with: pip install tiktoken\n")
            return 1

    results  = scan_directory(path, model, respect_llmignore=True)
    patterns = analyze_directory(path, model)

    active_results = [r for r in results if not r.get("skipped")]
    total_tokens = sum(r["tokens"] for r in active_results)
    total_cost   = sum(r["cost_usd"] for r in active_results)
    limit        = CONTEXT_LIMITS.get(model, 128_000)
    pct          = (total_tokens / limit) * 100

    high_waste   = [p for p in patterns if p.severity == "high"]

    # Overhead estimate (conversation framing, system prompts, etc.)
    has_overhead = overhead_pct or overhead_fixed
    adjusted_tokens = int(total_tokens * (1 + overhead_pct / 100)) + overhead_fixed if has_overhead else total_tokens
    adjusted_pct    = (adjusted_tokens / limit) * 100 if has_overhead else pct

    over_budget  = pct > max_pct
    has_waste    = fail_on_waste and bool(high_waste)
    failed       = over_budget or has_waste

    if output_json:
        data = {
            "passed":        not failed,
            "model":         model,
            "total_tokens":  total_tokens,
            "context_pct":   round(pct, 2),
            "max_pct":       max_pct,
            "cost_usd":      round(total_cost, 6),
            "over_budget":   over_budget,
            "waste_patterns": [{"name": p.name, "severity": p.severity, "tokens": p.tokens_wasted} for p in patterns],
        }
        if has_overhead:
            data["overhead_pct"] = overhead_pct
            data["overhead_fixed"] = overhead_fixed
            data["adjusted_tokens"] = adjusted_tokens
            data["adjusted_context_pct"] = round(adjusted_pct, 2)
        print(json.dumps(data, indent=2))
        return 1 if failed else 0

    status_icon  = f"{RED}✗ FAIL{NC}" if failed else f"{GREEN}✓ PASS{NC}"
    budget_color = RED if over_budget else (YELLOW if pct > max_pct * 0.8 else GREEN)

    print(f"\n{BOLD}  distill check{NC}  —  {path}")
    print(f"  {'─'*50}")
    print(f"  Status        : {status_icon}")
    print(f"  Model         : {model}")
    print(f"  Tokens        : {format_number(total_tokens)}  ({budget_color}{pct:.1f}%{NC} of {format_number(limit)} ctx)")
    if has_overhead:
        oh_color = RED if adjusted_pct > max_pct else (YELLOW if adjusted_pct > max_pct * 0.8 else GREEN)
        oh_parts = []
        if overhead_pct:
            oh_parts.append(f"{overhead_pct:.0f}%")
        if overhead_fixed:
            oh_parts.append(f"{format_number(overhead_fixed)} fixed")
        print(f"  + Overhead     : {format_number(adjusted_tokens)}  ({oh_color}{adjusted_pct:.1f}%{NC} with {' + '.join(oh_parts)} overhead)")
    print(f"  Budget        : ≤ {max_pct:.0f}% of context")
    print(f"  Per-session $ : {format_cost(total_cost)}")

    if over_budget:
        print(f"\n  {RED}Context {pct:.1f}% exceeds budget {max_pct:.0f}%{NC}")
        print(f"  Top offenders:")
        for r in active_results[:5]:
            print(f"    {r['path'][:55]:<55}  {format_number(r['tokens']):>7}  {format_cost(r['cost_usd'])}")
        print(f"\n  Fix: run `distill generate` to create .llmignore, or add large files manually.")

    if patterns:
        print(f"\n  Waste patterns found: {len(patterns)}")
        for p in patterns:
            c = RED if p.severity == "high" else (YELLOW if p.severity == "medium" else "")
            nc = NC if c else ""
            print(f"    {c}[{p.severity.upper()}]{nc} {p.name}  — {format_number(p.tokens_wasted)} tokens wasted")
            print(f"           Fix: {p.fix}")
        if has_waste:
            print(f"\n  {RED}Failing on {len(high_waste)} HIGH severity waste pattern(s){NC} (--fail-on-waste)")

    print(f"\n  {'─'*50}")
    print(f"  Exit code: {'1 (fail)' if failed else '0 (pass)'}\n")

    return 1 if failed else 0


def main():
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        elif hasattr(sys.stdout, 'buffer'):
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description="Token budget gate for CI — exits 1 if over budget"
    )
    parser.add_argument("--path",          "-p", default=".",        help="Path to scan (default: .)")
    parser.add_argument("--model",         "-m", default="claude",   help="Model family")
    parser.add_argument("--max-pct",       "-x", type=float, default=30.0,
                        help="Max allowed context %% before failing (default: 30)")
    parser.add_argument("--fail-on-waste",       action="store_true",
                        help="Also fail on HIGH severity waste patterns")
    parser.add_argument("--strict",              action="store_true",
                        help="Error if tiktoken is not installed (require accurate counts)")
    parser.add_argument("--overhead-pct",        type=float, default=0,
                        help="Estimated conversation overhead %% (default: 0)")
    parser.add_argument("--overhead-fixed",      type=int, default=0,
                        help="Fixed token overhead for system prompt/framing (default: 0)")
    parser.add_argument("--json",                action="store_true", help="Output JSON")
    args = parser.parse_args()

    path = Path(args.path).resolve()
    if not path.exists():
        print(f"Path not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    exit_code = run_check(
        path           = path,
        model          = args.model,
        max_pct        = args.max_pct,
        fail_on_waste  = args.fail_on_waste,
        output_json    = args.json,
        strict         = args.strict,
        overhead_pct   = args.overhead_pct,
        overhead_fixed = args.overhead_fixed,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
