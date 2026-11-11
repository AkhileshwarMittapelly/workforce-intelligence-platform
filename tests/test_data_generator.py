"""
Unit and integration tests for Synthetic Data Generator and Ground Truth validation.
"""

import json
from pathlib import Path
import pandas as pd
import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_starter_data_files_exist():
    """Validates that all required core entities are exported as CSV."""
    expected_files = [
        "roles.csv",
        "employees.csv",
        "skills.csv",
        "employee_skills.csv",
        "projects.csv",
        "demand_plans.csv",
        "allocations.csv",
        "availability.csv",
        "training.csv",
        "gap_analysis.csv",
        "ground_truth.csv",
        "ground_truth.json",
    ]
    for fname in expected_files:
        path = DATA_DIR / fname
        assert path.exists(), f"Missing required dataset: {fname}"


def test_ground_truth_anomalies_present():
    """Validates that all 4 required edge cases are captured in ground truth."""
    gt_json = DATA_DIR / "ground_truth.json"
    assert gt_json.exists()
    
    with open(gt_json, "r", encoding="utf-8") as f:
        records = json.load(f)

    issue_types = {r.get("issue_type") for r in records}
    
    # 4 required edge cases:
    # 1. Allocation exceeds availability / OVER_ALLOCATED
    # 2. Skill proficiency stale but treated current / STALE_SKILL_ACTIVE
    # 3. Demand double-counted / DEMAND_DOUBLE_COUNTED
    # 4. Employee assigned to overlapping projects / OVERLAPPING_ALLOCATION
    assert "OVER_ALLOCATED" in issue_types or "ALLOCATION_EXCEEDS_AVAILABILITY" in issue_types
    assert "STALE_SKILL_ACTIVE" in issue_types
    assert "DEMAND_DOUBLE_COUNTED" in issue_types
    assert "OVERLAPPING_ALLOCATION" in issue_types


def test_foreign_key_integrity():
    """Verifies relational integrity between generated tables."""
    emp_df = pd.read_csv(DATA_DIR / "employees.csv")
    esk_df = pd.read_csv(DATA_DIR / "employee_skills.csv")
    alloc_df = pd.read_csv(DATA_DIR / "allocations.csv")

    valid_emp_ids = set(emp_df["employee_id"])

    # All employee_skills must link to a valid employee
    for eid in esk_df["employee_id"]:
        assert eid in valid_emp_ids, f"Foreign key violation: {eid} not in employees"

    # All allocations must link to a valid employee
    for eid in alloc_df["employee_id"]:
        assert eid in valid_emp_ids, f"Foreign key violation: {eid} not in employees"


def test_capacity_reconciliation():
    """Verifies that capacity arithmetic holds across availability records."""
    avail_df = pd.read_csv(DATA_DIR / "availability.csv")
    
    for _, row in avail_df.iterrows():
        base = row["base_capacity_hours"]
        fte = row["fte"]
        leave = row["approved_leave_hours"]
        allocated = row["allocated_hours"]
        net = row["net_available_hours"]

        expected_contracted = round(base * fte, 2)
        expected_net = max(0.0, round(expected_contracted - leave - allocated, 2))
        
        assert abs(net - expected_net) <= 0.05, f"Capacity discrepancy in {row['availability_id']}"
