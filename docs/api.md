# REST API Reference

The skim server (`skim server`) exposes a JSON REST API at `http://localhost:7475`.

## Authentication

All protected endpoints require a JWT or API key in the `Authorization` header.

```
Authorization: Bearer <jwt-token>        # from POST /api/v1/auth/login
Authorization: Bearer sk-skim-<key>      # from POST /api/v1/auth/keys
```

API keys are scoped: `ingest` (proxy events only), `read` (stats + export), `admin` (full access). Requests that use a key with insufficient scope return `403`.

---

## Auth

### `POST /api/v1/auth/login`

Authenticate with email + password (or LDAP). Returns a JWT.

**Request:**
```json
{"email": "you@corp.com", "password": "your-password"}
```

**Response `200`:**
```json
{"token": "eyJ...", "user": {"id": "...", "email": "...", "role": "admin", "team": ""}}
```

**Response `401`:** Invalid credentials.

---

### `GET /api/v1/auth/me`

Returns the currently authenticated user.

**Response `200`:**
```json
{"user": {"id": "...", "email": "...", "name": "...", "role": "user", "team": "platform"}}
```

---

### `GET /api/v1/auth/keys`

List your API keys.

**Response `200`:**
```json
{"keys": [{"key": "sk-skim-...", "label": "proxy", "scope": "ingest", "created_at": "...", "expires_at": null, "last_used": "..."}]}
```

---

### `POST /api/v1/auth/keys`

Create a new API key.

**Request:**
```json
{"label": "ci-reader", "scope": "read", "expires_days": 90}
```
`scope`: `"ingest"` | `"read"` | `"admin"` (admin scope requires admin role).

**Response `201`:**
```json
{"key": "sk-skim-...", "label": "ci-reader", "scope": "read"}
```

---

### `DELETE /api/v1/auth/keys/<key_prefix>`

Revoke an API key. Pass the first 12+ characters as the prefix.

**Response `200`:** `{"revoked": true}`

---

### `GET /api/v1/auth/oidc/providers`

List configured OIDC providers (for login page).

**Response `200`:** `{"providers": ["google", "github"]}`

---

### `POST /api/v1/auth/register`

Self-register via an invite token.

**Request:**
```json
{"token": "abc123...", "name": "Jane Smith", "password": "secure-pass"}
```

**Response `201`:** `{"token": "eyJ...", "user": {...}}`
**Response `400`:** Invalid/expired invite or password too short.
**Response `409`:** Email already registered.

---

## Statistics

All stats endpoints accept `?days=N` (default varies per endpoint).

### `GET /api/v1/stats/summary?days=7`

Aggregate summary for the period. Admins see org-wide; users see own data.

**Response `200`:**
```json
{
  "total_calls": 142,
  "total_input": 1823400,
  "total_output": 94200,
  "total_saved": 441000,
  "total_cached": 680000,
  "total_cost": 5.47,
  "avg_latency": 1240,
  "avg_input": 12840
}
```

---

### `GET /api/v1/stats/daily?days=30`

Daily breakdown. **Response `200`:** `{"data": [{"day": "2026-05-31", "calls": 12, "input_tokens": 84200, "saved_tokens": 22100, "cost_usd": 0.2526}]}`

---

### `GET /api/v1/stats/hourly?days=7`

Hourly breakdown. **Response `200`:** `{"data": [{"hour": "2026-05-31T14", "calls": 3, "input_tokens": 18400, "cost_usd": 0.055}]}`

---

### `GET /api/v1/stats/by-user?days=30`

Per-user breakdown. Requires `team_admin` or `admin`. Team admins see only their own team.

**Response `200`:**
```json
{"data": [{"user_name": "Jane", "email": "jane@corp.com", "team": "platform", "calls": 42, "input_tokens": 340000, "cost_usd": 1.02, "waste_pct": 18.4, "cache_hit_pct": 52.1, "avg_latency_ms": 1100}]}
```

---

### `GET /api/v1/stats/by-model?days=30`

Per-model breakdown with cache and waste percentages. **Response `200`:** `{"data": [{"model": "claude-sonnet-4-6", "calls": 120, "input_tokens": 1400000, "output_tokens": 82000, "cost_usd": 4.20, "cache_hit_pct": 48.2, "waste_pct": 22.1, "avg_latency_ms": 1280}]}`

---

### `GET /api/v1/insights?days=30`

AI-generated optimization recommendations. **Admin only.**

**Response `200`:**
```json
{"insights": [{"severity": "high", "title": "Low waste filtering rate", "detail": "Only 12% of tokens are being stripped...", "action": "skim fix --path ."}], "days": 30}
```

---

## Events

### `POST /api/v1/events`

Ingest a token usage event from the proxy. Uses `ingest`-scoped keys.

**Request:**
```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "input_tokens": 12400,
  "output_tokens": 840,
  "saved_tokens": 4200,
  "cached_tokens": 6800,
  "cost_usd": 0.0372,
  "latency_ms": 1240,
  "session_id": "sess-abc",
  "project_path": "/home/user/my-project"
}
```

**Response `201`:** `{"id": 142}`

Budget thresholds are checked after insertion. If a threshold is crossed, webhooks are fired asynchronously.

---

### `GET /api/v1/events?days=7&limit=100&offset=0`

List events. Admins see all; users see own. Max `limit` is 500.

**Response `200`:** `{"events": [...], "count": 87}`

---

### `GET /skim/stream`

Server-Sent Events stream. Send `Authorization: Bearer <token>` header (or use EventSource with a token query param).

