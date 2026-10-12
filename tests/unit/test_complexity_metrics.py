"""Unit tests for complexity, Halstead, and maintainability index calculations."""

from pathlib import Path
from sem_cli.metrics.complexity import (
    calculate_halstead_from_counts,
    calculate_maintainability_index,
    compute_file_complexity_metrics,
    compute_repository_complexity_metrics,
)
from sem_cli.repository.models import FileItem


def test_halstead_calculation():
    report = calculate_halstead_from_counts(
        n1_distinct_operators=10,
        n2_distinct_operands=15,
        N1_total_operators=30,
        N2_total_operands=25,
    )
    assert report.vocabulary == 25
    assert report.length == 55
    assert report.volume > 0.0
    assert report.difficulty > 0.0
    assert report.effort > 0.0


def test_maintainability_index():
    mi_good = calculate_maintainability_index(
        halstead_volume=100.0,
        cyclomatic_complexity=2.0,
        sloc=20.0,
        comment_percentage=0.2,
    )
    assert 0.0 <= mi_good <= 100.0
    assert mi_good > 60.0  # High maintainability

    mi_bad = calculate_maintainability_index(
        halstead_volume=5000.0,
        cyclomatic_complexity=35.0,
        sloc=500.0,
        comment_percentage=0.0,
    )
    assert mi_bad < mi_good


def test_compute_file_complexity_python(tmp_path: Path):
    f = tmp_path / "calc.py"
    f.write_text(
        "def branchy(x):\n"
        "    if x > 10:\n"
        "        return 'high'\n"
        "    elif x > 5:\n"
        "        return 'med'\n"
        "    return 'low'\n",
        encoding="utf-8",
    )
    item = FileItem("calc.py", f, "Python", 100, is_test=False)
    metrics, funcs = compute_file_complexity_metrics(item)

    assert len(funcs) == 1
    assert funcs[0].name == "branchy"
    assert funcs[0].cyclomatic_complexity == 3

    m_dict = {m.name: m.value for m in metrics}
    assert m_dict["file_max_cyclomatic_complexity"] == 3.0
    assert "maintainability_index" in m_dict
