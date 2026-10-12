"""Interactive Unicode Home Screen TUI inspired by Claude Code."""

from __future__ import annotations

import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from sem_cli.config.settings import AppConfig, load_config
from sem_cli.persistence.repositories import RepositoryDatabase
from sem_cli.repository.git_client import is_git_installed
from sem_cli.repository.revision_resolver import resolve_revision
from sem_cli.ui.panels import create_header_banner


def render_home_screen(console: Console, config: AppConfig) -> str:
    """Display the interactive workspace screen and return user selection."""
    console.clear()

    # Detect if current directory is a git repo
    repo_name = None
    branch = None
    commit_sha = None
    file_count = None

    cwd = Path.cwd()
    if (cwd / ".git").is_dir():
        repo_name = cwd.name
        try:
            commit_sha, branch, _ = resolve_revision(cwd)
            # Count tracked files
            from sem_cli.repository.git_client import run_git
            out = run_git(["ls-files"], cwd=cwd)
            file_count = len(out.splitlines()) if out else 0
        except Exception:
            pass

    # Header banner
    banner = create_header_banner(
        repo_name=repo_name,
        branch=branch,
        commit_sha=commit_sha,
        file_count=file_count,
    )
    console.print(banner)

    # Workspace menu options
    menu_text = Text()
    menu_text.append("WORKSPACE ACTIONS\n\n", style="bold cyan")
    menu_text.append("  1. ", style="bold yellow")
    menu_text.append("Analyze repository", style="bold white")
    menu_text.append("              — Run full metrics, churn & security scan\n", style="dim")

    menu_text.append("  2. ", style="bold yellow")
    menu_text.append("Explore software metrics", style="bold white")
    menu_text.append("        — Product size, complexity, and CK suite\n", style="dim")

    menu_text.append("  3. ", style="bold yellow")
    menu_text.append("Inspect complexity hotspots", style="bold white")
    menu_text.append("     — Modules combining high CC and high churn\n", style="dim")

    menu_text.append("  4. ", style="bold yellow")
    menu_text.append("Explore Git history", style="bold white")
    menu_text.append("             — Commits, churn distribution & contributors\n", style="dim")

    menu_text.append("  5. ", style="bold yellow")
    menu_text.append("Security & dependency audit", style="bold white")
    menu_text.append("     — Hardcoded secrets & dependency risks\n", style="dim")

    menu_text.append("  6. ", style="bold yellow")
    menu_text.append("Statistical analysis", style="bold white")
    menu_text.append("            — Distributions, outliers & correlations\n", style="dim")

    menu_text.append("  7. ", style="bold yellow")
    menu_text.append("Ask Gemini about repository", style="bold white")
    menu_text.append("     — Evidence-grounded AI recommendations\n", style="dim")

    menu_text.append("  8. ", style="bold yellow")
    menu_text.append("Export report", style="bold white")
    menu_text.append("                   — Export to Markdown, JSON, or CSV\n", style="dim")

    menu_text.append("\n  q. ", style="dim")
    menu_text.append("Exit\n", style="dim")

    panel = Panel(
        menu_text,
        border_style="dim white",
        padding=(1, 3),
    )
    console.print(panel)

    choice = Prompt.ask(
        "[bold cyan]Select action (1-8, q to quit)[/bold cyan]",
        choices=["1", "2", "3", "4", "5", "6", "7", "8", "q", "Q"],
        default="1",
        console=console,
    )
    return choice.strip().lower()
