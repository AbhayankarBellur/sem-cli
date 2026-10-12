"""Safe Git CLI wrapper executing subprocess commands."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    """Base exception for Git operations."""


class GitNotFoundError(GitError):
    """Git executable is not installed or not in PATH."""


class GitTimeoutError(GitError):
    """Git command exceeded timeout limit."""


class GitAuthError(GitError):
    """Git authentication failure."""


class GitCommandError(GitError):
    """Git command failed with non-zero exit code."""

    def __init__(self, message: str, returncode: int, command: list[str], stderr: str) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.command = command
        self.stderr = stderr


def _sanitize_message(text: str) -> str:
    """Redact tokens, credentials, and passwords from command output/errors."""
    # Redact http(s)://user:password@
    redacted = re.sub(r"://([^:@\s]+):([^@\s]+)@", r"://\1:***@", text)
    # Redact common token patterns (ghp_, gho_, pat_, glpat-)
    redacted = re.sub(r"(gh[pousr]_[A-Za-z0-9_]{16,})", "[REDACTED_TOKEN]", redacted)
    redacted = re.sub(r"(glpat-[A-Za-z0-9\-]{16,})", "[REDACTED_TOKEN]", redacted)
    return redacted


def is_git_installed() -> bool:
    """Check if git executable is available in PATH."""
    return shutil.which("git") is not None


def get_git_version() -> str:
    """Return the installed Git version string."""
    try:
        out = run_git(["--version"], timeout=10)
        return out.strip()
    except Exception as exc:
        raise GitNotFoundError("Git is not found or could not be executed.") from exc


def run_git(
    args: list[str],
    *,
    cwd: Path | str | None = None,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> str:
    """Execute a Git CLI command safely with argument list, timeout, and output redaction.

    Returns the stripped stdout if successful.
    Raises GitCommandError, GitAuthError, GitTimeoutError, or GitNotFoundError.
    """
    if not is_git_installed():
        raise GitNotFoundError("Git is not installed or not available in the system PATH.")

    working_dir = str(cwd) if cwd is not None else None
    command = ["git", *args]

    try:
        result = subprocess.run(
            command,
            cwd=working_dir,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        safe_cmd = _sanitize_message(" ".join(command))
        raise GitTimeoutError(f"Git command timed out after {timeout}s: '{safe_cmd}'") from exc
    except OSError as exc:
        raise GitNotFoundError("Failed to execute Git process.") from exc

    if result.returncode != 0:
        clean_stderr = _sanitize_message(result.stderr.strip())
        clean_stdout = _sanitize_message(result.stdout.strip())
        err_msg = clean_stderr or clean_stdout or f"Git exited with code {result.returncode}"

        # Classify authentication failure
        lower_err = err_msg.lower()
        if any(auth_kw in lower_err for kw in ("authentication failed", "permission denied (publickey)", "could not read username", "terminal prompts disabled")):
            raise GitAuthError(f"Git authentication rejected: {err_msg}")

        raise GitCommandError(
            message=f"Git command failed: {err_msg}",
            returncode=result.returncode,
            command=[_sanitize_message(arg) for arg in command],
            stderr=clean_stderr,
        )

    return result.stdout.strip()
