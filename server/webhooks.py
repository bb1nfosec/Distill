"""
webhooks.py — Background webhook delivery for skim server.

Fires on: budget.warning, budget.exceeded, daily.digest
Formats: Slack-compatible (also works with Teams) + generic HMAC-signed HTTP POST
Never blocks — each delivery runs in a daemon thread.
"""

import hashlib
import hmac
import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slack_payload(event_type: str, data: dict) -> dict:
    color_map = {
        "budget.warning":  "#f5a623",
        "budget.exceeded": "#ff4d6d",
        "daily.digest":    "#6c63ff",
    }
    color  = color_map.get(event_type, "#6c63ff")
    titles = {
        "budget.warning":  "⚠️ Budget warning",
        "budget.exceeded": "🚫 Budget exceeded",
        "daily.digest":    "📊 Daily digest",
    }
    title = titles.get(event_type, event_type)

    fields = []
    for k, v in data.items():
        if v is not None and k not in ("event", "ts"):
            fields.append({"title": k.replace("_", " ").title(), "value": str(v), "short": True})

    return {
        "text": f"*skim* — {title}",
        "attachments": [{
            "color":  color,
            "fields": fields,
            "footer": "skim token intelligence",
            "ts":     int(datetime.now(timezone.utc).timestamp()),
        }],
    }


def _http_payload(event_type: str, data: dict, secret: str) -> tuple[bytes, str]:
    payload = json.dumps({"event": event_type, "data": data, "ts": _ts()}).encode()
    sig = ""
    if secret:
        sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return payload, sig


def _deliver(webhook: dict, event_type: str, data: dict) -> None:
    url     = webhook["url"]
    channel = webhook.get("channel", "http")
    secret  = webhook.get("secret", "")
    try:
        if channel == "slack":
            body = json.dumps(_slack_payload(event_type, data)).encode()
            req  = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
        else:
            body, sig = _http_payload(event_type, data, secret)
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type",    "application/json")
            req.add_header("X-Skim-Event",    event_type)
            if sig:
                req.add_header("X-Skim-Signature", sig)
        with urllib.request.urlopen(req, timeout=8):
            pass
    except Exception:
        pass  # delivery failure is silent — never impacts ingestion


def fire(conn, event_type: str, data: dict) -> None:
    """
    Look up active webhooks subscribed to event_type and fire them
    in background daemon threads. Returns immediately.
    """
    from server.db import get_active_webhooks, log_audit
    try:
        hooks = get_active_webhooks(conn, event_type)
    except Exception:
        return
    for hook in hooks:
        t = threading.Thread(
            target=_deliver, args=(hook, event_type, data), daemon=True
        )
        t.start()
        try:
            log_audit(conn, action="webhook.fired",
                      resource_type="webhook", resource_id=str(hook.get("id")),
                      detail=f"{event_type} → {hook['url']}")
        except Exception:
            pass
