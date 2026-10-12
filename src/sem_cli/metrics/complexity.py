"""Complexity and maintainability metrics (Cyclomatic Complexity, Halstead, MI, Bands)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from sem_cli.metrics.schema import MetricResult
from sem_cli.repository.models import FileItem

ANALYZER_NAME = "sem-complexity-engine"
ANALYZER_VERSION = "1.0.0"
FORMULA_VERSION = "2026.1"


@dataclass(frozen=True)
class FunctionComplexity:
    name: str
    file_path: str
    line_start: int
    cyclomatic_complexity: int
    nloc: int


@dataclass(frozen=True)
class HalsteadReport:
    volume: float
    difficulty: float
    effort: float
    bugs: float
    vocabulary: int
    length: int


def calculate_halstead_from_counts(
    n1_distinct_operators: int,
    n2_distinct_operands: int,
    N1_total_operators: int,
    N2_total_operands: int,
) -> HalsteadReport:
    """Calculate Halstead software science metrics from operator and operand counts."""
    vocab = n1_distinct_operators + n2_distinct_operands
    length = N1_total_operators + N2_total_operands

    if vocab <= 1 or length <= 0:
        return HalsteadReport(0.0, 0.0, 0.0, 0.0, vocab, length)

    volume = length * math.log2(vocab)
    difficulty = (n1_distinct_operators / 2.0) * (N2_total_operands / max(n2_distinct_operands, 1))
    effort = difficulty * volume
    bugs = volume / 3000.0

    return HalsteadReport(
        volume=round(volume, 2),
        difficulty=round(difficulty, 2),
        effort=round(effort, 2),
        bugs=round(bugs, 4),
        vocabulary=vocab,
        length=length,
    )


def calculate_maintainability_index(
    halstead_volume: float,
    cyclomatic_complexity: float,
    sloc: float,
    comment_percentage: float = 0.0,
) -> float:
    """Calculate normalized Maintainability Index (0 - 100 scale).

    Based on the SEI/Radon variant:
    raw_mi = 171 - 5.2 * ln(V) - 0.23 * CC - 16.2 * ln(LOC) + 50 * sin(sqrt(2.4 * C))
    scaled to [0, 100].
    """
    v = max(halstead_volume, 1.0)
    loc = max(sloc, 1.0)
    c = min(max(comment_percentage, 0.0), 1.0)

    raw_mi = 171.0 - 5.2 * math.log(v) - 0.23 * cyclomatic_complexity - 16.2 * math.log(loc)
    if c > 0:
        raw_mi += 50.0 * math.sin(math.sqrt(2.4 * c))

    normalized_mi = max(0.0, min(100.0, raw_mi * 100.0 / 171.0))
    return round(normalized_mi, 2)


def compute_python_complexity(file_path: Path, rel_path: str) -> tuple[list[FunctionComplexity], HalsteadReport, float]:
    """Calculate Cyclomatic Complexity and Halstead for a Python file using Radon/AST."""
    try:
        from radon.complexity import cc_visit
        from radon.raw import analyze as raw_analyze
        from radon.metrics import h_visit
    except ImportError:
        return _fallback_complexity_python(file_path, rel_path)

    try:
        code = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return [], HalsteadReport(0.0, 0.0, 0.0, 0.0, 0, 0), 0.0

    func_list: list[FunctionComplexity] = []
    try:
        blocks = cc_visit(code)
        for b in blocks:
            func_list.append(
                FunctionComplexity(
                    name=b.name,
                    file_path=rel_path,
                    line_start=b.lineno,
                    cyclomatic_complexity=b.complexity,
                    nloc=getattr(b, "endline", b.lineno) - b.lineno + 1,
                )
            )
    except Exception:
        pass

    # Halstead
    try:
        h_res = h_visit(code)
        halstead = HalsteadReport(
            volume=round(h_res.total.volume, 2),
            difficulty=round(h_res.total.difficulty, 2),
            effort=round(h_res.total.effort, 2),
            bugs=round(h_res.total.bugs, 4),
            vocabulary=h_res.total.vocabulary,
            length=h_res.total.length,
        )
    except Exception:
        halstead = HalsteadReport(0.0, 0.0, 0.0, 0.0, 0, 0)

    # Maintainability index
    avg_cc = sum(f.cyclomatic_complexity for f in func_list) / max(len(func_list), 1) if func_list else 1.0
    try:
        raw_stats = raw_analyze(code)
        sloc = raw_stats.sloc
        com_ratio = raw_stats.comments / max(raw_stats.sloc, 1)
    except Exception:
        sloc = max(len(code.splitlines()), 1)
        com_ratio = 0.0

    mi = calculate_maintainability_index(halstead.volume, avg_cc, float(sloc), com_ratio)
    return func_list, halstead, mi


def compute_lizard_complexity(file_path: Path, rel_path: str) -> tuple[list[FunctionComplexity], HalsteadReport, float]:
    """Compute complexity using Lizard for JS, TS, Java, C/C++, Go, etc."""
    try:
        import lizard
    except ImportError:
        return [], HalsteadReport(0.0, 0.0, 0.0, 0.0, 0, 0), 50.0

    func_list: list[FunctionComplexity] = []
    try:
        analysis = lizard.analyze_file(str(file_path))
        for f in analysis.function_list:
            func_list.append(
                FunctionComplexity(
                    name=f.name,
                    file_path=rel_path,
                    line_start=f.start_line,
                    cyclomatic_complexity=f.cyclomatic_complexity,
                    nloc=f.nloc,
                )
            )
        sloc = analysis.nloc
        avg_cc = analysis.average_cyclomatic_complexity or 1.0
    except Exception:
        return [], HalsteadReport(0.0, 0.0, 0.0, 0.0, 0, 0), 50.0

    # Approximate Halstead from tokens
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        words = text.split()
        distinct_words = len(set(words))
        halstead = calculate_halstead_from_counts(
            min(distinct_words // 2, 50),
            max(distinct_words - min(distinct_words // 2, 50), 1),
            len(words) // 2,
            len(words) - len(words) // 2,
        )
    except Exception:
        halstead = HalsteadReport(0.0, 0.0, 0.0, 0.0, 0, 0)

    mi = calculate_maintainability_index(halstead.volume, avg_cc, float(sloc), 0.1)
    return func_list, halstead, mi


def _fallback_complexity_python(file_path: Path, rel_path: str) -> tuple[list[FunctionComplexity], HalsteadReport, float]:
    """AST-based Python complexity when Radon is unavailable."""
    import ast

    try:
        code = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(code)
    except Exception:
        return [], HalsteadReport(0.0, 0.0, 0.0, 0.0, 0, 0), 0.0

    func_list: list[FunctionComplexity] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Count branching nodes
            branches = 1
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.Assert)):
                    branches += 1
                elif isinstance(child, ast.BoolOp):
                    branches += len(child.values) - 1
            func_list.append(
                FunctionComplexity(
                    name=node.name,
                    file_path=rel_path,
                    line_start=node.lineno,
                    cyclomatic_complexity=branches,
                    nloc=10,
                )
            )

    avg_cc = sum(f.cyclomatic_complexity for f in func_list) / max(len(func_list), 1) if func_list else 1.0
    sloc = len([l for l in code.splitlines() if l.strip()])
    halstead = calculate_halstead_from_counts(15, 25, sloc * 3, sloc * 4)
    mi = calculate_maintainability_index(halstead.volume, avg_cc, float(sloc), 0.1)
    return func_list, halstead, mi


def compute_file_complexity_metrics(
    file_item: FileItem,
) -> tuple[list[MetricResult], list[FunctionComplexity]]:
    """Compute complexity metrics for a single file and return (metrics, functions)."""
    lang = file_item.language
    func_list: list[FunctionComplexity] = []
    halstead = HalsteadReport(0.0, 0.0, 0.0, 0.0, 0, 0)
    mi = 50.0

    if lang == "Python":
        func_list, halstead, mi = compute_python_complexity(file_item.absolute_path, file_item.relative_path)
    elif lang in ("JavaScript", "TypeScript", "JavaScript (React)", "TypeScript (React)", "Go", "Rust", "Java", "C", "C++"):
        func_list, halstead, mi = compute_lizard_complexity(file_item.absolute_path, file_item.relative_path)
    else:
        # Unsupported language for AST complexity
        return [
            MetricResult(
                name="cyclomatic_complexity",
                category="complexity",
                value=None,
                unit="count",
                scope_type="file",
                scope_key=file_item.relative_path,
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="unsupported",
                explanation=f"Complexity analysis unsupported for language '{lang}'.",
            )
        ], []

    avg_cc = round(sum(f.cyclomatic_complexity for f in func_list) / max(len(func_list), 1), 2) if func_list else 1.0
    max_cc = max((f.cyclomatic_complexity for f in func_list), default=1)

    metrics = [
        MetricResult(
            name="file_avg_cyclomatic_complexity",
            category="complexity",
            value=float(avg_cc),
            unit="count",
            scope_type="file",
            scope_key=file_item.relative_path,
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Average cyclomatic complexity across functions in file.",
        ),
        MetricResult(
            name="file_max_cyclomatic_complexity",
            category="complexity",
            value=float(max_cc),
            unit="count",
            scope_type="file",
            scope_key=file_item.relative_path,
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Maximum cyclomatic complexity of any function in file.",
        ),
        MetricResult(
            name="maintainability_index",
            category="complexity",
            value=float(mi),
            unit="score",
            scope_type="file",
            scope_key=file_item.relative_path,
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Maintainability Index (0-100, higher indicates better maintainability).",
        ),
        MetricResult(
            name="halstead_volume",
            category="complexity",
            value=float(halstead.volume),
            unit="bits",
            scope_type="file",
            scope_key=file_item.relative_path,
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Halstead volume based on operator and operand vocabulary.",
        ),
        MetricResult(
            name="halstead_effort",
            category="complexity",
            value=float(halstead.effort),
            unit="effort",
            scope_type="file",
            scope_key=file_item.relative_path,
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Halstead effort score combining difficulty and volume.",
        ),
    ]

    # Function-level metrics
    for fn in func_list:
        metrics.append(
            MetricResult(
                name="cyclomatic_complexity",
                category="complexity",
                value=float(fn.cyclomatic_complexity),
                unit="count",
                scope_type="function",
                scope_key=f"{fn.file_path}::{fn.name}",
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation=f"Function complexity (line {fn.line_start}).",
            )
        )

    return metrics, func_list


def compute_repository_complexity_metrics(
    all_functions: list[FunctionComplexity],
    file_complexity_metrics: list[MetricResult],
    complexity_threshold: int = 10,
) -> list[MetricResult]:
    """Aggregate repository-level complexity distributions and indicators."""
    total_funcs = len(all_functions)
    if total_funcs == 0:
        return [
            MetricResult(
                name="function_count",
                category="complexity",
                value=0.0,
                unit="count",
                scope_type="repository",
                scope_key="repository",
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation="Total recognized functions.",
            ),
            MetricResult(
                name="high_complexity_function_count",
                category="complexity",
                value=0.0,
                unit="count",
                scope_type="repository",
                scope_key="repository",
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation="Functions exceeding complexity threshold.",
            ),
        ]

    ccs = [f.cyclomatic_complexity for f in all_functions]
    ccs.sort()
    avg_cc = round(sum(ccs) / total_funcs, 2)
    max_cc = max(ccs)
    median_cc = float(ccs[total_funcs // 2]) if total_funcs % 2 == 1 else round((ccs[total_funcs // 2 - 1] + ccs[total_funcs // 2]) / 2.0, 2)

    # Bands
    band_low = sum(1 for c in ccs if c <= 5)
    band_moderate = sum(1 for c in ccs if 6 <= c <= 10)
    band_high = sum(1 for c in ccs if 11 <= c <= 20)
    band_very_high = sum(1 for c in ccs if c >= 21)
    high_complexity_count = sum(1 for c in ccs if c > complexity_threshold)

    # Repository average MI
    mi_values = [m.value for m in file_complexity_metrics if m.name == "maintainability_index" and m.value is not None]
    avg_mi = round(sum(mi_values) / max(len(mi_values), 1), 2) if mi_values else 50.0

    return [
        MetricResult(
            name="function_count",
            category="complexity",
            value=float(total_funcs),
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Total recognized functions and methods.",
        ),
        MetricResult(
            name="avg_function_complexity",
            category="complexity",
            value=float(avg_cc),
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Average function cyclomatic complexity.",
        ),
        MetricResult(
            name="median_function_complexity",
            category="complexity",
            value=float(median_cc),
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Median function cyclomatic complexity.",
        ),
        MetricResult(
            name="max_function_complexity",
            category="complexity",
            value=float(max_cc),
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Maximum cyclomatic complexity of any function.",
        ),
        MetricResult(
            name="high_complexity_function_count",
            category="complexity",
            value=float(high_complexity_count),
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation=f"Functions with CC > {complexity_threshold}.",
        ),
        MetricResult(
            name="complexity_band_low_count",
            category="complexity",
            value=float(band_low),
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Functions in Low Complexity band (1-5).",
        ),
        MetricResult(
            name="complexity_band_moderate_count",
            category="complexity",
            value=float(band_moderate),
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Functions in Moderate Complexity band (6-10).",
        ),
        MetricResult(
            name="complexity_band_high_count",
            category="complexity",
            value=float(band_high),
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Functions in High Complexity band (11-20).",
        ),
        MetricResult(
            name="complexity_band_very_high_count",
            category="complexity",
            value=float(band_very_high),
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Functions in Very High Complexity band (21+).",
        ),
        MetricResult(
            name="avg_maintainability_index",
            category="complexity",
            value=float(avg_mi),
            unit="score",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Mean repository maintainability index (0-100).",
        ),
    ]
