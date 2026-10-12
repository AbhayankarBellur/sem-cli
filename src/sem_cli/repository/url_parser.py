"""URL and path parsing, validation, and sanitization for Git repositories."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse


class InvalidRepositoryURLError(ValueError):
    """Raised when repository URL or path is invalid or unsafe."""


@dataclass(frozen=True)
class ParsedRepositoryTarget:
    original_target: str
    normalized_url: str
    display_name: str
    is_local_path: bool
    local_path: Path | None
    safe_clone_url: str  # URL with any sensitive credentials stripped


def parse_and_validate_target(target: str) -> ParsedRepositoryTarget:
    """Validate, sanitize, and normalize a repository target (Git URL or local directory)."""
    target = target.strip()
    if not target:
        raise InvalidRepositoryURLError("Repository target cannot be empty.")

    # Check if local filesystem path
    local_candidate = Path(target).expanduser().resolve()
    if local_candidate.exists() and (local_candidate.is_dir() or (local_candidate / ".git").exists()):
        # It's a local path
        display_name = local_candidate.name
        # Normalized form uses forward slashes
        norm_path = local_candidate.as_posix()
        return ParsedRepositoryTarget(
            original_target=target,
            normalized_url=f"file://{norm_path}",
            display_name=display_name,
            is_local_path=True,
            local_path=local_candidate,
            safe_clone_url=str(local_candidate),
        )

    # Check for file:// schema
    if target.startswith("file://"):
        raw_path = target[7:]
        # On Windows, file:///D:/...
        if raw_path.startswith("/") and len(raw_path) > 3 and raw_path[2] == ":":
            raw_path = raw_path[1:]
        candidate_path = Path(raw_path).resolve()
        display_name = candidate_path.name or "local-repo"
        return ParsedRepositoryTarget(
            original_target=target,
            normalized_url=f"file://{candidate_path.as_posix()}",
            display_name=display_name,
            is_local_path=True,
            local_path=candidate_path,
            safe_clone_url=str(candidate_path),
        )

    # Check for Git SSH format (e.g., git@github.com:owner/repo.git)
    ssh_match = re.match(r"^(?:[\w\.\-]+@)?([\w\.\-]+):([\w\.\-]+/[\w\.\-]+?)(?:\.git)?$", target)
    if ssh_match:
        host, repo_path = ssh_match.groups()
        display_name = repo_path.rstrip("/").split("/")[-1]
        normalized = f"git@{host}:{repo_path}.git"
        return ParsedRepositoryTarget(
            original_target=target,
            normalized_url=normalized,
            display_name=display_name,
            is_local_path=False,
            local_path=None,
            safe_clone_url=target,
        )

    # URL parse for HTTP/HTTPS/GIT/SSH protocols
    parsed = urlparse(target)
    if parsed.scheme in ("http", "https", "git", "ssh"):
        if not parsed.netloc:
            raise InvalidRepositoryURLError(f"Invalid repository URL format: '{target}'")

        # Sanitize credentials (strip username:password@)
        netloc = parsed.netloc
        if "@" in netloc:
            netloc = netloc.split("@")[-1]

        # Clean path
        path = parsed.path.rstrip("/")
        if not path:
            raise InvalidRepositoryURLError(f"Repository path is missing in URL: '{target}'")

        display_name = Path(path).name
        if display_name.endswith(".git"):
            display_name = display_name[:-4]

        # Normalized URL (without trailing .git inconsistency, no credentials)
        clean_path = path if path.endswith(".git") else f"{path}.git"
        safe_url = urlunparse((parsed.scheme, netloc, clean_path, "", "", ""))
        normalized_url = f"{parsed.scheme}://{netloc}{clean_path}"

        return ParsedRepositoryTarget(
            original_target=target,
            normalized_url=normalized_url,
            display_name=display_name,
            is_local_path=False,
            local_path=None,
            safe_clone_url=safe_url,
        )

    # If it's a relative path that doesn't exist yet, check if it's supposed to be a directory
    if Path(target).is_dir():
        cand = Path(target).resolve()
        return ParsedRepositoryTarget(
            original_target=target,
            normalized_url=f"file://{cand.as_posix()}",
            display_name=cand.name,
            is_local_path=True,
            local_path=cand,
            safe_clone_url=str(cand),
        )

    raise InvalidRepositoryURLError(
        f"Target '{target}' is neither an existing directory nor a supported Git URL "
        f"(http://, https://, git://, ssh://, git@host:owner/repo.git)."
    )
