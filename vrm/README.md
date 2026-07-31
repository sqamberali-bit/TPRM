# VRM — Vendor Risk Management

Lightweight tiered vendor risk register for a NSW local council.
Ingests risks from Word assessment reports and the UpGuard CyberRisk API, then upserts them into SharePoint Online (system of record).

## Architecture

```
Word reports ──┐
               ├──► Normalise ──► Reconcile ──► Diff/Merge ──► SharePoint
UpGuard API ───┘        │              │              │
                   Pydantic       Link same        Protect
                   models         real risk         manual
                                  across            fields
                                  sources
```

**Operating model layers:**

| Layer | System | This build? |
|-------|--------|-------------|
| 1 — Monitoring | UpGuard | Consumes (API) |
| 2 — Governance register | SharePoint lists | **Writes here** |
| 3 — Workflow & alerts | Power Automate | Separate (reads fields we set) |
| 4 — Reporting | Power BI / SP views | Separate |

## Prerequisites

### 1. Entra app registration (IT must provision)

Create an app registration in Microsoft Entra with:

| Permission | Type | Scope |
|------------|------|-------|
| `Sites.Selected` | Application | Grant access to the specific SharePoint site only |

Generate a client secret. Provide tenant ID, client ID, and client secret via `.env`.

### 2. SharePoint lists

Create these lists on your SharePoint site. Column internal names must match exactly.

**VRM Vendors**

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
| RiskOwner | Person or single line | **Manual field -- never overwritten** |
| BusinessOwner | Person or single line | **Manual field** |
| UpGuardVendorId | Number | |
| ExternalRating | Number | UpGuard overall score |
| RatingDate | Date | |
| NextReviewDate | Date | **Manual field** |
| ReviewCadenceMonths | Number | |

**VRM Risks**

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
| ResidualRating | Choice | Same as above |
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

**VRM Audit Log**

| Column | Type |
|--------|------|
| Title | Single line | Auto-generated summary |
| Actor | Single line |
| Entity | Single line |
| EntityId | Single line |
| Field | Single line |
| OldValue | Multi-line |
| NewValue | Multi-line |
| RunId | Single line |

### 3. UpGuard API key

Generate an API key from **UpGuard > Settings > API**.
Required permissions: read access to vendors, risks, and questionnaires.

### 4. Environment variables

Copy `.env.example` to `.env` and fill in all values.

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

### Dry run (default -- prints diff without writing)

```bash
# From local files + UpGuard
vrm sync --reports-dir ./input/reports

# UpGuard only (no local reports)
vrm sync

# Reports only, skip UpGuard
vrm sync --reports-dir ./input/reports --no-upguard
```

### Apply to SharePoint

```bash
vrm sync --apply --reports-dir ./input/reports
```

### Parse a single report (inspect mode)

```bash
vrm parse-report-cmd path/to/report.docx
```

## UpGuard integration

The UpGuard client pulls:

- **Vendor list** with current ratings and category scores
- **Vendor risks** (automated scan findings) per hostname
- **Questionnaire risks** with remediation status
- **Risk changes** (delta since last run, max 30-day window)

### Rating change detection

Each sync compares the current UpGuard rating against the previous run.
Drops are logged as warnings; drops of 50+ points are flagged as significant
in the run summary. State is persisted in `.vrm-state.json`.

### Questionnaire risks

Questionnaire-sourced risks are keyed as `{vendor_id}-qr-{risk_id}` and
carry `source = upguard`. Risks marked `in_remediation` in UpGuard map
to `status = in_treatment`.

## Sync rules

1. **Insert** new risks/vendors not in SharePoint.
2. **Update** changed system fields on existing records.
3. **Never overwrite** manual fields (risk_owner, accepted_by, acceptance_level, accepted_date, acceptance_expiry, next_review_date).
4. **Never hard-delete.** Items absent from the latest source are marked `stale` for human review.
5. **Audit trail** -- every change logged to the VRM Audit Log list.
6. **Idempotent** -- re-running produces the same result.

## Tiering model

| Tier | Review cadence | Acceptance authority |
|------|---------------|---------------------|
| 1 | 6 months | Executive |
| 2 | 12 months | Senior management |
| 3 | 18 months | Manager |
| 4 | 24 months | Team lead |

Tier is computed from weighted inputs:

| Input | Weight |
|-------|--------|
| Data sensitivity | 30% |
| Business criticality | 25% |
| Access level | 15% |
| Data volume | 10% |
| Integration depth | 10% |
| Regulatory exposure | 10% |

## Risk source reconciliation

- Report risks: keyed as `{vendor_id}-{ref}` (e.g. `pet-loyalty-F1`)
- UpGuard scan risks: keyed as `{vendor_id}-ug-{upguard_risk_id}`
- UpGuard questionnaire risks: keyed as `{vendor_id}-qr-{questionnaire_risk_id}`
- A manual link map in SharePoint can join UpGuard risks to report risks to avoid duplication.

## Tests

```bash
# Generate test fixtures (once)
python tests/create_fixtures.py

# Run tests
pytest tests/ -v
```

## Project structure

```
vrm/
├── cli.py                  # Typer CLI entry point
├── config.py               # Settings from .env via pydantic-settings
├── models/
│   ├── enums.py            # All enumerations
│   ├── vendor.py           # Vendor + Certification models
│   ├── risk.py             # Risk model
│   ├── contract_clause.py  # ContractClause model
│   ├── assessment.py       # Assessment model
│   └── audit_event.py      # AuditEvent model
├── parsers/
│   └── word_report.py      # python-docx parser (3 table types)
├── clients/
│   ├── upguard.py          # UpGuard CyberRisk API client + risk normalisation
│   └── sharepoint.py       # MS Graph / SharePoint Online client
├── engine/
│   ├── normaliser.py       # Raw data → pydantic models
│   ├── tiering.py          # Tier 1-4 computation
│   ├── reconciler.py       # Merge risks from multiple sources
│   ├── state.py            # Delta tracking / run state persistence
│   └── sync.py             # Diff/upsert with manual field protection
└── utils/
    └── logging.py          # structlog setup
tests/
├── conftest.py
├── create_fixtures.py      # Generate sample .docx fixture
├── test_word_parser.py
├── test_normaliser.py
├── test_tiering.py
├── test_sync.py
├── test_reconciler.py
├── test_upguard.py         # UpGuard risk normalisation + rating changes
└── test_state.py           # Delta tracking state persistence
```
