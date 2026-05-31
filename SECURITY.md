# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.5.x   | ✅ Current |
| 0.4.x   | ✅ Security fixes only |
| < 0.4   | ❌ End of life |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email **vickytestssec@gmail.com** with the subject line:
```
[SECURITY] skim — <short description>
```

Include:
- Description of the vulnerability and its impact
- Steps to reproduce
- Affected versions
- Suggested fix (if you have one)

You will receive an acknowledgement within **48 hours** and a resolution timeline within **7 days**.

## Security surface

### Proxy (`skim proxy`)

| Area | Notes |
|------|-------|
| API key forwarding | `x-api-key` and `Authorization: Bearer` headers are forwarded as-is to the upstream API. They are never logged or stored locally. |
| Local store | `~/.skim/events.db` contains token counts and costs but **not** request/response content. No prompts, no model outputs. |
| Budget check | The proxy calls `SKIM_SERVER_URL/api/v1/budget/check` with `SKIM_SERVER_TOKEN`. Always uses HTTPS in production. |
| Passthrough | Unknown paths are forwarded to `api.anthropic.com` or `api.openai.com` based on the auth header present. |

### Server (`skim server`)

| Area | Notes |
|------|-------|
| Passwords | bcrypt via passlib; SHA-256 fallback if passlib unavailable. Passwords are never stored in plain text. |
| JWT | HS256 (HMAC-SHA256), stdlib only (no PyJWT dependency). Set `SKIM_JWT_SECRET` to a fixed value in production. |
| API keys | Stored as `sk-skim-<uuid-hex>`. Scope and expiry enforced on every request. |
| SQLite | WAL mode, no remote access. Stored at `SKIM_DB_PATH` (default `~/.skim/skim.db`). |
| Webhooks | HMAC-signed with the secret provided at creation. Verify signatures on your endpoint. |
| Audit log | Every sensitive action is logged. Cannot be deleted via the API. |

### File path inputs

`skim scan`, `skim analyze`, `skim fix`, etc. accept `--path` arguments. Paths are resolved with `Path.resolve()` and only **read**, never executed. The proxy reads `.llmignore` from the project root.

### Dependencies

Core proxy and scanner have **zero hard dependencies** (stdlib only). Optional dependencies:

| Package | Used for | Audit |
|---------|----------|-------|
| `flask` | Dashboard server | Pin in production |
| `tiktoken` | Accurate token counting | Pin in production |
| `anthropic` | ClaudeAdapter | Pin in production |
| `openai` | OpenAIAdapter | Pin in production |
| `passlib` | bcrypt password hashing | Pin in production |
| `ldap3` | LDAP/AD auth | Pin in production |
| `authlib` | OIDC/OAuth2 | Pin in production |

## Secrets handling

skim includes a built-in secret scanner (`skim secrets --path . --fail`) that detects:
- AWS Access Key IDs (`AKIA...`)
- Anthropic API keys (`sk-ant-...`)
- OpenAI API keys (`sk-...`, `sk-proj-...`)
- GitHub PATs (classic and fine-grained)
- Stripe live keys
- Slack bot/user tokens
- Private key blocks (`-----BEGIN ... PRIVATE KEY-----`)
- JWTs
- Generic password/secret assignments

Run this in CI before any LLM touches your codebase.

## Known limitations

- OIDC/OAuth2 flow configuration is defined in `server/auth.py` but the actual redirect flow requires an authlib-compatible Flask setup. The current implementation defines provider config but does not implement the full OAuth callback routes.
- SQLite is single-file; no row-level encryption. Use filesystem encryption for sensitive deployments.
