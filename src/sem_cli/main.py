"""Main executable entrypoint for sem-cli."""

from __future__ import annotations

import sys
from sem_cli.cli.commands import app


def run_cli() -> None:
    """Run the Typer application."""
    app()


if __name__ == "__main__":
    run_cli()
