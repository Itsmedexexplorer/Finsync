"""FastAPI dependencies and CaseStore abstraction for VERITY (Day 16).

Provides abstract CaseStore interface with InMemoryCaseStore and PersistentCaseStore implementations.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections import OrderedDict
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from backend.case_processing.result import CaseProcessingResult
from backend.case_processing.service import CaseProcessingService
from backend.config import Settings, get_settings
from backend.storage.service import StorageService


class CaseStore(ABC):
    """Abstract store interface for case outputs and demo fixtures."""

    @abstractmethod
    def save_case(self, result: CaseProcessingResult) -> None:
        pass

    @abstractmethod
    def get_case(self, case_id: str) -> Optional[CaseProcessingResult]:
        pass

    @abstractmethod
    def get_case_count(self) -> int:
        pass

    @abstractmethod
    def list_demo_cases(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_cases(self) -> List[CaseProcessingResult]:
        pass

    @abstractmethod
    def get_demo_case_dict(self, case_id: str) -> Optional[Dict[str, Any]]:
        pass


class InMemoryCaseStore(CaseStore):
    """Thread-safe in-memory store for demo cases and dynamic user executions with FIFO eviction."""

    def __init__(self, max_capacity: Optional[int] = None) -> None:
        self._lock = Lock()
        self._settings = get_settings()
        self.max_capacity = max_capacity or self._settings.max_cases_in_memory
        self._cases: OrderedDict[str, CaseProcessingResult] = OrderedDict()
        self._raw_demo_cases: Dict[str, Dict[str, Any]] = {}
        self._load_demo_fixtures()

    def _load_demo_fixtures(self) -> None:
        """Loads Day 10, Day 18, and Day 19 sample fixtures into memory for quick demo execution."""
        fixture_paths = [
            Path("data/samples/day10/case_processing_cases.json"),
            Path("data/samples/day18/cross_case_cases.json"),
            Path("data/samples/day19/remediation_cases.json"),
        ]
        for fixtures_path in fixture_paths:
            if fixtures_path.exists():
                try:
                    with open(fixtures_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for tc in data.get("test_cases", []):
                            self._raw_demo_cases[tc["case_id"]] = tc
                except Exception:
                    pass

    def save_case(self, result: CaseProcessingResult) -> None:
        """Saves or updates a case result, evicting oldest entry if capacity is exceeded."""
        with self._lock:
            if result.case_id in self._cases:
                self._cases.move_to_end(result.case_id)
            else:
                if len(self._cases) >= self.max_capacity:
                    self._cases.popitem(last=False)
            self._cases[result.case_id] = result

    def get_case(self, case_id: str) -> Optional[CaseProcessingResult]:
        with self._lock:
            case = self._cases.get(case_id)
            if case:
                self._cases.move_to_end(case_id)
            return case

    def get_case_count(self) -> int:
        with self._lock:
            return len(self._cases)

    def list_demo_cases(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [c for c in self._raw_demo_cases.values() if str(c.get("case_id", "")).startswith("DAY10-")]

    def list_cases(self) -> List[CaseProcessingResult]:
        with self._lock:
            return list(self._cases.values())

    def get_demo_case_dict(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._raw_demo_cases.get(case_id)


class PersistentCaseStore(CaseStore):
    """Database-backed persistent case store."""

    def __init__(self, storage_service: Optional[StorageService] = None) -> None:
        self._lock = Lock()
        if storage_service is None:
            from backend.storage.service import get_storage_service as _global_storage
            storage_service = _global_storage()
        self.storage = storage_service
        self._raw_demo_cases: Dict[str, Dict[str, Any]] = {}
        self._load_demo_fixtures()

    def _load_demo_fixtures(self) -> None:
        """Loads Day 10, Day 18, and Day 19 sample fixtures into memory for quick demo execution."""
        fixture_paths = [
            Path("data/samples/day10/case_processing_cases.json"),
            Path("data/samples/day18/cross_case_cases.json"),
            Path("data/samples/day19/remediation_cases.json"),
        ]
        for fixtures_path in fixture_paths:
            if fixtures_path.exists():
                try:
                    with open(fixtures_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for tc in data.get("test_cases", []):
                            self._raw_demo_cases[tc["case_id"]] = tc
                except Exception:
                    pass

    def save_case(self, result: CaseProcessingResult) -> None:
        with self._lock:
            case_dict = self._raw_demo_cases.get(result.case_id) or {}
            self.storage.process_and_persist_case(
                case_result=result,
                raw_evidence_list=case_dict.get("evidence", []),
                raw_claims_list=case_dict.get("claims", []),
                raw_entities_list=case_dict.get("entities", []),
                raw_transactions_list=case_dict.get("transactions", []),
            )

    def get_case(self, case_id: str) -> Optional[CaseProcessingResult]:
        with self._lock:
            return self.storage.get_case_result(case_id)

    def get_case_count(self) -> int:
        with self._lock:
            stats = self.storage.get_storage_stats()
            return stats.get("cases", 0)

    def list_demo_cases(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [c for c in self._raw_demo_cases.values() if str(c.get("case_id", "")).startswith("DAY10-")]

    def list_cases(self) -> List[CaseProcessingResult]:
        with self._lock:
            records = self.storage.list_cases()
            results = []
            for r in records:
                c = self.storage.get_case_result(r.case_id)
                if c:
                    results.append(c)
            return results

    def get_demo_case_dict(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._raw_demo_cases.get(case_id)


# Stateful services live in the current user's workspace (see backend/workspace.py).
def _workspace():
    from backend.workspace import get_workspace
    return get_workspace()


def get_controller_service():
    return _workspace().controller


def get_review_service():
    return _workspace().review


def get_portfolio_service():
    return _workspace().portfolio


def get_cross_case_service():
    return _workspace().cross_case


def get_remediation_service():
    return _workspace().remediation


def get_storage_service() -> StorageService:
    return _workspace().storage


def get_case_service() -> CaseProcessingService:
    """Dependency provider for CaseProcessingService."""
    return _workspace().case_service


def get_case_store() -> CaseStore:
    """Dependency provider for the current user's CaseStore."""
    return _workspace().case_store
