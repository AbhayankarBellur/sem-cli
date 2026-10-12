"""Rich tables for hotspots, metrics, findings, history, and snapshot comparisons."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from sem_cli.analytics.hotspots import HotspotItem
from sem_cli.metrics.schema import Finding, MetricResult
from sem_cli.ui.panels import create_severity_badge


def build_hotspots_table(hotspots: list[HotspotItem], limit: int = 15) -> Table:
    """Build a styled hotspots ranking table."""
    table = Table(
        title="Top Engineering Hotspots (Complexity × Change Concentration)",
        title_style="bold cyan",
        border_style="dim",
        expand=True,
    )
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("File Path", style="bold white", ratio=4)
    table.add_column("Hotspot Score", justify="right", style="bold magenta", width=14)
    table.add_column("Priority", justify="center", width=12)
    table.add_column("Max CC", justify="right", style="yellow", width=8)
    table.add_column("Changes", justify="right", style="cyan", width=9)
    table.add_column("Churn", justify="right", style="dim cyan", width=10)
    table.add_column("Supporting Evidence", ratio=4)

    for idx, h in enumerate(hotspots[:limit], start=1):
        color = "red" if h.priority_level == "Critical" else "dark_orange" if h.priority_level == "High" else "yellow" if h.priority_level == "Medium" else "green"
        p_text = Text(h.priority_level.upper(), style=f"bold {color}")
        evidence = "; ".join(h.supporting_findings) if h.supporting_findings else "High churn/complexity"

        table.add_row(
            str(idx),
            h.file_path,
            f"{h.hotspot_score:.3f}",
            p_text,
            str(int(h.complexity_score)),
            str(h.change_count),
            f"{h.churn:,}",
            evidence,
        )

    return table


def build_findings_table(findings: list[Finding], limit: int = 20) -> Table:
    """Build a findings summary table."""
    table = Table(
        title="Quality, Security, and Code Smell Audit",
        title_style="bold yellow",
        border_style="dim",
        expand=True,
    )
    table.add_column("Rule ID", style="bold white", width=22)
    table.add_column("Severity", justify="center", width=12)
    table.add_column("Category", style="dim", width=12)
    table.add_column("File Location", ratio=3)
    table.add_column("Description", ratio=5)
    table.add_column("Evidence", ratio=2)

    for f in findings[:limit]:
        f_loc = f"{f.file_path}:{f.line_start}" if f.file_path and f.line_start else (f.file_path or "-")
        evid = f.evidence or "-"
        table.add_row(
            f.rule_id,
            create_severity_badge(f.severity),
            f.category,
            f_loc,
            f.message,
            Text(evid[:40] + "..." if len(evid) > 40 else evid, style="dim"),
        )

    return table


def build_comparison_table(deltas: list[dict], limit: int = 25) -> Table:
    """Build snapshot comparison table with metric changes."""
    table = Table(
        title="Snapshot Comparison (Metric Deltas)",
        title_style="bold cyan",
        border_style="dim",
        expand=True,
    )
    table.add_column("Metric", style="bold white", ratio=3)
    table.add_column("Scope", style="dim", ratio=2)
    table.add_column("Before", justify="right", width=12)
    table.add_column("After", justify="right", width=12)
    table.add_column("Delta", justify="right", width=12)
    table.add_column("% Change", justify="right", width=12)

    for d in deltas[:limit]:
        v_bef = f"{d['value_before']}" if d['value_before'] is not None else "-"
        v_aft = f"{d['value_after']}" if d['value_after'] is not None else "-"
        delta = d['abs_delta']
        pct = d['pct_delta']

        delta_style = "green" if delta < 0 and "complexity" in d['name'] else "red" if delta > 0 and "complexity" in d['name'] else "bold white"
        delta_str = f"+{delta}" if delta > 0 else f"{delta}"
        pct_str = f"+{pct}%" if pct > 0 else f"{pct}%"

        table.add_row(
            d['name'],
            f"{d['scope_type']}:{d['scope_key']}",
            v_bef,
            v_aft,
            Text(delta_str, style=delta_style),
            Text(pct_str, style=delta_style),
        )

    return table


def build_runs_table(runs: list[dict]) -> Table:
    """Build previous analysis runs table."""
    table = Table(
        title="Historical Analysis Runs",
        title_style="bold cyan",
        border_style="dim",
        expand=True,
    )
    table.add_column("Run ID", style="bold magenta", width=14)
    table.add_column("Repository", style="bold white", ratio=3)
    table.add_column("Commit SHA", style="cyan", width=10)
    table.add_column("Status", justify="center", width=12)
    table.add_column("Started At", style="dim", width=22)

    for r in runs:
        status_color = "green" if r['status'] == "completed" else "yellow" if r['status'] == "partial" else "red"
        sha_abbrev = r['commit_sha'][:8] if r.get('commit_sha') else "-"
        table.add_row(
            r['id'],
            r.get('display_name') or r.get('normalized_url', '-'),
            sha_abbrev,
            Text(r['status'].upper(), style=f"bold {status_color}"),
            r.get('started_at', '-')[:19],
        )

    return table
