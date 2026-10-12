"""Unit tests for descriptive statistics, outlier detection, and correlations."""

from sem_cli.analytics.correlation import compute_correlations
from sem_cli.analytics.descriptive import compute_descriptive_stats
from sem_cli.analytics.outliers import detect_iqr_outliers
from sem_cli.analytics.trends import generate_sparkline


def test_descriptive_stats():
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    stats = compute_descriptive_stats(values)
    assert stats.count == 5
    assert stats.mean == 30.0
    assert stats.median == 30.0
    assert stats.min == 10.0
    assert stats.max == 50.0
    assert stats.iqr > 0.0


def test_descriptive_stats_empty():
    stats = compute_descriptive_stats([])
    assert stats.count == 0
    assert stats.mean == 0.0


def test_iqr_outliers():
    items = [
        ("f1", 10.0),
        ("f2", 12.0),
        ("f3", 11.0),
        ("f4", 13.0),
        ("f5", 100.0),  # Extreme outlier
    ]
    outliers = detect_iqr_outliers(items)
    assert len(outliers) == 1
    assert outliers[0].label == "f5"
    assert outliers[0].is_extreme is True


def test_correlations_positive():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    ys = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]
    res = compute_correlations("x", xs, "y", ys)
    assert res is not None
    assert res.pearson_r == 1.0
    assert res.spearman_rho == 1.0


def test_sparkline():
    line = generate_sparkline([1.0, 5.0, 10.0, 2.0])
    assert len(line) == 4
    assert line[2] == "█"  # max is highest bar
