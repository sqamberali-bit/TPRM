"""SharePoint Online client via Microsoft Graph API.

Uses MSAL client-credentials flow with an Entra app registration.
Required permission: Sites.Selected (least privilege).
"""
from __future__ import annotations

from typing import Any

import httpx
import msal

from vrm.config import Settings
from vrm.engine.sync import SyncAction, SyncPlan
from vrm.models.audit_event import AuditEvent
from vrm.utils.logging import get_logger

log = get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

LIST_NAMES = {
    "Vendor": "VRM Vendors",
    "Risk": "VRM Risks",
    "ContractClause": "VRM Contract Clauses",
    "Assessment": "VRM Assessments",
    "AuditEvent": "VRM Audit Log",
}

_FIELD_MAP_VENDOR = {
    "vendor_id": "VendorId",
    "legal_name": "Title",
    "aliases": "Aliases",
    "country": "Country",
    "application": "Application",
    "data_handled": "DataHandled",
    "hosting_region": "HostingRegion",
    "status": "VendorStatus",
    "tier": "Tier",
    "inherent_score": "InherentScore",
    "tier_rationale": "TierRationale",
    "data_sensitivity": "DataSensitivity",
    "business_criticality": "BusinessCriticality",
    "access_level": "AccessLevel",
    "data_volume": "DataVolume",
    "integration_depth": "IntegrationDepth",
    "regulatory_exposure": "RegulatoryExposure",
    "risk_owner": "RiskOwner",
    "business_owner": "BusinessOwner",
    "upguard_vendor_id": "UpGuardVendorId",
    "external_rating": "ExternalRating",
    "rating_date": "RatingDate",
    "next_review_date": "NextReviewDate",
    "review_cadence_months": "ReviewCadenceMonths",
}

_FIELD_MAP_RISK = {
    "risk_id": "RiskId",
    "vendor_id": "VendorId",
    "ref": "Ref",
    "source": "Source",
    "title": "Title",
    "description": "Description",
    "domain": "Domain",
    "inherent_rating": "InherentRating",
    "residual_rating": "ResidualRating",
    "likelihood": "Likelihood",
    "impact": "Impact",
    "status": "RiskStatus",
    "treatment": "Treatment",
    "compensating_controls": "CompensatingControls",
    "contingency_reverts_to": "ContingencyRevertsTo",
    "timebox_expiry": "TimeboxExpiry",
    "review_trigger": "ReviewTrigger",
    "accepted_by": "AcceptedBy",
    "acceptance_level": "AcceptanceLevel",
    "accepted_date": "AcceptedDate",
    "acceptance_expiry": "AcceptanceExpiry",
    "date_raised": "DateRaised",
    "date_updated": "DateUpdated",
    "date_closed": "DateClosed",
    "source_report": "SourceReport",
}


class SharePointClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._token: str | None = None
        self._site_id: str | None = settings.sharepoint_site_id or None
        self._list_ids: dict[str, str] = {}
        self._client = httpx.Client(timeout=30.0)

    def _get_token(self) -> str:
        if self._token:
            return self._token

        app = msal.ConfidentialClientApplication(
            self._settings.azure_client_id,
            authority=f"https://login.microsoftonline.com/{self._settings.azure_tenant_id}",
            client_credential=self._settings.azure_client_secret,
        )
        result = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(f"MSAL token acquisition failed: {result.get('error_description', result)}")
        self._token = result["access_token"]
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    def _resolve_site_id(self) -> str:
        if self._site_id:
            return self._site_id

        url = self._settings.sharepoint_site_url
        parts = url.replace("https://", "").split("/sites/")
        if len(parts) != 2:
            raise ValueError(f"Cannot parse SharePoint URL: {url}")

        hostname, site_path = parts[0], parts[1].strip("/")
        resp = self._client.get(
            f"{GRAPH_BASE}/sites/{hostname}:/sites/{site_path}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        self._site_id = resp.json()["id"]
        return self._site_id

    def _resolve_list_id(self, list_name: str) -> str:
        if list_name in self._list_ids:
            return self._list_ids[list_name]

        site_id = self._resolve_site_id()
        resp = self._client.get(
            f"{GRAPH_BASE}/sites/{site_id}/lists",
            headers=self._headers(),
            params={"$filter": f"displayName eq '{list_name}'"},
        )
        resp.raise_for_status()
        lists = resp.json().get("value", [])
        if not lists:
            raise ValueError(
                f"SharePoint list '{list_name}' not found. "
                "Create it first (see README for column definitions)."
            )
        self._list_ids[list_name] = lists[0]["id"]
        return self._list_ids[list_name]

    def read_all_items(
        self, entity_type: str
    ) -> dict[str, dict[str, Any]]:
        list_name = LIST_NAMES[entity_type]
        list_id = self._resolve_list_id(list_name)
        site_id = self._resolve_site_id()

        items: dict[str, dict[str, Any]] = {}
        url: str | None = (
            f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items"
            "?$expand=fields&$top=200"
        )

        while url:
            resp = self._client.get(url, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("value", []):
                fields = item.get("fields", {})
                if entity_type == "Risk":
                    key = fields.get("RiskId", "")
                elif entity_type == "Vendor":
                    key = fields.get("VendorId", "")
                else:
                    key = fields.get("id", str(item.get("id", "")))

                if key:
                    fields["_item_id"] = item["id"]
                    items[key] = fields

            url = data.get("@odata.nextLink")

        log.info("read_sharepoint_items", entity=entity_type, count=len(items))
        return items

    def execute_plan(
        self,
        plan: SyncPlan,
        vendors: dict[str, Any],
        risks: dict[str, Any],
        vendor_data: dict[str, dict[str, Any]],
        risk_data: dict[str, dict[str, Any]],
        existing_vendors: dict[str, dict[str, Any]],
        existing_risks: dict[str, dict[str, Any]],
    ) -> None:
        for action in plan.actions:
            if action.action == "unchanged":
                continue

            if action.entity_type == "Vendor":
                self._execute_vendor_action(
                    action,
                    vendor_data.get(action.entity_id, {}),
                    existing_vendors.get(action.entity_id),
                )
            elif action.entity_type == "Risk":
                self._execute_risk_action(
                    action,
                    risk_data.get(action.entity_id, {}),
                    existing_risks.get(action.entity_id),
                )

        for event in plan.audit_events:
            self._write_audit_event(event)

    def _execute_vendor_action(
        self,
        action: SyncAction,
        data: dict[str, Any],
        existing: dict[str, Any] | None,
    ) -> None:
        list_name = LIST_NAMES["Vendor"]
        list_id = self._resolve_list_id(list_name)
        site_id = self._resolve_site_id()
        sp_fields = _to_sharepoint_fields(data, _FIELD_MAP_VENDOR)

        if action.action == "insert":
            resp = self._client.post(
                f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items",
                headers=self._headers(),
                json={"fields": sp_fields},
            )
            resp.raise_for_status()
            log.info("inserted_vendor", vendor_id=action.entity_id)

        elif action.action == "update" and existing:
            item_id = existing.get("_item_id")
            if not item_id:
                log.error("missing_item_id", entity_id=action.entity_id)
                return
            update_fields = {
                _FIELD_MAP_VENDOR[k]: v
                for k, v in action.changes.items()
                if k in _FIELD_MAP_VENDOR
                for _, v in [action.changes[k]]
            }
            if update_fields:
                resp = self._client.patch(
                    f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items/{item_id}/fields",
                    headers=self._headers(),
                    json=update_fields,
                )
                resp.raise_for_status()
                log.info("updated_vendor", vendor_id=action.entity_id)

    def _execute_risk_action(
        self,
        action: SyncAction,
        data: dict[str, Any],
        existing: dict[str, Any] | None,
    ) -> None:
        list_name = LIST_NAMES["Risk"]
        list_id = self._resolve_list_id(list_name)
        site_id = self._resolve_site_id()
        sp_fields = _to_sharepoint_fields(data, _FIELD_MAP_RISK)

        if action.action == "insert":
            resp = self._client.post(
                f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items",
                headers=self._headers(),
                json={"fields": sp_fields},
            )
            resp.raise_for_status()
            log.info("inserted_risk", risk_id=action.entity_id)

        elif action.action == "update" and existing:
            item_id = existing.get("_item_id")
            if not item_id:
                log.error("missing_item_id", entity_id=action.entity_id)
                return
            update_fields = {}
            for k, (_, new_val) in action.changes.items():
                if k in _FIELD_MAP_RISK:
                    update_fields[_FIELD_MAP_RISK[k]] = new_val
            if update_fields:
                resp = self._client.patch(
                    f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items/{item_id}/fields",
                    headers=self._headers(),
                    json=update_fields,
                )
                resp.raise_for_status()
                log.info("updated_risk", risk_id=action.entity_id)

        elif action.action == "stale" and existing:
            item_id = existing.get("_item_id")
            if item_id:
                resp = self._client.patch(
                    f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items/{item_id}/fields",
                    headers=self._headers(),
                    json={"RiskStatus": "stale"},
                )
                resp.raise_for_status()
                log.info("marked_stale", risk_id=action.entity_id)

    def _write_audit_event(self, event: AuditEvent) -> None:
        list_name = LIST_NAMES["AuditEvent"]
        try:
            list_id = self._resolve_list_id(list_name)
        except ValueError:
            log.warning("audit_list_not_found", msg="Skipping audit write")
            return

        site_id = self._resolve_site_id()
        fields = {
            "Title": f"{event.entity}:{event.entity_id}:{event.field}",
            "Actor": event.actor,
            "Entity": event.entity,
            "EntityId": event.entity_id,
            "Field": event.field,
            "OldValue": event.old_value or "",
            "NewValue": event.new_value or "",
            "RunId": event.run_id,
        }
        resp = self._client.post(
            f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items",
            headers=self._headers(),
            json={"fields": fields},
        )
        resp.raise_for_status()

    def close(self) -> None:
        self._client.close()


def _to_sharepoint_fields(
    data: dict[str, Any], field_map: dict[str, str]
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for py_name, sp_name in field_map.items():
        if py_name in data:
            val = data[py_name]
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            if val is not None:
                result[sp_name] = val
    return result
