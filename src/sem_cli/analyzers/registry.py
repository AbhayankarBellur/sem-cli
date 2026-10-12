"""Analyzer registry and execution coordinator with stage isolation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from sem_cli.analyzers.dependency_analyzer import DependencyAnalyzer, DiscoveredDependency
from sem_cli.analyzers.security_analyzer import SecurityAnalyzer
from sem_cli.metrics.complexity import (
    FunctionComplexity,
    compute_file_complexity_metrics,
    compute_repository_complexity_metrics,
)
from sem_cli.metrics.product import (
    compute_file_product_metrics,
    compute_repository_product_metrics,
)
from sem_cli.metrics.quality import detect_code_smells
from sem_cli.metrics.schema import Finding, MetricResult
from sem_cli.metrics.structural import (
    ClassStructure,
    compute_structural_metrics,
)
from sem_cli.repository.models import RepositorySnapshot

logger = logging.getLogger(__name__)


@dataclass
class AnalysisStageResult:
    metrics: list[MetricResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    functions: list[FunctionComplexity] = field(default_factory=list)
    classes: list[ClassStructure] = field(default_factory=list)
    dependencies: list[DiscoveredDependency] = field(default_factory=list)
    circular_cycles: list[list[str]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)


def run_all_analyzers(
    snapshot: RepositorySnapshot,
    complexity_threshold: int = 10,
    security_enabled: bool = True,
) -> AnalysisStageResult:
    """Run all metric and static analyzers on the snapshot with error isolation."""
    result = AnalysisStageResult()

    # 1. Product size metrics per file
    file_product_metrics: list[MetricResult] = []
    for f in snapshot.files:
        try:
            f_mets = compute_file_product_metrics(f)
            file_product_metrics.extend(f_mets)
        except Exception as exc:
            result.errors.append({
                "stage": "product_size",
                "file": f.relative_path,
                "error": str(exc),
            })
    result.metrics.extend(file_product_metrics)

    # Repository product metrics
    try:
        repo_product_metrics = compute_repository_product_metrics(snapshot.files, file_product_metrics)
        result.metrics.extend(repo_product_metrics)
    except Exception as exc:
        result.errors.append({"stage": "repository_product_metrics", "error": str(exc)})

    # 2. Complexity metrics per file
    file_complexity_metrics: list[MetricResult] = []
    for f in snapshot.files:
        try:
            c_mets, fn_list = compute_file_complexity_metrics(f)
            file_complexity_metrics.extend(c_mets)
            result.functions.extend(fn_list)
        except Exception as exc:
            result.errors.append({
                "stage": "complexity",
                "file": f.relative_path,
                "error": str(exc),
            })
    result.metrics.extend(file_complexity_metrics)

    # Repository complexity metrics
    try:
        repo_comp_metrics = compute_repository_complexity_metrics(
            result.functions,
            file_complexity_metrics,
            complexity_threshold=complexity_threshold,
        )
        result.metrics.extend(repo_comp_metrics)
    except Exception as exc:
        result.errors.append({"stage": "repository_complexity_metrics", "error": str(exc)})

    # 3. Structural & Object-Oriented metrics
    try:
        struct_metrics, classes, cycles = compute_structural_metrics(snapshot.files)
        result.metrics.extend(struct_metrics)
        result.classes.extend(classes)
        result.circular_cycles.extend(cycles)
    except Exception as exc:
        result.errors.append({"stage": "structural_metrics", "error": str(exc)})

    # 4. Quality & Code Smells
    try:
        smell_findings, smell_metrics = detect_code_smells(
            snapshot.files,
            result.functions,
            result.classes,
        )
        result.findings.extend(smell_findings)
        result.metrics.extend(smell_metrics)
    except Exception as exc:
        result.errors.append({"stage": "quality_smells", "error": str(exc)})

    # 5. Security & Secrets Analyzer
    if security_enabled:
        try:
            sec_analyzer = SecurityAnalyzer()
            sec_metrics, sec_findings = sec_analyzer.analyze(snapshot)
            result.metrics.extend(sec_metrics)
            result.findings.extend(sec_findings)
        except Exception as exc:
            result.errors.append({"stage": "security_analyzer", "error": str(exc)})

    # 6. Dependency Analyzer
    try:
        dep_analyzer = DependencyAnalyzer()
        dep_metrics, dep_findings, deps = dep_analyzer.analyze(snapshot)
        result.metrics.extend(dep_metrics)
        result.findings.extend(dep_findings)
        result.dependencies.extend(deps)
    except Exception as exc:
        result.errors.append({"stage": "dependency_analyzer", "error": str(exc)})

    return result
