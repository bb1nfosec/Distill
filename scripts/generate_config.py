#!/usr/bin/env python3
"""
generate_config.py - Auto-detect project type and generate optimized LLM configs.

Usage:
    python3 scripts/generate_config.py --output ./my-project
    python3 scripts/generate_config.py --output . --model all
    python3 scripts/generate_config.py --output . --model claude --verbose
"""

import os
import sys
import json
import argparse
from pathlib import Path


def detect_project(path: Path) -> dict:
    """Auto-detect project type, language, package manager, and test setup."""
    info = {
        "type": "generic",
        "language": "unknown",
        "pkg_manager": "unknown",
        "test_cmd": "echo 'no test command detected'",
        "lint_cmd": "",
        "src_dirs": [],
        "forbidden_dirs": ["node_modules", ".git", "dist", "build", "coverage"],
    }

    files = {f.name for f in path.iterdir() if f.is_file()}
    dirs  = {d.name for d in path.iterdir() if d.is_dir()}

    # Language / framework detection
    if "package.json" in files:
        info["language"] = "javascript/typescript"
        try:
            pkg = json.loads((path / "package.json").read_text(encoding='utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pkg = {}
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

        if "next" in deps:
            info["type"] = "nextjs"
            info["forbidden_dirs"].extend([".next", ".turbo", ".vercel"])
        elif "react" in deps and "vite" in deps:
            info["type"] = "react-vite"
        elif "react" in deps:
            info["type"] = "react"
        elif "vue" in deps:
            info["type"] = "vue"
        elif "svelte" in deps:
            info["type"] = "svelte"
            info["forbidden_dirs"].append(".svelte-kit")
        elif "express" in deps or "fastify" in deps or "hono" in deps:
            info["type"] = "node-api"
        else:
            info["type"] = "node"

        # Test command
        scripts = pkg.get("scripts", {})
        if "test" in scripts:
            info["test_scripts"] = scripts["test"]
        if "typecheck" in scripts:    info["lint_cmd"] = "{pm} typecheck"
        elif "type-check" in scripts: info["lint_cmd"] = "{pm} type-check"
        elif "lint" in scripts:       info["lint_cmd"] = "{pm} lint"

        # Package manager
        if (path / "pnpm-lock.yaml").exists(): info["pkg_manager"] = "pnpm"
        elif (path / "bun.lockb").exists():    info["pkg_manager"] = "bun"
        elif (path / "yarn.lock").exists():    info["pkg_manager"] = "yarn"
        else:                                  info["pkg_manager"] = "npm"

        pm = info["pkg_manager"]
        run = f"{pm} run" if pm in ("npm",) else pm
        info["test_cmd"] = f"{pm} test"
        if info["lint_cmd"]: info["lint_cmd"] = info["lint_cmd"].replace("{pm}", run)

    elif "pyproject.toml" in files or "setup.py" in files or "requirements.txt" in files:
        info["language"] = "python"
        info["forbidden_dirs"].extend(["__pycache__", ".venv", "venv", "env", ".mypy_cache"])

        if (path / "pyproject.toml").exists():
            content = (path / "pyproject.toml").read_text()
            if "fastapi" in content or "starlette" in content:
                info["type"] = "fastapi"
            elif "django" in content:
                info["type"] = "django"
            elif "flask" in content:
                info["type"] = "flask"
            elif "poetry" in content:
                info["pkg_manager"] = "poetry"

        if (path / ".venv" / "bin" / "pytest").exists() or any("pytest" in f for f in files):
            info["test_cmd"] = "pytest"
            info["lint_cmd"] = "ruff check . && mypy ."
        else:
            info["test_cmd"] = "python -m pytest"

        if info["pkg_manager"] == "unknown":
            info["pkg_manager"] = "pip"

    elif "go.mod" in files:
        info["language"] = "go"
        info["type"] = "golang"
        info["pkg_manager"] = "go"
        info["test_cmd"] = "go test ./..."
        info["lint_cmd"] = "golangci-lint run"
        info["forbidden_dirs"].extend(["vendor"])

    elif "Cargo.toml" in files:
        info["language"] = "rust"
        info["type"] = "rust"
        info["pkg_manager"] = "cargo"
        info["test_cmd"] = "cargo test"
        info["lint_cmd"] = "cargo clippy"
        info["forbidden_dirs"].extend(["target"])

    elif "pubspec.yaml" in files:
        info["language"] = "dart"
        info["type"] = "flutter"
        info["pkg_manager"] = "flutter"
        info["test_cmd"] = "flutter test"
        info["lint_cmd"] = "flutter analyze"

    # Detect source directories
    for d in ["src", "app", "lib", "packages"]:
        if d in dirs:
            info["src_dirs"].append(d)

    return info


def generate_claude_md(info: dict, custom_notes: str = "") -> str:
    lines = [
        "# Project",
        f"- Type: {info['type']} ({info['language']})",
        f"- Package manager: {info['pkg_manager']}",
        f"- Test: `{info['test_cmd']}`",
    ]
    if info.get("lint_cmd"):
        lines.append(f"- Lint: `{info['lint_cmd']}`")
    if info["src_dirs"]:
        lines.append(f"- Source: {', '.join(info['src_dirs'])}/")

    lines += [
        "",
        "# Response rules",
        "- Batch all related edits into one pass.",
        "- No explanations unless asked. Code only.",
        "- Never ask 'shall I proceed?' - just execute.",
        "- Read only files relevant to the current task.",
        "- Terse responses. No summaries of what you did.",
        "",
        "# Forbidden - never read",
    ]
    for d in info["forbidden_dirs"]:
        lines.append(f"- {d}/")

    lines += [
        "",
        "# Research tasks → delegate to a subagent, return summary only.",
        "# Long sessions → /compact after each feature. /btw for quick lookups.",
    ]

    if custom_notes:
        lines += ["", "# Notes", custom_notes]

    return "\n".join(lines)


def generate_llmignore(info: dict) -> str:
    base = """# .llmignore - skip these paths in all LLM tool calls
# Works as .claudeignore for Claude Code

# Dependencies
node_modules/
vendor/
.venv/
venv/
env/
__pycache__/
*.pyc

# Build outputs
dist/
build/
out/
target/

# Framework caches
.next/
.nuxt/
.svelte-kit/
.turbo/
.vercel/

# Lock files (huge, useless)
package-lock.json
yarn.lock
pnpm-lock.yaml
bun.lockb
poetry.lock
Cargo.lock

# Generated
src/generated/
*.min.js
*.min.css

# Test artifacts
coverage/
.nyc_output/
htmlcov/
__snapshots__/

# Media
*.png
*.jpg
*.jpeg
*.gif
*.ico
*.mp4
*.woff
*.woff2
*.ttf

# Logs & secrets
*.log
.env
.env.*
*.pem
*.key
"""
    extras = []
    if info["type"] == "django":
        extras = ["migrations/", "staticfiles/", "*.sqlite3"]
    elif info["type"] == "fastapi":
        extras = ["*.db", "alembic/versions/"]
    elif info["type"] in ("nextjs", "react-vite"):
        extras = ["storybook-static/", "public/static/"]

    if extras:
        base += "\n# Project-specific\n" + "\n".join(extras) + "\n"

    return base


def generate_openai_system(info: dict) -> str:
    return f"""You are a terse senior engineer. Project: {info['type']} ({info['language']}).

Rules:
- Code only, no prose unless explicitly asked.
- Batch all edits in one response.
- Never ask for confirmation - just execute.
- Reference only code shown in this conversation.
- Keep responses as short as possible.

Test: {info['test_cmd']}
"""


def generate_ollama_modelfile(info: dict) -> str:
    # Recommend model based on project complexity
    model = "llama3.2"
    ctx = 8192
    if info["type"] in ("nextjs", "fastapi", "django"):
        model = "llama3.1:8b"
        ctx = 16384

    return f"""FROM {model}

PARAMETER num_ctx {ctx}
PARAMETER temperature 0.2
PARAMETER keep_alive 10m

SYSTEM \"\"\"Terse coding assistant for {info['type']} projects.
Code only. Batch edits. No preamble. Never ask to proceed.
Test: {info['test_cmd']}\"\"\"
"""


def write_file(path: Path, content: str, verbose: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    size = len(content)
    tokens_est = size // 4
    marker = "✓" if tokens_est < 500 else ("⚠" if tokens_est < 1500 else "✗")
    print(f"  {marker} {path.relative_to(path.parent.parent) if path.parent != path.parent.parent else path.name}"
          f"  (~{tokens_est} tokens)")
    if verbose:
        print(f"    {path}")


def main():
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        elif hasattr(sys.stdout, 'buffer'):
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Generate optimized LLM configs for your project")
    parser.add_argument("--output", "-o", default=".", help="Project root to write configs to")
    parser.add_argument("--model",  "-m", default="claude",
                        choices=["claude", "openai", "gemini", "ollama", "all"])
    parser.add_argument("--notes",  "-n", default="", help="Custom notes to add to configs")
    parser.add_argument("--dry-run", action="store_true", help="Print without writing files")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    path = Path(args.output).resolve()
    print(f"\nDetecting project at {path}...")
    info = detect_project(path)

    print(f"  Type     : {info['type']}")
    print(f"  Language : {info['language']}")
    print(f"  Pkg mgr  : {info['pkg_manager']}")
    print(f"  Test     : {info['test_cmd']}")
    print("\nGenerating configs...")

    files_to_write = {}

    # Always generate .llmignore
    files_to_write[path / ".llmignore"] = generate_llmignore(info)

    if args.model in ("claude", "all"):
        files_to_write[path / "CLAUDE.md"] = generate_claude_md(info, args.notes)
        files_to_write[path / ".claudeignore"] = generate_llmignore(info)

    if args.model in ("openai", "all"):
        files_to_write[path / ".llm" / "openai_system.md"] = generate_openai_system(info)

    if args.model in ("ollama", "all"):
        files_to_write[path / ".llm" / "Modelfile"] = generate_ollama_modelfile(info)

    if args.dry_run:
        for fpath, content in files_to_write.items():
            print(f"\n{'─'*50}")
            print(f"# {fpath}")
            print('─'*50)
            print(content)
        return

    for fpath, content in files_to_write.items():
        write_file(fpath, content, verbose=args.verbose)

    print(f"\n✓ Done. Run next:")
    print(f"  python3 core/token_counter.py --path {args.output} --model {args.model}")
    print(f"  python3 core/context_analyzer.py --path {args.output}")


if __name__ == "__main__":
    main()
