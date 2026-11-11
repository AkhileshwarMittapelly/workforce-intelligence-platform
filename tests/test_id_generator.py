"""
Unit tests for deterministic ID generator verifying compliance with schema regex rules.
"""

import re
import pytest
from src.utils.id_generator import (
    EntityPrefix,
    ID_REGEX_PATTERNS,
    format_deterministic_id,
    generate_employee_id,
    generate_skill_id,
    generate_project_id,
    generate_demand_id,
    generate_allocation_id,
)


def test_employee_id_convention():
    """Validates Employee: EMP-000001 (6 digits)."""
    emp_id = generate_employee_id(1)
    assert emp_id == "EMP-000001"
    assert re.match(ID_REGEX_PATTERNS[EntityPrefix.EMPLOYEE], emp_id)

    emp_id_large = generate_employee_id(45291)
    assert emp_id_large == "EMP-045291"
    assert re.match(ID_REGEX_PATTERNS[EntityPrefix.EMPLOYEE], emp_id_large)


def test_skill_id_convention():
    """Validates Skill: SKL-000001 (6 digits)."""
    skill_id = generate_skill_id(1)
    assert skill_id == "SKL-000001"
    assert re.match(ID_REGEX_PATTERNS[EntityPrefix.SKILL], skill_id)

    skill_id_large = generate_skill_id(120)
    assert skill_id_large == "SKL-000120"
    assert re.match(ID_REGEX_PATTERNS[EntityPrefix.SKILL], skill_id_large)


def test_project_id_convention():
    """Validates Project: PRJ-2026-000001 (PRJ-YYYY-XXXXXX)."""
    prj_id = generate_project_id(2026, 1)
    assert prj_id == "PRJ-2026-000001"
    assert re.match(ID_REGEX_PATTERNS[EntityPrefix.PROJECT], prj_id)

    prj_id_future = generate_project_id(2027, 45)
    assert prj_id_future == "PRJ-2027-000045"
    assert re.match(ID_REGEX_PATTERNS[EntityPrefix.PROJECT], prj_id_future)


def test_demand_id_convention():
    """Validates Demand: DEM-<project-id>-2026W01 (e.g., DEM-PRJ-2026-000001-2026W01)."""
    prj_id = "PRJ-2026-000001"
    demand_id = generate_demand_id(prj_id, 2026, 1)
    assert demand_id == "DEM-PRJ-2026-000001-2026W01"
    assert re.match(ID_REGEX_PATTERNS[EntityPrefix.DEMAND_PLAN], demand_id)

    # With disambiguation sequence suffix
    demand_id_seq = generate_demand_id(prj_id, 2026, 12, sequence_num=2)
    assert demand_id_seq == "DEM-PRJ-2026-000001-2026W12-02"
    assert re.match(ID_REGEX_PATTERNS[EntityPrefix.DEMAND_PLAN], demand_id_seq)


def test_allocation_id_convention():
    """Validates Allocation: ALLOC-2026-000001 (ALLOC-YYYY-XXXXXX)."""
    alloc_id = generate_allocation_id(2026, 1)
    assert alloc_id == "ALLOC-2026-000001"
    assert re.match(ID_REGEX_PATTERNS[EntityPrefix.ALLOCATION], alloc_id)

    alloc_id_large = generate_allocation_id(2026, 789)
    assert alloc_id_large == "ALLOC-2026-000789"
    assert re.match(ID_REGEX_PATTERNS[EntityPrefix.ALLOCATION], alloc_id_large)


@pytest.mark.parametrize(
    "entity,seq,expected_pattern",
    [
        (EntityPrefix.ROLE, 1, r"^ROL-[0-9]{4}$"),
        (EntityPrefix.EMPLOYEE, 1, r"^EMP-[0-9]{6}$"),
        (EntityPrefix.SKILL, 1, r"^SKL-[0-9]{6}$"),
        (EntityPrefix.EMPLOYEE_SKILL, 1, r"^ESK-[0-9]{6}$"),
        (EntityPrefix.PROJECT, 1, r"^PRJ-[0-9]{4}-[0-9]{6}$"),
        (EntityPrefix.DEMAND_PLAN, 1, r"^DEM-PRJ-[0-9]{4}-[0-9]{6}-[0-9]{4}W(0[1-9]|[1-4][0-9]|5[0-3])(-[0-9]{2})?$"),
        (EntityPrefix.ALLOCATION, 1, r"^ALLOC-[0-9]{4}-[0-9]{6}$"),
        (EntityPrefix.AVAILABILITY, 1, r"^AVL-[0-9]{5}$"),
        (EntityPrefix.TRAINING, 1, r"^TRN-[0-9]{5}$"),
        (EntityPrefix.GAP_ANALYSIS, 1, r"^GAP-[0-9]{5}$"),
        (EntityPrefix.HISTORICAL_EVENT, 1, r"^EVT-[0-9]{8}$"),
    ],
)
def test_all_deterministic_id_formats(entity, seq, expected_pattern):
    generated_id = format_deterministic_id(entity, seq)
    assert re.match(expected_pattern, generated_id), f"{generated_id} does not match {expected_pattern}"
