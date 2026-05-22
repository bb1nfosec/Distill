"""distill MCP server — exposes token scanning and budget gates as Claude tools."""

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.token_counter import scan_directory, print_report, estimate_cost, CONTEXT_LIMITS, PRICING
from core.context_analyzer import analyze_directory
from core.check import run_check

mcp = FastMCP("distill")


@mcp.tool()
def scan_tokens(
    path: str = ".",
    model: str = "claude",
    top_n: int = 20,
    extensions: str = "",
) -> str:
    """Scan a directory for token usage and dollar cost per file.

    Args:
        path: Directory to scan (default: current directory).
        model: Pricing model — claude, claude-haiku, claude-opus, gpt-4o, gpt-4o-mini, gemini, ollama.
        top_n: Number of files to show (default 20, sorted by token count).
        extensions: Comma-separated list of extensions to include, e.g. 'py,ts,md'. Empty = all.
    """
    ext_filter = {e.strip().lstrip(".") for e in extensions.split(",") if e.strip()}
    files = scan_directory(Path(path), model=model)
    if ext_filter:
        files = [f for f in files if Path(f["path"]).suffix.lstrip(".") in ext_filter]
    files.sort(key=lambda f: f["tokens"], reverse=True)

    total_tokens = sum(f["tokens"] for f in files)
    total_cost = sum(f.get("cost_usd", 0) for f in files)
    ctx_limit = CONTEXT_LIMITS.get(model, 200_000)
    pct = (total_tokens / ctx_limit * 100) if ctx_limit else 0
    price_per_m = PRICING.get(model, 2.50)

    lines = [
        f"distill scan — {path}",
        f"Model     : {model}  (${price_per_m:.2f}/1M tokens)",
        f"Files     : {len(files)}",
        f"Tokens    : {total_tokens:,}  ({pct:.1f}% of {ctx_limit // 1000}k ctx)",
        f"Session $ : ${total_cost:.4f}",
        f"Per $1    : {int(1 / total_cost) if total_cost > 0 else '∞'} sessions",
        "",
        f"{'File':<50} {'Tokens':>8}  {'Cost':>9}",
        "─" * 70,
    ]

    for f in files[:top_n]:
        rel = str(Path(f["path"]).relative_to(Path(path).resolve()) if Path(f["path"]).is_absolute() else f["path"])
        lines.append(f"{rel:<50} {f['tokens']:>8,}  ${f.get('cost_usd', 0):>8.4f}")

    if len(files) > top_n:
        lines.append(f"  … and {len(files) - top_n} more files")

    return "\n".join(lines)


@mcp.tool()
def check_budget(
    path: str = ".",
    model: str = "claude",
    max_pct: float = 30.0,
    fail_on_waste: bool = False,
) -> str:
    """Run the distill CI budget gate. Returns PASS or FAIL with details.

    Args:
        path: Directory to check (default: current directory).
        model: LLM model for token counting and pricing.
        max_pct: Maximum allowed context percentage (default 30%).
        fail_on_waste: Also fail if HIGH-severity waste patterns are detected.
    """
    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = run_check(Path(path), model=model, max_pct=max_pct, fail_on_waste=fail_on_waste)
    output = buf.getvalue()
    result = "PASS" if exit_code == 0 else "FAIL"
    return f"{result} (exit {exit_code})\n\n{output}"


@mcp.tool()
def analyze_context(path: str = ".") -> str:
    """Detect context waste patterns: lock files, build artifacts, minified assets, etc.

    Returns a list of patterns found with severity (HIGH/MEDIUM/LOW), tokens wasted,
    and the .llmignore rule to eliminate each one.

    Args:
        path: Directory to analyze (default: current directory).
    """
    patterns = analyze_directory(Path(path))
    if not patterns:
        return "No waste patterns detected. Context looks clean."

    lines = [f"Context waste patterns in {path}:", ""]
    for p in sorted(patterns, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.severity, 3)):
        lines += [
            f"[{p.severity.upper()}] {p.name}",
            f"  Files   : {len(p.files)}",
            f"  Tokens  : {p.tokens_wasted:,}",
            f"  Fix     : {p.fix}",
            "",
        ]
    total_waste = sum(p.tokens_wasted for p in patterns)
    lines.append(f"Total waste: {total_waste:,} tokens")
    return "\n".join(lines)


@mcp.tool()
def generate_llmignore(path: str = ".") -> str:
    """Generate an optimized .llmignore for the project at path.

    Detects project type (Node/Python/Go/Rust/etc.) and returns the recommended
    .llmignore content. Does NOT write to disk — returns the content for review.

    Args:
        path: Project root to analyze (default: current directory).
    """
    from scripts.generate_config import detect_project, generate_llmignore
    info = detect_project(Path(path))
    content = generate_llmignore(info)
    project_type = info.get("type", "unknown")
    return f"# Detected project type: {project_type}\n# Copy to {path}/.llmignore\n\n{content}"


@mcp.tool()
def fix_context(
    path: str = ".",
    model: str = "claude",
    dry_run: bool = False,
    min_severity: str = "high",
) -> str:
    """Automatically fix context waste by writing .llmignore rules.

    Detects waste patterns (lock files, build artifacts, snapshots, logs),
    appends the correct ignore rules to .llmignore, and returns a before/after
    comparison showing tokens and dollars saved.

    Args:
        path: Project root to fix (default: current directory).
        model: LLM model for token counting and cost estimates.
        dry_run: If True, show what would change without writing any files.
        min_severity: Minimum severity level to auto-fix — 'high' (default), 'medium', or 'low'.
    """
    from core.fix import run_fix
    buf = io.StringIO()
    with redirect_stdout(buf):
        run_fix(Path(path), model=model, dry_run=dry_run, min_severity=min_severity)
    return buf.getvalue()


def main():
    mcp.run()


if __name__ == "__main__":
    main()
