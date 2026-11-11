# Workforce Intelligence Platform

A strategic workforce planning, capacity management, and capability gap analysis platform built with **Python 3.11**, **MySQL 8.0**, **SQLAlchemy 2.0**, and **Streamlit**.

---

## 1. Problem Statement & Executive Overview

Modern enterprise organizations face continuous challenges balancing staffing supply against complex project delivery commitments:
- **Demand Forecasting**: Project staffing schedules demand resources across diverse job roles, skill taxonomies, and delivery periods.
- **Capacity & Utilization**: Employee availability fluctuates based on contracted FTE, part-time factors, approved leave, and overlapping commitments.
- **Skill Gaps & Actions**: When supply cannot satisfy demand, organizations require evidence-backed recommendations to hire externally, upskill existing staff, reassign bench talent, or engage contractors.

The **Workforce Intelligence Platform** delivers an end-to-end, traceable, and automated decision-support system covering the complete lifecycle:
1. **Master & Transactional Data**: 10 normalized relational entities enforcing SCD Type 2 temporal validity and immutable audit event logging.
2. **Deterministic Synthetics**: Reproducible baseline generation (seed: `20261022`) parameterizable from starter scale (50 employees) to enterprise volume (5,000 employees, 300 skills, 500 projects, 12 months demand).
3. **Injected Negative Scenarios**: 4 distinct labeled anomalies with a separate `ground_truth.json` for rigorous evaluator benchmarking without feature leakage.
4. **Intelligent Decision Engine**: Transparent, assumption-backed recommendations for recruitment, upskilling, and bench reallocation.
5. **Interactive Dashboard**: 6 multi-page Streamlit views tailored to 5 stakeholder personas (Employee, Manager, HR Partner, IT/Ops, and Admin).

---

