#!/usr/bin/env python3
"""
token_counter.py — Estimate token costs for any LLM before you run.

Usage:
    python3 core/token_counter.py --path ./my-project
    python3 core/token_counter.py --path ./my-project --model openai
    python3 core/token_counter.py --file ./src/api/handler.ts
    python3 core/token_counter.py --path . --top 20
"""

import os
import sys
import argparse
from pathlib import Path

# Token approximation ratios per model family
# (chars per token — higher = fewer tokens per char = cheaper)
MODEL_RATIOS = {
    "claude":  4.2,   # Claude tokenizer (cl100k-based)
    "openai":  4.0,   # GPT-4 / GPT-4o
    "gemini":  4.1,   # Gemini 1.5
    "ollama":  3.8,   # Llama/Mistral — slightly more tokens
    "generic": 4.0,
}

# Context window limits per model
CONTEXT_LIMITS = {
    "claude":        200_000,
    "claude-sonnet": 200_000,
    "claude-haiku":  200_000,
    "gpt-4o":        128_000,
    "gpt-4-turbo":   128_000,
    "gpt-3.5":        16_000,
    "gemini-1.5-pro": 1_000_000,
    "gemini-2.0":     1_000_000,
    "llama3":          128_000,
    "mistral":          32_000,
    "generic":         128_000,
}

# Files to always skip
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".mp3", ".wav", ".ogg",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".zip", ".tar", ".gz", ".br",
    ".pyc", ".pyo", ".pyd",
    ".so", ".dll", ".dylib", ".exe",
    ".db", ".sqlite", ".sqlite3",
    ".lock",  # lock files are huge and useless
}

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "out",
    ".next", ".nuxt", ".svelte-kit", "coverage",
    ".nyc_output", "__pycache__", ".venv", "venv", "env",
    "target", "vendor", ".turbo", ".vercel", "storybook-static",
    "htmlcov", ".eggs", ".mypy_cache", ".ruff_cache",
}


def estimate_tokens(text: str, model: str = "generic") -> int:
    ratio = MODEL_RATIOS.get(model, 4.0)
    # Try tiktoken for accuracy if available
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return max(1, int(len(text) / ratio))


