# Workforce Intelligence Platform - Database Data Dictionary

Target RDBMS: **MySQL 8.0+** | Storage Engine: **InnoDB** | Character Set: **utf8mb4** | Collation: **utf8mb4_0900_ai_ci**

---

## 1. Overview & Architectural Principles

The database follows Third Normal Form (3NF/BCNF) and implements enterprise workforce intelligence standards:

1. **Deterministic Primary Keys**: Enforced via MySQL 8.0 regular expression `CHECK` constraints to ensure predictable, structured identifiers across all environments.
2. **Effective Dating & Historical Tracking (SCD Type 2)**: Every core entity incorporates `effective_from`, `effective_to`, and `is_current` boolean flags. A record where `effective_to IS NULL` represents the current active state.
3. **Immutable Event Audit Trail**: The `historical_event_log` table captures state mutations across all entities with JSON diffs (`old_state`, `new_state`) and event timestamps.
4. **Intra-Row vs. Cross-Table Capacity Calculation**:
   - In adherence to MySQL 8.0 constraints (which prohibit generated columns referencing other tables), all generated columns operate strictly on intra-row values.
   - Dynamic cross-table capacity, headcount rollups, and utilization metrics are modeled through high-performance SQL analytical views and application service modules.

---

## 2. Deterministic Identifier Conventions

| Entity | Primary Key | Format Pattern | Regex Check Constraint | Sample Identifier |
|---|---|---|---|---|
| `role` | `role_id` | `ROL-XXXX` | `^ROL-[0-9]{4}$` | `ROL-0001` |
| `employee` | `employee_id` | `EMP-XXXXXX` | `^EMP-[0-9]{6}$` | `EMP-000001` |
| `skill` | `skill_id` | `SKL-XXXXXX` | `^SKL-[0-9]{6}$` | `SKL-000001` |
| `employee_skill` | `employee_skill_id` | `ESK-XXXXXX` | `^ESK-[0-9]{6}$` | `ESK-000001` |
| `project` | `project_id` | `PRJ-YYYY-XXXXXX` | `^PRJ-[0-9]{4}-[0-9]{6}$` | `PRJ-2026-000001` |
| `demand_plan` | `demand_id` | `DEM-<project-id>-YYYY'W'WW` | `^DEM-PRJ-[0-9]{4}-[0-9]{6}-[0-9]{4}W(0[1-9]\|[1-4][0-9]\|5[0-3])(-[0-9]{2})?$` | `DEM-PRJ-2026-000001-2026W01` |
| `allocation` | `allocation_id` | `ALLOC-YYYY-XXXXXX` | `^ALLOC-[0-9]{4}-[0-9]{6}$` | `ALLOC-2026-000001` |
| `availability` | `availability_id` | `AVL-XXXXX` | `^AVL-[0-9]{5}$` | `AVL-00001` |
| `training` | `training_id` | `TRN-XXXXX` | `^TRN-[0-9]{5}$` | `TRN-00001` |
| `gap_analysis` | `gap_analysis_id` | `GAP-XXXXX` | `^GAP-[0-9]{5}$` | `GAP-00001` |
| `historical_event_log` | `event_id` | `EVT-XXXXXXXX` | `^EVT-[0-9]{8}$` | `EVT-00000001` |

---

## 3. Capacity & Availability Business Rules

Capacity is governed by contracted FTE, approved leave, and project allocations:

1. **Contracted Capacity Hours**:
   $$\text{Contracted Capacity Hours} = \text{ROUND}(\text{base\_capacity\_hours} \times \text{fte}, 2)$$
   - Full-time employee (1.0 FTE, 40h base) = 40.00 contracted hours.
   - Part-time employee (0.5 FTE, 40h base) = 20.00 contracted hours.
2. **Approved Leave Impact**:
   - Approved PTO, sick leave, or parental leave directly subtracts from contracted capacity before allocations are considered.
3. **Net Available Bench Hours**:
   $$\text{Net Available Hours} = \max(0.00, \text{ROUND}((\text{base\_capacity\_hours} \times \text{fte}) - \text{approved\_leave\_hours} - \text{allocated\_hours}, 2))$$
