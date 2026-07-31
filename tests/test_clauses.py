from __future__ import annotations

from vrm.engine.clauses import ClauseFinding, check_clause_reversion
from vrm.models.contract_clause import ContractClause
from vrm.models.enums import (
    ClauseStatus,
    Rating,
    RiskSource,
    RiskStatus,
)
from vrm.models.risk import Risk


def _clause(
    cid: str = "acme-c1",
    vid: str = "acme",
    status: ClauseStatus = ClauseStatus.EXECUTED,
) -> ContractClause:
    return ContractClause(
        clause_id=cid,
        vendor_id=vid,
        ref="C1",
        title="Test clause",
        status=status,
    )


def _risk(
    rid: str = "acme-F1",
    vid: str = "acme",
    status: RiskStatus = RiskStatus.CONTINGENT,
    treating_clauses: list[str] | None = None,
    contingency_reverts_to: Rating | None = Rating.HIGH,
) -> Risk:
    return Risk(
        risk_id=rid,
        vendor_id=vid,
        ref="F1",
        source=RiskSource.ASSESSMENT_REPORT,
        title="Test risk",
        status=status,
        treating_clauses=treating_clauses or [],
        contingency_reverts_to=contingency_reverts_to,
    )


class TestClauseReversion:
    def test_executed_clause_no_finding(self) -> None:
        risk = _risk(treating_clauses=["acme-c1"])
        clause = _clause(status=ClauseStatus.EXECUTED)
        findings = check_clause_reversion([risk], [clause])
        assert len(findings) == 0

    def test_unexecuted_clause_flagged(self) -> None:
        risk = _risk(treating_clauses=["acme-c1"], status=RiskStatus.OPEN)
        clause = _clause(status=ClauseStatus.DRAFTED)
        findings = check_clause_reversion([risk], [clause])
        unexecuted = [f for f in findings if f.finding_type == "unexecuted_clause"]
        assert len(unexecuted) == 1

    def test_contingent_risk_reversion(self) -> None:
        risk = _risk(
            treating_clauses=["acme-c1"],
            status=RiskStatus.CONTINGENT,
            contingency_reverts_to=Rating.HIGH,
        )
        clause = _clause(status=ClauseStatus.AGREED)
        findings = check_clause_reversion([risk], [clause])
        reverted = [f for f in findings if f.finding_type == "reverted_risk"]
        assert len(reverted) == 1
        assert reverted[0].reverts_to == Rating.HIGH

    def test_missing_clause_flagged(self) -> None:
        risk = _risk(treating_clauses=["nonexistent"])
        findings = check_clause_reversion([risk], [])
        missing = [f for f in findings if f.finding_type == "missing_clause"]
        assert len(missing) == 1

    def test_no_treating_clauses_skipped(self) -> None:
        risk = _risk(treating_clauses=[])
        findings = check_clause_reversion([risk], [_clause()])
        assert len(findings) == 0

    def test_contingent_without_reversion_no_revert_finding(self) -> None:
        risk = _risk(
            treating_clauses=["acme-c1"],
            status=RiskStatus.CONTINGENT,
            contingency_reverts_to=None,
        )
        clause = _clause(status=ClauseStatus.DRAFTED)
        findings = check_clause_reversion([risk], [clause])
        reverted = [f for f in findings if f.finding_type == "reverted_risk"]
        assert len(reverted) == 0
        unexecuted = [f for f in findings if f.finding_type == "unexecuted_clause"]
        assert len(unexecuted) == 1
