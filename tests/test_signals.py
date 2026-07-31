from __future__ import annotations

from vrm.clients.upguard import RatingChange
from vrm.engine.signals import (
    SignalAction,
    apply_signal_actions,
    evaluate_upguard_signals,
)
from vrm.models.enums import Rating, RiskSource, RiskStatus
from vrm.models.risk import Risk
from vrm.models.vendor import Vendor


def _vendor(vid: str = "acme", review_due: bool = False) -> Vendor:
    return Vendor(vendor_id=vid, legal_name="Acme", review_due=review_due)


def _risk(
    vid: str = "acme",
    rating: Rating = Rating.CRITICAL,
    source: RiskSource = RiskSource.UPGUARD,
) -> Risk:
    return Risk(
        risk_id=f"{vid}-ug-1",
        vendor_id=vid,
        ref="ug-1",
        source=source,
        title="Critical finding",
        inherent_rating=rating,
        status=RiskStatus.OPEN,
    )


class TestEvaluateSignals:
    def test_rating_drop_produces_action(self) -> None:
        change = RatingChange("acme", "acme.com", 800, 700, "drop")
        actions = evaluate_upguard_signals([change], [])
        assert len(actions) == 1
        assert actions[0].signal_type == "rating_drop"

    def test_improvement_no_action(self) -> None:
        change = RatingChange("acme", "acme.com", 700, 800, "improve")
        actions = evaluate_upguard_signals([change], [])
        assert len(actions) == 0

    def test_significant_only_filters(self) -> None:
        small_drop = RatingChange("acme", "acme.com", 800, 780, "drop")
        actions = evaluate_upguard_signals([small_drop], [], significant_only=True)
        assert len(actions) == 0

        big_drop = RatingChange("acme", "acme.com", 800, 700, "drop")
        actions = evaluate_upguard_signals([big_drop], [], significant_only=True)
        assert len(actions) == 1

    def test_critical_risk_produces_action(self) -> None:
        risk = _risk(rating=Rating.CRITICAL)
        actions = evaluate_upguard_signals([], [risk])
        assert len(actions) == 1
        assert actions[0].signal_type == "critical_risk"

    def test_non_critical_risk_no_action(self) -> None:
        risk = _risk(rating=Rating.HIGH)
        actions = evaluate_upguard_signals([], [risk])
        assert len(actions) == 0

    def test_non_upguard_critical_no_action(self) -> None:
        risk = _risk(source=RiskSource.ASSESSMENT_REPORT, rating=Rating.CRITICAL)
        actions = evaluate_upguard_signals([], [risk])
        assert len(actions) == 0

    def test_deduplicates_vendor(self) -> None:
        change = RatingChange("acme", "acme.com", 800, 700, "drop")
        risk = _risk(vid="acme", rating=Rating.CRITICAL)
        actions = evaluate_upguard_signals([change], [risk])
        assert len(actions) == 1
        assert actions[0].signal_type == "rating_drop"


class TestApplySignalActions:
    def test_sets_review_due(self) -> None:
        vendor = _vendor(review_due=False)
        action = SignalAction("acme", "rating_drop", "Rating dropped")
        modified = apply_signal_actions([action], [vendor])
        assert len(modified) == 1
        assert vendor.review_due is True

    def test_already_review_due_not_duplicated(self) -> None:
        vendor = _vendor(review_due=True)
        action = SignalAction("acme", "rating_drop", "Rating dropped")
        modified = apply_signal_actions([action], [vendor])
        assert len(modified) == 0
