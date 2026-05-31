# Enterprise

skim v0.5.0 ships a complete enterprise control plane. Everything is open-source, self-hosted, and in the same pip package.

## Overview

| Feature | What it does |
|---------|-------------|
| [Budget enforcement](#budget-enforcement) | Hard-block API calls that exceed token/cost limits |
| [Webhook alerts](#webhook-alerts) | Notify Slack or any HTTP endpoint on budget events |
| [User invites](#user-invites) | Self-registration via invite links — no manual account creation |
| [API key scopes + expiry](#api-key-management) | Scope keys to ingest/read/admin, set expiry dates |
| [RBAC](#rbac) | admin / team_admin / user roles with enforced data isolation |
| [Audit log](#audit-log) | Immutable action trail for compliance |
| [Data export](#data-export) | CSV event log + JSON summary for accounting/BI |
| [`skim admin` CLI](#skim-admin-cli) | Manage everything from the terminal |

---

## Budget enforcement

Set hard spending limits. The proxy checks budgets before every API call and returns `429` if the user or their team is over the limit.

### How it works

```
proxy → POST /api/v1/budget/check (200ms timeout, fail-open)
      ← {allowed: false, reason: "user token budget exceeded (103% used)"}
proxy → 429 to Claude Code / Cursor
```

If the budget server is unreachable or times out, the request is **allowed through** — server downtime never blocks user work.

### Setting budgets

```bash
# User: 1M tokens per month
skim admin budget set \
  --owner-type user \
  --owner-id <user_id> \
  --tokens 1000000 \
  --period monthly

# Team: $500/month
skim admin budget set \
  --owner-type team \
  --owner-id engineering \
  --usd 500 \
  --period monthly

# Global org cap: 10M tokens/month
skim admin budget set \
  --owner-type global \
  --tokens 10000000 \
  --period monthly

# Check status
skim admin budget list
```

**Via API:**
```bash
curl -X POST http://localhost:7475/api/v1/admin/budgets \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "owner_type": "user",
    "owner_id": "user-uuid",
    "limit_tokens": 1000000,
    "period": "monthly",
    "alert_pct": 80
  }'
```

### Priority order

The proxy checks budgets in this order. The first matching budget that has a limit applies.

1. User budget (most specific)
2. Team budget
3. Global budget (org-wide cap)

### When a limit is hit

The proxy returns HTTP 429 with:
```json
{
  "error": {
    "type": "budget_exceeded",
    "message": "user token budget exceeded (103% used)"
  }
}
```

Claude Code displays this as a connection error. The user needs to contact their admin or wait for the next budget period.

### Budget periods

| Period | Resets when |
|--------|------------|
| `daily` | Each day (UTC midnight) |
| `weekly` | Each week (UTC Monday) |
| `monthly` | Every 30 days from creation |

---

## Webhook alerts

Get notified before and when budgets are hit. Works with Slack, Microsoft Teams, and any HTTP endpoint.

### Events

| Event | Fires when |
|-------|-----------|
| `budget.warning` | Usage reaches `alert_pct` (default 80%) |
| `budget.exceeded` | Usage goes over the limit |
| `daily.digest` | (reserved for future digest notifications) |

### Slack webhook

```bash
skim admin webhooks add \
  --url https://hooks.slack.com/services/T.../B.../... \
  --channel slack \
  --events budget.warning,budget.exceeded
```

**Payload format** (Slack incoming webhook compatible, also works with Teams connectors):
```json
{
  "text": "*skim* — ⚠️ Budget warning",
  "attachments": [{
    "color": "#f5a623",
    "fields": [
      {"title": "User",        "value": "dev@corp.com", "short": true},
      {"title": "Team",        "value": "engineering",  "short": true},
      {"title": "Pct Used",    "value": "83.4%",        "short": true},
      {"title": "Budget Type", "value": "team",         "short": true}
    ],
    "footer": "skim token intelligence"
  }]
}
```

### Generic HTTP webhook

```bash
skim admin webhooks add \
  --url https://your-system.example.com/hooks/skim \
  --channel http \
  --events budget.warning,budget.exceeded \
  --secret your-hmac-secret
```

**Payload format:**
```json
{
  "event": "budget.warning",
  "data": {
    "user": "dev@corp.com",
    "team": "engineering",
    "pct_used": 83.4,
    "budget_type": "team"
  },
  "ts": "2026-05-31T14:23:01Z",
  "sig": "sha256=a1b2c3..."
}
```

**Verifying the signature:**
```python
import hashlib, hmac
expected = "sha256=" + hmac.new(
    secret.encode(),
    raw_body,
    hashlib.sha256
).hexdigest()
assert hmac.compare_digest(expected, request.headers["X-Skim-Signature"])
```

### Manage webhooks

```bash
skim admin webhooks list
skim admin webhooks delete <id>
```

---

## User invites

No manual account creation. Admins generate invite links. Users click and self-register.

### Flow

```
Admin                          User
  │                              │
  ├─ skim admin users invite     │
  │   --email dev@corp.com       │
  │   --role user                │
  │   --team platform            │
  │                              │
  ├─ gets invite URL ────────────►
  │                              ├─ opens URL in browser
  │                              ├─ sees invite page
  │                              ├─ enters name + password
  │                              ├─ POST /api/v1/auth/register
  │                              └─ redirect to /dashboard
```

### Create an invite

```bash
# Via CLI
skim admin users invite \
  --email new@corp.com \
  --role user \
  --team engineering

# → Invite URL: http://skim.corp:7475/invite/abc123def456...
```

**Via API:**
```bash
curl -X POST http://localhost:7475/api/v1/admin/invites \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@corp.com", "role": "user", "team": "platform"}'
```

Response:
```json
{
  "token": "abc123...",
  "email": "dev@corp.com",
  "role": "user",
  "team": "platform",
  "expires_at": "2026-06-07T14:23:01Z",
  "invite_url": "http://skim.corp:7475/invite/abc123..."
}
```

### Token details

- Expires in **7 days**
- **Single-use** — once registered, the token is invalidated
- Pre-fills the email field (read-only on the invite page)
- Assigns the specified role and team automatically

### List pending invites

```bash
skim admin users invite  # list shows in dashboard Admin → Invites
```

**Via API:** `GET /api/v1/admin/invites`

---

## API key management

Every API key has a **scope** and optionally an **expiry date**.

### Scopes

| Scope | What it can do |
|-------|---------------|
| `ingest` | Push events from the proxy to the server (default for new keys) |
| `read` | Read stats, events, and summaries — use in CI, BI tools |
| `admin` | Full access — only org admins can create admin-scoped keys |

### Create a scoped key

```bash
# In dashboard: Settings → Generate API Key → choose scope + expiry

# Via API:
curl -X POST http://localhost:7475/api/v1/auth/keys \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{"label": "ci-reader", "scope": "read", "expires_days": 90}'
```

### Revoke a key

```bash
skim admin keys revoke sk-skim-abc1

# Via API:
curl -X DELETE http://localhost:7475/api/v1/auth/keys/sk-skim-abc1 \
  -H "Authorization: Bearer $TOKEN"
```

### List keys

```bash
skim admin keys list

# Shows: key prefix, label, scope, expiry, last used
```

---

## RBAC

Three roles with enforced data isolation.

| Role | Stats | Team view | Budget | Webhooks | Users | Audit |
|------|-------|-----------|--------|----------|-------|-------|
| `user` | Own data only | — | — | — | — | — |
| `team_admin` | Own team | Own team | — | — | — | — |
| `admin` | All org data | All teams | ✓ | ✓ | ✓ | ✓ |

### Assigning roles

```bash
# When inviting
skim admin users invite --email lead@corp.com --role team_admin --team platform

# When creating directly
curl -X POST .../api/v1/admin/users \
  -d '{"email": "lead@corp.com", "role": "team_admin", "team": "platform"}'
```

### team_admin capabilities

- Views team leaderboard for their own team
- Cannot see other teams' data or global stats
- Cannot manage budgets, webhooks, or other users

---

## Audit log

Every sensitive action is logged with timestamp, user, action type, and details. Cannot be deleted via API.

### Logged events

| Action | Fired when |
|--------|-----------|
| `auth.login` | User logs in (any method) |
| `auth.key_created` | API key is created |
| `auth.key_revoked` | API key is revoked |
| `budget.created` | Budget is created or updated |
| `budget.deleted` | Budget is deleted |
| `user.created` | User account is created |
| `user.invited` | Invite is generated |
| `user.deleted` | User is deleted |
| `webhook.created` | Webhook is added |
| `webhook.deleted` | Webhook is removed |
| `webhook.fired` | Webhook delivery is attempted |

### Query the log

```bash
# CLI — last 30 days
skim admin audit --days 30

# Filter by action
skim admin audit --days 7 --action auth.login

# Via API
curl ".../api/v1/admin/audit?days=30&action=budget.created" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Output:**
```
  Timestamp              User                         Action                 Detail
  2026-05-31 14:23:01    admin@corp.com               auth.login
  2026-05-31 14:24:10    admin@corp.com               budget.created         user:abc123
  2026-05-31 14:31:55    dev@corp.com                 auth.key_created       scope=ingest
  2026-05-31 15:00:00    system                       webhook.fired          budget.warning → https://hooks.slack.com/...
```

---

## Data export

### CSV event log

```bash
# Via CLI
skim admin export --days 30 --out june-2026.csv

# Via API
curl "http://localhost:7475/api/v1/export/events.csv?days=30" \
  -H "Authorization: Bearer $TOKEN" \
  -o june-events.csv
```

The CSV includes: `id, ts, user_id, session_id, provider, model, input_tokens, output_tokens, saved_tokens, cached_tokens, cost_usd, project_path, latency_ms, command`

Admins export all events. Regular users export only their own.

### JSON summary (for BI tools)

```bash
curl "http://localhost:7475/api/v1/export/summary.json?days=30" \
  -H "Authorization: Bearer $TOKEN"
```

Returns: `generated_at`, `period_days`, `summary` (aggregates), `by_day` (daily breakdown), `by_model` (model breakdown). Import directly into Looker Studio, Power BI, or any JSON-capable data source.

---

## Enterprise deployment checklist

Before going to production:

- [ ] `SKIM_JWT_SECRET` is set to a fixed value (not auto-generated)
- [ ] `SKIM_ADMIN_PASSWORD` is changed from `changeme`
- [ ] Server runs behind nginx/caddy with TLS
- [ ] `skim server --host 127.0.0.1` (nginx terminates TLS, proxies to localhost)
- [ ] `/data` volume is mounted for SQLite persistence
- [ ] gunicorn is installed (auto-detected, runs 4 workers)
- [ ] Backups of `skim.db` are scheduled
- [ ] `SKIM_SERVER_URL` + `SKIM_SERVER_TOKEN` distributed to developer machines
- [ ] Budget set at global level as a safety net
- [ ] Webhook configured for budget alerts

See [deployment guide](deployment.md) for a complete production setup.
