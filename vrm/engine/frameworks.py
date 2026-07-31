"""Item 7: Framework mapping views.

Tags risks to NIST CSF 2.0, ISO 27001:2022, Essential Eight,
NSW CSP and PPIP/MNDB. Produces coverage reports and identifies
frameworks with no mapped risks.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from vrm.models.enums import FrameworkTag, Rating
from vrm.models.risk import Risk
from vrm.utils.logging import get_logger

log = get_logger(__name__)

ALL_FRAMEWORKS = frozenset(FrameworkTag)


@dataclass
class FrameworkCoverage:
    framework: FrameworkTag
    total_risks: int
    by_rating: dict[str, int] = field(default_factory=dict)
    vendor_ids: list[str] = field(default_factory=list)


@dataclass
class FrameworkGap:
    framework: FrameworkTag
    detail: str


def build_framework_coverage(risks: list[Risk]) -> list[FrameworkCoverage]:
    grouped: dict[FrameworkTag, list[Risk]] = defaultdict(list)

    for risk in risks:
        for tag in risk.framework_tags:
            grouped[tag].append(risk)

    results: list[FrameworkCoverage] = []
    for tag in sorted(grouped, key=lambda t: t.value):
        tag_risks = grouped[tag]
        by_rating: dict[str, int] = defaultdict(int)
        vendor_set: set[str] = set()

        for r in tag_risks:
            rating_key = (r.inherent_rating or Rating.NONE).value
            by_rating[rating_key] += 1
            vendor_set.add(r.vendor_id)

        results.append(FrameworkCoverage(
            framework=tag,
            total_risks=len(tag_risks),
            by_rating=dict(by_rating),
            vendor_ids=sorted(vendor_set),
        ))

    return results


def identify_framework_gaps(
    risks: list[Risk],
    required_frameworks: list[FrameworkTag] | None = None,
) -> list[FrameworkGap]:
    required = set(required_frameworks) if required_frameworks else ALL_FRAMEWORKS
    covered = set()

    for risk in risks:
        for tag in risk.framework_tags:
            covered.add(tag)

    gaps: list[FrameworkGap] = []
    for fw in sorted(required, key=lambda t: t.value):
        if fw not in covered:
            gaps.append(FrameworkGap(
                framework=fw,
                detail=f"No risks mapped to {fw.value}",
            ))

    if gaps:
        log.info("framework_gaps", count=len(gaps))
    return gaps


def untagged_risks(risks: list[Risk]) -> list[Risk]:
    return [r for r in risks if not r.framework_tags]
