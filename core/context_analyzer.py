#!/usr/bin/env python3
"""
context_analyzer.py - Audit what's eating your LLM context window.

Analyzes a conversation/session log or directory and surfaces
the top waste patterns with actionable fixes.

Usage:
    python3 core/context_analyzer.py --path ./my-project
    python3 core/context_analyzer.py --session ./session.json --model openai
"""

import os
import sys
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class WastePattern:
    name: str
    tokens_wasted: int
    severity: str          # "high" | "medium" | "low"
    description: str
    fix: str
    files: list = field(default_factory=list)
    llmignore_entries: list = field(default_factory=list)  # non-empty → auto-fixable


def analyze_directory(path: Path, model: str = "claude") -> list[WastePattern]:
    """Identify token waste patterns in a project directory."""
    patterns = []
    
    # Import token counter
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from token_counter import estimate_tokens, scan_directory, SKIP_DIRS

    all_files = scan_directory(path, model, respect_llmignore=False)
    ignored_files = scan_directory(path, model, respect_llmignore=True)
    ignored_paths = {f["path"] for f in ignored_files}
    
    # Pattern 1: Lock files (exact filename match via Path.name)
    _lock_names = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml",
                   "bun.lockb", "Gemfile.lock", "poetry.lock", "Cargo.lock"}
    lock_files = [f for f in all_files if Path(f["path"]).name in _lock_names]
    if lock_files:
        total = sum(f["tokens"] for f in lock_files)
        patterns.append(WastePattern(
            name="Lock files",
            tokens_wasted=total,
            severity="high",
            description=f"{len(lock_files)} lock file(s) consuming {total:,} tokens. These are auto-generated and never helpful to an LLM.",
            fix="Add to .llmignore: package-lock.json, yarn.lock, pnpm-lock.yaml, bun.lockb",
            files=[f["path"] for f in lock_files],
            llmignore_entries=["package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "Gemfile.lock", "poetry.lock", "Cargo.lock"],
        ))

    # Pattern 2: Generated/built files not ignored (component-level matching)
    _generated_dirs = {"dist", "build", "out", "generated"}
    _generated_exts = {".min.js", ".min.css", ".bundle.js"}
    def _is_generated(fpath: str) -> bool:
        parts = Path(fpath.replace("\\", "/")).parts
        name = parts[-1] if parts else ""
        if any(d in parts for d in _generated_dirs):
            return True
        if "__snapshots__" in parts:
            return True
        if any(name.endswith(ext) for ext in _generated_exts):
            return True
        return False
    generated = [f for f in all_files if f["path"] not in ignored_paths and _is_generated(f["path"])]
    if generated:
        total = sum(f["tokens"] for f in generated)
        patterns.append(WastePattern(
            name="Generated/built files",
            tokens_wasted=total,
            severity="high",
            description=f"{len(generated)} generated file(s) consuming {total:,} tokens. LLMs should never read compiled output.",
            fix="Add to .llmignore: dist/, build/, out/, src/generated/, **/*.min.js",
            files=[f["path"] for f in generated[:5]],
            llmignore_entries=["dist/", "build/", "out/", "src/generated/", "**/*.min.js", "**/*.min.css", "**/*.bundle.js"],
        ))

    # Pattern 3: Very large single files
    huge = [f for f in all_files if f["tokens"] > 8000 and f["path"] not in ignored_paths]
    if huge:
        total = sum(f["tokens"] for f in huge)
        patterns.append(WastePattern(
            name="Oversized files",
            tokens_wasted=total,
            severity="medium",
            description=f"{len(huge)} file(s) over 8k tokens each. Single large files consume disproportionate context.",
            fix="Split large files, or tell the LLM explicitly which function/section to read.",
            files=[f"{f['path']} ({f['tokens']:,} tokens)" for f in huge[:5]]
        ))

    # Pattern 4: Test snapshots
    snapshots = [f for f in all_files if "__snapshots__" in f["path"] or f["path"].endswith(".snap")]
    if snapshots:
        total = sum(f["tokens"] for f in snapshots)
        patterns.append(WastePattern(
            name="Test snapshots",
            tokens_wasted=total,
            severity="medium",
            description=f"{len(snapshots)} snapshot file(s) consuming {total:,} tokens. Snapshot content is rarely useful to LLMs.",
            fix="Add to .llmignore: **/__snapshots__/, **/*.snap",
            files=[f["path"] for f in snapshots[:3]],
            llmignore_entries=["**/__snapshots__/", "**/*.snap"],
        ))

    # Pattern 5: Log files
    logs = [f for f in all_files
            if f["path"].endswith(".log")
            or "logs" in Path(f["path"].replace("\\", "/")).parts]
    if logs:
        total = sum(f["tokens"] for f in logs)
        patterns.append(WastePattern(
            name="Log files",
            tokens_wasted=total,
            severity="medium",
            description=f"{len(logs)} log file(s) consuming {total:,} tokens.",
            fix="Add to .llmignore: *.log, logs/",
            files=[f["path"] for f in logs[:3]],
            llmignore_entries=["*.log", "logs/"],
        ))

    # Pattern 6: Check CLAUDE.md / system prompt size
    for config_name in ["CLAUDE.md", ".cursorrules", "AGENTS.md"]:
        config_path = path / config_name
        if config_path.exists():
            with open(config_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
            lines = content.count("\n") + 1
            tokens = len(content) // 4
            if lines > 200:
                patterns.append(WastePattern(
                    name=f"Bloated {config_name}",
                    tokens_wasted=tokens,
                    severity="high",
                    description=f"{config_name} is {lines} lines ({tokens:,} tokens). This is loaded on EVERY session - every line costs forever.",
                    fix=f"Trim {config_name} to under 200 lines. Move project-specific rules to subdirectory CLAUDE.md files.",
                    files=[config_name]
                ))
            elif lines > 100:
                patterns.append(WastePattern(
                    name=f"{config_name} is getting heavy",
                    tokens_wasted=0,
                    severity="low",
                    description=f"{config_name} is {lines} lines. Getting long - consider trimming before it hurts.",
                    fix=f"Target: under 80 lines for lean sessions.",
                    files=[config_name]
                ))

    return sorted(patterns, key=lambda p: {"high": 0, "medium": 1, "low": 2}[p.severity])


def analyze_session(session_path: Path, model: str = "claude") -> dict:
    """Analyze a conversation JSON file for token waste patterns."""
    with open(session_path, encoding='utf-8') as f:
        session = json.load(f)

    messages = session if isinstance(session, list) else session.get("messages", [])
    
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from token_counter import estimate_tokens

    results = {
        "total_turns": len(messages),
        "total_tokens": 0,
        "by_role": {},
        "largest_messages": [],
        "repeated_content": [],
        "recommendations": [],
    }

    token_counts = []
    for i, msg in enumerate(messages):
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
        tokens = estimate_tokens(str(content), model)
        role = msg.get("role", "unknown")
        results["by_role"][role] = results["by_role"].get(role, 0) + tokens
        results["total_tokens"] += tokens
        token_counts.append({"index": i, "role": role, "tokens": tokens, "preview": str(content)[:80]})

    # Find largest messages
    results["largest_messages"] = sorted(token_counts, key=lambda x: x["tokens"], reverse=True)[:5]

    # Detect repeated content (simple heuristic)
    user_msgs = [m["preview"] for m in token_counts if m["role"] == "user"]
    if len(user_msgs) > len(set(user_msgs)):
        results["repeated_content"].append("Duplicate messages detected - possible retry loop")

    # Recommendations
    avg_tokens = results["total_tokens"] / max(len(messages), 1)
    if avg_tokens > 2000:
        results["recommendations"].append("Average message is very large - batch smaller tasks")
    if results["total_turns"] > 20:
        results["recommendations"].append("Long session - use /compact or start fresh for new tasks")
    if results["by_role"].get("assistant", 0) > results["by_role"].get("user", 0) * 3:
        results["recommendations"].append("Assistant responses are much larger than prompts - ask for shorter answers")

    return results


def apply_fixes(patterns: list[WastePattern], project_path: Path) -> int:
    """Write auto-fixable entries into .llmignore and .claudeignore. Returns count of entries added."""
    entries_to_add = []
    for p in patterns:
        entries_to_add.extend(p.llmignore_entries)

    if not entries_to_add:
        return 0

    ignore_files = [project_path / ".llmignore", project_path / ".claudeignore"]
    total_added = 0

    for ignore_path in ignore_files:
        existing = set()
        header = ""
        if ignore_path.exists():
            content = ignore_path.read_text(encoding='utf-8')
            existing = {line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")}
            header = content.rstrip("\n") + "\n"
        else:
            header = f"# {ignore_path.name} - auto-generated by distill analyze --fix\n"

        new_entries = [e for e in entries_to_add if e not in existing]
        if not new_entries:
            continue

        block = "\n# Added by distill analyze --fix\n" + "\n".join(new_entries) + "\n"
        ignore_path.write_text(header + block, encoding='utf-8')
        total_added += len(new_entries)

    return total_added


def print_analysis(patterns: list[WastePattern], path: str):
    RED = "\033[91m"; YELLOW = "\033[93m"; GREEN = "\033[92m"
    CYAN = "\033[96m"; BOLD = "\033[1m"; NC = "\033[0m"

    sev_color = {"high": RED, "medium": YELLOW, "low": GREEN}
    sev_icon  = {"high": "✗", "medium": "⚠", "low": "→"}

    total_wasted = sum(p.tokens_wasted for p in patterns)

    print(f"\n{BOLD}{'─'*60}{NC}")
    print(f"{BOLD}  Context Analyzer - Waste Report{NC}")
    print(f"  Path: {path}")
    print(f"{'─'*60}")
    
    auto_fixable = sum(1 for p in patterns if p.llmignore_entries)

    if not patterns:
        print(f"  {GREEN}✓ No significant waste patterns found. Good hygiene!{NC}")
    else:
        print(f"  Found {len(patterns)} waste pattern(s) - ~{total_wasted:,} tokens recoverable\n")
        for p in patterns:
            c = sev_color[p.severity]
            icon = sev_icon[p.severity]
            fixable_tag = f" {GREEN}[auto-fixable]{NC}" if p.llmignore_entries else ""
            print(f"  {c}{BOLD}[{p.severity.upper()}] {p.name}{NC}{fixable_tag}")
            print(f"  {p.description}")
            if p.files:
                for f in p.files[:3]:
                    print(f"    {CYAN}·{NC} {f}")
            print(f"  {GREEN}Fix:{NC} {p.fix}")
            print()

        if auto_fixable:
            print(f"  {BOLD}{auto_fixable} issue(s) can be fixed automatically.{NC}")
            print(f"  Run: distill analyze --fix  (or pass --fix now to apply)\n")

    print(f"{'─'*60}\n")


def main():
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        elif hasattr(sys.stdout, 'buffer'):
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Analyze LLM context waste patterns")
    parser.add_argument("--path",    "-p", default=".", help="Directory to analyze")
    parser.add_argument("--session", "-s", help="Session JSON file to analyze")
    parser.add_argument("--model",   "-m", default="claude",
                        choices=["claude", "openai", "gemini", "ollama", "generic"])
    parser.add_argument("--json",    action="store_true", help="Output raw JSON")
    parser.add_argument("--fix",     action="store_true", help="Auto-apply fixes (writes .llmignore / .claudeignore)")
    args = parser.parse_args()

    if args.session:
        results = analyze_session(Path(args.session), args.model)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            BOLD = "\033[1m"; NC = "\033[0m"; YELLOW = "\033[93m"; GREEN = "\033[92m"
            print(f"\n{BOLD}Session Analysis{NC}  -  {args.session}")
            print(f"  Turns        : {results['total_turns']}")
            print(f"  Total tokens : {results['total_tokens']:,}")
            for role, tok in results["by_role"].items():
                print(f"    {role:<12}: {tok:,}")
            if results["largest_messages"]:
                print(f"\n  {BOLD}Largest messages:{NC}")
                for m in results["largest_messages"][:5]:
                    print(f"    [{m['index']}] {m['role']:<10} {m['tokens']:>7,} tokens  {m['preview'][:60]}")
            if results["repeated_content"]:
                print(f"\n  {YELLOW}Repeated content:{NC}")
                for r in results["repeated_content"]:
                    print(f"    {r}")
            if results["recommendations"]:
                print(f"\n  {GREEN}Recommendations:{NC}")
                for r in results["recommendations"]:
                    print(f"    {r}")
            print()
        return

    path = Path(args.path).resolve()
    patterns = analyze_directory(path, args.model)

    if args.json:
        print(json.dumps([{
            "name": p.name, "tokens_wasted": p.tokens_wasted,
            "severity": p.severity, "fix": p.fix, "files": p.files,
            "auto_fixable": bool(p.llmignore_entries),
        } for p in patterns], indent=2))
        return

    print_analysis(patterns, str(path))

    if args.fix:
        added = apply_fixes(patterns, path)
        if added:
            print(f"\033[92m✓ Applied fixes - {added} entries added to .llmignore / .claudeignore\033[0m\n")
        else:
            print("  Nothing new to add (all entries already present).\n")


if __name__ == "__main__":
    main()
