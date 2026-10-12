"""Resolve branches, tags, and commits to immutable commit SHAs."""

from __future__ import annotations

from pathlib import Path
from sem_cli.repository.git_client import GitCommandError, run_git


class RevisionResolutionError(ValueError):
    """Raised when the requested revision or commit cannot be resolved."""


def resolve_revision(
    repository_path: Path,
    requested_ref: str | None = None,
) -> tuple[str, str | None, bool]:
    """Resolve a Git repository's current or requested ref to:

    (commit_sha, current_or_default_branch, is_shallow).
    """
    if requested_ref:
        try:
            # Check out or resolve the requested ref
            run_git(["checkout", requested_ref], cwd=repository_path)
        except GitCommandError as exc:
            raise RevisionResolutionError(
                f"Failed to resolve or checkout revision '{requested_ref}': {exc.stderr}"
            ) from exc

    try:
        # Full 40-character commit SHA
        commit_sha = run_git(["rev-parse", "HEAD"], cwd=repository_path)
        if len(commit_sha) != 40:
            raise RevisionResolutionError(f"Unexpected commit SHA length: '{commit_sha}'")
    except GitCommandError as exc:
        raise RevisionResolutionError(f"Failed to resolve HEAD commit: {exc.stderr}") from exc

    # Determine branch name if available
    branch_name: str | None = None
    try:
        current_branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repository_path)
        if current_branch and current_branch != "HEAD":
            branch_name = current_branch
        else:
            # Detached HEAD, check remote default branch
            try:
                remote_head = run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=repository_path)
                branch_name = remote_head.replace("refs/remotes/origin/", "").strip()
            except Exception:
                branch_name = None
    except Exception:
        branch_name = None

    # Determine if shallow clone
    is_shallow = False
    try:
        shallow_out = run_git(["rev-parse", "--is-shallow-repository"], cwd=repository_path)
        is_shallow = shallow_out.strip().lower() == "true"
    except Exception:
        is_shallow = (repository_path / ".git" / "shallow").is_file()

    return commit_sha, branch_name, is_shallow
