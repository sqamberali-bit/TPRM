"""Item 2: Contract clause tracking with reversion.

Links risks to treating clauses and flags risks whose clauses
are not yet executed. Contingent risks revert to their inherent
rating when the treating clause remains unexecuted.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from vrm.models.contract_clause import ContractClause
from vrm.models.enums import ClauseStatus, Rating, RiskStatus
from vrm.models.risk import Risk
from vrm.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class ClauseFinding:
    risk_id: str
    clause_id: str
    finding_type: str
    detail: str
    reverts_to: Optional[Rating] = None


def check_clause_reversion(
    risks: list[Risk],
    clauses: list[ContractClause],
) -> list[ClauseFinding]:
    clause_map = {c.clause_id: c for c in clauses}
    findings: list[ClauseFinding] = []

    for risk in risks:
        if not risk.treating_clauses:
            continue

        for clause_id in risk.treating_clauses:
            clause = clause_map.get(clause_id)

            if clause is None:
                findings.append(ClauseFinding(
                    risk_id=risk.risk_id,
                    clause_id=clause_id,
                    finding_type="missing_clause",
                    detail=(
                        f"Risk {risk.risk_id} references clause "
                        f"'{clause_id}' which does not exist"
                    ),
                ))
                continue

            if clause.status == ClauseStatus.EXECUTED:
                continue

            findings.append(ClauseFinding(
                risk_id=risk.risk_id,
                clause_id=clause_id,
                finding_type="unexecuted_clause",
                detail=(
                    f"Risk {risk.risk_id} treating clause '{clause_id}' "
                    f"status is {clause.status.value}, not executed"
                ),
            ))

            if (
                risk.status == RiskStatus.CONTINGENT
                and risk.contingency_reverts_to is not None
            ):
                findings.append(ClauseFinding(
                    risk_id=risk.risk_id,
                    clause_id=clause_id,
                    finding_type="reverted_risk",
                    detail=(
                        f"Risk {risk.risk_id} reverts to "
                        f"{risk.contingency_reverts_to.value} rating "
                        f"because clause '{clause_id}' is not executed"
                    ),
                    reverts_to=risk.contingency_reverts_to,
                ))

    if findings:
        log.info("clause_findings", count=len(findings))
    return findings
