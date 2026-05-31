# Configuration

skim is configured through environment variables and an optional `.skimrc` file. Environment variables always take priority.

## Environment variables

### Proxy

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_BASE_URL` | — | Point Claude Code / any Anthropic SDK client at the proxy. Set to `http://localhost:7474` |
| `OPENAI_BASE_URL` | — | Point OpenAI-compatible tools at the proxy. Set to `http://localhost:7474` |
| `ANTHROPIC_API_KEY` | — | Anthropic API key. Used by the proxy when the request doesn't include `x-api-key`. Not needed for Claude Pro/Max users. |
| `OPENAI_API_KEY` | — | OpenAI API key. Used by the proxy when the request doesn't include `Authorization`. |
| `SKIM_NO_FILTER` | (unset) | Set to any value to disable waste filtering. Proxy passes through all content unchanged. |
| `SKIM_NO_CACHE` | (unset) | Set to any value to disable prompt caching injection. Only affects API key plan users. |

### Server connection (enterprise)

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIM_SERVER_URL` | (unset) | URL of the central skim server. Set to enable enterprise mode: `https://skim.corp.internal`. When set, the proxy sends events to the server and checks budgets before forwarding. |
| `SKIM_SERVER_TOKEN` | (unset) | API key for proxy → server authentication. Generate in Settings → API Keys with `ingest` scope. |

### Server (skim server)

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIM_DB_PATH` | `~/.skim/skim.db` | Path to the SQLite database file. For Docker: set to `/data/skim.db` and mount a volume. |
| `SKIM_JWT_SECRET` | random UUID (new each restart) | Secret for signing JWT tokens. **Must be set to a fixed value in production.** If unset, all sessions are invalidated on server restart. |
| `SKIM_JWT_TTL` | `604800` (7 days) | JWT expiry in seconds. |
| `SKIM_ADMIN_EMAIL` | (unset) | Auto-create an admin user with this email on first server start. Ignored if the user already exists. |
| `SKIM_ADMIN_PASSWORD` | `changeme` | Password for the auto-created admin user. **Change before production.** |

### LDAP / Active Directory

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIM_LDAP_URL` | (unset) | LDAP server URL. Example: `ldaps://ad.corp.example.com`. Setting this enables LDAP auth. Requires `pip install 'skim-llm[ldap]'`. |
| `SKIM_LDAP_BASE_DN` | (unset) | LDAP base DN. Example: `DC=corp,DC=example,DC=com`. Required if `SKIM_LDAP_URL` is set. |
| `SKIM_LDAP_BIND_USER` | (unset) | Optional service account for LDAP lookups. Example: `svc-skim@corp.example.com`. |
| `SKIM_LDAP_BIND_PASS` | (unset) | Password for the LDAP service account. |
| `SKIM_LDAP_USER_ATTR` | `sAMAccountName` | LDAP attribute for username. Use `uid` for OpenLDAP. |
| `SKIM_LDAP_EMAIL_ATTR` | `mail` | LDAP attribute for email address. |
| `SKIM_LDAP_GROUP_DN` | (unset) | If set, users must be members of this group to authenticate. Example: `CN=skim-users,OU=Groups,DC=corp,DC=example,DC=com`. |

### OIDC / OAuth2 (SSO)

Requires `pip install 'skim-llm[sso]'`.

**Google:**

| Variable | Description |
|----------|-------------|
| `SKIM_OIDC_GOOGLE_CLIENT_ID` | Google OAuth2 client ID. Setting this enables Google login. |
| `SKIM_OIDC_GOOGLE_CLIENT_SECRET` | Google OAuth2 client secret. |

**GitHub:**

| Variable | Description |
|----------|-------------|
| `SKIM_OIDC_GITHUB_CLIENT_ID` | GitHub OAuth2 app client ID. Setting this enables GitHub login. |
| `SKIM_OIDC_GITHUB_CLIENT_SECRET` | GitHub OAuth2 app client secret. |

**Azure AD / Microsoft Entra:**

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIM_OIDC_AZURE_CLIENT_ID` | — | Azure AD app client ID. Setting this enables Azure login. |
| `SKIM_OIDC_AZURE_CLIENT_SECRET` | — | Azure AD app client secret. |
| `SKIM_OIDC_AZURE_TENANT` | `common` | Azure AD tenant ID. Use `common` for multi-tenant apps. |

**Custom OIDC (Okta, Keycloak, Auth0, etc.):**

| Variable | Description |
|----------|-------------|
| `SKIM_OIDC_CUSTOM_DISCOVERY` | OpenID Connect discovery URL. Example: `https://your-org.okta.com/.well-known/openid-configuration`. Setting this enables the custom provider. |
| `SKIM_OIDC_CUSTOM_CLIENT_ID` | Client ID for the custom OIDC provider. |
| `SKIM_OIDC_CUSTOM_CLIENT_SECRET` | Client secret for the custom OIDC provider. |

### LLM adapters (Python API)

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key for `ClaudeAdapter`. |
| `OPENAI_API_KEY` | OpenAI API key for `OpenAIAdapter`. |
| `GOOGLE_API_KEY` | Google API key for `GeminiAdapter`. |
| `GEMINI_API_KEY` | Gemini-specific API key (fallback if `GOOGLE_API_KEY` is not set). |

---

## .skimrc file

Create `.skimrc` in your project root and commit it for team-wide policy. skim merges user home config (`~/.skimrc`) with project config (project wins on conflicts).

**Format — key=value:**
```ini
# skim configuration
# Commit this file for team-wide policy

model         = claude       # claude | openai | gemini | ollama
max_pct       = 30           # CI failure threshold (% of model context limit)
fail_on_waste = false        # also fail CI on HIGH severity waste patterns
min_severity  = high         # auto-fix threshold: high | medium | low
audit         = false        # log every operation to ~/.skim/audit.log
proxy_port    = 7474         # port for skim proxy
top           = 20           # files shown in scan report
```

**Format — JSON (alternative):**
```json
{
  "model": "claude",
  "max_pct": 30,
  "fail_on_waste": false,
  "min_severity": "high"
}
```

Create with: `skim config init`
Show effective config: `skim config show`

### Load order

Priority (highest first):
1. CLI flags
2. Project `.skimrc` or `skim.json`
3. `~/.skimrc`
4. Defaults

---

## Quick reference by use case

### Individual developer (Claude Pro)
```bash
# ~/.bashrc or ~/.zshrc
export ANTHROPIC_BASE_URL=http://localhost:7474
```
No other config needed. Start with `skim proxy`.

### Individual developer (API key)
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export ANTHROPIC_BASE_URL=http://localhost:7474
```

### Enterprise proxy → server
```bash
# On each developer machine
export ANTHROPIC_BASE_URL=http://localhost:7474
export SKIM_SERVER_URL=https://skim.corp.internal
export SKIM_SERVER_TOKEN=sk-skim-...
```

### skim server (production)
```bash
export SKIM_JWT_SECRET=$(openssl rand -hex 32)  # fixed, not random
export SKIM_ADMIN_EMAIL=admin@corp.com
export SKIM_ADMIN_PASSWORD=your-secure-password
export SKIM_DB_PATH=/data/skim.db
```

### skim admin CLI
```bash
export SKIM_SERVER_URL=https://skim.corp.internal
export SKIM_SERVER_TOKEN=sk-skim-admin-...  # admin-scoped key
```

### CI pipeline
```bash
# .env or CI secrets
SKIM_SERVER_URL=https://skim.corp.internal
SKIM_SERVER_TOKEN=sk-skim-read-...  # read-scoped key for export/stats
```
