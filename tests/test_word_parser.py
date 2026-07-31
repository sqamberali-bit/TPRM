from __future__ import annotations

from pathlib import Path

import pytest

from vrm.parsers.word_report import (
    Finding,
    OutstandingItem,
    ParsedReport,
    ResidualRisk,
    parse_report,
)


@pytest.fixture
def sample_report(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "sample_report.docx"
    if not path.exists():
        pytest.skip("Run 'python tests/create_fixtures.py' first")
    return path


def test_parse_extracts_findings(sample_report: Path) -> None:
    result = parse_report(sample_report)
    assert len(result.findings) == 3
    assert result.findings[0].ref == "F1"
    assert result.findings[0].rating == "High"
    assert "MFA" in result.findings[0].title


def test_parse_extracts_residual_risks(sample_report: Path) -> None:
    result = parse_report(sample_report)
    assert len(result.residual_risks) == 3
    assert result.residual_risks[0].ref == "F1"
    assert result.residual_risks[0].rating == "Medium"
    assert "IP whitelist" in result.residual_risks[0].compensating_controls


def test_parse_extracts_outstanding_items(sample_report: Path) -> None:
    result = parse_report(sample_report)
    assert len(result.outstanding_items) == 2
    assert result.outstanding_items[0].ref == "F1"
    assert result.outstanding_items[0].status == "In progress"


def test_parse_extracts_vendor_name(sample_report: Path) -> None:
    result = parse_report(sample_report)
    assert result.vendor_name == "Acme Corp Security Assessment"


def test_parse_sets_source_file(sample_report: Path) -> None:
    result = parse_report(sample_report)
    assert result.source_file == "sample_report.docx"
