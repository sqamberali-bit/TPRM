from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from vrm.models.enums import ClauseStatus


class ContractClause(BaseModel):
    clause_id: str
    vendor_id: str
    ref: str
    title: str
    status: ClauseStatus = ClauseStatus.DRAFTED
    executed_date: Optional[date] = None
