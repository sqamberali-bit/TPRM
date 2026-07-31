"""Normalise parsed report data into the canonical pydantic models."""
from __future__ import annotations

import re
from datetime import date

from vrm.models.enums import Rating, RiskSource, RiskStatus
from vrm.models.risk import Risk
from vrm.models.vendor import Vendor
from vrm.parsers.word_report import Finding, OutstandingItem, ParsedReport, ResidualRisk
from vrm.utils.logging import get_logger

log = get_logger(__name__)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return slug.strip("-")


_RATING_MAP: dict[str, Rating] = {
    "critical": Rating.CRITICAL,
    "high": Rating.HIGH,
    "medium": Rating.MEDIUM,
    "moderate": Rating.MEDIUM,
    "low": Rating.LOW,
    "info": Rating.INFO,
    "informational": Rating.INFO,
    "none": Rating.NONE,
    "n/a": Rating.NONE,
}


def _parse_rating(text: str) -> Rating | None:
    norm = text.strip().lower()
    return _RATING_MAP.get(norm)


_STATUS_PATTERNS: list[tuple[str, RiskStatus]] = [
    (r"withdrawn", RiskStatus.WITHDRAWN),
    (r"removed", RiskStatus.REMOVED),
    (r"closed", RiskStatus.CLOSED),
    (r"resolved", RiskStatus.RESOLVED),
    (r"reverts?\s+(?:to|if)", RiskStatus.CONTINGENT),
    (r"contingent", RiskStatus.CONTINGENT),
    (r"time[\s-]*box", RiskStatus.ACCEPTED_TIMEBOXED),
    (r"accepted.*(?:until|expir)", RiskStatus.ACCEPTED_TIMEBOXED),
    (r"accepted", RiskStatus.ACCEPTED),
    (r"in[\s-]*treatment", RiskStatus.IN_TREATMENT),
    (r"in[\s-]*progress", RiskStatus.IN_TREATMENT),
    (r"open", RiskStatus.OPEN),
]


def derive_status(text: str) -> RiskStatus:
    norm = text.strip().lower()
    for pattern, status in _STATUS_PATTERNS:
        if re.search(pattern, norm):
            return status
    return RiskStatus.OPEN


def _parse_contingency_rating(text: str) -> Rating | None:
    m = re.search(r"reverts?\s+to\s+(\w+)", text, re.IGNORECASE)
    if m:
        return _parse_rating(m.group(1))
    return None


def risks_from_report(
    report: ParsedReport, vendor_id: str
) -> list[Risk]:
    risks: list[Risk] = []
    today = date.today()

    residual_by_ref: dict[str, ResidualRisk] = {
        rr.ref.strip(): rr for rr in report.residual_risks
    }
    outstanding_by_ref: dict[str, OutstandingItem] = {}
    for oi in report.outstanding_items:
        if oi.ref:
            outstanding_by_ref[oi.ref.strip()] = oi

    for finding in report.findings:
        ref = finding.ref.strip()
        risk_id = f"{vendor_id}-{ref}"

        residual = residual_by_ref.get(ref)
        outstanding = outstanding_by_ref.get(ref)

        status_text = ""
        if outstanding and outstanding.status:
            status_text = outstanding.status
        elif residual and residual.duration_or_trigger:
            status_text = residual.duration_or_trigger

        status = derive_status(status_text)

        inherent_rating = _parse_rating(finding.rating)
        residual_rating = _parse_rating(residual.rating) if residual else None

        contingency = None
        if residual and residual.duration_or_trigger:
            contingency = _parse_contingency_rating(residual.duration_or_trigger)

        risk = Risk(
            risk_id=risk_id,
            vendor_id=vendor_id,
            ref=ref,
            source=RiskSource.ASSESSMENT_REPORT,
            title=finding.title,
            description=finding.basis,
            inherent_rating=inherent_rating,
            residual_rating=residual_rating,
            status=status,
            compensating_controls=(
                residual.compensating_controls if residual else None
            ),
            contingency_reverts_to=contingency,
            review_trigger=(
                residual.duration_or_trigger
                if residual and not contingency
                else None
            ),
            date_raised=today,
            date_updated=today,
            source_report=report.source_file,
        )
        risks.append(risk)

    seen_refs = {f.ref.strip() for f in report.findings}
    for rr in report.residual_risks:
        if rr.ref.strip() in seen_refs:
            continue
        ref = rr.ref.strip()
        risk_id = f"{vendor_id}-{ref}"
        risks.append(
            Risk(
                risk_id=risk_id,
                vendor_id=vendor_id,
                ref=ref,
                source=RiskSource.ASSESSMENT_REPORT,
                title=rr.title,
                residual_rating=_parse_rating(rr.rating),
                status=derive_status(rr.duration_or_trigger),
                compensating_controls=rr.compensating_controls,
                contingency_reverts_to=_parse_contingency_rating(
                    rr.duration_or_trigger
                ),
                date_raised=today,
                date_updated=today,
                source_report=report.source_file,
            )
        )

    log.info("normalised_risks", vendor_id=vendor_id, count=len(risks))
    return risks
