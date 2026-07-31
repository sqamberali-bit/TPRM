from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from vrm.models.enums import ExceptionStatus


class RiskException(BaseModel):
    exception_id: str = Field(description="Unique exception identifier")
    risk_id: str
    vendor_id: str
    scope: str = Field(description="What the exception covers")
    owner: str
    justification: str
    granted_date: date
    expiry_date: date
    status: ExceptionStatus = ExceptionStatus.ACTIVE
    revoked_date: Optional[date] = None
    revoked_reason: Optional[str] = None
