"""Descriptive statistics: mean, median, std dev, quartiles, and distributions."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class DescriptiveStats:
    count: int
    mean: float
    median: float
    std_dev: float
    variance: float
    q1: float
    q3: float
    iqr: float
    min: float
    max: float
    skewness: float


def compute_descriptive_stats(values: list[float]) -> DescriptiveStats:
    """Compute comprehensive descriptive statistics on a list of numeric values."""
    clean_vals = [float(v) for v in values if v is not None and not math.isnan(v)]
    n = len(clean_vals)

    if n == 0:
        return DescriptiveStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    clean_vals.sort()
    val_min = clean_vals[0]
    val_max = clean_vals[-1]
    mean_val = sum(clean_vals) / n

    # Median & Quartiles
    def _percentile(data: list[float], p: float) -> float:
        if len(data) == 1:
            return data[0]
        k = (len(data) - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return data[int(k)]
        d0 = data[int(f)] * (c - k)
        d1 = data[int(c)] * (k - f)
        return d0 + d1

    median_val = _percentile(clean_vals, 0.5)
    q1_val = _percentile(clean_vals, 0.25)
    q3_val = _percentile(clean_vals, 0.75)
    iqr_val = max(0.0, q3_val - q1_val)

    # Variance and Standard Deviation
    if n > 1:
        var_val = sum((x - mean_val) ** 2 for x in clean_vals) / (n - 1)
        std_val = math.sqrt(var_val)
    else:
        var_val = 0.0
        std_val = 0.0

    # Skewness
    if n > 2 and std_val > 0:
        m3 = sum((x - mean_val) ** 3 for x in clean_vals) / n
        skew_val = m3 / (std_val ** 3)
    else:
        skew_val = 0.0

    return DescriptiveStats(
        count=n,
        mean=round(mean_val, 3),
        median=round(median_val, 3),
        std_dev=round(std_val, 3),
        variance=round(var_val, 3),
        q1=round(q1_val, 3),
        q3=round(q3_val, 3),
        iqr=round(iqr_val, 3),
        min=round(val_min, 3),
        max=round(val_max, 3),
        skewness=round(skew_val, 3),
    )
