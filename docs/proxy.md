# Proxy

The proxy is what makes skim different from every other LLM cost tool. Static scanners analyse files. skim intercepts calls.

## Architecture

```
Your tool (Claude Code / Cursor / custom app)
         │
         │  ANTHROPIC_BASE_URL=http://localhost:7474
         ▼
    skim proxy  (ThreadingHTTPServer, handles concurrent connections)
         │
         ├── Budget check  →  skim server /api/v1/budget/check (if SKIM_SERVER_URL set)
         │                    429 if over limit, fail-open on timeout
         │
         ├── Waste filter  →  strips lock files from tool_result blocks
         │
         ├── Cache inject  →  adds cache_control to system prompt + large context (API key only)
         │
         ├── Local store   →  writes event to ~/.skim/events.db
         │
         ├── SSE broadcast →  pushes to /skim/stream (dashboard updates live)
         │
         └── Forward       →  Anthropic / OpenAI API
```

## Start

```bash
skim proxy [--port 7474] [--host 127.0.0.1] [--model claude] [--no-browser]
           [--no-filter] [--no-cache] [--path .]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `7474` | Port to listen on |
| `--host` | `127.0.0.1` | Bind address. Use `0.0.0.0` to expose to network |
| `--model` | `claude` | Model family for context limit calculation |
| `--path` | `.` | Project root for `.llmignore` rules |
| `--no-browser` | off | Disable auto-open browser on start |
| `--no-filter` | off | Disable waste filtering (pure passthrough) |
| `--no-cache` | off | Disable prompt caching injection |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/messages` | Anthropic Messages API proxy |
| `POST` | `/v1/chat/completions` | OpenAI Chat API proxy |
| `GET` | `/dashboard` | Local no-auth dashboard (auto-opens on start) |
| `GET` | `/skim/stream` | SSE stream — live events for dashboard |
| `GET` | `/skim/data/summary` | Session summary stats (JSON) |
| `GET` | `/skim/data/daily` | By-day breakdown (JSON) |
| `GET` | `/skim/data/hourly` | By-hour breakdown (JSON) |
| `GET` | `/skim/data/models` | By-model breakdown with cache/waste % (JSON) |
| `GET` | `/skim/data/events` | Recent event log (JSON) |
| `GET` | `/health` | Health check + session stats (JSON) |
| `*` | `/v1/*` (other paths) | Transparent passthrough to Anthropic/OpenAI |

All `GET /skim/data/*` endpoints accept `?days=N` and `?limit=N` query params.

## Waste filtering

Detects known waste signatures inside `tool_result` blocks — the content the LLM receives when it reads a file. Strips before the tokens are sent to the API.

**Detected automatically:**

| File | Signatures checked |
|------|--------------------|
| `package-lock.json` | `"lockfileVersion"` + `"resolved": "https://"` |
| `yarn.lock` | `# yarn lockfile v1` + `resolved` |
| `pnpm-lock.yaml` | `lockfileVersion:` + `resolution:` |
| `Cargo.lock` | `@generated` + `[[package]]` |
| `poetry.lock` | `@generated` + `[[package]]` |
| `composer.lock` | `"content-hash":` + `"packages":` |

When stripped, the block is replaced with:
```
[skim: stripped package-lock.json (122,451 tokens). In .llmignore. Set SKIM_NO_FILTER=1 to disable.]
```

**Disable:** `skim proxy --no-filter` or `export SKIM_NO_FILTER=1`

## Prompt caching injection

For API key users only (not Pro/OAuth — Pro plan manages its own caching layer).

Automatically adds `cache_control: {"type": "ephemeral"}` to:
1. Your system prompt (1 cache breakpoint)
2. The 2 largest user messages in the conversation (up to 2 more breakpoints)

Total: up to 3 breakpoints per request (Anthropic allows 4 max).

**How it saves money:**
- First call: Anthropic caches the content (billed at 25% of normal input rate)
- Subsequent calls: content served from cache (free — 0% of normal rate)
- For Claude Code with a large CLAUDE.md: the system prompt loads free on every call after the first

**Disable:** `skim proxy --no-cache` or `export SKIM_NO_CACHE=1`

## Auth type detection

The proxy detects which Anthropic plan you're on and routes accordingly:

```python
def _auth_type():
    # Check for API key (API plan users)
    api_key = headers.get("x-api-key") or os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return ("apikey", api_key)

    # Check for OAuth token (Pro/Max plan users)
    auth = headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return ("oauth", auth)

    return ("", "")   # → 401
```

| Plan | Header | Caching injected |
|------|--------|-----------------|
| API plan | `x-api-key: sk-ant-...` | Yes |
| Claude Pro/Max | `Authorization: Bearer <token>` | No |
| Neither | — | 401 |

**Extending:** Adding a new plan type is one `elif` in `_auth_type()`. The rest of the codebase branches on `plan`.

> ⚠️ **Claude Code subscription caveat.** The `oauth` branch only applies to clients
> that actually send `Authorization: Bearer` to the proxy's base URL. **Claude Code on
> a Pro/Max subscription does NOT** — it ignores `ANTHROPIC_BASE_URL` entirely and
> routes subscription traffic straight to `api.anthropic.com`. To put Claude Code
> behind the proxy you must use API-key auth (`ANTHROPIC_API_KEY` + `ANTHROPIC_BASE_URL`,
> same shell, before launching `claude`). Cursor, the SDK, and OpenAI-compatible tools
> route through the proxy normally.

## Budget enforcement

When `SKIM_SERVER_URL` + `SKIM_SERVER_TOKEN` are set, the proxy calls `/api/v1/budget/check` before forwarding each request.

```
proxy                           skim server
  │                                 │
  ├─ estimate input tokens          │
  ├─ POST /api/v1/budget/check ────►│
  │   (200ms timeout, fail-open)    ├─ look up user budget
  │◄─ {allowed: true/false} ────────┤
  │                                 │
  ├─ if false → 429 immediately     │
  └─ if true  → forward to API      │
```

**Fail-open:** If the budget check times out or the server is unreachable, the request is allowed through. Server downtime never blocks user work.

**Response when blocked:**
```json
{
  "error": {
    "type": "budget_exceeded",
    "message": "user token budget exceeded (103% used)"
  }
}
```

## Local data storage

Every event is written to `~/.skim/events.db` regardless of whether a central server is configured. This is what powers the local dashboard with no setup.

Schema: `id, ts, provider, model, input_tokens, output_tokens, saved_tokens, cached_tokens, cost_usd, latency_ms, plan`

The data never leaves your machine unless you explicitly set `SKIM_SERVER_URL`.

## OpenAI-compatible tools

```bash
export OPENAI_BASE_URL=http://localhost:7474
```

The proxy handles `/v1/chat/completions` for anything using the OpenAI SDK format. Waste filtering and usage tracking work the same way. Prompt caching injection is Anthropic-only.

## Transparent passthrough

Any Anthropic endpoint not explicitly handled (e.g. `/v1/models`, `/v1/count_tokens`) is transparently forwarded to the real API. This ensures Claude Code's session and auth flow are never disrupted.

```
GET /v1/models → forwarded to api.anthropic.com/v1/models
```

The proxy determines the upstream based on which auth header is present.
