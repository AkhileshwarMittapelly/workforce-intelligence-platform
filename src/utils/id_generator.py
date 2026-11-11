"""
Deterministic ID generator utility enforcing schema prefix and format rules.

Supported Conventions:
- Employee:     EMP-000001 (6 digits)
- Skill:        SKL-000001 (6 digits)
- Project:      PRJ-2026-000001 (PRJ-YYYY-XXXXXX)
- Demand:       DEM-<project-id>-2026W01 (e.g. DEM-PRJ-2026-000001-2026W01)
- Allocation:   ALLOC-2026-000001 (ALLOC-YYYY-XXXXXX)
- Role:         ROL-0001 (4 digits)
- EmployeeSkill:ESK-000001 (6 digits)
- Availability: AVL-00001 (5 digits)
- Training:     TRN-00001 (5 digits)
- GapAnalysis:  GAP-00001 (5 digits)
- EventLog:     EVT-00000001 (8 digits)
"""

from enum import Enum


class EntityPrefix(str, Enum):
    ROLE = "ROL"
    EMPLOYEE = "EMP"
    SKILL = "SKL"
    EMPLOYEE_SKILL = "ESK"
    PROJECT = "PRJ"
    DEMAND_PLAN = "DEM"
    ALLOCATION = "ALLOC"
    AVAILABILITY = "AVL"
    TRAINING = "TRN"
    GAP_ANALYSIS = "GAP"
    LEAVE_EVENT = "LEV"
    HISTORICAL_EVENT = "EVT"


ID_REGEX_PATTERNS: dict[EntityPrefix, str] = {
    EntityPrefix.ROLE: r"^ROL-[0-9]{4}$",
    EntityPrefix.EMPLOYEE: r"^EMP-[0-9]{6}$",
    EntityPrefix.SKILL: r"^SKL-[0-9]{6}$",
    EntityPrefix.EMPLOYEE_SKILL: r"^ESK-[0-9]{6}$",
    EntityPrefix.PROJECT: r"^PRJ-[0-9]{4}-[0-9]{6}$",
    EntityPrefix.DEMAND_PLAN: r"^DEM-PRJ-[0-9]{4}-[0-9]{6}-[0-9]{4}W(0[1-9]|[1-4][0-9]|5[0-3])(-[0-9]{2})?$",
    EntityPrefix.ALLOCATION: r"^ALLOC-[0-9]{4}-[0-9]{6}$",
    EntityPrefix.AVAILABILITY: r"^AVL-[0-9]{5}$",
    EntityPrefix.TRAINING: r"^TRN-[0-9]{5}$",
    EntityPrefix.GAP_ANALYSIS: r"^GAP-[0-9]{5}$",
    EntityPrefix.LEAVE_EVENT: r"^LEV-[0-9]{5}$",
    EntityPrefix.HISTORICAL_EVENT: r"^EVT-[0-9]{8}$",
}


def generate_employee_id(sequence_num: int) -> str:
    """Formats an employee ID: EMP-000001 (6 digits)."""
    return f"{EntityPrefix.EMPLOYEE.value}-{str(sequence_num).zfill(6)}"


def generate_skill_id(sequence_num: int) -> str:
    """Formats a skill ID: SKL-000001 (6 digits)."""
    return f"{EntityPrefix.SKILL.value}-{str(sequence_num).zfill(6)}"


def generate_project_id(year: int, sequence_num: int) -> str:
    """Formats a project ID: PRJ-2026-000001 (PRJ-YYYY-XXXXXX)."""
    return f"{EntityPrefix.PROJECT.value}-{year}-{str(sequence_num).zfill(6)}"


def generate_demand_id(project_id: str, year: int, week: int, sequence_num: int | None = None) -> str:
    """
    Formats a demand plan ID: DEM-<project-id>-YYYY'W'WW[-SS]
    Example: DEM-PRJ-2026-000001-2026W01
    """
    week_str = f"{year}W{str(week).zfill(2)}"
    base = f"{EntityPrefix.DEMAND_PLAN.value}-{project_id}-{week_str}"
    if sequence_num is not None:
        return f"{base}-{str(sequence_num).zfill(2)}"
    return base


def generate_allocation_id(year: int, sequence_num: int) -> str:
    """Formats an allocation ID: ALLOC-2026-000001 (ALLOC-YYYY-XXXXXX)."""
    return f"{EntityPrefix.ALLOCATION.value}-{year}-{str(sequence_num).zfill(6)}"


def generate_leave_id(sequence_num: int) -> str:
    """Formats a leave event ID: LEV-00001 (5 digits)."""
    return f"{EntityPrefix.LEAVE_EVENT.value}-{str(sequence_num).zfill(5)}"


def format_deterministic_id(
    entity: EntityPrefix,
    sequence_num: int,
    year: int = 2026,
    project_id: str | None = None,
    week: int = 1,
) -> str:
    """
    Universal dispatcher for deterministic ID generation compliant with MySQL CHECK constraints.
    """
    if entity == EntityPrefix.EMPLOYEE:
        return generate_employee_id(sequence_num)
    elif entity == EntityPrefix.SKILL:
        return generate_skill_id(sequence_num)
    elif entity == EntityPrefix.PROJECT:
        return generate_project_id(year, sequence_num)
    elif entity == EntityPrefix.DEMAND_PLAN:
        proj = project_id or generate_project_id(year, 1)
        return generate_demand_id(proj, year, week, sequence_num if sequence_num > 1 else None)
    elif entity == EntityPrefix.ALLOCATION:
        return generate_allocation_id(year, sequence_num)
    elif entity == EntityPrefix.ROLE:
        return f"{EntityPrefix.ROLE.value}-{str(sequence_num).zfill(4)}"
    elif entity == EntityPrefix.EMPLOYEE_SKILL:
        return f"{EntityPrefix.EMPLOYEE_SKILL.value}-{str(sequence_num).zfill(6)}"
    elif entity == EntityPrefix.AVAILABILITY:
        return f"{EntityPrefix.AVAILABILITY.value}-{str(sequence_num).zfill(5)}"
    elif entity == EntityPrefix.TRAINING:
        return f"{EntityPrefix.TRAINING.value}-{str(sequence_num).zfill(5)}"
    elif entity == EntityPrefix.GAP_ANALYSIS:
        return f"{EntityPrefix.GAP_ANALYSIS.value}-{str(sequence_num).zfill(5)}"
    elif entity == EntityPrefix.LEAVE_EVENT:
        return generate_leave_id(sequence_num)
    elif entity == EntityPrefix.HISTORICAL_EVENT:
        return f"{EntityPrefix.HISTORICAL_EVENT.value}-{str(sequence_num).zfill(8)}"
    else:
        raise ValueError(f"Unsupported entity prefix: {entity}")
