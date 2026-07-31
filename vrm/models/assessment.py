from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel

from vrm.models.enums import ReportType


class Assessment(BaseModel):
    report_id: str
    vendor_id: str
    report_type: ReportType = ReportType.INITIAL
    date: Optional[date] = None
    recommendation: Optional[str] = None
    residual_profile: Optional[str] = None
    source_file: Optional[str] = None
