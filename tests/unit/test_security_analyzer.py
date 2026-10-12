"""Unit tests for security analysis and secrets redaction."""

from pathlib import Path
from sem_cli.analyzers.security_analyzer import SecurityAnalyzer, redact_secret_string
from sem_cli.repository.models import FileItem, RepositorySnapshot


def test_redact_secret_string():
    secret = "AKIAIOSFODNN7EXAMPLE"
    redacted = redact_secret_string(secret)
    assert redacted.startswith("AKI")
    assert redacted.endswith("PLE")
    assert "*" in redacted
    assert "IOSFODNN7EXAM" not in redacted


def test_detect_aws_key_and_eval(tmp_path: Path):
    f = tmp_path / "unsafe.py"
    f.write_text(
        'AWS_KEY = "AKIA1234567890ABCDEF"\n'
        'def unsafe_eval(code):\n'
        '    eval(code)\n',
        encoding="utf-8",
    )

    snapshot = RepositorySnapshot(
        run_id="test_run",
        normalized_url="file://test",
        display_name="test",
        workspace_path=tmp_path,
        requested_ref=None,
        commit_sha="a" * 40,
        default_branch="main",
        is_shallow=False,
        files=[FileItem("unsafe.py", f, "Python", 100, is_test=False)],
    )

    analyzer = SecurityAnalyzer()
    metrics, findings = analyzer.analyze(snapshot)

    rule_ids = [f.rule_id for f in findings]
    assert "SEC-AWS-KEY" in rule_ids
    assert "SEC-EVAL-EXEC" in rule_ids

    # Verify secret is redacted in findings evidence
    aws_finding = next(f for f in findings if f.rule_id == "SEC-AWS-KEY")
    assert "1234567890" not in aws_finding.evidence
    assert "*" in aws_finding.evidence
