from __future__ import annotations

import json
from pathlib import Path

import pytest

from vrm.engine.state import (
    get_last_run,
    load_state,
    record_vendor_sync,
    save_state,
)


def test_load_empty_state(tmp_path: Path) -> None:
    state = load_state(tmp_path / "missing.json")
    assert state == {"last_run": None, "vendors": {}}


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = {"last_run": None, "vendors": {}}
    save_state(state, path)

    loaded = load_state(path)
    assert loaded["last_run"] is not None
    assert get_last_run(loaded) is not None


def test_record_vendor_sync_tracks_previous_rating(tmp_path: Path) -> None:
    state: dict = {"last_run": None, "vendors": {}}

    record_vendor_sync(state, "acme", "acme.com", 750, 5)
    assert state["vendors"]["acme"]["rating"] == 750
    assert state["vendors"]["acme"]["previous_rating"] is None

    record_vendor_sync(state, "acme", "acme.com", 680, 7)
    assert state["vendors"]["acme"]["rating"] == 680
    assert state["vendors"]["acme"]["previous_rating"] == 750
