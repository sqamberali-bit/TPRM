"""Item 5: Event-driven reassessment triggers.

Evaluates reassessment events and sets affected vendors to review_due
when unresolved events exist.
"""
from __future__ import annotations

from dataclasses import dataclass

from vrm.models.enums import TriggerEventType
from vrm.models.reassessment_event import ReassessmentEvent
from vrm.models.vendor import Vendor
from vrm.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class ReassessmentAction:
    vendor_id: str
    reason: str
    event_type: TriggerEventType
    event_id: str


def evaluate_triggers(
    events: list[ReassessmentEvent],
    vendors: list[Vendor],
) -> list[ReassessmentAction]:
    vendors_by_id = {v.vendor_id: v for v in vendors}
    actions: list[ReassessmentAction] = []

    for event in events:
        if event.resolved_date is not None:
            continue

        vendor = vendors_by_id.get(event.vendor_id)
        if vendor is None:
            continue

        actions.append(ReassessmentAction(
            vendor_id=event.vendor_id,
            reason=(
                f"{event.event_type.value}: {event.description}"
            ),
            event_type=event.event_type,
            event_id=event.event_id,
        ))

    if actions:
        log.info("reassessment_actions", count=len(actions))
    return actions


def apply_reassessment_actions(
    actions: list[ReassessmentAction],
    vendors: list[Vendor],
) -> list[Vendor]:
    vendors_by_id = {v.vendor_id: v for v in vendors}
    modified: list[Vendor] = []

    for action in actions:
        vendor = vendors_by_id.get(action.vendor_id)
        if vendor is None:
            continue

        if not vendor.review_due:
            vendor.review_due = True
            vendor.review_due_reason = action.reason
            modified.append(vendor)

    return modified
