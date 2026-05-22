#!/usr/bin/env python3
"""
fix.py — Automatically apply .llmignore rules to eliminate detected waste.

Detects context waste patterns, writes the rules into .llmignore, and prints
a before/after comparison showing tokens and dollars saved.

Usage:
    python3 core/fix.py --path .
    python3 core/fix.py --path . --dry-run        # show what would change, don't write
    python3 core/fix.py --path . --model gpt-4o
    python3 core/fix.py --path . --min-severity medium
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from token_counter import scan_directory, format_number, format_cost, CONTEXT_LIMITS, PRICING
from context_analyzer import analyze_directory

SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _read_llmignore(path: Path) -> list[str]:
    ig = path / ".llmignore"
    return ig.read_text(encoding='utf-8').splitlines() if ig.exists() else []


def _write_llmignore(path: Path, lines: list[str]) -> None:
    (path / ".llmignore").write_text("\n".join(lines) + "\n", encoding='utf-8')


def run_fix(
    path: Path,
    model: str = "claude",
    dry_run: bool = False,
    min_severity: str = "high",
) -> int:
    RED   = "\033[91m"; YELLOW = "\033[93m"; GREEN = "\033[92m"
    BOLD  = "\033[1m";  CYAN   = "\033[96m";  NC   = "\033[0m"

    min_rank  = SEVERITY_RANK.get(min_severity, 0)
    ctx_limit = CONTEXT_LIMITS.get(model, 200_000)

    # Before scan
    before        = scan_directory(path, model, respect_llmignore=True)
    before_tokens = sum(f["tokens"] for f in before)
    before_cost   = sum(f["cost_usd"] for f in before)
    before_pct    = before_tokens / ctx_limit * 100

    patterns = analyze_directory(path, model)

    print(f"\n{BOLD}  distill fix{NC}  —  {path}")
    print(f"  {'─'*54}")
    print(f"  Before  : {format_number(before_tokens)} tokens  "
          f"({before_pct:.1f}% ctx)  {format_cost(before_cost)}/session")

    in_scope = [p for p in patterns if SEVERITY_RANK.get(p.severity, 99) <= min_rank]
    if not in_scope:
        print(f"\n  {GREEN}✓ No actionable waste patterns found — context already clean.{NC}\n")
        return 0

    existing     = _read_llmignore(path)
    existing_set = set(existing)
    added_rules: list[str] = []
    skipped:     list[str] = []

    print(f"\n  {'Pattern':<28} {'Severity':<8} {'Tokens saved':>13}  {'Rules to add'}")
    print(f"  {'─'*80}")

    for p in sorted(in_scope, key=lambda x: SEVERITY_RANK.get(x.severity, 99)):
        rules = p.llmignore_entries  # comes from WastePattern.llmignore_entries
        sev_color = RED if p.severity == "high" else YELLOW

        if not rules:
            print(f"  {p.name:<28} {sev_color}{p.severity.upper():<8}{NC} "
                  f"{format_number(p.tokens_wasted):>13}  ⚠ manual fix required")
            print(f"    {CYAN}→ {p.fix}{NC}")
            continue

        new_rules = [r for r in rules if r not in existing_set]
        already   = [r for r in rules if r in existing_set]

        print(f"  {p.name:<28} {sev_color}{p.severity.upper():<8}{NC} "
              f"{format_number(p.tokens_wasted):>13}  "
              f"{'+ ' + str(len(new_rules)) + ' rule(s)' if new_rules else '✓ already ignored'}")

        for r in new_rules:
            added_rules.append(r)
            existing_set.add(r)
        skipped.extend(already)

    if not added_rules:
        print(f"\n  {GREEN}✓ All rules already present in .llmignore{NC}\n")
        return 0

    # Build new .llmignore content
    new_lines = existing.copy()
    if new_lines and new_lines[-1] != "":
        new_lines.append("")
    new_lines.append("# Added by distill fix")
    new_lines.extend(added_rules)

    # Write temporarily (even for dry-run) so after-scan is accurate
    ig_path          = path / ".llmignore"
    original_content = ig_path.read_text(encoding='utf-8') if ig_path.exists() else None
    _write_llmignore(path, new_lines)

    after        = scan_directory(path, model, respect_llmignore=True)
    after_tokens = sum(f["tokens"] for f in after)
    after_cost   = sum(f["cost_usd"] for f in after)
    after_pct    = after_tokens / ctx_limit * 100
    saved_tokens = before_tokens - after_tokens
    saved_cost   = before_cost - after_cost
    saved_pct    = (saved_tokens / before_tokens * 100) if before_tokens else 0

    # Restore if dry-run
    if dry_run:
        if original_content is None:
            ig_path.unlink(missing_ok=True)
        else:
            ig_path.write_text(original_content, encoding='utf-8')

    print(f"\n  {'─'*54}")
    if dry_run:
        print(f"  {YELLOW}DRY RUN — no files written{NC}")
        print(f"  Would add {len(added_rules)} rule(s) to .llmignore")
    else:
        print(f"  {GREEN}✓ Written to .llmignore ({len(added_rules)} rule(s) added){NC}")

    print(f"\n  After   : {format_number(after_tokens)} tokens  "
          f"({after_pct:.1f}% ctx)  {format_cost(after_cost)}/session")
    print(f"  {GREEN}Saved   : {format_number(saved_tokens)} tokens  "
          f"({saved_pct:.1f}% reduction)  {format_cost(saved_cost)}/session{NC}")
    sessions_per_dollar = int(1 / after_cost) if after_cost > 0 else 0
    print(f"  Now     : {sessions_per_dollar} sessions / $1")

    if skipped:
        print(f"\n  Already in .llmignore: {', '.join(skipped)}")

    print()
    return 0


def main():
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        elif hasattr(sys.stdout, 'buffer'):
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Auto-fix context waste by updating .llmignore")
    parser.add_argument("--path",         default=".", help="Project root to fix")
    parser.add_argument("--model",        default="claude", help="Model for token/cost estimates")
    parser.add_argument("--dry-run",      action="store_true", help="Show changes without writing")
    parser.add_argument("--min-severity", default="high",
                        choices=["high", "medium", "low"],
                        help="Minimum severity to auto-fix (default: high)")
    args = parser.parse_args()
    sys.exit(run_fix(Path(args.path), model=args.model,
                     dry_run=args.dry_run, min_severity=args.min_severity))


if __name__ == "__main__":
    main()
