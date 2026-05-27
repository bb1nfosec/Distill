#!/usr/bin/env python3
"""
token_counter.py - Estimate token costs and dollar spend for any LLM.

Usage:
    python3 core/token_counter.py --path ./my-project
    python3 core/token_counter.py --path . --model openai --cost
    python3 core/token_counter.py --file ./src/api/handler.ts
    python3 core/token_counter.py --path . --top 20
"""

import os
import sys
import argparse
import fnmatch
import warnings
from pathlib import Path, PurePosixPath

MODEL_RATIOS = {
    "claude":  4.2,
    "openai":  4.0,
    "gemini":  4.1,
    "ollama":  3.8,
    "generic": 4.0,
}

CONTEXT_LIMITS = {
    "claude":             200_000,
    "claude-sonnet":      200_000,
    "claude-haiku":       200_000,
    "claude-opus":        200_000,
    "gpt-4o":             128_000,
    "gpt-4o-mini":        128_000,
    "gpt-4-turbo":        128_000,
    "gpt-3.5":             16_000,
    "gemini-1.5-pro":   1_000_000,
    "gemini-2.0-flash": 1_048_576,
    "llama3":             128_000,
    "mistral":             32_000,
    "generic":            128_000,
    "ollama":             128_000,
}

# USD per 1M input tokens (input rate - what a scan estimate represents)
PRICING = {
    "claude":          3.00,   # claude-sonnet-4-5/4-6
    "claude-sonnet":   3.00,
    "claude-haiku":    0.80,
    "claude-opus":    15.00,
    "openai":          2.50,   # gpt-4o
    "gpt-4o":          2.50,
    "gpt-4o-mini":     0.15,
    "gemini":          1.25,   # gemini-1.5-pro
    "gemini-1.5-pro":  1.25,
    "gemini-2.0-flash":0.10,
    "ollama":          0.00,   # local - free
    "generic":         2.50,
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".mp3", ".wav", ".ogg",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".zip", ".tar", ".gz", ".br",
    ".pyc", ".pyo", ".pyd",
    ".so", ".dll", ".dylib", ".exe",
    ".db", ".sqlite", ".sqlite3",
    ".lock",
}

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "out",
    ".next", ".nuxt", ".svelte-kit", "coverage",
    ".nyc_output", "__pycache__", ".venv", "venv", "env",
    "target", "vendor", ".turbo", ".vercel", "storybook-static",
    "htmlcov", ".eggs", ".mypy_cache", ".ruff_cache",
}


def _matches_path_component(pattern: str, rel_path: str) -> bool:
    """Check if pattern matches as a complete path component (directory or filename).

    ``"dist"`` matches ``dist/foo.js`` but NOT ``distribution/config.py``.
    Uses ``PurePosixPath.parts`` for reliable component-level matching.
    """
    parts = PurePosixPath(rel_path.replace("\\", "/")).parts
    return pattern in parts


def is_tiktoken_available() -> bool:
    """Return True if tiktoken is installed and token counts are accurate."""
    try:
        import tiktoken  # noqa: F401
        return True
    except ImportError:
        return False


_TIKTOKEN_WARNING_SHOWN = False


def estimate_tokens(text: str, model: str = "generic") -> int:
    global _TIKTOKEN_WARNING_SHOWN
    ratio = MODEL_RATIOS.get(model, 4.0)
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        if not _TIKTOKEN_WARNING_SHOWN:
            warnings.warn(
                "tiktoken not installed - token counts are approximate "
                "(character-based estimation). Install tiktoken for accurate counts: "
                "pip install tiktoken",
                stacklevel=2,
            )
            _TIKTOKEN_WARNING_SHOWN = True
        return max(1, int(len(text) / ratio))


def estimate_cost(tokens: int, model: str) -> float:
    """Return estimated USD cost for `tokens` input tokens."""
    rate = PRICING.get(model, PRICING["generic"])
    return tokens / 1_000_000 * rate


def format_cost(usd: float) -> str:
    if usd == 0:
        return "$0.000 (local)"
    if usd < 0.01:
        return f"${usd:.4f}"
    return f"${usd:.2f}"


