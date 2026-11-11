-- ==============================================================================
-- Workforce Intelligence Platform - Normalized Database Schema
-- Target RDBMS: MySQL 8.0+
-- Storage Engine: InnoDB
-- Character Set: utf8mb4 / utf8mb4_0900_ai_ci
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS workforce_intelligence
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE workforce_intelligence;

-- Disable foreign key checks during schema re-creation if executed as script
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS historical_event_log;
DROP TABLE IF EXISTS gap_analysis;
DROP TABLE IF EXISTS training;
DROP TABLE IF EXISTS availability;
DROP TABLE IF EXISTS allocation;
DROP TABLE IF EXISTS demand_plan;
DROP TABLE IF EXISTS project;
DROP TABLE IF EXISTS employee_skill;
DROP TABLE IF EXISTS skill;
DROP TABLE IF EXISTS employee;
DROP TABLE IF EXISTS role;

SET FOREIGN_KEY_CHECKS = 1;

-- ==============================================================================
-- 1. TABLE: role
-- Represents standard organizational roles, job titles, and tier levels.
-- Deterministic ID Format: ROL-XXXX (e.g., ROL-0001, ROL-0105)
-- ==============================================================================
CREATE TABLE role (
    role_id                  VARCHAR(16)   NOT NULL,
    role_code                VARCHAR(30)   NOT NULL,
    role_name                VARCHAR(100)  NOT NULL,
    department               VARCHAR(100)  NOT NULL,
    job_level                VARCHAR(20)   NOT NULL COMMENT 'ENTRY, JUNIOR, MID, SENIOR, LEAD, PRINCIPAL, DIRECTOR',
    standard_hourly_cost     DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    description              TEXT          NULL,
    status                   ENUM('DRAFT', 'ACTIVE', 'INACTIVE', 'ARCHIVED') NOT NULL DEFAULT 'ACTIVE',
    effective_from           DATE          NOT NULL,
    effective_to             DATE          NULL,
    is_current               BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT pk_role PRIMARY KEY (role_id),
    CONSTRAINT uq_role_code UNIQUE (role_code),
    CONSTRAINT chk_role_id_format CHECK (role_id REGEXP '^ROL-[0-9]{4}$'),
    CONSTRAINT chk_role_hourly_cost CHECK (standard_hourly_cost >= 0.00),
    CONSTRAINT chk_role_effective_dates CHECK (effective_to IS NULL OR effective_to >= effective_from)
) ENGINE=InnoDB COMMENT='Master catalog of organizational job roles and levels';

-- Indexes for role
CREATE INDEX idx_role_department ON role(department);
CREATE INDEX idx_role_status_dates ON role(status, is_current, effective_from, effective_to);


