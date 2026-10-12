"""Report generation service: Markdown, JSON, CSV, and Snapshot Comparison."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict
from typing import Any
from sem_cli.analytics.trends import generate_sparkline
from sem_cli.metrics.schema import Finding, MetricResult
from sem_cli.services.analysis_service import CompletedAnalysis


def generate_markdown_report(analysis: CompletedAnalysis) -> str:
    """Generate a clean, evidence-linked Markdown engineering report."""
    md = []
    md.append(f"# Software Engineering Metrics Report — {analysis.repository_name}")
    md.append("")
    md.append(f"**Repository:** `{analysis.normalized_url}`  ")
    md.append(f"**Revision SHA:** `{analysis.commit_sha}`  ")
    md.append(f"**Branch:** `{analysis.branch or 'HEAD'}`  ")
    md.append(f"**Run ID:** `{analysis.run_id}`  ")
    md.append(f"**Overall Engineering Risk:** `{analysis.risk_assessment.risk_level}` (Score: {analysis.risk_assessment.overall_risk_score}/1.00)  ")
    md.append("")

    # Summary table
    md.append("## 1. Repository Health Overview")
    md.append("")
    md.append("| Metric | Measured Value | Unit | Definition |")
    md.append("|---|---|---|---|")

    key_metrics = [
        ("total_sloc", "Source Lines of Code (SLOC)"),
        ("total_loc", "Physical Lines (LOC)"),
        ("file_count", "Eligible Files"),
        ("function_count", "Functions & Methods"),
        ("high_complexity_function_count", "High-Complexity Functions (CC > 10)"),
        ("avg_function_complexity", "Average Function Complexity"),
        ("avg_maintainability_index", "Average Maintainability Index (0-100)"),
        ("security_finding_count", "Security & Secret Findings"),
        ("code_smell_count", "Code Smell Indicators"),
        ("total_churn", "Historical Code Churn"),
        ("churn_gini_concentration", "Churn Gini Concentration (0=equal, 1=concentrated)"),
    ]

    metric_lookup = {m.name: m for m in analysis.metrics if m.scope_type == "repository"}
    for name, title in key_metrics:
        m = metric_lookup.get(name)
        if m and m.value is not None:
            val_str = f"{m.value:,.2f}" if isinstance(m.value, float) and not m.value.is_integer() else f"{int(m.value):,}"
            md.append(f"| {title} | **{val_str}** | {m.unit} | {m.explanation or ''} |")

    md.append("")

    # Hotspots table
    md.append("## 2. Top Complexity & Churn Hotspots")
    md.append("")
    md.append("Hotspot score is prioritized using: $H_f = C_f \\times N_f$ (normalized complexity $\\times$ historical change frequency).")
    md.append("")
    md.append("| File | Hotspot Score | Priority | Max CC | Changes | Churn | Supporting Evidence |")
    md.append("|---|---|---|---|---|---|---|")
    for h in analysis.hotspots[:15]:
        ev = "; ".join(h.supporting_findings) if h.supporting_findings else "High churn/complexity combination"
        md.append(f"| `{h.file_path}` | **{h.hotspot_score:.3f}** | {h.priority_level} | {h.complexity_score} | {h.change_count} | {h.churn:,} | {ev} |")

    md.append("")

    # Security & secrets findings
    md.append("## 3. Quality & Security Audit")
    md.append("")
    if analysis.findings:
        md.append("| Rule ID | Severity | File | Line | Finding | Evidence |")
        md.append("|---|---|---|---|---|---|")
        for f in analysis.findings[:25]:
            f_p = f"`{f.file_path}`" if f.file_path else "-"
            l_num = str(f.line_start) if f.line_start else "-"
            evid = f"`{f.evidence}`" if f.evidence else "-"
            md.append(f"| `{f.rule_id}` | **{f.severity.upper()}** | {f_p} | {l_num} | {f.message} | {evid} |")
    else:
        md.append("✓ No static security risks, hardcoded credentials, or critical code smells detected.")

    md.append("")

    # Statistical decision support
    md.append("## 4. Statistical Analysis & Decision Support")
    md.append("")
    if analysis.descriptive_stats:
        md.append("### Descriptive Statistics")
        md.append("")
        md.append("| Measure | Mean | Median | Std Dev | Q1 | Q3 | IQR | Min | Max | Skewness |")
        md.append("|---|---|---|---|---|---|---|---|---|---|")
        for name, st in analysis.descriptive_stats.items():
            md.append(f"| `{name}` | {st.mean} | {st.median} | {st.std_dev} | {st.q1} | {st.q3} | {st.iqr} | {st.min} | {st.max} | {st.skewness} |")
        md.append("")

    if analysis.correlations:
        md.append("### Empirical Metric Correlations")
        md.append("")
        for c in analysis.correlations:
            md.append(f"- **{c.metric_x} vs {c.metric_y}**: {c.interpretation}")
        md.append("")

    # Recommendations
    md.append("## 5. Engineering Action Plan")
    md.append("")
    for i, rec in enumerate(analysis.risk_assessment.recommendations, start=1):
        md.append(f"{i}. {rec}")

    md.append("")

    # AI Section if available
    if analysis.ai_response:
        md.append("## 6. Gemini-Assisted Interpretation")
        md.append("")
        md.append(f"> **Executive Summary:** {analysis.ai_response.executive_summary}")
        md.append("")
        md.append("### Main Engineering Risks")
        for r in analysis.ai_response.main_risks:
            md.append(f"- {r}")
        md.append("")
        md.append("### Recommended AI Prioritizations")
        for a in analysis.ai_response.recommended_actions:
            md.append(f"- {a}")
        md.append("")
        md.append(f"*Confidence & Limitations:* {analysis.ai_response.confidence_and_limitations}")
        md.append("")

    md.append("---")
    md.append(f"*Report generated by sem-cli v{analysis.run_id} · Local-first reproducibility guaranteed.*")
    return "\n".join(md)


def generate_json_report(analysis: CompletedAnalysis) -> str:
    """Generate structured JSON export for CI/CD integrations."""
    data = {
        "run_id": analysis.run_id,
        "repository_name": analysis.repository_name,
        "normalized_url": analysis.normalized_url,
        "commit_sha": analysis.commit_sha,
        "branch": analysis.branch,
        "is_shallow": analysis.is_shallow,
        "status": analysis.status,
        "file_count": analysis.file_count,
        "risk_assessment": asdict(analysis.risk_assessment),
        "metrics": [asdict(m) for m in analysis.metrics],
        "findings": [asdict(f) for f in analysis.findings],
        "hotspots": [asdict(h) for h in analysis.hotspots],
        "descriptive_stats": {k: asdict(v) for k, v in analysis.descriptive_stats.items()},
        "correlations": [asdict(c) for c in analysis.correlations],
        "ai_response": asdict(analysis.ai_response) if analysis.ai_response else None,
    }
    return json.dumps(data, indent=2)


def generate_csv_report(analysis: CompletedAnalysis) -> str:
    """Generate CSV representation of all computed metrics."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ScopeType",
        "ScopeKey",
        "Category",
        "MetricName",
        "Value",
        "Unit",
        "Status",
        "Analyzer",
        "Explanation",
    ])
    for m in analysis.metrics:
        writer.writerow([
            m.scope_type,
            m.scope_key,
            m.category,
            m.name,
            m.value if m.value is not None else "",
            m.unit,
            m.status,
            m.analyzer,
            m.explanation or "",
        ])
    return output.getvalue()
