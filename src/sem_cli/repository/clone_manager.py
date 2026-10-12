"""Clone lifecycle management and disposable workspaces."""

from __future__ import annotations

import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sem_cli.config.settings import RepositoryConfig
from sem_cli.repository.git_client import GitCommandError, run_git
from sem_cli.repository.models import RepositorySnapshot
from sem_cli.repository.revision_resolver import resolve_revision
from sem_cli.repository.url_parser import ParsedRepositoryTarget


class CloneError(RuntimeError):
    """Raised when repository cloning fails."""


class CloneManager:
    """Manages cloning, revision checking, and workspace cleanup."""

    def __init__(self, config: RepositoryConfig, root_workspace_dir: Path | None = None) -> None:
        self.config = config
        self.root_workspace_dir = root_workspace_dir

    def prepare_snapshot(
        self,
        target: ParsedRepositoryTarget,
        *,
        requested_ref: str | None = None,
        history_depth: int | None = None,
        run_id: str | None = None,
    ) -> tuple[RepositorySnapshot, Path, bool]:
        """Prepare repository workspace.

        Returns (snapshot, workspace_path, is_temporary).
        If is_temporary is True, workspace_path must be deleted on completion.
        """
        run_id = run_id or uuid.uuid4().hex[:12]
        depth = history_depth or self.config.history_depth

        # For a local repository without a requested ref change, we can analyze in-place or clone locally.
        # If no ref change requested and local path exists:
        if target.is_local_path and target.local_path and (target.local_path / ".git").is_dir() and not requested_ref:
            commit_sha, branch_name, is_shallow = resolve_revision(target.local_path, requested_ref=None)
            snapshot = RepositorySnapshot(
                run_id=run_id,
                normalized_url=target.normalized_url,
                display_name=target.display_name,
                workspace_path=target.local_path,
                requested_ref=requested_ref,
                commit_sha=commit_sha,
                default_branch=branch_name,
                is_shallow=is_shallow,
            )
            return snapshot, target.local_path, False

        # Otherwise, clone into managed workspace
        if self.root_workspace_dir:
            self.root_workspace_dir.mkdir(parents=True, exist_ok=True)
            workspace = Path(tempfile.mkdtemp(prefix=f"sem-{run_id}-", dir=self.root_workspace_dir))
        else:
            workspace = Path(tempfile.mkdtemp(prefix=f"sem-{run_id}-"))

        repo_path = workspace / "repo"

        try:
            clone_args = ["clone", "--no-tags"]
            if depth and depth > 0:
                clone_args.extend(["--depth", str(depth)])
            if requested_ref:
                clone_args.extend(["--branch", requested_ref])

            clone_args.extend([target.safe_clone_url, str(repo_path)])

            try:
                run_git(clone_args, timeout=self.config.clone_timeout_seconds)
            except GitCommandError as exc:
                # If --branch failed (e.g. requested_ref was a commit SHA), retry without --branch and checkout later
                if requested_ref and "not found" in exc.stderr.lower():
                    if repo_path.exists():
                        shutil.rmtree(repo_path, ignore_errors=True)
                    fallback_args = ["clone", "--no-tags"]
                    if depth and depth > 0:
                        fallback_args.extend(["--depth", str(depth)])
                    fallback_args.extend([target.safe_clone_url, str(repo_path)])
                    run_git(fallback_args, timeout=self.config.clone_timeout_seconds)
                else:
                    raise

            # Resolve commit SHA and checkout ref if needed
            commit_sha, branch_name, is_shallow = resolve_revision(repo_path, requested_ref)

            snapshot = RepositorySnapshot(
                run_id=run_id,
                normalized_url=target.normalized_url,
                display_name=target.display_name,
                workspace_path=repo_path,
                requested_ref=requested_ref,
                commit_sha=commit_sha,
                default_branch=branch_name,
                is_shallow=is_shallow,
            )
            return snapshot, workspace, True

        except Exception as exc:
            # Clean up partial directory on failure
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)
            raise CloneError(f"Failed to clone repository: {exc}") from exc


@contextmanager
def managed_workspace(
    manager: CloneManager,
    target: ParsedRepositoryTarget,
    *,
    requested_ref: str | None = None,
    history_depth: int | None = None,
    run_id: str | None = None,
    retain_clone: bool = False,
) -> Generator[RepositorySnapshot, None, None]:
    """Context manager for preparing and safely cleaning up workspace."""
    snapshot, workspace_path, is_temp = manager.prepare_snapshot(
        target,
        requested_ref=requested_ref,
        history_depth=history_depth,
        run_id=run_id,
    )
    try:
        yield snapshot
    finally:
        if is_temp and not retain_clone:
            # Safely delete workspace directory
            # On Windows git objects might be read-only, handle chmod
            def _remove_readonly(func, path, exc_info):
                import os, stat
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass

            shutil.rmtree(workspace_path, onerror=_remove_readonly, ignore_errors=True)
