"""Item 3: Obligation and certificate tracking.

Checks vendor certifications (ISO 27001 surveillance, recertification),
pen-test schedules, and insurance currency dates, flagging anything
overdue.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from vrm.models.vendor import Vendor
from vrm.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class ObligationFinding:
    vendor_id: str
    finding_type: str
    detail: str
    due_date: date | None = None
    days_overdue: int = 0


def check_obligations(
    vendors: list[Vendor],
    today: date | None = None,
) -> list[ObligationFinding]:
    today = today or date.today()
    findings: list[ObligationFinding] = []

    for vendor in vendors:
        for cert in vendor.certifications:
            if cert.surveillance_due and cert.surveillance_due < today:
                overdue = (today - cert.surveillance_due).days
                findings.append(ObligationFinding(
                    vendor_id=vendor.vendor_id,
                    finding_type="cert_surveillance_overdue",
                    detail=(
                        f"Vendor {vendor.vendor_id} {cert.type.value} "
                        f"surveillance was due {cert.surveillance_due.isoformat()} "
                        f"({overdue} days overdue)"
                    ),
                    due_date=cert.surveillance_due,
                    days_overdue=overdue,
                ))

            if cert.recert_due and cert.recert_due < today:
                overdue = (today - cert.recert_due).days
                findings.append(ObligationFinding(
                    vendor_id=vendor.vendor_id,
                    finding_type="cert_recert_overdue",
                    detail=(
                        f"Vendor {vendor.vendor_id} {cert.type.value} "
                        f"recertification was due {cert.recert_due.isoformat()} "
                        f"({overdue} days overdue)"
                    ),
                    due_date=cert.recert_due,
                    days_overdue=overdue,
                ))

        if vendor.pen_test_due and vendor.pen_test_due < today:
            overdue = (today - vendor.pen_test_due).days
            findings.append(ObligationFinding(
                vendor_id=vendor.vendor_id,
                finding_type="pen_test_overdue",
                detail=(
                    f"Vendor {vendor.vendor_id} pen test was due "
                    f"{vendor.pen_test_due.isoformat()} ({overdue} days overdue)"
                ),
                due_date=vendor.pen_test_due,
                days_overdue=overdue,
            ))

        if vendor.insurance_expiry and vendor.insurance_expiry < today:
            overdue = (today - vendor.insurance_expiry).days
            findings.append(ObligationFinding(
                vendor_id=vendor.vendor_id,
                finding_type="insurance_expired",
                detail=(
                    f"Vendor {vendor.vendor_id} insurance expired "
                    f"{vendor.insurance_expiry.isoformat()} ({overdue} days overdue)"
                ),
                due_date=vendor.insurance_expiry,
                days_overdue=overdue,
            ))

    if findings:
        log.info("obligation_findings", count=len(findings))
    return findings
