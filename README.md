# Compass — Executive Oversight for Agile Federal Delivery

A Streamlit application that operationalizes CLIN acceptance, agile delivery
performance tracking, and the **hybrid acceptance + holdback workflow** that
gates payment until business value is confirmed.

Built by **Zvolvant Solutions LLC** for federal customers running agile
delivery on CLIN-structured contracts.

## What Compass does

- **Executive Command Center** — per-CLIN cards with acceptance decision,
  weighted score, KPI strip, burn vs. plan, required COR action, open-risks
  badge, and a sprint predictability trend.
- **CLIN Summary** — tabular RAG across the seven Compass KPIs with sprint
  drill-through. CORs record acceptance decisions here.
- **Readiness Dashboard** — UAT first-pass, defect leakage, cycle time, and
  availability by workstream, plus a sprint-level scatter for spotting trends.
- **Feature Value Tracker** — per-feature outcome, evidence, acceptance stage,
  and payment status. CORs trigger Stage 1 technical acceptance, Stage 2 value
  confirmation, or rework required from here.
- **Hybrid Acceptance Summary** — stage counts (technically accepted / value
  pending / fully accepted / rework required) with filters by CLIN and
  workstream, plus the average payment-release posture across the portfolio.
- **Risks & Issues** — open / monitor / closed with priority, mitigation,
  owner, due date.
- **Settings** — configurable KPI thresholds (COR-only edits).
- **Audit log** — immutable trail of every decision and threshold change,
  with actor, rationale, and timestamps.

## The hybrid acceptance + holdback model

This is the differentiator. Traditional COR tooling does technical
acceptance only. Compass adds a Stage 2 value-validation window: when a
feature is technically accepted, the contractor receives `1 - holdback_pct`
of the slice. The remaining `holdback_pct` is held pending Stage 2.

- **Fully accepted** → 100% released
- **Technically accepted** → `(1 - holdback_pct)` released, remainder held
- **Value pending** → nothing released yet
- **Rework required** → nothing released; backlog impact flagged
  (continue / reprioritize / stop)

Default holdback is 30% per feature; configurable per row.

## Quick start

```bash
git clone https://github.com/Zvolvant-SOlutions/compass
cd compass
cp .env.example .env
make install
make seed       # builds local SQLite DB from scripts/seed_db.py
make demo       # launches Streamlit on :8501
```

**Demo credentials** (password `compass-demo` for all):

| Email | Role | Can do |
| --- | --- | --- |
| `cor@example.gov` | COR | Acceptance decisions, threshold overrides, full edit |
| `pm@example.gov` | PM | Data entry, mitigations, risk management |
| `po@example.gov` | PO | Data entry, mitigations, risk management |
| `auditor@example.gov` | READONLY | Dashboards and audit log only |

## Repo layout

```
streamlit_app.py             # entrypoint with top nav and page routing
.streamlit/config.toml       # navy/gold theme
src/compass/
  branding.py                # CSS + Zvolvant palette helpers
  db.py                      # SQLite schema + connection helpers
  kpi.py                     # PURE FUNCTIONS — every KPI formula
  rag.py                     # threshold logic; configurable per kpi
  acceptance.py              # hybrid acceptance state machine
  auth.py                    # bcrypt auth + RBAC (Azure AD scaffolded for v2)
  audit.py                   # audit log write/read helpers
  ado_connector.py           # ADO REST stub (mock in v1, live in v2)
  exports.py                 # PDF + CSV invoice decision trail
  state.py                   # session state helpers
  pages/                     # one module per route
data/                        # (empty — seed_db.py generates compass.db)
scripts/seed_db.py           # initializes the DB with CLINs / sprints / features
docs/
  DATA_MODEL.md              # ERD snapshot of the 11 entities
  KPI_FORMULAS.md            # spec reference for every formula in kpi.py
  HOSTING.md                 # Streamlit Cloud deploy steps
tests/                       # pytest — KPI, RAG, acceptance, auth (no live API)
```

## KPI catalog

| KPI | Formula | Direction | Default green | Default yellow |
| --- | --- | --- | --- | --- |
| Sprint predictability | `completed / committed` | high is good | ≥ 0.85 | ≥ 0.75 |
| Story completion | `completed / committed` | high is good | ≥ 0.90 | ≥ 0.80 |
| Defect leakage | `post_release_defects / accepted_stories` | low is good | ≤ 0.05 | ≤ 0.08 |
| UAT first-pass | `uat_first_pass / uat_tests` | high is good | ≥ 0.95 | ≥ 0.90 |
| Cycle time (days) | `avg_cycle_time_days` | low is good | ≤ 7 | ≤ 10 |
| Availability | per CLIN, 0..1 | high is good | ≥ 0.995 | ≥ 0.99 |
| Burn variance | `|actual - planned| / planned` | low is good | ≤ 0.10 | ≤ 0.15 |

**Overall Weighted Score = 0.70 × Delivery Performance + 0.30 × Customer Value Score.**

Customer Value Score combines: Business Value Rate (25%), User Satisfaction
(25%), Adoption Rate (20%), Rework Rate inverted (15%), Feature Utilization
(15%).

All weights are configurable. Thresholds live in the `settings` table and are
COR-editable in the Settings page.

## ADO integration

`src/compass/ado_connector.py` is the seam. In v1, it reads from the seeded
local DB. To enable live Azure DevOps sync:

1. Provision an ADO Personal Access Token with read access to Work Items + Test Runs
2. Set `ADO_ORG`, `ADO_PROJECT`, and `ADO_PAT` in Streamlit Cloud secrets
3. Complete the WIQL queries in `_fetch_sprints_from_ado()` (scaffolded but raises NotImplementedError today)

## Azure AD / Entra SSO

`src/compass/auth.py` checks for `AZURE_AD_TENANT_ID` + `AZURE_AD_CLIENT_ID`.
When both are set, the login page shows a "Sign in with Microsoft Entra"
button (currently disabled). Wiring the MSAL flow is the v2 task — the
interface is shaped so pages don't need to change when it lights up.

## License

Proprietary. See [LICENSE](LICENSE).

---

Compass is part of Zvolvant Solutions' federal product family: **Z-GRC** for
governance/risk/compliance assessment, **Z-NIST53 Assessor** (free public tool)
for policy-document review, and **Compass** for executive acceptance oversight.
Contact `software@zvolvant.com` for engagement scoping.
