"""Integration tests for Git client and history mining on a real repository."""

from pathlib import Path
from sem_cli.services.history_service import mine_git_history


def test_mine_git_history(fixture_git_repo: Path):
    result = mine_git_history(fixture_git_repo, history_depth=50)

    # In fixture_git_repo we created 3 commits
    assert len(result.commits) == 3
    assert len(result.contributors) >= 1
    assert result.contributors[0].display_name == "Test Author"
    assert result.total_churn > 0

    # Check file histories
    assert "math_utils.py" in result.file_histories
    assert "service.py" in result.file_histories
    assert result.file_histories["service.py"].change_count >= 2  # Modified across commits
