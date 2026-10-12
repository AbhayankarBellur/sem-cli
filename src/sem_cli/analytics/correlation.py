"""Correlation analysis (Pearson and Spearman) with sample size and significance checks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from scipy import stats as scipy_stats


@dataclass(frozen=True)
class CorrelationResult:
    metric_x: str
    metric_y: str
    pearson_r: float
    pearson_p_value: float
    spearman_rho: float
    spearman_p_value: float
    sample_size: int
    interpretation: str


def compute_correlations(
    metric_x_name: str,
    x_values: list[float],
    metric_y_name: str,
    y_values: list[float],
) -> CorrelationResult | None:
    """Compute Pearson and Spearman rank correlations between two metric vectors."""
    # Filter valid pairs
    pairs = [
        (float(x), float(y))
        for x, y in zip(x_values, y_values)
        if x is not None and y is not None and not (math.isnan(x) or math.isnan(y))
    ]
    n = len(pairs)
    if n < 3:
        return None

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    # Check for constant arrays (std dev == 0)
    if len(set(xs)) <= 1 or len(set(ys)) <= 1:
        return CorrelationResult(
            metric_x=metric_x_name,
            metric_y=metric_y_name,
            pearson_r=0.0,
            pearson_p_value=1.0,
            spearman_rho=0.0,
            spearman_p_value=1.0,
            sample_size=n,
            interpretation="Constant value in dataset; correlation undefined (0.0).",
        )

    try:
        p_res = scipy_stats.pearsonr(xs, ys)
        pr = round(float(p_res.statistic), 3)
        pp = round(float(p_res.pvalue), 4)
    except Exception:
        pr, pp = 0.0, 1.0

    try:
        s_res = scipy_stats.spearmanr(xs, ys)
        srho = round(float(s_res.statistic), 3)
        sp = round(float(s_res.pvalue), 4)
    except Exception:
        srho, sp = 0.0, 1.0

    # Interpretation
    abs_r = abs(pr)
    if abs_r >= 0.7:
        strength = "Strong"
    elif abs_r >= 0.4:
        strength = "Moderate"
    elif abs_r >= 0.2:
        strength = "Weak"
    else:
        strength = "Negligible"

    direction = "positive" if pr > 0 else "negative"
    significance = "statistically significant" if pp < 0.05 else "not statistically significant"
    interp = f"{strength} {direction} correlation (r={pr}), {significance} (p={pp}, N={n}). Not causal."

    return CorrelationResult(
        metric_x=metric_x_name,
        metric_y=metric_y_name,
        pearson_r=pr,
        pearson_p_value=pp,
        spearman_rho=srho,
        spearman_p_value=sp,
        sample_size=n,
        interpretation=interp,
    )
