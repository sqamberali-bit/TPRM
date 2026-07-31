from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from vrm.models.enums import EvidenceType


class EvidenceLink(BaseModel):
    evidence_id: str = Field(description="Unique evidence identifier")
    risk_id: str
    vendor_id: str
    evidence_type: EvidenceType
    title: str
    location: str = Field(description="SharePoint URL or Teams file path")
    uploaded_date: Optional[date] = None
    expiry_date: Optional[date] = None
