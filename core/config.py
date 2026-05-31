#!/usr/bin/env python3
"""
config.py — Configuration file support for skim.

Load order (highest priority first):
  1. CLI flags
  2. .skimrc   (project root — commit this for team-wide policy)
  3. ~/.skimrc  (user home)

Format: JSON or simple key=value pairs.

Keys:
  model         = claude
  max_pct       = 30
  fail_on_waste = false
  min_severity  = high
  audit         = false
  proxy_port    = 7474
  top           = 20
"""

import json
import sys
import argparse
from pathlib import Path

_DEFAULTS: dict = {
    "model":         "claude",
    "max_pct":       30.0,
    "fail_on_waste": False,
    "min_severity":  "high",
    "audit":         False,
    "proxy_port":    7474,
    "top":           20,
}

_NAMES = [".skimrc", "skim.json"]


def _parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    result: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            k = k.strip(); v = v.strip().strip('"').strip("'")
            if v.lower() in ("true", "yes", "1"):
                result[k] = True
            elif v.lower() in ("false", "no", "0"):
                result[k] = False
            else:
                try:
                    result[k] = float(v) if "." in v else int(v)
                except ValueError:
                    result[k] = v
    return result


def load(project_path: Path = None) -> dict:
    cfg = dict(_DEFAULTS)
    for src in [Path.home() / ".skimrc", *(
        [project_path / n for n in _NAMES] if project_path else []
    )]:
        if src.exists():
            try:
                cfg.update(_parse(src.read_text(encoding="utf-8")))
                break  # use the first project-level file found
            except Exception:
                pass
    return cfg


_STARTER = """\
# skim configuration — commit to repo for team-wide policy
# Docs: https://github.com/bb1nfosec/skim

model         = claude       # claude | openai | gemini | ollama
max_pct       = 30           # fail CI if context exceeds this % of model limit
fail_on_waste = false        # also fail CI on HIGH severity waste patterns
min_severity  = high         # auto-fix threshold: high | medium | low
audit         = false        # log every operation to ~/.skim/audit.log
proxy_port    = 7474         # port for skim proxy
top           = 20           # files shown in scan report
"""


def cmd_init(project_path: Path) -> None:
    for name in _NAMES:
        target = project_path / name
        if target.exists():
            print(f"  {name} already exists at {target}")
            return
    target = project_path / _NAMES[0]
    target.write_text(_STARTER, encoding="utf-8")
    print(f"  Created {target}")


def cmd_show(project_path: Path) -> None:
    cfg = load(project_path)
    BOLD = "\033[1m"; NC = "\033[0m"
    print(f"\n{BOLD}  skim config — Active Settings{NC}")
    print(f"  {'─'*40}")
    for k, v in cfg.items():
        print(f"  {k:<18} = {v}")
    print()


def main():
    p = argparse.ArgumentParser(description="Manage skim configuration")
    sub = p.add_subparsers(dest="action")
    sub.add_parser("init", help="Create a .skimrc in the current directory")
    sub.add_parser("show", help="Show effective configuration")
    args = p.parse_args()

    path = Path(".").resolve()
    if args.action == "init":
        cmd_init(path)
    else:
        cmd_show(path)


if __name__ == "__main__":
    main()