4. **Availability Percentage**:
   $$\text{Availability \%} = \min\left(100.00, \max\left(0.00, \text{ROUND}\left(\frac{\text{net\_available\_hours}}{\text{contracted\_capacity\_hours}} \times 100, 2\right)\right)\right)$$
5. **Availability Classification Hierarchy**:
   - `ON_APPROVED_LEAVE`: When approved leave equals or exceeds contracted capacity.
   - `FULLY_ALLOCATED`: When remaining net available hours reach 0.00.
   - `PARTIALLY_ALLOCATED`: When allocated hours > 0 but net available hours > 0.
   - `AVAILABLE_BENCH`: When allocated hours = 0 and employee is 100% available.

---

## 4. Entity Data Dictionaries

### 4.1 Table: `role`
Master catalog of standardized organizational job titles, seniority tiers, and baseline billing rates.

| Column Name | Data Type | Nullable | Default | Keys / Constraints | Description |
|---|---|---|---|---|---|
| `role_id` | `VARCHAR(16)` | No | None | **PK**, `REGEXP '^ROL-[0-9]{4}$'` | Deterministic role identifier. |
| `role_code` | `VARCHAR(30)` | No | None | **UNIQUE** (`uq_role_code`) | Human-readable natural code (e.g., `SWE-SR-01`). |
| `role_name` | `VARCHAR(100)` | No | None | None | Official job title. |
| `department` | `VARCHAR(100)` | No | None | Index (`idx_role_department`) | Department or practice group. |
| `job_level` | `VARCHAR(20)` | No | None | None | Seniority tier (e.g. ENTRY, MID, SENIOR, LEAD, PRINCIPAL). |
| `standard_hourly_cost` | `DECIMAL(10,2)`| No | `0.00` | `CHECK (standard_hourly_cost >= 0.00)` | Baseline internal cost rate per hour. |
| `description` | `TEXT` | Yes | `NULL` | None | Detailed role responsibilities. |
| `status` | `ENUM` | No | `'ACTIVE'` | `'DRAFT','ACTIVE','INACTIVE','ARCHIVED'` | Lifecycle status. |
| `effective_from` | `DATE` | No | None | Index (`idx_role_status_dates`) | Start date of role validity. |
| `effective_to` | `DATE` | Yes | `NULL` | `CHECK (effective_to IS NULL OR effective_to >= effective_from)` | End date of role validity (`NULL` = active). |
| `is_current` | `BOOLEAN` | No | `TRUE` | Index (`idx_role_status_dates`) | Fast-path flag for current version. |
| `created_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | None | Record creation timestamp. |
| `updated_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP ON UPDATE` | None | Last modification timestamp. |

---

### 4.2 Table: `employee`
Master profile of all internal and contingent workforce members.

| Column Name | Data Type | Nullable | Default | Keys / Constraints | Description |
|---|---|---|---|---|---|
| `employee_id` | `VARCHAR(20)` | No | None | **PK**, `REGEXP '^EMP-[0-9]{6}$'` | Deterministic employee identifier. |
| `first_name` | `VARCHAR(50)` | No | None | None | Given name. |
| `last_name` | `VARCHAR(50)` | No | None | None | Family name. |
| `email` | `VARCHAR(100)` | No | None | **UNIQUE**, `LIKE '%_@__%.__%'` | Corporate email address. |
| `phone` | `VARCHAR(25)` | Yes | `NULL` | None | Primary contact telephone. |
| `current_role_id` | `VARCHAR(16)` | No | None | **FK** ➔ `role(role_id)` (`RESTRICT`) | Foreign key to assigned job role. |
| `department` | `VARCHAR(100)` | No | None | Index (`idx_emp_department`) | Primary organizational unit. |
| `manager_id` | `VARCHAR(20)` | Yes | `NULL` | **FK** ➔ `employee(employee_id)` (`SET NULL`) | Self-referencing reporting manager. |
| `employment_type` | `ENUM` | No | `'FULL_TIME'` | `'FULL_TIME','PART_TIME','CONTRACTOR','INTERN'` | Contract arrangement. |
| `fte` | `DECIMAL(3,2)` | No | `1.00` | `CHECK (fte > 0.00 AND fte <= 1.00)` | Contracted Full-Time Equivalent capacity. |
| `work_location` | `VARCHAR(100)` | No | `'Remote'` | None | Office or remote location. |
| `hire_date` | `DATE` | No | None | None | Official date of joining. |
| `termination_date`| `DATE` | Yes | `NULL` | `CHECK (termination_date IS NULL OR termination_date >= hire_date)` | Exit date if departed. |
| `cost_rate_per_hour` | `DECIMAL(10,2)`| No | `0.00` | `CHECK (cost_rate_per_hour >= 0.00)` | Internal fully burdened hourly cost. |
| `standard_hours_per_week` | `DECIMAL(4,2)`| No | `40.00` | `CHECK (> 0.00 AND <= 80.00)` | Standard weekly hours expectation. |
| `status` | `ENUM` | No | `'ACTIVE'` | `'ONBOARDING','ACTIVE','ON_LEAVE','NOTICE_PERIOD','TERMINATED'` | Employment lifecycle status. |
| `effective_from` | `DATE` | No | None | Index (`idx_emp_effective_dates`) | Start date of profile version. |
| `effective_to` | `DATE` | Yes | `NULL` | `CHECK (effective_to IS NULL OR effective_to >= effective_from)` | End date of profile version. |
| `is_current` | `BOOLEAN` | No | `TRUE` | Index (`idx_emp_status_current`) | Version active indicator. |
| `created_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | None | Audit timestamp. |
| `updated_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP ON UPDATE` | None | Audit timestamp. |

