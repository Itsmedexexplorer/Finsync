"""Central configuration management for VERITY.

Provides typed, environment-driven configuration with safe defaults for production
and local demonstration environments.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Loads KEY=VALUE lines from .env without overriding real environment variables."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)


if "pytest" not in __import__("sys").modules:
    _load_dotenv()


class Settings(BaseModel):
    """Global application settings and security limits."""
    
    # Environment & Server
    env: str = Field(
        default_factory=lambda: os.getenv("VERITY_ENV", "development"),
        description="Deployment environment ('development', 'staging', 'production', 'test')"
    )
    host: str = Field(
        default_factory=lambda: os.getenv("VERITY_HOST", "0.0.0.0"),
        description="Server host address"
    )
    port: int = Field(
        default_factory=lambda: int(os.getenv("VERITY_PORT", "8000")),
        description="Server port"
    )
    api_version: str = Field(
        default_factory=lambda: os.getenv("VERITY_API_VERSION", "0.1.0-day12"),
        description="API version tag"
    )
    enable_docs: bool = Field(
        default_factory=lambda: os.getenv("VERITY_ENABLE_DOCS", "true").lower() in ("true", "1", "yes"),
        description="Enable Swagger/OpenAPI docs (/docs and /redoc)"
    )

    enable_demo: bool = Field(
        default_factory=lambda: os.getenv("VERITY_ENABLE_DEMO", "false").lower() in ("true", "1", "yes"),
        description="Expose the built-in demo scenarios and benchmark endpoints (off for real users)"
    )

    # Security & Resource Limits
    max_upload_mb: float = Field(
        default_factory=lambda: float(os.getenv("VERITY_MAX_UPLOAD_MB", "15.0")),
        description="Maximum single file upload size in megabytes"
    )
    max_text_length: int = Field(
        default_factory=lambda: int(os.getenv("VERITY_MAX_TEXT_LENGTH", "250000")),
        description="Maximum length for raw text/chat exports in characters"
    )
    max_files_per_case: int = Field(
        default_factory=lambda: int(os.getenv("VERITY_MAX_FILES_PER_CASE", "20")),
        description="Maximum files allowed in a single case submission"
    )
    max_evidence_items: int = Field(
        default_factory=lambda: int(os.getenv("VERITY_MAX_EVIDENCE_ITEMS", "100")),
        description="Maximum evidence items allowed per case"
    )
    max_claims_per_case: int = Field(
        default_factory=lambda: int(os.getenv("VERITY_MAX_CLAIMS_PER_CASE", "200")),
        description="Maximum claim objects allowed per case"
    )
    max_transactions_per_case: int = Field(
        default_factory=lambda: int(os.getenv("VERITY_MAX_TRANSACTIONS_PER_CASE", "500")),
        description="Maximum ledger transactions allowed per case"
    )
    max_cases_in_memory: int = Field(
        default_factory=lambda: int(os.getenv("VERITY_MAX_CASES_IN_MEMORY", "1000")),
        description="Capacity of the in-memory demo case store before FIFO eviction"
    )

    # CORS Configuration
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "VERITY_CORS_ORIGINS",
                "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173"
            ).split(",")
            if origin.strip()
        ],
        description="Allowed CORS origins"
    )

    # Logging
    log_level: str = Field(
        default_factory=lambda: os.getenv("VERITY_LOG_LEVEL", "INFO").upper(),
        description="Application logging level"
    )

    # Benchmark Path
    benchmark_path: str = Field(
        default_factory=lambda: os.getenv("VERITY_BENCHMARK_PATH", "data/benchmark/ground_truth_cases.json"),
        description="Relative or absolute path to the ground-truth benchmark JSON"
    )

    # AI Extraction Provider (Day 17)
    ai_provider_type: str = Field(
        default_factory=lambda: os.getenv("VERITY_AI_PROVIDER", "MOCK"),
        description="AI extraction provider type: MOCK, GEMINI, OPENAI_COMPATIBLE"
    )
    ai_model_name: str = Field(
        default_factory=lambda: os.getenv("VERITY_AI_MODEL", "gemini-3.6-flash"),
        description="AI model name for extraction"
    )
    ai_api_key_env_var: str = Field(
        default_factory=lambda: os.getenv("VERITY_AI_API_KEY_ENV_VAR", "GEMINI_API_KEY"),
        description="Environment variable name containing the AI API key"
    )
    ai_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("VERITY_AI_TIMEOUT", "30")),
        description="AI provider request timeout in seconds"
    )

    @property
    def max_upload_bytes(self) -> int:
        """Returns max upload limit in bytes."""
        return int(self.max_upload_mb * 1024 * 1024)

    @property
    def is_production(self) -> bool:
        """Returns True if running in production mode."""
        return self.env.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    """Returns cached singleton Settings instance."""
    return Settings()
