from __future__ import annotations

from datetime import date

from vrm.engine.evidence import EvidenceFinding, check_evidence_coverage
from vrm.models.enums import EvidenceType, RiskSource, RiskStatus
from vrm.models.evidence import EvidenceLink
from vrm.models.risk import Risk


def _risk(
    rid: str = "acme-F1",
    status: RiskStatus = RiskStatus.OPEN,
) -> Risk:
    return Risk(
        risk_id=rid,
        vendor_id="acme",
        ref="F1",
        source=RiskSource.ASSESSMENT_REPORT,
        title="Test",
        status=status,
    )


def _evidence(
    eid: str = "ev-1",
    rid: str = "acme-F1",
    expiry: date | None = None,
) -> EvidenceLink:
    return EvidenceLink(
        evidence_id=eid,
        risk_id=rid,
        vendor_id="acme",
        evidence_type=EvidenceType.REPORT,
        title="Pen test report",
        location="https://sharepoint/docs/report.pdf",
        expiry_date=expiry,
    )


class TestEvidenceCoverage:
    def test_no_evidence_flagged(self) -> None:
        risk = _risk()
        findings = check_evidence_coverage([risk], [])
        no_ev = [f for f in findings if f.finding_type == "no_evidence"]
        assert len(no_ev) == 1

    def test_with_evidence_no_finding(self) -> None:
        risk = _risk()
        ev = _evidence()
        findings = check_evidence_coverage([risk], [ev])
        no_ev = [f for f in findings if f.finding_type == "no_evidence"]
        assert len(no_ev) == 0

    def test_expired_evidence_flagged(self) -> None:
        risk = _risk()
        ev = _evidence(expiry=date(2024, 1, 1))
        findings = check_evidence_coverage([risk], [ev], today=date(2024, 6, 1))
        expired = [f for f in findings if f.finding_type == "evidence_expired"]
        assert len(expired) == 1

    def test_valid_evidence_not_flagged(self) -> None:
        risk = _risk()
        ev = _evidence(expiry=date(2025, 12, 31))
        findings = check_evidence_coverage([risk], [ev], today=date(2024, 6, 1))
        expired = [f for f in findings if f.finding_type == "evidence_expired"]
        assert len(expired) == 0

    def test_closed_risk_skipped(self) -> None:
        risk = _risk(status=RiskStatus.CLOSED)
        findings = check_evidence_coverage([risk], [])
        assert len(findings) == 0

    def test_stale_risk_skipped(self) -> None:
        risk = _risk(status=RiskStatus.STALE)
        findings = check_evidence_coverage([risk], [])
        assert len(findings) == 0
