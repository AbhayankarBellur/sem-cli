"""Static security analysis and secret detection with automatic redaction."""

from __future__ import annotations

import math
import re
from pathlib import Path
from sem_cli.metrics.schema import Finding, MetricResult
from sem_cli.repository.models import RepositorySnapshot

ANALYZER_NAME = "sem-security-analyzer"
ANALYZER_VERSION = "1.0.0"

SECRET_PATTERNS: list[tuple[str, str, str, str]] = [
    (
        "SEC-AWS-KEY",
        r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}",
        "critical",
        "Potential AWS Access Key ID detected.",
    ),
    (
        "SEC-PRIVATE-KEY",
        r"-----BEGIN\s+(?:RSA|DSA|EC|OPENSSH|PGP)?\s*PRIVATE\s+KEY-----",
        "critical",
        "Unencrypted Private Key header detected.",
    ),
    (
        "SEC-JWT-TOKEN",
        r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        "high",
        "Potential JSON Web Token (JWT) detected.",
    ),
    (
        "SEC-GENERIC-API-KEY",
        r"""(?i)(?:api_key|apikey|secret_key|secret|auth_token|access_token|password)\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}['"]""",
        "high",
        "Hardcoded credentials or API key detected in assignment.",
    ),
]

CODE_SECURITY_PATTERNS: list[tuple[str, str, str, str]] = [
    (
        "SEC-EVAL-EXEC",
        r"""\b(?:eval|exec)\s*\(""",
        "high",
        "Use of dynamic code execution (eval/exec) poses severe code injection risk.",
    ),
    (
        "SEC-SHELL-TRUE",
        r"""subprocess\.(?:run|Popen|call|check_output)\([^)]*shell\s*=\s*True""",
        "high",
        "subprocess invoked with shell=True invites command injection vulnerability.",
    ),
    (
        "SEC-INSECURE-HASH",
        r"""hashlib\.(?:md5|sha1)\s*\(""",
        "medium",
        "Use of cryptographically weak hash algorithm (MD5 or SHA1).",
    ),
    (
        "SEC-INSECURE-DESERIALIZATION",
        r"""pickle\.(?:loads|load)\s*\(""",
        "high",
        "Insecure deserialization via pickle can lead to arbitrary code execution.",
    ),
    (
        "SEC-SQL-FORMATTING",
        r"""cursor\.execute\s*\(\s*(?:f['"]|['"].*%|['"].*\.format\()""",
        "high",
        "Possible SQL injection: SQL query constructed via string formatting instead of parameterized query.",
    ),
]


def shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    counts: dict[str, int] = {}
    for char in data:
        counts[char] = counts.get(char, 0) + 1
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def redact_secret_string(value: str) -> str:
    """Redact sensitive text for safe persistence and display."""
    if len(value) <= 6:
        return "******"
    return value[:3] + "*" * (len(value) - 6) + value[-3:]


class SecurityAnalyzer:
    """Detects secrets and common security anti-patterns."""

    name = ANALYZER_NAME
    version = ANALYZER_VERSION

    def supports(self, snapshot: RepositorySnapshot) -> bool:
        return True

    def analyze(self, snapshot: RepositorySnapshot) -> tuple[list[MetricResult], list[Finding]]:
        findings: list[Finding] = []

        for f in snapshot.files:
            # Skip test files and markdown from heavy security smell alerts, but still check secrets
            try:
                content = f.absolute_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = content.splitlines()

            # 1. Scan secrets
            for line_idx, line in enumerate(lines, start=1):
                # Skip comments or documentation if marked
                stripped = line.strip()
                if not stripped:
                    continue

                for rule_id, pattern, severity, msg in SECRET_PATTERNS:
                    match = re.search(pattern, line)
                    if match:
                        raw_match = match.group(0)
                        redacted = redact_secret_string(raw_match)
                        findings.append(
                            Finding(
                                rule_id=rule_id,
                                category="secret",
                                severity=severity,  # type: ignore
                                confidence="high",
                                message=msg,
                                file_path=f.relative_path,
                                line_start=line_idx,
                                line_end=line_idx,
                                evidence=redacted,
                                tool_name=self.name,
                                tool_version=self.version,
                            )
                        )
                        break

            # 2. Scan code security patterns
            if not f.is_test and f.language in ("Python", "JavaScript", "TypeScript"):
                for line_idx, line in enumerate(lines, start=1):
                    for rule_id, pattern, severity, msg in CODE_SECURITY_PATTERNS:
                        if re.search(pattern, line):
                            # Redact line snippet
                            snippet = line.strip()[:100]
                            findings.append(
                                Finding(
                                    rule_id=rule_id,
                                    category="security",
                                    severity=severity,  # type: ignore
                                    confidence="medium",
                                    message=msg,
                                    file_path=f.relative_path,
                                    line_start=line_idx,
                                    line_end=line_idx,
                                    evidence=snippet,
                                    tool_name=self.name,
                                    tool_version=self.version,
                                )
                            )

        # Aggregate metrics
        critical_count = sum(1 for f in findings if f.severity == "critical")
        high_count = sum(1 for f in findings if f.severity == "high")
        medium_count = sum(1 for f in findings if f.severity == "medium")
        total_findings = float(len(findings))

        metrics = [
            MetricResult(
                name="security_finding_count",
                category="security",
                value=total_findings,
                unit="findings",
                scope_type="repository",
                scope_key="repository",
                analyzer=self.name,
                analyzer_version=self.version,
                formula_version="2026.1",
                status="measured",
                explanation="Total security and secret findings detected.",
            ),
            MetricResult(
                name="critical_security_finding_count",
                category="security",
                value=float(critical_count),
                unit="findings",
                scope_type="repository",
                scope_key="repository",
                analyzer=self.name,
                analyzer_version=self.version,
                formula_version="2026.1",
                status="measured",
                explanation="Critical security and secret findings.",
            ),
            MetricResult(
                name="high_security_finding_count",
                category="security",
                value=float(high_count),
                unit="findings",
                scope_type="repository",
                scope_key="repository",
                analyzer=self.name,
                analyzer_version=self.version,
                formula_version="2026.1",
                status="measured",
                explanation="High-severity security findings.",
            ),
        ]

        return metrics, findings
