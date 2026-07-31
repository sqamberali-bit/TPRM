from __future__ import annotations

from datetime import date

from vrm.engine.expiry import ExpiryFinding, check_timebox_expiry
from vrm.models.enums import Rating, RiskSource, RiskStatus
from vrm.models.risk import Risk


def _risk(
    rid: str = "acme-F1",
    status: RiskStatus = RiskStatus.ACCEPTED_TIMEBOXED,
    timebox_expiry: date | None = None,
    contingency_reverts_to: Rating | None = None,
    inherent_rating: Rating | None = Rating.HIGH,
) -> Risk:
    return Risk(
        risk_id=rid,
        vendor_id="acme",
        ref="F1",
        source=RiskSource.ASSESSMENT_REPORT,
        title="Test risk",
        status=status,
        timebox_expiry=timebox_expiry,
        contingency_reverts_to=contingency_reverts_to,
        inherent_rating=inherent_rating,
    )


class TestTimeboxExpiry:
    def test_expired_timebox_flagged(self) -> None:
        risk = _risk(timebox_expiry=date(2024, 3, 1))
        findings = check_timebox_expiry([risk], today=date(2024, 6, 1))
        expired = [f for f in findings if f.finding_type == "timebox_expired"]
        assert len(expired) == 1
        assert expired[0].days_overdue == 92

    def test_expired_reverts_to_contingency(self) -> None:
        risk = _risk(
            timebox_expiry=date(2024, 3, 1),
            contingency_reverts_to=Rating.CRITICAL,
            inherent_rating=Rating.HIGH,
        )
        findings = check_timebox_expiry([risk], today=date(2024, 6, 1))
        assert findings[0].reverts_to == Rating.CRITICAL

    def test_expired_falls_back_to_inherent(self) -> None:
        risk = _risk(
            timebox_expiry=date(2024, 3, 1),
            contingency_reverts_to=None,
            inherent_rating=Rating.MEDIUM,
        )
        findings = check_timebox_expiry([risk], today=date(2024, 6, 1))
        assert findings[0].reverts_to == Rating.MEDIUM

    def test_future_timebox_no_finding(self) -> None:
        risk = _risk(timebox_expiry=date(2025, 12, 31))
        findings = check_timebox_expiry([risk], today=date(2024, 6, 1))
        assert len(findings) == 0

    def test_missing_timebox_date_flagged(self) -> None:
        risk = _risk(timebox_expiry=None)
        findings = check_timebox_expiry([risk], today=date(2024, 6, 1))
        missing = [f for f in findings if f.finding_type == "missing_timebox_date"]
        assert len(missing) == 1

    def test_non_timeboxed_risk_skipped(self) -> None:
        risk = _risk(status=RiskStatus.ACCEPTED, timebox_expiry=date(2024, 1, 1))
        findings = check_timebox_expiry([risk], today=date(2024, 6, 1))
        assert len(findings) == 0
