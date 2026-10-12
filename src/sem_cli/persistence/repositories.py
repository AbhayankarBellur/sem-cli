"""Data access repository for SQLite persistence and snapshot comparison."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from sem_cli.analyzers.dependency_analyzer import DiscoveredDependency
from sem_cli.metrics.schema import Finding, MetricResult
from sem_cli.persistence.database import get_db_connection, initialize_database
from sem_cli.repository.models import CommitInfo


class RepositoryDatabase:
    """Encapsulates all SQLite persistence queries and snapshot operations."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        initialize_database(self.db_path)

    def get_or_create_repository(self, normalized_url: str, display_name: str) -> int:
        with get_db_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT id FROM repositories WHERE normalized_url = ?",
                (normalized_url,),
            ).fetchone()
            if row:
                return row["id"]
            cursor = conn.execute(
                "INSERT INTO repositories (normalized_url, display_name) VALUES (?, ?)",
                (normalized_url, display_name),
            )
            conn.commit()
            return cursor.lastrowid

    def create_analysis_run(
        self,
        run_id: str,
        repository_id: int,
        requested_ref: str | None,
        commit_sha: str,
        profile: str,
        tool_version: str,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO analysis_runs (
                    id, repository_id, requested_ref, commit_sha,
                    status, profile, started_at, tool_version
                ) VALUES (?, ?, ?, ?, 'running', ?, ?, ?)
                """,
                (run_id, repository_id, requested_ref, commit_sha, profile, now_iso, tool_version),
            )
            conn.commit()

    def update_run_status(
        self,
        run_id: str,
        status: str,
        error_code: str | None = None,
        error_summary: str | None = None,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE analysis_runs
                SET status = ?, completed_at = ?, error_code = ?, error_summary = ?
                WHERE id = ?
                """,
                (status, now_iso, error_code, error_summary, run_id),
            )
            conn.commit()

    def save_metric_values(self, run_id: str, metrics: list[MetricResult]) -> None:
        if not metrics:
            return
        with get_db_connection(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO metric_values (
                    run_id, name, category, value, unit, scope_type,
                    scope_key, status, analyzer, analyzer_version,
                    formula_version, explanation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        m.name,
                        m.category,
                        m.value,
                        m.unit,
                        m.scope_type,
                        m.scope_key,
                        m.status,
                        m.analyzer,
                        m.analyzer_version,
                        m.formula_version,
                        m.explanation,
                    )
                    for m in metrics
                ],
            )
            conn.commit()

    def save_findings(self, run_id: str, findings: list[Finding]) -> None:
        if not findings:
            return
        with get_db_connection(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO findings (
                    run_id, rule_id, category, severity, confidence,
                    message, file_path, line_start, line_end, evidence,
                    tool_name, tool_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        f.rule_id,
                        f.category,
                        f.severity,
                        f.confidence,
                        f.message,
                        f.file_path,
                        f.line_start,
                        f.line_end,
                        f.evidence,
                        f.tool_name,
                        f.tool_version,
                    )
                    for f in findings
                ],
            )
            conn.commit()

    def save_commits(self, repository_id: int, commits: list[CommitInfo]) -> None:
        if not commits:
            return
        with get_db_connection(self.db_path) as conn:
            for c in commits:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO commits (
                        repository_id, commit_sha, author_identity,
                        author_timestamp, committer_timestamp, subject
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        repository_id,
                        c.commit_sha,
                        f"{c.author_name} <{c.author_email}>",
                        c.author_date,
                        c.committer_date,
                        c.subject,
                    ),
                )
                if c.changes:
                    conn.executemany(
                        """
                        INSERT OR REPLACE INTO commit_changes (
                            repository_id, commit_sha, file_path,
                            change_type, lines_added, lines_deleted
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (
                                repository_id,
                                ch.commit_sha,
                                ch.file_path,
                                ch.change_type,
                                ch.lines_added,
                                ch.lines_deleted,
                            )
                            for ch in c.changes
                        ],
                    )
            conn.commit()

    def save_dependencies(self, repository_id: int, dependencies: list[DiscoveredDependency]) -> None:
        if not dependencies:
            return
        with get_db_connection(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO dependencies (
                    repository_id, name, version_spec, ecosystem, manifest_file
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [(repository_id, d.name, d.version_spec, d.ecosystem, d.manifest_file) for d in dependencies],
            )
            conn.commit()

    def save_report(self, run_id: str, report_format: str, content: str) -> None:
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO reports (run_id, report_format, content) VALUES (?, ?, ?)",
                (run_id, report_format, content),
            )
            conn.commit()

    def save_summary(self, run_id: str, summary_type: str, content: str) -> None:
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO analysis_summaries (run_id, summary_type, content) VALUES (?, ?, ?)",
                (run_id, summary_type, content),
            )
            conn.commit()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with get_db_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT r.*, repo.normalized_url, repo.display_name
                FROM analysis_runs r
                JOIN repositories repo ON r.repository_id = repo.id
                WHERE r.id = ?
                """,
                (run_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT r.*, repo.normalized_url, repo.display_name
                FROM analysis_runs r
                JOIN repositories repo ON r.repository_id = repo.id
                ORDER BY r.started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_latest_run_for_repo(self, normalized_url: str) -> dict[str, Any] | None:
        with get_db_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT r.*, repo.normalized_url, repo.display_name
                FROM analysis_runs r
                JOIN repositories repo ON r.repository_id = repo.id
                WHERE repo.normalized_url = ? AND r.status IN ('completed', 'partial')
                ORDER BY r.started_at DESC
                LIMIT 1
                """,
                (normalized_url,),
            ).fetchone()
            return dict(row) if row else None

    def get_metrics_for_run(self, run_id: str) -> list[MetricResult]:
        with get_db_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM metric_values WHERE run_id = ?",
                (run_id,),
            ).fetchall()
            return [
                MetricResult(
                    name=r["name"],
                    category=r["category"],
                    value=r["value"],
                    unit=r["unit"],
                    scope_type=r["scope_type"],
                    scope_key=r["scope_key"],
                    analyzer=r["analyzer"],
                    analyzer_version=r["analyzer_version"],
                    formula_version=r["formula_version"],
                    status=r["status"],
                    explanation=r["explanation"],
                )
                for r in rows
            ]

    def get_findings_for_run(self, run_id: str) -> list[Finding]:
        with get_db_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM findings WHERE run_id = ?",
                (run_id,),
            ).fetchall()
            return [
                Finding(
                    rule_id=r["rule_id"],
                    category=r["category"],
                    severity=r["severity"],
                    confidence=r["confidence"],
                    message=r["message"],
                    file_path=r["file_path"],
                    line_start=r["line_start"],
                    line_end=r["line_end"],
                    evidence=r["evidence"],
                    tool_name=r["tool_name"],
                    tool_version=r["tool_version"],
                )
                for r in rows
            ]

    def compare_snapshots(self, run_id_a: str, run_id_b: str) -> dict[str, Any]:
        """Compare two analysis runs, computing metric deltas, new findings, and trends."""
        run_a = self.get_run(run_id_a)
        run_b = self.get_run(run_id_b)
        if not run_a or not run_b:
            raise ValueError(f"One or both run IDs not found: '{run_id_a}', '{run_id_b}'")

        metrics_a = {f"{m.scope_type}:{m.scope_key}:{m.name}": m for m in self.get_metrics_for_run(run_id_a)}
        metrics_b = {f"{m.scope_type}:{m.scope_key}:{m.name}": m for m in self.get_metrics_for_run(run_id_b)}

        deltas: list[dict[str, Any]] = []
        all_keys = sorted(set(metrics_a.keys()) | set(metrics_b.keys()))

        for k in all_keys:
            m_a = metrics_a.get(k)
            m_b = metrics_b.get(k)
            # Only compare repository-level or file-level metrics
            scope_type, scope_key, name = k.split(":", 2)
            if scope_type not in ("repository", "file"):
                continue

            val_a = m_a.value if (m_a and m_a.value is not None) else None
            val_b = m_b.value if (m_b and m_b.value is not None) else None

            if val_a is not None and val_b is not None:
                abs_delta = round(val_b - val_a, 2)
                pct_delta = round(((val_b - val_a) / val_a) * 100.0, 1) if val_a != 0 else 0.0
            elif val_a is None and val_b is not None:
                abs_delta = val_b
                pct_delta = 100.0
            elif val_a is not None and val_b is None:
                abs_delta = -val_a
                pct_delta = -100.0
            else:
                abs_delta = 0.0
                pct_delta = 0.0

            deltas.append({
                "scope_type": scope_type,
                "scope_key": scope_key,
                "name": name,
                "unit": (m_b or m_a).unit,
                "value_before": val_a,
                "value_after": val_b,
                "abs_delta": abs_delta,
                "pct_delta": pct_delta,
            })

        findings_a = self.get_findings_for_run(run_id_a)
        findings_b = self.get_findings_for_run(run_id_b)

        rule_files_a = {(f.rule_id, f.file_path) for f in findings_a}
        new_findings = [f for f in findings_b if (f.rule_id, f.file_path) not in rule_files_a]
        resolved_findings = [f for f in findings_a if (f.rule_id, f.file_path) not in {(f.rule_id, f.file_path) for f in findings_b}]

        return {
            "run_before": run_a,
            "run_after": run_b,
            "metric_deltas": deltas,
            "new_findings_count": len(new_findings),
            "resolved_findings_count": len(resolved_findings),
            "new_findings": new_findings[:20],
            "resolved_findings": resolved_findings[:20],
        }
