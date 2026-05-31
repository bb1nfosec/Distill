# Changelog

All notable changes to **skim** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.2.0] — 2026-05-31

### Added
- `core/proxy.py` — runtime interceptor proxy; sits between any LLM tool and the API; strips
  waste from `tool_result` blocks in real-time; injects `cache_control` for Anthropic prompt
  caching automatically; prints live context fill % with progress bar after every call
- `core/fix.py` — `skim fix` command; writes `.llmignore` rules and shows before/after token
  savings with severity breakdown
- `core/secrets_detector.py` — `skim secrets` command; detects AWS keys, OpenAI/Anthropic keys,
  GitHub PATs, Stripe live keys, Slack tokens, JWTs, and private key blocks
- `core/audit.py` — `skim audit` command; view operation log at `~/.skim/audit.log`
- `server/` — Flask web dashboard with login, per-user cost charts, budget alerts, and REST API;
  supports local password, LDAP/AD, and OIDC (Google, GitHub, Azure AD, Okta)
- `skim_mcp/` — MCP server exposing skim as Claude Desktop tools: `scan_tokens`,
  `analyze_context`, `check_budget`, `fix_context`, `generate_llmignore`
- `Dockerfile` — self-hosted container; exposes proxy on 7474 and dashboard on 7475
- `skim-mcp`, `skim-proxy`, `skim-server`, `skim-secrets`, `skim-audit` CLI entry points

### Changed
- **Renamed** package `distill-llm` → `skim-llm`; all CLI commands renamed `distill` → `skim`
- PyPI package name: `skim-llm`; install with `pip install skim-llm`
- Entry points updated: `skim`, `skim-scan`, `skim-analyze`, `skim-check`, `skim-fix`,
  `skim-generate`, `skim-proxy`, `skim-server`, `skim-secrets`, `skim-audit`, `skim-mcp`

---

## [0.1.0] — 2026-05-22

### Added
- `core/token_counter.py` — scan any directory, estimate tokens **and dollar cost** per file;
  `--cost` flag and per-session spend shown by default; `PRICING` table covers Claude, GPT-4o,
  Gemini, and Ollama at current rates
- `core/context_analyzer.py` — detect waste patterns (lock files, generated code, oversized
  files, bloated configs) with severity levels and actionable fix commands
- `core/check.py` — CI budget gate; `skim check --max-pct 30` exits 1 if over budget;
  `--fail-on-waste` also fails on HIGH-severity patterns; `--json` for machine-readable output
- `core/cli.py` — unified `skim` command dispatcher: `scan`, `analyze`, `check`, `generate`,
  `version`; installed as `skim` entry point via `pip install -e .`
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
- `pyproject.toml` — installable as `skim-llm` (formerly `distill-llm`); optional dep groups
  `[claude]`, `[openai]`, `[gemini]`, `[all]`; entry points for `skim`, `skim-scan`,
  `skim-analyze`, `skim-check`
- `benchmarks/run_benchmarks.py` — reproducible benchmark suite: accuracy, throughput, waste
  elimination, compaction savings
- `benchmarks/results.md` — captured results: 0.00% token estimation error, 1.8M tok/s
  throughput, 42.9% compaction savings over 10-turn sessions
- `.llmignore` / `CLAUDE.md` / `.claudeignore` — applied to this repo itself
- CI: token budget check (`skim check --max-pct 40`) runs on every push
- Docs: `UNIVERSAL_TIPS.md`, `CLAUDE_CODE.md`, `OLLAMA.md`
- Repo: issue templates, PR template, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `Makefile`
