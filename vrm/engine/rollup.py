"""Item 13: Board vs operational rollup.

Produces an aggregate exposure view by tier for the board,
alongside full operational detail.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from vrm.models.enums import Rating, RiskStatus
from vrm.models.risk import Risk
from vrm.models.vendor import Vendor
from vrm.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class TierRollup:
    tier: int | None
    vendor_count: int = 0
    risk_count: int = 0
    critical_risks: int = 0
    high_risks: int = 0
    open_risks: int = 0
    review_due_count: int = 0
    avg_external_rating: float | None = None


@dataclass
class BoardSummary:
    snapshot_date: str
    tiers: list[TierRollup] = field(default_factory=list)
    total_vendors: int = 0
    total_risks: int = 0
    total_critical: int = 0
    total_high: int = 0
    total_review_due: int = 0


def build_board_rollup(
    vendors: list[Vendor],
    risks: list[Risk],
    snapshot_date: date | None = None,
) -> BoardSummary:
    snapshot_date = snapshot_date or date.today()

    vendors_by_tier: dict[int | None, list[Vendor]] = defaultdict(list)
    for vendor in vendors:
        vendors_by_tier[vendor.tier].append(vendor)

    risks_by_vendor: dict[str, list[Risk]] = defaultdict(list)
    for risk in risks:
        risks_by_vendor[risk.vendor_id].append(risk)

    tier_rollups: list[TierRollup] = []

    for tier in sorted(vendors_by_tier, key=lambda t: t if t is not None else 99):
        tier_vendors = vendors_by_tier[tier]
        tier_risks: list[Risk] = []
        for v in tier_vendors:
            tier_risks.extend(risks_by_vendor.get(v.vendor_id, []))

        ratings_with_values = [
            v.external_rating for v in tier_vendors
            if v.external_rating is not None
        ]
        avg_rating = (
            sum(ratings_with_values) / len(ratings_with_values)
            if ratings_with_values else None
        )

        tier_rollups.append(TierRollup(
            tier=tier,
            vendor_count=len(tier_vendors),
            risk_count=len(tier_risks),
            critical_risks=sum(
                1 for r in tier_risks
                if r.inherent_rating == Rating.CRITICAL
            ),
            high_risks=sum(
                1 for r in tier_risks
                if r.inherent_rating == Rating.HIGH
            ),
            open_risks=sum(
                1 for r in tier_risks
                if r.status == RiskStatus.OPEN
            ),
            review_due_count=sum(
                1 for v in tier_vendors if v.review_due
            ),
            avg_external_rating=round(avg_rating, 1) if avg_rating else None,
        ))

    return BoardSummary(
        snapshot_date=snapshot_date.isoformat(),
        tiers=tier_rollups,
        total_vendors=len(vendors),
        total_risks=len(risks),
        total_critical=sum(t.critical_risks for t in tier_rollups),
        total_high=sum(t.high_risks for t in tier_rollups),
        total_review_due=sum(t.review_due_count for t in tier_rollups),
    )


@dataclass
class VendorDetail:
    vendor_id: str
    legal_name: str
    tier: int | None
    status: str
    risk_count: int
    critical_risks: int
    high_risks: int
    external_rating: int | None
    review_due: bool


def build_operational_detail(
    vendors: list[Vendor],
    risks: list[Risk],
) -> list[VendorDetail]:
    risks_by_vendor: dict[str, list[Risk]] = defaultdict(list)
    for risk in risks:
        risks_by_vendor[risk.vendor_id].append(risk)

    details: list[VendorDetail] = []
    for vendor in sorted(vendors, key=lambda v: (v.tier or 99, v.vendor_id)):
        vendor_risks = risks_by_vendor.get(vendor.vendor_id, [])
        details.append(VendorDetail(
            vendor_id=vendor.vendor_id,
            legal_name=vendor.legal_name,
            tier=vendor.tier,
            status=vendor.status.value,
            risk_count=len(vendor_risks),
            critical_risks=sum(
                1 for r in vendor_risks
                if r.inherent_rating == Rating.CRITICAL
            ),
            high_risks=sum(
                1 for r in vendor_risks
                if r.inherent_rating == Rating.HIGH
            ),
            external_rating=vendor.external_rating,
            review_due=vendor.review_due,
        ))

    return details
