"""Per-user workspaces.

Every signed-in user gets an isolated workspace: their own SQLite database plus the
in-memory review/portfolio services that sit on top of it. Nothing is shared between
users, so a new account always starts with an empty dashboard.

When Supabase is not configured the app runs in single-user local mode and the
"local" workspace reuses the global database configured by VERITY_DATABASE_URL.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from contextvars import ContextVar
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("verity.workspace")

LOCAL_USER_ID = "local"

_current_user_id: ContextVar[str] = ContextVar("verity_user_id", default=LOCAL_USER_ID)


def workspace_root() -> Path:
    return Path(os.getenv("VERITY_WORKSPACE_DIR", "data/workspaces"))


def _safe_user_dir(user_id: str) -> str:
    """User ids come from verified JWTs, but keep the path component strictly safe anyway."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", user_id)
    if not cleaned:
        raise ValueError("Invalid user id")
    return cleaned


class Workspace:
    """All stateful services belonging to one user."""

    def __init__(self, user_id: str) -> None:
        from backend.api.dependencies import PersistentCaseStore
        from backend.controller.remediation.service import RemediationActionService
        from backend.controller.service import ControllerService
        from backend.cross_case.service import CrossCaseIntelligenceService
        from backend.portfolio.service import PortfolioService
        from backend.review.service import ReviewService
        from backend.storage.database import DatabaseEngine, get_database_engine
        from backend.storage.config import StorageSettings
        from backend.storage.service import StorageService, get_storage_service

        self.user_id = user_id
        self.lock = threading.RLock()

        if user_id == LOCAL_USER_ID:
            self.dir: Optional[Path] = None
            self.engine = get_database_engine()
            self.storage = get_storage_service()
        else:
            self.dir = workspace_root() / _safe_user_dir(user_id)
            self.dir.mkdir(parents=True, exist_ok=True)
            from backend import cloud_sync

            cloud_sync.restore_workspace(user_id, self.dir)
            settings = StorageSettings(database_url=f"sqlite:///{self.db_path}")
            self.engine = DatabaseEngine(settings)
            self.engine.initialize()
            self.storage = StorageService(self.engine)

        from backend.case_processing.service import CaseProcessingService

        self.case_service = CaseProcessingService()
        self.case_store = PersistentCaseStore(self.storage)
        self.controller = ControllerService()
        self.review = ReviewService()
        self.portfolio = PortfolioService()
        self.cross_case = CrossCaseIntelligenceService(self.engine)
        self.remediation = RemediationActionService(engine=self.engine)
        self._load_review_state()

    @property
    def db_path(self) -> Path:
        assert self.dir is not None
        return self.dir / "verity.db"

    @property
    def review_state_path(self) -> Optional[Path]:
        if self.dir:
            return self.dir / "reviews.json"
        # Local mode: keep review state next to the local database file.
        if getattr(self.engine, "is_memory", True):
            return None
        return Path(self.engine.db_path).parent / "reviews.json"

    def _load_review_state(self) -> None:
        path = self.review_state_path
        if path and path.exists():
            try:
                self.review.load_state(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                logger.exception("Could not restore review state for workspace %s", self.user_id)

    def persist(self) -> None:
        """Writes in-memory review state to disk and schedules a cloud backup."""
        path = self.review_state_path
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.review.export_state()), encoding="utf-8")
            tmp.replace(path)
        from backend import cloud_sync

        cloud_sync.schedule_backup(self)


_workspaces: Dict[str, Workspace] = {}
_registry_lock = threading.Lock()


def get_workspace(user_id: Optional[str] = None) -> Workspace:
    uid = user_id or _current_user_id.get()
    with _registry_lock:
        ws = _workspaces.get(uid)
        if ws is None:
            ws = Workspace(uid)
            _workspaces[uid] = ws
        return ws


def set_current_user(user_id: str):
    return _current_user_id.set(user_id)


def reset_current_user(token) -> None:
    _current_user_id.reset(token)


def all_workspaces() -> list[Workspace]:
    with _registry_lock:
        return list(_workspaces.values())