## 2. System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Streamlit Presentation Layer                      │
│   ├── Workforce Overview       ├── Demand Forecasting                  │
│   ├── Skill Matrix             ├── Gap Diagnostics & Action Engine     │
│   ├── 5 Stakeholder Personas   └── Executive Analytics Dashboard       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                       Domain Services Layer                            │
│   ├── CapacityService      (FTE scaling, leave deduction, bench math)  │
│   ├── ForecastService      (Labor demand aggregation & risk scoring)   │
│   ├── GapService           (Capability shortfalls & recommendations)   │
│   └── AnalyticsService     (Executive KPIs, 12-month trend analysis)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                 Data Abstraction Layer (db_service)                     │
│               Attempts Live MySQL with PyMySQL / Pool                  │
│               Seamlessly Falls Back to Local Seed CSVs                 │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
┌───────────────────▼───────────┐  ┌─────────────────▼──────────────────┐
│        MySQL 8.0 Engine       │  │       Synthetic Data Engine        │
│   10 Core Tables + 5 Views    │  │   Deterministic RNG (Seed: 20261022)│
│   SCD Type 2 + CHECK Regex    │  │   4 Labeled Edge Cases + GroundTruth│
└───────────────────────────────┘  └────────────────────────────────────┘
```

---

## 3. Project Directory Structure

```
workforce-intelligence-platform/
│
├── run.py                                  # One-command quickstart runner (App, Datagen, Tests)
├── requirements.txt                        # Production & development dependencies
├── .env.example                            # Safe credential template
├── .gitignore                              # Exclusion rules for credentials and virtualenvs
├── README.md                               # Platform documentation & hackathon submission guide
│
├── database/                               # Database scripts & DDL
│   ├── schema.sql                          # MySQL 8.0 normalized DDL (10 tables, 5 views)
│   ├── data_dictionary.md                  # Comprehensive field definitions & validation rules
│   └── apply_schema.py                     # Schema application script for live MySQL
│
├── data/                                   # Seed datasets & validation artifacts
│   ├── roles.csv                           # Master catalog of organizational roles
│   ├── employees.csv                       # Workforce member records
│   ├── skills.csv                          # Competency catalog
│   ├── employee_skills.csv                 # Verified proficiency ratings
│   ├── projects.csv                        # Client and internal initiatives
│   ├── demand_plans.csv                    # Forward staffing demand requirements
│   ├── allocations.csv                     # Staff assignments & commitments
│   ├── availability.csv                    # Contracted, leave, bench capacity
│   ├── training.csv                        # Upskilling & enablement enrollments
│   ├── gap_analysis.csv                    # Capability shortfall diagnostics
│   ├── ground_truth.csv                    # Injected anomaly ground truth (tabular)
│   ├── ground_truth.json                   # Structured edge-case ground truth labels
│   ├── seeds.sql                           # Full SQL INSERT statements for seed data
│   ├── manifest.json                       # Generator command, seed, and lawful provenance
│   └── validation_summary.json             # Automated data integrity summary
│
├── app/                                    # Streamlit Presentation Layer
│   ├── main.py                             # Streamlit landing view & live system diagnostic
│   ├── components/
│   │   ├── charts.py                       # Plotly visualizations (gauge, heatmap, bars)
│   │   └── kpi_cards.py                    # Metric cards, alert banners, recommendation cards
│   └── pages/
│       ├── 1_Workforce_Overview.py         # Headcount, capacity & department breakdowns
│       ├── 2_Demand_Forecasting.py         # Project labor schedules, FTE gap & fulfillment
│       ├── 3_Skill_Matrix.py               # Verified proficiencies & stale skill alerts
│       ├── 4_Gap_Analysis.py               # Deficit diagnostics & recommendation inspector
│       ├── 5_Actor_Views.py                # 5 Stakeholder Personas (Emp, Mgr, HR, Ops, Admin)
│       └── 6_Analytics_Dashboard.py        # 12-Month utilization trajectory & hiring split
│
├── src/                                    # Application Core & Domain Logic
│   ├── config.py                           # Pydantic environment configuration
│   ├── db/
│   │   ├── __init__.py
│   │   └── connection.py                   # SQLAlchemy pooling & connectivity diagnostics
│   ├── models/
│   │   ├── __init__.py                     # Model exports
│   │   └── entities.py                     # SQLAlchemy 2.0 ORM declarative models
│   ├── services/
│   │   ├── capacity_service.py             # Capacity arithmetic (base * FTE - leave - alloc)
│   │   ├── forecast_service.py             # Supply vs demand forecasting & risk scoring
│   │   ├── gap_service.py                  # Shortage detection & action recommendations
│   │   ├── analytics_service.py            # Workforce KPIs & 12-month trends
│   │   └── db_service.py                   # Dual MySQL / CSV fallback query layer
│   ├── utils/
│   │   ├── __init__.py
│   │   └── id_generator.py                 # Deterministic ID generator utility
│   └── generators/
│       ├── __init__.py
│       └── synthetic_data_generator.py     # Deterministic baseline & edge-case generator
│
└── tests/                                  # Automated Pytest Suite (38 Tests)
    ├── test_capacity_service.py            # Unit tests for capacity, FTE, and leave impacts
    ├── test_id_generator.py                # Regex tests for deterministic ID patterns
    ├── test_db_connection.py               # Tests for DB pool, URL encoding, table checks
    ├── test_services.py                    # Tests for forecast, gap, and analytics services
    └── test_data_generator.py              # Tests for relational integrity & ground truth
