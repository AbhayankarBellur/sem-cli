"""Unit tests for product and size metrics."""

from pathlib import Path
from sem_cli.metrics.product import count_lines_detailed, compute_file_product_metrics, compute_repository_product_metrics
from sem_cli.repository.models import FileItem


def test_count_lines_python(tmp_path: Path):
    sample = tmp_path / "sample.py"
    sample.write_text(
        "# Comment line 1\n"
        "\n"
        "def foo():\n"
        "    # Inside comment\n"
        "    x = 1\n"
        "    return x\n",
        encoding="utf-8",
    )
    loc, sloc, blank, comments = count_lines_detailed(sample, "Python")
    assert loc == 6
    assert blank == 1
    assert comments == 2
    assert sloc == 3


def test_count_lines_javascript(tmp_path: Path):
    sample = tmp_path / "sample.js"
    sample.write_text(
        "// JS Single line comment\n"
        "/* Multiline\n"
        "   comment */\n"
        "\n"
        "function hello() {\n"
        "  return 'world';\n"
        "}\n",
        encoding="utf-8",
    )
    loc, sloc, blank, comments = count_lines_detailed(sample, "JavaScript")
    assert loc == 7
    assert blank == 1
    assert comments == 3
    assert sloc == 3


def test_compute_repository_product_metrics(tmp_path: Path):
    f1 = tmp_path / "src.py"
    f1.write_text("a = 1\nb = 2\n", encoding="utf-8")
    f2 = tmp_path / "test_src.py"
    f2.write_text("assert True\n", encoding="utf-8")

    items = [
        FileItem("src.py", f1, "Python", 10, is_test=False),
        FileItem("test_src.py", f2, "Python", 10, is_test=True),
    ]

    m1 = compute_file_product_metrics(items[0])
    m2 = compute_file_product_metrics(items[1])

    repo_m = compute_repository_product_metrics(items, m1 + m2)
    m_dict = {m.name: m.value for m in repo_m}

    assert m_dict["total_loc"] == 3.0
    assert m_dict["total_sloc"] == 3.0
    assert m_dict["file_count"] == 2.0
    assert m_dict["test_to_source_ratio"] == 0.5  # 1 test SLOC / 2 prod SLOC
