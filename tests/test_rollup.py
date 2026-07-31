from __future__ import annotations

from datetime import date

from vrm.engine.rollup import (
    BoardSummary,
    TierRollup,
    VendorDetail,
    build_board_rollup,
    build_operational_detail,
)
from vrm.models.enums import Rating, RiskSource, RiskStatus
from vrm.models.risk import Risk
from vrm.models.vendor import Vendor


def _vendor(
    vid: str = "acme",
    tier: int | None = 2,
    rating: int | None = 750,
    review_due: bool = False,
) -> Vendor:
    return Vendor(
        vendor_id=vid, legal_name="Acme", tier=tier,
        external_rating=rating, review_due=review_due,
    )


def _risk(
    rid: str = "acme-F1",
    vid: str = "acme",
    rating: Rating = Rating.HIGH,
    status: RiskStatus = RiskStatus.OPEN,
) -> Risk:
    return Risk(
        risk_id=rid, vendor_id=vid, ref="F1",
        source=RiskSource.ASSESSMENT_REPORT, title="Test",
        inherent_rating=rating, status=status,
    )


class TestBoardRollup:
    def test_basic_rollup(self) -> None:
        vendors = [_vendor(vid="v1", tier=1), _vendor(vid="v2", tier=2)]
        risks = [
            _risk("v1-F1", vid="v1", rating=Rating.CRITICAL),
            _risk("v2-F1", vid="v2", rating=Rating.HIGH),
        ]
        board = build_board_rollup(vendors, risks, snapshot_date=date(2024, 6, 1))
        assert board.total_vendors == 2
        assert board.total_risks == 2
        assert board.total_critical == 1
        assert board.total_high == 1
        assert len(board.tiers) == 2

    def test_tier_grouping(self) -> None:
        vendors = [
            _vendor(vid="v1", tier=1, rating=800),
            _vendor(vid="v2", tier=1, rating=700),
        ]
        risks = [
            _risk("v1-F1", vid="v1", rating=Rating.CRITICAL),
            _risk("v2-F1", vid="v2", rating=Rating.HIGH),
        ]
        board = build_board_rollup(vendors, risks)
        assert len(board.tiers) == 1
        t1 = board.tiers[0]
        assert t1.vendor_count == 2
        assert t1.risk_count == 2
        assert t1.avg_external_rating == 750.0

    def test_review_due_counted(self) -> None:
        vendors = [_vendor(vid="v1", tier=1, review_due=True)]
        board = build_board_rollup(vendors, [])
        assert board.total_review_due == 1

    def test_empty_data(self) -> None:
        board = build_board_rollup([], [])
        assert board.total_vendors == 0
        assert len(board.tiers) == 0


class TestOperationalDetail:
    def test_produces_vendor_details(self) -> None:
        vendors = [_vendor(vid="acme", tier=2, review_due=True)]
        risks = [
            _risk("acme-F1", vid="acme", rating=Rating.CRITICAL),
            _risk("acme-F2", vid="acme", rating=Rating.HIGH),
        ]
        detail = build_operational_detail(vendors, risks)
        assert len(detail) == 1
        d = detail[0]
        assert d.vendor_id == "acme"
        assert d.risk_count == 2
        assert d.critical_risks == 1
        assert d.high_risks == 1
        assert d.review_due is True

    def test_sorted_by_tier(self) -> None:
        vendors = [
            _vendor(vid="v3", tier=3),
            _vendor(vid="v1", tier=1),
        ]
        detail = build_operational_detail(vendors, [])
        assert detail[0].vendor_id == "v1"
        assert detail[1].vendor_id == "v3"
