"""Item 1: Acceptance and approval workflow.

Enforces tier-based acceptance authority and flags expired or
incomplete acceptances.

Tier authority mapping:
  Tier 1 -> Executive
  Tier 2 -> Senior management
  Tier 3 -> Manager
  Tier 4 -> Team lead
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from vrm.models.enums import AcceptanceAuthority, RiskStatus
from vrm.models.risk import Risk
from vrm.models.vendor import Vendor
from vrm.utils.logging import get_logger

log = get_logger(__name__)

TIER_AUTHORITY: dict[int, AcceptanceAuthority] = {
    1: AcceptanceAuthority.EXECUTIVE,
    2: AcceptanceAuthority.SENIOR_MANAGEMENT,
    3: AcceptanceAuthority.MANAGER,
    4: AcceptanceAuthority.TEAM_LEAD,
}

AUTHORITY_RANK: dict[AcceptanceAuthority, int] = {
    AcceptanceAuthority.EXECUTIVE: 4,
    AcceptanceAuthority.SENIOR_MANAGEMENT: 3,
    AcceptanceAuthority.MANAGER: 2,
    AcceptanceAuthority.TEAM_LEAD: 1,
}

_ACCEPTED_STATUSES = frozenset({
    RiskStatus.ACCEPTED,
    RiskStatus.ACCEPTED_TIMEBOXED,
    RiskStatus.CONTINGENT,
})


@dataclass
class AcceptanceFinding:
    risk_id: str
    vendor_id: str
    finding_type: str
    detail: str
    required_authority: Optional[AcceptanceAuthority] = None
    actual_authority: Optional[AcceptanceAuthority] = None


def check_acceptances(
    risks: list[Risk],
    vendors: list[Vendor],
    today: date | None = None,
) -> list[AcceptanceFinding]:
    today = today or date.today()
    vendors_by_id = {v.vendor_id: v for v in vendors}
    findings: list[AcceptanceFinding] = []

    for risk in risks:
        if risk.status not in _ACCEPTED_STATUSES:
            continue

        vendor = vendors_by_id.get(risk.vendor_id)

        if not risk.accepted_by:
            findings.append(AcceptanceFinding(
                risk_id=risk.risk_id,
                vendor_id=risk.vendor_id,
                finding_type="missing_approver",
                detail=f"Risk {risk.risk_id} is {risk.status.value} but has no accepted_by",
            ))

        if vendor and vendor.tier and risk.acceptance_level:
            required = TIER_AUTHORITY.get(vendor.tier)
            try:
                actual = AcceptanceAuthority(risk.acceptance_level)
            except ValueError:
                findings.append(AcceptanceFinding(
                    risk_id=risk.risk_id,
                    vendor_id=risk.vendor_id,
                    finding_type="invalid_authority",
                    detail=(
                        f"Risk {risk.risk_id} acceptance_level "
                        f"'{risk.acceptance_level}' is not a valid authority"
                    ),
                ))
                continue

            if required and AUTHORITY_RANK.get(actual, 0) < AUTHORITY_RANK[required]:
                findings.append(AcceptanceFinding(
                    risk_id=risk.risk_id,
                    vendor_id=risk.vendor_id,
                    finding_type="insufficient_authority",
                    detail=(
                        f"Risk {risk.risk_id} accepted by {actual.value} "
                        f"but Tier {vendor.tier} requires {required.value}"
                    ),
                    required_authority=required,
                    actual_authority=actual,
                ))

        if risk.acceptance_expiry and risk.acceptance_expiry < today:
            findings.append(AcceptanceFinding(
                risk_id=risk.risk_id,
                vendor_id=risk.vendor_id,
                finding_type="expired_acceptance",
                detail=(
                    f"Risk {risk.risk_id} acceptance expired on "
                    f"{risk.acceptance_expiry.isoformat()}"
                ),
            ))

    if findings:
        log.info("acceptance_findings", count=len(findings))
    return findings
