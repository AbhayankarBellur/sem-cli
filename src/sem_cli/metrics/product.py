"""Product and size metrics (LOC, SLOC, Comment Density, Test-to-Source ratio)."""

from __future__ import annotations

import re
from pathlib import Path
from sem_cli.metrics.schema import MetricResult
from sem_cli.repository.models import FileItem

ANALYZER_NAME = "sem-size-engine"
ANALYZER_VERSION = "1.0.0"
FORMULA_VERSION = "2026.1"


def count_lines_detailed(file_path: Path, language: str) -> tuple[int, int, int, int]:
    """Count (physical_loc, sloc, blank_lines, comment_lines) for a single file.

    Follows standard counting convention:
    - LOC: total physical lines
    - Blank: whitespace-only lines
    - Comments: single and multi-line comments
    - SLOC: lines with actual executable/declarative code
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0, 0, 0, 0

    if not content:
        return 0, 0, 0, 0

    lines = content.splitlines()
    loc = len(lines)
    blank_lines = 0
    comment_lines = 0
    sloc = 0

    # Determine comment syntax
    is_hash_comment = language in ("Python", "Shell", "PowerShell", "Ruby", "YAML", "TOML")
    is_slash_comment = language in ("JavaScript", "TypeScript", "JavaScript (React)", "TypeScript (React)", "Go", "Rust", "Java", "C", "C++", "C/C++ Header", "C++ Header", "C#", "PHP", "CSS", "SCSS", "Sass", "SQL")

    in_multiline_comment = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank_lines += 1
            continue

        if in_multiline_comment:
            comment_lines += 1
            if is_slash_comment and "*/" in stripped:
                in_multiline_comment = False
            elif is_hash_comment and ('"""' in stripped or "'''" in stripped):
                in_multiline_comment = False
            continue

        # Check start of multiline comment
        if is_slash_comment and stripped.startswith("/*"):
            comment_lines += 1
            if "*/" not in stripped[2:]:
                in_multiline_comment = True
            continue
        elif is_hash_comment and (stripped.startswith('"""') or stripped.startswith("'''")) and stripped.count('"""') != 2 and stripped.count("'''") != 2:
            comment_lines += 1
            in_multiline_comment = True
            continue

        # Single line comment
        if is_hash_comment and stripped.startswith("#"):
            comment_lines += 1
        elif is_slash_comment and (stripped.startswith("//") or stripped.startswith("--")):
            comment_lines += 1
        else:
            sloc += 1

    return loc, sloc, blank_lines, comment_lines


def compute_file_product_metrics(file_item: FileItem) -> list[MetricResult]:
    """Compute file-level product metrics."""
    loc, sloc, blank, comments = count_lines_detailed(file_item.absolute_path, file_item.language)
    comment_density = round(comments / max(sloc, 1), 4)

    results = [
        MetricResult(
            name="loc",
            category="product",
            value=float(loc),
            unit="lines",
            scope_type="file",
            scope_key=file_item.relative_path,
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Physical line count including comments and blanks.",
        ),
        MetricResult(
            name="sloc",
            category="product",
            value=float(sloc),
            unit="lines",
            scope_type="file",
            scope_key=file_item.relative_path,
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Source lines of code excluding comments and blank lines.",
        ),
        MetricResult(
            name="comment_density",
            category="product",
            value=float(comment_density),
            unit="ratio",
            scope_type="file",
            scope_key=file_item.relative_path,
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Ratio of comment lines to source lines.",
        ),
    ]
    return results


def compute_repository_product_metrics(
    files: list[FileItem],
    file_metrics: list[MetricResult],
) -> list[MetricResult]:
    """Aggregate repository-level product size and composition metrics."""
    total_loc = 0.0
    total_sloc = 0.0
    total_test_sloc = 0.0
    total_prod_sloc = 0.0
    file_count = len(files)

    test_file_lookup = {f.relative_path: f.is_test for f in files}

    file_slocs: list[float] = []

    for m in file_metrics:
        if m.scope_type == "file" and m.value is not None:
            if m.name == "loc":
                total_loc += m.value
            elif m.name == "sloc":
                total_sloc += m.value
                file_slocs.append(m.value)
                if test_file_lookup.get(m.scope_key, False):
                    total_test_sloc += m.value
                else:
                    total_prod_sloc += m.value

    avg_file_size = round(total_sloc / max(file_count, 1), 2)
    max_file_size = max(file_slocs) if file_slocs else 0.0

    test_to_source_ratio = (
        round(total_test_sloc / total_prod_sloc, 4)
        if total_prod_sloc > 0
        else (0.0 if total_test_sloc == 0 else 1.0)
    )

    results = [
        MetricResult(
            name="total_loc",
            category="product",
            value=float(total_loc),
            unit="lines",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Total physical lines across all tracked repository files.",
        ),
        MetricResult(
            name="total_sloc",
            category="product",
            value=float(total_sloc),
            unit="lines",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Total executable source lines across all tracked files.",
        ),
        MetricResult(
            name="file_count",
            category="product",
            value=float(file_count),
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Number of eligible source files.",
        ),
        MetricResult(
            name="avg_file_size_sloc",
            category="product",
            value=float(avg_file_size),
            unit="lines",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Average SLOC per file.",
        ),
        MetricResult(
            name="max_file_size_sloc",
            category="product",
            value=float(max_file_size),
            unit="lines",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Maximum SLOC in any single file.",
        ),
        MetricResult(
            name="test_to_source_ratio",
            category="product",
            value=float(test_to_source_ratio),
            unit="ratio",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Ratio of test SLOC to non-test production SLOC.",
        ),
    ]
    return results