---

### 4.3 Table: `skill`
Standardized competency and skill taxonomy catalog.

| Column Name | Data Type | Nullable | Default | Keys / Constraints | Description |
|---|---|---|---|---|---|
| `skill_id` | `VARCHAR(20)` | No | None | **PK**, `REGEXP '^SKL-[0-9]{6}$'` | Deterministic skill identifier. |
| `skill_code` | `VARCHAR(50)` | No | None | **UNIQUE** (`uq_skill_code`) | Unique natural skill tag (e.g., `SKL-PY-CORE`). |
| `skill_name` | `VARCHAR(100)` | No | None | None | Official display name of skill. |
| `category` | `ENUM` | No | None | Index (`idx_skill_category`) | Category: `PROGRAMMING_LANGUAGE`, `FRAMEWORK`, `DATABASE`, `CLOUD_DEVOPS`, `DATA_AI`, `DOMAIN_BUSINESS`, `SOFT_SKILL`, `CYBERSECURITY`. |
| `description` | `TEXT` | Yes | `NULL` | None | Scope and definition of skill. |
| `status` | `ENUM` | No | `'ACTIVE'` | `'ACTIVE','DEPRECATED','PROPOSED'` | Skill catalog lifecycle status. |
| `effective_from` | `DATE` | No | None | None | Date skill was adopted. |
| `effective_to` | `DATE` | Yes | `NULL` | `CHECK (effective_to IS NULL OR effective_to >= effective_from)` | Date skill was deprecated. |
| `is_current` | `BOOLEAN` | No | `TRUE` | Index (`idx_skill_status`) | Current validity flag. |
| `created_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | None | Audit timestamp. |
| `updated_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP ON UPDATE` | None | Audit timestamp. |

---

### 4.4 Table: `employee_skill`
Associative entity mapping employees to skills with verified proficiency ratings and experience.

| Column Name | Data Type | Nullable | Default | Keys / Constraints | Description |
|---|---|---|---|---|---|
| `employee_skill_id` | `VARCHAR(20)` | No | None | **PK**, `REGEXP '^ESK-[0-9]{6}$'` | Deterministic mapping identifier. |
| `employee_id` | `VARCHAR(20)` | No | None | **FK** ➔ `employee(employee_id)` (`RESTRICT`) | Foreign key to employee. |
| `skill_id` | `VARCHAR(20)` | No | None | **FK** ➔ `skill(skill_id)` (`RESTRICT`) | Foreign key to skill. |
| `proficiency_level` | `TINYINT` | No | None | `CHECK (BETWEEN 1 AND 5)` | 1=Beginner, 2=Intermediate, 3=Proficient, 4=Advanced, 5=Expert/Master. |
| `years_of_experience` | `DECIMAL(4,1)`| No | `0.0` | `CHECK (years_of_experience >= 0.0)` | Tracked years using the skill. |
| `verification_status` | `ENUM` | No | `'SELF_REPORTED'`| `'SELF_REPORTED','PEER_REVIEWED','MANAGER_VERIFIED','ASSESSMENT_PASSED','CERTIFIED'` | Competency verification state. |
| `last_evaluated_date` | `DATE` | Yes | `NULL` | None | Date of latest review or assessment. |
| `status` | `ENUM` | No | `'ACTIVE'` | `'ACTIVE','INACTIVE','EXPIRED'` | Portfolio skill status. |
| `effective_from` | `DATE` | No | None | Composite **UNIQUE** (`employee_id, skill_id, effective_from`) | Start of this proficiency tier. |
| `effective_to` | `DATE` | Yes | `NULL` | `CHECK (effective_to IS NULL OR effective_to >= effective_from)` | End of this proficiency tier. |
| `is_current` | `BOOLEAN` | No | `TRUE` | Index (`idx_es_emp_current`) | Current active rating flag. |
| `created_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | None | Audit timestamp. |
| `updated_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP ON UPDATE` | None | Audit timestamp. |

