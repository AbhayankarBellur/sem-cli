"""Data models for repository ingestion and metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class FileItem:
    relative_path: str
    absolute_path: Path
    language: str
    size_bytes: int
    is_test: bool
    is_generated: bool = False


@dataclass(frozen=True)
class RepositorySnapshot:
    run_id: str
    normalized_url: str
    display_name: str
    workspace_path: Path
    requested_ref: str | None
    commit_sha: str
    default_branch: str | None
    is_shallow: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    files: list[FileItem] = field(default_factory=list)


@dataclass(frozen=True)
class FileChangeInfo:
    commit_sha: str
    file_path: str
    change_type: str  # A (added), M (modified), D (deleted), R (renamed)
    lines_added: int
    lines_deleted: int


@dataclass(frozen=True)
class CommitInfo:
    commit_sha: str
    parents: list[str]
    author_name: str
    author_email: str
    author_date: str
    committer_date: str
    subject: str
    additions: int = 0
    deletions: int = 0
    files_changed_count: int = 0
    changes: list[FileChangeInfo] = field(default_factory=list)


@dataclass(frozen=True)
class ContributorInfo:
    identity_key: str  # Normalized name/email
    display_name: str
    email: str
    commit_count: int
    first_commit_date: str
    last_commit_date: str


@dataclass(frozen=True)
class RepositoryMetadata:
    total_commits: int
    total_contributors: int
    branches: list[str]
    tags: list[str]
    age_days: int
    first_commit_date: str | None
    last_commit_date: str | None
