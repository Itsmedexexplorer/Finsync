"""Supabase authentication for the API.

When SUPABASE_URL and SUPABASE_ANON_KEY are set, every /api/ request (except the public
config endpoint) must carry a Supabase access token. The token is checked against
Supabase Auth and the request runs inside that user's workspace. Without Supabase the
app runs in single-user local mode.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Dict, Optional, Tuple

import httpx

from backend.api import rate_limit as rl
from backend.workspace import LOCAL_USER_ID, get_workspace, reset_current_user, set_current_user

PUBLIC_API_PATHS = {"/api/v1/config", "/api/v1/info"}
TOKEN_CACHE_SECONDS = 300

_token_cache: Dict[str, Tuple[float, dict]] = {}


def supabase_public_config() -> Dict[str, object]:
    url = os.getenv("SUPABASE_URL") or None
    key = os.getenv("SUPABASE_ANON_KEY") or None
    return {
        "supabase_url": url,
        "supabase_anon_key": key,
        # The web app must never fall back to "no login" when this is true.
        "auth_required": bool(url and key) or _is_production(),
    }


def _is_production() -> bool:
    return os.getenv("VERITY_ENV", "development").lower() == "production"


def auth_enabled() -> bool:
    cfg = supabase_public_config()
    return bool(cfg["supabase_url"] and cfg["supabase_anon_key"])


async def _verify_token(token: str) -> Optional[dict]:
    key = hashlib.sha256(token.encode()).hexdigest()
    cached = _token_cache.get(key)
    now = time.time()
    if cached and cached[0] > now:
        return cached[1]

    cfg = supabase_public_config()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{cfg['supabase_url'].rstrip('/')}/auth/v1/user",
                headers={"Authorization": f"Bearer {token}", "apikey": cfg["supabase_anon_key"]},
            )
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    user = r.json()
    if not user.get("id"):
        return None
    if len(_token_cache) > 5000:
        _token_cache.clear()
    _token_cache[key] = (now + TOKEN_CACHE_SECONDS, user)
    return user


class SupabaseAuthMiddleware:
    """Pure ASGI middleware so the user context propagates into sync endpoints."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")
        needs_user = path.startswith("/api/") and path not in PUBLIC_API_PATHS and method != "OPTIONS"

        if not needs_user:
            await self.app(scope, receive, send)
            return

        ip = rl.client_ip(scope)
        wait = rl.limiter.hit(f"ip:{ip}", rl.IP_LIMIT)
        if wait:
            await _send_rate_limited(send, wait)
            return

        user_id = LOCAL_USER_ID
        if auth_enabled():
            headers = dict(scope.get("headers") or [])
            auth = headers.get(b"authorization", b"").decode()
            token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
            user = await _verify_token(token) if token and len(token) < 4096 else None
            if not user:
                wait = rl.limiter.hit(f"anon:{ip}", rl.UNAUTHENTICATED_LIMIT)
                if wait:
                    await _send_rate_limited(send, wait)
                    return
                await _send_json(send, 401, {
                    "error": {"code": "UNAUTHORIZED", "message": "Please sign in again.", "request_id": ""}
                })
                return
            user_id = user["id"]
        elif _is_production():
            # Fail closed: a production server without auth configured must not expose data.
            await _send_json(send, 503, {
                "error": {"code": "AUTH_NOT_CONFIGURED", "message": "Sign-in is not configured on this server.", "request_id": ""}
            })
            return

        for name, limit in [("user", rl.USER_LIMIT)] + rl.user_limits_for(path, method):
            wait = rl.limiter.hit(f"{name}:{user_id}", limit)
            if wait:
                await _send_rate_limited(send, wait)
                return

        ctx_token = set_current_user(user_id)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_current_user(ctx_token)
            if method in ("POST", "PUT", "PATCH", "DELETE"):
                try:
                    get_workspace(user_id).persist()
                except Exception:
                    pass


async def _send_rate_limited(send, retry_after: int) -> None:
    minutes = (retry_after + 59) // 60
    wait_text = f"{retry_after} seconds" if retry_after < 90 else f"{minutes} minutes"
    await _send_json(send, 429, {
        "error": {"code": "RESOURCE_LIMIT", "message": f"Too many requests. Please wait {wait_text} and try again.", "request_id": ""}
    }, extra_headers=[(b"retry-after", str(retry_after).encode())])


async def _send_json(send, status: int, body: dict, extra_headers=None) -> None:
    data = json.dumps(body).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode())] + (extra_headers or []),
    })
    await send({"type": "http.response.body", "body": data})
