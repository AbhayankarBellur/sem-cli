"""Repository ingestion, cloning, metadata, and git client package."""

from sem_cli.repository.models import (
    CommitInfo,
    ContributorInfo,
    FileChangeInfo,
    FileItem,
    RepositoryMetadata,
    RepositorySnapshot,
)
from sem_cli.repository.url_parser import (
    InvalidRepositoryURLError,
    ParsedRepositoryTarget,
    parse_and_validate_target,
)
from sem_cli.repository.git_client import (
    GitAuthError,
    GitCommandError,
    GitError,
    GitNotFoundError,
    GitTimeoutError,
    get_git_version,
    is_git_installed,
    run_git,
)
from sem_cli.repository.clone_manager import CloneError, CloneManager, managed_workspace
from sem_cli.repository.revision_resolver import RevisionResolutionError, resolve_revision
from sem_cli.repository.file_inventory import discover_files
from sem_cli.repository.repository_metadata import get_repository_metadata

__all__ = [
    "CommitInfo",
    "ContributorInfo",
    "FileChangeInfo",
    "FileItem",
    "RepositoryMetadata",
    "RepositorySnapshot",
    "InvalidRepositoryURLError",
    "ParsedRepositoryTarget",
    "parse_and_validate_target",
    "GitAuthError",
    "GitCommandError",
    "GitError",
    "GitNotFoundError",
    "GitTimeoutError",
    "get_git_version",
    "is_git_installed",
    "run_git",
    "CloneError",
    "CloneManager",
    "managed_workspace",
    "RevisionResolutionError",
    "resolve_revision",
    "discover_files",
    "get_repository_metadata",
]
