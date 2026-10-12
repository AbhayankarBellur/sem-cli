"""Outlier detection using Interquartile Range (IQR) and Z-score."""

from __future__ import annotations

from dataclasses import dataclass
from sem_cli.analytics.descriptive import compute_descriptive_stats


@dataclass(frozen=True)
class OutlierItem:
    label: str
    value: float
    lower_bound: float
    upper_bound: float
    is_extreme: bool


def detect_iqr_outliers(
    items: list[tuple[str, float]],
    iqr_multiplier: float = 1.5,
) -> list[OutlierItem]:
    """Detect outliers in a list of (label, numeric_value) tuples using IQR."""
    if len(items) < 4:
        return []

    values = [val for _, val in items]
    stats = compute_descriptive_stats(values)

    lower_bound = stats.q1 - (iqr_multiplier * stats.iqr)
    upper_bound = stats.q3 + (iqr_multiplier * stats.iqr)
    extreme_upper = stats.q3 + (3.0 * stats.iqr)

    outliers: list[OutlierItem] = []
    for label, val in items:
        if val < lower_bound or val > upper_bound:
            outliers.append(
                OutlierItem(
                    label=label,
                    value=round(val, 2),
                    lower_bound=round(lower_bound, 2),
                    upper_bound=round(upper_bound, 2),
                    is_extreme=(val > extreme_upper or val < (stats.q1 - 3.0 * stats.iqr)),
                )
            )

    return sorted(outliers, key=lambda x: x.value, reverse=True)
