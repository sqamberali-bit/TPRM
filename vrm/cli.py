"""VRM CLI — Vendor Risk Management sync tool."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import typer

from vrm.config import Settings
from vrm.utils.logging import get_logger, setup_logging

app = typer.Typer(name="vrm", help="Vendor Risk Management sync tool")


@app.command()
def sync(
    reports_dir: Optional[Path] = typer.Option(
        None, help="Directory containing Word assessment reports"
    ),
    vendor_id: Optional[str] = typer.Option(
        None, help="Override vendor_id slug for report ingestion"
    ),
    upguard: bool = typer.Option(
        True, help="Pull risks from UpGuard API"
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply",
        help="Print diff without writing to SharePoint",
    ),
    log_level: str = typer.Option("INFO", help="Log level"),
) -> None:
    """Ingest reports, pull UpGuard data, and sync to SharePoint."""
    setup_logging(log_level)
    log = get_logger("vrm.cli")

    settings = Settings()
    if reports_dir:
        settings.reports_dir = reports_dir

    from vrm.engine.normaliser import risks_from_report, slugify
    from vrm.engine.state import get_last_run, load_state, record_vendor_sync, save_state
    from vrm.parsers.word_report import parse_report

    all_vendors: list = []
    all_risks: list = []
    resolved_vendor_id = vendor_id
    state = load_state()
    last_run = get_last_run(state)

    report_paths = []
    if settings.reports_dir.exists():
        report_paths = sorted(settings.reports_dir.glob("*.docx"))

    if not report_paths:
        log.info("no_reports_found", dir=str(settings.reports_dir))

    for rpath in report_paths:
        if rpath.name.startswith("~$"):
            continue
        parsed = parse_report(rpath)
        vid = resolved_vendor_id or slugify(parsed.vendor_name or rpath.stem)
        risks = risks_from_report(parsed, vid)
        all_risks.extend(risks)
        log.info(
            "report_ingested",
            file=rpath.name,
            vendor_id=vid,
            findings=len(parsed.findings),
            residual=len(parsed.residual_risks),
            risks=len(risks),
        )

    rating_changes = []
    if upguard and settings.upguard_api_key:
        from vrm.clients.upguard import (
            UpGuardClient,
            detect_rating_changes,
            risks_from_questionnaires,
            risks_from_upguard,
        )

        log.info("upguard_sync_start")
        ug = UpGuardClient(settings)
        try:
            ug_vendors = ug.list_vendors()
            rating_changes = detect_rating_changes(ug_vendors, state)

            for change in rating_changes:
                if change.direction == "drop":
                    log.warning(
                        "rating_drop",
                        vendor=change.vendor_id,
                        previous=change.previous_rating,
                        current=change.current_rating,
                        significant=change.is_significant_drop,
                    )

            for ugv in ug_vendors:
                hostname = ugv.get("primary_hostname", "")
                ug_id = ugv.get("id")
                name = ugv.get("name", hostname)
                vid = slugify(name)
                overall_score = ugv.get("overall_score")

                existing = next(
                    (v for v in all_vendors if v.vendor_id == vid), None
                )
                if existing:
                    existing.upguard_vendor_id = ug_id
                    existing.external_rating = overall_score
                else:
                    from vrm.models.vendor import Vendor

                    all_vendors.append(
                        Vendor(
                            vendor_id=vid,
                            legal_name=name,
                            upguard_vendor_id=ug_id,
                            external_rating=overall_score,
                        )
                    )

                vendor_risk_count = 0
                if hostname:
                    ug_risks_raw = ug.get_vendor_risks(hostname)
                    ug_risks = risks_from_upguard(ug_risks_raw, vid)
                    all_risks.extend(ug_risks)
                    vendor_risk_count += len(ug_risks)

                    q_risks_raw = ug.get_questionnaire_risks(
                        primary_hostname=hostname
                    )
                    if q_risks_raw:
                        q_risks = risks_from_questionnaires(q_risks_raw, vid)
                        all_risks.extend(q_risks)
                        vendor_risk_count += len(q_risks)
                        log.info(
                            "questionnaire_risks",
                            vendor=vid,
                            count=len(q_risks),
                        )

                    if last_run:
                        start = max(
                            last_run,
                            datetime.now(timezone.utc) - timedelta(days=30),
                        )
                        try:
                            diff = ug.get_risk_changes(
                                hostname, start_date=start
                            )
                            introduced = diff.get("risks_introduced", [])
                            resolved = diff.get("risks_resolved", [])
                            if introduced or resolved:
                                log.info(
                                    "upguard_risk_delta",
                                    vendor=vid,
                                    introduced=len(introduced),
                                    resolved=len(resolved),
                                )
                        except Exception as e:
                            log.warning(
                                "risk_diff_failed",
                                vendor=vid,
                                error=str(e),
                            )

                record_vendor_sync(
                    state, vid, hostname, overall_score, vendor_risk_count
                )
        finally:
            ug.close()
        log.info("upguard_sync_complete")
    elif upguard:
        log.info("upguard_skipped", reason="no API key configured")

    from vrm.engine.tiering import compute_tier

    for vendor in all_vendors:
        result = compute_tier(vendor)
        if result and vendor.tier is None:
            vendor.tier = result.tier
            vendor.inherent_score = result.score
            vendor.tier_rationale = result.rationale
            vendor.review_cadence_months = result.review_cadence_months
            log.info(
                "tiered_vendor",
                vendor_id=vendor.vendor_id,
                tier=result.tier,
                score=result.score,
            )

    # --- Phase 3 items 7-9: framework, alias, pipeline checks ---
    from vrm.engine.aliases import detect_duplicates
    from vrm.engine.frameworks import identify_framework_gaps, untagged_risks
    from vrm.engine.pipeline import check_pipeline

    framework_gaps = identify_framework_gaps(all_risks)
    untagged = untagged_risks(all_risks)
    duplicate_vendors = detect_duplicates(all_vendors)
    pipeline_actions = check_pipeline(all_vendors)

    # --- Phase 3 items 1-6: governance checks ---
    from vrm.engine.acceptance import check_acceptances
    from vrm.engine.clauses import check_clause_reversion
    from vrm.engine.expiry import check_timebox_expiry
    from vrm.engine.obligations import check_obligations
    from vrm.engine.signals import apply_signal_actions, evaluate_upguard_signals

    acceptance_findings = check_acceptances(all_risks, all_vendors)
    clause_findings = check_clause_reversion(all_risks, [])
    obligation_findings = check_obligations(all_vendors)
    expiry_findings = check_timebox_expiry(all_risks)

    signal_actions = evaluate_upguard_signals(rating_changes, all_risks)
    apply_signal_actions(signal_actions, all_vendors)

    from vrm.engine.sync import build_sync_plan

    existing_vendors: dict = {}
    existing_risks: dict = {}

    if not dry_run and settings.sharepoint_site_url:
        from vrm.clients.sharepoint import SharePointClient

        sp = SharePointClient(settings)
        try:
            existing_vendors = sp.read_all_items("Vendor")
            existing_risks = sp.read_all_items("Risk")
        except Exception as e:
            log.error("sharepoint_read_failed", error=str(e))
            raise typer.Exit(1)
    else:
        log.info("sharepoint_read_skipped", reason="dry-run or no URL configured")

    plan = build_sync_plan(all_vendors, all_risks, existing_vendors, existing_risks)

    typer.echo(f"\n{'='*60}")
    typer.echo(f"  VRM Sync {'(DRY RUN)' if dry_run else 'APPLIED'}  —  Run {plan.run_id}")
    typer.echo(f"{'='*60}")
    typer.echo(f"  Vendors processed: {len(all_vendors)}")
    typer.echo(f"  Risks processed:   {len(all_risks)}")
    typer.echo(f"  Actions:")
    for action_type, count in sorted(plan.summary.items()):
        typer.echo(f"    {action_type:12s}: {count}")
    typer.echo(f"  Audit events:      {len(plan.audit_events)}")

    if rating_changes:
        drops = [c for c in rating_changes if c.direction == "drop"]
        if drops:
            typer.echo(f"\n  Rating drops detected: {len(drops)}")
            for d in drops:
                flag = " *** SIGNIFICANT" if d.is_significant_drop else ""
                typer.echo(
                    f"    {d.vendor_id}: {d.previous_rating} -> "
                    f"{d.current_rating}{flag}"
                )

    all_governance_findings = (
        acceptance_findings
        + clause_findings
        + obligation_findings
        + expiry_findings
    )
    if all_governance_findings:
        typer.echo(f"\n  Governance findings: {len(all_governance_findings)}")
        for finding in all_governance_findings:
            typer.echo(f"    [{finding.finding_type}] {finding.detail}")

    if signal_actions:
        typer.echo(f"\n  UpGuard signal actions: {len(signal_actions)}")
        for sa in signal_actions:
            typer.echo(f"    [{sa.signal_type}] {sa.vendor_id}: {sa.detail}")

    if framework_gaps:
        typer.echo(f"\n  Framework coverage gaps: {len(framework_gaps)}")
        for gap in framework_gaps:
            typer.echo(f"    {gap.detail}")

    if untagged:
        typer.echo(f"\n  Risks without framework tags: {len(untagged)}")

    if duplicate_vendors:
        typer.echo(f"\n  Potential duplicate vendors: {len(duplicate_vendors)}")
        for v1, v2, norm in duplicate_vendors:
            typer.echo(f"    {v1} <-> {v2} (matched on '{norm}')")

    if pipeline_actions:
        typer.echo(f"\n  Vendor pipeline actions: {len(pipeline_actions)}")
        for pa in pipeline_actions:
            typer.echo(f"    [{pa.action}] {pa.detail}")

    typer.echo(f"{'='*60}\n")

    if dry_run:
        for action in plan.actions:
            if action.action == "unchanged":
                continue
            typer.echo(
                f"  [{action.action.upper():8s}] {action.entity_type} "
                f"{action.entity_id}"
            )
            for field_name, (old, new) in action.changes.items():
                typer.echo(f"             {field_name}: {old!r} -> {new!r}")
    else:
        if not settings.sharepoint_site_url:
            log.error("no_sharepoint_url", msg="Set SHAREPOINT_SITE_URL to apply")
            raise typer.Exit(1)

        from vrm.clients.sharepoint import SharePointClient

        sp = SharePointClient(settings)
        try:
            vendor_data = {v.vendor_id: v.model_dump(mode="json") for v in all_vendors}
            risk_data = {r.risk_id: r.model_dump(mode="json") for r in all_risks}
            sp.execute_plan(
                plan,
                vendors={},
                risks={},
                vendor_data=vendor_data,
                risk_data=risk_data,
                existing_vendors=existing_vendors,
                existing_risks=existing_risks,
            )
            log.info("sync_applied", run_id=plan.run_id)
        except Exception as e:
            log.error("sync_failed", error=str(e))
            raise typer.Exit(1)
        finally:
            sp.close()

    if not dry_run:
        save_state(state)

    typer.echo("Done.")


@app.command()
def parse_report_cmd(
    report: Path = typer.Argument(help="Path to .docx assessment report"),
) -> None:
    """Parse a Word report and print extracted data (no sync)."""
    setup_logging("INFO")
    from vrm.parsers.word_report import parse_report

    result = parse_report(report)
    typer.echo(f"Vendor: {result.vendor_name}")
    typer.echo(f"Findings: {len(result.findings)}")
    for f in result.findings:
        typer.echo(f"  {f.ref}: {f.title} [{f.rating}]")
    typer.echo(f"Residual risks: {len(result.residual_risks)}")
    for r in result.residual_risks:
        typer.echo(f"  {r.ref}: {r.title} [{r.rating}]")
    typer.echo(f"Outstanding items: {len(result.outstanding_items)}")
    for o in result.outstanding_items:
        typer.echo(f"  {o.ref or '-'}: {o.item} [{o.status}]")
    typer.echo(f"Unmatched tables: {result.unmatched_tables}")


@app.command()
def snapshot(
    output: Path = typer.Option(
        Path("vrm-snapshots.json"),
        help="Path to store snapshot history",
    ),
    log_level: str = typer.Option("INFO", help="Log level"),
) -> None:
    """Take a trend snapshot of the current register state."""
    setup_logging(log_level)
    from vrm.engine.snapshots import load_snapshots, save_snapshot, take_snapshot, compare_snapshots
    from uuid import uuid4

    typer.echo("Taking register snapshot...")

    all_vendors: list = []
    all_risks: list = []

    snap = take_snapshot(all_vendors, all_risks, uuid4().hex[:12])

    previous = load_snapshots(output)
    save_snapshot(snap, output)

    typer.echo(f"  Date:      {snap.snapshot_date}")
    typer.echo(f"  Vendors:   {snap.total_vendors}")
    typer.echo(f"  Risks:     {snap.total_risks}")
    typer.echo(f"  Open:      {snap.open_risks}")
    typer.echo(f"  Review due: {snap.review_due_count}")

    if previous:
        delta = compare_snapshots(snap, previous[-1])
        typer.echo(f"\n  Changes since last snapshot:")
        typer.echo(f"    Vendors: +{delta.vendors_added} / -{delta.vendors_removed}")
        typer.echo(f"    Risks:   +{delta.risks_added} / -{delta.risks_removed}")
        typer.echo(f"    Open risk change: {delta.open_risk_change:+d}")

    typer.echo(f"\nSnapshot saved to {output}")


@app.command()
def rollup(
    log_level: str = typer.Option("INFO", help="Log level"),
) -> None:
    """Generate board-level and operational rollup views."""
    setup_logging(log_level)
    from vrm.engine.rollup import build_board_rollup, build_operational_detail

    all_vendors: list = []
    all_risks: list = []

    board = build_board_rollup(all_vendors, all_risks)

    typer.echo(f"\n{'='*60}")
    typer.echo(f"  Board Rollup — {board.snapshot_date}")
    typer.echo(f"{'='*60}")
    typer.echo(f"  Total vendors: {board.total_vendors}")
    typer.echo(f"  Total risks:   {board.total_risks}")
    typer.echo(f"  Critical:      {board.total_critical}")
    typer.echo(f"  High:          {board.total_high}")
    typer.echo(f"  Review due:    {board.total_review_due}")

    if board.tiers:
        typer.echo(f"\n  {'Tier':>6s}  {'Vendors':>8s}  {'Risks':>6s}  "
                   f"{'Crit':>5s}  {'High':>5s}  {'AvgRtg':>7s}")
        typer.echo(f"  {'-'*45}")
        for t in board.tiers:
            tier_label = str(t.tier) if t.tier else "N/A"
            avg_str = f"{t.avg_external_rating:.0f}" if t.avg_external_rating else "  -"
            typer.echo(
                f"  {tier_label:>6s}  {t.vendor_count:>8d}  {t.risk_count:>6d}  "
                f"{t.critical_risks:>5d}  {t.high_risks:>5d}  {avg_str:>7s}"
            )

    detail = build_operational_detail(all_vendors, all_risks)
    if detail:
        typer.echo(f"\n  Operational Detail:")
        typer.echo(f"  {'Vendor':<20s}  {'Tier':>4s}  {'Status':<12s}  "
                   f"{'Risks':>5s}  {'Crit':>4s}  {'High':>4s}  {'Review':>6s}")
        typer.echo(f"  {'-'*65}")
        for d in detail:
            tier_str = str(d.tier) if d.tier else "-"
            review_str = "DUE" if d.review_due else ""
            typer.echo(
                f"  {d.vendor_id:<20s}  {tier_str:>4s}  {d.status:<12s}  "
                f"{d.risk_count:>5d}  {d.critical_risks:>4d}  "
                f"{d.high_risks:>4d}  {review_str:>6s}"
            )

    typer.echo(f"{'='*60}\n")


@app.command()
def digest(
    lookback_days: int = typer.Option(7, help="Days to look back for new risks"),
    log_level: str = typer.Option("INFO", help="Log level"),
) -> None:
    """Generate a notifications digest for Power Automate."""
    setup_logging(log_level)
    import json
    from vrm.engine.digest import build_digest

    all_vendors: list = []
    all_risks: list = []

    result = build_digest(all_vendors, all_risks, lookback_days=lookback_days)

    typer.echo(f"\n{'='*60}")
    typer.echo(f"  Weekly Digest — {result.generated_date}")
    typer.echo(f"  Period: {result.period_start} to {result.period_end}")
    typer.echo(f"{'='*60}")

    if not result.items:
        typer.echo("  No items to report.")
    else:
        typer.echo(f"\n  Summary:")
        for category, count in sorted(result.summary.items()):
            typer.echo(f"    {category}: {count}")

        typer.echo(f"\n  Items ({len(result.items)}):")
        for item in result.items:
            typer.echo(
                f"    [{item.priority.upper():>6s}] [{item.category}] "
                f"{item.detail}"
            )

    typer.echo(f"\n{'='*60}")
    typer.echo("\nJSON output (for Power Automate):")
    typer.echo(json.dumps({
        "generated_date": result.generated_date,
        "period_start": result.period_start,
        "period_end": result.period_end,
        "summary": result.summary,
        "items": [
            {
                "category": i.category,
                "vendor_id": i.vendor_id,
                "detail": i.detail,
                "priority": i.priority,
            }
            for i in result.items
        ],
    }, indent=2))


if __name__ == "__main__":
    app()
