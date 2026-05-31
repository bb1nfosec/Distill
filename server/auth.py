"""
auth.py — Authentication for skim server.

Supports:
  - Local password auth (bcrypt via passlib, or SHA-256 fallback)
  - API key auth  (Bearer sk-skim-...)
  - OIDC/OAuth2   (Google, GitHub, Azure AD, Okta) — requires authlib
  - LDAP/AD       (enterprise) — requires ldap3

JWT is issued on successful login and validated on every API request.
"""

import hashlib
import hmac
import json
import os
import time
import uuid
from functools import wraps
from typing import Callable

# ── JWT (stdlib, no PyJWT needed) ────────────────────────────────────────────

import base64

_SECRET = os.environ.get("SKIM_JWT_SECRET", uuid.uuid4().hex)
_TTL    = int(os.environ.get("SKIM_JWT_TTL", 86400 * 7))  # 7 days default


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * (pad % 4))


def issue_jwt(payload: dict) -> str:
    header  = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    now     = int(time.time())
    claims  = {**payload, "iat": now, "exp": now + _TTL}
    body    = _b64(json.dumps(claims).encode())
    sig     = hmac.new(_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256)
    return f"{header}.{body}.{_b64(sig.digest())}"


def verify_jwt(token: str) -> dict | None:
    try:
        header, body, sig = token.split(".")
        expected = hmac.new(_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256)
        if not hmac.compare_digest(_b64(expected.digest()), sig):
            return None
        claims = json.loads(_b64d(body))
        if claims.get("exp", 0) < time.time():
            return None
        return claims
    except Exception:
        return None


# ── Password hashing (SHA-256 fallback if bcrypt unavailable) ────────────────

def hash_password(pw: str) -> str:
    try:
        from passlib.hash import bcrypt
        return bcrypt.hash(pw)
    except ImportError:
        salt = uuid.uuid4().hex
        h    = hashlib.sha256(f"{salt}{pw}".encode()).hexdigest()
        return f"sha256${salt}${h}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        from passlib.hash import bcrypt
        if stored.startswith("$2"):
            return bcrypt.verify(pw, stored)
    except ImportError:
        pass
    if stored.startswith("sha256$"):
        _, salt, h = stored.split("$")
        return hmac.compare_digest(h, hashlib.sha256(f"{salt}{pw}".encode()).hexdigest())
    return False


# ── LDAP auth (optional) ─────────────────────────────────────────────────────

def ldap_authenticate(username: str, password: str) -> dict | None:
    """
    Authenticate against LDAP/Active Directory.
    Configure via env vars:
      SKIM_LDAP_URL         ldaps://ad.corp.example.com
      SKIM_LDAP_BASE_DN     DC=corp,DC=example,DC=com
      SKIM_LDAP_BIND_USER   svc-skim@corp.example.com  (optional service account)
      SKIM_LDAP_BIND_PASS   (password for service account)
      SKIM_LDAP_USER_ATTR   sAMAccountName  (default)
      SKIM_LDAP_EMAIL_ATTR  mail            (default)
      SKIM_LDAP_GROUP_ATTR  memberOf        (optional — restrict to group)
      SKIM_LDAP_GROUP_DN    CN=skim-users,OU=Groups,DC=corp,DC=example,DC=com
    """
    url      = os.environ.get("SKIM_LDAP_URL", "")
    base_dn  = os.environ.get("SKIM_LDAP_BASE_DN", "")
    if not url or not base_dn:
        return None

    try:
        from ldap3 import Server, Connection, ALL, NTLM
    except ImportError:
        return None  # ldap3 not installed — skip

    user_attr  = os.environ.get("SKIM_LDAP_USER_ATTR",  "sAMAccountName")
    email_attr = os.environ.get("SKIM_LDAP_EMAIL_ATTR", "mail")
    group_dn   = os.environ.get("SKIM_LDAP_GROUP_DN", "")

    try:
        server   = Server(url, get_info=ALL)
        user_dn  = f"{user_attr}={username},{base_dn}"
        conn     = Connection(server, user=user_dn, password=password, auto_bind=True)
        attrs    = [email_attr, "cn", "displayName"]
        conn.search(base_dn, f"({user_attr}={username})", attributes=attrs)
        if not conn.entries:
            return None
        entry = conn.entries[0]
        email = str(entry[email_attr]) if email_attr in entry else f"{username}@ldap"
        name  = str(entry["displayName"]) if "displayName" in entry else username

        if group_dn:
            conn.search(base_dn, f"(&({user_attr}={username})(memberOf={group_dn}))",
                        attributes=["cn"])
            if not conn.entries:
                return None  # not in required group

        return {"email": email, "name": name, "source": "ldap"}
    except Exception:
        return None


# ── OIDC/OAuth2 (optional via authlib) ───────────────────────────────────────

def get_oidc_providers() -> dict:
    """
    Return configured OIDC providers.
    Configure via env vars:
      SKIM_OIDC_GOOGLE_CLIENT_ID      /  SKIM_OIDC_GOOGLE_CLIENT_SECRET
      SKIM_OIDC_GITHUB_CLIENT_ID      /  SKIM_OIDC_GITHUB_CLIENT_SECRET
      SKIM_OIDC_AZURE_CLIENT_ID       /  SKIM_OIDC_AZURE_CLIENT_SECRET / SKIM_OIDC_AZURE_TENANT
      SKIM_OIDC_CUSTOM_CLIENT_ID      /  SKIM_OIDC_CUSTOM_CLIENT_SECRET / SKIM_OIDC_CUSTOM_DISCOVERY
    """
    providers = {}

    if os.environ.get("SKIM_OIDC_GOOGLE_CLIENT_ID"):
        providers["google"] = {
            "client_id":     os.environ["SKIM_OIDC_GOOGLE_CLIENT_ID"],
            "client_secret": os.environ.get("SKIM_OIDC_GOOGLE_CLIENT_SECRET", ""),
            "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
            "client_kwargs": {"scope": "openid email profile"},
        }

    if os.environ.get("SKIM_OIDC_GITHUB_CLIENT_ID"):
        providers["github"] = {
            "client_id":      os.environ["SKIM_OIDC_GITHUB_CLIENT_ID"],
            "client_secret":  os.environ.get("SKIM_OIDC_GITHUB_CLIENT_SECRET", ""),
            "access_token_url": "https://github.com/login/oauth/access_token",
            "authorize_url":    "https://github.com/login/oauth/authorize",
            "api_base_url":     "https://api.github.com/",
            "client_kwargs":    {"scope": "user:email"},
        }

    if os.environ.get("SKIM_OIDC_AZURE_CLIENT_ID"):
        tenant = os.environ.get("SKIM_OIDC_AZURE_TENANT", "common")
        providers["azure"] = {
            "client_id":     os.environ["SKIM_OIDC_AZURE_CLIENT_ID"],
            "client_secret": os.environ.get("SKIM_OIDC_AZURE_CLIENT_SECRET", ""),
            "server_metadata_url": f"https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration",
            "client_kwargs": {"scope": "openid email profile"},
        }

    if os.environ.get("SKIM_OIDC_CUSTOM_DISCOVERY"):
        providers["custom"] = {
            "client_id":     os.environ.get("SKIM_OIDC_CUSTOM_CLIENT_ID", ""),
            "client_secret": os.environ.get("SKIM_OIDC_CUSTOM_CLIENT_SECRET", ""),
            "server_metadata_url": os.environ["SKIM_OIDC_CUSTOM_DISCOVERY"],
            "client_kwargs": {"scope": "openid email profile"},
        }

    return providers
