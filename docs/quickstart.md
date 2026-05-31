# Quickstart

Get skim running in under 2 minutes.

## Install

```bash
pip install skim-llm
```

No hard dependencies for the core proxy and scanner. Optional extras for the dashboard and provider SDKs — install what you need.

## Start the proxy

```bash
skim proxy
```

On start:
- Proxy binds to `http://localhost:7474`
- Browser opens automatically to `http://localhost:7474/dashboard`
- All events are persisted to `~/.skim/events.db`

To disable browser auto-open: `skim proxy --no-browser`

## Point your tool at it

**Claude Code:**
```bash
export ANTHROPIC_API_KEY=sk-ant-...        # required — see note below
export ANTHROPIC_BASE_URL=http://localhost:7474
```

Add this to your `.zshrc` or `.bashrc` to make it permanent.

> ⚠️ **Claude Code on a Pro/Max subscription cannot use the proxy.** Subscription
> (OAuth `/login`) traffic ignores `ANTHROPIC_BASE_URL` and routes straight to
> Anthropic — the proxy stays on "waiting for calls". To intercept Claude Code
> you must use **API-key auth**: set `ANTHROPIC_API_KEY` in the same shell,
> before launching `claude`. This bills against API credits, not the
> subscription. Cursor, the SDK, and OpenAI-compatible tools are unaffected.

**Cursor / Windsurf / any OpenAI-compatible tool:**
```bash
export OPENAI_BASE_URL=http://localhost:7474
```

**That's it.** Every API call now goes through skim. The dashboard updates in real-time via SSE.

## What you see in the terminal

```
┌──────────────────────────────────────────────────────────────┐
│  skim v0.5.0  — runtime token proxy                         │
├──────────────────────────────────────────────────────────────┤
│  listening  http://127.0.0.1:7474                            │
│  dashboard  http://127.0.0.1:7474/dashboard                  │
│  model      claude  (200,000 token limit)                    │
│  filtering  on — strips waste from tool results              │
│  caching    on — auto-injects prompt caching                 │
├──────────────────────────────────────────────────────────────┤
│  Claude Code / Cursor:                                       │
│    export ANTHROPIC_BASE_URL=http://127.0.0.1:7474           │
│  OpenAI-compatible tools:                                    │
│    export OPENAI_BASE_URL=http://127.0.0.1:7474              │
├──────────────────────────────────────────────────────────────┤
│  Ctrl+C to stop   data → ~/.skim/events.db                   │
└──────────────────────────────────────────────────────────────┘

  ⠋ LIVE  14:23:01  waiting for calls...
```

After a call:
```
[skim] 14:23:01  call #1  1,247ms
  ctx  ████░░░░░░░░░░░░░░░░ 12.4%  24.8k/200k
  in 24.8k  out 1.2k  cost $0.0001   ▼ stripped package-lock.json (122k)  ◈ cached 18.6k
```

## Which plan are you on?

skim detects your Anthropic auth type automatically:

| You have | skim uses | Features |
|----------|-----------|---------|
| `ANTHROPIC_API_KEY` env var | `x-api-key` header | Filtering + caching + tracking |
| Claude Pro/Max login | `Authorization: Bearer` (OAuth) | Filtering + tracking (no caching injection — Pro manages its own) |
| Neither | — | 401 error |

## Static analysis (no API key needed)

```bash
# See your codebase's token footprint
skim scan --path .

# Find what's wasting tokens
skim analyze --path .

# Auto-fix — writes .llmignore rules
skim fix --path . --min-severity medium
```

## Next steps

- [Proxy deep-dive →](proxy.md) — all features, all flags, OpenAI compatibility
- [Dashboard guide →](dashboard.md) — local solo dashboard and team server
- [Enterprise setup →](enterprise.md) — budgets, teams, webhooks, invites
- [Configuration →](configuration.md) — all env vars and .skimrc options