def scan_directory(path: Path, model: str, respect_llmignore: bool = True,
                   max_file_size: int = 500_000) -> list[dict]:
    ignore_patterns = set()
    negation_patterns = set()

    if respect_llmignore:
        for ignore_file in [".llmignore", ".claudeignore", ".gitignore"]:
            ig_path = path / ignore_file
            if ig_path.exists():
                with open(ig_path, encoding='utf-8', errors='replace') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            if line.startswith("!"):
                                negation_patterns.add(line[1:].rstrip("/"))
                            else:
                                ignore_patterns.add(line.rstrip("/"))

    def _is_negated(fname: str, rel_str: str) -> bool:
        """Check if a file is un-ignored by a negation pattern."""
        for neg in negation_patterns:
            if (fname == neg
                    or fnmatch.fnmatch(fname, neg)
                    or fnmatch.fnmatch(rel_str, neg)
                    or _matches_path_component(neg, rel_str)):
                return True
        return False

    def _dir_has_negation(dirname: str) -> bool:
        """Check if any negation pattern references files inside this directory."""
        for neg in negation_patterns:
            # e.g. negation "dist/important.js" should keep "dist" from being pruned
            if neg.startswith(dirname + "/") or _matches_path_component(dirname, neg):
                return True
        return False

    results = []
    for root, dirs, files in os.walk(path):
        root_path = Path(root)

        dirs[:] = [
            d for d in dirs
            if (
                d not in SKIP_DIRS
                or _dir_has_negation(d)
            )
            and not d.startswith(".")
            and (
                not any(
                    d == p or fnmatch.fnmatch(d, p)
                    for p in ignore_patterns
                )
                or _dir_has_negation(d)
            )
        ]

        for fname in files:
            fpath = root_path / fname
            rel_path = fpath.relative_to(path)

            if fpath.suffix.lower() in SKIP_EXTENSIONS:
                continue

            skip = False
            rel_str = str(rel_path).replace("\\", "/")

            # Check if file is inside a SKIP_DIRS directory kept alive by negation
            for skip_dir in SKIP_DIRS:
                if _matches_path_component(skip_dir, rel_str):
                    skip = True
                    break

            for pattern in ignore_patterns:
                if (_matches_path_component(pattern, rel_str)
                        or fname == pattern
                        or fnmatch.fnmatch(fname, pattern)
                        or fnmatch.fnmatch(rel_str, pattern)):
                    skip = True
                    break
            if skip and _is_negated(fname, rel_str):
                skip = False
            if skip:
                continue

            try:
                size = fpath.stat().st_size
                if size == 0:
                    continue
                if size > max_file_size:
                    results.append({
                        "path": str(rel_path),
                        "tokens": 0,
                        "lines": 0,
                        "size_kb": round(size / 1024, 1),
                        "cost_usd": 0.0,
                        "skipped": True,
                        "skip_reason": f"File size {round(size/1024, 1)}KB exceeds limit {round(max_file_size/1024, 1)}KB",
                    })
                    continue
                with open(fpath, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                tokens = estimate_tokens(content, model)
                lines = content.count("\n") + 1
                results.append({
                    "path": str(rel_path),
                    "tokens": tokens,
                    "lines": lines,
                    "size_kb": round(size / 1024, 1),
                    "cost_usd": estimate_cost(tokens, model),
                })
            except (PermissionError, OSError):
                continue

    return sorted(results, key=lambda x: x["tokens"], reverse=True)


def format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def print_report(results: list[dict], model: str, top_n: int = 20,
                 context_limit: int = None, show_cost: bool = True):
    active_results = [r for r in results if not r.get("skipped")]
    skipped_results = [r for r in results if r.get("skipped")]
    total_tokens = sum(r["tokens"] for r in active_results)
    total_cost   = sum(r["cost_usd"] for r in active_results)
    total_files  = len(active_results)
    limit        = context_limit or CONTEXT_LIMITS.get(model, 128_000)
    pct          = (total_tokens / limit) * 100

    RED = "\033[91m"; YELLOW = "\033[93m"; GREEN = "\033[92m"
    CYAN = "\033[96m"; BOLD = "\033[1m"; NC = "\033[0m"

    color = GREEN if pct < 30 else (YELLOW if pct < 70 else RED)
    rate  = PRICING.get(model, PRICING["generic"])

    print(f"\n{BOLD}{'─'*62}{NC}")
    print(f"{BOLD}  distill - Context Audit{NC}")
    print(f"{'─'*62}")
    print(f"  Model         : {model}  (${rate:.2f} / 1M input tokens)")
    print(f"  Context limit : {format_number(limit)} tokens")
    print(f"  Files scanned : {total_files:,}")
    print(f"  Total tokens  : {BOLD}{color}{format_number(total_tokens)}{NC}  ({pct:.1f}% of context)")
    if show_cost:
        print(f"  Per-session $  : {BOLD}{format_cost(total_cost)}{NC}  (input cost, context loaded once)")
        sessions_per_dollar = (1 / total_cost) if total_cost > 0 else float("inf")
        if sessions_per_dollar < float("inf"):
            print(f"  Sessions / $1  : {sessions_per_dollar:.0f}")
    print(f"{'─'*62}\n")

    if pct > 100:
        print(f"  {RED}✗ OVER CONTEXT LIMIT{NC} - LLM cannot read all files in one pass")
        print(f"    → Add paths to .llmignore")
        print(f"    → Use subagents for different subsystems\n")
    elif pct > 70:
        print(f"  {YELLOW}⚠  Heavy context{NC} - quality may degrade near limit")
        print(f"    → Review top files below and ignore the largest unnecessary ones\n")
    else:
        print(f"  {GREEN}✓ Context healthy{NC}\n")

    col = f"  {'File':<48} {'Tokens':>8}  {'Lines':>6}  {'Size':>7}"
    if show_cost:
        col += f"  {'Cost':>8}"
    print(f"{BOLD}{col}{NC}")

    sep = f"  {'─'*48} {'─'*8}  {'─'*6}  {'─'*7}"
    if show_cost:
        sep += f"  {'─'*8}"
    print(sep)

    for r in active_results[:top_n]:
        path_str = r["path"][:47]
        line = f"  {path_str:<48} {format_number(r['tokens']):>8}  {r['lines']:>6}  {r['size_kb']:>6}KB"
        if show_cost:
            line += f"  {format_cost(r['cost_usd']):>8}"
        print(line)

    if len(active_results) > top_n:
        remaining_tok  = sum(r["tokens"]   for r in active_results[top_n:])
        remaining_cost = sum(r["cost_usd"] for r in active_results[top_n:])
        line = f"  {'... and ' + str(len(active_results)-top_n) + ' more files':<48} {format_number(remaining_tok):>8}"
        if show_cost:
            line += f"  {'':>8}  {'':>6}  {'':>7}  {format_cost(remaining_cost):>8}"
        print(line)

    if skipped_results:
        print(f"\n  {YELLOW}⚠  {len(skipped_results)} file(s) skipped (over size limit):{NC}")
        for sr in skipped_results[:5]:
            print(f"      {sr['path']}  ({sr['size_kb']}KB - {sr['skip_reason']})")
        if len(skipped_results) > 5:
            print(f"      ... and {len(skipped_results) - 5} more")

    print(f"\n  {BOLD}Recommendations:{NC}")

    large_files = [r for r in active_results if r["tokens"] > 5000]
    if large_files:
        print(f"  {YELLOW}→{NC} {len(large_files)} files over 5k tokens - split or ignore:")
        for f in large_files[:3]:
            print(f"      {f['path']} ({format_number(f['tokens'])} tokens, {format_cost(f['cost_usd'])})")

    _lock_names = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml",
                   "bun.lockb", "Gemfile.lock", "poetry.lock", "Cargo.lock"}
    lock_files = [r for r in active_results if Path(r["path"]).name in _lock_names]
    if lock_files:
        tot = sum(r["tokens"] for r in lock_files)
        cost = sum(r["cost_usd"] for r in lock_files)
        print(f"  {RED}→{NC} Lock files: {format_number(tot)} tokens ({format_cost(cost)}) - add to .llmignore")

    _gen_dirs = {"dist", "build", "generated"}
    _gen_exts = {".min.js", ".min.css", ".bundle.js"}
    def _is_gen(p: str) -> bool:
        norm = p.replace("\\", "/")
        parts = Path(norm).parts
        name = parts[-1] if parts else ""
        return any(d in parts for d in _gen_dirs) or any(name.endswith(e) for e in _gen_exts)
    generated = [r for r in active_results if _is_gen(r["path"])]
    if generated:
        tot = sum(r["tokens"] for r in generated)
        print(f"  {YELLOW}→{NC} Generated/built files: {format_number(tot)} tokens - ignore them")

    print(f"\n{'─'*62}\n")


