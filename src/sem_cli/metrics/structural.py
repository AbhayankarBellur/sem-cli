"""Structural and object-oriented metrics (CK Suite, Fan-in/out, Circular dependencies)."""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from sem_cli.metrics.schema import MetricResult
from sem_cli.repository.models import FileItem

ANALYZER_NAME = "sem-structural-engine"
ANALYZER_VERSION = "1.0.0"
FORMULA_VERSION = "2026.1"


@dataclass
class ClassStructure:
    name: str
    file_path: str
    base_classes: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    method_complexities: dict[str, int] = field(default_factory=dict)
    field_accesses: dict[str, set[str]] = field(default_factory=dict)  # method -> {self.attr}
    external_types: set[str] = field(default_factory=set)
    invoked_methods: set[str] = field(default_factory=set)


@dataclass
class FileImports:
    file_path: str
    imported_modules: set[str] = field(default_factory=set)
    total_imports_count: int = 0


def extract_python_classes_and_imports(file_path: Path, rel_path: str) -> tuple[list[ClassStructure], FileImports]:
    """Parse Python AST to extract Class structures and import relationships."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content)
    except Exception:
        return [], FileImports(rel_path)

    classes: list[ClassStructure] = []
    imports = FileImports(rel_path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.imported_modules.add(alias.name.split(".")[0])
                imports.total_imports_count += 1
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.imported_modules.add(node.module.split(".")[0])
            imports.total_imports_count += len(node.names)

    # Class visitor
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            cs = ClassStructure(name=node.name, file_path=rel_path)
            for b in node.bases:
                if isinstance(b, ast.Name):
                    cs.base_classes.append(b.id)
                elif isinstance(b, ast.Attribute):
                    cs.base_classes.append(b.attr)

            # Analyze class methods
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_name = item.name
                    cs.methods.append(m_name)
                    # Rough complexity of method
                    m_cc = 1
                    accessed_attrs: set[str] = set()
                    for sub in ast.walk(item):
                        if isinstance(sub, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                            m_cc += 1
                        elif isinstance(sub, ast.Attribute):
                            if isinstance(sub.value, ast.Name) and sub.value.id == "self":
                                accessed_attrs.add(sub.attr)
                        elif isinstance(sub, ast.Call):
                            if isinstance(sub.func, ast.Name):
                                cs.invoked_methods.add(sub.func.id)
                            elif isinstance(sub.func, ast.Attribute):
                                cs.invoked_methods.add(sub.func.attr)

                    cs.method_complexities[m_name] = m_cc
                    cs.field_accesses[m_name] = accessed_attrs

            classes.append(cs)

    return classes, imports


def calculate_lcom4(cs: ClassStructure) -> int:
    """Calculate Lack of Cohesion in Methods (LCOM4).

    LCOM4 is the number of connected components in the graph where nodes are methods
    and an edge exists between two methods if they share access to an instance variable.
    """
    if len(cs.methods) <= 1:
        return 1

    methods = [m for m in cs.methods if not m.startswith("__")]
    if not methods:
        return 1

    # Build adjacency
    adj: dict[str, set[str]] = {m: set() for m in methods}
    for i in range(len(methods)):
        m1 = methods[i]
        attrs1 = cs.field_accesses.get(m1, set())
        for j in range(i + 1, len(methods)):
            m2 = methods[j]
            attrs2 = cs.field_accesses.get(m2, set())
            if attrs1 & attrs2:  # Share attribute
                adj[m1].add(m2)
                adj[m2].add(m1)

    # Count connected components
    visited: set[str] = set()
    components = 0

    for m in methods:
        if m not in visited:
            components += 1
            stack = [m]
            visited.add(m)
            while stack:
                curr = stack.pop()
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)

    return max(1, components)


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Detect circular dependencies (elementary cycles) in a directed graph."""
    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: list[str] = []

    def dfs(node: str) -> None:
        visited.add(node)
        rec_stack.append(node)

        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in rec_stack:
                # Cycle detected
                cycle_start = rec_stack.index(neighbor)
                cycle = rec_stack[cycle_start:] + [neighbor]
                if len(cycle) > 2 and cycle not in cycles:
                    cycles.append(cycle)

        rec_stack.pop()

    for node in list(graph.keys()):
        if node not in visited:
            dfs(node)

    return cycles


