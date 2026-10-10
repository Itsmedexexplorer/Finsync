"""Durable backup of per-user workspaces to a private Supabase Storage bucket.

Hosts like Render's free tier wipe the local disk on every restart. Each workspace is a
small SQLite file plus a JSON file, so after every change we upload a consistent
snapshot, and when a workspace is opened on a fresh disk we download it again.

All functions are no-ops unless SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Dict

import httpx

if TYPE_CHECKING:
    from backend.workspace import Workspace

logger = logging.getLogger("verity.cloud_sync")

FILES = ("verity.db", "reviews.json")
DEBOUNCE_SECONDS = 2.0

_timers: Dict[str, threading.Timer] = {}
_timers_lock = threading.Lock()


def _config():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    bucket = os.getenv("VERITY_BACKUP_BUCKET", "workspaces")
    return url, key, bucket


def enabled() -> bool:
    url, key, _ = _config()
    return bool(url and key)


def _headers(key: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {key}", "apikey": key}


def ensure_bucket() -> None:
    """Creates the private backup bucket if it does not exist yet."""
    if not enabled():
        return
    url, key, bucket = _config()
    try:
        r = httpx.get(f"{url}/storage/v1/bucket/{bucket}", headers=_headers(key), timeout=15)
        if r.status_code == 200:
            return
        r = httpx.post(
            f"{url}/storage/v1/bucket",
            headers=_headers(key),
            json={"id": bucket, "name": bucket, "public": False},
            timeout=15,
        )
        if r.status_code not in (200, 201, 409):
            logger.error("Could not create backup bucket: %s %s", r.status_code, r.text)
    except httpx.HTTPError:
        logger.exception("Could not reach Supabase Storage")


def restore_workspace(user_id: str, target_dir: Path) -> None:
    """Downloads a user's backup into target_dir unless a local copy already exists."""
    if not enabled() or (target_dir / "verity.db").exists():
        return
    url, key, bucket = _config()
    for name in FILES:
        try:
            r = httpx.get(
                f"{url}/storage/v1/object/authenticated/{bucket}/{user_id}/{name}",
                headers=_headers(key),
                timeout=30,
            )
        except httpx.HTTPError:
            logger.exception("Restore of %s for %s failed", name, user_id)
            continue
        if r.status_code == 200:
            (target_dir / name).write_bytes(r.content)
            logger.info("Restored %s for workspace %s", name, user_id)


def _snapshot_db(src: Path) -> bytes:
    """Consistent copy of a live SQLite database (WAL included) via the backup API."""
    with tempfile.TemporaryDirectory() as tmp:
        dst_path = Path(tmp) / "snapshot.db"
        src_conn = sqlite3.connect(str(src))
        dst_conn = sqlite3.connect(str(dst_path))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()
        return dst_path.read_bytes()


def backup_now(ws: "Workspace") -> None:
    if not enabled() or ws.dir is None:
        return
    url, key, bucket = _config()
    payloads = {}
    with ws.lock:
        if ws.db_path.exists():
            payloads["verity.db"] = _snapshot_db(ws.db_path)
        if ws.review_state_path and ws.review_state_path.exists():
            payloads["reviews.json"] = ws.review_state_path.read_bytes()
    for name, data in payloads.items():
        try:
            r = httpx.post(
                f"{url}/storage/v1/object/{bucket}/{ws.user_id}/{name}",
                headers={**_headers(key), "x-upsert": "true", "Content-Type": "application/octet-stream"},
                content=data,
                timeout=60,
            )
            if r.status_code not in (200, 201):
                logger.error("Backup of %s for %s failed: %s %s", name, ws.user_id, r.status_code, r.text)
        except httpx.HTTPError:
            logger.exception("Backup of %s for %s failed", name, ws.user_id)


def schedule_backup(ws: "Workspace") -> None:
    """Debounced backup so a burst of edits results in one upload."""
    if not enabled() or ws.dir is None:
        return
    with _timers_lock:
        existing = _timers.get(ws.user_id)
        if existing:
            existing.cancel()
        timer = threading.Timer(DEBOUNCE_SECONDS, backup_now, args=(ws,))
        timer.daemon = True
        _timers[ws.user_id] = timer
        timer.start()


def flush_all() -> None:
    """Runs any pending backups immediately (called on shutdown)."""
    from backend.workspace import all_workspaces

    with _timers_lock:
        pending = list(_timers.keys())
        for t in _timers.values():
            t.cancel()
        _timers.clear()
    for ws in all_workspaces():
        if ws.user_id in pending:
            backup_now(ws)