def main():
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        elif hasattr(sys.stdout, 'buffer'):
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Estimate token costs and $ spend for any codebase")
    parser.add_argument("--path",     "-p", default=".",      help="Directory to scan (default: .)")
    parser.add_argument("--file",     "-f",                   help="Scan a single file")
    parser.add_argument("--model",    "-m", default="claude",
                        choices=list(MODEL_RATIOS.keys()),     help="LLM model family")
    parser.add_argument("--top",      "-t", type=int, default=20, help="Show top N files")
    parser.add_argument("--cost",     "-c", action="store_true",  help="Show per-file cost column (always shown in header)")
    parser.add_argument("--no-cost",        action="store_true",  help="Hide cost column")
    parser.add_argument("--no-ignore",      action="store_true",  help="Ignore .llmignore files")
    parser.add_argument("--max-file-size", type=int, default=500_000,
                        help="Max file size in bytes before skipping (default: 500000)")
    parser.add_argument("--json",           action="store_true",  help="Output raw JSON")
    args = parser.parse_args()

    show_cost = not args.no_cost

    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
        tokens = estimate_tokens(content, args.model)
        cost   = estimate_cost(tokens, args.model)
        print(f"{path}: {format_number(tokens)} tokens  {format_cost(cost)}  ({path.stat().st_size // 1024}KB)")
        return

    path = Path(args.path).resolve()
    if not path.exists():
        print(f"Path not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {path}...", file=sys.stderr)
    results = scan_directory(path, args.model, respect_llmignore=not args.no_ignore,
                             max_file_size=args.max_file_size)

    if args.json:
        import json
        print(json.dumps(results, indent=2))
        return

    print_report(results, args.model, top_n=args.top, show_cost=show_cost)


if __name__ == "__main__":
    main()
