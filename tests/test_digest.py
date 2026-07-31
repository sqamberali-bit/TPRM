from __future__ import annotations

from datetime import date

from vrm.engine.digest import DigestItem, WeeklyDigest, build_digest
from vrm.models.enums import (
    CertificationType,
    Rating,
    RiskSource,
    RiskStatus,
)
from vrm.models.risk import Risk
from vrm.models.vendor import Certification, Vendor


def _vendor(
    vid: str = "acme",
    review_due: bool = False,
    review_due_reason: str | None = None,
    next_review_date: date | None = None,
    certs: list[Certification] | None = None,
) -> Vendor:
    return Vendor(
        vendor_id=vid, legal_name="Acme",
        review_due=review_due, review_due_reason=review_due_reason,
        next_review_date=next_review_date,
        certifications=certs or [],
    )


def _risk(
    rid: str = "acme-F1",
    vid: str = "acme",
    rating: Rating = Rating.HIGH,
    status: RiskStatus = RiskStatus.OPEN,
    date_raised: date | None = None,
    acceptance_expiry: date | None = None,
) -> Risk:
    return Risk(
        risk_id=rid, vendor_id=vid, ref="F1",
        source=RiskSource.ASSESSMENT_REPORT, title="Test risk",
        inherent_rating=rating, status=status,
        date_raised=date_raised, acceptance_expiry=acceptance_expiry,
    )


class TestBuildDigest:
    def test_new_high_risk_included(self) -> None:
        risk = _risk(rating=Rating.HIGH, date_raised=date(2024, 5, 28))
        digest = build_digest([], [risk], today=date(2024, 6, 1))
        items = [i for i in digest.items if i.category == "new_high_risk"]
        assert len(items) == 1

    def test_old_high_risk_excluded(self) -> None:
        risk = _risk(rating=Rating.HIGH, date_raised=date(2024, 1, 1))
        digest = build_digest([], [risk], today=date(2024, 6, 1))
        items = [i for i in digest.items if i.category == "new_high_risk"]
        assert len(items) == 0

    def test_critical_risk_high_priority(self) -> None:
        risk = _risk(rating=Rating.CRITICAL, date_raised=date(2024, 5, 28))
        digest = build_digest([], [risk], today=date(2024, 6, 1))
        items = [i for i in digest.items if i.category == "new_high_risk"]
        assert items[0].priority == "high"

    def test_review_due_vendor_included(self) -> None:
        vendor = _vendor(review_due=True, review_due_reason="rating drop")
        digest = build_digest([vendor], [], today=date(2024, 6, 1))
        items = [i for i in digest.items if i.category == "review_due"]
        assert len(items) == 1
        assert "rating drop" in items[0].detail

    def test_overdue_review_included(self) -> None:
        vendor = _vendor(next_review_date=date(2024, 5, 1))
        digest = build_digest([vendor], [], today=date(2024, 6, 1))
        items = [i for i in digest.items if i.category == "overdue_review"]
        assert len(items) == 1

    def test_expiring_acceptance_included(self) -> None:
        risk = _risk(
            status=RiskStatus.ACCEPTED,
            acceptance_expiry=date(2024, 6, 5),
        )
        digest = build_digest([], [risk], today=date(2024, 6, 1))
        items = [i for i in digest.items if i.category == "expiring_acceptance"]
        assert len(items) == 1

    def test_already_expired_acceptance_excluded(self) -> None:
        risk = _risk(
            status=RiskStatus.ACCEPTED,
            acceptance_expiry=date(2024, 5, 1),
        )
        digest = build_digest([], [risk], today=date(2024, 6, 1))
        items = [i for i in digest.items if i.category == "expiring_acceptance"]
        assert len(items) == 0

    def test_expiring_certificate_included(self) -> None:
        cert = Certification(
            type=CertificationType.ISO27001,
            recert_due=date(2024, 6, 15),
        )
        vendor = _vendor(certs=[cert])
        digest = build_digest([vendor], [], today=date(2024, 6, 1))
        items = [i for i in digest.items if i.category == "expiring_certificate"]
        assert len(items) == 1

    def test_summary_counts(self) -> None:
        risk = _risk(rating=Rating.HIGH, date_raised=date(2024, 5, 28))
        vendor = _vendor(review_due=True)
        digest = build_digest([vendor], [risk], today=date(2024, 6, 1))
        assert digest.summary["new_high_risk"] == 1
        assert digest.summary["review_due"] == 1

    def test_empty_digest(self) -> None:
        digest = build_digest([], [], today=date(2024, 6, 1))
        assert len(digest.items) == 0
        assert len(digest.summary) == 0
