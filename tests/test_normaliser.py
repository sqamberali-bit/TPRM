from __future__ import annotations

import pytest

from vrm.engine.normaliser import derive_status, risks_from_report, slugify
from vrm.models.enums import Rating, RiskSource, RiskStatus
from vrm.parsers.word_report import Finding, ParsedReport, ResidualRisk


def test_slugify() -> None:
    assert slugify("Acme Corp Pty Ltd") == "acme-corp-pty-ltd"
    assert slugify("  Pet Loyalty  ") == "pet-loyalty"
    assert slugify("ISO-27001") == "iso-27001"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("accepted", RiskStatus.ACCEPTED),
        ("Accepted until December 2025", RiskStatus.ACCEPTED_TIMEBOXED),
        ("time-boxed acceptance", RiskStatus.ACCEPTED_TIMEBOXED),
        ("closed", RiskStatus.CLOSED),
        ("resolved", RiskStatus.RESOLVED),
        ("removed", RiskStatus.REMOVED),
        ("withdrawn", RiskStatus.WITHDRAWN),
        ("reverts to High if clause not executed", RiskStatus.CONTINGENT),
        ("Reverts if clause F9 not executed", RiskStatus.CONTINGENT),
        ("in progress", RiskStatus.IN_TREATMENT),
        ("in treatment", RiskStatus.IN_TREATMENT),
        ("open", RiskStatus.OPEN),
        ("something unexpected", RiskStatus.OPEN),
    ],
)
def test_derive_status(text: str, expected: RiskStatus) -> None:
    assert derive_status(text) == expected


def test_risks_from_report_basic() -> None:
    report = ParsedReport(
        source_file="test.docx",
        vendor_name="Test Vendor",
        findings=[
            Finding(ref="F1", title="No MFA", rating="High", basis="Missing MFA"),
        ],
        residual_risks=[
            ResidualRisk(
                ref="F1",
                title="No MFA residual",
                compensating_controls="IP whitelist",
                rating="Medium",
                duration_or_trigger="Accepted until Dec 2025",
            ),
        ],
    )

    risks = risks_from_report(report, "test-vendor")
    assert len(risks) == 1

    r = risks[0]
    assert r.risk_id == "test-vendor-F1"
    assert r.source == RiskSource.ASSESSMENT_REPORT
    assert r.inherent_rating == Rating.HIGH
    assert r.residual_rating == Rating.MEDIUM
    assert r.status == RiskStatus.ACCEPTED_TIMEBOXED
    assert r.compensating_controls == "IP whitelist"


def test_risks_from_report_contingent() -> None:
    report = ParsedReport(
        source_file="test.docx",
        findings=[
            Finding(ref="F2", title="Unencrypted", rating="Medium", basis=""),
        ],
        residual_risks=[
            ResidualRisk(
                ref="F2",
                title="Data unencrypted",
                rating="Low",
                duration_or_trigger="Reverts to High if clause F9 not executed",
            ),
        ],
    )

    risks = risks_from_report(report, "vendor-x")
    assert len(risks) == 1
    r = risks[0]
    assert r.status == RiskStatus.CONTINGENT
    assert r.contingency_reverts_to == Rating.HIGH


def test_risks_from_report_residual_only() -> None:
    report = ParsedReport(
        source_file="test.docx",
        findings=[],
        residual_risks=[
            ResidualRisk(ref="R1", title="Extra risk", rating="Low"),
        ],
    )

    risks = risks_from_report(report, "vendor-y")
    assert len(risks) == 1
    assert risks[0].risk_id == "vendor-y-R1"
