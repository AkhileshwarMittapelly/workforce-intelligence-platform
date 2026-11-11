# Project Overview — Workforce Intelligence Platform

## Executive Summary

The **Workforce Intelligence Platform** is an enterprise-grade, data-driven workforce planning, capacity management, and capability gap analysis platform. Engineered with **Python 3.11**, **MySQL 8.0**, **SQLAlchemy 2.0**, **Pandas**, and **Streamlit**, the platform translates forward-looking project delivery schedules and employee competency profiles into actionable, explainable staffing recommendations.

Enterprise resource planning typically suffers from siloed spreadsheets, hidden over-allocations, unrecorded leave impacts, stale skill assessments, and opaque staffing decisions. This platform resolves these operational challenges by delivering an end-to-end, mathematically rigorous, auditable resource optimization engine with full temporal tracking (SCD Type 2), deterministic synthetic data generation, independent anomaly detection, and role-tailored dashboards for five organizational personas.

---

## Problem Statement

Modern technology and professional services organizations navigate volatile project demands requiring multidisciplinary engineering, cloud architecture, and data science capabilities. Managing workforce allocations across matrix organizations presents several systemic failures:

1. **Labor Demand Volatility & Blindspots**: Projects frequently post overlapping, unsynchronized, or duplicate labor demands across delivery horizons without centralized validation.
2. **Hidden Capacity Over-Allocation**: Standard ERP tools clamp negative capacity or average allocation percentages over months, masking acute weekly over-allocations where employees are committed to 120%–150% load.
3. **Leave & Capacity Disconnect**: Approved PTO, parental, or sick leave recorded in HR systems often fails to deduct directly from project bench capacity, causing sudden delivery crunches.
4. **Competency Stagnation**: Employee skill matrices reflect historical certifications without expiration or recency tracking, leading to staffing assignments based on obsolete competencies.
5. **Black-Box Staffing Decisions**: Recommendations to hire externally or reassign staff lack mathematical justification, cost-benefit context, or auditable decision trails.

---

## Proposed Solution

The Workforce Intelligence Platform establishes a unified, source-driven intelligence layer that models the complete talent lifecycle:

- **Mathematical Capacity Engine**: Derives weekly employee-level capacity using true un-clamped arithmetic:
  $$\text{Contracted Hours} = \text{Base Capacity} \times \text{FTE}$$
  $$\text{Net Available Capacity} = \text{Contracted Hours} - \text{Approved Leave}$$
  $$\text{Remaining Bench Capacity} = \text{Net Capacity} - \text{Allocated Project Hours}$$
  Negative balances are explicitly surfaced as over-allocation percentages rather than artificially floored at zero.
- **Period-Specific Demand Forecasting**: Matches project demand against active, qualified supply on an ISO-week basis (`YYYY'W'WW`) while strictly filtering out stale skills (>18 months) and expired competencies.
- **Demand De-duplication Quarantine**: Detects composite duplicate demands (`project_id + role_id + skill_id + start_date + end_date`) and computes dual raw vs. corrected forecasts to prevent double-counting of FTE requirements.
- **Explainable 13-Point Recommendation Engine**: Categorizes deficits into `HIRE_EXTERNAL`, `REASSIGN_BENCH`, `UPSKILL_INTERNAL`, `ENGAGE_CONTRACTOR`, or `CROSS_TRAIN`, preserving full explainability metadata (shortage volume, bench availability, proficiency gaps, lead times, and risk scores).
- **Independent Anomaly Detection Benchmark**: Hardened detection algorithms identify four critical workforce edge cases (EC-1 through EC-4) directly from transactional data without leaking ground truth labels.
- **Dual Data Layer**: Operates seamlessly against a live MySQL 8.0 RDBMS with connection pooling and SSL encryption, or gracefully falls back to deterministic CSV seed files when running offline or in lightweight sandbox environments.

---

## Target Users & Persona Alignment

