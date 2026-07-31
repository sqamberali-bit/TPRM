from __future__ import annotations

from vrm.engine.frameworks import (
    build_framework_coverage,
    identify_framework_gaps,
    untagged_risks,
)
from vrm.models.enums import FrameworkTag, Rating, RiskSource, RiskStatus
from vrm.models.risk import Risk


def _risk(
    rid: str = "acme-F1",
    tags: list[FrameworkTag] | None = None,
    rating: Rating = Rating.HIGH,
) -> Risk:
    return Risk(
        risk_id=rid,
        vendor_id="acme",
        ref="F1",
        source=RiskSource.ASSESSMENT_REPORT,
        title="Test",
        inherent_rating=rating,
        status=RiskStatus.OPEN,
        framework_tags=tags or [],
    )


class TestFrameworkCoverage:
    def test_groups_by_framework(self) -> None:
        risks = [
            _risk("r1", tags=[FrameworkTag.NIST_CSF_2]),
            _risk("r2", tags=[FrameworkTag.NIST_CSF_2, FrameworkTag.ISO_27001_2022]),
            _risk("r3", tags=[FrameworkTag.ISO_27001_2022]),
        ]
        coverage = build_framework_coverage(risks)
        cov_map = {c.framework: c for c in coverage}
        assert cov_map[FrameworkTag.NIST_CSF_2].total_risks == 2
        assert cov_map[FrameworkTag.ISO_27001_2022].total_risks == 2

    def test_by_rating_counts(self) -> None:
        risks = [
            _risk("r1", tags=[FrameworkTag.NIST_CSF_2], rating=Rating.HIGH),
            _risk("r2", tags=[FrameworkTag.NIST_CSF_2], rating=Rating.CRITICAL),
            _risk("r3", tags=[FrameworkTag.NIST_CSF_2], rating=Rating.HIGH),
        ]
        coverage = build_framework_coverage(risks)
        assert coverage[0].by_rating["high"] == 2
        assert coverage[0].by_rating["critical"] == 1

    def test_empty_risks(self) -> None:
        coverage = build_framework_coverage([])
        assert len(coverage) == 0

    def test_vendor_ids_tracked(self) -> None:
        risks = [
            Risk(
                risk_id="v1-F1", vendor_id="v1", ref="F1",
                source=RiskSource.ASSESSMENT_REPORT, title="T",
                framework_tags=[FrameworkTag.NSW_CSP],
            ),
            Risk(
                risk_id="v2-F1", vendor_id="v2", ref="F1",
                source=RiskSource.ASSESSMENT_REPORT, title="T",
                framework_tags=[FrameworkTag.NSW_CSP],
            ),
        ]
        coverage = build_framework_coverage(risks)
        assert sorted(coverage[0].vendor_ids) == ["v1", "v2"]


class TestFrameworkGaps:
    def test_identifies_missing_frameworks(self) -> None:
        risks = [_risk(tags=[FrameworkTag.NIST_CSF_2])]
        gaps = identify_framework_gaps(
            risks,
            required_frameworks=[FrameworkTag.NIST_CSF_2, FrameworkTag.ISO_27001_2022],
        )
        assert len(gaps) == 1
        assert gaps[0].framework == FrameworkTag.ISO_27001_2022

    def test_no_gaps_when_all_covered(self) -> None:
        risks = [
            _risk("r1", tags=[FrameworkTag.NIST_CSF_2]),
            _risk("r2", tags=[FrameworkTag.ISO_27001_2022]),
        ]
        gaps = identify_framework_gaps(
            risks,
            required_frameworks=[FrameworkTag.NIST_CSF_2, FrameworkTag.ISO_27001_2022],
        )
        assert len(gaps) == 0

    def test_defaults_to_all_frameworks(self) -> None:
        gaps = identify_framework_gaps([])
        assert len(gaps) == len(FrameworkTag)


class TestUntaggedRisks:
    def test_finds_untagged(self) -> None:
        risks = [
            _risk("r1", tags=[FrameworkTag.NIST_CSF_2]),
            _risk("r2", tags=[]),
        ]
        result = untagged_risks(risks)
        assert len(result) == 1
        assert result[0].risk_id == "r2"

    def test_all_tagged(self) -> None:
        risks = [_risk("r1", tags=[FrameworkTag.NIST_CSF_2])]
        assert len(untagged_risks(risks)) == 0
