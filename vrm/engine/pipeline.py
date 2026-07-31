"""Item 9: Prospective vs active vendors.

Supports a pre-contract pipeline: tier and pre-screen prospects
before onboarding, then promote to active when ready.
"""
from __future__ import annotations

from dataclasses import dataclass

from vrm.models.enums import VendorStatus
from vrm.models.vendor import Vendor
from vrm.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class PipelineAction:
    vendor_id: str
    action: str
    detail: str


def check_pipeline(vendors: list[Vendor]) -> list[PipelineAction]:
    actions: list[PipelineAction] = []

    for vendor in vendors:
        if vendor.status != VendorStatus.PROSPECTIVE:
            continue

        if vendor.tier is None:
            actions.append(PipelineAction(
                vendor_id=vendor.vendor_id,
                action="tier_required",
                detail=(
                    f"Prospective vendor {vendor.vendor_id} has no tier assigned; "
                    f"complete tiering inputs before onboarding"
                ),
            ))
        elif vendor.data_sensitivity is None or vendor.business_criticality is None:
            actions.append(PipelineAction(
                vendor_id=vendor.vendor_id,
                action="pre_screen_incomplete",
                detail=(
                    f"Prospective vendor {vendor.vendor_id} is Tier {vendor.tier} "
                    f"but is missing required pre-screen inputs"
                ),
            ))
        else:
            actions.append(PipelineAction(
                vendor_id=vendor.vendor_id,
                action="ready_to_promote",
                detail=(
                    f"Prospective vendor {vendor.vendor_id} (Tier {vendor.tier}) "
                    f"is ready for promotion to active"
                ),
            ))

    if actions:
        log.info("pipeline_actions", count=len(actions))
    return actions


def promote_vendor(vendor: Vendor) -> bool:
    if vendor.status != VendorStatus.PROSPECTIVE:
        return False
    if vendor.tier is None:
        return False

    vendor.status = VendorStatus.ACTIVE
    log.info("vendor_promoted", vendor_id=vendor.vendor_id, tier=vendor.tier)
    return True
