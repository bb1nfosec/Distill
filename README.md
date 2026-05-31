<div align="center">

# skim

**The runtime layer between your AI tools and the LLM API.**

[![PyPI](https://img.shields.io/pypi/v/skim-llm?color=2563eb&logo=pypi&logoColor=white)](https://pypi.org/project/skim-llm/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/skim-llm?color=2563eb)](https://pypi.org/project/skim-llm/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-2563eb?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-059669)](LICENSE)
[![Zero hard deps](https://img.shields.io/badge/core-zero%20hard%20deps-d97706)](pyproject.toml)

[Quickstart](#quickstart) · [Proxy](#proxy--the-core) · [Dashboard](#dashboard) · [CLI](#cli-reference) · [Enterprise](#enterprise) · [Live Demo](https://demo-mu-ten-60.vercel.app)

</div>

---

Most LLM tools waste tokens invisibly. Claude Code reads a `package-lock.json` (122k tokens, $0.37) before answering a question about a 200-line file. Conversation history compounds quadratically. Your 200k context window fills up silently, quality degrades, and you're flying blind until the model forgets what it was doing.

**skim** sits in the API call path and fixes this in real-time — without touching any code.

```
Your tool (Claude Code / Cursor / custom)
       │
       ▼
  skim proxy                    ← one env var activates this
  ├── strips lock files from tool outputs
  ├── auto-injects prompt caching (50–90% cheaper)
  ├── shows live context fill %
  └── ships usage data to your team dashboard
       │
       ▼
Anthropic / OpenAI / Gemini API
```

---

## Quickstart

```bash
pip install skim-llm

# Start the proxy
skim proxy --port 7474 --path .

# In your shell (or .zshrc / .bashrc):
export ANTHROPIC_BASE_URL=http://localhost:7474

# That's it. Every Claude Code / Cursor call now goes through skim.
```

**What you'll see in the terminal:**

```
[skim] 14:23:01  call #1  1,247ms
  Context  ████░░░░░░░░░░░░░░░░░░ 12.4%  24.8k/200k
  This call: 24.8k in / 1.2k out  stripped 122k waste (package-lock.json)

[skim] 14:23:45  call #2  892ms
  Context  ███████░░░░░░░░░░░░░░░ 38.1%  76.2k/200k
  This call: 51.4k in / 2.1k out  cache hit 18.6k tokens free

[skim] 14:24:55  call #4  788ms
  Context  ████████████████░░░░░░ 78.4%  156.8k/200k
  ⚠  78% full — /compact NOW before quality degrades
```

---

## Proxy — the core

The proxy is what makes skim different from every other LLM cost tool. They scan files. skim intercepts calls.

### What it does on every API call

**1. Waste filtering**
Detects lock files, build artifacts, and generated code inside `tool_result` blocks (the content Claude Code gets back when it reads a file) and strips them before they enter context. A `package-lock.json` read that would cost 122k tokens becomes a 12-token note.

**2. Prompt caching auto-injection** (Anthropic only)
Wraps your system prompt and large context blocks with `cache_control: {"type": "ephemeral"}` automatically. First call: Anthropic caches the content (25% write fee once). Every subsequent call: that content is free. For Claude Code, the CLAUDE.md + project context loads at zero cost on calls 2+. Real savings: 50–90% on system prompt tokens.

**3. Live session health**
After every call, prints context fill % with a progress bar. Warns at 65%, alerts at 85%. For Claude Code Pro users, this is the visibility you never had.

**4. Actual usage tracking**
Reads `usage.input_tokens` from the API response — not estimates. Ships real numbers to `~/.skim/audit.log` and optionally to a central team dashboard.

### OpenAI-compatible tools

```bash
export OPENAI_BASE_URL=http://localhost:7474
```

Works with anything that uses `openai.OpenAI(base_url=...)`.

---

## Dashboard

For teams, skim includes a web server with login, per-user cost attribution, and budget alerts.

```bash
# Install web extras
pip install 'skim-llm[web]'

# Start the server
SKIM_ADMIN_EMAIL=you@corp.com skim server --host 0.0.0.0 --port 7475

# Open http://localhost:7475/dashboard
```

Then connect each developer's proxy to it:

```bash
export SKIM_SERVER_URL=https://skim.corp.internal
export SKIM_SERVER_TOKEN=sk-skim-...   # generate in Settings
```

**Auth options:**
- Local password (default)
- LDAP / Active Directory: set `SKIM_LDAP_URL` + `SKIM_LDAP_BASE_DN`
- Google / GitHub / Azure AD / Okta: set `SKIM_OIDC_*` env vars

**Docker:**
```bash
docker run -p 7474:7474 -p 7475:7475 \
  -e SKIM_ADMIN_EMAIL=you@corp.com \
  -v /data/skim:/data \
  ghcr.io/bb1nfosec/skim
```

---

## CLI Reference

```
skim scan       Audit token costs per file
skim analyze    Detect waste patterns with severity + auto-fix
skim fix        Write .llmignore rules — shows before/after savings
skim check      CI budget gate (exits 1 if over threshold)
skim generate   Generate .llmignore, .skimrc, CLAUDE.md
skim secrets    Scan for leaked credentials (AWS, OpenAI, GitHub PAT...)
skim proxy      Runtime interceptor + query optimizer
skim server     Web dashboard + REST API
skim audit      View operation log (~/.skim/audit.log)
skim config     Manage .skimrc configuration
skim hooks      Install/remove git pre-commit budget gate
skim baseline   Save/compare token count snapshots
```

### Static analysis (no API key needed)

```bash
# See what's eating your tokens and what it costs
skim scan --path ./my-project

# Find waste patterns with one-line fixes
skim analyze --path .

# Auto-fix: write .llmignore rules, show before/after
skim fix --path . --min-severity medium

# Fail CI if project exceeds 30% of model context limit
skim check --path . --max-pct 30 --fail-on-waste
```

**Example output — `skim fix`:**
```
  skim fix  —  ./my-project
  ──────────────────────────────────────────────────────
  Before  : 166.8k tokens  (83.4% ctx)  $0.50/session

  Pattern              Severity    Tokens saved  Rules
  ────────────────────────────────────────────────────
  Lock files           HIGH           160.3k     +7
  Test snapshots       MEDIUM           4.1k     +2

  ✓ Written to .llmignore

  After   : 6.5k tokens  (3.2% ctx)  $0.02/session
  Saved   : 160.3k tokens  (96.1% reduction)  $0.48/session
  Now     : 51 sessions / $1
```

### Secrets scan

```bash
# Scan before any LLM touches your codebase
skim secrets --path . --fail    # exits 1 if findings exist
```

Detects: AWS Access Key IDs, OpenAI API keys, Anthropic keys, GitHub PATs, private key blocks, Stripe live keys, Slack tokens, JWTs, and generic secrets/passwords.

### Baseline regression (CI)

```bash
# Save before a refactor
skim baseline save --name pre-refactor

# Compare after — fails CI if > 5k tokens regressed
skim baseline compare --name pre-refactor
```

### Git hook

```bash
# Block commits that push context over budget
skim hooks install --max-pct 30 --fail-on-waste
```

---

## Enterprise

| Need | Solution |
|------|----------|
| Cost attribution by team | `skim server` dashboard, per-user breakdown |
| Budget enforcement | `skim check` in CI + git hooks + proxy hard limits |
| SSO / LDAP | `SKIM_OIDC_*` + `SKIM_LDAP_*` env vars |
| Audit trail | `~/.skim/audit.log` + central server ingestion |
| Self-hosted deployment | Docker image — see [Dockerfile](Dockerfile) |
| Secrets governance | `skim secrets --fail` in pre-commit + CI |
| Regression prevention | `skim baseline compare` in PR pipelines |
| Air-gapped / Ollama | `--model ollama` — all analysis local, $0.00 |

---

## Configuration

Create `.skimrc` in your project root (commit it for team-wide policy):

```ini
model         = claude       # claude | openai | gemini | ollama
max_pct       = 30           # fail CI if context exceeds X% of limit
fail_on_waste = false        # also fail on HIGH severity patterns
min_severity  = high         # auto-fix: high | medium | low
audit         = false        # log every operation to ~/.skim/audit.log
proxy_port    = 7474
```

---

## MCP Server

Exposes skim as Claude Desktop tools (no CLI needed):

```json
{
  "mcpServers": {
    "skim": { "command": "skim-mcp" }
  }
}
```

Available tools: `scan_tokens`, `analyze_context`, `check_budget`, `fix_context`, `generate_llmignore`

---

## Python API

```python
from adapters import ClaudeAdapter

claude = ClaudeAdapter(
    model="claude-sonnet-4-6",
    system_prompt="You are a terse coding assistant.",
    enable_caching=True,   # enables prompt caching automatically
)
response = claude.chat("Refactor the auth module")
claude.print_stats()
# Session: 12,400 tokens | Cache hit rate: 87% | Cost: $0.0037
```

Adapters: `ClaudeAdapter`, `OpenAIAdapter`, `GeminiAdapter`, `OllamaAdapter`

---

## Install

```bash
# Core (zero hard deps — scan, analyze, check, fix, proxy)
pip install skim-llm

# With accurate token counting
pip install 'skim-llm[tiktoken]'

# With Claude adapter
pip install 'skim-llm[claude]'

# Web dashboard
pip install 'skim-llm[web]'

# Enterprise (SSO + LDAP)
pip install 'skim-llm[web,sso,ldap]'

# Everything
pip install 'skim-llm[all]'
```

---

## Demo

Live demo (individual + org/enterprise): **https://demo-mu-ten-60.vercel.app**

---

<div align="center">

MIT License · [GitHub](https://github.com/bb1nfosec/skim) · [PyPI](https://pypi.org/project/skim-llm/) · [Issues](https://github.com/bb1nfosec/skim/issues) · [Changelog](CHANGELOG.md)

</div>
