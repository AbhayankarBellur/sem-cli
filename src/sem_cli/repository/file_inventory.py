"""File discovery, language classification, and test detection."""

from __future__ import annotations

import os
from pathlib import Path
from sem_cli.config.settings import AnalysisConfig
from sem_cli.repository.git_client import run_git
from sem_cli.repository.models import FileItem

LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "PowerShell",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
}

EXCLUDE_DIRS: set[str] = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "target",
    ".idea",
    ".vscode",
    "vendor",
}

GENERATED_INDICATORS: tuple[str, ...] = (
    ".min.",
    "bundle.",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Cargo.lock",
)


def is_test_file(rel_path: str) -> bool:
    """Check if the relative path indicates a test file."""
    p_lower = rel_path.lower().replace("\\", "/")
    parts = p_lower.split("/")
    filename = parts[-1]

    if any(part in ("test", "tests", "spec", "specs", "__tests__") for part in parts[:-1]):
        return True

    if filename.startswith("test_") or filename.endswith(("_test.py", "_spec.js", ".spec.js", ".test.js", ".spec.ts", ".test.ts", "_test.go")):
        return True

    return False


def is_generated_file(rel_path: str) -> bool:
    """Check if file matches known generated patterns."""
    filename = Path(rel_path).name.lower()
    return any(ind in filename for ind in GENERATED_INDICATORS)


def discover_files(workspace_path: Path, config: AnalysisConfig) -> list[FileItem]:
    """Discover, classify, and filter eligible files in repository."""
    max_size_bytes = int(config.max_file_size_mb * 1024 * 1024)
    file_items: list[FileItem] = []

    # First attempt: use git ls-files to get tracked files
    tracked_rel_paths: set[str] | None = None
    if (workspace_path / ".git").exists():
        try:
            out = run_git(["ls-files"], cwd=workspace_path)
            if out:
                tracked_rel_paths = {line.strip() for line in out.splitlines() if line.strip()}
        except Exception:
            tracked_rel_paths = None

    if tracked_rel_paths is not None:
        # Use git tracked files
        for rel_str in sorted(tracked_rel_paths):
            p = workspace_path / rel_str
            if not p.is_file():
                continue

            try:
                size = p.stat().st_size
            except OSError:
                continue

            if size > max_size_bytes:
                continue

            ext = p.suffix.lower()
            lang = LANGUAGE_EXTENSIONS.get(ext, "Other")
            test_flag = is_test_file(rel_str)
            gen_flag = is_generated_file(rel_str)

            if gen_flag and not config.include_generated:
                continue
            if test_flag and not config.include_tests:
                continue

            file_items.append(
                FileItem(
                    relative_path=rel_str.replace("\\", "/"),
                    absolute_path=p,
                    language=lang,
                    size_bytes=size,
                    is_test=test_flag,
                    is_generated=gen_flag,
                )
            )
    else:
        # Walk filesystem
        for root, dirs, files in os.walk(workspace_path, followlinks=config.follow_symlinks):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file_name in files:
                p = Path(root) / file_name
                try:
                    rel_p = p.relative_to(workspace_path).as_posix()
                    size = p.stat().st_size
                except (ValueError, OSError):
                    continue

                if size > max_size_bytes:
                    continue

                ext = p.suffix.lower()
                lang = LANGUAGE_EXTENSIONS.get(ext, "Other")
                test_flag = is_test_file(rel_p)
                gen_flag = is_generated_file(rel_p)

                if gen_flag and not config.include_generated:
                    continue
                if test_flag and not config.include_tests:
                    continue

                file_items.append(
                    FileItem(
                        relative_path=rel_p,
                        absolute_path=p,
                        language=lang,
                        size_bytes=size,
                        is_test=test_flag,
                        is_generated=gen_flag,
                    )
                )

    return file_items
