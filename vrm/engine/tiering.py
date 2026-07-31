"""Compute vendor tier (1-4) from tiering inputs.

Tier 1 = highest risk, most scrutiny.  Tier 4 = lowest.

Weighted scoring:
  data_sensitivity     30%
  business_criticality 25%
  access_level         15%
  data_volume          10%
  integration_depth    10%
  regulatory_exposure  10%

Score maps to tier:
  >= 3.5 => Tier 1
  >= 2.5 => Tier 2
  >= 1.5 => Tier 3
  <  1.5 => Tier 4

Each tier sets a default review cadence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from vrm.models.enums import (
    AccessLevel,
    BusinessCriticality,
    DataSensitivity,
    DataVolume,
    IntegrationDepth,
    RegulatoryExposure,
)
from vrm.models.vendor import Vendor

_SENSITIVITY_SCORES = {
    DataSensitivity.PUBLIC: 1,
    DataSensitivity.INTERNAL: 2,
    DataSensitivity.CONFIDENTIAL: 3,
    DataSensitivity.RESTRICTED: 4,
}

_CRITICALITY_SCORES = {
    BusinessCriticality.LOW: 1,
    BusinessCriticality.MEDIUM: 2,
    BusinessCriticality.HIGH: 3,
    BusinessCriticality.CRITICAL: 4,
}

_ACCESS_SCORES = {
    AccessLevel.NONE: 1,
    AccessLevel.READ_ONLY: 2,
    AccessLevel.READ_WRITE: 3,
    AccessLevel.ADMIN: 4,
}

_VOLUME_SCORES = {
    DataVolume.MINIMAL: 1,
    DataVolume.MODERATE: 2,
    DataVolume.LARGE: 3,
    DataVolume.EXTENSIVE: 4,
}

_INTEGRATION_SCORES = {
    IntegrationDepth.STANDALONE: 1,
    IntegrationDepth.API: 2,
    IntegrationDepth.DEEP: 3,
    IntegrationDepth.EMBEDDED: 4,
}

_REGULATORY_SCORES = {
    RegulatoryExposure.NONE: 1,
    RegulatoryExposure.LOW: 2,
    RegulatoryExposure.MODERATE: 3,
    RegulatoryExposure.HIGH: 4,
}

_WEIGHTS = {
    "data_sensitivity": 0.30,
    "business_criticality": 0.25,
    "access_level": 0.15,
    "data_volume": 0.10,
    "integration_depth": 0.10,
    "regulatory_exposure": 0.10,
}

TIER_CADENCE_MONTHS = {1: 6, 2: 12, 3: 18, 4: 24}


@dataclass
class TieringResult:
    score: float
    tier: int
    rationale: str
    review_cadence_months: int


def compute_tier(vendor: Vendor) -> Optional[TieringResult]:
    scores: dict[str, tuple[float, int]] = {}

    if vendor.data_sensitivity:
        scores["data_sensitivity"] = (
            _WEIGHTS["data_sensitivity"],
            _SENSITIVITY_SCORES[vendor.data_sensitivity],
        )
    if vendor.business_criticality:
        scores["business_criticality"] = (
            _WEIGHTS["business_criticality"],
            _CRITICALITY_SCORES[vendor.business_criticality],
        )
    if vendor.access_level:
        scores["access_level"] = (
            _WEIGHTS["access_level"],
            _ACCESS_SCORES[vendor.access_level],
        )
    if vendor.data_volume:
        scores["data_volume"] = (
            _WEIGHTS["data_volume"],
            _VOLUME_SCORES[vendor.data_volume],
        )
    if vendor.integration_depth:
        scores["integration_depth"] = (
            _WEIGHTS["integration_depth"],
            _INTEGRATION_SCORES[vendor.integration_depth],
        )
    if vendor.regulatory_exposure:
        scores["regulatory_exposure"] = (
            _WEIGHTS["regulatory_exposure"],
            _REGULATORY_SCORES[vendor.regulatory_exposure],
        )

    if not scores:
        return None

    total_weight = sum(w for w, _ in scores.values())
    if total_weight == 0:
        return None

    weighted_sum = sum(w * s for w, s in scores.values())
    normalised = weighted_sum / total_weight

    if normalised >= 3.5:
        tier = 1
    elif normalised >= 2.5:
        tier = 2
    elif normalised >= 1.5:
        tier = 3
    else:
        tier = 4

    parts = [f"{k}={s} (w={w:.0%})" for k, (w, s) in scores.items()]
    rationale = f"Score {normalised:.2f} -> Tier {tier}. Inputs: {', '.join(parts)}"

    return TieringResult(
        score=round(normalised, 2),
        tier=tier,
        rationale=rationale,
        review_cadence_months=TIER_CADENCE_MONTHS[tier],
    )
