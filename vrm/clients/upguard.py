"""UpGuard CyberRisk API client.

Base URL: https://cyber-risk.upguard.com/api/public
Auth: Authorization header with raw API key (no Bearer prefix).
Pagination: token-based cursor via page_token / page_size.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

from vrm.config import Settings
from vrm.models.enums import Rating, RiskSource, RiskStatus
from vrm.models.risk import Risk
from vrm.utils.logging import get_logger

log = get_logger(__name__)

_SEVERITY_TO_RATING: dict[str, Rating] = {
    "critical": Rating.CRITICAL,
    "high": Rating.HIGH,
    "medium": Rating.MEDIUM,
    "low": Rating.LOW,
    "info": Rating.INFO,
    "none": Rating.NONE,
}


class UpGuardClient:
    def __init__(self, settings: Settings) -> None:
        self._base = settings.upguard_base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=30.0,
            headers={"Authorization": settings.upguard_api_key},
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base}{path}"
        resp = self._client.get(url, params=params)
        if resp.status_code == 429:
            log.warning("upguard_rate_limited", path=path)
            raise RuntimeError("UpGuard API rate limited; retry later")
        resp.raise_for_status()
        return resp.json()

    def list_vendors(
        self, page_size: int = 1000, include_risks: bool = False
    ) -> list[dict[str, Any]]:
        vendors: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {
                "page_size": page_size,
                "include_risks": str(include_risks).lower(),
            }
            if page_token:
                params["page_token"] = page_token

            data = self._get("/vendors", params)
            vendors.extend(data.get("vendors", []))

            page_token = data.get("next_page_token")
            if not page_token:
                break

        log.info("upguard_vendors_fetched", count=len(vendors))
        return vendors

    def get_vendor(
        self,
        vendor_id: int | None = None,
        hostname: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if vendor_id is not None:
            params["id"] = vendor_id
        elif hostname:
            params["hostname"] = hostname
        else:
            raise ValueError("Provide either vendor_id or hostname")

        return self._get("/vendor", params)

    def get_vendor_risks(
        self, primary_hostname: str, min_severity: str = "info"
    ) -> list[dict[str, Any]]:
        data = self._get(
            "/risks/vendors",
            {"primary_hostname": primary_hostname, "min_severity": min_severity},
        )
        risks = data.get("risks", [])
        log.info(
            "upguard_risks_fetched",
            hostname=primary_hostname,
            count=len(risks),
        )
        return risks

    def get_risk_changes(
        self,
        vendor_hostname: str,
        start_date: datetime,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "vendor_primary_hostname": vendor_hostname,
            "start_date": start_date.isoformat(),
        }
        if end_date:
            params["end_date"] = end_date.isoformat()

        return self._get("/risks/vendors/diff", params)

    def get_questionnaires(
        self,
        vendor_hostname: str | None = None,
        exclude_archived: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if vendor_hostname:
            params["vendor_primary_hostname"] = vendor_hostname
        if exclude_archived:
            params["exclude_archived"] = "true"

        return self._get("/vendor/questionnaires/v2", params)

    def get_questionnaire_risks(
        self,
        vendor_id: int | None = None,
        primary_hostname: str | None = None,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        risks: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {"page_size": page_size}
            if vendor_id is not None:
                params["vendor_id"] = vendor_id
            if primary_hostname:
                params["primary_hostname"] = primary_hostname
            if page_token:
                params["page_token"] = page_token

            data = self._get("/risks/vendors/questionnaires/v2", params)
            risks.extend(data.get("risks", []))

            page_token = data.get("next_page_token")
            if not page_token:
                break

        return risks

    def close(self) -> None:
        self._client.close()


@dataclass
class RatingChange:
    vendor_id: str
    hostname: str
    previous_rating: int | None
    current_rating: int | None
    direction: str  # "drop" | "improve" | "new"

    @property
    def is_significant_drop(self) -> bool:
        if self.previous_rating is None or self.current_rating is None:
            return False
        return (self.previous_rating - self.current_rating) >= 50


def detect_rating_changes(
    current_vendors: list[dict[str, Any]],
    previous_state: dict[str, Any],
) -> list[RatingChange]:
    changes: list[RatingChange] = []
    prev_vendors = previous_state.get("vendors", {})

    for ugv in current_vendors:
        name = ugv.get("name", "")
        hostname = ugv.get("primary_hostname", "")
        current_rating = ugv.get("overall_score")
        vid = _slugify(name)

        prev = prev_vendors.get(vid, {})
        prev_rating = prev.get("rating")

        if prev_rating is None and current_rating is not None:
            changes.append(RatingChange(vid, hostname, None, current_rating, "new"))
        elif prev_rating is not None and current_rating is not None:
            if current_rating < prev_rating:
                changes.append(
                    RatingChange(vid, hostname, prev_rating, current_rating, "drop")
                )
            elif current_rating > prev_rating:
                changes.append(
                    RatingChange(vid, hostname, prev_rating, current_rating, "improve")
                )

    return changes


def _slugify(name: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return slug.strip("-")


def risks_from_upguard(
    ug_risks: list[dict[str, Any]], vendor_id: str
) -> list[Risk]:
    results: list[Risk] = []
    today = date.today()

    for raw in ug_risks:
        ug_id = str(raw.get("id", ""))
        if not ug_id:
            continue

        risk_id = f"{vendor_id}-ug-{ug_id}"
        severity = str(raw.get("severity", "info")).lower()
        rating = _SEVERITY_TO_RATING.get(severity, Rating.INFO)

        has_waiver = bool(raw.get("risk_waivers"))
        status = RiskStatus.ACCEPTED if has_waiver else RiskStatus.OPEN

        results.append(
            Risk(
                risk_id=risk_id,
                vendor_id=vendor_id,
                ref=f"ug-{ug_id}",
                source=RiskSource.UPGUARD,
                title=str(raw.get("risk", raw.get("finding", ""))),
                description=str(raw.get("description", "")),
                domain=str(raw.get("category", "")),
                inherent_rating=rating,
                residual_rating=rating if has_waiver else None,
                status=status,
                date_raised=today,
                date_updated=today,
            )
        )

    log.info("normalised_upguard_risks", vendor_id=vendor_id, count=len(results))
    return results


def risks_from_questionnaires(
    q_risks: list[dict[str, Any]], vendor_id: str
) -> list[Risk]:
    results: list[Risk] = []
    today = date.today()

    for raw in q_risks:
        q_risk_id = str(raw.get("risk_id", ""))
        if not q_risk_id:
            continue

        risk_id = f"{vendor_id}-qr-{q_risk_id}"
        severity = str(raw.get("risk_severity", "info")).lower()
        rating = _SEVERITY_TO_RATING.get(severity, Rating.INFO)

        in_remediation = raw.get("in_remediation", False)
        status = RiskStatus.IN_TREATMENT if in_remediation else RiskStatus.OPEN

        results.append(
            Risk(
                risk_id=risk_id,
                vendor_id=vendor_id,
                ref=f"qr-{q_risk_id}",
                source=RiskSource.UPGUARD,
                title=str(raw.get("risk_name", "")),
                description=str(raw.get("risk_text", "")),
                domain=str(raw.get("risk_category", "")),
                inherent_rating=rating,
                status=status,
                date_raised=today,
                date_updated=today,
            )
        )

    log.info(
        "normalised_questionnaire_risks",
        vendor_id=vendor_id,
        count=len(results),
    )
    return results
