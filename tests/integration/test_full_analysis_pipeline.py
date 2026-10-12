"""End-to-end integration test of complete analysis pipeline on Git repository."""

import json
from pathlib import Path
from sem_cli.config.settings import AppConfig
from sem_cli.services.analysis_service import execute_analysis_pipeline
from sem_cli.services.report_service import (
    generate_csv_report,
    generate_json_report,
    generate_markdown_report,
)


def test_full_pipeline_on_fixture_repo(fixture_git_repo: Path, test_config: AppConfig):
    # Execute full analysis on the controlled test repository
    analysis = execute_analysis_pipeline(
        str(fixture_git_repo),
        test_config,
        profile="full",
        use_ai=False,
    )

    assert analysis.status == "completed"
    assert analysis.file_count >= 2
    assert len(analysis.commit_sha) == 40
    assert analysis.branch == "main"

    # Check metrics
    m_dict = {m.name: m.value for m in analysis.metrics if m.scope_type == "repository"}
    assert m_dict["total_sloc"] > 0
    assert m_dict["function_count"] >= 3
    assert m_dict["file_count"] >= 2
    assert "avg_maintainability_index" in m_dict

    # Check findings (eval in service.py should be caught)
    eval_findings = [f for f in analysis.findings if f.rule_id == "SEC-EVAL-EXEC"]
    assert len(eval_findings) >= 1
    assert eval_findings[0].file_path == "service.py"

    # Check hotspots
    assert len(analysis.hotspots) >= 1
    # service.py has higher complexity + multiple changes
    top_file = analysis.hotspots[0].file_path
    assert "service.py" in top_file or "math_utils.py" in top_file

    # Check risk assessment
    assert analysis.risk_assessment.overall_risk_score >= 0.0
    assert len(analysis.risk_assessment.recommendations) >= 1

    # Check report generation
    md_rep = generate_markdown_report(analysis)
    assert "# Software Engineering Metrics Report" in md_rep
    assert analysis.commit_sha in md_rep

    json_rep = generate_json_report(analysis)
    data = json.loads(json_rep)
    assert data["run_id"] == analysis.run_id
    assert len(data["metrics"]) > 0

    csv_rep = generate_csv_report(analysis)
    assert "ScopeType,ScopeKey,Category,MetricName,Value" in csv_rep
