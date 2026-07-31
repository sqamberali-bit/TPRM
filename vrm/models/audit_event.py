from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: str = "vrm-sync"
    entity: str
    entity_id: str
    field: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    run_id: str
