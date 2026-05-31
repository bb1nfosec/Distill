# Dashboard

skim has two dashboard modes. Both use the same dark theme, Inter font, Lucide icons, and Chart.js charts. The difference is setup requirements and who can see it.

## Local dashboard (solo — zero setup)

Every time you run `skim proxy`, a fully featured dashboard starts automatically.

```bash
skim proxy
# → browser opens to http://localhost:7474/dashboard
```

**No login. No server. No config.** Data persists in `~/.skim/events.db` between proxy sessions.

### Pages

| Page | Content |
|------|---------|
| **Overview** | 4 metric cards (tokens sent, cost, saved, cache hits) + usage line chart + model donut + sent-vs-saved bar chart + cost per day + recent calls table |
| **Sessions** | Full call log — searchable, filterable by model/provider. Shows model, tokens in/out, saved, cached, cost, latency, auth plan type |
| **Usage** | Hourly activity chart (configurable window: today/3d/7d) + daily calls bar chart + daily breakdown table with save % badge |
| **Models** | Token distribution donut + cost distribution donut + model comparison table with cost/1k tokens, cache hit %, waste % |
| **Savings** | 3 big metric cards (tokens saved, $ saved, cache hits) + cumulative savings line + daily save rate bar + sent/saved/cached stacked bar + savings by model |

### Live updates

The dashboard subscribes to `/skim/stream` (SSE) when it loads. When any API call goes through the proxy, the dashboard updates within 1 second — no refresh needed. A toast notification shows model + tokens in + tokens saved.

If the SSE connection drops, the dashboard retries in 12 seconds and falls back to polling every 30 seconds.

### Local data API

The proxy serves these endpoints for the dashboard. All require no auth.

```
GET /skim/data/summary?days=N    → {total_calls, total_input, total_saved, ...}
GET /skim/data/daily?days=N      → [{day, calls, input_tokens, saved_tokens, cost_usd}]
GET /skim/data/hourly?days=N     → [{hour, calls, input_tokens, cost_usd}]
GET /skim/data/models?days=N     → [{model, calls, input_tokens, cost_usd, cache_hit_pct, waste_pct}]
GET /skim/data/events?days=N&limit=N → [event objects]
```

---

## Team dashboard (enterprise)

For teams, `skim server` runs a separate authenticated dashboard with multi-user views, team leaderboards, budget management, and org-level insights.

### Setup

```bash
pip install 'skim-llm[web]'

# First run — auto-creates admin account
SKIM_ADMIN_EMAIL=you@corp.com \
SKIM_ADMIN_PASSWORD=changeme \
SKIM_JWT_SECRET=your-secret-here \
skim server --host 0.0.0.0 --port 7475

# Open http://your-server:7475
```

> **Production:** Use gunicorn (auto-detected if installed) and set `SKIM_JWT_SECRET` to a fixed value. If unset, a new secret is generated on each restart — all existing sessions become invalid.

### Connect proxies to it

On each developer's machine:

```bash
export SKIM_SERVER_URL=https://skim.corp.internal
export SKIM_SERVER_TOKEN=sk-skim-...   # generate in Settings → API Keys
```

Every API call the proxy intercepts is now sent to the central server after being forwarded to the LLM.

### Auth methods

| Method | Configure via | Notes |
|--------|--------------|-------|
| Local password | `SKIM_ADMIN_EMAIL` + `SKIM_ADMIN_PASSWORD` | Default, no extra deps |
| LDAP / Active Directory | `SKIM_LDAP_URL` + `SKIM_LDAP_BASE_DN` | Requires `pip install 'skim-llm[ldap]'` |
| Google OAuth | `SKIM_OIDC_GOOGLE_CLIENT_ID` + `_SECRET` | Requires `pip install 'skim-llm[sso]'` |
| GitHub OAuth | `SKIM_OIDC_GITHUB_CLIENT_ID` + `_SECRET` | Requires `pip install 'skim-llm[sso]'` |
| Azure AD | `SKIM_OIDC_AZURE_CLIENT_ID` + `_SECRET` + `_TENANT` | Requires `pip install 'skim-llm[sso]'` |
| Custom OIDC (Okta, Keycloak) | `SKIM_OIDC_CUSTOM_DISCOVERY` + `_CLIENT_ID` + `_SECRET` | Requires `pip install 'skim-llm[sso]'` |

### Pages

| Page | Who sees it | Content |
|------|------------|---------|
| **Dashboard** | Everyone | Org-wide or per-user summary cards + 4 charts |
| **Sessions** | Everyone | Own call log (admins see all) |
| **Usage** | Everyone | Hourly + daily breakdown |
| **Models** | Everyone | Model comparison table |
| **Savings** | Everyone | Cumulative savings + ROI |
| **Team** | admin, team_admin | Per-user leaderboard with waste % and cache hit % |
| **Insights** | admin only | AI-generated optimization recommendations |
| **Budgets** | admin only | Set/edit/delete budgets per user/team/global |
| **Webhooks** | admin only | Manage webhook endpoints |
| **Invites** | admin only | Generate invite URLs, list pending |
| **Audit Log** | admin only | Full action history |
| **Settings** | Everyone | API key management (scope, expiry, revoke) |

### RBAC

| Role | Can see | Can manage |
|------|---------|-----------|
| `user` | Own data | Own API keys |
| `team_admin` | Own team stats | Own API keys |
| `admin` | Everything | All users, budgets, webhooks, invites, audit |

### Real-time updates

The server dashboard subscribes to `/skim/stream` (SSE) after login. Events ingested from any connected proxy update the dashboard live — same 1-second delay as the local dashboard.

### API key generation

1. Log in to dashboard
2. Go to **Settings**
3. Click **Generate API Key**
4. Choose scope (`ingest` for proxy, `read` for CI/reporting, `admin` for full management)
5. Optionally set expiry in days
6. Copy the key — it won't be shown again

Use the key:
```bash
export SKIM_SERVER_TOKEN=sk-skim-<your-key>
```

---

## Docker

```bash
docker run -d \
  -p 7474:7474 \
  -p 7475:7475 \
  -e SKIM_ADMIN_EMAIL=admin@corp.com \
  -e SKIM_ADMIN_PASSWORD=changeme \
  -e SKIM_JWT_SECRET=$(openssl rand -hex 32) \
  -v /data/skim:/data \
  ghcr.io/bb1nfosec/skim
```

See [deployment guide](deployment.md) for production setup with nginx, TLS, and gunicorn.
