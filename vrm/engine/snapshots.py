"""Item 12: Trend snapshots.

Captures a periodic (monthly) snapshot of the register for
trend analysis and board reporting.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from vrm.models.enums import Rating, RiskStatus
from vrm.models.risk import Risk
from vrm.models.vendor import Vendor
from vrm.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class TrendSnapshot:
    snapshot_date: str
    run_id: str
    total_vendors: int
    total_risks: int
    risks_by_rating: dict[str, int] = field(default_factory=dict)
    risks_by_status: dict[str, int] = field(default_factory=dict)
    vendors_by_tier: dict[str, int] = field(default_factory=dict)
    review_due_count: int = 0
    open_risks: int = 0
    accepted_risks: int = 0


def take_snapshot(
    vendors: list[Vendor],
    risks: list[Risk],
    run_id: str,
    snapshot_date: date | None = None,
) -> TrendSnapshot:
    snapshot_date = snapshot_date or date.today()

    risks_by_rating: dict[str, int] = defaultdict(int)
    risks_by_status: dict[str, int] = defaultdict(int)

    for risk in risks:
        rating_key = (risk.inherent_rating or Rating.NONE).value
        risks_by_rating[rating_key] += 1
        risks_by_status[risk.status.value] += 1

    vendors_by_tier: dict[str, int] = defaultdict(int)
    review_due_count = 0
    for vendor in vendors:
        tier_key = str(vendor.tier) if vendor.tier else "untiered"
        vendors_by_tier[tier_key] += 1
        if vendor.review_due:
            review_due_count += 1

    return TrendSnapshot(
        snapshot_date=snapshot_date.isoformat(),
        run_id=run_id,
        total_vendors=len(vendors),
        total_risks=len(risks),
        risks_by_rating=dict(risks_by_rating),
        risks_by_status=dict(risks_by_status),
        vendors_by_tier=dict(vendors_by_tier),
        review_due_count=review_due_count,
        open_risks=risks_by_status.get(RiskStatus.OPEN.value, 0),
        accepted_risks=(
            risks_by_status.get(RiskStatus.ACCEPTED.value, 0)
            + risks_by_status.get(RiskStatus.ACCEPTED_TIMEBOXED.value, 0)
        ),
    )


@dataclass
class SnapshotDelta:
    vendors_added: int
    vendors_removed: int
    risks_added: int
    risks_removed: int
    open_risk_change: int
    review_due_change: int


def compare_snapshots(
    current: TrendSnapshot,
    previous: TrendSnapshot,
) -> SnapshotDelta:
    return SnapshotDelta(
        vendors_added=max(0, current.total_vendors - previous.total_vendors),
        vendors_removed=max(0, previous.total_vendors - current.total_vendors),
        risks_added=max(0, current.total_risks - previous.total_risks),
        risks_removed=max(0, previous.total_risks - current.total_risks),
        open_risk_change=current.open_risks - previous.open_risks,
        review_due_change=current.review_due_count - previous.review_due_count,
    )


def save_snapshot(snapshot: TrendSnapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if path.exists():
        existing = json.loads(path.read_text())

    existing.append(asdict(snapshot))
    path.write_text(json.dumps(existing, indent=2))
    log.info("snapshot_saved", path=str(path), date=snapshot.snapshot_date)


def load_snapshots(path: Path) -> list[TrendSnapshot]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    return [TrendSnapshot(**entry) for entry in raw]