---

### 4.5 Table: `project`
Client engagements and internal initiatives requiring resource staffing.

| Column Name | Data Type | Nullable | Default | Keys / Constraints | Description |
|---|---|---|---|---|---|
| `project_id` | `VARCHAR(30)` | No | None | **PK**, `REGEXP '^PRJ-[0-9]{4}-[0-9]{6}$'` | Deterministic project identifier (`PRJ-2026-000001`). |
| `project_code` | `VARCHAR(30)` | No | None | **UNIQUE** (`uq_project_code`) | Natural project code (e.g., `PRJ-ALPHA-26`). |
| `project_name` | `VARCHAR(150)` | No | None | None | Display title of engagement. |
| `client_name` | `VARCHAR(100)` | Yes | `NULL` | None | External client organization. |
| `business_unit` | `VARCHAR(100)` | No | None | Index (`idx_prj_business_unit`) | Sponsoring business unit. |
| `project_manager_id` | `VARCHAR(20)` | Yes | `NULL` | **FK** ➔ `employee(employee_id)` (`SET NULL`) | Employee leading the project. |
| `start_date` | `DATE` | No | None | Index (`idx_prj_dates`) | Official project start date. |
| `end_date` | `DATE` | Yes | `NULL` | `CHECK (end_date IS NULL OR end_date >= start_date)` | Planned project finish date. |
| `planned_budget` | `DECIMAL(14,2)`| No | `0.00` | `CHECK (planned_budget >= 0.00)` | Approved financial budget. |
| `priority` | `ENUM` | No | `'MEDIUM'` | `'LOW','MEDIUM','HIGH','CRITICAL'` | Organizational priority ranking. |
| `status` | `ENUM` | No | `'PROPOSED'`| `'PIPELINE','PROPOSED','ACTIVE','ON_HOLD','COMPLETED','CANCELLED'` | Project lifecycle status. |
| `effective_from` | `DATE` | No | None | None | Record effective date. |
| `effective_to` | `DATE` | Yes | `NULL` | `CHECK (effective_to IS NULL OR effective_to >= effective_from)` | Record expiry date. |
| `is_current` | `BOOLEAN` | No | `TRUE` | None | Current version flag. |
| `created_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | None | Audit timestamp. |
| `updated_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP ON UPDATE` | None | Audit timestamp. |

---

### 4.6 Table: `demand_plan`
Forward-looking staffing demand requirements by role, skill, and FTE schedule.

| Column Name | Data Type | Nullable | Default | Keys / Constraints | Description |
|---|---|---|---|---|---|
| `demand_id` | `VARCHAR(60)` | No | None | **PK**, `REGEXP '^DEM-PRJ-[0-9]{4}-[0-9]{6}-[0-9]{4}W[0-9]{2}(-[0-9]{2})?$'` | Deterministic demand identifier (`DEM-PRJ-2026-000001-2026W01`). |
| `project_id` | `VARCHAR(30)` | No | None | **FK** ➔ `project(project_id)` (`RESTRICT`) | Project generating the labor demand. |
| `role_id` | `VARCHAR(16)` | No | None | **FK** ➔ `role(role_id)` (`RESTRICT`) | Requested organizational job role. |
| `required_skill_id` | `VARCHAR(20)` | No | None | **FK** ➔ `skill(skill_id)` (`RESTRICT`) | Primary required technical/domain competency. |
| `min_proficiency_level` | `TINYINT` | No | `3` | `CHECK (BETWEEN 1 AND 5)` | Minimum acceptable skill proficiency rating. |
| `headcount_required` | `INT` | No | `1` | `CHECK (headcount_required > 0)` | Quantity of individuals requested. |
| `required_fte` | `DECIMAL(5,2)` | No | `1.00` | `CHECK (required_fte > 0.00)` | Full-Time Equivalent demand volume. |
| `start_date` | `DATE` | No | None | Index (`idx_dp_dates`) | Required start date of staffing. |
| `end_date` | `DATE` | No | None | `CHECK (end_date >= start_date)` | Release date of requested resource. |
| `priority` | `ENUM` | No | `'MEDIUM'` | `'LOW','MEDIUM','HIGH','CRITICAL'` | Staffing urgency. |
| `fulfillment_status` | `ENUM` | No | `'UNFULFILLED'` | `'UNFULFILLED','PARTIALLY_FULFILLED','FULFILLED','CANCELLED'` | Staffing allocation fulfillment progress. |
| `status` | `ENUM` | No | `'DRAFT'` | `'DRAFT','SUBMITTED','APPROVED','ACTIVE','CLOSED','SUPERSEDED'` | Governance lifecycle status. |
| `effective_from` | `DATE` | No | None | None | Record effective date. |
| `effective_to` | `DATE` | Yes | `NULL` | `CHECK (effective_to IS NULL OR effective_to >= effective_from)` | Record expiry date. |
| `is_current` | `BOOLEAN` | No | `TRUE` | Index (`idx_dp_fulfillment`) | Active demand flag. |
| `created_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | None | Audit timestamp. |
| `updated_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP ON UPDATE` | None | Audit timestamp. |

