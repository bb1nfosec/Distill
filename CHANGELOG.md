# Changelog

All notable changes to **skim** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.5.0] — 2026-05-31

### Added — Enterprise control plane

- **Budget enforcement** — hard-block API calls when users/teams exceed token or cost limits.
  Proxy calls `/api/v1/budget/check` before forwarding; returns 429 on breach; fails open
  on timeout (200ms) so server downtime never blocks work. Checks user → team → global budget
  in priority order.
- **Webhook alerts** — `server/webhooks.py` fires background HTTP/Slack payloads on
  `budget.warning` (at `alert_pct`) and `budget.exceeded`. Slack-compatible format also works
  with Microsoft Teams connectors. Payloads are HMAC-signed when a secret is configured.
- **User invite system** — admins generate single-use, 7-day invite links via
  `POST /api/v1/admin/invites`. New users self-register at `/invite/<token>`.
  New page: `server/static/invite.html`.
- **API key scopes + expiry** — keys now carry `scope` (`ingest` | `read` | `admin`) and
  optional `expires_at`. `get_user_for_key` enforces both. Only org admins can create
  `admin`-scoped keys.
- **RBAC: team_admin role** — new role between `user` and `admin`. `team_admin` sees their
  own team's stats only; `require_team_admin` decorator enforces this.
- **Audit log** — new `audit_log` table. Every sensitive action (login, key created/revoked,
  budget created/deleted, user invited/created/deleted, webhook fired) is recorded immutably.
  Queryable via `GET /api/v1/admin/audit` and `skim admin audit`.
- **Data export** — `GET /api/v1/export/events.csv` (up to 10k rows, CSV download) and
  `GET /api/v1/export/summary.json` (structured JSON for BI tools).
- **`skim admin` CLI** — new command with subcommands: `users`, `budget`, `keys`, `webhooks`,
  `export`, `audit`. Calls server REST API using `SKIM_SERVER_URL` + `SKIM_SERVER_TOKEN`.
  New `skim-admin` entry point in `pyproject.toml`.
- New server routes: `POST /api/v1/budget/check`, `GET/POST/DELETE /api/v1/admin/budgets`,
  `GET/POST/DELETE /api/v1/admin/webhooks`, `GET/POST /api/v1/admin/invites`,
  `POST /api/v1/auth/register`, `GET /invite/<token>`, `DELETE /api/v1/auth/keys/<prefix>`,
  `GET /api/v1/export/events.csv`, `GET /api/v1/export/summary.json`,
  `GET /api/v1/admin/audit`, `DELETE /api/v1/admin/users/<user_id>`.
- New DB functions: `set_budget`, `check_budget`, `get_period_usage`, `list_budgets`,
  `delete_budget`, `create_webhook`, `list_webhooks`, `delete_webhook`, `get_active_webhooks`,
  `create_invite`, `get_invite`, `use_invite`, `list_invites`, `log_audit`, `get_audit_log`,
  `revoke_api_key`, `delete_user`.
- New DB tables: `webhooks`, `invites`, `audit_log`. Migrations: added `scope` + `expires_at`
  to `api_keys`, `updated_at` to `budgets`.
- New file: `server/webhooks.py` — background Slack/HTTP webhook delivery.

### Changed

- `server/db.py` — `connect()` now returns a new connection per call (was a shared connection
  with `check_same_thread=False`). Flask routes use `get_db()` (Flask `g`-backed per-request
  connection with teardown close). Eliminates concurrent-write corruption risk.
- `stats_by_model()` — now includes `cached_tokens`, `cache_hit_pct`, `waste_pct`,
  `avg_latency_ms` in addition to basic stats.
- New `stats_by_hour()` function added to `server/db.py`.
- `create_api_key()` — now accepts `scope` and `expires_days` parameters.
- `get_user_for_key()` — enforces key expiry and scope. Returns `None` for expired or
  insufficient-scope keys.
- `stats_by_user_route` now uses `require_team_admin` (was `require_admin`) — team admins
  can see their own team's data.
- `ingest_event` route: fires webhooks when budget thresholds are crossed post-ingestion.
- `skim server` startup: uses gunicorn automatically if installed (4 workers, sync class);
  falls back to Flask dev server with a clear production warning printed to stderr.
- `CONTRIBUTING.md` + `SECURITY.md` updated to reflect skim (was "Distill" in both).

---

## [0.4.0] — 2026-05-31

### Added

- **Self-contained proxy dashboard** — `skim proxy` now serves a full 5-page local dashboard
  at `/dashboard` (no server, no auth, no config). Opens in browser automatically 1.5s after
  start. Disable with `--no-browser`.
- **Local event persistence** — all proxy events are written to `~/.skim/events.db` (SQLite)
  regardless of whether `SKIM_SERVER_URL` is set. Powers the local dashboard.
- **New file: `core/local_store.py`** — thread-safe SQLite writer with `init()`, `record()`,
  `summary()`, `by_day()`, `by_hour()`, `by_model()`, `recent_events()` functions.
