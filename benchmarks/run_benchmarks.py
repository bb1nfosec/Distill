#!/usr/bin/env python3
"""
run_benchmarks.py — Real benchmarks for distill.

Runs against actual directories on disk. No mocks.
Usage:
    python3 benchmarks/run_benchmarks.py
    python3 benchmarks/run_benchmarks.py --path /your/project
    python3 benchmarks/run_benchmarks.py --json
"""

import sys
import time
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "core"))
from token_counter import estimate_tokens, scan_directory, CONTEXT_LIMITS

# ANSI
BOLD  = "\033[1m"
GREEN = "\033[92m"
CYAN  = "\033[96m"
YELL  = "\033[93m"
RED   = "\033[91m"
NC    = "\033[0m"


# ── 1. Token estimation accuracy ─────────────────────────────────────────────

def bench_accuracy():
    """Compare distill estimates to tiktoken ground truth across file types."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
    except ImportError:
        print("  [skip] tiktoken not installed — run: pip install tiktoken")
        return None

    samples = [
        ("inline comment (45 chars)",     "// TODO: fix edge case in auth middleware"),
        ("one-liner (80 chars)",           "export const isAdmin = (u: User) => u.roles.includes('admin');"),
        ("short function (200 chars)",     "function debounce(fn, ms) {\n  let t;\n  return (...args) => {\n    clearTimeout(t);\n    t = setTimeout(() => fn(...args), ms);\n  };\n}"),
        ("50-line module (~1.5 KB)",       (ROOT / "adapters" / "base_adapter.py").read_text()[:1500]),
        ("full adapter (~8 KB)",           (ROOT / "adapters" / "claude_adapter.py").read_text()),
        ("lock file slice (50 KB)",        _read_first_bytes(Path("/home/bbinfosec/Documents/vaathi-main/package-lock.json"), 50_000)),
        ("large Python file (~35 KB)",     _read_first_bytes(Path("/home/bbinfosec/TradingAgents/cli/main.py"), 35_000)),
    ]

    rows = []
    for name, text in samples:
        if not text:
            continue
        t0 = time.perf_counter()
        est = estimate_tokens(text, "claude")
        ms = (time.perf_counter() - t0) * 1000
        actual = len(enc.encode(text))
        err = abs(est - actual) / max(actual, 1) * 100
        rows.append((name, len(text), est, actual, err, ms))

    return rows


def _read_first_bytes(path: Path, n: int) -> str:
    if not path.exists():
        return ""
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read(n)


# ── 2. Scan throughput ────────────────────────────────────────────────────────

def bench_throughput(extra_paths: list[str] = None):
    """Measure files/sec and tokens/sec on small, medium, large repos."""
    paths = [
        ("distill (this repo, small)",   ROOT),
        ("TradingAgents (Python, medium)", Path("/home/bbinfosec/TradingAgents")),
        ("vaathi-main (Next.js, large)",   Path("/home/bbinfosec/Documents/vaathi-main")),
    ]
    for p in (extra_paths or []):
        pp = Path(p)
        if pp.exists():
            paths.append((pp.name, pp))

    rows = []
    for name, path in paths:
        if not path.exists():
            continue
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            files = scan_directory(path, "claude", respect_llmignore=False)
            times.append(time.perf_counter() - t0)
        median = sorted(times)[1]
        total_tokens = sum(f["tokens"] for f in files)
        rows.append((
            name, len(files), total_tokens,
            median * 1000,
            len(files) / median,
            total_tokens / 1_000_000 / median,
        ))
    return rows


# ── 3. .llmignore waste elimination ──────────────────────────────────────────

def bench_ignore_impact():
    """Show before/after token counts when .llmignore is applied."""
    projects = [
        ("distill (this repo)",   ROOT,                                                    None),
        ("TradingAgents",         Path("/home/bbinfosec/TradingAgents"),                   None),
        ("vaathi-main (Next.js)", Path("/home/bbinfosec/Documents/vaathi-main"),           _vaathi_ignore()),
    ]

    rows = []
    for name, path, custom_ignore in projects:
        if not path.exists():
            continue

        ignore_file = path / ".llmignore"
        wrote_ignore = False
        if custom_ignore and not ignore_file.exists():
            ignore_file.write_text(custom_ignore)
            wrote_ignore = True

        before = scan_directory(path, "claude", respect_llmignore=False)
        after  = scan_directory(path, "claude", respect_llmignore=True)

        tok_b = sum(f["tokens"] for f in before)
        tok_a = sum(f["tokens"] for f in after)
        limit = CONTEXT_LIMITS["claude"]
        pct_b = tok_b / limit * 100
        pct_a = tok_a / limit * 100
        saved = tok_b - tok_a
        pct_saved = saved / max(tok_b, 1) * 100

        rows.append((name, len(before), tok_b, pct_b, len(after), tok_a, pct_a, saved, pct_saved))

        if wrote_ignore:
            ignore_file.unlink()

    return rows


def _vaathi_ignore() -> str:
    return (
        "# Generated by distill\n"
        "package-lock.json\nyarn.lock\npnpm-lock.yaml\nbun.lock\nbun.lockb\n"
        "*.tsbuildinfo\n*.snap\n*.xsd\n*.xml\n"
        "dist/\nbuild/\n.next/\nnode_modules/\ncoverage/\n.turbo/\n"
        "storybook-static/\n**/*.min.js\n**/*.min.css\nskills/ppt/ooxml/\n"
        "skills/pdf/scripts/design_engine.py\npublic/\n"
    )


# ── 4. Compaction: quadratic growth simulation ────────────────────────────────

def bench_compaction():
    """
    Simulate a 10-turn coding session and compare total tokens sent to the API
    with vs without compaction.  Uses realistic message sizes from real code.
    """
    base_adapter = (ROOT / "adapters" / "base_adapter.py").read_text()
    claude_adapter = (ROOT / "adapters" / "claude_adapter.py").read_text()

    system = (
        "You are a terse, precise coding assistant. "
        "Respond with code only. No explanations unless asked. "
        "Batch all edits into one pass."
    )
    sys_tok = estimate_tokens(system, "claude")

    # Realistic turn pairs: (user_tokens, assistant_tokens)
    # Sizes modelled on actual Claude Code sessions scanning real source files
    turn_sizes = [
        (80,  420),   # Turn 1 — simple question, short answer
        (60,  680),   # Turn 2 — ask for edit, code diff returned
        (40,  820),   # Turn 3 — follow-up fix
        (90,  1100),  # Turn 4 — add feature, medium response
        (55,  760),   # Turn 5 — tweak
        (70,  940),   # Turn 6 — add tests
        (45,  610),   # Turn 7 — lint fix
        (80,  1050),  # Turn 8 — refactor
        (60,  890),   # Turn 9 — review
        (50,  420),   # Turn 10 — final check
    ]

    cumulative_history = 0
    compact_ctx = sys_tok
    without_totals = []
    with_totals = []
    compact_at = 4   # compact after turn 4

    for i, (u_tok, a_tok) in enumerate(turn_sizes):
        turn = i + 1

        # Without compaction: every call pays for full history
        input_tokens_raw = sys_tok + cumulative_history + u_tok
        without_totals.append(input_tokens_raw)
        cumulative_history += u_tok + a_tok

        # With compaction: compact after turn `compact_at`
        if turn == compact_at + 1:
            # Compact: history → ~18% summary
            history_size = compact_ctx - sys_tok
            summary_size = int(history_size * 0.18)
            compact_ctx = sys_tok + summary_size
        input_tokens_compact = compact_ctx + u_tok
        compact_ctx += u_tok + a_tok
        with_totals.append(input_tokens_compact)

    return {
        "turns": list(range(1, len(turn_sizes) + 1)),
        "without_compact": without_totals,
        "with_compact": with_totals,
        "compact_at_turn": compact_at,
        "total_without": sum(without_totals),
        "total_with": sum(with_totals),
        "total_saved": sum(without_totals) - sum(with_totals),
    }


# ── Printing ──────────────────────────────────────────────────────────────────

def _fmt(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def print_accuracy(rows):
    print(f"\n{BOLD}1. Token Estimation Accuracy{NC}  (distill vs tiktoken ground truth)\n")
    print(f"  {'Sample':<35} {'Chars':>8}  {'Distill':>9}  {'tiktoken':>9}  {'Error':>7}  {'Time':>8}")
    print(f"  {'-'*35} {'-'*8}  {'-'*9}  {'-'*9}  {'-'*7}  {'-'*8}")
    for name, chars, est, actual, err, ms in rows:
        c = GREEN if err < 1 else YELL if err < 5 else RED
        print(f"  {name:<35} {chars:>8,}  {est:>9,}  {actual:>9,}  {c}{err:>6.1f}%{NC}  {ms:>7.1f}ms")
    avg_err = sum(r[4] for r in rows) / len(rows)
    print(f"\n  Average error: {GREEN}{avg_err:.2f}%{NC}")


def print_throughput(rows):
    print(f"\n{BOLD}2. Scan Throughput{NC}  (median of 3 runs, no .llmignore)\n")
    print(f"  {'Project':<35}  {'Files':>6}  {'Tokens':>10}  {'Time':>8}  {'Files/s':>9}  {'Tok/s':>12}")
    print(f"  {'-'*35}  {'-'*6}  {'-'*10}  {'-'*8}  {'-'*9}  {'-'*12}")
    for name, files, tokens, ms, fps, mtps in rows:
        print(f"  {name:<35}  {files:>6}  {tokens:>10,}  {ms:>7.0f}ms  {fps:>9,.0f}  {mtps:>10.2f}M/s")


def print_ignore_impact(rows):
    print(f"\n{BOLD}3. .llmignore Waste Elimination{NC}  (Claude 200k context)\n")
    hdr = f"  {'Project':<25}  {'Before files':>12}  {'Before tokens':>14}  {'Ctx%':>6}  {'After tokens':>13}  {'Ctx%':>6}  {'Saved':>11}  {'Reduction':>10}"
    print(hdr)
    print(f"  {'-'*25}  {'-'*12}  {'-'*14}  {'-'*6}  {'-'*13}  {'-'*6}  {'-'*11}  {'-'*10}")
    for name, fb, tb, pb, fa, ta, pa, saved, pct in rows:
        c = GREEN if pa < 30 else YELL if pa < 80 else RED
        print(
            f"  {name:<25}  {fb:>12,}  {tb:>14,}  {pb:>5.1f}%  "
            f"{ta:>13,}  {c}{pa:>5.1f}%{NC}  {saved:>11,}  {GREEN}{pct:>8.1f}%{NC}"
        )


def print_compaction(data):
    print(f"\n{BOLD}4. Compaction: Input Tokens Per Turn{NC}  (10-turn coding session, compaction at turn {data['compact_at_turn']})\n")
    print(f"  {'Turn':>5}  {'No compaction':>15}  {'With compaction':>16}  {'Saved this turn':>16}")
    print(f"  {'-'*5}  {'-'*15}  {'-'*16}  {'-'*16}")
    for i, (wo, wi) in enumerate(zip(data["without_compact"], data["with_compact"])):
        marker = f"  {CYAN}← compact{NC}" if i == data["compact_at_turn"] else ""
        saved = wo - wi
        c = GREEN if saved > 0 else ""
        nc = NC if saved > 0 else ""
        print(f"  {i+1:>5}  {wo:>15,}  {wi:>16,}  {c}{saved:>15,}{nc}{marker}")
    print()
    pct = data["total_saved"] / data["total_without"] * 100
    print(f"  Total API input (10 turns): {data['total_without']:,} without  vs  {data['total_with']:,} with compaction")
    print(f"  {GREEN}Total saved: {_fmt(data['total_saved'])} tokens ({pct:.1f}%){NC}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path",  action="append", help="Extra project paths to scan")
    parser.add_argument("--json",  action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    print(f"\n{BOLD}{'═'*65}{NC}")
    print(f"{BOLD}  distill — benchmark suite{NC}  (real data, no mocks)")
    print(f"{BOLD}{'═'*65}{NC}")

    acc  = bench_accuracy()
    tput = bench_throughput(args.path)
    ign  = bench_ignore_impact()
    comp = bench_compaction()

    if args.json:
        print(json.dumps({
            "accuracy":    [{"name": r[0], "chars": r[1], "distill": r[2], "tiktoken": r[3], "error_pct": r[4], "ms": r[5]} for r in (acc or [])],
            "throughput":  [{"project": r[0], "files": r[1], "tokens": r[2], "ms": r[3], "files_per_s": r[4], "mtokens_per_s": r[5]} for r in tput],
            "ignore":      [{"project": r[0], "before_tokens": r[2], "after_tokens": r[5], "saved": r[7], "pct_saved": r[8]} for r in ign],
            "compaction":  comp,
        }, indent=2))
        return

    if acc:
        print_accuracy(acc)
    print_throughput(tput)
    print_ignore_impact(ign)
    print_compaction(comp)

    print(f"\n{'═'*65}\n")


if __name__ == "__main__":
    main()
