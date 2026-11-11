"""
SQLAlchemy 2.0 declarative ORM models for the Workforce Intelligence Platform.
Mirrors database/schema.sql exactly (10 core tables).
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Enum definitions (mirroring MySQL ENUM columns)
# ---------------------------------------------------------------------------

class RoleStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class JobLevel(str, enum.Enum):
    ENTRY = "ENTRY"
    JUNIOR = "JUNIOR"
    MID = "MID"
    SENIOR = "SENIOR"
    LEAD = "LEAD"
    PRINCIPAL = "PRINCIPAL"
    DIRECTOR = "DIRECTOR"


class EmploymentType(str, enum.Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACTOR = "CONTRACTOR"
    INTERN = "INTERN"


class EmployeeStatus(str, enum.Enum):
    ONBOARDING = "ONBOARDING"
    ACTIVE = "ACTIVE"
    ON_LEAVE = "ON_LEAVE"
    NOTICE_PERIOD = "NOTICE_PERIOD"
    TERMINATED = "TERMINATED"


class SkillCategory(str, enum.Enum):
    PROGRAMMING_LANGUAGE = "PROGRAMMING_LANGUAGE"
    FRAMEWORK = "FRAMEWORK"
    DATABASE = "DATABASE"
    CLOUD_DEVOPS = "CLOUD_DEVOPS"
    DATA_AI = "DATA_AI"
    DOMAIN_BUSINESS = "DOMAIN_BUSINESS"
    SOFT_SKILL = "SOFT_SKILL"
    CYBERSECURITY = "CYBERSECURITY"


class SkillStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    PROPOSED = "PROPOSED"


class VerificationStatus(str, enum.Enum):
    SELF_REPORTED = "SELF_REPORTED"
    PEER_REVIEWED = "PEER_REVIEWED"
    MANAGER_VERIFIED = "MANAGER_VERIFIED"
    ASSESSMENT_PASSED = "ASSESSMENT_PASSED"
    CERTIFIED = "CERTIFIED"


class EmployeeSkillStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    EXPIRED = "EXPIRED"


class ProjectPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ProjectStatus(str, enum.Enum):
    PIPELINE = "PIPELINE"
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class FulfillmentStatus(str, enum.Enum):
    UNFULFILLED = "UNFULFILLED"
    PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"


class DemandStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    SUPERSEDED = "SUPERSEDED"


class AllocationOperationalStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    RELEASED = "RELEASED"
    CANCELLED = "CANCELLED"


class AllocationStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    COMMITTED = "COMMITTED"
    TERMINATED_EARLY = "TERMINATED_EARLY"
    ARCHIVED = "ARCHIVED"


class AvailabilityType(str, enum.Enum):
    AVAILABLE_BENCH = "AVAILABLE_BENCH"
    PARTIALLY_ALLOCATED = "PARTIALLY_ALLOCATED"
    FULLY_ALLOCATED = "FULLY_ALLOCATED"
    ON_APPROVED_LEAVE = "ON_APPROVED_LEAVE"
    TRAINING = "TRAINING"
    SABBATICAL = "SABBATICAL"


class AvailabilityStatus(str, enum.Enum):
    PROJECTED = "PROJECTED"
    CONFIRMED = "CONFIRMED"
    OVERRIDDEN = "OVERRIDDEN"
    HISTORICAL = "HISTORICAL"


class TrainingType(str, enum.Enum):
    COURSE = "COURSE"
    BOOTCAMP = "BOOTCAMP"
    CERTIFICATION = "CERTIFICATION"
    INTERNAL_WORKSHOP = "INTERNAL_WORKSHOP"
    MENTORSHIP = "MENTORSHIP"
    SELF_PACED = "SELF_PACED"


class TrainingLifecycleStatus(str, enum.Enum):
    NOMINATED = "NOMINATED"
    APPROVED = "APPROVED"
    ENROLLED = "ENROLLED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DROPPED = "DROPPED"


class TrainingStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class GapSeverity(str, enum.Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendedAction(str, enum.Enum):
    HIRE_EXTERNAL = "HIRE_EXTERNAL"
    UPSKILL_INTERNAL = "UPSKILL_INTERNAL"
    REASSIGN_BENCH = "REASSIGN_BENCH"
    ENGAGE_CONTRACTOR = "ENGAGE_CONTRACTOR"
    CROSS_TRAIN = "CROSS_TRAIN"
    NO_ACTION = "NO_ACTION"


class GapAnalysisStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    ACTION_PLANNED = "ACTION_PLANNED"
    MITIGATED = "MITIGATED"
    CLOSED = "CLOSED"


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# 1. Role
# ---------------------------------------------------------------------------

class Role(Base):
    __tablename__ = "role"

    role_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    role_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    job_level: Mapped[str] = mapped_column(String(20), nullable=False)
    standard_hourly_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED"), nullable=False, default="ACTIVE"
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    employees: Mapped[List["Employee"]] = relationship(
        "Employee", back_populates="role", foreign_keys="Employee.current_role_id"
    )
    demand_plans: Mapped[List["DemandPlan"]] = relationship("DemandPlan", back_populates="role")
    gap_analyses: Mapped[List["GapAnalysis"]] = relationship("GapAnalysis", back_populates="role")


# ---------------------------------------------------------------------------
# 2. Employee
# ---------------------------------------------------------------------------

class Employee(Base):
    __tablename__ = "employee"

    employee_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(25), nullable=True)
    current_role_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("role.role_id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    manager_id: Mapped[Optional[str]] = mapped_column(
        String(20), ForeignKey("employee.employee_id", onupdate="CASCADE", ondelete="SET NULL"), nullable=True
    )
    employment_type: Mapped[str] = mapped_column(
        Enum("FULL_TIME", "PART_TIME", "CONTRACTOR", "INTERN"), nullable=False, default="FULL_TIME"
    )
    fte: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=Decimal("1.00"))
    work_location: Mapped[str] = mapped_column(String(100), nullable=False, default="Remote")
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cost_rate_per_hour: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    standard_hours_per_week: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("40.00")
    )
    status: Mapped[str] = mapped_column(
        Enum("ONBOARDING", "ACTIVE", "ON_LEAVE", "NOTICE_PERIOD", "TERMINATED"),
        nullable=False,
        default="ACTIVE",
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    role: Mapped["Role"] = relationship(
        "Role", back_populates="employees", foreign_keys=[current_role_id]
    )
    manager: Mapped[Optional["Employee"]] = relationship(
        "Employee", remote_side="Employee.employee_id", foreign_keys=[manager_id], back_populates="subordinates"
    )
    subordinates: Mapped[List["Employee"]] = relationship(
        "Employee", foreign_keys=[manager_id], back_populates="manager"
    )
    employee_skills: Mapped[List["EmployeeSkill"]] = relationship("EmployeeSkill", back_populates="employee")
    managed_projects: Mapped[List["Project"]] = relationship("Project", back_populates="project_manager")
    allocations: Mapped[List["Allocation"]] = relationship("Allocation", back_populates="employee")
    availabilities: Mapped[List["Availability"]] = relationship("Availability", back_populates="employee")
    trainings: Mapped[List["Training"]] = relationship("Training", back_populates="employee")
    leave_events: Mapped[List["LeaveEvent"]] = relationship(
        "LeaveEvent", foreign_keys="LeaveEvent.employee_id", back_populates="employee"
    )


# ---------------------------------------------------------------------------
# 3. Skill
# ---------------------------------------------------------------------------

class Skill(Base):
    __tablename__ = "skill"

    skill_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    skill_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(
        Enum(
            "PROGRAMMING_LANGUAGE", "FRAMEWORK", "DATABASE", "CLOUD_DEVOPS",
            "DATA_AI", "DOMAIN_BUSINESS", "SOFT_SKILL", "CYBERSECURITY"
        ),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("ACTIVE", "DEPRECATED", "PROPOSED"), nullable=False, default="ACTIVE"
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    employee_skills: Mapped[List["EmployeeSkill"]] = relationship("EmployeeSkill", back_populates="skill")
    demand_plans: Mapped[List["DemandPlan"]] = relationship("DemandPlan", back_populates="required_skill")
    trainings: Mapped[List["Training"]] = relationship("Training", back_populates="skill")
    gap_analyses: Mapped[List["GapAnalysis"]] = relationship("GapAnalysis", back_populates="skill")


# ---------------------------------------------------------------------------
# 4. EmployeeSkill
# ---------------------------------------------------------------------------

class EmployeeSkill(Base):
    __tablename__ = "employee_skill"

    employee_skill_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("employee.employee_id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    skill_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("skill.skill_id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    proficiency_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    years_of_experience: Mapped[Decimal] = mapped_column(
        Numeric(4, 1), nullable=False, default=Decimal("0.0")
    )
    verification_status: Mapped[str] = mapped_column(
        Enum("SELF_REPORTED", "PEER_REVIEWED", "MANAGER_VERIFIED", "ASSESSMENT_PASSED", "CERTIFIED"),
        nullable=False,
        default="SELF_REPORTED",
    )
    last_evaluated_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("ACTIVE", "INACTIVE", "EXPIRED"), nullable=False, default="ACTIVE"
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    employee: Mapped["Employee"] = relationship("Employee", back_populates="employee_skills")
    skill: Mapped["Skill"] = relationship("Skill", back_populates="employee_skills")


# ---------------------------------------------------------------------------
# 5. Project
# ---------------------------------------------------------------------------

class Project(Base):
    __tablename__ = "project"

    project_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    project_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    project_name: Mapped[str] = mapped_column(String(150), nullable=False)
    client_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    business_unit: Mapped[str] = mapped_column(String(100), nullable=False)
    project_manager_id: Mapped[Optional[str]] = mapped_column(
        String(20), ForeignKey("employee.employee_id", onupdate="CASCADE", ondelete="SET NULL"), nullable=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    planned_budget: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    priority: Mapped[str] = mapped_column(
        Enum("LOW", "MEDIUM", "HIGH", "CRITICAL"), nullable=False, default="MEDIUM"
    )
    status: Mapped[str] = mapped_column(
        Enum("PIPELINE", "PROPOSED", "ACTIVE", "ON_HOLD", "COMPLETED", "CANCELLED"),
        nullable=False,
        default="PROPOSED",
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    project_manager: Mapped[Optional["Employee"]] = relationship("Employee", back_populates="managed_projects")
    demand_plans: Mapped[List["DemandPlan"]] = relationship("DemandPlan", back_populates="project")
    allocations: Mapped[List["Allocation"]] = relationship("Allocation", back_populates="project")
    gap_analyses: Mapped[List["GapAnalysis"]] = relationship("GapAnalysis", back_populates="project")


# ---------------------------------------------------------------------------
# 6. DemandPlan
# ---------------------------------------------------------------------------

class DemandPlan(Base):
    __tablename__ = "demand_plan"

    demand_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("project.project_id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    role_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("role.role_id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    required_skill_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("skill.skill_id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    min_proficiency_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    headcount_required: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    required_fte: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("1.00"))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    priority: Mapped[str] = mapped_column(
        Enum("LOW", "MEDIUM", "HIGH", "CRITICAL"), nullable=False, default="MEDIUM"
    )
    fulfillment_status: Mapped[str] = mapped_column(
        Enum("UNFULFILLED", "PARTIALLY_FULFILLED", "FULFILLED", "CANCELLED"),
        nullable=False,
        default="UNFULFILLED",
    )
    status: Mapped[str] = mapped_column(
        Enum("DRAFT", "SUBMITTED", "APPROVED", "ACTIVE", "CLOSED", "SUPERSEDED"),
        nullable=False,
        default="DRAFT",
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="demand_plans")
    role: Mapped["Role"] = relationship("Role", back_populates="demand_plans")
    required_skill: Mapped["Skill"] = relationship("Skill", back_populates="demand_plans")
    allocations: Mapped[List["Allocation"]] = relationship("Allocation", back_populates="demand")
    gap_analyses: Mapped[List["GapAnalysis"]] = relationship("GapAnalysis", back_populates="demand")


# ---------------------------------------------------------------------------
# 7. Allocation
# ---------------------------------------------------------------------------

class Allocation(Base):
    __tablename__ = "allocation"

    allocation_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("employee.employee_id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("project.project_id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    demand_id: Mapped[Optional[str]] = mapped_column(
        String(60), ForeignKey("demand_plan.demand_id", onupdate="CASCADE", ondelete="SET NULL"), nullable=True
    )
    allocation_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("100.00")
    )
    billing_rate_per_hour: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    is_billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    allocation_status: Mapped[str] = mapped_column(
        Enum("REQUESTED", "CONFIRMED", "ACTIVE", "COMPLETED", "RELEASED", "CANCELLED"),
        nullable=False,
        default="REQUESTED",
    )
    status: Mapped[str] = mapped_column(
        Enum("PLANNED", "COMMITTED", "TERMINATED_EARLY", "ARCHIVED"),
        nullable=False,
        default="COMMITTED",
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    employee: Mapped["Employee"] = relationship("Employee", back_populates="allocations")
    project: Mapped["Project"] = relationship("Project", back_populates="allocations")
    demand: Mapped[Optional["DemandPlan"]] = relationship("DemandPlan", back_populates="allocations")


# ---------------------------------------------------------------------------
# 8. Availability
# ---------------------------------------------------------------------------

class Availability(Base):
    __tablename__ = "availability"

    availability_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("employee.employee_id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    fte: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=Decimal("1.00"))
    base_capacity_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("40.00")
    )
    # contracted_capacity_hours — GENERATED ALWAYS (STORED); read-only via ORM
    contracted_capacity_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    approved_leave_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    allocated_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    # net_available_hours — GENERATED ALWAYS (STORED); read-only via ORM
    net_available_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    # availability_percentage — GENERATED ALWAYS (STORED); read-only via ORM
    availability_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    availability_type: Mapped[str] = mapped_column(
        Enum(
            "AVAILABLE_BENCH", "PARTIALLY_ALLOCATED", "FULLY_ALLOCATED",
            "ON_APPROVED_LEAVE", "TRAINING", "SABBATICAL"
        ),
        nullable=False,
        default="AVAILABLE_BENCH",
    )
    status: Mapped[str] = mapped_column(
        Enum("PROJECTED", "CONFIRMED", "OVERRIDDEN", "HISTORICAL"),
        nullable=False,
        default="PROJECTED",
    )
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    employee: Mapped["Employee"] = relationship("Employee", back_populates="availabilities")


# ---------------------------------------------------------------------------
# 9. Training
# ---------------------------------------------------------------------------

class Training(Base):
    __tablename__ = "training"

    training_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("employee.employee_id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    skill_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("skill.skill_id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    training_title: Mapped[str] = mapped_column(String(150), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    training_type: Mapped[str] = mapped_column(
        Enum("COURSE", "BOOTCAMP", "CERTIFICATION", "INTERNAL_WORKSHOP", "MENTORSHIP", "SELF_PACED"),
        nullable=False,
    )
    target_proficiency_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_completion_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    hours_dedicated: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    certification_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(
        Enum("NOMINATED", "APPROVED", "ENROLLED", "IN_PROGRESS", "COMPLETED", "FAILED", "DROPPED"),
        nullable=False,
        default="NOMINATED",
    )
    status: Mapped[str] = mapped_column(
        Enum("ACTIVE", "SUPERSEDED", "CANCELLED", "ARCHIVED"), nullable=False, default="ACTIVE"
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    employee: Mapped["Employee"] = relationship("Employee", back_populates="trainings")
    skill: Mapped["Skill"] = relationship("Skill", back_populates="trainings")


# ---------------------------------------------------------------------------
# 10. GapAnalysis
# ---------------------------------------------------------------------------

class GapAnalysis(Base):
    __tablename__ = "gap_analysis"

    gap_analysis_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    analysis_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    demand_id: Mapped[Optional[str]] = mapped_column(
        String(60), ForeignKey("demand_plan.demand_id", onupdate="CASCADE", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        String(30), ForeignKey("project.project_id", onupdate="CASCADE", ondelete="SET NULL"), nullable=True
    )
    role_id: Mapped[Optional[str]] = mapped_column(
        String(16), ForeignKey("role.role_id", onupdate="CASCADE", ondelete="SET NULL"), nullable=True
    )
    skill_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("skill.skill_id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    required_headcount: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    available_headcount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # shortage_headcount — GENERATED ALWAYS (STORED); read-only via ORM
    shortage_headcount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    required_proficiency_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    avg_current_proficiency_level: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2), nullable=True)
    gap_severity: Mapped[str] = mapped_column(
        Enum("NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"), nullable=False, default="MEDIUM"
    )
    recommended_action: Mapped[str] = mapped_column(
        Enum("HIRE_EXTERNAL", "UPSKILL_INTERNAL", "REASSIGN_BENCH", "ENGAGE_CONTRACTOR", "CROSS_TRAIN", "NO_ACTION"),
        nullable=False,
        default="UPSKILL_INTERNAL",
    )
    status: Mapped[str] = mapped_column(
        Enum("OPEN", "IN_REVIEW", "ACTION_PLANNED", "MITIGATED", "CLOSED"),
        nullable=False,
        default="OPEN",
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    demand: Mapped[Optional["DemandPlan"]] = relationship("DemandPlan", back_populates="gap_analyses")
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="gap_analyses")
    role: Mapped[Optional["Role"]] = relationship("Role", back_populates="gap_analyses")
    skill: Mapped["Skill"] = relationship("Skill", back_populates="gap_analyses")


# ---------------------------------------------------------------------------
# 11. LeaveEvent (Supporting Entity)
# ---------------------------------------------------------------------------

class LeaveEvent(Base):
    __tablename__ = "leave_event"

    leave_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("employee.employee_id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    leave_type: Mapped[str] = mapped_column(
        Enum("ANNUAL", "SICK", "PARENTAL", "UNPAID", "BEREAVEMENT"), nullable=False, default="ANNUAL"
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    leave_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("8.00"))
    approval_status: Mapped[str] = mapped_column(
        Enum("PENDING", "APPROVED", "REJECTED", "CANCELLED"), nullable=False, default="PENDING"
    )
    approver_id: Mapped[Optional[str]] = mapped_column(
        String(20), ForeignKey("employee.employee_id", onupdate="CASCADE", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    employee: Mapped["Employee"] = relationship(
        "Employee", foreign_keys=[employee_id], back_populates="leave_events"
    )
    approver: Mapped[Optional["Employee"]] = relationship(
        "Employee", foreign_keys=[approver_id]
    )


# ---------------------------------------------------------------------------
# 12. HistoricalEventLog (Supporting Entity - Immutable Audit Trail)
# ---------------------------------------------------------------------------

class HistoricalEventLog(Base):
    __tablename__ = "historical_event_log"

    event_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    entity_type: Mapped[str] = mapped_column(
        Enum("EMPLOYEE", "ROLE", "SKILL", "EMPLOYEE_SKILL", "PROJECT", "DEMAND_PLAN", "ALLOCATION", "AVAILABILITY", "TRAINING", "GAP_ANALYSIS", "LEAVE_EVENT"),
        nullable=False,
    )
    entity_id: Mapped[str] = mapped_column(String(60), nullable=False)
    event_type: Mapped[str] = mapped_column(
        Enum("CREATED", "STATUS_CHANGE", "ALLOCATED", "DEALLOCATED", "SKILL_UPGRADE", "CAPACITY_CHANGE", "DEMAND_CHANGE", "GAP_IDENTIFIED", "TRAINING_ENROLLED", "TRAINING_COMPLETED", "RECORD_SUPERSEDED", "LEAVE_REQUESTED", "LEAVE_APPROVED", "LEAVE_REJECTED"),
        nullable=False,
    )
    old_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    performed_by: Mapped[str] = mapped_column(String(100), nullable=False, default="SYSTEM")
    event_timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
