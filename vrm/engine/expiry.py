"""Item 4: Time-boxed acceptance expiry.

Flags risks with status accepted_timeboxed whose timebox_expiry
has passed. Reports what the risk should revert to.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from vrm.models.enums import Rating, RiskStatus
from vrm.models.risk import Risk
from vrm.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class ExpiryFinding:
    risk_id: str
    vendor_id: str
    finding_type: str
    detail: str
    days_overdue: int = 0
    reverts_to: Optional[Rating] = None


def check_timebox_expiry(
    risks: list[Risk],
    today: date | None = None,
) -> list[ExpiryFinding]:
    today = today or date.today()
    findings: list[ExpiryFinding] = []

    for risk in risks:
        if risk.status != RiskStatus.ACCEPTED_TIMEBOXED:
            continue

        if risk.timebox_expiry is None:
            findings.append(ExpiryFinding(
                risk_id=risk.risk_id,
                vendor_id=risk.vendor_id,
                finding_type="missing_timebox_date",
                detail=(
                    f"Risk {risk.risk_id} is accepted_timeboxed "
                    f"but has no timebox_expiry date set"
                ),
            ))
            continue

        if risk.timebox_expiry < today:
            overdue = (today - risk.timebox_expiry).days
            reverts_to = risk.contingency_reverts_to or risk.inherent_rating
            findings.append(ExpiryFinding(
                risk_id=risk.risk_id,
                vendor_id=risk.vendor_id,
                finding_type="timebox_expired",
                detail=(
                    f"Risk {risk.risk_id} timebox expired on "
                    f"{risk.timebox_expiry.isoformat()} ({overdue} days ago), "
                    f"reverts to {reverts_to.value if reverts_to else 'unknown'}"
                ),
                days_overdue=overdue,
                reverts_to=reverts_to,
            ))

    if findings:
        log.info("timebox_expiry_findings", count=len(findings))
    return findings