def scan_directory(path: Path, model: str, respect_llmignore: bool = True) -> list[dict]:
    """Walk directory and return token estimates per file."""
    ignore_patterns = set()
    
    if respect_llmignore:
        for ignore_file in [".llmignore", ".claudeignore", ".gitignore"]:
            ig_path = path / ignore_file
            if ig_path.exists():
                with open(ig_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            ignore_patterns.add(line.rstrip("/"))

    results = []
    for root, dirs, files in os.walk(path):
        root_path = Path(root)
        
        # Skip ignored dirs
        dirs[:] = [
            d for d in dirs
            if d not in SKIP_DIRS
            and not d.startswith(".")
            and d not in ignore_patterns
        ]

        for fname in files:
            fpath = root_path / fname
            rel_path = fpath.relative_to(path)

            # Skip binary/generated extensions
            if fpath.suffix.lower() in SKIP_EXTENSIONS:
                continue

            # Skip ignored patterns (simple glob match)
            skip = False
            for pattern in ignore_patterns:
                if pattern in str(rel_path) or fname == pattern:
                    skip = True
                    break
            if skip:
                continue

            try:
                size = fpath.stat().st_size
                if size == 0 or size > 500_000:  # skip empty or >500KB
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


def print_report(results: list[dict], model: str, top_n: int = 20, context_limit: int = None):
    total_tokens = sum(r["tokens"] for r in results)
    total_files = len(results)
    limit = context_limit or CONTEXT_LIMITS.get(model, 128_000)
    pct_of_context = (total_tokens / limit) * 100

    # ANSI colors
    RED = "\033[91m"; YELLOW = "\033[93m"; GREEN = "\033[92m"
    CYAN = "\033[96m"; BOLD = "\033[1m"; NC = "\033[0m"

    color = GREEN if pct_of_context < 30 else (YELLOW if pct_of_context < 70 else RED)

    print(f"\n{BOLD}{'─'*60}{NC}")
    print(f"{BOLD}  LLM Token Optimizer — Context Audit{NC}")
    print(f"{'─'*60}")
    print(f"  Model         : {model}")
    print(f"  Context limit : {format_number(limit)} tokens")
    print(f"  Files scanned : {total_files:,}")
    print(f"  Total tokens  : {BOLD}{color}{format_number(total_tokens)}{NC}")
    print(f"  % of context  : {color}{pct_of_context:.1f}%{NC}")
    print(f"{'─'*60}\n")

    if pct_of_context > 100:
        print(f"  {RED}✗ OVER CONTEXT LIMIT — Claude cannot read all files in one session{NC}")
        print(f"    → Add more paths to .llmignore")
        print(f"    → Use subagents for different parts of the codebase\n")
    elif pct_of_context > 70:
        print(f"  {YELLOW}⚠  Heavy context — risk of degraded quality near limit{NC}")
        print(f"    → Review the top files below and add large ones to .llmignore\n")
    else:
        print(f"  {GREEN}✓ Context looks healthy{NC}\n")

    print(f"  {BOLD}Top {min(top_n, len(results))} token consumers:{NC}")
    print(f"  {'File':<50} {'Tokens':>8}  {'Lines':>6}  {'Size':>7}")
    print(f"  {'─'*50} {'─'*8}  {'─'*6}  {'─'*7}")

    cumulative = 0
    for r in results[:top_n]:
        cumulative += r["tokens"]
        pct = r["tokens"] / total_tokens * 100 if total_tokens else 0
        bar = "█" * int(pct / 2)
        path_str = r["path"][:49]
        print(f"  {path_str:<50} {format_number(r['tokens']):>8}  {r['lines']:>6}  {r['size_kb']:>6}KB")

    if len(results) > top_n:
        remaining = sum(r["tokens"] for r in results[top_n:])
        print(f"  {'... and ' + str(len(results)-top_n) + ' more files':<50} {format_number(remaining):>8}")

    print(f"\n  {BOLD}Recommendations:{NC}")

    # Smart recommendations
    large_files = [r for r in results if r["tokens"] > 5000]
    if large_files:
        print(f"  {YELLOW}→{NC} {len(large_files)} files over 5k tokens — consider splitting or ignoring:")
        for f in large_files[:3]:
            print(f"      {f['path']} ({format_number(f['tokens'])} tokens)")

    lock_files = [r for r in results if any(x in r["path"] for x in ["lock", "Lock"])]
    if lock_files:
        total_lock = sum(r["tokens"] for r in lock_files)
        print(f"  {RED}→{NC} Lock files using {format_number(total_lock)} tokens — add to .llmignore!")

    generated = [r for r in results if any(x in r["path"] for x in ["generated", "dist/", "build/", ".min."])]
    if generated:
        total_gen = sum(r["tokens"] for r in generated)
        print(f"  {YELLOW}→{NC} Generated/built files using {format_number(total_gen)} tokens — ignore them")

    print(f"\n{'─'*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Estimate LLM token costs for a codebase")
    parser.add_argument("--path",  "-p", default=".", help="Directory to scan (default: .)")
    parser.add_argument("--file",  "-f", help="Scan a single file")
    parser.add_argument("--model", "-m", default="claude",
                        choices=list(MODEL_RATIOS.keys()), help="LLM model family")
    parser.add_argument("--top",   "-t", type=int, default=20, help="Show top N files")
    parser.add_argument("--no-ignore", action="store_true", help="Ignore .llmignore files")
    parser.add_argument("--json",  action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
        tokens = estimate_tokens(content, args.model)
        print(f"{path}: {format_number(tokens)} tokens ({path.stat().st_size // 1024}KB)")
        return

    path = Path(args.path).resolve()
    if not path.exists():
        print(f"Path not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {path}...", file=sys.stderr)
    results = scan_directory(path, args.model, respect_llmignore=not args.no_ignore)

    if args.json:
        import json
        print(json.dumps(results, indent=2))
        return

    print_report(results, args.model, top_n=args.top)


if __name__ == "__main__":
    main()
