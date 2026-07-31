# TPRM — Tiered Vendor Risk Management

Lightweight, opinionated third-party risk management system for a NSW local council.
Ingests risks from Word assessment reports and the UpGuard CyberRisk API, computes tiered vendor scores, runs governance checks, and upserts the register into SharePoint Online as the system of record.

## Architecture

```
Word reports ──┐
               ├──► Normalise ──► Reconcile ──► Governance ──► Diff/Merge ──► SharePoint
UpGuard API ───┘        │              │            │               │
                   Pydantic       Link same     14 checks       Protect
                   models         real risk     (acceptance,     manual
                                  across        obligations,     fields
                                  sources       expiry, etc.)
```

**Operating model layers**

| Layer | System | This build |
|-------|--------|------------|
| 1 — Monitoring | UpGuard CyberRisk | Consumes (API) |
| 2 — Governance register | SharePoint lists | **Writes here** |
| 3 — Workflow & alerts | Power Automate | Separate (reads fields we set) |
| 4 — Reporting | Power BI / SP views | Separate |

## Design principles

- **No secrets in code.** All credentials via `.env` / environment variables.
- **Idempotent and re-runnable.** Dry-run mode is the default; `--apply` writes.
- **No hard deletes.** Items absent from the latest source are flagged `stale` for human review.
- **Manual field protection.** Fields maintained by governance staff (risk_owner, accepted_by, acceptance dates, next_review_date) are never overwritten by sync.
- **Full audit trail.** Every field change logged (who, when, what, run ID).
- **Least privilege.** Entra app uses `Sites.Selected`; UpGuard key is read-only.
- **Validate before writing.** Pydantic models reject bad rows; partial data never reaches SharePoint.

## Tiering model

Vendor tier (1-4) drives review cadence and acceptance authority:

| Tier | Review cadence | Acceptance authority |
|------|---------------|---------------------|
| 1 | 6 months | Executive |
| 2 | 12 months | Senior management |
| 3 | 18 months | Manager |
| 4 | 24 months | Team lead |

Tier is computed from six weighted inputs:

| Input | Weight |
|-------|--------|
| Data sensitivity | 30% |
| Business criticality | 25% |
| Access level | 15% |
| Data volume | 10% |
| Integration depth | 10% |
| Regulatory exposure | 10% |

## Governance engine

The sync pipeline runs 14 governance checks before writing to SharePoint:

| # | Module | What it does |
|---|--------|-------------|
| 1 | `acceptance` | Enforces tier-based approval authority; flags missing, expired, or insufficient approvals |
| 2 | `clauses` | Links risks to contract clauses; reverts contingent risks when clauses are unexecuted |
| 3 | `obligations` | Tracks ISO 27001 surveillance/recert, pen-test schedules, insurance currency |
| 4 | `expiry` | Flags time-boxed acceptances past their expiry; reports reversion rating |
| 5 | `triggers` | Evaluates reassessment events; sets affected vendors to review-due |
| 6 | `signals` | Reacts to UpGuard rating drops and critical findings; triggers vendor reviews |
| 7 | `frameworks` | Maps risks to NIST CSF 2.0, ISO 27001:2022, Essential Eight, NSW CSP, PPIP/MNDB; reports coverage gaps |
| 8 | `aliases` | Resolves vendor name variants; detects potential duplicate vendors |
| 9 | `pipeline` | Manages prospective-to-active vendor lifecycle; flags incomplete pre-screening |
| 10 | `exceptions` | Scoped, time-limited exceptions with owner and expiry; flags expired or ownerless exceptions |
| 11 | `evidence` | Links risks to evidence artefacts; flags risks without evidence and expired evidence |
| 12 | `snapshots` | Captures periodic register snapshots for trend analysis |
| 13 | `rollup` | Produces board-level aggregate exposure by tier and operational per-vendor detail |
| 14 | `digest` | Builds weekly digest (new high risks, overdue reviews, expiring items) for Power Automate |

## Prerequisites

### 1. Entra app registration

Create an app registration in Microsoft Entra with:

| Permission | Type | Scope |
|------------|------|-------|
| `Sites.Selected` | Application | The specific SharePoint site only |

Generate a client secret. Provide tenant ID, client ID, and client secret via `.env`.

### 2. SharePoint lists

Create three lists on your SharePoint site. Column internal names must match exactly.

<details>
<summary><strong>VRM Vendors</strong> — click to expand columns</summary>

