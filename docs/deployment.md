# Deployment

This guide covers production deployment of the skim server. The proxy runs on each developer machine — no special deployment needed for it.

## Minimum requirements

- Python 3.10+
- 512 MB RAM (SQLite-backed, very lightweight)
- Any Linux/macOS host with outbound HTTPS (for the dashboard, not the proxy)
- Persistent disk for `skim.db` (grows at ~1 KB per API call)

---

## Option 1 — Docker (recommended)

### Quick start

```bash
docker run -d \
  --name skim \
  --restart unless-stopped \
  -p 7475:7475 \
  -e SKIM_ADMIN_EMAIL=admin@corp.com \
  -e SKIM_ADMIN_PASSWORD=changeme \
  -e SKIM_JWT_SECRET=$(openssl rand -hex 32) \
  -e SKIM_DB_PATH=/data/skim.db \
  -v /data/skim:/data \
  ghcr.io/bb1nfosec/skim
```

- Dashboard: `http://localhost:7475/dashboard`
- Health: `http://localhost:7475/api/v1/health`
- Data: `/data/skim.db` on host

### With nginx (TLS termination)

**`docker-compose.yml`:**
```yaml
version: "3.9"
services:
  skim:
    image: ghcr.io/bb1nfosec/skim
    restart: unless-stopped
    environment:
      SKIM_JWT_SECRET: "${SKIM_JWT_SECRET}"
      SKIM_ADMIN_EMAIL: "${SKIM_ADMIN_EMAIL}"
      SKIM_ADMIN_PASSWORD: "${SKIM_ADMIN_PASSWORD}"
      SKIM_DB_PATH: /data/skim.db
    volumes:
      - skim-data:/data
    expose:
      - "7475"

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/ssl/certs:ro
    depends_on:
      - skim

volumes:
  skim-data:
```

**`.env`:**
```bash
SKIM_JWT_SECRET=<output of: openssl rand -hex 32>
SKIM_ADMIN_EMAIL=admin@corp.com
SKIM_ADMIN_PASSWORD=your-secure-password
```

**`nginx.conf` (minimal):**
```nginx
events {}
http {
  upstream skim { server skim:7475; }

  server {
    listen 80;
    server_name skim.corp.internal;
    return 301 https://$host$request_uri;
  }

  server {
    listen 443 ssl;
    server_name skim.corp.internal;

    ssl_certificate     /etc/ssl/certs/skim.crt;
    ssl_certificate_key /etc/ssl/certs/skim.key;

    location / {
      proxy_pass         http://skim;
      proxy_set_header   Host $host;
      proxy_set_header   X-Real-IP $remote_addr;
      proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header   X-Forwarded-Proto $scheme;

      # Required for SSE (Server-Sent Events)
      proxy_buffering    off;
      proxy_cache        off;
      proxy_read_timeout 300s;
    }
  }
}
```

**Deploy:**
```bash
docker compose up -d
```

---

## Option 2 — Direct (systemd)

### Install

```bash
pip install 'skim-llm[web,tiktoken]'

# Production: also install gunicorn (skim auto-detects it)
pip install gunicorn
```

### Create service file

`/etc/systemd/system/skim.service`:
```ini
[Unit]
Description=skim token intelligence server
After=network.target

[Service]
Type=simple
User=skim
Group=skim
WorkingDirectory=/opt/skim

Environment=SKIM_JWT_SECRET=<your-secret>
Environment=SKIM_ADMIN_EMAIL=admin@corp.com
Environment=SKIM_ADMIN_PASSWORD=changeme
Environment=SKIM_DB_PATH=/var/lib/skim/skim.db

ExecStart=/usr/local/bin/skim server --host 127.0.0.1 --port 7475
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Enable and start

```bash
useradd --system --no-create-home skim
mkdir -p /var/lib/skim
chown skim:skim /var/lib/skim

systemctl daemon-reload
systemctl enable skim
systemctl start skim
systemctl status skim
```

### nginx config (same as Docker option above)

Point nginx to `127.0.0.1:7475`.

---

## Production server

skim detects gunicorn automatically at startup. If installed, it runs with 4 workers — no extra config needed.

```bash
pip install gunicorn
skim server --host 127.0.0.1 --port 7475
# → starts gunicorn with 4 workers automatically
```

If gunicorn is not installed, Flask's development server runs with a clear warning. It works but is not suitable for production load.

**Manual gunicorn (if needed):**
```bash
gunicorn 'server.app:create_app()' \
  --bind 127.0.0.1:7475 \
  --workers 4 \
  --worker-class sync \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

---

## Environment variables checklist

Before going live:

```bash
# Required — generates a new secret on every restart if not set
# This logs out all users on every deployment
SKIM_JWT_SECRET=$(openssl rand -hex 32)   # set once, keep fixed

# Required — auto-creates admin on first start
SKIM_ADMIN_EMAIL=admin@corp.com
SKIM_ADMIN_PASSWORD=change-this-immediately

# Recommended — explicit DB path for backups
SKIM_DB_PATH=/var/lib/skim/skim.db
```

---

## SSE and reverse proxies

skim uses Server-Sent Events for real-time dashboard updates. Most reverse proxies buffer responses by default, which breaks SSE.

**nginx:** Add `proxy_buffering off;` and `proxy_read_timeout 300s;` to the location block (shown above).

**Caddy:** SSE works without special config — Caddy doesn't buffer by default.

**AWS ALB / CloudFront:** Enable "streaming" on the target group. Set idle timeout > 60s.

**Cloudflare:** Turn off response buffering in the Rules settings for the skim hostname.

---

## Backups

SQLite is a single file. Back it up with any standard method:

```bash
# Copy while server is running (WAL mode makes this safe)
cp /var/lib/skim/skim.db /backup/skim-$(date +%Y%m%d).db

# Or use sqlite3 online backup
sqlite3 /var/lib/skim/skim.db ".backup /backup/skim-$(date +%Y%m%d).db"
```

Schedule with cron or your infrastructure's backup system.

---

## Health checks

```bash
curl http://localhost:7475/api/v1/health
# {"status": "ok", "version": "0.5.0"}
```

The Dockerfile includes a built-in health check every 30 seconds.

---

## Scaling

skim uses SQLite with WAL mode. For teams under ~200 developers and ~50k events/day, this is sufficient with no additional infrastructure.

For larger scale:
- Run multiple skim server instances behind a load balancer (each with its own SQLite, or migrate to PostgreSQL via a future adapter)
- Use read replicas for the dashboard while the proxy writes to a primary

The SQLite WAL mode allows concurrent reads while writes are serialised — typical dashboard queries (reads) won't be blocked by event ingestion (writes).

---

## Monitoring

**Key metrics to watch:**

| Metric | Source | Alert if |
|--------|--------|----------|
| Health endpoint | `GET /api/v1/health` | Non-200 |
| DB file size | `ls -lh /var/lib/skim/skim.db` | > 10 GB |
| Process memory | `ps aux \| grep skim` | > 500 MB |
| Event ingestion | `GET /api/v1/stats/summary` | `total_calls` stops growing |

**Logs:**
- systemd: `journalctl -u skim -f`
- Docker: `docker logs skim -f`
- gunicorn: stdout (configure with `--access-logfile` / `--error-logfile`)
