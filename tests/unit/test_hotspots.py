"""Unit tests for hotspot ranking logic and normalization."""

from sem_cli.analytics.hotspots import min_max_normalize, rank_hotspots


def test_min_max_normalize():
    vals = [10.0, 20.0, 30.0]
    norm = min_max_normalize(vals)
    assert norm == [0.0, 0.5, 1.0]


def test_min_max_normalize_constant():
    vals = [5.0, 5.0, 5.0]
    norm = min_max_normalize(vals)
    assert norm == [0.5, 0.5, 0.5]  # No divide by zero


def test_rank_hotspots():
    complexities = {
        "service/billing.py": 25.0,
        "api/auth.py": 15.0,
        "utils/string.py": 2.0,
    }
    changes = {
        "service/billing.py": 50,
        "api/auth.py": 10,
        "utils/string.py": 1,
    }
    churns = {
        "service/billing.py": 500,
        "api/auth.py": 100,
        "utils/string.py": 10,
    }

    hotspots = rank_hotspots(complexities, changes, churns)
    assert len(hotspots) == 3
    # Top hotspot should be billing.py (high CC and high changes)
    assert hotspots[0].file_path == "service/billing.py"
    assert hotspots[0].hotspot_score == 1.0
    assert hotspots[0].priority_level == "Critical"
