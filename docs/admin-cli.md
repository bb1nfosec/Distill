# skim admin CLI

`skim admin` manages users, budgets, keys, webhooks, and exports from the terminal — no browser needed.

## Setup

```bash
export SKIM_SERVER_URL=https://skim.corp.internal   # your skim server
export SKIM_SERVER_TOKEN=sk-skim-...                # admin-scoped API key
```

Run `skim admin` with no arguments to see the full help.

---

## Users

### List users

```bash
skim admin users list
```

```
  Email                          Name               Team            Role
  ─────────────────────────────── ─────────────────── ─────────────── ──────────
  admin@corp.com                  Admin              —               admin
  jane@corp.com                   Jane Smith         platform        team_admin
  dev@corp.com                    Dev One            engineering     user
```

### Invite a user

```bash
skim admin users invite \
  --email dev@corp.com \
  --role user \
  --team engineering

# → ✓ Invite created for dev@corp.com
# →   https://skim.corp:7475/invite/abc123def456...
```

Share the invite URL. The user clicks it, enters their name and password, and is automatically added with the specified role and team. Invites expire in 7 days and are single-use.

**Roles:** `user` · `team_admin` · `admin`

### Delete a user

```bash
skim admin users delete dev@corp.com
```

---

## Budgets

### List all budgets

```bash
skim admin budget list
```

```
  ID    Type     Owner                    Tokens         USD     Period     Alert%
  ───── ──────── ──────────────────────── ────────────── ─────── ────────── ──────
  1     user     user-abc-123             1,000,000       —       monthly    80.0%
  2     team     engineering             —               500     monthly    80.0%
  3     global   global                  10,000,000      —       monthly    80.0%
```

### Set a budget

**Token limit:**
```bash
skim admin budget set \
  --owner-type user \
  --owner-id <user-id> \
  --tokens 1000000 \
  --period monthly \
  --alert-pct 80

# → ✓ Budget set (id=1)
```

**Cost limit:**
```bash
skim admin budget set \
  --owner-type team \
  --owner-id engineering \
  --usd 500 \
  --period monthly
```

**Global org cap:**
```bash
skim admin budget set \
  --owner-type global \
  --tokens 10000000 \
  --period monthly
```

**Periods:** `daily` · `weekly` · `monthly`

> If a budget for the given owner already exists, it is updated in place.

### Delete a budget

```bash
skim admin budget delete <id>
```

---

## API Keys

### List keys (own keys)

```bash
skim admin keys list

  Key (prefix)         Label              Scope      Expires                  Last used
  ──────────────────── ────────────────── ────────── ──────────────────────── ────────────────────
  sk-skim-abc123abc…   proxy              ingest     never                    2026-05-31T14:23:01Z
  sk-skim-def456def…   ci-reader          read       2026-08-31T00:00:00Z     2026-05-30T09:10:22Z
```

### Revoke a key

```bash
skim admin keys revoke sk-skim-abc1

# → ✓ Key revoked
```

Pass at least the first 8 characters as the prefix.

---

## Webhooks

### List webhooks

```bash
skim admin webhooks list

  ID    Channel  Events                              URL
  ───── ──────── ─────────────────────────────────── ──────────────────────────────
  1     slack    budget.warning,budget.exceeded       https://hooks.slack.com/...
  2     http     budget.exceeded                      https://ops.corp.com/hook
```

### Add a webhook

**Slack:**
```bash
skim admin webhooks add \
  --url https://hooks.slack.com/services/T.../B.../... \
  --channel slack \
  --events budget.warning,budget.exceeded
```

**Generic HTTP with HMAC signing:**
```bash
skim admin webhooks add \
  --url https://your-system.example.com/hooks/skim \
  --channel http \
  --events budget.warning,budget.exceeded \
  --secret your-hmac-secret
```

**Available events:** `budget.warning` · `budget.exceeded` · `daily.digest`

### Delete a webhook

```bash
skim admin webhooks delete <id>
```

---

## Export

### Export events as CSV

```bash
skim admin export --days 30 --out june-2026.csv

# → ✓ Exported to june-2026.csv
```

The CSV includes: `id, ts, user_id, session_id, provider, model, input_tokens, output_tokens, saved_tokens, cached_tokens, cost_usd, project_path, latency_ms, command`

---

## Audit log

### View recent actions

```bash
skim admin audit --days 30
```

```
  Timestamp              User                         Action                 Detail
  ────────────────────── ──────────────────────────── ────────────────────── ──────────────────────
  2026-05-31 14:23:01    admin@corp.com               auth.login
  2026-05-31 14:24:10    admin@corp.com               budget.created         user:abc123
  2026-05-31 14:31:55    dev@corp.com                 auth.key_created       scope=ingest
  2026-05-31 15:00:00    system                       webhook.fired          budget.warning → https://...

  142 entries
```

### Filter by action

```bash
skim admin audit --days 7 --action auth.login
skim admin audit --days 30 --action budget
skim admin audit --days 90 --action user.invited
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (server unreachable, auth failed, not found, etc.) |

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SKIM_SERVER_URL` | Yes | Base URL of the skim server. Example: `https://skim.corp.internal` |
| `SKIM_SERVER_TOKEN` | Yes | API key with `admin` scope for management, `read` scope for export |

Both must be set or `skim admin` exits immediately with a clear error.
