"""Item 11: Evidence register linkage.

Links risks to their evidence artefacts (certificates, reports,
policies) stored in SharePoint/Teams. Flags risks without
evidence and evidence with expired dates.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from vrm.models.evidence import EvidenceLink
from vrm.models.enums import RiskStatus
from vrm.models.risk import Risk
from vrm.utils.logging import get_logger

log = get_logger(__name__)

_ACTIVE_STATUSES = frozenset({
    RiskStatus.OPEN,
    RiskStatus.IN_TREATMENT,
    RiskStatus.ACCEPTED,
    RiskStatus.ACCEPTED_TIMEBOXED,
    RiskStatus.CONTINGENT,
})


@dataclass
class EvidenceFinding:
    risk_id: str
    vendor_id: str
    finding_type: str
    detail: str
    evidence_id: str | None = None


def check_evidence_coverage(
    risks: list[Risk],
    evidence: list[EvidenceLink],
    today: date | None = None,
) -> list[EvidenceFinding]:
    today = today or date.today()
    findings: list[EvidenceFinding] = []

    evidence_by_risk: dict[str, list[EvidenceLink]] = defaultdict(list)
    for ev in evidence:
        evidence_by_risk[ev.risk_id].append(ev)

    for risk in risks:
        if risk.status not in _ACTIVE_STATUSES:
            continue

        risk_evidence = evidence_by_risk.get(risk.risk_id, [])

        if not risk_evidence:
            findings.append(EvidenceFinding(
                risk_id=risk.risk_id,
                vendor_id=risk.vendor_id,
                finding_type="no_evidence",
                detail=(
                    f"Active risk {risk.risk_id} has no evidence artefacts linked"
                ),
            ))

        for ev in risk_evidence:
            if ev.expiry_date and ev.expiry_date < today:
                findings.append(EvidenceFinding(
                    risk_id=risk.risk_id,
                    vendor_id=risk.vendor_id,
                    finding_type="evidence_expired",
                    detail=(
                        f"Evidence '{ev.title}' for risk {risk.risk_id} "
                        f"expired {ev.expiry_date.isoformat()}"
                    ),
                    evidence_id=ev.evidence_id,
                ))

    if findings:
        log.info("evidence_findings", count=len(findings))
    return findings