```

---

## 4. Deterministic Identifier Conventions

All primary keys enforce deterministic, structured identifier patterns validated via MySQL 8.0 `CHECK (column REGEXP '...')` constraints:

| Entity | Primary Key | Format Pattern | Regex Check Constraint | Example Identifier |
|---|---|---|---|---|
| `Role` | `role_id` | `ROL-XXXX` | `^ROL-[0-9]{4}$` | `ROL-0001` |
| `Employee` | `employee_id` | `EMP-XXXXXX` | `^EMP-[0-9]{6}$` | `EMP-000001` |
| `Skill` | `skill_id` | `SKL-XXXXXX` | `^SKL-[0-9]{6}$` | `SKL-000001` |
| `EmployeeSkill` | `employee_skill_id` | `ESK-XXXXXX` | `^ESK-[0-9]{6}$` | `ESK-000001` |
| `Project` | `project_id` | `PRJ-YYYY-XXXXXX` | `^PRJ-[0-9]{4}-[0-9]{6}$` | `PRJ-2026-000001` |
| `DemandPlan` | `demand_id` | `DEM-<project-id>-YYYY'W'WW` | `^DEM-PRJ-[0-9]{4}-[0-9]{6}-[0-9]{4}W(0[1-9]\|[1-4][0-9]\|5[0-3])(-[0-9]{2})?$` | `DEM-PRJ-2026-000001-2026W01` |
| `Allocation` | `allocation_id` | `ALLOC-YYYY-XXXXXX` | `^ALLOC-[0-9]{4}-[0-9]{6}$` | `ALLOC-2026-000001` |
| `Availability` | `availability_id` | `AVL-XXXXX` | `^AVL-[0-9]{5}$` | `AVL-00001` |
| `Training` | `training_id` | `TRN-XXXXX` | `^TRN-[0-9]{5}$` | `TRN-00001` |
| `GapAnalysis` | `gap_analysis_id` | `GAP-XXXXX` | `^GAP-[0-9]{5}$` | `GAP-00001` |
| `HistoricalEvent`| `event_id` | `EVT-XXXXXXXX` | `^EVT-[0-9]{8}$` | `EVT-00000001` |

---

## 5. Capacity & Availability Business Rules

### Core Mathematical Formulations:
1. **Contracted Capacity Hours**:
   $$\text{Contracted Capacity Hours} = \text{base\_capacity\_hours} \times \text{fte}$$
   *(A full-time employee at 1.0 FTE has 40.0h; a part-time employee at 0.5 FTE has 20.0h).*
2. **Approved Leave Deductions**:
   Approved PTO, sick leave, or parental leave directly subtracts from contracted capacity before allocations are considered:
   $$\text{Net Available Bench Hours} = \max(0.00, (\text{base\_capacity\_hours} \times \text{fte}) - \text{approved\_leave\_hours} - \text{allocated\_hours})$$
3. **Availability Percentage**:
   $$\text{Availability \%} = \min\left(100.00, \max\left(0.00, \frac{\text{net\_available\_hours}}{\text{contracted\_capacity\_hours}} \times 100\right)\right)$$
4. **Availability Classifications**:
   - `ON_APPROVED_LEAVE`: When approved leave $\ge$ contracted capacity.
   - `FULLY_ALLOCATED`: When remaining net available bench hours equal 0.00.
   - `PARTIALLY_ALLOCATED`: When allocated hours $> 0$ but net available hours remain.
   - `AVAILABLE_BENCH`: When allocated hours $= 0$ and the employee is 100% available.

---

## 6. Synthetic Data Engine & Edge Cases

The synthetic data generator (`src/generators/synthetic_data_generator.py`) generates realistic enterprise workforce data deterministically using seed `20261022`.

### Supported Scales:
- **Starter Scale** (`--scale starter`): 50 employees, 30 skills, 20 projects, 15 roles.
- **Enterprise Scale** (`--scale full`): 5,000 employees, 300 skills, 500 projects, 12 months demand.

### Labeled Negative Scenarios (Ground Truth):
The generator injects 4 deliberate anomalies and logs them to `data/ground_truth.json` for evaluator benchmarking:
1. **EC-1: Allocation exceeds availability (`OVER_ALLOCATED`)**:
   Employee assigned 50.0 hours on a 40.0-hour contracted capacity (`ALLOC-2026-000049`).
2. **EC-2: Skill proficiency stale but treated current (`STALE_SKILL_ACTIVE`)**:
   Active employee rating with an evaluation date $>18$ months old (`ESK-000001`), surfacing an alert banner on the Skill Matrix dashboard.
3. **EC-3: Demand double-counted (`DEMAND_DOUBLE_COUNTED`)**:
   Duplicate demand entries for the same project, role, and schedule week (`DEM-PRJ-2026-000001-2026W01-99`).
4. **EC-4: Overlapping project allocations (`OVERLAPPING_ALLOCATION`)**:
   Employee assigned to simultaneous active client commitments creating a schedule conflict (`ALLOC-2026-000050` & `ALLOC-2026-000051`).

---

## 7. AI/ML Capability Gap & Decision Engine

The platform implements an auditable, multi-factor recommendation engine (`src/services/gap_service.py`):
- **Shortage $> 5$ FTE & Proficiency Gap $> 2$ Levels**:
  $\implies$ `HIRE_EXTERNAL` (Internal reskilling cannot bridge deficit within delivery window).
- **Shortage $> 2$ FTE & Qualified Bench Resources Available**:
  $\implies$ `REASSIGN_BENCH` (Fastest, zero-cost reallocation).
- **Shortage $\le 2$ FTE & Training Lead Time Available**:
  $\implies$ `UPSKILL_INTERNAL` (Targeted training cohort via `training` catalog).
- **Critical Priority Project Engagement**:
  $\implies$ `ENGAGE_CONTRACTOR` (Rapid contingent staffing).
- **Default Transition**:
  $\implies$ `CROSS_TRAIN` (Cross-functional lateral skills development).

---

## 8. Five Stakeholder Persona Views

The platform provides role-specific dashboards (`app/pages/5_Actor_Views.py`):
1. **👤 Employee / Candidate**: Personal competency portfolio, active project allocations, and enrolled training courses.
2. **👔 Manager**: Team size, contracted capacity, bench availability, and project commitments.
3. **🤝 HR Partner**: Strategic external hiring backlogs and internal upskilling cohorts.
4. **⚙️ IT / Operations**: System health diagnostic, live database connectivity probe, and table verification.
5. **🛡️ System Administrator**: Anomaly inspection console reviewing injected ground-truth edge cases.

---

## 9. Quickstart Guide

### Prerequisites
- Python 3.11+
- (Optional) MySQL 8.0+

### Installation & Execution

1. **Clone the repository**:
   ```bash
   git clone https://github.com/AkhileshwarMittapelly/workforce-intelligence-platform.git
   cd workforce-intelligence-platform
   ```

2. **Launch the Streamlit Platform**:
   ```bash
   python run.py
   ```
   *(Automatically verifies seed data and opens `http://localhost:8501`)*

