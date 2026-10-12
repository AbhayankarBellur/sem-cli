"""Hotspot analysis: ranking modules combining high complexity and frequent change."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HotspotItem:
    file_path: str
    complexity_score: float  # raw max or average CC
    normalized_complexity: float  # [0, 1]
    change_count: int  # historical commits modifying file
    normalized_changes: float  # [0, 1]
    churn: int  # lines added + deleted
    hotspot_score: float  # H_f = C_f * N_f
    priority_level: str  # "Critical", "High", "Medium", "Low"
    supporting_findings: list[str] = field(default_factory=list)


def min_max_normalize(values: list[float]) -> list[float]:
    """Apply min-max normalization to an array into [0.0, 1.0].

    If all values are identical, returns [0.5, ...] for non-empty or empty list.
    """
    if not values:
        return []
    min_v = min(values)
    max_v = max(values)
    span = max_v - min_v

    if span == 0:
        return [0.5 for _ in values]

    return [round((v - min_v) / span, 4) for v in values]


def rank_hotspots(
    file_complexities: dict[str, float],  # file_path -> complexity (e.g. max CC)
    file_change_counts: dict[str, int],  # file_path -> change count
    file_churns: dict[str, int],  # file_path -> churn
    findings_by_file: dict[str, list[str]] | None = None,
    limit: int = 20,
) -> list[HotspotItem]:
    """Calculate H_f = C_f * N_f for all files and rank the top hotspots."""
    # Union of all files present in either complexity or history
    all_files = sorted(set(file_complexities.keys()) | set(file_change_counts.keys()))
    if not all_files:
        return []

    comp_vals = [file_complexities.get(f, 1.0) for f in all_files]
    change_vals = [float(file_change_counts.get(f, 0)) for f in all_files]

    norm_c = min_max_normalize(comp_vals)
    norm_n = min_max_normalize(change_vals)

    items: list[HotspotItem] = []
    findings_map = findings_by_file or {}

    for idx, f_path in enumerate(all_files):
        c_raw = comp_vals[idx]
        c_norm = norm_c[idx]
        n_raw = int(change_vals[idx])
        n_norm = norm_n[idx]

        h_score = round(c_norm * n_norm, 4)

        if h_score >= 0.5:
            priority = "Critical"
        elif h_score >= 0.25:
            priority = "High"
        elif h_score >= 0.1:
            priority = "Medium"
        else:
            priority = "Low"

        reasons: list[str] = []
        if c_norm >= 0.5:
            reasons.append(f"High complexity (CC={c_raw})")
        if n_norm >= 0.5:
            reasons.append(f"Frequent historical churn ({n_raw} changes)")
        reasons.extend(findings_map.get(f_path, []))

        items.append(
            HotspotItem(
                file_path=f_path,
                complexity_score=round(c_raw, 2),
                normalized_complexity=c_norm,
                change_count=n_raw,
                normalized_changes=n_norm,
                churn=file_churns.get(f_path, 0),
                hotspot_score=h_score,
                priority_level=priority,
                supporting_findings=reasons,
            )
        )

    # Sort descending by hotspot score, then churn
    items.sort(key=lambda x: (x.hotspot_score, x.churn, x.change_count), reverse=True)
    return items[:limit]
