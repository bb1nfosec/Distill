#!/usr/bin/env python3
"""
hooks.py — Install skim's git pre-commit hook.

The hook runs `skim check` before every commit and blocks the commit
if the project is over its token budget.

Usage:
    skim hooks install [--path .] [--max-pct 30] [--fail-on-waste]
    skim hooks remove  [--path .]
    skim hooks status  [--path .]
"""

import stat
import sys
import argparse
from pathlib import Path

_MARKER = "# skim-hook"


def _hooks_dir(project: Path):
    git = project / ".git"
    return (git / "hooks") if git.is_dir() else None


def _script(max_pct: float = 30.0, fail_on_waste: bool = False) -> str:
    flags = f"--max-pct {max_pct}"
    if fail_on_waste:
        flags += " --fail-on-waste"
    return f"""\
#!/usr/bin/env bash
{_MARKER}
# Installed by: skim hooks install
# Runs skim check before every commit.
if command -v skim &>/dev/null; then
    skim check {flags} --path "$(git rev-parse --show-toplevel)"
    if [ $? -ne 0 ]; then
        echo ""
        echo "  [skim] Context budget exceeded — commit blocked."
        echo "  Run: skim fix   to remove waste, then retry."
        echo "  Run: skim hooks remove   to disable this check."
        echo ""
        exit 1
    fi
fi
"""


def install(project: Path, max_pct: float = 30.0, fail_on_waste: bool = False) -> bool:
    hdir = _hooks_dir(project)
    if not hdir:
        print("  Not a git repository.", file=sys.stderr)
        return False
    hdir.mkdir(parents=True, exist_ok=True)
    hook = hdir / "pre-commit"
    script = _script(max_pct, fail_on_waste)

    if hook.exists():
        existing = hook.read_text(encoding="utf-8")
        if _MARKER in existing:
            hook.write_text(script, encoding="utf-8")
            m = hook.stat().st_mode
            hook.chmod(m | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            print(f"  Updated pre-commit hook: {hook}")
        else:
            print(f"  Pre-commit hook already exists at {hook}")
            print("  Merge manually or remove it first.")
            return False
    else:
        hook.write_text(script, encoding="utf-8")
        m = hook.stat().st_mode
        hook.chmod(m | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"  Installed pre-commit hook: {hook}")
    return True


def remove(project: Path) -> bool:
    hdir = _hooks_dir(project)
    if not hdir:
        print("  Not a git repository.", file=sys.stderr)
        return False
    hook = hdir / "pre-commit"
    if not hook.exists():
        print("  No pre-commit hook found.")
        return True
    if _MARKER not in hook.read_text(encoding="utf-8"):
        print("  Hook not managed by skim — not removing.")
        return False
    hook.unlink()
    print(f"  Removed pre-commit hook: {hook}")
    return True


def status(project: Path) -> None:
    GREEN = "\033[92m"; RED = "\033[91m"; BOLD = "\033[1m"; NC = "\033[0m"
    print(f"\n{BOLD}  skim hooks — Status{NC}")
    print(f"  {'─'*44}")
    hdir = _hooks_dir(project)
    if not hdir:
        print(f"  {RED}Not a git repository.{NC}")
    else:
        hook = hdir / "pre-commit"
        if hook.exists() and _MARKER in hook.read_text(encoding="utf-8"):
            print(f"  {GREEN}✓ skim pre-commit hook installed{NC}")
            print(f"    {hook}")
        else:
            print(f"  {RED}✗ skim pre-commit hook NOT installed{NC}")
            print(f"    Run: skim hooks install")
    print()


def main():
    p = argparse.ArgumentParser(description="Manage skim's git pre-commit hook")
    sub = p.add_subparsers(dest="action")

    inst = sub.add_parser("install")
    inst.add_argument("--path", "-p", default=".")
    inst.add_argument("--max-pct", "-x", type=float, default=30.0)
    inst.add_argument("--fail-on-waste", action="store_true")

    rm = sub.add_parser("remove")
    rm.add_argument("--path", "-p", default=".")

    st = sub.add_parser("status")
    st.add_argument("--path", "-p", default=".")

    args = p.parse_args()
    if not args.action:
        p.print_help()
        return

    path = Path(getattr(args, "path", ".")).resolve()
    if args.action == "install":
        install(path, args.max_pct, args.fail_on_waste)
    elif args.action == "remove":
        remove(path)
    elif args.action == "status":
        status(path)


if __name__ == "__main__":
    main()
