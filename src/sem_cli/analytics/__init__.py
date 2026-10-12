"""Analytics package for statistics, hotspots, trends, and risk assessment."""

from sem_cli.analytics.descriptive import DescriptiveStats, compute_descriptive_stats
from sem_cli.analytics.outliers import OutlierItem, detect_iqr_outliers
from sem_cli.analytics.correlation import CorrelationResult, compute_correlations
from sem_cli.analytics.trends import generate_sparkline
from sem_cli.analytics.hotspots import HotspotItem, rank_hotspots
from sem_cli.analytics.risk import RiskAssessment, evaluate_repository_risk

__all__ = [
    "DescriptiveStats",
    "compute_descriptive_stats",
    "OutlierItem",
    "detect_iqr_outliers",
    "CorrelationResult",
    "compute_correlations",
    "generate_sparkline",
    "HotspotItem",
    "rank_hotspots",
    "RiskAssessment",
    "evaluate_repository_risk",
]
