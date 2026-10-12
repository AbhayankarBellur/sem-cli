"""Rich Unicode panels, headers, banners, and severity cards."""

from __future__ import annotations

from rich.align import Align
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from sem_cli.ui.console import is_unicode_supported


def create_header_banner(
    repo_name: str | None = None,
    branch: str | None = None,
    commit_sha: str | None = None,
    file_count: int | None = None,
    mode: str = "LOCAL MODE",
) -> Panel:
    """Create the branded Unicode header panel inspired by Claude Code."""
    title_text = Text()
    title_text.append(" sem-cli ", style="bold white on dark_blue")
    title_text.append(f"  {mode}  ", style="bold green on black")
    title_text.append("Software Engineering Metrics & Intelligence · v0.1.0\n", style="dim cyan")

    repo_bullet = "◆ " if is_unicode_supported() else "-> "
    if repo_name:
        title_text.append(f"\n{repo_bullet}Repository: ", style="bold cyan")
        title_text.append(f"{repo_name}\n", style="bold white")
        meta_parts = []
        if branch:
            meta_parts.append(f"Branch: {branch}")
        if commit_sha:
            meta_parts.append(f"HEAD: {commit_sha[:8]}")
        if file_count is not None:
            meta_parts.append(f"{file_count} files")
        title_text.append(" · ".join(meta_parts), style="dim white")

    return Panel(
        title_text,
        border_style="cyan",
        padding=(1, 2),
    )


def create_severity_badge(severity: str) -> Text:
    """Format a consistent styled severity badge."""
    sev = severity.lower()
    if sev == "critical":
        return Text("CRITICAL", style="bold red")
    elif sev == "high":
        return Text("HIGH", style="bold dark_orange")
    elif sev == "medium":
        return Text("MEDIUM", style="bold yellow")
    elif sev == "low":
        return Text("LOW", style="cyan")
    return Text("INFO", style="dim")


def create_health_cards(
    sloc: int,
    functions: int,
    high_complexity: int,
    security_findings: int,
    hotspot_count: int,
    risk_level: str,
) -> Table:
    """Display high-level key metric summary cards in a multi-column table."""
    grid = Table.grid(expand=True, padding=(0, 2))
    for _ in range(6):
        grid.add_column(justify="center", ratio=1)

    grid.add_row(
        Panel(f"[bold cyan]{sloc:,}[/bold cyan]\n[dim]Source LOC[/dim]", border_style="dim"),
        Panel(f"[bold cyan]{functions:,}[/bold cyan]\n[dim]Functions[/dim]", border_style="dim"),
        Panel(
            f"[bold {'red' if high_complexity > 0 else 'green'}]{high_complexity}[/bold {'red' if high_complexity > 0 else 'green'}]\n[dim]High CC (>10)[/dim]",
            border_style="dim",
        ),
        Panel(
            f"[bold {'red' if security_findings > 0 else 'green'}]{security_findings}[/bold {'red' if security_findings > 0 else 'green'}]\n[dim]Security Risks[/dim]",
            border_style="dim",
        ),
        Panel(
            f"[bold {'yellow' if hotspot_count > 0 else 'green'}]{hotspot_count}[/bold {'yellow' if hotspot_count > 0 else 'green'}]\n[dim]Hotspots[/dim]",
            border_style="dim",
        ),
        Panel(
            f"[bold {'red' if risk_level == 'Critical' else 'yellow' if risk_level in ('High', 'Moderate') else 'green'}]{risk_level}[/bold {'red' if risk_level == 'Critical' else 'yellow' if risk_level in ('High', 'Moderate') else 'green'}]\n[dim]Risk Level[/dim]",
            border_style="dim",
        ),
    )
    return grid
