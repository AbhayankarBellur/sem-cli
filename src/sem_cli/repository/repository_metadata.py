"""Extract high-level Git repository metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from sem_cli.repository.git_client import run_git
from sem_cli.repository.models import RepositoryMetadata


def get_repository_metadata(workspace_path: Path) -> RepositoryMetadata:
    """Extract branches, tags, age, and commit count from repository."""
    # Branches
    branches: list[str] = []
    try:
        b_out = run_git(["branch", "-a", "--format=%(refname:short)"], cwd=workspace_path)
        branches = [b.strip() for b in b_out.splitlines() if b.strip()]
    except Exception:
        pass

    # Tags
    tags: list[str] = []
    try:
        t_out = run_git(["tag", "-l", "--sort=-creatordate"], cwd=workspace_path)
        tags = [t.strip() for t in t_out.splitlines() if t.strip()]
    except Exception:
        pass

    # Commit count
    total_commits = 0
    try:
        c_out = run_git(["rev-list", "--count", "HEAD"], cwd=workspace_path)
        total_commits = int(c_out.strip())
    except Exception:
        pass

    # Total unique contributors
    contributors: set[str] = set()
    try:
        auth_out = run_git(["log", "--format=%an <%ae>"], cwd=workspace_path)
        for line in auth_out.splitlines():
            if line.strip():
                contributors.add(line.strip().lower())
    except Exception:
        pass

    # First and last commit dates
    first_commit_date: str | None = None
    last_commit_date: str | None = None
    age_days = 0

    try:
        last_date_str = run_git(["log", "-1", "--format=%cI"], cwd=workspace_path).strip()
        last_commit_date = last_date_str

        # First commit
        first_date_str = run_git(["log", "--reverse", "-1", "--format=%cI"], cwd=workspace_path).strip()
        first_commit_date = first_date_str

        if first_commit_date and last_commit_date:
            d_first = datetime.fromisoformat(first_commit_date)
            d_last = datetime.fromisoformat(last_commit_date)
            age_days = max(0, (d_last - d_first).days)
    except Exception:
        pass

    return RepositoryMetadata(
        total_commits=total_commits,
        total_contributors=len(contributors),
        branches=branches,
        tags=tags,
        age_days=age_days,
        first_commit_date=first_commit_date,
        last_commit_date=last_commit_date,
    )
