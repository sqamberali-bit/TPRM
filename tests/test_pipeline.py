from __future__ import annotations

from vrm.engine.pipeline import PipelineAction, check_pipeline, promote_vendor
from vrm.models.enums import DataSensitivity, BusinessCriticality, VendorStatus
from vrm.models.vendor import Vendor


def _vendor(
    vid: str = "acme",
    status: VendorStatus = VendorStatus.PROSPECTIVE,
    tier: int | None = None,
    data_sensitivity: DataSensitivity | None = None,
    business_criticality: BusinessCriticality | None = None,
) -> Vendor:
    return Vendor(
        vendor_id=vid,
        legal_name="Acme",
        status=status,
        tier=tier,
        data_sensitivity=data_sensitivity,
        business_criticality=business_criticality,
    )


class TestCheckPipeline:
    def test_untiered_prospect_needs_tier(self) -> None:
        vendor = _vendor(tier=None)
        actions = check_pipeline([vendor])
        assert len(actions) == 1
        assert actions[0].action == "tier_required"

    def test_tiered_but_incomplete_prescreen(self) -> None:
        vendor = _vendor(tier=2, data_sensitivity=DataSensitivity.INTERNAL)
        actions = check_pipeline([vendor])
        assert len(actions) == 1
        assert actions[0].action == "pre_screen_incomplete"

    def test_ready_to_promote(self) -> None:
        vendor = _vendor(
            tier=2,
            data_sensitivity=DataSensitivity.CONFIDENTIAL,
            business_criticality=BusinessCriticality.HIGH,
        )
        actions = check_pipeline([vendor])
        assert len(actions) == 1
        assert actions[0].action == "ready_to_promote"

    def test_active_vendor_skipped(self) -> None:
        vendor = _vendor(status=VendorStatus.ACTIVE, tier=2)
        actions = check_pipeline([vendor])
        assert len(actions) == 0


class TestPromoteVendor:
    def test_promotes_tiered_prospect(self) -> None:
        vendor = _vendor(tier=3)
        result = promote_vendor(vendor)
        assert result is True
        assert vendor.status == VendorStatus.ACTIVE

    def test_rejects_untiered(self) -> None:
        vendor = _vendor(tier=None)
        result = promote_vendor(vendor)
        assert result is False
        assert vendor.status == VendorStatus.PROSPECTIVE

    def test_rejects_already_active(self) -> None:
        vendor = _vendor(status=VendorStatus.ACTIVE, tier=2)
        result = promote_vendor(vendor)
        assert result is False
