# Changelog

All notable changes to Distill are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.1.0] — 2026-05-22

### Added
- `core/token_counter.py` — scan any directory and estimate token costs per file, with support for Claude, OpenAI, Gemini, and Ollama tokenizers
- `core/context_analyzer.py` — detect waste patterns (lock files, generated code, oversized files, bloated configs) with actionable fixes
- `adapters/base_adapter.py` — abstract base class: auto-compact, history management, lazy file loading, session stats
- `adapters/claude_adapter.py` — Claude API adapter with prompt caching, subagent pattern, `CLAUDE.md` generator
- `adapters/openai_adapter.py` — OpenAI adapter with lean system prompt prefix and automatic history trimming
- `adapters/ollama_adapter.py` — Ollama adapter with `num_ctx` auto-tuning, Modelfile generator, local model recommendations
- `scripts/generate_config.py` — auto-generate `.llmignore`, `.claudeignore`, `CLAUDE.md`, `openai_system.md`, `Modelfile` for any project type
- `scripts/example_usage.py` — working examples for all four providers
- `setup.sh` — one-command setup script with project-type auto-detection
- `docs/UNIVERSAL_TIPS.md` — token optimization rules that apply to every LLM
- `docs/CLAUDE_CODE.md` — Claude Code-specific deep guide
- `docs/OLLAMA.md` — local model optimization guide
- CI workflow — tests on Python 3.10, 3.11, 3.12
