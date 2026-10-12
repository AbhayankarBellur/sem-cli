"""Base protocol and interface for static analyzers."""

from __future__ import annotations

from typing import Protocol
from sem_cli.metrics.schema import Finding, MetricResult
from sem_cli.repository.models import RepositorySnapshot


class Analyzer(Protocol):
    """Protocol for pluggable metrics and security analyzers."""

    name: str
    version: str

    def supports(self, snapshot: RepositorySnapshot) -> bool:
        """Check if analyzer can run on the given repository snapshot."""
        ...

    def analyze(self, snapshot: RepositorySnapshot) -> tuple[list[MetricResult], list[Finding]]:
        """Run analysis on repository snapshot, returning metrics and findings."""
        ...
