"""Rich Unicode screens for Main Workspace and Analysis Results."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from sem_cli.services.analysis_service import CompletedAnalysis
from sem_cli.ui.panels import create_header_banner, create_health_cards
from sem_cli.ui.tables import build_findings_table, build_hotspots_table


def render_analysis_results(console: Console, analysis: CompletedAnalysis) -> None:
    """Render the full analysis results screen."""
    # 1. Header
    banner = create_header_banner(
        repo_name=analysis.repository_name,
        branch=analysis.branch,
        commit_sha=analysis.commit_sha,
        file_count=analysis.file_count,
    )
    console.print(banner)

    # 2. Key numbers summary
    sloc = int(next((m.value for m in analysis.metrics if m.name == "total_sloc" and m.value is not None), 0))
    funcs = int(next((m.value for m in analysis.metrics if m.name == "function_count" and m.value is not None), 0))
    high_cc = int(next((m.value for m in analysis.metrics if m.name == "high_complexity_function_count" and m.value is not None), 0))
    findings_count = len(analysis.findings)
    hotspot_count = len([h for h in analysis.hotspots if h.priority_level in ("Critical", "High")])

    health_cards = create_health_cards(
        sloc=sloc,
        functions=funcs,
        high_complexity=high_cc,
        security_findings=findings_count,
        hotspot_count=hotspot_count,
        risk_level=analysis.risk_assessment.risk_level,
    )
    console.print(health_cards)
    console.print()

    # 3. Hotspots Table
    if analysis.hotspots:
        console.print(build_hotspots_table(analysis.hotspots, limit=8))
        console.print()

    # 4. Top Security Findings
    if analysis.findings:
        console.print(build_findings_table(analysis.findings, limit=6))
        console.print()

    # 5. Suggested next action panel
    next_action_text = Text()
    next_action_text.append("Suggested Next Action\n", style="bold yellow")
    for i, rec in enumerate(analysis.risk_assessment.recommendations[:2], start=1):
        next_action_text.append(f"{i}. {rec}\n", style="white")

    if analysis.stage_errors:
        next_action_text.append(f"\n[bold yellow]Warnings/Partial Stages:[/bold yellow] {len(analysis.stage_errors)} partial items recorded.")

    console.print(
        Panel(
            next_action_text,
            border_style="yellow",
            padding=(0, 2),
        )
    )

    console.print(
        f"[dim]Run ID: [bold magenta]{analysis.run_id}[/bold magenta] · "
        f"Export: [cyan]sem export {analysis.run_id} --format json[/cyan] · "
        f"Report: [cyan]sem report {analysis.run_id}[/cyan][/dim]\n"
    )
