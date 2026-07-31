from __future__ import annotations

from datetime import date
from pathlib import Path

from vrm.engine.snapshots import (
    TrendSnapshot,
    compare_snapshots,
    load_snapshots,
    save_snapshot,
    take_snapshot,
)
from vrm.models.enums import Rating, RiskSource, RiskStatus
from vrm.models.risk import Risk
from vrm.models.vendor import Vendor


def _vendor(vid: str = "acme", tier: int | None = 2, review_due: bool = False) -> Vendor:
    return Vendor(
        vendor_id=vid, legal_name="Acme", tier=tier, review_due=review_due,
    )


def _risk(
    rid: str = "acme-F1",
    rating: Rating = Rating.HIGH,
    status: RiskStatus = RiskStatus.OPEN,
) -> Risk:
    return Risk(
        risk_id=rid, vendor_id="acme", ref="F1",
        source=RiskSource.ASSESSMENT_REPORT, title="Test",
        inherent_rating=rating, status=status,
    )


class TestTakeSnapshot:
    def test_basic_snapshot(self) -> None:
        vendors = [_vendor()]
        risks = [_risk(), _risk("acme-F2", rating=Rating.CRITICAL)]
        snap = take_snapshot(vendors, risks, "run-1", snapshot_date=date(2024, 6, 1))
        assert snap.total_vendors == 1
        assert snap.total_risks == 2
        assert snap.risks_by_rating["high"] == 1
        assert snap.risks_by_rating["critical"] == 1
        assert snap.open_risks == 2

    def test_review_due_counted(self) -> None:
        vendors = [_vendor(review_due=True), _vendor(vid="v2", review_due=False)]
        snap = take_snapshot(vendors, [], "run-1")
        assert snap.review_due_count == 1

    def test_vendors_by_tier(self) -> None:
        vendors = [
            _vendor(vid="v1", tier=1),
            _vendor(vid="v2", tier=1),
            _vendor(vid="v3", tier=3),
        ]
        snap = take_snapshot(vendors, [], "run-1")
        assert snap.vendors_by_tier["1"] == 2
        assert snap.vendors_by_tier["3"] == 1


class TestCompareSnapshots:
    def test_detects_changes(self) -> None:
        prev = TrendSnapshot(
            snapshot_date="2024-05-01", run_id="r1",
            total_vendors=5, total_risks=10,
            open_risks=3, review_due_count=1,
        )
        curr = TrendSnapshot(
            snapshot_date="2024-06-01", run_id="r2",
            total_vendors=7, total_risks=12,
            open_risks=5, review_due_count=3,
        )
        delta = compare_snapshots(curr, prev)
        assert delta.vendors_added == 2
        assert delta.vendors_removed == 0
        assert delta.risks_added == 2
        assert delta.open_risk_change == 2
        assert delta.review_due_change == 2


class TestPersistence:
    def test_save_and_load(self, tmp_path: Path) -> None:
        path = tmp_path / "snapshots.json"
        snap = take_snapshot([_vendor()], [_risk()], "run-1", snapshot_date=date(2024, 6, 1))
        save_snapshot(snap, path)

        loaded = load_snapshots(path)
        assert len(loaded) == 1
        assert loaded[0].total_vendors == 1

    def test_appends_to_existing(self, tmp_path: Path) -> None:
        path = tmp_path / "snapshots.json"
        snap1 = take_snapshot([], [], "r1", snapshot_date=date(2024, 5, 1))
        snap2 = take_snapshot([], [], "r2", snapshot_date=date(2024, 6, 1))
        save_snapshot(snap1, path)
        save_snapshot(snap2, path)

        loaded = load_snapshots(path)
        assert len(loaded) == 2

    def test_load_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.json"
        loaded = load_snapshots(path)
        assert len(loaded) == 0