The platform provides dedicated, role-tailored workflows across five organizational stakeholder personas:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Stakeholder Persona Matrix                            │
├─────────────────────┬───────────────────────────────────────────────────────┤
│ Persona             │ Operational Focus & Primary Workflows                 │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ 👤 Employee         │ Personal profile, active project allocations, leave   │
│                     │ calendar, competency ratings, and enrolled training.  │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ 👔 Resource Manager │ Team headcount, weekly capacity reconciliation,       │
│                     │ over-allocation alerts, and bench availability.       │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ 🤝 HR Partner       │ Strategic hiring backlogs, internal upskilling        │
│                     │ cohorts, skill decay alerts, and talent acquisition.  │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ ⚙️ IT / Operations  │ Infrastructure health, database pool telemetry, table │
│                     │ row counts, and environment configuration.            │
├─────────────────────┼───────────────────────────────────────────────────────┤
│ 🛡️ System Admin     │ Data validation report (13-point check), demand dup   │
│                     │ quarantine log, anomaly benchmarking, and audit trail.│
└─────────────────────┴───────────────────────────────────────────────────────┘
```

---

## Main Features

### 1. Data Validation & Relational Integrity (13-Point Check)
A dedicated `DataValidationService` verifies:
- Primary key uniqueness across all 12 tables using deterministic regex patterns.
- Foreign key referential integrity, supporting nullable manager, approver, and project manager references.
- Mandatory field presence and schema null constraints.
- Enumeration conformance (`leave_type`, `lifecycle_status`, `seniority_level`, etc.).
- Temporal date sequencing (`start_date <= end_date`, `effective_from <= effective_to`).
- Overlapping historical version validation (SCD Type 2 consistency).
- Composite duplicate demand detection.
- Cross-table allocation and capacity reconciliation.
- Approved leave deductions against contracted capacity.
- Demand plan boundary containment within parent project start/end dates.
- Training lifecycle sequence and completion date logic.
- Capability gap arithmetic ($\text{Gap} = \max(0, \text{Demand} - \text{Supply})$).
- Ground truth reference isolation.

### 2. Source-Driven Weekly Capacity Engine
- Evaluates contracted hours against base hours and FTE factor.
- Deducts approved leave directly before allocations are evaluated.
- Identifies and flags over-allocations with exact percentages (e.g., 125%, 150%).
- Categorizes employees into `AVAILABLE_BENCH`, `PARTIALLY_ALLOCATED`, `FULLY_ALLOCATED`, `OVER_ALLOCATED`, or `ON_APPROVED_LEAVE`.

### 3. Demand Forecasting & De-duplication
- Aggregates labor requirements by ISO week (`2026-W01` through `2026-W53`) and calendar month.
- Isolates composite duplicate demand entries to prevent artificial inflation of hiring needs.
- Evaluates forecast accuracy against committed allocations using holdout backtesting (MAE, RMSE, WAPE%, Bias%).

### 4. Explainable Capability Gap Diagnostics
- Multi-factor heuristic decision tree evaluating demand FTE, internal bench supply, proficiency delta, and project delivery deadlines.
- Every recommendation outputs 13 auditable attributes: demand quantity, qualified internal supply, available bench supply, required proficiency, verified proficiency, skill freshness, training lead time, project deadline, capacity shortage, utilization risk, selected action, business reasoning, and operational assumptions.
- Governed by stateful review lifecycle: `PROPOSED` $\to$ `APPROVED` $\to$ `IN_PROGRESS` $\to$ `RESOLVED`.

### 5. Benchmark Anomaly Detection
- Scans operational tables without reading ground truth files.
- Achieves 100% Precision, Recall, and F1 score against the reference benchmark dataset.
- Eliminates false positives on valid sequential project allocations and handles missing date inputs safely.

### 6. Immutable Historical Audit Trail
- Logs state mutations across all entities with JSON diffs (`old_state`, `new_state`).
- Records operational events: `ROLE_CHANGE`, `SKILL_VERIFICATION`, `STATUS_TRANSITION`, `ALLOCATION_CONFIRMED`, `ALLOCATION_RELEASED`, `TRAINING_COMPLETED`, and `RECOMMENDATION_DECISION`.

---

## Business Value & ROI

1. **Labor Cost Optimization**: Prevents premature external recruiting by surfacing hidden internal bench capacity and eligible upskilling candidates.
2. **Delivery Predictability**: Eliminates project delays caused by double-booked lead engineers or unrecorded leave collisions.
3. **Burnout Mitigation**: Pinpoints over-allocated employees (>100% capacity) before fatigue impacts project delivery or retention.
4. **Talent Currency**: Identifies deteriorating skills (>18 months since evaluation) to maintain organizational technical competitiveness.
5. **Audit Readiness**: Provides full mathematical traceability from raw employee contracts and leave forms to high-level executive hiring plans.

---

## Innovation & Uniqueness

- **Deterministic Reproducibility**: Generates identical, provably validated synthetic datasets across platforms using fixed random seeds and cryptographic SHA-256 manifest verification.
- **Zero Feature Leakage**: Benchmarks anomaly detection purely on raw data attributes, keeping ground truth references completely isolated.
- **Unclamped Capacity Modeling**: Unlike standard enterprise software that floors negative balances, the engine models over-allocation as a first-class mathematical metric.
- **Graceful Degradation Architecture**: Functions seamlessly with live MySQL 8.0 enterprise pools or zero-install CSV fallback mode, ensuring 100% operational uptime.
