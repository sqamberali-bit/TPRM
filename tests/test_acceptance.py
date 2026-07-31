from __future__ import annotations

from datetime import date

from vrm.engine.acceptance import (
    AcceptanceFinding,
    check_acceptances,
)
from vrm.models.enums import (
    AcceptanceAuthority,
    Rating,
    RiskSource,
    RiskStatus,
)
from vrm.models.risk import Risk
from vrm.models.vendor import Vendor


def _vendor(vid: str = "acme", tier: int | None = 2) -> Vendor:
    return Vendor(vendor_id=vid, legal_name="Acme", tier=tier)


def _risk(
    rid: str = "acme-F1",
    vid: str = "acme",
    status: RiskStatus = RiskStatus.ACCEPTED,
    accepted_by: str | None = "Jane",
    acceptance_level: str | None = "senior_management",
    acceptance_expiry: date | None = None,
) -> Risk:
    return Risk(
        risk_id=rid,
        vendor_id=vid,
        ref="F1",
        source=RiskSource.ASSESSMENT_REPORT,
        title="Test risk",
        status=status,
        accepted_by=accepted_by,
        acceptance_level=acceptance_level,
        acceptance_expiry=acceptance_expiry,
    )


class TestAcceptanceAuthority:
    def test_sufficient_authority_no_finding(self) -> None:
        vendor = _vendor(tier=2)
        risk = _risk(acceptance_level="senior_management")
        findings = check_acceptances([risk], [vendor])
        authority_findings = [f for f in findings if f.finding_type == "insufficient_authority"]
        assert len(authority_findings) == 0

    def test_higher_authority_accepted(self) -> None:
        vendor = _vendor(tier=3)
        risk = _risk(acceptance_level="executive")
        findings = check_acceptances([risk], [vendor])
        authority_findings = [f for f in findings if f.finding_type == "insufficient_authority"]
        assert len(authority_findings) == 0

    def test_insufficient_authority_flagged(self) -> None:
        vendor = _vendor(tier=1)
        risk = _risk(acceptance_level="team_lead")
        findings = check_acceptances([risk], [vendor])
        authority_findings = [f for f in findings if f.finding_type == "insufficient_authority"]
        assert len(authority_findings) == 1
        assert authority_findings[0].required_authority == AcceptanceAuthority.EXECUTIVE
        assert authority_findings[0].actual_authority == AcceptanceAuthority.TEAM_LEAD

    def test_invalid_authority_value(self) -> None:
        vendor = _vendor(tier=2)
        risk = _risk(acceptance_level="intern")
        findings = check_acceptances([risk], [vendor])
        invalid = [f for f in findings if f.finding_type == "invalid_authority"]
        assert len(invalid) == 1


class TestMissingApprover:
    def test_missing_accepted_by(self) -> None:
        risk = _risk(accepted_by=None)
        findings = check_acceptances([risk], [_vendor()])
        missing = [f for f in findings if f.finding_type == "missing_approver"]
        assert len(missing) == 1

    def test_present_accepted_by_no_finding(self) -> None:
        risk = _risk(accepted_by="Jane")
        findings = check_acceptances([risk], [_vendor()])
        missing = [f for f in findings if f.finding_type == "missing_approver"]
        assert len(missing) == 0


class TestExpiredAcceptance:
    def test_expired_acceptance_flagged(self) -> None:
        risk = _risk(acceptance_expiry=date(2024, 1, 1))
        findings = check_acceptances([risk], [_vendor()], today=date(2024, 6, 1))
        expired = [f for f in findings if f.finding_type == "expired_acceptance"]
        assert len(expired) == 1

    def test_future_expiry_no_finding(self) -> None:
        risk = _risk(acceptance_expiry=date(2025, 12, 31))
        findings = check_acceptances([risk], [_vendor()], today=date(2024, 6, 1))
        expired = [f for f in findings if f.finding_type == "expired_acceptance"]
        assert len(expired) == 0


class TestNonAcceptedRisks:
    def test_open_risk_skipped(self) -> None:
        risk = _risk(status=RiskStatus.OPEN, accepted_by=None, acceptance_level=None)
        findings = check_acceptances([risk], [_vendor()])
        assert len(findings) == 0

    def test_contingent_risk_checked(self) -> None:
        risk = _risk(status=RiskStatus.CONTINGENT, accepted_by=None)
        findings = check_acceptances([risk], [_vendor()])
        missing = [f for f in findings if f.finding_type == "missing_approver"]
        assert len(missing) == 1
