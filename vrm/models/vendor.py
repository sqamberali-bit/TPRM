from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from vrm.models.enums import (
    AccessLevel,
    BusinessCriticality,
    CertificationType,
    DataSensitivity,
    DataVolume,
    IntegrationDepth,
    RegulatoryExposure,
    VendorStatus,
)


class Certification(BaseModel):
    type: CertificationType
    id: Optional[str] = None
    issued: Optional[date] = None
    surveillance_due: Optional[date] = None
    recert_due: Optional[date] = None


class Vendor(BaseModel):
    vendor_id: str = Field(description="Stable slug, primary key")
    legal_name: str
    aliases: list[str] = Field(default_factory=list)
    country: Optional[str] = None

    application: Optional[str] = None
    data_handled: Optional[str] = None
    hosting_region: Optional[str] = None

    status: VendorStatus = VendorStatus.ACTIVE
    tier: Optional[int] = Field(default=None, ge=1, le=4)
    inherent_score: Optional[float] = None
    tier_rationale: Optional[str] = None

    data_sensitivity: Optional[DataSensitivity] = None
    business_criticality: Optional[BusinessCriticality] = None
    access_level: Optional[AccessLevel] = None
    data_volume: Optional[DataVolume] = None
    integration_depth: Optional[IntegrationDepth] = None
    regulatory_exposure: Optional[RegulatoryExposure] = None

    risk_owner: Optional[str] = None
    business_owner: Optional[str] = None

    upguard_vendor_id: Optional[int] = None
    external_rating: Optional[int] = None
    rating_date: Optional[date] = None

    certifications: list[Certification] = Field(default_factory=list)

    next_review_date: Optional[date] = None
    review_cadence_months: Optional[int] = None

    review_due: bool = False
    review_due_reason: Optional[str] = None

    pen_test_due: Optional[date] = None
    insurance_expiry: Optional[date] = None

    model_config = {"frozen": False}


VENDOR_MANUAL_FIELDS: frozenset[str] = frozenset({
    "risk_owner",
    "business_owner",
    "next_review_date",
    "tier_rationale",
})