def compute_structural_metrics(
    files: list[FileItem],
) -> tuple[list[MetricResult], list[ClassStructure], list[list[str]]]:
    """Compute structural, OO, coupling, fan-in/fan-out, and circular dependency metrics."""
    all_classes: list[ClassStructure] = []
    file_imports_map: dict[str, FileImports] = {}

    for f in files:
        if f.language == "Python":
            cls_list, f_imp = extract_python_classes_and_imports(f.absolute_path, f.relative_path)
            all_classes.extend(cls_list)
            file_imports_map[f.relative_path] = f_imp
        elif f.language in ("JavaScript", "TypeScript"):
            # Lightweight regex-based import extraction for JS/TS
            f_imp = FileImports(f.relative_path)
            try:
                txt = f.absolute_path.read_text(encoding="utf-8", errors="replace")
                import re
                matches = re.findall(r'(?:import|from|require\()\s*[\'"]([^\'"]+)[\'"]', txt)
                for m in matches:
                    f_imp.imported_modules.add(m.split("/")[-1].replace(".js", "").replace(".ts", ""))
                    f_imp.total_imports_count += 1
            except Exception:
                pass
            file_imports_map[f.relative_path] = f_imp

    # Class inheritance tree & children
    children_count: dict[str, int] = defaultdict(int)
    for c in all_classes:
        for b in c.base_classes:
            children_count[b] += 1

    metrics: list[MetricResult] = []

    # CK metrics per class
    wmc_list: list[float] = []
    lcom_list: list[float] = []
    dit_list: list[float] = []
    cbo_list: list[float] = []

    for c in all_classes:
        wmc = float(sum(c.method_complexities.values()))
        wmc_list.append(wmc)

        dit = float(len(c.base_classes))  # Direct inheritance depth
        dit_list.append(dit)

        noc = float(children_count.get(c.name, 0))

        # CBO: Coupling between objects
        cbo = float(len(c.base_classes) + len(c.external_types))
        cbo_list.append(cbo)

        # RFC: Response for a class (methods + distinct calls)
        rfc = float(len(c.methods) + len(c.invoked_methods))

        # LCOM4
        lcom4 = float(calculate_lcom4(c))
        lcom_list.append(lcom4)

        metrics.extend([
            MetricResult(
                name="wmc",
                category="structural",
                value=wmc,
                unit="count",
                scope_type="class",
                scope_key=f"{c.file_path}::{c.name}",
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation="Weighted Methods per Class (sum of method complexities).",
            ),
            MetricResult(
                name="cbo",
                category="structural",
                value=cbo,
                unit="count",
                scope_type="class",
                scope_key=f"{c.file_path}::{c.name}",
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation="Coupling Between Objects (dependencies on other classes).",
            ),
            MetricResult(
                name="lcom4",
                category="structural",
                value=lcom4,
                unit="components",
                scope_type="class",
                scope_key=f"{c.file_path}::{c.name}",
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation="Lack of Cohesion in Methods (LCOM4 connected components).",
            ),
            MetricResult(
                name="dit",
                category="structural",
                value=dit,
                unit="levels",
                scope_type="class",
                scope_key=f"{c.file_path}::{c.name}",
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation="Depth of Inheritance Tree.",
            ),
            MetricResult(
                name="noc",
                category="structural",
                value=noc,
                unit="count",
                scope_type="class",
                scope_key=f"{c.file_path}::{c.name}",
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation="Number of Children (immediate subclasses).",
            ),
            MetricResult(
                name="rfc",
                category="structural",
                value=rfc,
                unit="count",
                scope_type="class",
                scope_key=f"{c.file_path}::{c.name}",
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation="Response for a Class (methods + external calls).",
            ),
        ])

    # Module-level dependency graph (internal fan-in, fan-out, cycles)
    # Map module stem/names to files
    module_to_file: dict[str, str] = {}
    for f in files:
        stem = Path(f.relative_path).stem
        module_to_file[stem] = f.relative_path

    internal_graph: dict[str, set[str]] = defaultdict(set)
    fan_in: dict[str, int] = defaultdict(int)
    fan_out: dict[str, int] = defaultdict(int)

    for f_path, imp in file_imports_map.items():
        stem = Path(f_path).stem
        for mod in imp.imported_modules:
            if mod in module_to_file and module_to_file[mod] != f_path:
                target_f = module_to_file[mod]
                internal_graph[f_path].add(target_f)
                fan_out[f_path] += 1
                fan_in[target_f] += 1

    # File-level structural metrics
    for f in files:
        f_p = f.relative_path
        f_in = float(fan_in.get(f_p, 0))
        f_out = float(fan_out.get(f_p, 0))
        dep_count = float(file_imports_map.get(f_p, FileImports(f_p)).total_imports_count)

        metrics.extend([
            MetricResult(
                name="fan_in",
                category="structural",
                value=f_in,
                unit="count",
                scope_type="file",
                scope_key=f_p,
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation="Number of other internal modules importing this file.",
            ),
            MetricResult(
                name="fan_out",
                category="structural",
                value=f_out,
                unit="count",
                scope_type="file",
                scope_key=f_p,
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation="Number of internal modules this file imports.",
            ),
            MetricResult(
                name="dependency_count",
                category="structural",
                value=dep_count,
                unit="count",
                scope_type="file",
                scope_key=f_p,
                analyzer=ANALYZER_NAME,
                analyzer_version=ANALYZER_VERSION,
                formula_version=FORMULA_VERSION,
                status="measured",
                explanation="Total import statements in file.",
            ),
        ])

    # Circular dependencies
    detected_cycles = find_cycles(internal_graph)
    cycle_count = float(len(detected_cycles))

    # Repository-level structural summaries
    total_classes = float(len(all_classes))
    avg_wmc = round(sum(wmc_list) / max(len(wmc_list), 1), 2) if wmc_list else 0.0
    avg_cbo = round(sum(cbo_list) / max(len(cbo_list), 1), 2) if cbo_list else 0.0
    avg_lcom = round(sum(lcom_list) / max(len(lcom_list), 1), 2) if lcom_list else 1.0

    metrics.extend([
        MetricResult(
            name="class_count",
            category="structural",
            value=total_classes,
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Total object-oriented class declarations.",
        ),
        MetricResult(
            name="avg_wmc",
            category="structural",
            value=avg_wmc,
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Average Weighted Methods per Class.",
        ),
        MetricResult(
            name="avg_cbo",
            category="structural",
            value=avg_cbo,
            unit="count",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Average Coupling Between Objects.",
        ),
        MetricResult(
            name="avg_lcom4",
            category="structural",
            value=avg_lcom,
            unit="components",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Average Lack of Cohesion in Methods (LCOM4).",
        ),
        MetricResult(
            name="circular_dependency_count",
            category="structural",
            value=cycle_count,
            unit="cycles",
            scope_type="repository",
            scope_key="repository",
            analyzer=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            formula_version=FORMULA_VERSION,
            status="measured",
            explanation="Detected circular import cycles between modules.",
        ),
    ])

    return metrics, all_classes, detected_cycles
