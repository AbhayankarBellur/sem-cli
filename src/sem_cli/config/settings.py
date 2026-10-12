"""Configuration and settings manager for sem-cli."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AnalysisConfig:
    default_profile: str = "full"
    history_depth: int = 1000
    include_tests: bool = True
    include_generated: bool = False
    follow_symlinks: bool = False
    max_file_size_mb: float = 10.0


@dataclass
class RepositoryConfig:
    clone_timeout_seconds: int = 600
    max_repository_size_mb: int = 1000
    max_files: int = 100000
    retain_clone: bool = False
    cache_enabled: bool = False


@dataclass
class MetricsConfig:
    complexity_threshold: int = 10
    hotspot_window_days: int = 90


@dataclass
class SecurityConfig:
    enabled: bool = True
    scan_secrets: bool = True
    scan_dependencies: bool = True
    redact_secrets: bool = True


@dataclass
class AIConfig:
    enabled: bool = False
    provider: str = "gemini"
    send_source_code: bool = False
    model: str = "gemini-2.5-flash"
    api_key: str | None = None


@dataclass
class ReportingConfig:
    default_format: str = "markdown"


@dataclass
class AppConfig:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("SEM_DATA_DIR", Path.home() / ".sem-cli")).expanduser())
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    repository: RepositoryConfig = field(default_factory=RepositoryConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)

    def ensure_directories(self) -> None:
        """Create necessary application directories."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "workspaces").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "reports").mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "sem_data.db"


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration from file and environment variables."""
    cfg = AppConfig()

    search_paths = [
        config_path,
        Path("config/default.toml"),
        Path.home() / ".sem-cli" / "config.toml",
    ]

    for p in search_paths:
        if p and p.is_file():
            try:
                with open(p, "rb") as f:
                    data = tomllib.load(f)
                _apply_dict_to_config(cfg, data)
                break
            except Exception:
                pass

    # Apply environment variable overrides
    if "GEMINI_API_KEY" in os.environ:
        cfg.ai.api_key = os.environ["GEMINI_API_KEY"]
    if os.environ.get("SEM_AI_ENABLED", "").lower() in ("true", "1", "yes"):
        cfg.ai.enabled = True
    elif os.environ.get("SEM_AI_ENABLED", "").lower() in ("false", "0", "no"):
        cfg.ai.enabled = False

    if "SEM_DATA_DIR" in os.environ:
        cfg.data_dir = Path(os.environ["SEM_DATA_DIR"]).expanduser()

    cfg.ensure_directories()
    return cfg


def _apply_dict_to_config(cfg: AppConfig, data: dict) -> None:
    if "analysis" in data:
        a = data["analysis"]
        cfg.analysis.default_profile = a.get("default_profile", cfg.analysis.default_profile)
        cfg.analysis.history_depth = int(a.get("history_depth", cfg.analysis.history_depth))
        cfg.analysis.include_tests = bool(a.get("include_tests", cfg.analysis.include_tests))
        cfg.analysis.include_generated = bool(a.get("include_generated", cfg.analysis.include_generated))
        cfg.analysis.follow_symlinks = bool(a.get("follow_symlinks", cfg.analysis.follow_symlinks))
        cfg.analysis.max_file_size_mb = float(a.get("max_file_size_mb", cfg.analysis.max_file_size_mb))

    if "repository" in data:
        r = data["repository"]
        cfg.repository.clone_timeout_seconds = int(r.get("clone_timeout_seconds", cfg.repository.clone_timeout_seconds))
        cfg.repository.max_repository_size_mb = int(r.get("max_repository_size_mb", cfg.repository.max_repository_size_mb))
        cfg.repository.max_files = int(r.get("max_files", cfg.repository.max_files))
        cfg.repository.retain_clone = bool(r.get("retain_clone", cfg.repository.retain_clone))
        cfg.repository.cache_enabled = bool(r.get("cache_enabled", cfg.repository.cache_enabled))

    if "metrics" in data:
        m = data["metrics"]
        cfg.metrics.complexity_threshold = int(m.get("complexity_threshold", cfg.metrics.complexity_threshold))
        cfg.metrics.hotspot_window_days = int(m.get("hotspot_window_days", cfg.metrics.hotspot_window_days))

    if "security" in data:
        s = data["security"]
        cfg.security.enabled = bool(s.get("enabled", cfg.security.enabled))
        cfg.security.scan_secrets = bool(s.get("scan_secrets", cfg.security.scan_secrets))
        cfg.security.scan_dependencies = bool(s.get("scan_dependencies", cfg.security.scan_dependencies))
        cfg.security.redact_secrets = bool(s.get("redact_secrets", cfg.security.redact_secrets))

    if "ai" in data:
        ai = data["ai"]
        cfg.ai.enabled = bool(ai.get("enabled", cfg.ai.enabled))
        cfg.ai.provider = str(ai.get("provider", cfg.ai.provider))
        cfg.ai.send_source_code = bool(ai.get("send_source_code", cfg.ai.send_source_code))
        cfg.ai.model = str(ai.get("model", cfg.ai.model))

    if "reporting" in data:
        rep = data["reporting"]
        cfg.reporting.default_format = str(rep.get("default_format", cfg.reporting.default_format))
