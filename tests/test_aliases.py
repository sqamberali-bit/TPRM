from __future__ import annotations

from vrm.engine.aliases import (
    AliasMatch,
    build_alias_map,
    detect_duplicates,
    resolve_vendor_name,
)
from vrm.models.vendor import Vendor


def _vendor(
    vid: str = "acme",
    name: str = "Acme Corp",
    aliases: list[str] | None = None,
) -> Vendor:
    return Vendor(
        vendor_id=vid,
        legal_name=name,
        aliases=aliases or [],
    )


class TestBuildAliasMap:
    def test_includes_legal_name(self) -> None:
        vendor = _vendor(vid="acme", name="Acme Corp")
        alias_map = build_alias_map([vendor])
        assert "acme" in alias_map
        assert alias_map["acme"] == "acme"

    def test_includes_aliases(self) -> None:
        vendor = _vendor(vid="acme", name="Acme Corp", aliases=["Acme Inc.", "ACME"])
        alias_map = build_alias_map([vendor])
        assert "acme" in alias_map
        assert alias_map["acme"] == "acme"

    def test_strips_company_suffixes(self) -> None:
        vendor = _vendor(vid="acme", name="Acme Pty Ltd")
        alias_map = build_alias_map([vendor])
        assert "acme" in alias_map


class TestResolveVendorName:
    def test_exact_match(self) -> None:
        alias_map = {"acme": "acme-corp"}
        match = resolve_vendor_name("Acme", alias_map)
        assert match is not None
        assert match.matched_vendor_id == "acme-corp"
        assert match.matched_via == "exact"

    def test_substring_match(self) -> None:
        alias_map = {"acme international": "acme"}
        match = resolve_vendor_name("Acme International Holdings", alias_map)
        assert match is not None
        assert match.matched_via == "substring"

    def test_no_match(self) -> None:
        alias_map = {"acme": "acme-corp"}
        match = resolve_vendor_name("Totally Different", alias_map)
        assert match is None

    def test_empty_name(self) -> None:
        alias_map = {"acme": "acme-corp"}
        match = resolve_vendor_name("", alias_map)
        assert match is None


class TestDetectDuplicates:
    def test_finds_duplicates_by_alias(self) -> None:
        v1 = _vendor(vid="acme-1", name="Acme Corp", aliases=["Acme Inc"])
        v2 = _vendor(vid="acme-2", name="Acme Inc", aliases=[])
        dupes = detect_duplicates([v1, v2])
        assert len(dupes) == 1
        pair_ids = {dupes[0][0], dupes[0][1]}
        assert pair_ids == {"acme-1", "acme-2"}

    def test_no_duplicates(self) -> None:
        v1 = _vendor(vid="acme", name="Acme Corp")
        v2 = _vendor(vid="globex", name="Globex Corp")
        dupes = detect_duplicates([v1, v2])
        assert len(dupes) == 0

    def test_same_vendor_not_flagged(self) -> None:
        v1 = _vendor(vid="acme", name="Acme Corp", aliases=["Acme"])
        dupes = detect_duplicates([v1])
        assert len(dupes) == 0
