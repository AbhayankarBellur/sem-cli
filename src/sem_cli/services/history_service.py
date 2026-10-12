"""Git history mining, code churn calculation, and change concentration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from sem_cli.metrics.schema import MetricResult
from sem_cli.repository.git_client import run_git
from sem_cli.repository.models import CommitInfo, ContributorInfo, FileChangeInfo

ANALYZER_NAME = "sem-history-engine"
ANALYZER_VERSION = "1.0.0"
FORMULA_VERSION = "2026.1"


@dataclass
class FileHistorySummary:
    file_path: str
    change_count: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    churn: int = 0
    last_modified_date: str | None = None
    first_seen_date: str | None = None


@dataclass
class HistoryMiningResult:
    commits: list[CommitInfo] = field(default_factory=list)
    contributors: list[ContributorInfo] = field(default_factory=list)
    file_histories: dict[str, FileHistorySummary] = field(default_factory=dict)
    total_churn: int = 0
    metrics: list[MetricResult] = field(default_factory=list)
    gini_concentration: float = 0.0
    top_churn_files: list[tuple[str, int, int]] = field(default_factory=list)  # (path, changes, churn)


def calculate_gini(values: list[float]) -> float:
    """Calculate Gini coefficient of inequality for an array of numbers (e.g. churn concentration).

    Returns 0.0 (completely equal distribution) to 1.0 (completely concentrated).
    """
    if not values or len(values) <= 1:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    total = sum(sorted_vals)
    if total == 0:
        return 0.0
    index = sum((2 * (i + 1) - n - 1) * sorted_vals[i] for i in range(n))
    return round(float(index / (n * total)), 4)


def mine_git_history(
    workspace_path: Path,
    history_depth: int = 1000,
) -> HistoryMiningResult:
    """Extract commits, numstat file changes, contributors, and churn metrics."""
    result = HistoryMiningResult()

    if not (workspace_path / ".git").exists():
        return result

    # Format: SHA | PARENTS | AUTHOR_NAME | AUTHOR_EMAIL | AUTHOR_DATE | SUBJECT
    delimiter = "---SEM_COMMIT---"
    log_format = f"{delimiter}%H|%P|%an|%ae|%cI|%s"

    try:
        cmd = [
            "log",
            f"-n{history_depth}",
            f"--format={log_format}",
            "--numstat",
        ]
        raw_output = run_git(cmd, cwd=workspace_path, timeout=180)
    except Exception:
        return result

    raw_chunks = raw_output.split(delimiter)

    contributor_stats: dict[str, dict] = defaultdict(lambda: {
        "display_name": "",
        "email": "",
        "count": 0,
        "first_date": None,
        "last_date": None,
    })

    for chunk in raw_chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        lines = chunk.splitlines()
        header = lines[0].strip()
        header_parts = header.split("|", 5)
        if len(header_parts) < 6:
            continue

        commit_sha, parents_str, aname, aemail, cdate, subject = header_parts
        parents = [p for p in parents_str.split() if p]

        # Contributor identity normalization: group by lowercase email or name
        identity_key = (aemail.lower().strip() if aemail else aname.lower().strip())
        c_stat = contributor_stats[identity_key]
        c_stat["display_name"] = aname
        c_stat["email"] = aemail
        c_stat["count"] += 1
        if not c_stat["last_date"]:
            c_stat["last_date"] = cdate
        c_stat["first_date"] = cdate

        commit_additions = 0
        commit_deletions = 0
        changes: list[FileChangeInfo] = []

        # Parse numstat lines
        for numstat_line in lines[1:]:
            parts = numstat_line.split("\t")
            if len(parts) >= 3:
                raw_add, raw_del, raw_path = parts[0].strip(), parts[1].strip(), parts[2].strip()
                # Binary files show '-'
                added = int(raw_add) if raw_add.isdigit() else 0
                deleted = int(raw_del) if raw_del.isdigit() else 0
                # Handle rename syntax 'old => new' or '{old => new}'
                clean_path = raw_path.split(" => ")[-1].replace("}", "").strip()

                commit_additions += added
                commit_deletions += deleted

                c_info = FileChangeInfo(
                    commit_sha=commit_sha,
                    file_path=clean_path,
                    change_type="M",
                    lines_added=added,
                    lines_deleted=deleted,
                )
                changes.append(c_info)

                # Update file history
                f_hist = result.file_histories.setdefault(clean_path, FileHistorySummary(clean_path))
                f_hist.change_count += 1
                f_hist.lines_added += added
                f_hist.lines_deleted += deleted
                f_hist.churn += (added + deleted)
                if not f_hist.last_modified_date:
                    f_hist.last_modified_date = cdate
                f_hist.first_seen_date = cdate

        c_info_obj = CommitInfo(
            commit_sha=commit_sha,
            parents=parents,
            author_name=aname,
            author_email=aemail,
            author_date=cdate,
            committer_date=cdate,
            subject=subject,
            additions=commit_additions,
            deletions=commit_deletions,
            files_changed_count=len(changes),
            changes=changes,
        )
        result.commits.append(c_info_obj)
        result.total_churn += (commit_additions + commit_deletions)

    # Build contributors list
    for key, val in contributor_stats.items():
        result.contributors.append(
            ContributorInfo(
                identity_key=key,
                display_name=val["display_name"],
                email=val["email"],
                commit_count=val["count"],
                first_commit_date=val["first_date"] or "",
                last_commit_date=val["last_date"] or "",
            )
        )
    result.contributors.sort(key=lambda c: c.commit_count, reverse=True)

    # Churn concentration (Gini coefficient over file churns)
    file_churns = [f.churn for f in result.file_histories.values()]
    result.gini_concentration = calculate_gini([float(c) for c in file_churns])

    # Top churn files
    sorted_files = sorted(result.file_histories.values(), key=lambda x: (x.churn, x.change_count), reverse=True)
    result.top_churn_files = [(f.file_path, f.change_count, f.churn) for f in sorted_files[:20]]

    # Process metrics
    total_commits = float(len(result.commits))
    total_contributors = float(len(result.contributors))
    total_churn_val = float(result.total_churn)

    result.metrics = [
        MetricResult(
            name="commit_count",
            category="process",
            value=total_commits,
            unit="commits",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Number of commits mined in the selected history window.",
        ),
        MetricResult(
            name="contributor_count",
            category="process",
            value=total_contributors,
            unit="authors",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Distinct contributors normalized by email identity.",
        ),
        MetricResult(
            name="total_churn",
            category="process",
            value=total_churn_val,
            unit="lines",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Sum of lines added and deleted over analyzed history.",
        ),
        MetricResult(
            name="churn_gini_concentration",
            category="process",
            value=float(result.gini_concentration),
            unit="gini",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Gini inequality coefficient of churn distribution across files (0=equal, 1=concentrated).",
        ),
    ]

    # File-level process metrics
    for fh in result.file_histories.values():
        result.metrics.extend([
            MetricResult(
                name="change_frequency",
                category="process",
                value=float(fh.change_count),
                unit="commits",
                scope_type="file",
                scope_key=fh.file_path,
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation="Number of historical commits modifying this file.",
            ),
            MetricResult(
                name="churn",
                category="process",
                value=float(fh.churn),
                unit="lines",
                scope_type="file",
                scope_key=fh.file_path,
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation="Lines added + deleted for this file.",
            ),
        ])

    return result
