"""Item 8: Vendor identity and alias resolution.

Resolves entity name variants to a single canonical vendor_id.
Maintains an alias map built from Vendor.aliases and detects
potential duplicates via normalised name matching.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from vrm.models.vendor import Vendor
from vrm.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class AliasMatch:
    incoming_name: str
    matched_vendor_id: str
    matched_via: str


def _normalise(name: str) -> str:
    lowered = name.strip().lower()
    lowered = re.sub(
        r"\b(pty|ltd|inc|llc|corp|group|limited|proprietary)\b\.?",
        "",
        lowered,
    )
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def build_alias_map(vendors: list[Vendor]) -> dict[str, str]:
    alias_map: dict[str, str] = {}

    for vendor in vendors:
        norm_name = _normalise(vendor.legal_name)
        alias_map[norm_name] = vendor.vendor_id

        for alias in vendor.aliases:
            norm_alias = _normalise(alias)
            if norm_alias:
                alias_map[norm_alias] = vendor.vendor_id

    return alias_map


def resolve_vendor_name(
    name: str,
    alias_map: dict[str, str],
) -> AliasMatch | None:
    norm = _normalise(name)
    if not norm:
        return None

    if norm in alias_map:
        return AliasMatch(
            incoming_name=name,
            matched_vendor_id=alias_map[norm],
            matched_via="exact",
        )

    for known, vid in alias_map.items():
        if norm in known or known in norm:
            return AliasMatch(
                incoming_name=name,
                matched_vendor_id=vid,
                matched_via="substring",
            )

    return None


def detect_duplicates(vendors: list[Vendor]) -> list[tuple[str, str, str]]:
    norm_to_vid: dict[str, list[str]] = {}

    for vendor in vendors:
        norm = _normalise(vendor.legal_name)
        if norm:
            norm_to_vid.setdefault(norm, []).append(vendor.vendor_id)
        for alias in vendor.aliases:
            norm_alias = _normalise(alias)
            if norm_alias:
                norm_to_vid.setdefault(norm_alias, []).append(vendor.vendor_id)

    duplicates: list[tuple[str, str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for norm_name, vids in norm_to_vid.items():
        unique_vids = sorted(set(vids))
        if len(unique_vids) > 1:
            for i, v1 in enumerate(unique_vids):
                for v2 in unique_vids[i + 1:]:
                    pair = (v1, v2)
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        duplicates.append((v1, v2, norm_name))

    if duplicates:
        log.warning("potential_duplicates", count=len(duplicates))
    return duplicates