3. **Regenerate Synthetic Data**:
   ```bash
   # Starter dataset (fast demo)
   python run.py --datagen --scale starter

   # Full enterprise volume (5,000 employees, 300 skills, 500 projects)
   python run.py --datagen --scale full
   ```

4. **Run the Full Test Suite**:
   ```bash
   python run.py --test
   ```

5. **(Optional) Apply Schema to MySQL**:
   ```bash
   python database/apply_schema.py
   ```

---

## 10. Automated Test Suite (38/38 Passed)

```bash
python -m pytest tests/ -v
```

```text
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\CandidateWorkspace\workforce-intelligence-platform

tests/test_capacity_service.py ......                                    [ 15%]
tests/test_data_generator.py ....                                        [ 26%]
tests/test_db_connection.py .......                                      [ 44%]
tests/test_id_generator.py ................                              [ 86%]
tests/test_services.py .....                                             [100%]

============================== 38 passed in 3.52s ==============================
```

- **Capacity & Availability Logic**: 6 tests verifying FTE scaling, approved leave, and bench math.
- **Deterministic Identifier Generator**: 16 tests verifying regex patterns for all 10 entities.
- **Database Connection & Fallback**: 7 tests verifying URL encoding, pooling, and graceful error handling.
- **Data Generator & Integrity**: 4 tests verifying foreign keys, 4 edge cases, and arithmetic consistency.
- **Forecasting & Analytics Services**: 5 tests verifying risk scoring, gap diagnostics, and executive KPIs.

---

## 11. Lawful Data Provenance

All data utilized within the platform is **100% synthetically generated** using deterministic seeds and Python's `Faker` and `NumPy` libraries. No proprietary, personal, confidential, or copyrighted third-party data was accessed, collected, or stored. Complete provenance is recorded in `data/manifest.json`.
