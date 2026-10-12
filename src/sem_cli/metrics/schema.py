"""Standard normalized schemas for metrics and findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MetricScope = Literal["repository", "file", "class", "function", "commit"]
MetricStatus = Literal["measured", "unsupported", "not_applicable", "error"]
FindingSeverity = Literal["critical", "high", "medium", "low", "info"]
FindingConfidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class MetricResult:
    name: str
    category: str  # product, complexity, structural, process, quality, security
    value: float | None
    unit: str
    scope_type: MetricScope
    scope_key: str  # repo, relative file path, class/function name, etc.
    analyzer: str
    analyzer_version: str
    formula_version: str
    status: MetricStatus
    explanation: str | None = None

    def is_measured(self) -> bool:
        return self.status == "measured" and self.value is not None


@dataclass(frozen=True)
class Finding:
    rule_id: str
    category: str  # security, secret, smell, dependency, bug_risk
    severity: FindingSeverity
    confidence: FindingConfidence
    message: str
    file_path: str | None
    line_start: int | None = None
    line_end: int | None = None
    evidence: str | None = None
    tool_name: str = "sem-scanner"
    tool_version: str = "1.0.0"
