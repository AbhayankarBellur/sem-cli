"""Trend analysis and Unicode terminal sparklines."""

from __future__ import annotations

SPARKLINE_BARS = (" ", "▂", "▃", "▄", "▅", "▆", "▇", "█")


def generate_sparkline(values: list[float]) -> str:
    """Generate a compact Unicode sparkline representation of a numerical series.

    Example: [1, 2, 5, 8, 3] -> ' ▂▅█▃'
    """
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return ""
    if len(clean) == 1:
        return "▅"

    min_v = min(clean)
    max_v = max(clean)

    if min_v == max_v:
        return "▄" * len(clean)

    span = max_v - min_v
    num_bars = len(SPARKLINE_BARS)

    result = []
    for v in clean:
        fraction = (v - min_v) / span
        idx = min(int(fraction * num_bars), num_bars - 1)
        result.append(SPARKLINE_BARS[idx])

    return "".join(result)
