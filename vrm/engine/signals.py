"""Item 6: UpGuard signal actions.

Reacts to UpGuard rating drops and critical risk findings by
setting affected vendors to review_due.
"""
from __future__ import annotations

from dataclasses import dataclass

from vrm.clients.upguard import RatingChange
from vrm.models.enums import Rating, RiskSource
from vrm.models.risk import Risk
from vrm.models.vendor import Vendor
from vrm.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class SignalAction:
    vendor_id: str
    signal_type: str
    detail: str


def evaluate_upguard_signals(
    rating_changes: list[RatingChange],
    risks: list[Risk],
    significant_only: bool = False,
) -> list[SignalAction]:
    actions: list[SignalAction] = []
    seen_vendors: set[str] = set()

    for change in rating_changes:
        if change.direction != "drop":
            continue
        if significant_only and not change.is_significant_drop:
            continue

        if change.vendor_id not in seen_vendors:
            detail = (
                f"Rating dropped from {change.previous_rating} to "
                f"{change.current_rating}"
            )
            if change.is_significant_drop:
                detail += " (significant: >= 50 point drop)"
            actions.append(SignalAction(
                vendor_id=change.vendor_id,
                signal_type="rating_drop",
                detail=detail,
            ))
            seen_vendors.add(change.vendor_id)

    critical_vendors: dict[str, int] = {}
    for risk in risks:
        if (
            risk.source == RiskSource.UPGUARD
            and risk.inherent_rating == Rating.CRITICAL
        ):
            critical_vendors[risk.vendor_id] = (
                critical_vendors.get(risk.vendor_id, 0) + 1
            )

    for vid, count in critical_vendors.items():
        if vid not in seen_vendors:
            actions.append(SignalAction(
                vendor_id=vid,
                signal_type="critical_risk",
                detail=f"{count} critical UpGuard risk(s) detected",
            ))
            seen_vendors.add(vid)

    if actions:
        log.info("upguard_signal_actions", count=len(actions))
    return actions


def apply_signal_actions(
    actions: list[SignalAction],
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
            vendor.review_due_reason = f"{action.signal_type}: {action.detail}"
            modified.append(vendor)

    return modified
