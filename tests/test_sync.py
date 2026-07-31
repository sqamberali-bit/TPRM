from __future__ import annotations

import pytest

from vrm.engine.sync import (
    build_sync_plan,
    diff_risk,
    diff_vendor,
    mark_stale,
)
from vrm.models.enums import Rating, RiskSource, RiskStatus
from vrm.models.risk import Risk
from vrm.models.vendor import Vendor


def _make_risk(**kwargs) -> Risk:
    defaults = {
        "risk_id": "vendor-F1",
        "vendor_id": "vendor",
        "ref": "F1",
        "source": RiskSource.ASSESSMENT_REPORT,
        "title": "Test Risk",
    }
    defaults.update(kwargs)
    return Risk(**defaults)


def _make_vendor(**kwargs) -> Vendor:
    defaults = {"vendor_id": "test", "legal_name": "Test Corp"}
    defaults.update(kwargs)
    return Vendor(**defaults)


class TestDiffRisk:
    def test_insert_when_no_existing(self) -> None:
        risk = _make_risk()
        action = diff_risk(risk, None)
        assert action.action == "insert"

    def test_unchanged_when_identical(self) -> None:
        risk = _make_risk(status=RiskStatus.OPEN, inherent_rating=Rating.HIGH)
        existing = risk.model_dump(mode="json")
        action = diff_risk(risk, existing)
        assert action.action == "unchanged"

    def test_update_on_changed_field(self) -> None:
        risk = _make_risk(residual_rating=Rating.MEDIUM)
        existing = risk.model_dump(mode="json")
        existing["residual_rating"] = "high"
        action = diff_risk(risk, existing)
        assert action.action == "update"
        assert "residual_rating" in action.changes

    def test_manual_fields_protected(self) -> None:
        risk = _make_risk(accepted_by="auto-system")
        existing = risk.model_dump(mode="json")
        existing["accepted_by"] = "Jane Smith"
        action = diff_risk(risk, existing)
        assert action.action == "unchanged"


class TestDiffVendor:
    def test_insert_new_vendor(self) -> None:
        vendor = _make_vendor()
        action = diff_vendor(vendor, None)
        assert action.action == "insert"

    def test_manual_fields_protected(self) -> None:
        vendor = _make_vendor(risk_owner="auto")
        existing = vendor.model_dump(mode="json")
        existing["risk_owner"] = "Jane Smith"
        action = diff_vendor(vendor, existing)
        assert action.action == "unchanged"


class TestMarkStale:
    def test_marks_missing_as_stale(self) -> None:
        existing = {"vendor-F1", "vendor-F2", "vendor-F3"}
        incoming = {"vendor-F1", "vendor-F3"}
        stale = mark_stale(existing, incoming, "Risk")
        assert len(stale) == 1
        assert stale[0].entity_id == "vendor-F2"
        assert stale[0].action == "stale"

    def test_no_stale_when_all_present(self) -> None:
        existing = {"vendor-F1"}
        incoming = {"vendor-F1"}
        stale = mark_stale(existing, incoming, "Risk")
        assert len(stale) == 0


class TestBuildSyncPlan:
    def test_full_plan(self) -> None:
        vendors = [_make_vendor(vendor_id="v1")]
        risks = [_make_risk(risk_id="v1-F1", vendor_id="v1")]

        existing_risks = {
            "v1-F1": {"risk_id": "v1-F1", "status": "open", "title": "Old Title"},
            "v1-F2": {"risk_id": "v1-F2", "status": "open"},
        }

        plan = build_sync_plan(vendors, risks, {}, existing_risks)
        actions_by_type = {}
        for a in plan.actions:
            actions_by_type.setdefault(a.action, []).append(a)

        assert "insert" in actions_by_type  # vendor v1 is new
        assert "stale" in actions_by_type   # v1-F2 is stale
        assert len(plan.audit_events) > 0
        assert plan.run_id
