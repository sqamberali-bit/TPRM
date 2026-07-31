from __future__ import annotations

from vrm.clients.upguard import (
    RatingChange,
    detect_rating_changes,
    risks_from_questionnaires,
    risks_from_upguard,
)
from vrm.models.enums import Rating, RiskSource, RiskStatus


class TestRisksFromUpguard:
    def test_basic_risk_normalisation(self) -> None:
        raw = [
            {
                "id": "abc123",
                "risk": "Weak TLS",
                "severity": "high",
                "description": "TLS 1.0 detected",
                "category": "network_security",
            }
        ]
        risks = risks_from_upguard(raw, "acme")
        assert len(risks) == 1
        r = risks[0]
        assert r.risk_id == "acme-ug-abc123"
        assert r.ref == "ug-abc123"
        assert r.source == RiskSource.UPGUARD
        assert r.inherent_rating == Rating.HIGH
        assert r.status == RiskStatus.OPEN

    def test_waived_risk_is_accepted(self) -> None:
        raw = [
            {
                "id": "def456",
                "risk": "Open port",
                "severity": "medium",
                "risk_waivers": [{"justification": "accepted"}],
            }
        ]
        risks = risks_from_upguard(raw, "vendor-x")
        assert risks[0].status == RiskStatus.ACCEPTED
        assert risks[0].residual_rating == Rating.MEDIUM

    def test_skips_empty_id(self) -> None:
        raw = [{"risk": "No id", "severity": "low"}]
        risks = risks_from_upguard(raw, "v")
        assert len(risks) == 0


class TestRisksFromQuestionnaires:
    def test_basic_questionnaire_risk(self) -> None:
        raw = [
            {
                "risk_id": "qr-001",
                "risk_name": "No backup policy",
                "risk_severity": "high",
                "risk_text": "Vendor lacks backup",
                "risk_category": "data_protection",
                "in_remediation": False,
            }
        ]
        risks = risks_from_questionnaires(raw, "acme")
        assert len(risks) == 1
        r = risks[0]
        assert r.risk_id == "acme-qr-qr-001"
        assert r.source == RiskSource.UPGUARD
        assert r.status == RiskStatus.OPEN
        assert r.inherent_rating == Rating.HIGH

    def test_in_remediation_is_in_treatment(self) -> None:
        raw = [
            {
                "risk_id": "qr-002",
                "risk_name": "Missing encryption",
                "risk_severity": "medium",
                "in_remediation": True,
            }
        ]
        risks = risks_from_questionnaires(raw, "vendor-y")
        assert risks[0].status == RiskStatus.IN_TREATMENT


class TestRatingChanges:
    def test_detects_drop(self) -> None:
        vendors = [{"name": "Acme Corp", "primary_hostname": "acme.com", "overall_score": 600}]
        state = {"vendors": {"acme-corp": {"rating": 750, "hostname": "acme.com"}}}
        changes = detect_rating_changes(vendors, state)
        assert len(changes) == 1
        assert changes[0].direction == "drop"
        assert changes[0].previous_rating == 750
        assert changes[0].current_rating == 600
        assert changes[0].is_significant_drop is True

    def test_detects_improvement(self) -> None:
        vendors = [{"name": "Acme Corp", "primary_hostname": "acme.com", "overall_score": 800}]
        state = {"vendors": {"acme-corp": {"rating": 750}}}
        changes = detect_rating_changes(vendors, state)
        assert len(changes) == 1
        assert changes[0].direction == "improve"

    def test_new_vendor_is_flagged(self) -> None:
        vendors = [{"name": "NewCo", "primary_hostname": "newco.com", "overall_score": 500}]
        state = {"vendors": {}}
        changes = detect_rating_changes(vendors, state)
        assert len(changes) == 1
        assert changes[0].direction == "new"

    def test_no_change_produces_no_result(self) -> None:
        vendors = [{"name": "Acme Corp", "primary_hostname": "acme.com", "overall_score": 750}]
        state = {"vendors": {"acme-corp": {"rating": 750}}}
        changes = detect_rating_changes(vendors, state)
        assert len(changes) == 0

    def test_significant_drop_threshold(self) -> None:
        c = RatingChange("v", "v.com", 800, 755, "drop")
        assert c.is_significant_drop is False
        c2 = RatingChange("v", "v.com", 800, 749, "drop")
        assert c2.is_significant_drop is True