| Column | Type | Notes |
|--------|------|-------|
| VendorId | Single line (indexed) | Primary key |
| Title | Single line | Legal name (uses SP built-in Title) |
| Aliases | Multi-line | Comma-separated |
| Country | Single line | |
| Application | Single line | |
| DataHandled | Multi-line | |
| HostingRegion | Single line | |
| VendorStatus | Choice | prospective, active, offboarding, retired |
| Tier | Number | 1-4 |
| InherentScore | Number | |
| TierRationale | Multi-line | |
| DataSensitivity | Choice | public, internal, confidential, restricted |
| BusinessCriticality | Choice | low, medium, high, critical |
| AccessLevel | Choice | none, read_only, read_write, admin |
| DataVolume | Choice | minimal, moderate, large, extensive |
| IntegrationDepth | Choice | standalone, api, deep, embedded |
| RegulatoryExposure | Choice | none, low, moderate, high |
| RiskOwner | Person or single line | **Manual field** |
| BusinessOwner | Person or single line | **Manual field** |
| UpGuardVendorId | Number | |
| ExternalRating | Number | UpGuard overall score |
| RatingDate | Date | |
| NextReviewDate | Date | **Manual field** |
| ReviewCadenceMonths | Number | |

</details>

<details>
<summary><strong>VRM Risks</strong> — click to expand columns</summary>

| Column | Type | Notes |
|--------|------|-------|
| RiskId | Single line (indexed) | Primary key (`{vendor_id}-{ref}`) |
| VendorId | Single line (lookup) | |
| Ref | Single line | F/R number or UpGuard ID |
| Source | Choice | assessment_report, upguard, manual |
| Title | Single line | Uses SP built-in Title |
| Description | Multi-line | |
| Domain | Single line | Control area |
| InherentRating | Choice | critical, high, medium, low, info, none |
| ResidualRating | Choice | Same values |
| Likelihood | Single line | |
| Impact | Single line | |
| RiskStatus | Choice | open, in_treatment, accepted, accepted_timeboxed, contingent, closed, resolved, removed, withdrawn, stale |
| Treatment | Multi-line | |
| CompensatingControls | Multi-line | |
| ContingencyRevertsTo | Choice | Rating values |
| TimeboxExpiry | Date | |
| ReviewTrigger | Multi-line | |
| AcceptedBy | Person or single line | **Manual field** |
| AcceptanceLevel | Single line | **Manual field** |
| AcceptedDate | Date | **Manual field** |
| AcceptanceExpiry | Date | **Manual field** |
| DateRaised | Date | |
| DateUpdated | Date | |
| DateClosed | Date | |
| SourceReport | Single line | |

</details>

<details>
<summary><strong>VRM Audit Log</strong> — click to expand columns</summary>

| Column | Type |
|--------|------|
| Title | Single line |
| Actor | Single line |
| Entity | Single line |
| EntityId | Single line |
| Field | Single line |
| OldValue | Multi-line |
| NewValue | Multi-line |
| RunId | Single line |

</details>

### 3. UpGuard API key

Generate an API key from **UpGuard > Settings > API**.
Required permissions: read access to vendors, risks, and questionnaires.

### 4. Environment variables

Copy `.env.example` to `.env` and fill in all values:

```
UPGUARD_API_KEY=...
UPGUARD_BASE_URL=https://cyber-risk.upguard.com/api/public
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
SHAREPOINT_SITE_URL=https://yourcouncil.sharepoint.com/sites/VRM
SHAREPOINT_SITE_ID=...
REPORTS_DIR=./input/reports
DRY_RUN=true
LOG_LEVEL=INFO
```

## Installation

```bash
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Usage

### Sync (primary command)

```bash
# Dry run — prints diff without writing (default)
vrm sync --reports-dir ./input/reports

# UpGuard only, no local reports
vrm sync

# Reports only, skip UpGuard
vrm sync --reports-dir ./input/reports --no-upguard

# Apply to SharePoint
vrm sync --apply --reports-dir ./input/reports