---

### 4.7 Table: `allocation`
Operational assignment linking an employee to a project and demand plan with dedicated FTE commitment.

| Column Name | Data Type | Nullable | Default | Keys / Constraints | Description |
|---|---|---|---|---|---|
| `allocation_id` | `VARCHAR(30)` | No | None | **PK**, `REGEXP '^ALLOC-[0-9]{4}-[0-9]{6}$'` | Deterministic allocation identifier (`ALLOC-2026-000001`). |
| `employee_id` | `VARCHAR(20)` | No | None | **FK** ➔ `employee(employee_id)` (`RESTRICT`) | Assigned employee. |
| `project_id` | `VARCHAR(30)` | No | None | **FK** ➔ `project(project_id)` (`RESTRICT`) | Target project. |
| `demand_id` | `VARCHAR(60)` | Yes | `NULL` | **FK** ➔ `demand_plan(demand_id)` (`SET NULL`) | Origin demand requirement. |
| `allocation_percentage` | `DECIMAL(5,2)` | No | `100.00` | `CHECK (> 0.00 AND <= 100.00)` | Commitment percentage (e.g. 50.00 = 50%). |
| `billing_rate_per_hour` | `DECIMAL(10,2)`| No | `0.00` | `CHECK (billing_rate_per_hour >= 0.00)` | Client billable rate per hour. |
| `is_billable` | `BOOLEAN` | No | `TRUE` | None | True if revenue-generating. |
| `start_date` | `DATE` | No | None | Index (`idx_alc_emp_dates`) | Commitment start date. |
| `end_date` | `DATE` | No | None | `CHECK (end_date >= start_date)` | Commitment end date. |
| `allocation_status` | `ENUM` | No | `'REQUESTED'` | `'REQUESTED','CONFIRMED','ACTIVE','COMPLETED','RELEASED','CANCELLED'` | Operational workflow status. |
| `status` | `ENUM` | No | `'COMMITTED'` | `'PLANNED','COMMITTED','TERMINATED_EARLY','ARCHIVED'` | Lifecycle status. |
| `effective_from` | `DATE` | No | None | None | Record validity start. |
| `effective_to` | `DATE` | Yes | `NULL` | `CHECK (effective_to IS NULL OR effective_to >= effective_from)` | Record validity end. |
| `is_current` | `BOOLEAN` | No | `TRUE` | Index (`idx_alc_status`) | Current active allocation. |
| `created_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | None | Audit timestamp. |
| `updated_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP ON UPDATE` | None | Audit timestamp. |

---

### 4.8 Table: `availability`
Tracks employee periodic capacity, FTE factor, approved leave deductions, and net bench availability.

| Column Name | Data Type | Nullable | Default | Keys / Constraints | Description |
|---|---|---|---|---|---|
| `availability_id` | `VARCHAR(20)` | No | None | **PK**, `REGEXP '^AVL-[0-9]{5}$'` | Deterministic availability identifier. |
| `employee_id` | `VARCHAR(20)` | No | None | **FK** ➔ `employee(employee_id)` (`RESTRICT`) | Target employee. |
| `start_date` | `DATE` | No | None | Index (`idx_avl_emp_period`) | Period window start (e.g. Monday). |
| `end_date` | `DATE` | No | None | `CHECK (end_date >= start_date)` | Period window end (e.g. Sunday). |
| `fte` | `DECIMAL(3,2)` | No | `1.00` | `CHECK (fte > 0.00 AND fte <= 1.00)` | Contracted FTE multiplier for period. |
| `base_capacity_hours` | `DECIMAL(5,2)` | No | `40.00` | `CHECK (base_capacity_hours >= 0.00)` | Baseline full-time hours for the period. |
| `contracted_capacity_hours` | `DECIMAL(5,2)` | No | None | **STORED GENERATED** `(ROUND(base_capacity_hours * fte, 2))` | Effective capacity = base * FTE. |
| `approved_leave_hours` | `DECIMAL(5,2)` | No | `0.00` | `CHECK (approved_leave_hours >= 0.00)` | Approved PTO / leave deducted. |
| `allocated_hours` | `DECIMAL(5,2)` | No | `0.00` | `CHECK (allocated_hours >= 0.00)` | Project commitments (updated via service/ETL). |
| `net_available_hours` | `DECIMAL(5,2)` | No | None | **STORED GENERATED** `(GREATEST(0.00, ROUND((base_capacity_hours * fte) - approved_leave_hours - allocated_hours, 2)))` | Remaining bench hours. |
| `availability_percentage` | `DECIMAL(5,2)` | No | None | **STORED GENERATED** `(net_available_hours / contracted_capacity_hours * 100)` | Bench availability percentage. |
| `availability_type` | `ENUM` | No | `'AVAILABLE_BENCH'` | `'AVAILABLE_BENCH','PARTIALLY_ALLOCATED','FULLY_ALLOCATED','ON_APPROVED_LEAVE','TRAINING','SABBATICAL'` | Capacity state classification. |
| `status` | `ENUM` | No | `'PROJECTED'` | `'PROJECTED','CONFIRMED','OVERRIDDEN','HISTORICAL'` | Forecast vs confirmed state. |
| `notes` | `VARCHAR(255)` | Yes | `NULL` | None | Schedule notes / comments. |
| `effective_from` | `DATE` | No | None | None | Period effective date. |
| `effective_to` | `DATE` | Yes | `NULL` | `CHECK (effective_to IS NULL OR effective_to >= effective_from)` | Period expiry date. |
| `is_current` | `BOOLEAN` | No | `TRUE` | Index (`idx_avl_type_status`) | Active schedule flag. |
| `created_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | None | Audit timestamp. |
| `updated_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP ON UPDATE` | None | Audit timestamp. |

