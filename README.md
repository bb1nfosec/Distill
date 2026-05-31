<div align="center">

# skim

**Runtime token intelligence for Claude Code, Cursor, and any LLM tool.**

[![PyPI](https://img.shields.io/pypi/v/skim-llm?color=6c63ff&logo=pypi&logoColor=white)](https://pypi.org/project/skim-llm/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/skim-llm?color=6c63ff)](https://pypi.org/project/skim-llm/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-6c63ff?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-00d4aa)](LICENSE)
[![Zero hard deps](https://img.shields.io/badge/core-zero%20hard%20deps-f5a623)](pyproject.toml)

[Quickstart](#quickstart) · [How it works](#how-it-works) · [Dashboard](#dashboard) · [Enterprise](#enterprise) · [CLI](#cli-reference) · [Docs](docs/) · [Live Demo](https://demo-mu-ten-60.vercel.app)

</div>

---

LLM tools waste tokens invisibly. Claude Code reads `package-lock.json` (122k tokens, $0.37) before answering about a 200-line file. History compounds. Your context window fills silently, quality degrades, and you're paying for noise.

**skim sits in the API call path and fixes this in real-time — one env var, no code changes.**

```
Claude Code / Cursor / your app
         │
         ▼
    skim proxy                       ← set ANTHROPIC_BASE_URL=http://localhost:7474
    ├─ strips lock files & build artifacts from tool outputs (real-time)
    ├─ auto-injects prompt caching   (50–90% cost reduction on repeated context)
    ├─ enforces token/cost budgets   (hard block on 429, enterprise-grade)
    ├─ serves local dashboard        (opens in browser automatically)
    └─ streams live events to team dashboard (optional)
         │
         ▼
  Anthropic / OpenAI / Gemini API
```

---

## Quickstart

```bash
pip install skim-llm

# Start — browser opens automatically to your dashboard
skim proxy

# Point Claude Code (or any LLM tool) at it
export ANTHROPIC_BASE_URL=http://localhost:7474
```

That's it. Every API call now goes through skim. Open `http://localhost:7474/dashboard` to see live token usage, cost, savings, and cache hit rate.

**Works with all plans — no API key required for Claude Pro/Max users.** skim detects your auth type automatically (`x-api-key` for API plans, `Authorization: Bearer` for Pro/OAuth plans) and routes accordingly.

---

## How it works

### 1 · Waste filtering

Detects lock files, build artifacts, and generated code inside `tool_result` blocks and strips them before they enter context. A `package-lock.json` read becomes a 12-token note instead of 122k tokens.

Detected automatically: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`, `poetry.lock`, `composer.lock` — and anything in your `.llmignore`.

### 2 · Prompt caching injection (Anthropic only)

Wraps your system prompt and large context blocks with `cache_control: {"type": "ephemeral"}` automatically. First call: Anthropic caches it (25% write fee once). Every subsequent call: free. CLAUDE.md and project context load at zero cost on calls 2+.

> Skipped for Pro/OAuth plan users — Pro plan manages its own caching layer.

### 3 · Live dashboard

`skim proxy` opens a browser tab automatically. The local dashboard requires no login, no server setup, and persists all events to `~/.skim/events.db`. Five pages:

| Page | Shows |
|------|-------|
| Overview | Token usage over time, cost, savings, cache hits, recent calls |
| Sessions | Full call log with model, latency, plan type, cost per call |
| Usage | Hourly activity heatmap, daily breakdown table |
| Models | Side-by-side comparison — cost/1k tokens, cache hit %, waste % |
| Savings | Cumulative savings, save rate, ROI of using skim |

### 4 · Plan detection

```
_auth_type() → ("apikey", key)    API plan users   → full features
             → ("oauth",  token)  Pro/Max users    → filtering + tracking
             → ("", "")           No auth          → 401
```

One method owns this logic. Extending for new plan types (enterprise SSO, team tokens) is one `elif`.

### 5 · Budget enforcement (enterprise)

When `SKIM_SERVER_URL` is set, the proxy calls `/api/v1/budget/check` before every request. If the user or their team has exceeded their token/cost budget, the proxy returns `429` immediately — no call is forwarded. Fails open (200ms timeout) so server downtime never blocks work.

---

## Dashboard

### Local (solo — no setup)

```bash
skim proxy          # browser opens to http://localhost:7474/dashboard
```

No login. No server. Data lives in `~/.skim/events.db`. Works for any plan.

### Team (enterprise)

```bash
pip install 'skim-llm[web]'

SKIM_ADMIN_EMAIL=you@corp.com skim server --host 0.0.0.0 --port 7475
# → open http://your-server:7475/dashboard
```

Connect each developer's proxy:

```bash
export SKIM_SERVER_URL=https://skim.corp.internal
export SKIM_SERVER_TOKEN=sk-skim-...   # generate in Settings
```

The team dashboard adds: multi-user auth, team leaderboard, org-level insights, budget management, webhook alerts, user invites, and a full audit log.

**Auth options:** Local password · LDAP/AD (`SKIM_LDAP_*`) · Google/GitHub/Azure/Okta (`SKIM_OIDC_*`)

---

## Enterprise

skim v0.5.0 ships a full enterprise control plane. All features are in the open-source repo.

### Budget enforcement

Set hard spending limits per user, team, or globally. Proxy blocks requests that would exceed the limit.

```bash
# Set a 1M token monthly budget for a user
skim admin budget set --owner-type user --owner-id <user_id> --tokens 1000000 --period monthly

# Set a $500/month cost budget for a team
skim admin budget set --owner-type team --owner-id engineering --usd 500 --period monthly
```

When the budget is hit, the proxy returns:
```json
{"error": {"type": "budget_exceeded", "message": "user token budget exceeded (103% used)"}}
```

### Webhook alerts

Get notified on Slack (or any HTTP endpoint) when teams approach or exceed budgets.

```bash
# Slack (works with Teams connectors too)
skim admin webhooks add \
  --url https://hooks.slack.com/services/... \
  --channel slack \
  --events budget.warning,budget.exceeded

# Generic HTTP with HMAC signature
skim admin webhooks add --url https://your-system.example.com/hook
```

Payload on `budget.warning`:
```json
{
  "event": "budget.warning",
  "data": {"user": "dev@corp.com", "team": "engineering", "pct_used": 83.4, "budget_type": "team"},
  "ts": "2026-05-31T14:23:01Z",
  "sig": "sha256=..."
}
```

### User invites

No manual account creation. Admins generate invite links; users self-register.

```bash
skim admin users invite --email new@corp.com --role user --team engineering
# → https://skim.corp:7475/invite/abc123...  (7-day token, single-use)
```

### API key scopes

Keys are scoped and can expire.

| Scope | Can do |
|-------|--------|
| `ingest` | Push events from proxy (default) |
| `read` | Read stats and dashboard API |
| `admin` | Full access (only org admins can create) |

```bash
# Create a 90-day read-only key
curl -X POST .../api/v1/auth/keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"label": "ci-reader", "scope": "read", "expires_days": 90}'
```

### RBAC

Three roles: `admin` (org-wide), `team_admin` (own team only), `user` (own data only).

### Audit log

Every action is logged. Queryable via API or CLI.

```bash
skim admin audit --days 30
#  Timestamp              User                         Action                 Detail
#  2026-05-31 14:23:01    admin@corp.com               auth.login
#  2026-05-31 14:24:10    admin@corp.com               budget.created         user:abc123
#  2026-05-31 14:31:55    dev@corp.com                 auth.key_created       scope=ingest
```

### Data export

```bash
# CSV for accounting
skim admin export --days 30 --out june-usage.csv

# JSON for BI tools
curl .../api/v1/export/summary.json?days=30
```

### `skim admin` CLI

Full management from the command line — no browser needed.

```bash
skim admin users list
skim admin users invite --email X --role team_admin --team platform
skim admin budget list
skim admin budget set --owner-type global --tokens 10000000 --period monthly
skim admin keys list
skim admin keys revoke sk-skim-abc1
skim admin webhooks list
skim admin audit --days 7 --action auth.login
skim admin export --days 30 --out report.csv
```

Reads `SKIM_SERVER_URL` + `SKIM_SERVER_TOKEN` from env.

---

## CLI Reference

```
Static analysis (no API key needed):
  skim scan       Audit token costs per file across your codebase
  skim analyze    Detect waste patterns (lock files, build artifacts, etc.)
  skim fix        Auto-write .llmignore rules — shows before/after savings
  skim check      CI budget gate — exits 1 if over context threshold
  skim generate   Generate .llmignore, .skimrc, and CLAUDE.md
  skim secrets    Scan for leaked credentials before they reach an LLM

Runtime:
  skim proxy      Runtime interceptor — set ANTHROPIC_BASE_URL=http://localhost:7474
  skim server     Web dashboard + REST API (login, charts, team usage)
  skim admin      Manage users, budgets, keys, webhooks via server API

Operations:
  skim audit      View the local operation log (~/.skim/audit.log)
  skim config     Manage .skimrc configuration
  skim hooks      Install/remove git pre-commit budget gate
  skim baseline   Save & compare token count snapshots (regression detection)
  skim version    Print version
```

### Key flags

```bash
skim proxy --port 7474 --model claude --no-filter --no-cache --no-browser
skim server --port 7475 --host 0.0.0.0
skim check --max-pct 30 --fail-on-waste --json
skim fix --min-severity medium --dry-run
skim scan --model gpt-4o --top 30 --json
skim secrets --path . --fail          # use in CI to block leaked keys
skim hooks install --max-pct 30 --fail-on-waste
skim baseline save --name pre-refactor
skim baseline compare --name pre-refactor
```

---

## Configuration

`.skimrc` in your project root (commit for team-wide policy):

```ini
model         = claude       # claude | openai | gemini | ollama
max_pct       = 30           # fail CI if context exceeds this %
fail_on_waste = false        # also fail on HIGH severity waste patterns
min_severity  = high         # auto-fix threshold: high | medium | low
proxy_port    = 7474
```

**Environment variables:**

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_BASE_URL` | Point Claude Code at the proxy |
| `OPENAI_BASE_URL` | Point OpenAI-compatible tools at the proxy |
| `SKIM_NO_FILTER` | Disable waste filtering (passthrough only) |
| `SKIM_NO_CACHE` | Disable prompt caching injection |
| `SKIM_SERVER_URL` | Central dashboard URL (enables enterprise mode) |
| `SKIM_SERVER_TOKEN` | API key for proxy → server reporting |
| `SKIM_JWT_SECRET` | JWT signing secret (auto-generated if unset) |
| `SKIM_ADMIN_EMAIL` | Auto-create admin user on first server run |
| `SKIM_ADMIN_PASSWORD` | Password for auto-created admin |
| `SKIM_DB_PATH` | SQLite DB path (default: `~/.skim/skim.db`) |
| `SKIM_LDAP_URL` | Enable LDAP auth |
| `SKIM_OIDC_GOOGLE_CLIENT_ID` | Enable Google SSO |
| `SKIM_OIDC_GITHUB_CLIENT_ID` | Enable GitHub SSO |
| `SKIM_OIDC_AZURE_CLIENT_ID` | Enable Azure AD SSO |

---

## Python API

```python
from adapters import ClaudeAdapter, OpenAIAdapter, GeminiAdapter, OllamaAdapter

# Claude with prompt caching
claude = ClaudeAdapter(
    model="claude-sonnet-4-6",
    system_prompt="You are a terse coding assistant.",
    enable_caching=True,
)
response = claude.chat("Refactor the auth module")
claude.print_stats()
# Session: 12,400 tokens | Cache hit rate: 87% | Cost: $0.0037

# Subagent pattern — keeps your main context clean
summary = claude.run_subagent(
    "Investigate how authentication handles token refresh",
    context_files=["src/auth/"]
)
```

---

## MCP Server

```json
{
  "mcpServers": {
    "skim": { "command": "skim-mcp" }
  }
}
```

Tools: `scan_tokens`, `analyze_context`, `check_budget`, `fix_context`, `generate_llmignore`

---

## Install

```bash
pip install skim-llm                      # core — zero hard deps
pip install 'skim-llm[tiktoken]'          # accurate token counting
pip install 'skim-llm[web]'              # dashboard (Flask)
pip install 'skim-llm[web,sso,ldap]'    # enterprise auth
pip install 'skim-llm[all]'             # everything
```

---

## Docs

| Document | What it covers |
|----------|----------------|
| [docs/quickstart.md](docs/quickstart.md) | Zero to running in 2 minutes |
| [docs/proxy.md](docs/proxy.md) | Proxy deep-dive — all features, all flags |
| [docs/dashboard.md](docs/dashboard.md) | Local and team dashboard guide |
| [docs/enterprise.md](docs/enterprise.md) | Budgets, webhooks, invites, RBAC, audit |
| [docs/admin-cli.md](docs/admin-cli.md) | `skim admin` complete reference |
| [docs/api.md](docs/api.md) | REST API reference |
| [docs/configuration.md](docs/configuration.md) | All env vars and .skimrc options |
| [docs/deployment.md](docs/deployment.md) | Production deployment guide |
| [docs/mcp-setup.md](docs/mcp-setup.md) | Claude Desktop MCP integration |

---

<div align="center">

MIT License · [GitHub](https://github.com/bb1nfosec/skim) · [PyPI](https://pypi.org/project/skim-llm/) · [Issues](https://github.com/bb1nfosec/skim/issues) · [Changelog](CHANGELOG.md)

</div>
