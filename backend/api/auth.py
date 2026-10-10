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

from backend.workspace import LOCAL_USER_ID, get_workspace, reset_current_user, set_current_user

PUBLIC_API_PATHS = {"/api/v1/config", "/api/v1/info"}
TOKEN_CACHE_SECONDS = 300

_token_cache: Dict[str, Tuple[float, dict]] = {}


def supabase_public_config() -> Dict[str, Optional[str]]:
    return {
        "supabase_url": os.getenv("SUPABASE_URL") or None,
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY") or None,
    }


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

        user_id = LOCAL_USER_ID
        if auth_enabled():
            headers = dict(scope.get("headers") or [])
            auth = headers.get(b"authorization", b"").decode()
            token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
            user = await _verify_token(token) if token else None
            if not user:
                await _send_json(send, 401, {
                    "error": {"code": "UNAUTHORIZED", "message": "Please sign in again.", "request_id": ""}
                })
                return
            user_id = user["id"]

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


async def _send_json(send, status: int, body: dict) -> None:
    data = json.dumps(body).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode())],
    })
    await send({"type": "http.response.body", "body": data})
