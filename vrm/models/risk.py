from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from vrm.models.enums import FrameworkTag, Rating, RiskSource, RiskStatus


class Risk(BaseModel):
    risk_id: str = Field(description="Composite: {vendor_id}-{ref}")
    vendor_id: str
    ref: str = Field(description="F/R number from report, or UpGuard finding id")

    source: RiskSource
    title: str
    description: Optional[str] = None
    domain: Optional[str] = None

    inherent_rating: Optional[Rating] = None
    residual_rating: Optional[Rating] = None
    likelihood: Optional[str] = None
    impact: Optional[str] = None

    status: RiskStatus = RiskStatus.OPEN

    treatment: Optional[str] = None
    compensating_controls: Optional[str] = None

    treating_clauses: list[str] = Field(
        default_factory=list,
        description="clause_id references",
    )
    contingency_reverts_to: Optional[Rating] = None

    timebox_expiry: Optional[date] = None
    review_trigger: Optional[str] = None

    accepted_by: Optional[str] = None
    acceptance_level: Optional[str] = None
    accepted_date: Optional[date] = None
    acceptance_expiry: Optional[date] = None

    framework_tags: list[FrameworkTag] = Field(default_factory=list)

    date_raised: Optional[date] = None
    date_updated: Optional[date] = None
    date_closed: Optional[date] = None
    source_report: Optional[str] = None

    model_config = {"frozen": False}


RISK_MANUAL_FIELDS: frozenset[str] = frozenset({
    "risk_owner",
    "accepted_by",
    "acceptance_level",
    "accepted_date",
    "acceptance_expiry",
    "next_review_date",
})
