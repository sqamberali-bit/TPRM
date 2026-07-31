from __future__ import annotations

from datetime import date

from vrm.engine.obligations import ObligationFinding, check_obligations
from vrm.models.enums import CertificationType
from vrm.models.vendor import Certification, Vendor


def _vendor(
    vid: str = "acme",
    certs: list[Certification] | None = None,
    pen_test_due: date | None = None,
    insurance_expiry: date | None = None,
) -> Vendor:
    return Vendor(
        vendor_id=vid,
        legal_name="Acme",
        certifications=certs or [],
        pen_test_due=pen_test_due,
        insurance_expiry=insurance_expiry,
    )


class TestCertificateTracking:
    def test_surveillance_overdue(self) -> None:
        cert = Certification(
            type=CertificationType.ISO27001,
            surveillance_due=date(2024, 3, 1),
        )
        vendor = _vendor(certs=[cert])
        findings = check_obligations([vendor], today=date(2024, 6, 1))
        surv = [f for f in findings if f.finding_type == "cert_surveillance_overdue"]
        assert len(surv) == 1
        assert surv[0].days_overdue == 92

    def test_surveillance_not_due_yet(self) -> None:
        cert = Certification(
            type=CertificationType.ISO27001,
            surveillance_due=date(2025, 3, 1),
        )
        vendor = _vendor(certs=[cert])
        findings = check_obligations([vendor], today=date(2024, 6, 1))
        surv = [f for f in findings if f.finding_type == "cert_surveillance_overdue"]
        assert len(surv) == 0

    def test_recert_overdue(self) -> None:
        cert = Certification(
            type=CertificationType.SOC2_TYPE2,
            recert_due=date(2024, 1, 15),
        )
        vendor = _vendor(certs=[cert])
        findings = check_obligations([vendor], today=date(2024, 6, 1))
        recert = [f for f in findings if f.finding_type == "cert_recert_overdue"]
        assert len(recert) == 1

    def test_no_certs_no_findings(self) -> None:
        vendor = _vendor(certs=[])
        findings = check_obligations([vendor], today=date(2024, 6, 1))
        assert len(findings) == 0


class TestPenTestTracking:
    def test_pen_test_overdue(self) -> None:
        vendor = _vendor(pen_test_due=date(2024, 2, 1))
        findings = check_obligations([vendor], today=date(2024, 6, 1))
        pt = [f for f in findings if f.finding_type == "pen_test_overdue"]
        assert len(pt) == 1
        assert pt[0].days_overdue == 121

    def test_pen_test_not_due(self) -> None:
        vendor = _vendor(pen_test_due=date(2025, 2, 1))
        findings = check_obligations([vendor], today=date(2024, 6, 1))
        pt = [f for f in findings if f.finding_type == "pen_test_overdue"]
        assert len(pt) == 0


class TestInsuranceTracking:
    def test_insurance_expired(self) -> None:
        vendor = _vendor(insurance_expiry=date(2024, 4, 30))
        findings = check_obligations([vendor], today=date(2024, 6, 1))
        ins = [f for f in findings if f.finding_type == "insurance_expired"]
        assert len(ins) == 1

    def test_insurance_valid(self) -> None:
        vendor = _vendor(insurance_expiry=date(2025, 4, 30))
        findings = check_obligations([vendor], today=date(2024, 6, 1))
        ins = [f for f in findings if f.finding_type == "insurance_expired"]
        assert len(ins) == 0
