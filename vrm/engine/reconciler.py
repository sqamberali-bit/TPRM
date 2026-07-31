"""Reconcile risks from multiple sources (assessment reports + UpGuard).

When the same real risk appears from both UpGuard and a report, link
rather than duplicate.  Keying strategy:
  - Report risks: {vendor_id}-{ref}  (e.g. pet-loyalty-F1)
  - UpGuard risks: {vendor_id}-ug-{upguard_risk_id}

A manual link table (maintained in SharePoint) can map an UpGuard risk
to a report risk.  This module merges where links exist and keeps both
where they don't.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from vrm.models.risk import Risk
from vrm.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class ReconciliationResult:
    merged: list[Risk] = field(default_factory=list)
    report_only: list[Risk] = field(default_factory=list)
    upguard_only: list[Risk] = field(default_factory=list)
    linked: list[tuple[str, str]] = field(default_factory=list)


def reconcile(
    report_risks: list[Risk],
    upguard_risks: list[Risk],
    link_map: dict[str, str] | None = None,
) -> ReconciliationResult:
    """Merge risks from reports and UpGuard.

    link_map: {upguard_risk_id: report_risk_id} for known equivalences.
    """
    link_map = link_map or {}
    result = ReconciliationResult()

    report_by_id = {r.risk_id: r for r in report_risks}
    matched_report_ids: set[str] = set()

    for ug_risk in upguard_risks:
        linked_report_id = link_map.get(ug_risk.risk_id)
        if linked_report_id and linked_report_id in report_by_id:
            report_risk = report_by_id[linked_report_id]
            merged = _merge_linked(report_risk, ug_risk)
            result.merged.append(merged)
            matched_report_ids.add(linked_report_id)
            result.linked.append((ug_risk.risk_id, linked_report_id))
            log.info(
                "linked_risk",
                upguard=ug_risk.risk_id,
                report=linked_report_id,
            )
        else:
            result.upguard_only.append(ug_risk)

    for r in report_risks:
        if r.risk_id not in matched_report_ids:
            result.report_only.append(r)

    log.info(
        "reconciliation_complete",
        merged=len(result.merged),
        report_only=len(result.report_only),
        upguard_only=len(result.upguard_only),
    )
    return result


def _merge_linked(report: Risk, upguard: Risk) -> Risk:
    """Report risk is the primary; enrich with UpGuard data."""
    merged = report.model_copy()
    if upguard.inherent_rating and not merged.inherent_rating:
        merged.inherent_rating = upguard.inherent_rating
    if upguard.description and not merged.description:
        merged.description = upguard.description
    return merged
