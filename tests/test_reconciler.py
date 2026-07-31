from __future__ import annotations

from vrm.engine.reconciler import reconcile
from vrm.models.enums import Rating, RiskSource, RiskStatus
from vrm.models.risk import Risk


def _report_risk(ref: str, vendor_id: str = "vendor") -> Risk:
    return Risk(
        risk_id=f"{vendor_id}-{ref}",
        vendor_id=vendor_id,
        ref=ref,
        source=RiskSource.ASSESSMENT_REPORT,
        title=f"Report risk {ref}",
        inherent_rating=Rating.HIGH,
    )


def _ug_risk(ug_id: str, vendor_id: str = "vendor") -> Risk:
    return Risk(
        risk_id=f"{vendor_id}-ug-{ug_id}",
        vendor_id=vendor_id,
        ref=f"ug-{ug_id}",
        source=RiskSource.UPGUARD,
        title=f"UpGuard risk {ug_id}",
        inherent_rating=Rating.MEDIUM,
    )


def test_no_links_keeps_separate() -> None:
    report_risks = [_report_risk("F1")]
    upguard_risks = [_ug_risk("123")]
    result = reconcile(report_risks, upguard_risks)

    assert len(result.report_only) == 1
    assert len(result.upguard_only) == 1
    assert len(result.merged) == 0


def test_linked_risks_merge() -> None:
    report_risks = [_report_risk("F1")]
    upguard_risks = [_ug_risk("123")]
    link_map = {"vendor-ug-123": "vendor-F1"}
    result = reconcile(report_risks, upguard_risks, link_map)

    assert len(result.merged) == 1
    assert len(result.report_only) == 0
    assert len(result.upguard_only) == 0
    assert result.merged[0].risk_id == "vendor-F1"
    assert result.linked == [("vendor-ug-123", "vendor-F1")]


def test_partial_links() -> None:
    report_risks = [_report_risk("F1"), _report_risk("F2")]
    upguard_risks = [_ug_risk("100"), _ug_risk("200")]
    link_map = {"vendor-ug-100": "vendor-F1"}
    result = reconcile(report_risks, upguard_risks, link_map)

    assert len(result.merged) == 1
    assert len(result.report_only) == 1
    assert len(result.upguard_only) == 1
