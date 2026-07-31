"""Run state persistence for delta tracking.

Stores the last sync timestamp per vendor so UpGuard risk-diff
calls only pull changes since the previous run.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vrm.utils.logging import get_logger

log = get_logger(__name__)

DEFAULT_STATE_PATH = Path(".vrm-state.json")


def load_state(path: Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"last_run": None, "vendors": {}}
    with open(path) as f:
        return json.load(f)


def save_state(state: dict[str, Any], path: Path = DEFAULT_STATE_PATH) -> None:
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w") as f:
        json.dump(state, f, indent=2, default=str)
    log.info("state_saved", path=str(path))


def get_last_run(state: dict[str, Any]) -> datetime | None:
    raw = state.get("last_run")
    if not raw:
        return None
    return datetime.fromisoformat(raw)


def record_vendor_sync(
    state: dict[str, Any],
    vendor_id: str,
    hostname: str,
    rating: int | None,
    risk_count: int,
) -> None:
    vendors = state.setdefault("vendors", {})
    prev = vendors.get(vendor_id, {})
    prev_rating = prev.get("rating")

    vendors[vendor_id] = {
        "hostname": hostname,
        "rating": rating,
        "previous_rating": prev_rating,
        "risk_count": risk_count,
        "last_synced": datetime.now(timezone.utc).isoformat(),
    }
