"""Integration tests for SQLite persistence and snapshot comparison."""

from pathlib import Path
from sem_cli.metrics.schema import Finding, MetricResult
from sem_cli.persistence.repositories import RepositoryDatabase


def test_sqlite_persistence_and_comparison(test_db: RepositoryDatabase):
    repo_id = test_db.get_or_create_repository("file:///test/repo", "test-repo")
    assert repo_id > 0

    # Run 1
    test_db.create_analysis_run("run_1", repo_id, "main", "1111" * 10, "full", "0.1.0")
    test_db.save_metric_values("run_1", [
        MetricResult("total_sloc", "product", 100.0, "lines", "repository", "repository", "test", "1.0", "1.0", "measured"),
        MetricResult("avg_function_complexity", "complexity", 4.0, "count", "repository", "repository", "test", "1.0", "1.0", "measured"),
    ])
    test_db.save_findings("run_1", [
        Finding("SEC-EVAL", "security", "high", "high", "Eval used", "file.py", 10, 10, "eval()"),
    ])
    test_db.update_run_status("run_1", "completed")

    # Run 2
    test_db.create_analysis_run("run_2", repo_id, "main", "2222" * 10, "full", "0.1.0")
    test_db.save_metric_values("run_2", [
        MetricResult("total_sloc", "product", 150.0, "lines", "repository", "repository", "test", "1.0", "1.0", "measured"),
        MetricResult("avg_function_complexity", "complexity", 6.0, "count", "repository", "repository", "test", "1.0", "1.0", "measured"),
    ])
    test_db.save_findings("run_2", [])  # Finding resolved
    test_db.update_run_status("run_2", "completed")

    # Verify retrieval
    r1 = test_db.get_run("run_1")
    assert r1 is not None
    assert r1["status"] == "completed"

    m1 = test_db.get_metrics_for_run("run_1")
    assert len(m1) == 2

    # Compare snapshots
    comp = test_db.compare_snapshots("run_1", "run_2")
    assert comp["resolved_findings_count"] == 1
    assert comp["new_findings_count"] == 0

    deltas = {d["name"]: d for d in comp["metric_deltas"]}
    assert deltas["total_sloc"]["abs_delta"] == 50.0
    assert deltas["avg_function_complexity"]["abs_delta"] == 2.0
