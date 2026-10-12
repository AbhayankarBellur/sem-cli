"""Unit tests for URL and repository target parser."""

import pytest
from pathlib import Path
from sem_cli.repository.url_parser import (
    InvalidRepositoryURLError,
    parse_and_validate_target,
)


def test_parse_local_directory(tmp_path: Path):
    d = tmp_path / "my_repo"
    d.mkdir()
    res = parse_and_validate_target(str(d))
    assert res.is_local_path is True
    assert res.display_name == "my_repo"
    assert res.normalized_url.startswith("file://")


def test_parse_https_github_url():
    url = "https://github.com/torvalds/linux.git"
    res = parse_and_validate_target(url)
    assert res.is_local_path is False
    assert res.display_name == "linux"
    assert res.normalized_url == "https://github.com/torvalds/linux.git"


def test_parse_https_url_strips_credentials():
    url = "https://myuser:ghp_1234567890abcdef@github.com/org/secret-service.git"
    res = parse_and_validate_target(url)
    assert "ghp_" not in res.normalized_url
    assert "myuser" not in res.normalized_url
    assert res.normalized_url == "https://github.com/org/secret-service.git"
    assert "ghp_" not in res.safe_clone_url


def test_parse_ssh_url():
    url = "git@github.com:facebook/react.git"
    res = parse_and_validate_target(url)
    assert res.is_local_path is False
    assert res.display_name == "react"
    assert res.normalized_url == "git@github.com:facebook/react.git"


def test_invalid_target_empty():
    with pytest.raises(InvalidRepositoryURLError):
        parse_and_validate_target("")


def test_invalid_target_unsupported():
    with pytest.raises(InvalidRepositoryURLError):
        parse_and_validate_target("ftp://ftp.example.com/repo")