-- ==============================================================================
-- 2. TABLE: employee
-- Represents workforce members, employment contracts, and reporting hierarchy.
-- Deterministic ID Format: EMP-XXXXXX (6 digits, e.g., EMP-000001, EMP-000125)
-- ==============================================================================
CREATE TABLE employee (
    employee_id              VARCHAR(20)   NOT NULL,
    first_name               VARCHAR(50)   NOT NULL,
    last_name                VARCHAR(50)   NOT NULL,
    email                    VARCHAR(100)  NOT NULL,
    phone                    VARCHAR(25)   NULL,
    current_role_id          VARCHAR(16)   NOT NULL,
    department               VARCHAR(100)  NOT NULL,
    manager_id               VARCHAR(20)   NULL,
    employment_type          ENUM('FULL_TIME', 'PART_TIME', 'CONTRACTOR', 'INTERN') NOT NULL DEFAULT 'FULL_TIME',
    fte                      DECIMAL(3,2)  NOT NULL DEFAULT 1.00 COMMENT 'Contracted Full-Time Equivalent (0.10 to 1.00)',
    work_location            VARCHAR(100)  NOT NULL DEFAULT 'Remote',
    hire_date                DATE          NOT NULL,
    termination_date         DATE          NULL,
    cost_rate_per_hour       DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    standard_hours_per_week  DECIMAL(4,2)  NOT NULL DEFAULT 40.00,
    status                   ENUM('ONBOARDING', 'ACTIVE', 'ON_LEAVE', 'NOTICE_PERIOD', 'TERMINATED') NOT NULL DEFAULT 'ACTIVE',
    effective_from           DATE          NOT NULL,
    effective_to             DATE          NULL,
    is_current               BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT pk_employee PRIMARY KEY (employee_id),
    CONSTRAINT uq_employee_email UNIQUE (email),
    CONSTRAINT chk_employee_id_format CHECK (employee_id REGEXP '^EMP-[0-9]{6}$'),
    CONSTRAINT chk_emp_email_format CHECK (email LIKE '%_@__%.__%'),
    CONSTRAINT chk_emp_fte CHECK (fte > 0.00 AND fte <= 1.00),
    CONSTRAINT chk_emp_dates CHECK (termination_date IS NULL OR termination_date >= hire_date),
    CONSTRAINT chk_emp_effective_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT chk_emp_cost_rate CHECK (cost_rate_per_hour >= 0.00),
    CONSTRAINT chk_emp_hours_week CHECK (standard_hours_per_week > 0.00 AND standard_hours_per_week <= 80.00),

    -- Foreign Keys
    CONSTRAINT fk_emp_role FOREIGN KEY (current_role_id) 
        REFERENCES role(role_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_emp_manager FOREIGN KEY (manager_id) 
        REFERENCES employee(employee_id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB COMMENT='Master profile of all internal and contingent workforce members';

-- Indexes for employee
CREATE INDEX idx_emp_role ON employee(current_role_id);
CREATE INDEX idx_emp_manager ON employee(manager_id);
CREATE INDEX idx_emp_department ON employee(department);
CREATE INDEX idx_emp_status_current ON employee(status, is_current);
CREATE INDEX idx_emp_effective_dates ON employee(effective_from, effective_to);


-- ==============================================================================
-- 3. TABLE: skill
-- Master taxonomy of technical, domain, and soft competencies.
-- Deterministic ID Format: SKL-XXXXXX (6 digits, e.g., SKL-000001, SKL-000080)
-- ==============================================================================
CREATE TABLE skill (
    skill_id                 VARCHAR(20)   NOT NULL,
    skill_code               VARCHAR(50)   NOT NULL,
    skill_name               VARCHAR(100)  NOT NULL,
    category                 ENUM('PROGRAMMING_LANGUAGE', 'FRAMEWORK', 'DATABASE', 'CLOUD_DEVOPS', 'DATA_AI', 'DOMAIN_BUSINESS', 'SOFT_SKILL', 'CYBERSECURITY') NOT NULL,
    description              TEXT          NULL,
    status                   ENUM('ACTIVE', 'DEPRECATED', 'PROPOSED') NOT NULL DEFAULT 'ACTIVE',
    effective_from           DATE          NOT NULL,
    effective_to             DATE          NULL,
    is_current               BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT pk_skill PRIMARY KEY (skill_id),
    CONSTRAINT uq_skill_code UNIQUE (skill_code),
    CONSTRAINT chk_skill_id_format CHECK (skill_id REGEXP '^SKL-[0-9]{6}$'),
    CONSTRAINT chk_skill_effective_dates CHECK (effective_to IS NULL OR effective_to >= effective_from)
) ENGINE=InnoDB COMMENT='Standardized competency and skill taxonomy catalog';

-- Indexes for skill
CREATE INDEX idx_skill_category ON skill(category);
CREATE INDEX idx_skill_status ON skill(status, is_current);


-- ==============================================================================
-- 4. TABLE: employee_skill
-- Associative entity mapping employees to skills with verified proficiency ratings.
-- Deterministic ID Format: ESK-XXXXXX (6 digits, e.g., ESK-000001)
-- ==============================================================================
CREATE TABLE employee_skill (
    employee_skill_id        VARCHAR(20)   NOT NULL,
    employee_id              VARCHAR(20)   NOT NULL,
    skill_id                 VARCHAR(20)   NOT NULL,
    proficiency_level        TINYINT       NOT NULL COMMENT '1=Beginner, 2=Intermediate, 3=Proficient, 4=Advanced, 5=Expert/Master',
    years_of_experience      DECIMAL(4,1)  NOT NULL DEFAULT 0.0,
    verification_status      ENUM('SELF_REPORTED', 'PEER_REVIEWED', 'MANAGER_VERIFIED', 'ASSESSMENT_PASSED', 'CERTIFIED') NOT NULL DEFAULT 'SELF_REPORTED',
    last_evaluated_date      DATE          NULL,
    status                   ENUM('ACTIVE', 'INACTIVE', 'EXPIRED') NOT NULL DEFAULT 'ACTIVE',
    effective_from           DATE          NOT NULL,
    effective_to             DATE          NULL,
    is_current               BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT pk_employee_skill PRIMARY KEY (employee_skill_id),
    CONSTRAINT chk_emp_skill_id_format CHECK (employee_skill_id REGEXP '^ESK-[0-9]{6}$'),
    CONSTRAINT chk_es_proficiency CHECK (proficiency_level BETWEEN 1 AND 5),
    CONSTRAINT chk_es_experience CHECK (years_of_experience >= 0.0),
    CONSTRAINT chk_es_effective_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT uq_emp_skill_version UNIQUE (employee_id, skill_id, effective_from),

    -- Foreign Keys
    CONSTRAINT fk_es_employee FOREIGN KEY (employee_id) 
        REFERENCES employee(employee_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_es_skill FOREIGN KEY (skill_id) 
        REFERENCES skill(skill_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='Employee competency portfolio and skill verification records';

-- Indexes for employee_skill
CREATE INDEX idx_es_emp_current ON employee_skill(employee_id, is_current, status);
CREATE INDEX idx_es_skill_proficiency ON employee_skill(skill_id, proficiency_level);
CREATE INDEX idx_es_lookup ON employee_skill(employee_id, skill_id, is_current);


-- ==============================================================================
-- 5. TABLE: project
-- Organizational projects, client engagements, and internal initiatives.
-- Deterministic ID Format: PRJ-YYYY-XXXXXX (e.g., PRJ-2026-000001)
-- ==============================================================================
CREATE TABLE project (
    project_id               VARCHAR(30)   NOT NULL,
    project_code             VARCHAR(30)   NOT NULL,
    project_name             VARCHAR(150)  NOT NULL,
    client_name              VARCHAR(100)  NULL,
    business_unit            VARCHAR(100)  NOT NULL,
    project_manager_id       VARCHAR(20)   NULL,
    start_date               DATE          NOT NULL,
    end_date                 DATE          NULL,
    planned_budget           DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    priority                 ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') NOT NULL DEFAULT 'MEDIUM',
    status                   ENUM('PIPELINE', 'PROPOSED', 'ACTIVE', 'ON_HOLD', 'COMPLETED', 'CANCELLED') NOT NULL DEFAULT 'PROPOSED',
    effective_from           DATE          NOT NULL,
    effective_to             DATE          NULL,
    is_current               BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT pk_project PRIMARY KEY (project_id),
    CONSTRAINT uq_project_code UNIQUE (project_code),
    CONSTRAINT chk_project_id_format CHECK (project_id REGEXP '^PRJ-[0-9]{4}-[0-9]{6}$'),
    CONSTRAINT chk_prj_dates CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT chk_prj_effective_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT chk_prj_budget CHECK (planned_budget >= 0.00),

    -- Foreign Keys
    CONSTRAINT fk_prj_manager FOREIGN KEY (project_manager_id) 
        REFERENCES employee(employee_id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB COMMENT='Client delivery and internal initiative project definitions';

-- Indexes for project
CREATE INDEX idx_prj_manager ON project(project_manager_id);
CREATE INDEX idx_prj_business_unit ON project(business_unit);
CREATE INDEX idx_prj_status_priority ON project(status, priority);
CREATE INDEX idx_prj_dates ON project(start_date, end_date);


-- ==============================================================================
-- 6. TABLE: demand_plan
-- Forward-looking staffing demand requirements per role, skill, and timeframe.
-- Deterministic ID Format: DEM-<project-id>-YYYY'W'WW (e.g., DEM-PRJ-2026-000001-2026W01)
-- ==============================================================================
CREATE TABLE demand_plan (
    demand_id                VARCHAR(60)   NOT NULL,
    project_id               VARCHAR(30)   NOT NULL,
    role_id                  VARCHAR(16)   NOT NULL,
    required_skill_id        VARCHAR(20)   NOT NULL,
    min_proficiency_level    TINYINT       NOT NULL DEFAULT 3 COMMENT 'Required proficiency level 1-5',
    headcount_required       INT           NOT NULL DEFAULT 1,
    required_fte             DECIMAL(5,2)  NOT NULL DEFAULT 1.00 COMMENT 'Full-Time Equivalent required (e.g. 1.0 = 1 FTE)',
    start_date               DATE          NOT NULL,
    end_date                 DATE          NOT NULL,
    priority                 ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') NOT NULL DEFAULT 'MEDIUM',
    fulfillment_status       ENUM('UNFULFILLED', 'PARTIALLY_FULFILLED', 'FULFILLED', 'CANCELLED') NOT NULL DEFAULT 'UNFULFILLED',
    status                   ENUM('DRAFT', 'SUBMITTED', 'APPROVED', 'ACTIVE', 'CLOSED', 'SUPERSEDED') NOT NULL DEFAULT 'DRAFT',
    effective_from           DATE          NOT NULL,
    effective_to             DATE          NULL,
    is_current               BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT pk_demand_plan PRIMARY KEY (demand_id),
    CONSTRAINT chk_demand_id_format CHECK (demand_id REGEXP '^DEM-PRJ-[0-9]{4}-[0-9]{6}-[0-9]{4}W(0[1-9]|[1-4][0-9]|5[0-3])(-[0-9]{2})?$'),
    CONSTRAINT chk_dp_dates CHECK (end_date >= start_date),
    CONSTRAINT chk_dp_effective_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT chk_dp_headcount CHECK (headcount_required > 0),
    CONSTRAINT chk_dp_fte CHECK (required_fte > 0.00),
    CONSTRAINT chk_dp_min_prof CHECK (min_proficiency_level BETWEEN 1 AND 5),

    -- Foreign Keys
    CONSTRAINT fk_dp_project FOREIGN KEY (project_id) 
        REFERENCES project(project_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_dp_role FOREIGN KEY (role_id) 
        REFERENCES role(role_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_dp_skill FOREIGN KEY (required_skill_id) 
        REFERENCES skill(skill_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='Project staffing demand requirements by role, skill, and FTE';

-- Indexes for demand_plan
CREATE INDEX idx_dp_project ON demand_plan(project_id);
CREATE INDEX idx_dp_role_skill ON demand_plan(role_id, required_skill_id);
CREATE INDEX idx_dp_fulfillment ON demand_plan(fulfillment_status, status);
CREATE INDEX idx_dp_dates ON demand_plan(start_date, end_date);


-- ==============================================================================
-- 7. TABLE: allocation
-- Operational assignment of an employee to a project/demand plan.
-- Deterministic ID Format: ALLOC-YYYY-XXXXXX (e.g., ALLOC-2026-000001)
-- ==============================================================================
CREATE TABLE allocation (
    allocation_id            VARCHAR(30)   NOT NULL,
    employee_id              VARCHAR(20)   NOT NULL,
    project_id               VARCHAR(30)   NOT NULL,
    demand_id                VARCHAR(60)   NULL,
    allocation_percentage    DECIMAL(5,2)  NOT NULL DEFAULT 100.00 COMMENT 'Percentage of time dedicated (e.g. 100.00 = 100%, 50.00 = 50%)',
    billing_rate_per_hour    DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    is_billable              BOOLEAN       NOT NULL DEFAULT TRUE,
    start_date               DATE          NOT NULL,
    end_date                 DATE          NOT NULL,
    allocation_status        ENUM('REQUESTED', 'CONFIRMED', 'ACTIVE', 'COMPLETED', 'RELEASED', 'CANCELLED') NOT NULL DEFAULT 'REQUESTED',
    status                   ENUM('PLANNED', 'COMMITTED', 'TERMINATED_EARLY', 'ARCHIVED') NOT NULL DEFAULT 'COMMITTED',
    effective_from           DATE          NOT NULL,
    effective_to             DATE          NULL,
    is_current               BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT pk_allocation PRIMARY KEY (allocation_id),
    CONSTRAINT chk_allocation_id_format CHECK (allocation_id REGEXP '^ALLOC-[0-9]{4}-[0-9]{6}$'),
    CONSTRAINT chk_alc_dates CHECK (end_date >= start_date),
    CONSTRAINT chk_alc_effective_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT chk_alc_percentage CHECK (allocation_percentage > 0.00 AND allocation_percentage <= 100.00),
    CONSTRAINT chk_alc_bill_rate CHECK (billing_rate_per_hour >= 0.00),

    -- Foreign Keys
    CONSTRAINT fk_alc_employee FOREIGN KEY (employee_id) 
        REFERENCES employee(employee_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_alc_project FOREIGN KEY (project_id) 
        REFERENCES project(project_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_alc_demand FOREIGN KEY (demand_id) 
        REFERENCES demand_plan(demand_id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB COMMENT='Assignment of workforce talent to project demands and schedules';

-- Indexes for allocation
CREATE INDEX idx_alc_emp_dates ON allocation(employee_id, start_date, end_date, allocation_status);
CREATE INDEX idx_alc_prj_dates ON allocation(project_id, start_date, end_date, allocation_status);
CREATE INDEX idx_alc_demand ON allocation(demand_id);
CREATE INDEX idx_alc_status ON allocation(allocation_status, is_current);


-- ==============================================================================
-- 8. TABLE: availability
-- Tracks employee periodic capacity, FTE factor, approved leave, and net bench availability.
-- Deterministic ID Format: AVL-XXXXX (e.g., AVL-00001, AVL-00340)
-- NOTE: In compliance with MySQL 8.0 rules, generated columns compute strictly
-- within intra-row columns (base_capacity_hours * fte - approved_leave - allocated).
-- Cross-table aggregations are computed via SQL Views / application service logic.
-- ==============================================================================
CREATE TABLE availability (
    availability_id           VARCHAR(20)   NOT NULL,
    employee_id               VARCHAR(20)   NOT NULL,
    start_date                DATE          NOT NULL,
    end_date                  DATE          NOT NULL,
    fte                       DECIMAL(3,2)  NOT NULL DEFAULT 1.00 COMMENT 'Contracted FTE (e.g. 1.00 = 100%, 0.50 = 50%)',
    base_capacity_hours       DECIMAL(5,2)  NOT NULL DEFAULT 40.00 COMMENT 'Standard full-time weekly base hours (e.g. 40.00)',
    contracted_capacity_hours DECIMAL(5,2)  GENERATED ALWAYS AS (ROUND(base_capacity_hours * fte, 2)) STORED COMMENT 'Effective contracted capacity = base_hours * fte',
    approved_leave_hours      DECIMAL(5,2)  NOT NULL DEFAULT 0.00 COMMENT 'Approved leave / PTO hours deducted for this period',
    allocated_hours           DECIMAL(5,2)  NOT NULL DEFAULT 0.00 COMMENT 'Committed project hours for this period (updated via service/ETL)',
    net_available_hours       DECIMAL(5,2)  GENERATED ALWAYS AS (
        GREATEST(0.00, ROUND((base_capacity_hours * fte) - approved_leave_hours - allocated_hours, 2))
    ) STORED COMMENT 'Net available bench hours = contracted_capacity - leave - allocated',
    availability_percentage   DECIMAL(5,2)  GENERATED ALWAYS AS (
        CASE 
            WHEN (base_capacity_hours * fte) > 0.00 THEN
                LEAST(100.00, GREATEST(0.00, ROUND(
                    (GREATEST(0.00, (base_capacity_hours * fte) - approved_leave_hours - allocated_hours) / (base_capacity_hours * fte)) * 100.00, 2
                )))
            ELSE 0.00 
        END
    ) STORED COMMENT 'Bench availability percentage (0.00% to 100.00%)',
    availability_type         ENUM('AVAILABLE_BENCH', 'PARTIALLY_ALLOCATED', 'FULLY_ALLOCATED', 'ON_APPROVED_LEAVE', 'TRAINING', 'SABBATICAL') NOT NULL DEFAULT 'AVAILABLE_BENCH',
    status                    ENUM('PROJECTED', 'CONFIRMED', 'OVERRIDDEN', 'HISTORICAL') NOT NULL DEFAULT 'PROJECTED',
    notes                     VARCHAR(255)  NULL,
    effective_from            DATE          NOT NULL,
    effective_to              DATE          NULL,
    is_current                BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at                TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT pk_availability PRIMARY KEY (availability_id),
    CONSTRAINT chk_availability_id_format CHECK (availability_id REGEXP '^AVL-[0-9]{5}$'),
    CONSTRAINT chk_avl_dates CHECK (end_date >= start_date),
    CONSTRAINT chk_avl_effective_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT chk_avl_fte CHECK (fte > 0.00 AND fte <= 1.00),
    CONSTRAINT chk_avl_hours CHECK (base_capacity_hours >= 0.00 AND approved_leave_hours >= 0.00 AND allocated_hours >= 0.00),

    -- Foreign Keys
    CONSTRAINT fk_avl_employee FOREIGN KEY (employee_id) 
        REFERENCES employee(employee_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='Employee weekly/periodic capacity and bench availability log';

-- Indexes for availability
CREATE INDEX idx_avl_emp_period ON availability(employee_id, start_date, end_date);
CREATE INDEX idx_avl_type_status ON availability(availability_type, status, is_current);
CREATE INDEX idx_avl_percentage ON availability(availability_percentage);


-- ==============================================================================
-- 9. TABLE: training
-- Employee upskilling programs, certifications, and courses for skill enablement.
-- Deterministic ID Format: TRN-XXXXX (e.g., TRN-00001, TRN-00120)
-- ==============================================================================
CREATE TABLE training (
    training_id              VARCHAR(20)   NOT NULL,
    employee_id              VARCHAR(20)   NOT NULL,
    skill_id                 VARCHAR(20)   NOT NULL,
    training_title           VARCHAR(150)  NOT NULL,
    provider                 VARCHAR(100)  NOT NULL,
    training_type            ENUM('COURSE', 'BOOTCAMP', 'CERTIFICATION', 'INTERNAL_WORKSHOP', 'MENTORSHIP', 'SELF_PACED') NOT NULL,
    target_proficiency_level TINYINT       NOT NULL COMMENT 'Target level 1-5 to be achieved upon completion',
    start_date               DATE          NOT NULL,
    expected_completion_date DATE          NOT NULL,
    actual_completion_date   DATE          NULL,
    cost                     DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    hours_dedicated          DECIMAL(5,2)  NOT NULL DEFAULT 0.00,
    score                    DECIMAL(5,2)  NULL COMMENT 'Assessment or final exam score percentage (0-100)',
    certification_url        VARCHAR(255)  NULL,
    lifecycle_status         ENUM('NOMINATED', 'APPROVED', 'ENROLLED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'DROPPED') NOT NULL DEFAULT 'NOMINATED',
    status                   ENUM('ACTIVE', 'SUPERSEDED', 'CANCELLED', 'ARCHIVED') NOT NULL DEFAULT 'ACTIVE',
    effective_from           DATE          NOT NULL,
    effective_to             DATE          NULL,
    is_current               BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT pk_training PRIMARY KEY (training_id),
    CONSTRAINT chk_training_id_format CHECK (training_id REGEXP '^TRN-[0-9]{5}$'),
    CONSTRAINT chk_trn_dates CHECK (expected_completion_date >= start_date),
    CONSTRAINT chk_trn_comp_date CHECK (actual_completion_date IS NULL OR actual_completion_date >= start_date),
    CONSTRAINT chk_trn_effective_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT chk_trn_target_prof CHECK (target_proficiency_level BETWEEN 1 AND 5),
    CONSTRAINT chk_trn_cost CHECK (cost >= 0.00),
    CONSTRAINT chk_trn_score CHECK (score IS NULL OR (score >= 0.00 AND score <= 100.00)),

    -- Foreign Keys
    CONSTRAINT fk_trn_employee FOREIGN KEY (employee_id) 
        REFERENCES employee(employee_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_trn_skill FOREIGN KEY (skill_id) 
        REFERENCES skill(skill_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='Employee upskilling, certification, and training engagement tracking';

-- Indexes for training
CREATE INDEX idx_trn_emp_skill ON training(employee_id, skill_id);
CREATE INDEX idx_trn_lifecycle ON training(lifecycle_status, status);
CREATE INDEX idx_trn_dates ON training(start_date, expected_completion_date);


-- ==============================================================================
-- 10. TABLE: gap_analysis
-- Workforce intelligence analytics evaluating shortfalls between supply and demand.
-- Deterministic ID Format: GAP-XXXXX (e.g., GAP-00001, GAP-00050)
-- NOTE: shortage_headcount uses intra-row calculation. Cross-table dynamic gap
-- identification is surfaced via SQL Views and Python analytics services.
-- ==============================================================================
CREATE TABLE gap_analysis (
    gap_analysis_id               VARCHAR(20)   NOT NULL,
    analysis_code                 VARCHAR(50)   NOT NULL,
    demand_id                     VARCHAR(60)   NULL COMMENT 'Optional reference to origin demand plan',
    project_id                    VARCHAR(30)   NULL COMMENT 'Optional reference to origin project',
    role_id                       VARCHAR(16)   NULL COMMENT 'Target role examined',
    skill_id                      VARCHAR(20)   NOT NULL COMMENT 'Target skill analyzed',
    analysis_date                 DATE          NOT NULL,
    period_start_date             DATE          NOT NULL,
    period_end_date               DATE          NOT NULL,
    required_headcount            INT           NOT NULL DEFAULT 1,
    available_headcount           INT           NOT NULL DEFAULT 0,
    shortage_headcount            INT           GENERATED ALWAYS AS (GREATEST(0, required_headcount - available_headcount)) STORED,
    required_proficiency_level    TINYINT       NOT NULL DEFAULT 3,
    avg_current_proficiency_level DECIMAL(3,2)  NULL,
    gap_severity                  ENUM('NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL') NOT NULL DEFAULT 'MEDIUM',
    recommended_action            ENUM('HIRE_EXTERNAL', 'UPSKILL_INTERNAL', 'REASSIGN_BENCH', 'ENGAGE_CONTRACTOR', 'CROSS_TRAIN', 'NO_ACTION') NOT NULL DEFAULT 'UPSKILL_INTERNAL',
    status                        ENUM('OPEN', 'IN_REVIEW', 'ACTION_PLANNED', 'MITIGATED', 'CLOSED') NOT NULL DEFAULT 'OPEN',
    notes                         TEXT          NULL,
    effective_from                DATE          NOT NULL,
    effective_to                  DATE          NULL,
    is_current                    BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at                    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT pk_gap_analysis PRIMARY KEY (gap_analysis_id),
    CONSTRAINT uq_gap_analysis_code UNIQUE (analysis_code),
    CONSTRAINT chk_gap_id_format CHECK (gap_analysis_id REGEXP '^GAP-[0-9]{5}$'),
    CONSTRAINT chk_gap_period_dates CHECK (period_end_date >= period_start_date),
    CONSTRAINT chk_gap_effective_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT chk_gap_headcounts CHECK (required_headcount >= 0 AND available_headcount >= 0),
    CONSTRAINT chk_gap_req_prof CHECK (required_proficiency_level BETWEEN 1 AND 5),
    CONSTRAINT chk_gap_avg_prof CHECK (avg_current_proficiency_level IS NULL OR (avg_current_proficiency_level >= 0.00 AND avg_current_proficiency_level <= 5.00)),

    -- Foreign Keys
    CONSTRAINT fk_gap_demand FOREIGN KEY (demand_id) 
        REFERENCES demand_plan(demand_id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_gap_project FOREIGN KEY (project_id) 
        REFERENCES project(project_id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_gap_role FOREIGN KEY (role_id) 
        REFERENCES role(role_id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_gap_skill FOREIGN KEY (skill_id) 
        REFERENCES skill(skill_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='Workforce supply vs. demand capability and headcount gap diagnostics';

-- Indexes for gap_analysis
CREATE INDEX idx_gap_skill_role ON gap_analysis(skill_id, role_id);
CREATE INDEX idx_gap_project_demand ON gap_analysis(project_id, demand_id);
CREATE INDEX idx_gap_severity_status ON gap_analysis(gap_severity, status, is_current);
CREATE INDEX idx_gap_dates ON gap_analysis(analysis_date, period_start_date, period_end_date);


-- ==============================================================================
-- 11. TABLE: historical_event_log
-- Audit log and event-sourcing trail supporting historical lifecycle events.
-- Deterministic ID Format: EVT-XXXXXXXX (e.g., EVT-00000001)
-- ==============================================================================
CREATE TABLE historical_event_log (
    event_id                 VARCHAR(24)   NOT NULL,
    entity_type              ENUM('EMPLOYEE', 'ROLE', 'SKILL', 'EMPLOYEE_SKILL', 'PROJECT', 'DEMAND_PLAN', 'ALLOCATION', 'AVAILABILITY', 'TRAINING', 'GAP_ANALYSIS') NOT NULL,
    entity_id                VARCHAR(60)   NOT NULL,
    event_type               ENUM('CREATED', 'STATUS_CHANGE', 'ALLOCATED', 'DEALLOCATED', 'SKILL_UPGRADE', 'CAPACITY_CHANGE', 'DEMAND_CHANGE', 'GAP_IDENTIFIED', 'TRAINING_ENROLLED', 'TRAINING_COMPLETED', 'RECORD_SUPERSEDED') NOT NULL,
    old_state                JSON          NULL,
    new_state                JSON          NULL,
    reason                   VARCHAR(255)  NULL,
    performed_by             VARCHAR(100)  NOT NULL DEFAULT 'SYSTEM',
    event_timestamp          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT pk_historical_event_log PRIMARY KEY (event_id),
    CONSTRAINT chk_event_id_format CHECK (event_id REGEXP '^EVT-[0-9]{8}$')
) ENGINE=InnoDB COMMENT='Immutable event audit trail capturing all state transitions';

-- Indexes for historical_event_log
CREATE INDEX idx_evt_entity ON historical_event_log(entity_type, entity_id);
CREATE INDEX idx_evt_timestamp ON historical_event_log(event_timestamp);
CREATE INDEX idx_evt_type ON historical_event_log(event_type);


-- ==============================================================================
-- ANALYTICAL VIEWS FOR STREAMLIT DASHBOARD (Cross-Table Calculations)
-- ==============================================================================

-- View 1: Active Workforce Profile with Role details and Contracted Capacity
CREATE OR REPLACE VIEW vw_active_workforce AS
SELECT 
    e.employee_id,
    CONCAT(e.first_name, ' ', e.last_name) AS full_name,
    e.email,
    e.department,
    e.work_location,
    e.employment_type,
    e.fte,
    e.standard_hours_per_week,
    ROUND(e.standard_hours_per_week * e.fte, 2) AS contracted_weekly_hours,
    e.hire_date,
    e.cost_rate_per_hour,
    e.status AS employee_status,
    r.role_id,
    r.role_name,
    r.job_level,
    CONCAT(m.first_name, ' ', m.last_name) AS manager_name
FROM employee e
JOIN role r ON e.current_role_id = r.role_id
LEFT JOIN employee m ON e.manager_id = m.employee_id
WHERE e.is_current = TRUE AND e.status != 'TERMINATED';

-- View 2: Active Skill Matrix & Employee Proficiency
CREATE OR REPLACE VIEW vw_employee_skill_inventory AS
SELECT 
    es.employee_skill_id,
    e.employee_id,
    CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
    e.department,
    s.skill_id,
    s.skill_name,
    s.category AS skill_category,
    es.proficiency_level,
    CASE es.proficiency_level
        WHEN 1 THEN 'Beginner'
        WHEN 2 THEN 'Intermediate'
        WHEN 3 THEN 'Proficient'
        WHEN 4 THEN 'Advanced'
        WHEN 5 THEN 'Expert / Master'
    END AS proficiency_label,
    es.years_of_experience,
    es.verification_status,
    es.status AS skill_status
FROM employee_skill es
JOIN employee e ON es.employee_id = e.employee_id
JOIN skill s ON es.skill_id = s.skill_id
WHERE es.is_current = TRUE AND es.status = 'ACTIVE';

-- View 3: Project Allocation and Demand Fulfillment
CREATE OR REPLACE VIEW vw_project_allocation_summary AS
SELECT 
    p.project_id,
    p.project_code,
    p.project_name,
    p.business_unit,
    p.status AS project_status,
    a.allocation_id,
    e.employee_id,
    CONCAT(e.first_name, ' ', e.last_name) AS consultant_name,
    r.role_name,
    a.allocation_percentage,
    a.billing_rate_per_hour,
    a.start_date AS allocation_start,
    a.end_date AS allocation_end,
    a.allocation_status,
    a.demand_id
FROM allocation a
JOIN project p ON a.project_id = p.project_id
JOIN employee e ON a.employee_id = e.employee_id
JOIN role r ON e.current_role_id = r.role_id
WHERE a.is_current = TRUE;

-- View 4: Live Cross-Table Workforce Capacity & Bench Analysis
-- Dynamically integrates employee FTE, standard hours, approved leave, and active allocations
CREATE OR REPLACE VIEW vw_workforce_capacity_analysis AS
SELECT 
    av.availability_id,
    av.employee_id,
    CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
    e.department,
    e.employment_type,
    av.start_date AS period_start,
    av.end_date AS period_end,
    av.fte,
    av.base_capacity_hours,
    av.contracted_capacity_hours,
    av.approved_leave_hours,
    av.allocated_hours,
    av.net_available_hours,
    av.availability_percentage,
    av.availability_type,
    av.status AS capacity_status
FROM availability av
JOIN employee e ON av.employee_id = e.employee_id
WHERE av.is_current = TRUE;

-- View 5: Workforce Capability Gaps Requiring Action
CREATE OR REPLACE VIEW vw_actionable_gaps AS
SELECT 
    g.gap_analysis_id,
    g.analysis_code,
    g.gap_severity,
    g.recommended_action,
    g.status AS gap_status,
    s.skill_name,
    s.category AS skill_category,
    r.role_name,
    p.project_name,
    g.required_headcount,
    g.available_headcount,
    g.shortage_headcount,
    g.required_proficiency_level,
    g.avg_current_proficiency_level,
    g.period_start_date,
    g.period_end_date
FROM gap_analysis g
JOIN skill s ON g.skill_id = s.skill_id
LEFT JOIN role r ON g.role_id = r.role_id
LEFT JOIN project p ON g.project_id = p.project_id
WHERE g.is_current = TRUE AND g.status IN ('OPEN', 'IN_REVIEW', 'ACTION_PLANNED')
ORDER BY 
    CASE g.gap_severity 
        WHEN 'CRITICAL' THEN 1 
        WHEN 'HIGH' THEN 2 
        WHEN 'MEDIUM' THEN 3 
        WHEN 'LOW' THEN 4 
        ELSE 5 
    END,
    g.shortage_headcount DESC;
