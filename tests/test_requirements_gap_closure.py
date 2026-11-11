"""
Requirements Gap Closure Test Suite.

Validates:
1. Phase 1: Comprehensive data validation service (13 rules, reports, zero unhandled errors).
2. Phase 2: Weekly capacity reconciliation with unclamped over-allocation detection.
3. Phase 3: Composite demand duplicate detection, exception reporting, and corrected forecasts.
4. Phase 4: Recommendation explainability (all 13 fields, decision status PROPOSED).
5. Phase 5: Ground-truth isolation (detect_anomalies runs independently).
6. Phase 7: Forecast accuracy metrics (MAE, RMSE, WAPE, Bias).
7. Phase 8: Explicit lifecycle audit events across all six core domains.
"""

import json
from pathlib import Path
import pandas as pd
import pytest

from src.services.validation_service import DataValidationService, run_data_validation
from src.services.capacity_service import calculate_capacity, reconcile_weekly_capacities_df
from src.services.forecast_service import detect_demand_duplicates, forecast_comparison, evaluate_forecast_accuracy
from src.services.gap_service import analyze_gaps_csv
from src.services.anomaly_service import detect_anomalies

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_data_validation_service_execution():
    """Phase 1: Validation service executes all 13 checks and exports report artifacts."""
    report = run_data_validation(data_dir=DATA_DIR)
    assert report.error_count == 0, f"Expected 0 errors, got: {report.errors}"
    assert report.total_checks >= 13
    assert report.status in ("PASSED", "PASSED_WITH_WARNINGS")

    # Artifact files must exist
    assert (DATA_DIR / "validation_summary.json").exists()
    assert (DATA_DIR / "validation_report.json").exists()
    assert (DATA_DIR / "validation_errors.csv").exists()

    with open(DATA_DIR / "validation_report.json", "r", encoding="utf-8") as f:
        rep_json = json.load(f)
    assert rep_json["status"] == report.status
    assert rep_json["intentional_anomaly_count"] >= 1


def test_weekly_capacity_reconciliation_engine():
    """Phase 2: Source-driven weekly capacity reconciliation calculates unclamped balances."""
    df = reconcile_weekly_capacities_df(data_dir=DATA_DIR)
    assert not df.empty, "Reconciliation DataFrame should not be empty"

    required_cols = [
        "employee_id", "period_start", "period_end", "fte",
        "contracted_hours", "approved_leave_hours", "net_capacity_hours",
        "allocated_hours", "remaining_capacity_hours", "utilization_percentage",
        "over_allocation_percentage", "capacity_status"
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing column {col} in reconciliation"

    # Math consistency check on every row
    for _, row in df.iterrows():
        expected_net = round(row["contracted_hours"] - row["approved_leave_hours"], 2)
        assert round(row["net_capacity_hours"], 2) == expected_net
        expected_rem = round(row["net_capacity_hours"] - row["allocated_hours"], 2)
        assert round(row["remaining_capacity_hours"], 2) == expected_rem


def test_demand_duplicate_exception_and_corrected_forecast():
    """Phase 3: Composite duplicate detection produces exception report and corrected forecast."""
    dup_df = detect_demand_duplicates(data_dir=DATA_DIR)
    assert not dup_df.empty, "Injected duplicate demand should be detected"

    expected_cols = [
        "original_demand_id", "duplicate_demand_id", "duplicate_classification",
        "original_fte", "duplicate_fte", "potential_double_counted_fte",
        "detection_timestamp", "resolution_status"
    ]
    for col in expected_cols:
        assert col in dup_df.columns, f"Missing column {col} in duplicate exceptions"

    # Verify forecast comparison removes double-counted FTE
    comparison = forecast_comparison(data_dir=DATA_DIR)
    assert comparison["original_total_demand_fte"] > comparison["corrected_total_demand_fte"]
    assert comparison["double_counted_fte_delta"] > 0


def test_recommendation_explainability_all_fields():
    """Phase 4: Gap recommendations include all 13 explainability attributes and decision status."""
    recs = analyze_gaps_csv()
    assert len(recs) > 0, "Recommendations should not be empty"

    for r in recs:
        # Check all 13 required fields
        assert hasattr(r, "demand_quantity")
        assert hasattr(r, "qualified_internal_supply")
        assert hasattr(r, "available_bench_supply")
        assert hasattr(r, "skill_proficiency_requirement")
        assert hasattr(r, "current_verified_proficiency")
        assert hasattr(r, "skill_freshness")
        assert hasattr(r, "training_lead_time")
        assert hasattr(r, "project_deadline")
        assert hasattr(r, "capacity_shortage")
        assert hasattr(r, "utilization_risk")
        assert hasattr(r, "chosen_recommendation")
        assert hasattr(r, "reasoning")
        assert hasattr(r, "assumptions")

        # Must not be auto-approved
        assert r.decision_status == "PROPOSED"
        assert r.chosen_recommendation in [
            "HIRE_EXTERNAL", "UPSKILL_INTERNAL", "REASSIGN_BENCH",
            "ENGAGE_CONTRACTOR", "CROSS_TRAIN", "NO_ACTION"
        ]


def test_ground_truth_isolation_independent_detection():
    """Phase 5: Anomaly detection operates independently without loading ground truth."""
    det_df = detect_anomalies(data_dir=DATA_DIR)
    assert not det_df.empty, "Anomaly detection should detect issues without ground truth"
    # Anomaly service output does not include ground truth labels in its detection routine
    assert "ground_truth" not in det_df.columns


def test_forecast_accuracy_holdout_evaluation():
    """Phase 7: Separate forecast accuracy metrics (MAE, RMSE, WAPE, Bias)."""
    metrics = evaluate_forecast_accuracy(data_dir=DATA_DIR)
    assert metrics["status"] == "EVALUATED"
    assert "mae" in metrics and metrics["mae"] >= 0.0
    assert "rmse" in metrics and metrics["rmse"] >= 0.0
    assert "wape_pct" in metrics
    assert "forecast_bias_pct" in metrics
    assert "assumptions" in metrics
    assert (DATA_DIR / "forecast_accuracy_metrics.json").exists()


def test_lifecycle_audit_events_coverage():
    """Phase 8: Verify explicit historical event log records state changes across all core entities."""
    evt_file = DATA_DIR / "historical_event_log.csv"
    assert evt_file.exists()
    df = pd.read_csv(evt_file)

    event_types = set(df["event_type"].dropna().unique())
    # Required lifecycle event transitions
    expected_event_types = {
        "CREATED",
        "ROLE_CHANGE",
        "SKILL_VERIFICATION",
        "STATUS_TRANSITION",
        "ALLOCATION_CONFIRMED",
        "ALLOCATION_RELEASED",
        "LEAVE_REQUESTED",
        "LEAVE_APPROVED",
        "GAP_IDENTIFIED",
        "RECOMMENDATION_DECISION",
        "TRAINING_ENROLLED",
        "TRAINING_COMPLETED",
    }
    for et in expected_event_types:
        assert et in event_types, f"Missing lifecycle event type: {et}"
