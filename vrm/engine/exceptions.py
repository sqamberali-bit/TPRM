"""Item 10: Exception register.

Scoped, time-limited exceptions with owner and expiry,
kept separate from accepted risks. Flags expired or
ownerless exceptions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from vrm.models.enums import ExceptionStatus
from vrm.models.exception import RiskException
from vrm.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class ExceptionFinding:
    exception_id: str
    vendor_id: str
    finding_type: str
    detail: str
    days_overdue: int = 0


def check_exceptions(
    exceptions: list[RiskException],
    today: date | None = None,
) -> list[ExceptionFinding]:
    today = today or date.today()
    findings: list[ExceptionFinding] = []

    for exc in exceptions:
        if exc.status != ExceptionStatus.ACTIVE:
            continue

        if exc.expiry_date < today:
            overdue = (today - exc.expiry_date).days
            findings.append(ExceptionFinding(
                exception_id=exc.exception_id,
                vendor_id=exc.vendor_id,
                finding_type="exception_expired",
                detail=(
                    f"Exception {exc.exception_id} for risk {exc.risk_id} "
                    f"expired {exc.expiry_date.isoformat()} ({overdue} days ago)"
                ),
                days_overdue=overdue,
            ))

        if not exc.owner or not exc.owner.strip():
            findings.append(ExceptionFinding(
                exception_id=exc.exception_id,
                vendor_id=exc.vendor_id,
                finding_type="missing_owner",
                detail=(
                    f"Exception {exc.exception_id} for risk {exc.risk_id} "
                    f"has no owner assigned"
                ),
            ))

        if not exc.justification or not exc.justification.strip():
            findings.append(ExceptionFinding(
                exception_id=exc.exception_id,
                vendor_id=exc.vendor_id,
                finding_type="missing_justification",
                detail=(
                    f"Exception {exc.exception_id} for risk {exc.risk_id} "
                    f"has no justification documented"
                ),
            ))

    if findings:
        log.info("exception_findings", count=len(findings))
    return findings


def expire_exceptions(
    exceptions: list[RiskException],
    today: date | None = None,
) -> list[RiskException]:
    today = today or date.today()
    expired: list[RiskException] = []

    for exc in exceptions:
        if exc.status == ExceptionStatus.ACTIVE and exc.expiry_date < today:
            exc.status = ExceptionStatus.EXPIRED
            expired.append(exc)

    return expired
