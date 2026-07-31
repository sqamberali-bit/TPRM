"""Upsert logic for syncing to SharePoint.

Rules:
  - Insert new risks (by risk_id).
  - Update changed system fields on existing risks.
  - NEVER overwrite manual fields (risk_owner, accepted_by, etc.).
  - NEVER hard-delete; mark items absent from latest source as 'stale'.
  - Full audit trail of every change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import uuid4

from vrm.models.audit_event import AuditEvent
from vrm.models.risk import RISK_MANUAL_FIELDS, Risk
from vrm.models.vendor import VENDOR_MANUAL_FIELDS, Vendor
from vrm.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class SyncAction:
    action: str  # "insert" | "update" | "stale" | "unchanged"
    entity_type: str
    entity_id: str
    changes: dict[str, tuple[Any, Any]] = field(default_factory=dict)


@dataclass
class SyncPlan:
    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    actions: list[SyncAction] = field(default_factory=list)
    audit_events: list[AuditEvent] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for a in self.actions:
            counts[a.action] = counts.get(a.action, 0) + 1
        return counts


def diff_risk(
    incoming: Risk,
    existing: dict[str, Any] | None,
    manual_fields: frozenset[str] | None = None,
) -> SyncAction:
    manual_fields = manual_fields or RISK_MANUAL_FIELDS

    if existing is None:
        return SyncAction(
            action="insert",
            entity_type="Risk",
            entity_id=incoming.risk_id,
        )

    changes: dict[str, tuple[Any, Any]] = {}
    incoming_dict = incoming.model_dump(mode="json")

    for field_name, new_val in incoming_dict.items():
        if field_name in manual_fields:
            continue
        if field_name == "MANUAL_FIELDS":
            continue

        old_val = existing.get(field_name)
        if _values_differ(old_val, new_val):
            changes[field_name] = (old_val, new_val)

    if changes:
        return SyncAction(
            action="update",
            entity_type="Risk",
            entity_id=incoming.risk_id,
            changes=changes,
        )

    return SyncAction(
        action="unchanged",
        entity_type="Risk",
        entity_id=incoming.risk_id,
    )


def diff_vendor(
    incoming: Vendor,
    existing: dict[str, Any] | None,
    manual_fields: frozenset[str] | None = None,
) -> SyncAction:
    manual_fields = manual_fields or VENDOR_MANUAL_FIELDS

    if existing is None:
        return SyncAction(
            action="insert",
            entity_type="Vendor",
            entity_id=incoming.vendor_id,
        )

    changes: dict[str, tuple[Any, Any]] = {}
    incoming_dict = incoming.model_dump(mode="json")

    for field_name, new_val in incoming_dict.items():
        if field_name in manual_fields:
            continue
        if field_name == "MANUAL_FIELDS":
            continue

        old_val = existing.get(field_name)
        if _values_differ(old_val, new_val):
            changes[field_name] = (old_val, new_val)

    if changes:
        return SyncAction(
            action="update",
            entity_type="Vendor",
            entity_id=incoming.vendor_id,
            changes=changes,
        )

    return SyncAction(
        action="unchanged",
        entity_type="Vendor",
        entity_id=incoming.vendor_id,
    )


def mark_stale(
    existing_ids: set[str],
    incoming_ids: set[str],
    entity_type: str,
) -> list[SyncAction]:
    stale_ids = existing_ids - incoming_ids
    return [
        SyncAction(action="stale", entity_type=entity_type, entity_id=eid)
        for eid in sorted(stale_ids)
    ]


def build_sync_plan(
    incoming_vendors: list[Vendor],
    incoming_risks: list[Risk],
    existing_vendors: dict[str, dict[str, Any]],
    existing_risks: dict[str, dict[str, Any]],
) -> SyncPlan:
    plan = SyncPlan()

    for vendor in incoming_vendors:
        action = diff_vendor(vendor, existing_vendors.get(vendor.vendor_id))
        plan.actions.append(action)
        if action.action in ("insert", "update"):
            for field_name, (old, new) in action.changes.items():
                plan.audit_events.append(
                    AuditEvent(
                        entity="Vendor",
                        entity_id=vendor.vendor_id,
                        field=field_name,
                        old_value=str(old) if old is not None else None,
                        new_value=str(new) if new is not None else None,
                        run_id=plan.run_id,
                    )
                )
            if action.action == "insert":
                plan.audit_events.append(
                    AuditEvent(
                        entity="Vendor",
                        entity_id=vendor.vendor_id,
                        field="__created__",
                        new_value="inserted",
                        run_id=plan.run_id,
                    )
                )

    for risk in incoming_risks:
        action = diff_risk(risk, existing_risks.get(risk.risk_id))
        plan.actions.append(action)
        if action.action in ("insert", "update"):
            for field_name, (old, new) in action.changes.items():
                plan.audit_events.append(
                    AuditEvent(
                        entity="Risk",
                        entity_id=risk.risk_id,
                        field=field_name,
                        old_value=str(old) if old is not None else None,
                        new_value=str(new) if new is not None else None,
                        run_id=plan.run_id,
                    )
                )
            if action.action == "insert":
                plan.audit_events.append(
                    AuditEvent(
                        entity="Risk",
                        entity_id=risk.risk_id,
                        field="__created__",
                        new_value="inserted",
                        run_id=plan.run_id,
                    )
                )

    incoming_risk_ids = {r.risk_id for r in incoming_risks}
    for stale_action in mark_stale(
        set(existing_risks.keys()), incoming_risk_ids, "Risk"
    ):
        plan.actions.append(stale_action)
        plan.audit_events.append(
            AuditEvent(
                entity="Risk",
                entity_id=stale_action.entity_id,
                field="status",
                old_value=existing_risks[stale_action.entity_id].get("status"),
                new_value="stale",
                run_id=plan.run_id,
            )
        )

    log.info("sync_plan_built", summary=plan.summary, run_id=plan.run_id)
    return plan


def _values_differ(old: Any, new: Any) -> bool:
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    return str(old) != str(new)
