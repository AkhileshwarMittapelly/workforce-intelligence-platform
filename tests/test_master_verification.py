"""
Master Verification & Audit Test Suite.

Validates:
1. LeaveEvent entity schema and relational integrity.
2. HistoricalEventLog entity schema and JSON diffs.
3. Anomaly detection model Precision, Recall, and F1-score (100% benchmark).
4. Deterministic reproducibility across two independent runs.
5. 300+ unique skills taxonomy integrity.
"""

import json
from pathlib import Path
import re
import tempfile
import pandas as pd
import pytest

from src.generators.synthetic_data_generator import SyntheticDataGenerator, SKILL_POOL
from src.services.anomaly_service import detect_anomalies, evaluate_anomalies
from src.utils.id_generator import EntityPrefix, ID_REGEX_PATTERNS

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_leave_events_integrity():
    """Verify leave_events.csv schema, foreign keys, and constraints."""
    leave_file = DATA_DIR / "leave_events.csv"
    assert leave_file.exists(), "leave_events.csv must exist"
    
    df = pd.read_csv(leave_file)
    expected_cols = [
        "leave_id", "employee_id", "leave_type", "start_date",
        "end_date", "leave_hours", "approval_status", "approver_id", "reason"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing column {col} in leave_events"

    # ID format validation
    for lid in df["leave_id"]:
        assert re.match(ID_REGEX_PATTERNS[EntityPrefix.LEAVE_EVENT], lid), f"Invalid leave ID {lid}"

    # Foreign key validation
    emp_df = pd.read_csv(DATA_DIR / "employees.csv")
    valid_emps = set(emp_df["employee_id"])
    for eid in df["employee_id"]:
        assert eid in valid_emps, f"Foreign key error: {eid} not in employees.csv"

    # Leave hours must be positive and within reasonable bounds
    assert (df["leave_hours"] > 0).all()
    assert (df["leave_hours"] <= 40.0).all()


def test_historical_event_log_integrity():
    """Verify historical_event_log.csv schema, JSON diffs, and audit trail."""
    evt_file = DATA_DIR / "historical_event_log.csv"
    assert evt_file.exists(), "historical_event_log.csv must exist"

    df = pd.read_csv(evt_file)
    expected_cols = [
        "event_id", "event_timestamp", "entity_type", "entity_id",
        "event_type", "performed_by", "old_state", "new_state"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing column {col} in historical_event_log"

    assert len(df) > 0, "Historical event log should not be empty"

    # Verify JSON validity in old_state and new_state (skip NaN rows)
    for _, row in df.head(50).iterrows():
        if pd.notna(row["old_state"]):
            old_val = json.loads(row["old_state"])
            assert isinstance(old_val, dict)
        if pd.notna(row["new_state"]):
            new_val = json.loads(row["new_state"])
            assert isinstance(new_val, dict)


def test_anomaly_detection_benchmark_100_percent():
    """Verify anomaly detection service achieves 100% precision and recall on ground truth."""
    det_df = detect_anomalies(data_dir=DATA_DIR)
    eval_res = evaluate_anomalies(detected_df=det_df, data_dir=DATA_DIR)

    assert eval_res["status"] == "EVALUATED"
    assert eval_res["total_ground_truth"] == 4
    assert eval_res["total_detected"] == 4
    assert eval_res["true_positives"] == 4
    assert eval_res["false_positives"] == 0
    assert eval_res["false_negatives"] == 0

    assert eval_res["overall_precision"] == 1.0
    assert eval_res["overall_recall"] == 1.0
    assert eval_res["overall_f1"] == 1.0

    # Test all 4 individual categories
    for ec in ["EC-1", "EC-2", "EC-3", "EC-4"]:
        cat = eval_res["categories"][ec]
        assert cat["precision"] == 1.0, f"Precision failure in {ec}"
        assert cat["recall"] == 1.0, f"Recall failure in {ec}"
        assert cat["f1_score"] == 1.0, f"F1 failure in {ec}"


def test_unique_skills_pool():
    """Verify the skill pool has at least 300 unique skills across 8 categories."""
    assert len(SKILL_POOL) >= 300
    names = [s[0] for s in SKILL_POOL]
    assert len(names) == len(set(names)), "Skill names must be strictly unique"
    
    categories = {s[1] for s in SKILL_POOL}
    assert len(categories) == 8, "Must cover all 8 skill categories"

    # Full scale config must specify 300 skills
    assert SyntheticDataGenerator.SCALE_PARAMS["full"]["n_skills"] == 300


def test_deterministic_reproducibility():
    """Verify running the generator twice with identical seeds yields identical SHA-256."""
    seed = 20261022
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        gen1 = SyntheticDataGenerator(scale="starter", seed=seed, output_dir=tmp1)
        gen1.generate()
        gen1.export()
        chk1 = gen1.checksum()

        gen2 = SyntheticDataGenerator(scale="starter", seed=seed, output_dir=tmp2)
        gen2.generate()
        gen2.export()
        chk2 = gen2.checksum()

        assert chk1 == chk2, f"Checksum mismatch between identical runs: {chk1} != {chk2}"


def test_demand_coverage_53_iso_weeks():
    """Verify all 53 ISO weeks for 2026 are covered, demand IDs match ISO week, and fall within project bounds."""
    dp_file = DATA_DIR / "demand_plans.csv"
    prj_file = DATA_DIR / "projects.csv"
    assert dp_file.exists() and prj_file.exists()

    dp_df = pd.read_csv(dp_file)
    prj_df = pd.read_csv(prj_file)

    # 1. All 53 ISO weeks must be present in demand (derived from start_date)
    iso_weeks_present = set(pd.to_datetime(dp_df["start_date"]).dt.isocalendar().week)
    assert len(iso_weeks_present) == 53, f"Expected 53 weeks, got {len(iso_weeks_present)}"
    assert set(range(1, 54)) == iso_weeks_present

    # 2. Demand plan ID format matches year and week (except injected duplicate -99)
    for _, row in dp_df.iterrows():
        did = str(row["demand_id"])
        dt = pd.to_datetime(row["start_date"])
        iso_wk = dt.isocalendar().week
        iso_yr = dt.isocalendar().year
        if did.endswith("-99"):
            continue
        # Expected e.g. DEM-PRJ-2026-000001-2026W23
        expected_tag = f"{iso_yr}W{iso_wk:02d}"
        assert expected_tag in did, f"Demand ID {did} does not match expected week tag {expected_tag}"

    # 3. Project date coverage
    prj_dates = prj_df.set_index("project_id")[["start_date", "end_date"]].to_dict(orient="index")
    for _, row in dp_df.iterrows():
        pid = row["project_id"]
        if pid in prj_dates:
            p_s = str(prj_dates[pid]["start_date"])
            p_e = str(prj_dates[pid]["end_date"])
            d_s = str(row["start_date"])
            d_e = str(row["end_date"])
            assert d_s >= p_s, f"Demand starts before project: {d_s} < {p_s}"
            assert d_e <= p_e, f"Demand ends after project: {d_e} > {p_e}"


def test_anomaly_detection_false_positives_and_edge_cases():
    """Test anomaly detection handles sequential allocations (no false positive), multiple overlaps, and empty/NaN data."""
    from src.services.anomaly_service import _detect_ec1_over_allocated, _detect_ec4_overlapping_assignments

    # 1. Sequential non-overlapping allocations: 60% Jan-Feb, 60% Mar-Apr (Sum=120% lifetime, but max concurrent=60%)
    seq_allocs = pd.DataFrame([
        {
            "allocation_id": "ALLOC-TEST-001",
            "employee_id": "EMP-TEST-001",
            "project_id": "PRJ-001",
            "start_date": "2026-01-01",
            "end_date": "2026-02-28",
            "allocation_percentage": 60,
        },
        {
            "allocation_id": "ALLOC-TEST-002",
            "employee_id": "EMP-TEST-001",
            "project_id": "PRJ-002",
            "start_date": "2026-03-01",
            "end_date": "2026-04-30",
            "allocation_percentage": 60,
        },
    ])
    ec1_anomalies = _detect_ec1_over_allocated(seq_allocs)
    assert len(ec1_anomalies) == 0, "Sequential non-overlapping allocations must NOT trigger EC-1 false positive"

    # 2. Overlapping concurrent allocations: 60% Jan-Mar, 60% Feb-Apr (Concurrent in Feb-Mar = 120%)
    concurrent_allocs = pd.DataFrame([
        {
            "allocation_id": "ALLOC-TEST-003",
            "employee_id": "EMP-TEST-002",
            "project_id": "PRJ-001",
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "allocation_percentage": 60,
        },
        {
            "allocation_id": "ALLOC-TEST-004",
            "employee_id": "EMP-TEST-002",
            "project_id": "PRJ-002",
            "start_date": "2026-02-01",
            "end_date": "2026-04-30",
            "allocation_percentage": 60,
        },
    ])
    ec1_detected = _detect_ec1_over_allocated(concurrent_allocs)
    assert len(ec1_detected) == 1, "Concurrent allocations exceeding 100% must trigger EC-1"

    # 3. Multiple overlaps: 1 long allocation spanning Jan-Jun overlapping two different allocations (Feb and May)
    multi_overlap_allocs = pd.DataFrame([
        {
            "allocation_id": "ALLOC-LONG",
            "employee_id": "EMP-TEST-003",
            "project_id": "PRJ-001",
            "start_date": "2026-01-01",
            "end_date": "2026-06-30",
            "allocation_percentage": 40,
        },
        {
            "allocation_id": "ALLOC-SHORT-1",
            "employee_id": "EMP-TEST-003",
            "project_id": "PRJ-002",
            "start_date": "2026-02-01",
            "end_date": "2026-02-28",
            "allocation_percentage": 40,
        },
        {
            "allocation_id": "ALLOC-SHORT-2",
            "employee_id": "EMP-TEST-003",
            "project_id": "PRJ-003",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "allocation_percentage": 40,
        },
    ])
    ec4_detected = _detect_ec4_overlapping_assignments(multi_overlap_allocs)
    # ALLOC-LONG overlaps ALLOC-SHORT-1 AND ALLOC-LONG overlaps ALLOC-SHORT-2 => 2 anomaly records
    assert len(ec4_detected) == 2, f"Expected 2 overlapping pair conflicts, got {len(ec4_detected)}"

    # 4. Graceful handling of empty and NaN dates
    empty_df = pd.DataFrame()
    assert _detect_ec1_over_allocated(empty_df) == []
    assert _detect_ec4_overlapping_assignments(empty_df) == []

    nan_dates_df = pd.DataFrame([
        {
            "allocation_id": "ALLOC-NAN-1",
            "employee_id": "EMP-TEST-004",
            "project_id": "PRJ-001",
            "start_date": None,
            "end_date": None,
            "allocation_percentage": 50,
        },
        {
            "allocation_id": "ALLOC-NAN-2",
            "employee_id": "EMP-TEST-004",
            "project_id": "PRJ-002",
            "start_date": None,
            "end_date": None,
            "allocation_percentage": 50,
        },
    ])
    assert _detect_ec4_overlapping_assignments(nan_dates_df) == []


def test_period_specific_forecasting_with_leave_and_overlap():
    """Test period-specific supply calculation, leave deductions, and multi-demand capacity tracking."""
    from src.services.forecast_service import _compute_forecasts

    emp_df = pd.DataFrame([
        {"employee_id": "EMP-001", "fte": 1.0, "status": "ACTIVE"},
        {"employee_id": "EMP-002", "fte": 1.0, "status": "ACTIVE"},
    ])
    skills_df = pd.DataFrame([
        {"employee_id": "EMP-001", "skill_id": "SKL-001", "proficiency_level": 4, "last_evaluated_date": "2026-10-01"},
        {"employee_id": "EMP-002", "skill_id": "SKL-001", "proficiency_level": 4, "last_evaluated_date": "2026-10-01"},
    ])
    # EMP-001 is allocated 0.5 FTE during 2026-W05
    alloc_df = pd.DataFrame([
        {
            "allocation_id": "AL-1",
            "employee_id": "EMP-001",
            "start_date": "2026-01-26",
            "end_date": "2026-02-08",
            "allocation_percentage": 50,
        }
    ])
    # EMP-002 has 40 hours approved leave during 2026-W05 (100% capacity reduction)
    leave_df = pd.DataFrame([
        {
            "leave_id": "LV-1",
            "employee_id": "EMP-002",
            "start_date": "2026-01-26",
            "end_date": "2026-02-01",
            "leave_hours": 40.0,
            "approval_status": "APPROVED",
        }
    ])
    # Demand requires 1.0 FTE for SKL-001 in week 2026-W05
    demand_df = pd.DataFrame([
        {
            "demand_id": "DP-001",
            "required_skill_id": "SKL-001",
            "role_id": "ROL-001",
            "required_fte": 1.0,
            "min_proficiency_level": 3,
            "week_number": "2026-W05",
            "period_start": "2026-01-26",
            "period_end": "2026-02-01",
        }
    ])

    results = _compute_forecasts(
        demand_df=demand_df,
        employees_df=emp_df,
        employee_skills_df=skills_df,
        allocations_df=alloc_df,
        leave_events_df=leave_df,
        granularity="week",
    )

    assert len(results) == 1
    res = results[0]
    # EMP-001 has 1.0 - 0.5 = 0.5 FTE available
    # EMP-002 has 1.0 - 1.0 = 0.0 FTE available
    # Total supply = 0.5 FTE. Demand = 1.0 FTE. Gap = 0.5 FTE. Utilization = 200% -> capped at 150% -> CRITICAL
    assert res.supply_fte == 0.5
    assert res.demand_fte == 1.0
    assert res.gap_fte == 0.5
    assert res.risk_level == "CRITICAL"

