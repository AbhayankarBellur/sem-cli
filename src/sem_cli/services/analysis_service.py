"""Full analysis pipeline orchestration service."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from sem_cli import __version__
from sem_cli.analytics.correlation import CorrelationResult, compute_correlations
from sem_cli.analytics.descriptive import DescriptiveStats, compute_descriptive_stats
from sem_cli.analytics.hotspots import HotspotItem, rank_hotspots
from sem_cli.analytics.outliers import OutlierItem, detect_iqr_outliers
from sem_cli.analytics.risk import RiskAssessment, evaluate_repository_risk
from sem_cli.analyzers.registry import AnalysisStageResult, run_all_analyzers
from sem_cli.config.settings import AppConfig
from sem_cli.metrics.schema import Finding, MetricResult
from sem_cli.persistence.repositories import RepositoryDatabase
from sem_cli.repository.clone_manager import CloneManager
from sem_cli.repository.file_inventory import discover_files
from sem_cli.repository.models import CommitInfo, ContributorInfo, RepositorySnapshot
from sem_cli.repository.repository_metadata import get_repository_metadata
from sem_cli.repository.url_parser import parse_and_validate_target
from sem_cli.services.ai_service import (
    AIAnalysisResponse,
    EvidencePayload,
    GeminiAIService,
    build_evidence_payload,
)
from sem_cli.services.history_service import HistoryMiningResult, mine_git_history

logger = logging.getLogger(__name__)


@dataclass
class CompletedAnalysis:
    run_id: str
    repository_id: int
    repository_name: str
    normalized_url: str
    commit_sha: str
    branch: str | None
    is_shallow: bool
    status: str
    profile: str
    file_count: int
    metrics: list[MetricResult]
    findings: list[Finding]
    hotspots: list[HotspotItem]
    risk_assessment: RiskAssessment
    history_result: HistoryMiningResult
    descriptive_stats: dict[str, DescriptiveStats]
    outliers: dict[str, list[OutlierItem]]
    correlations: list[CorrelationResult]
    stage_errors: list[dict[str, str]]
    ai_response: AIAnalysisResponse | None = None


def execute_analysis_pipeline(
    target_str: str,
    config: AppConfig,
    *,
    requested_ref: str | None = None,
    history_depth: int | None = None,
    profile: str = "full",
    use_ai: bool = False,
    business_context: str | None = None,
    progress_callback: Callable[[str, float], None] | None = None,
) -> CompletedAnalysis:
    """Execute complete software engineering metrics ingestion, analysis, and persistence pipeline."""

    def _notify(stage_name: str, pct: float) -> None:
        if progress_callback:
            progress_callback(stage_name, pct)

    _notify("Validating repository target", 0.05)
    parsed_target = parse_and_validate_target(target_str)

    db = RepositoryDatabase(config.db_path)
    repo_id = db.get_or_create_repository(parsed_target.normalized_url, parsed_target.display_name)
    run_id = uuid.uuid4().hex[:12]

    depth = history_depth or config.analysis.history_depth

    clone_mgr = CloneManager(config.repository, config.data_dir / "workspaces")
    _notify("Cloning and preparing workspace", 0.15)
    snapshot, workspace_path, is_temp = clone_mgr.prepare_snapshot(
        parsed_target,
        requested_ref=requested_ref,
        history_depth=depth,
        run_id=run_id,
    )

    db.create_analysis_run(
        run_id=run_id,
        repository_id=repo_id,
        requested_ref=requested_ref,
        commit_sha=snapshot.commit_sha,
        profile=profile,
        tool_version=__version__,
    )

    stage_errors: list[dict[str, str]] = []

    try:
        # File discovery
        _notify("Enumerating and classifying source files", 0.30)
        files = discover_files(snapshot.workspace_path, config.analysis)
        snapshot = RepositorySnapshot(
            run_id=snapshot.run_id,
            normalized_url=snapshot.normalized_url,
            display_name=snapshot.display_name,
            workspace_path=snapshot.workspace_path,
            requested_ref=snapshot.requested_ref,
            commit_sha=snapshot.commit_sha,
            default_branch=snapshot.default_branch,
            is_shallow=snapshot.is_shallow,
            created_at=snapshot.created_at,
            files=files,
        )

        # Mining Git history
        _notify("Mining commit history and code churn", 0.45)
        history_res = mine_git_history(snapshot.workspace_path, history_depth=depth)

        # Running static metrics and analyzers
        _notify("Calculating software metrics and security findings", 0.65)
        analysis_stage = run_all_analyzers(
            snapshot,
            complexity_threshold=config.metrics.complexity_threshold,
            security_enabled=config.security.enabled,
        )
        stage_errors.extend(analysis_stage.errors)

        # Combine metrics
        all_metrics = list(analysis_stage.metrics) + list(history_res.metrics)
        all_findings = list(analysis_stage.findings)

        # Hotspots ranking
        _notify("Computing hotspots and statistical analysis", 0.80)
        file_complexities: dict[str, float] = {}
        for m in all_metrics:
            if m.scope_type == "file" and m.name == "file_max_cyclomatic_complexity" and m.value is not None:
                file_complexities[m.scope_key] = m.value

        file_changes = {fh.file_path: fh.change_count for fh in history_res.file_histories.values()}
        file_churns = {fh.file_path: fh.churn for fh in history_res.file_histories.values()}

        findings_by_file: dict[str, list[str]] = {}
        for f in all_findings:
            if f.file_path:
                findings_by_file.setdefault(f.file_path, []).append(f"[{f.severity.upper()}] {f.message}")

        ranked_hotspots = rank_hotspots(
            file_complexities=file_complexities,
            file_change_counts=file_changes,
            file_churns=file_churns,
            findings_by_file=findings_by_file,
            limit=20,
        )

        # Statistics
        desc_stats: dict[str, DescriptiveStats] = {}
        outliers_map: dict[str, list[OutlierItem]] = {}

        # 1. Complexity stats
        fn_ccs = [float(fn.cyclomatic_complexity) for fn in analysis_stage.functions]
        if fn_ccs:
            desc_stats["cyclomatic_complexity"] = compute_descriptive_stats(fn_ccs)
            fn_tuples = [(f"{fn.file_path}::{fn.name}", float(fn.cyclomatic_complexity)) for fn in analysis_stage.functions]
            outliers_map["cyclomatic_complexity"] = detect_iqr_outliers(fn_tuples)

        # 2. File SLOC stats
        file_slocs = [
            (m.scope_key, float(m.value))
            for m in all_metrics
            if m.scope_type == "file" and m.name == "sloc" and m.value is not None
        ]
        if file_slocs:
            desc_stats["file_sloc"] = compute_descriptive_stats([s[1] for s in file_slocs])
            outliers_map["file_sloc"] = detect_iqr_outliers(file_slocs)

        # 3. Churn stats
        churn_items = [(fh.file_path, float(fh.churn)) for fh in history_res.file_histories.values() if fh.churn > 0]
        if churn_items:
            desc_stats["file_churn"] = compute_descriptive_stats([c[1] for c in churn_items])
            outliers_map["file_churn"] = detect_iqr_outliers(churn_items)

        # 4. Correlation: Complexity vs Churn
        common_files = sorted(set(file_complexities.keys()) & set(file_churns.keys()))
        correlations: list[CorrelationResult] = []
        if len(common_files) >= 4:
            c_vals = [file_complexities[f] for f in common_files]
            ch_vals = [float(file_churns[f]) for f in common_files]
            corr = compute_correlations("max_complexity", c_vals, "historical_churn", ch_vals)
            if corr:
                correlations.append(corr)

        # Risk assessment
        crit_f = sum(1 for f in all_findings if f.severity == "critical")
        high_f = sum(1 for f in all_findings if f.severity == "high")
        avg_mi_m = next((m.value for m in all_metrics if m.name == "avg_maintainability_index" and m.value is not None), 60.0)
        smell_m = next((m.value for m in all_metrics if m.name == "technical_debt_ratio" and m.value is not None), 0.5)

        risk_assessment = evaluate_repository_risk(
            hotspots=ranked_hotspots,
            critical_findings=crit_f,
            high_findings=high_f,
            avg_maintainability=float(avg_mi_m),
            smell_ratio=float(smell_m),
        )

        # Optional Gemini AI analysis
        ai_response: AIAnalysisResponse | None = None
        if use_ai:
            _notify("Invoking Gemini for evidence-grounded review", 0.90)
            ai_service = GeminiAIService(config.ai)
            if ai_service.is_available():
                payload = build_evidence_payload(
                    repo_name=parsed_target.display_name,
                    commit_sha=snapshot.commit_sha,
                    metrics=all_metrics,
                    findings=all_findings,
                    hotspots=ranked_hotspots,
                    risk=risk_assessment,
                    business_context=business_context,
                )
                try:
                    ai_response = ai_service.generate_review(payload, mode="engineering_review")
                    db.save_summary(run_id, "ai_engineering", ai_response.raw_response)
                except Exception as exc:
                    stage_errors.append({"stage": "gemini_ai", "error": str(exc)})
            else:
                stage_errors.append({
                    "stage": "gemini_ai",
                    "error": "GEMINI_API_KEY is not set. Skipped AI analysis.",
                })

        # Persistence
        _notify("Persisting results and historical snapshot to SQLite", 0.95)
        db.save_metric_values(run_id, all_metrics)
        db.save_findings(run_id, all_findings)
        db.save_commits(repo_id, history_res.commits)
        db.save_dependencies(repo_id, analysis_stage.dependencies)

        final_status = "partial" if stage_errors else "completed"
        db.update_run_status(
            run_id=run_id,
            status=final_status,
            error_summary=str(stage_errors) if stage_errors else None,
        )

        _notify("Analysis complete!", 1.0)

        return CompletedAnalysis(
            run_id=run_id,
            repository_id=repo_id,
            repository_name=parsed_target.display_name,
            normalized_url=parsed_target.normalized_url,
            commit_sha=snapshot.commit_sha,
            branch=snapshot.default_branch,
            is_shallow=snapshot.is_shallow,
            status=final_status,
            profile=profile,
            file_count=len(snapshot.files),
            metrics=all_metrics,
            findings=all_findings,
            hotspots=ranked_hotspots,
            risk_assessment=risk_assessment,
            history_result=history_res,
            descriptive_stats=desc_stats,
            outliers=outliers_map,
            correlations=correlations,
            stage_errors=stage_errors,
            ai_response=ai_response,
        )

    except Exception as exc:
        db.update_run_status(run_id, status="failed", error_summary=str(exc))
        raise
    finally:
        # Cleanup temporary clone if needed
        if is_temp and not config.repository.retain_clone:
            import shutil, stat

            def _on_rm_error(func, path, exc_info):
                import os
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass

            shutil.rmtree(workspace_path, onerror=_on_rm_error, ignore_errors=True)