Each event is a JSON payload:
```
data: {"type": "event", "provider": "anthropic", "model": "...", "input_tokens": 12400, ...}
```

Heartbeat every 25 seconds:
```
:heartbeat
```

---

## Budget

### `POST /api/v1/budget/check`

Check whether a user is within their budget. Called by the proxy before forwarding.

**Request:**
```json
{"user_id": "user-uuid", "input_tokens": 15000}
```

**Response `200` (allowed):**
```json
{"allowed": true, "reason": "ok", "pct_used": 74.2, "at_warning": false, "remaining_tokens": 257400, "budget_type": "user"}
```

**Response `429` (blocked):**
```json
{"allowed": false, "reason": "user token budget exceeded (103% used)", "pct_used": 103.0, "budget_type": "user"}
```

---

### `GET /api/v1/admin/budgets`

List all budgets. **Admin only.**

**Response `200`:** `{"budgets": [{"id": 1, "owner_type": "user", "owner_id": "...", "limit_tokens": 1000000, "limit_usd": null, "period": "monthly", "alert_pct": 80.0}]}`

---

### `POST /api/v1/admin/budgets`

Create or update a budget. **Admin only.**

**Request:**
```json
{
  "owner_type": "user",
  "owner_id": "user-uuid",
  "limit_tokens": 1000000,
  "limit_usd": null,
  "period": "monthly",
  "alert_pct": 80
}
```
`owner_type`: `"user"` | `"team"` | `"global"`. For `"global"`, omit `owner_id`.

**Response `201`:** `{"budget": {...}}`

---

### `DELETE /api/v1/admin/budgets/<id>`

Delete a budget. **Admin only.** **Response `200`:** `{"deleted": true}`

---

## Webhooks

### `GET /api/v1/admin/webhooks`

List webhooks. **Admin only.** **Response `200`:** `{"webhooks": [{"id": 1, "url": "...", "channel": "slack", "events": "budget.warning,budget.exceeded", "active": 1}]}`

---

### `POST /api/v1/admin/webhooks`

Create a webhook. **Admin only.**

**Request:**
```json
{
  "url": "https://hooks.slack.com/services/...",
  "channel": "slack",
  "events": "budget.warning,budget.exceeded",
  "secret": "optional-hmac-secret"
}
```
`channel`: `"http"` (generic HMAC-signed) | `"slack"` (Slack-formatted, also works with Teams).

**Response `201`:** `{"webhook": {"id": 3, "url": "...", "channel": "slack", ...}}`

---

### `DELETE /api/v1/admin/webhooks/<id>`

Delete a webhook. **Admin only.** **Response `200`:** `{"deleted": true}`

---

## Invites

### `POST /api/v1/admin/invites`

Create an invite. **Admin only.**

**Request:**
```json
{"email": "new@corp.com", "role": "user", "team": "engineering"}
```
`role`: `"user"` | `"team_admin"` | `"admin"`.

**Response `201`:**
```json
{"token": "abc123...", "email": "new@corp.com", "role": "user", "team": "engineering", "expires_at": "...", "invite_url": "https://skim.corp:7475/invite/abc123..."}
```

---

### `GET /api/v1/admin/invites`

List all pending invites. **Admin only.**

---

## Users

### `GET /api/v1/admin/users`

List all users. **Admin only.** **Response `200`:** `{"users": [{"id": "...", "email": "...", "name": "...", "team": "...", "role": "..."}]}`

---

### `POST /api/v1/admin/users`

Create a user directly (without invite). **Admin only.**

**Request:** `{"email": "...", "name": "...", "team": "...", "role": "user", "password": "..."}`

**Response `201`:** `{"user": {...}}`

---

### `DELETE /api/v1/admin/users/<user_id>`

Delete a user. **Admin only.** **Response `200`:** `{"deleted": true}`

---

## Export

### `GET /api/v1/export/events.csv?days=30`

Download events as CSV. Admins get all events; users get own data. Max 10,000 rows.

**Response:** `text/csv` with `Content-Disposition: attachment; filename=skim-events-30d.csv`

---

### `GET /api/v1/export/summary.json?days=30`

Structured JSON report for BI tools.

**Response `200`:**
```json
{
  "generated_at": "2026-05-31T14:23:01Z",
  "period_days": 30,
  "summary": {"total_calls": 420, "total_input": 5200000, ...},
  "by_day": [...],
  "by_model": [...]
}
```

---

## Audit

### `GET /api/v1/admin/audit?days=30&action=auth.login&limit=200`

Query the audit log. **Admin only.**

**Query params:**
- `days` (int, default 30): Period to query
- `action` (string, optional): Filter by action (partial match)
- `limit` (int, default 200, max 1000): Results per page

**Response `200`:** `{"log": [{"ts": "...", "user_id": "...", "email": "...", "action": "auth.login", "resource_type": null, "resource_id": null, "detail": null}]}`

---

## Health

### `GET /api/v1/health`

No auth required. **Response `200`:** `{"status": "ok", "version": "0.5.0"}`

---

## Error responses

All errors return a JSON body:
```json
{"error": "Human-readable error message"}
```

| Code | Meaning |
|------|---------|
| `400` | Bad request — missing required field or invalid value |
| `401` | Unauthorized — missing or invalid token |
| `403` | Forbidden — insufficient role or scope |
| `404` | Not found |
| `409` | Conflict — resource already exists (e.g., email taken) |
| `429` | Budget exceeded — proxy request blocked |
| `500` | Server error |
