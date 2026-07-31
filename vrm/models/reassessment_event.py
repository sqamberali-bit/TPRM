from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from vrm.models.enums import TriggerEventType


class ReassessmentEvent(BaseModel):
    event_id: str = Field(description="Unique event identifier")
    vendor_id: str
    event_type: TriggerEventType
    description: str
    raised_date: date = Field(default_factory=date.today)
    resolved_date: Optional[date] = None
