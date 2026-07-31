from __future__ import annotations

import pytest

from vrm.engine.tiering import compute_tier
from vrm.models.enums import (
    AccessLevel,
    BusinessCriticality,
    DataSensitivity,
    DataVolume,
    IntegrationDepth,
    RegulatoryExposure,
)
from vrm.models.vendor import Vendor


def _make_vendor(**kwargs) -> Vendor:
    defaults = {"vendor_id": "test", "legal_name": "Test"}
    defaults.update(kwargs)
    return Vendor(**defaults)


def test_tier_1_critical_vendor() -> None:
    v = _make_vendor(
        data_sensitivity=DataSensitivity.RESTRICTED,
        business_criticality=BusinessCriticality.CRITICAL,
        access_level=AccessLevel.ADMIN,
        data_volume=DataVolume.EXTENSIVE,
        integration_depth=IntegrationDepth.EMBEDDED,
        regulatory_exposure=RegulatoryExposure.HIGH,
    )
    result = compute_tier(v)
    assert result is not None
    assert result.tier == 1
    assert result.review_cadence_months == 6


def test_tier_4_low_risk_vendor() -> None:
    v = _make_vendor(
        data_sensitivity=DataSensitivity.PUBLIC,
        business_criticality=BusinessCriticality.LOW,
        access_level=AccessLevel.NONE,
        data_volume=DataVolume.MINIMAL,
        integration_depth=IntegrationDepth.STANDALONE,
        regulatory_exposure=RegulatoryExposure.NONE,
    )
    result = compute_tier(v)
    assert result is not None
    assert result.tier == 4
    assert result.review_cadence_months == 24


def test_tier_2_moderate_vendor() -> None:
    v = _make_vendor(
        data_sensitivity=DataSensitivity.CONFIDENTIAL,
        business_criticality=BusinessCriticality.HIGH,
        access_level=AccessLevel.READ_WRITE,
        data_volume=DataVolume.MODERATE,
        integration_depth=IntegrationDepth.API,
        regulatory_exposure=RegulatoryExposure.MODERATE,
    )
    result = compute_tier(v)
    assert result is not None
    assert result.tier == 2


def test_no_tiering_inputs_returns_none() -> None:
    v = _make_vendor()
    result = compute_tier(v)
    assert result is None


def test_partial_inputs_still_tiers() -> None:
    v = _make_vendor(
        data_sensitivity=DataSensitivity.RESTRICTED,
        business_criticality=BusinessCriticality.CRITICAL,
    )
    result = compute_tier(v)
    assert result is not None
    assert result.tier == 1


def test_rationale_contains_inputs() -> None:
    v = _make_vendor(
        data_sensitivity=DataSensitivity.INTERNAL,
        business_criticality=BusinessCriticality.MEDIUM,
    )
    result = compute_tier(v)
    assert result is not None
    assert "data_sensitivity" in result.rationale
    assert "business_criticality" in result.rationale
