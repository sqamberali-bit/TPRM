from __future__ import annotations

from datetime import date

from vrm.engine.exceptions import (
    ExceptionFinding,
    check_exceptions,
    expire_exceptions,
)
from vrm.models.enums import ExceptionStatus
from vrm.models.exception import RiskException


def _exc(
    eid: str = "exc-1",
    expiry: date = date(2025, 6, 1),
    owner: str = "Jane",
    justification: str = "Approved by CTO",
    status: ExceptionStatus = ExceptionStatus.ACTIVE,
) -> RiskException:
    return RiskException(
        exception_id=eid,
        risk_id="acme-F1",
        vendor_id="acme",
        scope="TLS downgrade",
        owner=owner,
        justification=justification,
        granted_date=date(2024, 1, 1),
        expiry_date=expiry,
        status=status,
    )


class TestCheckExceptions:
    def test_expired_exception_flagged(self) -> None:
        exc = _exc(expiry=date(2024, 3, 1))
        findings = check_exceptions([exc], today=date(2024, 6, 1))
        expired = [f for f in findings if f.finding_type == "exception_expired"]
        assert len(expired) == 1
        assert expired[0].days_overdue == 92

    def test_valid_exception_no_finding(self) -> None:
        exc = _exc(expiry=date(2025, 12, 31))
        findings = check_exceptions([exc], today=date(2024, 6, 1))
        expired = [f for f in findings if f.finding_type == "exception_expired"]
        assert len(expired) == 0

    def test_missing_owner_flagged(self) -> None:
        exc = _exc(owner="")
        findings = check_exceptions([exc], today=date(2024, 6, 1))
        missing = [f for f in findings if f.finding_type == "missing_owner"]
        assert len(missing) == 1

    def test_missing_justification_flagged(self) -> None:
        exc = _exc(justification="")
        findings = check_exceptions([exc], today=date(2024, 6, 1))
        missing = [f for f in findings if f.finding_type == "missing_justification"]
        assert len(missing) == 1

    def test_revoked_exception_skipped(self) -> None:
        exc = _exc(status=ExceptionStatus.REVOKED, expiry=date(2024, 1, 1))
        findings = check_exceptions([exc], today=date(2024, 6, 1))
        assert len(findings) == 0


class TestExpireExceptions:
    def test_expires_past_due(self) -> None:
        exc = _exc(expiry=date(2024, 3, 1))
        expired = expire_exceptions([exc], today=date(2024, 6, 1))
        assert len(expired) == 1
        assert exc.status == ExceptionStatus.EXPIRED

    def test_does_not_expire_future(self) -> None:
        exc = _exc(expiry=date(2025, 12, 31))
        expired = expire_exceptions([exc], today=date(2024, 6, 1))
        assert len(expired) == 0
        assert exc.status == ExceptionStatus.ACTIVE

    def test_already_expired_skipped(self) -> None:
        exc = _exc(status=ExceptionStatus.EXPIRED, expiry=date(2024, 1, 1))
        expired = expire_exceptions([exc], today=date(2024, 6, 1))
        assert len(expired) == 0
