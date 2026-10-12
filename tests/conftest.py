"""Pytest fixtures and test repository generator."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from sem_cli.config.settings import AppConfig
from sem_cli.persistence.repositories import RepositoryDatabase


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Provide a temporary SQLite database path."""
    return tmp_path / "test_sem_data.db"


@pytest.fixture
def test_db(temp_db_path: Path) -> RepositoryDatabase:
    """Initialize a test database."""
    return RepositoryDatabase(temp_db_path)


@pytest.fixture
def test_config(tmp_path: Path, temp_db_path: Path) -> AppConfig:
    """Provide an AppConfig pointing to temporary paths."""
    cfg = AppConfig(data_dir=tmp_path)
    cfg.ensure_directories()
    return cfg


@pytest.fixture
def fixture_git_repo(tmp_path: Path) -> Path:
    """Create a controlled local Git repository with known commits and files."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )

    # Init repo
    git("init", "-b", "main")
    git("config", "user.name", "Test Author")
    git("config", "user.email", "author@example.com")

    # Commit 1: Initial files
    math_py = repo_dir / "math_utils.py"
    math_py.write_text(
        '"""Math utilities."""\n'
        '\n'
        'def add(a: int, b: int) -> int:\n'
        '    # Simple addition\n'
        '    return a + b\n'
        '\n'
        'def complex_calc(x: int) -> int:\n'
        '    res = 0\n'
        '    if x > 10:\n'
        '        res += 10\n'
        '    elif x > 5:\n'
        '        res += 5\n'
        '    else:\n'
        '        res += 1\n'
        '    for i in range(x):\n'
        '        if i % 2 == 0:\n'
        '            res += i\n'
        '    return res\n',
        encoding="utf-8",
    )

    test_math_py = repo_dir / "test_math_utils.py"
    test_math_py.write_text(
        'from math_utils import add\n'
        '\n'
        'def test_add():\n'
        '    assert add(1, 2) == 3\n',
        encoding="utf-8",
    )

    git("add", ".")
    git("commit", "-m", "Initial commit: math_utils and tests")

    # Commit 2: Add service with classes and a simulated finding
    service_py = repo_dir / "service.py"
    service_py.write_text(
        'import os\n'
        'import math_utils\n'
        '\n'
        'class PaymentService:\n'
        '    def __init__(self, key: str):\n'
        '        self.key = key\n'
        '        self.balance = 0\n'
        '\n'
        '    def charge(self, amount: int) -> bool:\n'
        '        if amount <= 0:\n'
        '            return False\n'
        '        self.balance += amount\n'
        '        return True\n'
        '\n'
        '    def refund(self, amount: int) -> bool:\n'
        '        if self.balance >= amount:\n'
        '            self.balance -= amount\n'
        '            return True\n'
        '        return False\n'
        '\n'
        'def run_eval(user_input: str):\n'
        '    eval(user_input)\n',
        encoding="utf-8",
    )

    req_txt = repo_dir / "requirements.txt"
    req_txt.write_text("requests==2.31.0\npydantic>=2.0.0\nfake-pkg\n", encoding="utf-8")

    git("add", ".")
    git("commit", "-m", "Add PaymentService and dependencies")

    # Commit 3: Churn on service.py
    service_py.write_text(
        service_py.read_text(encoding="utf-8") + "\n# Extra update for churn\n",
        encoding="utf-8",
    )
    git("add", "service.py")
    git("commit", "-m", "Minor update to service.py")

    return repo_dir
