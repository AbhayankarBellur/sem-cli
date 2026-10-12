"""Deterministic engineering risk scoring and decision support recommendations."""

from __future__ import annotations

from dataclasses import dataclass, field
from sem_cli.analytics.hotspots import HotspotItem


@dataclass(frozen=True)
class RiskAssessment:
    overall_risk_score: float  # [0.0, 1.0]
    risk_level: str  # "Low", "Moderate", "High", "Critical"
    component_scores: dict[str, float]  # weights and subscores
    recommendations: list[str] = field(default_factory=list)


def evaluate_repository_risk(
    hotspots: list[HotspotItem],
    critical_findings: int,
    high_findings: int,
    avg_maintainability: float,
    smell_ratio: float,
) -> RiskAssessment:
    """Calculate transparent deterministic risk score.

    Model:
    - Hotspot risk (0.35 weight): mean score of top 5 hotspots
    - Security risk (0.30 weight): min(1.0, (critical*0.5 + high*0.2))
    - Maintainability deficit (0.20 weight): max(0.0, (100 - avg_mi) / 100)
    - Code smell density (0.15 weight): min(1.0, smell_ratio / 5.0)
    """
    top_hotspot_scores = [h.hotspot_score for h in hotspots[:5]]
    hotspot_component = sum(top_hotspot_scores) / max(len(top_hotspot_scores), 1) if top_hotspot_scores else 0.0

    security_component = min(1.0, (critical_findings * 0.5 + high_findings * 0.2))
    mi_deficit = max(0.0, (100.0 - avg_maintainability) / 100.0)
    smell_component = min(1.0, smell_ratio / 5.0)

    overall = (
        0.35 * hotspot_component
        + 0.30 * security_component
        + 0.20 * mi_deficit
        + 0.15 * smell_component
    )
    overall = round(max(0.0, min(1.0, overall)), 3)

    if overall >= 0.70:
        level = "Critical"
    elif overall >= 0.45:
        level = "High"
    elif overall >= 0.25:
        level = "Moderate"
    else:
        level = "Low"

    recs: list[str] = []
    if security_component > 0.3:
        recs.append("Resolve critical/high static security findings and remove detected hardcoded secrets.")
    if hotspot_component > 0.25:
        top_h = hotspots[0].file_path if hotspots else "hotspot modules"
        recs.append(f"Refactor '{top_h}' which combines high cyclomatic complexity with frequent historical churn.")
    if avg_maintainability < 65.0:
        recs.append(f"Improve code maintainability index (currently {avg_maintainability}/100) by decomposing large functions.")
    if smell_component > 0.4:
        recs.append("Reduce architectural technical debt by refactoring God Classes and deeply nested logic.")
    if not recs:
        recs.append("Codebase metrics are within healthy thresholds. Maintain current testing and review discipline.")

    return RiskAssessment(
        overall_risk_score=overall,
        risk_level=level,
        component_scores={
            "hotspot_factor": round(hotspot_component, 3),
            "security_factor": round(security_component, 3),
            "maintainability_deficit": round(mi_deficit, 3),
            "code_smell_density": round(smell_component, 3),
        },
        recommendations=recs,
    )