# Single vendor override
vrm sync --reports-dir ./input/reports --vendor-id pet-loyalty
```

### Parse a single report

```bash
vrm parse-report-cmd path/to/report.docx
```

Prints extracted vendor name, findings, residual risks, and outstanding items. No side effects.

### Trend snapshot

```bash
vrm snapshot --output vrm-snapshots.json
```

Captures a point-in-time register snapshot (vendor/risk counts, open risks, review-due count) and compares with the previous snapshot.

### Board and operational rollup

```bash
vrm rollup
```

Prints a board-level summary (aggregate by tier) and operational detail (per-vendor breakdown).

### Notifications digest

```bash
vrm digest --lookback-days 7
```

Generates a weekly digest covering new high/critical risks, vendors due for review, overdue reviews, expiring acceptances, and expiring certificates. Outputs JSON for Power Automate.

## UpGuard integration

The UpGuard client pulls:

- **Vendor list** with current ratings and category scores
- **Vendor risks** (automated scan findings) per hostname
- **Questionnaire risks** with remediation status
- **Risk changes** (delta since last run, max 30-day window)

### Rating change detection

Each sync compares the current UpGuard rating against the previous run. Drops are logged as warnings; drops of 50+ points trigger the `signals` engine to flag the vendor for review. State is persisted in `.vrm-state.json`.

### Risk source reconciliation

- Report risks: keyed as `{vendor_id}-{ref}` (e.g. `pet-loyalty-F1`)
- UpGuard scan risks: keyed as `{vendor_id}-ug-{upguard_risk_id}`
- UpGuard questionnaire risks: keyed as `{vendor_id}-qr-{questionnaire_risk_id}`

No key collisions across sources. A manual link map in SharePoint can join UpGuard risks to report risks to avoid duplication.

## Sync rules

1. **Insert** new risks/vendors not in SharePoint.
2. **Update** changed system fields on existing records.
3. **Never overwrite** manual fields (risk_owner, accepted_by, acceptance_level, accepted_date, acceptance_expiry, next_review_date).
4. **Never hard-delete.** Items absent from the latest source are marked `stale` for human review.
5. **Audit trail** — every change logged to the VRM Audit Log list.
6. **Idempotent** — re-running produces the same result.

## Tests

```bash
# Generate test fixtures (once)
python tests/create_fixtures.py

# Run tests
pytest tests/ -v
```

161 tests across 20 test files covering all engine modules, parsers, clients, and models.

## Project structure

```
vrm/
├── cli.py                      # Typer CLI (sync, parse-report-cmd, snapshot, rollup, digest)
├── config.py                   # Settings from .env via pydantic-settings
├── models/
│   ├── enums.py                # All enumerations (19 enum types)
│   ├── vendor.py               # Vendor + Certification models
│   ├── risk.py                 # Risk model
│   ├── contract_clause.py      # ContractClause model
│   ├── assessment.py           # Assessment model
│   ├── audit_event.py          # AuditEvent model
│   ├── reassessment_event.py   # ReassessmentEvent model
│   ├── exception.py            # RiskException model
│   └── evidence.py             # EvidenceLink model
├── parsers/
│   └── word_report.py          # python-docx parser (3 table types, fuzzy headers)
├── clients/
│   ├── upguard.py              # UpGuard CyberRisk API client + risk normalisation
│   └── sharepoint.py           # MS Graph / SharePoint Online client (MSAL auth)
├── engine/
│   ├── normaliser.py           # Raw data → pydantic models
│   ├── tiering.py              # Tier 1-4 weighted scoring
│   ├── reconciler.py           # Merge risks from multiple sources
│   ├── state.py                # Delta tracking / run state persistence
│   ├── sync.py                 # Diff/upsert with manual field protection
│   ├── acceptance.py           # Tier-based approval authority enforcement
│   ├── clauses.py              # Contract clause tracking with reversion
│   ├── obligations.py          # Certificate / pen-test / insurance tracking
│   ├── expiry.py               # Time-boxed acceptance expiry
│   ├── triggers.py             # Event-driven reassessment triggers
│   ├── signals.py              # UpGuard signal actions (rating drops, critical risks)
│   ├── frameworks.py           # Framework mapping (NIST, ISO, Essential Eight, NSW CSP)
│   ├── aliases.py              # Vendor identity / alias resolution
│   ├── pipeline.py             # Prospective → active vendor lifecycle
│   ├── exceptions.py           # Exception register
│   ├── evidence.py             # Evidence register linkage
│   ├── snapshots.py            # Trend snapshots
│   ├── rollup.py               # Board + operational rollup
│   └── digest.py               # Notifications digest for Power Automate
└── utils/
    └── logging.py              # structlog configuration
tests/
├── conftest.py
├── create_fixtures.py          # Generate sample .docx fixture
├── test_word_parser.py         # 5 tests
├── test_normaliser.py          # 17 tests
├── test_reconciler.py          # 3 tests
├── test_sync.py                # 9 tests
├── test_tiering.py             # 6 tests
├── test_upguard.py             # 10 tests
├── test_state.py               # 3 tests
├── test_acceptance.py          # 10 tests
├── test_clauses.py             # 6 tests
├── test_obligations.py         # 8 tests
├── test_expiry.py              # 6 tests
├── test_triggers.py            # 6 tests
├── test_signals.py             # 9 tests
├── test_frameworks.py          # 9 tests
├── test_aliases.py             # 10 tests
├── test_pipeline.py            # 7 tests
├── test_exceptions.py          # 8 tests
├── test_evidence.py            # 6 tests
├── test_snapshots.py           # 7 tests
├── test_rollup.py              # 6 tests
└── test_digest.py              # 10 tests
```

## License

Internal use only — NSW local council.
