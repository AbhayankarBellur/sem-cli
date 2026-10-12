"""UI package."""

from sem_cli.ui.console import console, get_console
from sem_cli.ui.panels import create_header_banner, create_health_cards, create_severity_badge
from sem_cli.ui.tables import (
    build_comparison_table,
    build_findings_table,
    build_hotspots_table,
    build_runs_table,
)

__all__ = [
    "console",
    "get_console",
    "create_header_banner",
    "create_health_cards",
    "create_severity_badge",
    "build_comparison_table",
    "build_findings_table",
    "build_hotspots_table",
    "build_runs_table",
]
