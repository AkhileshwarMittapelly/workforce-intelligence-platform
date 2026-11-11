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
