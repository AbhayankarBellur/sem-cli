"""Unit tests for structural OO metrics and circular dependency detection."""

from pathlib import Path
from sem_cli.metrics.structural import (
    calculate_lcom4,
    compute_structural_metrics,
    find_cycles,
)
from sem_cli.repository.models import FileItem


def test_find_cycles_graph():
    graph = {
        "A": {"B"},
        "B": {"C"},
        "C": {"A"},
        "D": {"A"},
    }
    cycles = find_cycles(graph)
    assert len(cycles) > 0
    cycle_nodes = set(cycles[0])
    assert {"A", "B", "C"}.issubset(cycle_nodes)


def test_structural_oo_metrics(tmp_path: Path):
    f = tmp_path / "models.py"
    f.write_text(
        "class BaseEntity:\n"
        "    def save(self):\n"
        "        pass\n"
        "\n"
        "class User(BaseEntity):\n"
        "    def __init__(self, name):\n"
        "        self.name = name\n"
        "    def get_name(self):\n"
        "        return self.name\n",
        encoding="utf-8",
    )

    items = [FileItem("models.py", f, "Python", 100, is_test=False)]
    metrics, classes, cycles = compute_structural_metrics(items)

    class_names = [c.name for c in classes]
    assert "BaseEntity" in class_names
    assert "User" in class_names

    user_cls = next(c for c in classes if c.name == "User")
    assert "BaseEntity" in user_cls.base_classes

    m_dict = {f"{m.scope_key}:{m.name}": m.value for m in metrics}
    assert m_dict["models.py::User:dit"] == 1.0
    assert m_dict["models.py::BaseEntity:noc"] == 1.0  # User inherits from BaseEntity
