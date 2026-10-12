"""Dependency manifest analysis and vulnerability indicator scanner."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from sem_cli.metrics.schema import Finding, MetricResult
from sem_cli.repository.models import RepositorySnapshot

ANALYZER_NAME = "sem-dependency-analyzer"
ANALYZER_VERSION = "1.0.0"


@dataclass(frozen=True)
class DiscoveredDependency:
    name: str
    version_spec: str
    ecosystem: str  # PyPI, npm
    manifest_file: str


def parse_requirements_txt(content: str, rel_path: str) -> list[DiscoveredDependency]:
    """Parse requirements.txt lines."""
    deps: list[DiscoveredDependency] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-", "@", "git+")):
            continue
        # Split on ==, >=, <=, ~=, <, >
        parts = re.split(r"(==|>=|<=|~=|<|>)", line, maxsplit=1)
        name = parts[0].strip()
        ver = "".join(parts[1:]).strip() if len(parts) > 1 else "*"
        if name:
            deps.append(DiscoveredDependency(name=name, version_spec=ver, ecosystem="PyPI", manifest_file=rel_path))
    return deps


def parse_pyproject_toml(content: str, rel_path: str) -> list[DiscoveredDependency]:
    """Parse pyproject.toml dependencies."""
    deps: list[DiscoveredDependency] = []
    try:
        data = tomllib.loads(content)
        # project.dependencies
        if "project" in data and "dependencies" in data["project"]:
            for item in data["project"]["dependencies"]:
                parts = re.split(r"(==|>=|<=|~=|<|>)", item, maxsplit=1)
                name = parts[0].strip()
                ver = "".join(parts[1:]).strip() if len(parts) > 1 else "*"
                if name:
                    deps.append(DiscoveredDependency(name=name, version_spec=ver, ecosystem="PyPI", manifest_file=rel_path))
        # poetry dependencies
        if "tool" in data and "poetry" in data["tool"] and "dependencies" in data["tool"]["poetry"]:
            for name, ver_val in data["tool"]["poetry"]["dependencies"].items():
                if name.lower() != "python":
                    ver_str = str(ver_val)
                    deps.append(DiscoveredDependency(name=name, version_spec=ver_str, ecosystem="PyPI", manifest_file=rel_path))
    except Exception:
        pass
    return deps


def parse_package_json(content: str, rel_path: str) -> list[DiscoveredDependency]:
    """Parse package.json dependencies."""
    deps: list[DiscoveredDependency] = []
    try:
        data = json.loads(content)
        for dep_type in ("dependencies", "devDependencies"):
            if dep_type in data and isinstance(data[dep_type], dict):
                for name, ver in data[dep_type].items():
                    deps.append(DiscoveredDependency(name=name, version_spec=str(ver), ecosystem="npm", manifest_file=rel_path))
    except Exception:
        pass
    return deps


class DependencyAnalyzer:
    """Discovers dependencies and flags manifest risks (e.g., wildcards, unpinned packages)."""

    name = ANALYZER_NAME
    version = ANALYZER_VERSION

    def supports(self, snapshot: RepositorySnapshot) -> bool:
        return True

    def analyze(self, snapshot: RepositorySnapshot) -> tuple[list[MetricResult], list[Finding], list[DiscoveredDependency]]:
        discovered: list[DiscoveredDependency] = []
        findings: list[Finding] = []

        manifest_names = {
            "requirements.txt",
            "pyproject.toml",
            "setup.py",
            "package.json",
            "Pipfile",
        }

        for f in snapshot.files:
            file_name = Path(f.relative_path).name.lower()
            if file_name in manifest_names:
                try:
                    txt = f.absolute_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                if file_name == "requirements.txt":
                    discovered.extend(parse_requirements_txt(txt, f.relative_path))
                elif file_name == "pyproject.toml":
                    discovered.extend(parse_pyproject_toml(txt, f.relative_path))
                elif file_name == "package.json":
                    discovered.extend(parse_package_json(txt, f.relative_path))

        # Check for unpinned/wildcard dependencies
        for d in discovered:
            if d.version_spec in ("*", "latest") or not d.version_spec:
                findings.append(
                    Finding(
                        rule_id="DEP-UNPINNED",
                        category="dependency",
                        severity="low",
                        confidence="high",
                        message=f"Dependency '{d.name}' in {d.manifest_file} is unpinned ('{d.version_spec}'), risking breaking changes.",
                        file_path=d.manifest_file,
                        evidence=f"{d.name}: {d.version_spec}",
                        tool_name=self.name,
                        tool_version=self.version,
                    )
                )

        total_deps = float(len(discovered))

        metrics = [
            MetricResult(
                name="dependency_count",
                category="structural",
                value=total_deps,
                unit="dependencies",
                scope_type="repository",
                scope_key="repository",
                analyzer=self.name,
                analyzer_version=self.version,
                formula_version="2026.1",
                status="measured",
                explanation="Total distinct dependencies found in project manifests.",
            )
        ]

        return metrics, findings, discovered
