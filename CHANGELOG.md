# Changelog

All notable changes to Distill are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.1.0] — 2026-05-22

### Added
- `core/token_counter.py` — scan any directory, estimate tokens **and dollar cost** per file;
  `--cost` flag and per-session spend shown by default; `PRICING` table covers Claude, GPT-4o,
  Gemini, and Ollama at current rates
- `core/context_analyzer.py` — detect waste patterns (lock files, generated code, oversized
  files, bloated configs) with severity levels and actionable fix commands
- `core/check.py` — CI budget gate; `distill check --max-pct 30` exits 1 if over budget;
  `--fail-on-waste` also fails on HIGH-severity patterns; `--json` for machine-readable output
- `core/cli.py` — unified `distill` command dispatcher: `scan`, `analyze`, `check`, `generate`,
  `version`; installed as `distill` entry point via `pip install -e .`
- `adapters/base_adapter.py` — abstract base: auto-compact, history management, lazy file
  loading, session cost stats
- `adapters/claude_adapter.py` — Claude API adapter with prompt caching (up to 90% reduction),
  subagent pattern, `CLAUDE.md` generator
- `adapters/openai_adapter.py` — OpenAI adapter with lean system prompt prefix and automatic
  history trimming
- `adapters/gemini_adapter.py` — **new** Google Gemini adapter; supports Gemini 2.0 Flash,
  1.5 Pro, 1.5 Flash; 1M token context window; native token counting via `model.count_tokens()`
- `adapters/ollama_adapter.py` — Ollama adapter with `num_ctx` auto-tuning, Modelfile
  generator, task-based model selection guide
- `adapters/__init__.py` — exports all four adapters; `from adapters import ClaudeAdapter`
  works after install
- `scripts/generate_config.py` — auto-generate `.llmignore`, `.claudeignore`, `CLAUDE.md`,
  `openai_system.md`, `Modelfile` for Node/Python/Go/Rust/generic projects
- `scripts/example_usage.py` — runnable examples for all providers
- `setup.sh` — one-command project setup with auto-detection
- `pyproject.toml` — installable as `distill-llm`; optional dep groups `[claude]`, `[openai]`,
  `[gemini]`, `[all]`; entry points for `distill`, `distill-scan`, `distill-analyze`,
  `distill-check`
- `benchmarks/run_benchmarks.py` — reproducible benchmark suite: accuracy, throughput, waste
  elimination, compaction savings
- `benchmarks/results.md` — captured results: 0.00% token estimation error, 1.8M tok/s
  throughput, 42.9% compaction savings over 10-turn sessions
- `.llmignore` / `CLAUDE.md` / `.claudeignore` — applied to this repo itself
- CI: token budget check (`distill check --max-pct 40`) runs on every push
- Docs: `UNIVERSAL_TIPS.md`, `CLAUDE_CODE.md`, `OLLAMA.md`
- Repo: issue templates, PR template, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `Makefile`
