# Project
- Type: generic (python)
- Package manager: pip
- Test: `python -m pytest`

# Response rules
- Batch all related edits into one pass.
- No explanations unless asked. Code only.
- Never ask 'shall I proceed?' — just execute.
- Read only files relevant to the current task.
- Terse responses. No summaries of what you did.

# Forbidden — never read
- node_modules/
- .git/
- dist/
- build/
- coverage/
- __pycache__/
- .venv/
- venv/
- env/
- .mypy_cache/

# Research tasks → delegate to a subagent, return summary only.
# Long sessions → /compact after each feature. /btw for quick lookups.