- **New file: `core/static/local_dashboard.html`** — self-contained 5-page dashboard
  (Overview, Sessions, Usage, Models, Savings) with Chart.js, dark theme, Inter font,
  Lucide icons, SSE live updates, and number count-up animations.
- **SSE live updates** — proxy broadcasts events to all open `/skim/stream` SSE connections.
  Dashboard updates within 1 second of each API call. No polling.
- **Local analytics API** — new proxy endpoints: `GET /skim/data/summary`, `/skim/data/daily`,
  `/skim/data/hourly`, `/skim/data/models`, `/skim/data/events`. No auth required.
- **Passthrough for unknown paths** — any Anthropic or OpenAI endpoint the proxy doesn't
  handle explicitly (e.g. `/v1/models`, `/v1/count_tokens`) is now forwarded transparently.
  Fixes Claude Code auth/session flow disruption.
- **`--no-browser` flag** on `skim proxy` — disables automatic browser open.
- **`_auth_type()` method** in proxy — centralises Anthropic plan detection:
  `("apikey", key)` for API key users, `("oauth", bearer)` for Pro/OAuth users, `("", "")` if
  no auth. Routing and feature decisions branch on this single return value.
- **Pro/OAuth plan support** — `Authorization: Bearer <token>` is now accepted and forwarded
  as-is. Prompt caching injection is skipped for OAuth users (Pro plan manages its own cache).
- **`ThreadingHTTPServer`** with `allow_reuse_address = True` — proxy can handle concurrent
  connections; port is released immediately on shutdown.
- **`server.server_close()`** in `serve()` finally block — socket released cleanly on Ctrl+C.
- **Server dashboard**: implemented Sessions, Usage, Models, Savings pages (were stubs saying
  "coming in next release"). Added `/skim/stream` SSE endpoint and `stats_by_hour` route.
- **Thread-safe SQLite for server** — `server/db.py` uses per-request connections via Flask `g`
  with teardown close. Replaced shared `check_same_thread=False` connection.

### Changed

- Dashboard CSS: proxy-served dashboard uses Inter font, Lucide icons, accent card colours,
  Chart.js gradient fills, animated number counters, custom scrollbar.
- `server/static/dashboard.html` + `login.html`: same font/icon improvements.
- `skim proxy` startup banner: now shows dashboard URL alongside proxy URL.
- `distill_mcp/` directory deleted — was an exact duplicate of `skim_mcp/` with stale branding.
- `requirements.txt` header corrected from "TokenWise" to "skim-llm".
- `skim_mcp/server.py` scan tool output: "distill scan" → "skim scan".

### Fixed

- `config.py:load()` — `~/.skimrc` was preempting project `.skimrc` due to a misplaced
  `break`. Project config is now loaded after user home config and takes priority.
- `base_adapter.py:compact()` — summary was stored as `role="assistant"`, causing a 400 error
  on the next Anthropic API call (first message must be `role="user"`). Now stored as a
  `user`+`assistant` pair.
- `fix.py` — dry-run temp write not wrapped in `try/finally`; an exception during the
  after-scan would leave `.llmignore` permanently modified. Fixed with `try/finally`.
- `hooks.py` — `chmod +x` was applied on new hook install but not on update. Git hooks
  silently stopped executing after a second `skim hooks install`.
- `claude_adapter.py:run_subagent()` — did not forward `api_key` to the sub-adapter.
  If the parent was initialised with an explicit key, the subagent would fail.
- `proxy.py` stream handlers — `body` variable (request dict) was overwritten by the error
  response in `except urllib.error.HTTPError` blocks. `_report_bg` would then log the wrong
  model from the error dict. Renamed to `err_body`.
- `proxy.py` sync handlers — `json.loads(e.read())` in HTTPError handlers was unprotected;
  non-JSON error responses (HTML error pages) would raise an unhandled `JSONDecodeError`.

---

## [0.3.0] — 2026-05-31

### Added

- `core/config.py` — `.skimrc` / `skim.json` config file support; load order: CLI flags →
  project config → user home config → defaults; `skim config init` and `skim config show`
- `core/hooks.py` — `skim hooks install/remove/status`; installs a git pre-commit hook that
  runs `skim check` before every commit; safe update (checks for skim marker before removing)
- `core/baseline.py` — `skim baseline save/compare/list/delete`; save token count snapshots
  and diff against them in CI; fails if regression > 5k tokens
- Enhanced `skim server` dashboard: team leaderboard, per-user waste %, cache hit rate, org
  insights, LDAP + OIDC auth hooks
- Streaming proxy: Anthropic and OpenAI streaming responses are forwarded chunk-by-chunk
  without buffering; `cache_read_input_tokens` parsed from SSE stream for accurate tracking

### Changed

- `skim server` banner now shows admin email and env var instructions
- `stats_by_user` returns `waste_pct` and `cache_hit_pct` derived fields

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
