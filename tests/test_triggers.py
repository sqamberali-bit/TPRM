from __future__ import annotations

from datetime import date

from vrm.engine.triggers import (
    ReassessmentAction,
    apply_reassessment_actions,
    evaluate_triggers,
)
from vrm.models.enums import TriggerEventType
from vrm.models.reassessment_event import ReassessmentEvent
from vrm.models.vendor import Vendor


def _vendor(vid: str = "acme", review_due: bool = False) -> Vendor:
    return Vendor(vendor_id=vid, legal_name="Acme", review_due=review_due)


def _event(
    eid: str = "evt-1",
    vid: str = "acme",
    event_type: TriggerEventType = TriggerEventType.BREACH_NOTIFICATION,
    resolved: bool = False,
) -> ReassessmentEvent:
    return ReassessmentEvent(
        event_id=eid,
        vendor_id=vid,
        event_type=event_type,
        description="Test event",
        raised_date=date(2024, 6, 1),
        resolved_date=date(2024, 7, 1) if resolved else None,
    )


class TestEvaluateTriggers:
    def test_unresolved_event_triggers_action(self) -> None:
        event = _event(resolved=False)
        vendor = _vendor()
        actions = evaluate_triggers([event], [vendor])
        assert len(actions) == 1
        assert actions[0].vendor_id == "acme"
        assert actions[0].event_type == TriggerEventType.BREACH_NOTIFICATION

    def test_resolved_event_no_action(self) -> None:
        event = _event(resolved=True)
        vendor = _vendor()
        actions = evaluate_triggers([event], [vendor])
        assert len(actions) == 0

    def test_unknown_vendor_skipped(self) -> None:
        event = _event(vid="unknown")
        vendor = _vendor(vid="acme")
        actions = evaluate_triggers([event], [vendor])
        assert len(actions) == 0

    def test_multiple_events_for_same_vendor(self) -> None:
        events = [
            _event(eid="e1", event_type=TriggerEventType.BREACH_NOTIFICATION),
            _event(eid="e2", event_type=TriggerEventType.MAJOR_OUTAGE),
        ]
        actions = evaluate_triggers(events, [_vendor()])
        assert len(actions) == 2


class TestApplyReassessmentActions:
    def test_sets_review_due(self) -> None:
        vendor = _vendor(review_due=False)
        action = ReassessmentAction(
            vendor_id="acme",
            reason="breach_notification: Test event",
            event_type=TriggerEventType.BREACH_NOTIFICATION,
            event_id="evt-1",
        )
        modified = apply_reassessment_actions([action], [vendor])
        assert len(modified) == 1
        assert vendor.review_due is True
        assert "breach_notification" in vendor.review_due_reason

    def test_already_review_due_not_duplicated(self) -> None:
        vendor = _vendor(review_due=True)
        action = ReassessmentAction(
            vendor_id="acme",
            reason="test",
            event_type=TriggerEventType.MANUAL,
            event_id="evt-1",
        )
        modified = apply_reassessment_actions([action], [vendor])
        assert len(modified) == 0