---

### 4.9 Table: `training`
Employee upskilling programs, certifications, and courses for skill gap closure.

| Column Name | Data Type | Nullable | Default | Keys / Constraints | Description |
|---|---|---|---|---|---|
| `training_id` | `VARCHAR(20)` | No | None | **PK**, `REGEXP '^TRN-[0-9]{5}$'` | Deterministic training identifier. |
| `employee_id` | `VARCHAR(20)` | No | None | **FK** ➔ `employee(employee_id)` (`RESTRICT`) | Enrolled employee. |
| `skill_id` | `VARCHAR(20)` | No | None | **FK** ➔ `skill(skill_id)` (`RESTRICT`) | Target skill being acquired/improved. |
| `training_title` | `VARCHAR(150)` | No | None | None | Course or certification title. |
| `provider` | `VARCHAR(100)` | No | None | None | Training vendor or institution. |
| `training_type` | `ENUM` | No | None | `'COURSE','BOOTCAMP','CERTIFICATION','INTERNAL_WORKSHOP','MENTORSHIP','SELF_PACED'` | Pedagogical format. |
| `target_proficiency_level` | `TINYINT` | No | None | `CHECK (BETWEEN 1 AND 5)` | Target level upon completion. |
| `start_date` | `DATE` | No | None | Index (`idx_trn_dates`) | Training start date. |
| `expected_completion_date`| `DATE` | No | None | `CHECK (expected_completion_date >= start_date)` | Planned completion target. |
| `actual_completion_date` | `DATE` | Yes | `NULL` | `CHECK (actual_completion_date IS NULL OR actual_completion_date >= start_date)` | Verified completion date. |
| `cost` | `DECIMAL(10,2)`| No | `0.00` | `CHECK (cost >= 0.00)` | Direct course/exam cost. |
| `hours_dedicated` | `DECIMAL(5,2)` | No | `0.00` | None | Total learning hours spent. |
| `score` | `DECIMAL(5,2)` | Yes | `NULL` | `CHECK (score IS NULL OR (score >= 0.00 AND score <= 100.00))` | Exam score percentage. |
| `certification_url` | `VARCHAR(255)` | Yes | `NULL` | None | Credential verification hyperlink. |
| `lifecycle_status` | `ENUM` | No | `'NOMINATED'` | `'NOMINATED','APPROVED','ENROLLED','IN_PROGRESS','COMPLETED','FAILED','DROPPED'` | Learner progress status. |
| `status` | `ENUM` | No | `'ACTIVE'` | `'ACTIVE','SUPERSEDED','CANCELLED','ARCHIVED'` | Administrative record status. |
| `effective_from` | `DATE` | No | None | None | Validity start date. |
| `effective_to` | `DATE` | Yes | `NULL` | `CHECK (effective_to IS NULL OR effective_to >= effective_from)` | Validity end date. |
| `is_current` | `BOOLEAN` | No | `TRUE` | Index (`idx_trn_lifecycle`) | Active training flag. |
| `created_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | None | Audit timestamp. |
| `updated_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP ON UPDATE` | None | Audit timestamp. |

---

### 4.10 Table: `gap_analysis`
Workforce capability and headcount deficit diagnostics comparing supply and demand.

| Column Name | Data Type | Nullable | Default | Keys / Constraints | Description |
|---|---|---|---|---|---|
| `gap_analysis_id` | `VARCHAR(20)` | No | None | **PK**, `REGEXP '^GAP-[0-9]{5}$'` | Deterministic gap identifier. |
| `analysis_code` | `VARCHAR(50)` | No | None | **UNIQUE** (`uq_gap_analysis_code`) | Natural identifier (e.g., `GAP-2026-Q1-01`). |
| `demand_id` | `VARCHAR(60)` | Yes | `NULL` | **FK** ➔ `demand_plan(demand_id)` (`SET NULL`) | Source demand requirement. |
| `project_id` | `VARCHAR(30)` | Yes | `NULL` | **FK** ➔ `project(project_id)` (`SET NULL`) | Associated project. |
| `role_id` | `VARCHAR(16)` | Yes | `NULL` | **FK** ➔ `role(role_id)` (`SET NULL`) | Associated job role. |
| `skill_id` | `VARCHAR(20)` | No | None | **FK** ➔ `skill(skill_id)` (`RESTRICT`) | Target skill analyzed. |
| `analysis_date` | `DATE` | No | None | Index (`idx_gap_dates`) | Date diagnosis was conducted. |
| `period_start_date` | `DATE` | No | None | None | Target evaluation window start. |
| `period_end_date` | `DATE` | No | None | `CHECK (period_end_date >= period_start_date)` | Target evaluation window end. |
| `required_headcount` | `INT` | No | `1` | `CHECK (required_headcount >= 0)` | Labor required by projects. |
| `available_headcount`| `INT` | No | `0` | `CHECK (available_headcount >= 0)` | Active internal labor available. |
| `shortage_headcount` | `INT` | No | None | **STORED GENERATED** `(GREATEST(0, required_headcount - available_headcount))` | Net deficit headcount. |
| `required_proficiency_level` | `TINYINT` | No | `3` | `CHECK (BETWEEN 1 AND 5)` | Benchmark proficiency level. |
| `avg_current_proficiency_level`| `DECIMAL(3,2)`| Yes | `NULL` | `CHECK (IS NULL OR (>= 0.00 AND <= 5.00))` | Current workforce average skill level. |
| `gap_severity` | `ENUM` | No | `'MEDIUM'` | `'NONE','LOW','MEDIUM','HIGH','CRITICAL'` | Risk classification. |
| `recommended_action` | `ENUM` | No | `'UPSKILL_INTERNAL'` | `'HIRE_EXTERNAL','UPSKILL_INTERNAL','REASSIGN_BENCH','ENGAGE_CONTRACTOR','CROSS_TRAIN','NO_ACTION'` | Strategic remediation path. |
| `status` | `ENUM` | No | `'OPEN'` | `'OPEN','IN_REVIEW','ACTION_PLANNED','MITIGATED','CLOSED'` | Remediation progress status. |
| `notes` | `TEXT` | Yes | `NULL` | None | Qualitative rationale. |
| `effective_from` | `DATE` | No | None | None | Diagnosis effective date. |
| `effective_to` | `DATE` | Yes | `NULL` | `CHECK (effective_to IS NULL OR effective_to >= effective_from)` | Diagnosis resolution date. |
| `is_current` | `BOOLEAN` | No | `TRUE` | Index (`idx_gap_severity_status`) | Active gap flag. |
| `created_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | None | Audit timestamp. |
| `updated_at` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP ON UPDATE` | None | Audit timestamp. |

---

### 4.11 Table: `historical_event_log`
Immutable event audit log supporting event-sourcing and complete state reconstruction.

| Column Name | Data Type | Nullable | Default | Keys / Constraints | Description |
|---|---|---|---|---|---|
| `event_id` | `VARCHAR(24)` | No | None | **PK**, `REGEXP '^EVT-[0-9]{8}$'` | Deterministic event identifier (`EVT-00000001`). |
| `entity_type` | `ENUM` | No | None | Index (`idx_evt_entity`) | `'EMPLOYEE','ROLE','SKILL','EMPLOYEE_SKILL','PROJECT','DEMAND_PLAN','ALLOCATION','AVAILABILITY','TRAINING','GAP_ANALYSIS'`. |
| `entity_id` | `VARCHAR(60)` | No | None | Index (`idx_evt_entity`) | Primary key of modified entity. |
| `event_type` | `ENUM` | No | None | Index (`idx_evt_type`) | `'CREATED','STATUS_CHANGE','ALLOCATED','DEALLOCATED','SKILL_UPGRADE','CAPACITY_CHANGE','DEMAND_CHANGE','GAP_IDENTIFIED','TRAINING_ENROLLED','TRAINING_COMPLETED','RECORD_SUPERSEDED'`. |
| `old_state` | `JSON` | Yes | `NULL` | None | Snapshot of row before change. |
| `new_state` | `JSON` | Yes | `NULL` | None | Snapshot of row after change. |
| `reason` | `VARCHAR(255)` | Yes | `NULL` | None | Business reason for change. |
| `performed_by` | `VARCHAR(100)` | No | `'SYSTEM'` | None | User or service triggering event. |
| `event_timestamp` | `TIMESTAMP` | No | `CURRENT_TIMESTAMP` | Index (`idx_evt_timestamp`) | Immutable wall-clock event time. |

---

## 5. SQL Analytical Views for Streamlit

To avoid prohibited cross-table MySQL generated columns, the following analytical views compute live cross-table values:

1. **`vw_active_workforce`**: Joins `employee` with `role` to display active staffing, reporting managers, and contracted weekly hours (`standard_hours_per_week * fte`).
2. **`vw_employee_skill_inventory`**: Matrices active employee competencies, descriptive proficiency labels, and verification ratings.
3. **`vw_project_allocation_summary`**: Summarizes project assignments, billing rates, and demand fulfillment commitments.
4. **`vw_workforce_capacity_analysis`**: Dynamically computes live employee capacity, combining base hours, FTE factors, approved leave hours, and project allocation hours.
5. **`vw_actionable_gaps`**: Ranks open skill and headcount deficits by critical severity for workforce planning dashboards.
