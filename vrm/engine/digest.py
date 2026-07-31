"""Item 14: Notifications digest.

Emits a weekly digest object (new high risks, overdue reviews,
expiring acceptances, expiring certificates) for Power Automate
to send to Teams.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from vrm.models.enums import Rating, RiskStatus
from vrm.models.risk import Risk
from vrm.models.vendor import Vendor
from vrm.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class DigestItem:
    category: str
    vendor_id: str
    detail: str
    priority: str


@dataclass
class WeeklyDigest:
    generated_date: str
    period_start: str
    period_end: str
    items: list[DigestItem] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


def build_digest(
    vendors: list[Vendor],
    risks: list[Risk],
    today: date | None = None,
    lookback_days: int = 7,
) -> WeeklyDigest:
    today = today or date.today()
    period_start = today - timedelta(days=lookback_days)

    items: list[DigestItem] = []

    for risk in risks:
        if (
            risk.inherent_rating in (Rating.HIGH, Rating.CRITICAL)
            and risk.status == RiskStatus.OPEN
            and risk.date_raised
            and risk.date_raised >= period_start
        ):
            priority = (
                "high" if risk.inherent_rating == Rating.CRITICAL else "medium"
            )
            items.append(DigestItem(
                category="new_high_risk",
                vendor_id=risk.vendor_id,
                detail=f"{risk.risk_id}: {risk.title} [{risk.inherent_rating.value}]",
                priority=priority,
            ))

    for vendor in vendors:
        if vendor.review_due:
            items.append(DigestItem(
                category="review_due",
                vendor_id=vendor.vendor_id,
                detail=(
                    f"Vendor {vendor.vendor_id} is due for review"
                    + (f": {vendor.review_due_reason}" if vendor.review_due_reason else "")
                ),
                priority="medium",
            ))

        if vendor.next_review_date and vendor.next_review_date <= today:
            items.append(DigestItem(
                category="overdue_review",
                vendor_id=vendor.vendor_id,
                detail=(
                    f"Vendor {vendor.vendor_id} review overdue since "
                    f"{vendor.next_review_date.isoformat()}"
                ),
                priority="high",
            ))

    for risk in risks:
        if (
            risk.status in (RiskStatus.ACCEPTED, RiskStatus.ACCEPTED_TIMEBOXED)
            and risk.acceptance_expiry
            and today <= risk.acceptance_expiry <= today + timedelta(days=lookback_days)
        ):
            items.append(DigestItem(
                category="expiring_acceptance",
                vendor_id=risk.vendor_id,
                detail=(
                    f"Risk {risk.risk_id} acceptance expires "
                    f"{risk.acceptance_expiry.isoformat()}"
                ),
                priority="medium",
            ))

    for vendor in vendors:
        for cert in vendor.certifications:
            if cert.recert_due and today <= cert.recert_due <= today + timedelta(days=30):
                items.append(DigestItem(
                    category="expiring_certificate",
                    vendor_id=vendor.vendor_id,
                    detail=(
                        f"{cert.type.value} recertification due "
                        f"{cert.recert_due.isoformat()}"
                    ),
                    priority="medium",
                ))
            if cert.surveillance_due and today <= cert.surveillance_due <= today + timedelta(days=30):
                items.append(DigestItem(
                    category="expiring_certificate",
                    vendor_id=vendor.vendor_id,
                    detail=(
                        f"{cert.type.value} surveillance due "
                        f"{cert.surveillance_due.isoformat()}"
                    ),
                    priority="medium",
                ))

    summary: dict[str, int] = defaultdict(int)
    for item in items:
        summary[item.category] += 1

    digest = WeeklyDigest(
        generated_date=today.isoformat(),
        period_start=period_start.isoformat(),
        period_end=today.isoformat(),
        items=items,
        summary=dict(summary),
    )

    log.info("digest_built", items=len(items), summary=dict(summary))
    return digest
