"""Rich console configuration with UTF-8 enforcement and Windows encoding resilience."""

from __future__ import annotations

import os
import sys
from rich.console import Console
from rich.theme import Theme

# Ensure UTF-8 on Windows streams to avoid charmap / cp1252 crashes
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SEM_THEME = Theme({
    "sem.brand": "bold cyan",
    "sem.header": "bold white on dark_blue",
    "sem.highlight": "bold yellow",
    "sem.success": "bold green",
    "sem.warning": "bold yellow",
    "sem.danger": "bold red",
    "sem.muted": "dim",
    "sem.score": "bold magenta",
})


def is_unicode_supported() -> bool:
    """Check if stdout can safely render Unicode box drawing and symbols."""
    try:
        enc = (sys.stdout.encoding or "").lower()
        return "utf" in enc or os.environ.get("PYTHONIOENCODING", "").lower().startswith("utf")
    except Exception:
        return False


# Adaptive symbols
SYM_OK = "[green]✓[/green]" if is_unicode_supported() else "[green][OK][/green]"
SYM_FAIL = "[red]✗[/red]" if is_unicode_supported() else "[red][FAIL][/red]"
SYM_WARN = "[yellow]▲[/yellow]" if is_unicode_supported() else "[yellow][WARN][/yellow]"
SYM_INFO = "[cyan]○[/cyan]" if is_unicode_supported() else "[cyan][*][/cyan]"


def get_console(no_color: bool = False) -> Console:
    """Return a configured Rich Console instance."""
    env_no_color = os.environ.get("NO_COLOR", "").strip() != ""
    disable_color = no_color or env_no_color
    return Console(
        theme=SEM_THEME,
        no_color=disable_color,
        legacy_windows=False if is_unicode_supported() else None,
    )


console = get_console()
