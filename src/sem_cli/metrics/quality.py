"""Quality indicators, code smell detection, and technical debt estimation."""

from __future__ import annotations

import ast
from sem_cli.metrics.complexity import FunctionComplexity
from sem_cli.metrics.schema import Finding, MetricResult
from sem_cli.metrics.structural import ClassStructure
from sem_cli.repository.models import FileItem

ANALYZER_NAME = "sem-quality-engine"
ANALYZER_VERSION = "1.0.0"
FORMULA_VERSION = "2026.1"


def detect_code_smells(
    files: list[FileItem],
    functions: list[FunctionComplexity],
    classes: list[ClassStructure],
) -> tuple[list[Finding], list[MetricResult]]:
    """Detect code smells (Long Method, God Class, Long Parameter List, Deep Nesting)."""
    findings: list[Finding] = []

    # 1. Long Method smell
    for fn in functions:
        if fn.nloc > 50 or fn.cyclomatic_complexity > 15:
            findings.append(
                Finding(
                    rule_id="SMELL-LONG-METHOD",
                    category="smell",
                    severity="medium" if fn.cyclomatic_complexity <= 20 else "high",
                    confidence="high",
                    message=f"Function '{fn.name}' is too long or complex ({fn.nloc} NLOC, CC={fn.cyclomatic_complexity}).",
                    file_path=fn.file_path,
                    line_start=fn.line_start,
                    evidence=f"NLOC={fn.nloc}, CC={fn.cyclomatic_complexity}",
                    tool_name=ANALYZER_NAME,
                    tool_version=ANALYZER_VERSION,
                )
            )

    # 2. God Class smell
    for cls in classes:
        wmc = sum(cls.method_complexities.values())
        method_count = len(cls.methods)
        if wmc > 30 or method_count > 15:
            findings.append(
                Finding(
                    rule_id="SMELL-GOD-CLASS",
                    category="smell",
                    severity="high",
                    confidence="high",
                    message=f"Class '{cls.name}' shows God Class characteristics ({method_count} methods, WMC={wmc}).",
                    file_path=cls.file_path,
                    evidence=f"Methods={method_count}, WMC={wmc}",
                    tool_name=ANALYZER_NAME,
                    tool_version=ANALYZER_VERSION,
                )
            )

    # 3. Deep Nesting & Long Parameter Lists (for Python AST)
    for f in files:
        if f.language == "Python":
            try:
                tree = ast.parse(f.absolute_path.read_text(encoding="utf-8", errors="replace"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Long parameter list
                        param_count = len(node.args.args)
                        if param_count > 5:
                            findings.append(
                                Finding(
                                    rule_id="SMELL-LONG-PARAM-LIST",
                                    category="smell",
                                    severity="low",
                                    confidence="high",
                                    message=f"Function '{node.name}' has {param_count} parameters (threshold: 5).",
                                    file_path=f.relative_path,
                                    line_start=node.lineno,
                                    evidence=f"Params={param_count}",
                                    tool_name=ANALYZER_NAME,
                                    tool_version=ANALYZER_VERSION,
                                )
                            )

                        # Deep nesting check
                        def _get_max_nesting(n: ast.AST, current_depth: int) -> int:
                            max_d = current_depth
                            is_block = isinstance(n, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.Try, ast.With))
                            next_d = current_depth + 1 if is_block else current_depth
                            for child in ast.iter_child_nodes(n):
                                max_d = max(max_d, _get_max_nesting(child, next_d))
                            return max_d

                        nesting = _get_max_nesting(node, 0)
                        if nesting > 4:
                            findings.append(
                                Finding(
                                    rule_id="SMELL-DEEP-NESTING",
                                    category="smell",
                                    severity="medium",
                                    confidence="high",
                                    message=f"Function '{node.name}' has nesting depth of {nesting} (threshold: 4).",
                                    file_path=f.relative_path,
                                    line_start=node.lineno,
                                    evidence=f"NestingDepth={nesting}",
                                    tool_name=ANALYZER_NAME,
                                    tool_version=ANALYZER_VERSION,
                                )
                            )
            except Exception:
                pass

    smell_count = float(len(findings))

    metrics = [
        MetricResult(
            name="code_smell_count",
            category="quality",
            value=smell_count,
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Total code smells detected (Long Method, God Class, Deep Nesting, Long Params).",
        ),
        MetricResult(
            name="technical_debt_ratio",
            category="quality",
            value=round(smell_count / max(len(files), 1), 2),
            unit="ratio",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Average detected smells per source file.",
        ),
    ]

    return findings, metrics
