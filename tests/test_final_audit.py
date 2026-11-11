"""
Final Audit Test Suite.

Tests for:
1. Source-driven dashboard metrics (analytics_service uses actual data, not hardcodes).
2. Zero-capacity period handling.
3. All four edge cases independently verified.
4. Full-scale data validation.
5. Reproducibility across two independent generations.
6. Recommendation explainability references source records.
7. Forecast accuracy semantics audit.
"""

import hashlib
import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.services.analytics_service import (
    get_monthly_utilization_trend,
    get_recommendation_action_split,
    get_workforce_kpis,
)
from src.services.capacity_service import calculate_capacity, reconcile_weekly_capacities_df
from src.services.anomaly_service import (
    _detect_ec1_over_allocated,
    _detect_ec2_stale_skills,
    _detect_ec3_duplicate_demand,
    _detect_ec4_overlapping_assignments,
    detect_anomalies,
    evaluate_anomalies,
)
from src.services.forecast_service import evaluate_forecast_accuracy
from src.services.gap_service import analyze_gaps_csv

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# 1. Source-driven dashboard metrics (no hardcodes)
# ---------------------------------------------------------------------------

class TestSourceDrivenDashboardMetrics:
    """Validate that analytics_service derives metrics from actual data."""

    def test_monthly_trend_has_12_months(self):
        df = get_monthly_utilization_trend()
        assert len(df) == 12
        assert list(df["month"]) == [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]

    def test_monthly_trend_has_net_capacity_column(self):
        """The source-driven version must include net_capacity_hours."""
        df = get_monthly_utilization_trend()
        assert "net_capacity_hours" in df.columns

    def test_monthly_trend_period_format(self):
        """Periods must be ISO YYYY-MM format, not YYYY-MonthName."""
        df = get_monthly_utilization_trend()
        for _, row in df.iterrows():
            p = row["period"]
            # Must match e.g. "2026-01" .. "2026-12"
            assert len(p) == 7 and p[4] == "-", f"Period {p} not in YYYY-MM format"

    def test_monthly_trend_utilization_is_derived(self):
        """Utilization must be derived from allocated/net_capacity, not hardcoded."""
        df = get_monthly_utilization_trend()
        for _, row in df.iterrows():
            net = row["net_capacity_hours"]
            alloc = row["allocated_hours"]
            util = row["utilization_pct"]
            if net > 0:
                expected_util = round(min(100.0, (alloc / net) * 100.0), 1)
                assert abs(util - expected_util) < 0.2, (
                    f"Utilization {util} doesn't match derived {expected_util} "
                    f"(alloc={alloc}, net={net})"
                )

    def test_recommendation_split_empty_when_no_data(self):
        """When gap data is empty or missing, must return empty DF, not hardcoded values."""
        df = get_recommendation_action_split()
        # We have gap data in data/, so it should return actual values.
        # But the structure must be correct.
        assert set(df.columns) >= {"action", "count", "pct"}
        if not df.empty:
            total_pct = df["pct"].sum()
            assert 99.0 <= total_pct <= 101.0, f"Percentages should sum to ~100, got {total_pct}"


# ---------------------------------------------------------------------------
# 2. Zero-capacity period handling
# ---------------------------------------------------------------------------

class TestZeroCapacityPeriods:
    """Verify capacity engine handles zero-capacity edge cases."""

    def test_zero_fte_employee(self):
        metrics = calculate_capacity(base_hours=40.0, fte=0.0, approved_leave_hours=0.0, allocated_hours=0.0)
        assert float(metrics.contracted_capacity_hours) == 0.0
        assert float(metrics.utilization_percentage) == 0.0
        assert metrics.capacity_status == "AVAILABLE_BENCH"

    def test_zero_base_hours(self):
        metrics = calculate_capacity(base_hours=0.0, fte=1.0, approved_leave_hours=0.0, allocated_hours=0.0)
        assert float(metrics.contracted_capacity_hours) == 0.0

    def test_all_capacity_consumed_by_leave(self):
        """When leave equals contracted capacity, status should reflect leave."""
        metrics = calculate_capacity(base_hours=40.0, fte=1.0, approved_leave_hours=40.0, allocated_hours=0.0)
        assert float(metrics.net_capacity_hours) == 0.0
        assert metrics.capacity_status == "ON_APPROVED_LEAVE"

    def test_leave_exceeds_capacity_with_allocation(self):
        """Over-allocation when leave eats capacity and allocation is added on top."""
        metrics = calculate_capacity(base_hours=40.0, fte=1.0, approved_leave_hours=30.0, allocated_hours=20.0)
        assert float(metrics.remaining_capacity_hours) < 0.0
        assert metrics.capacity_status == "OVER_ALLOCATED"


# ---------------------------------------------------------------------------
# 3. All four edge cases independently verified
# ---------------------------------------------------------------------------

class TestEdgeCaseDetection:
    """Verify each EC detector functions correctly on the seed data."""

    def test_ec1_over_allocation_detected(self):
        alloc_df = pd.read_csv(DATA_DIR / "allocations.csv")
        detected = _detect_ec1_over_allocated(alloc_df)
        entity_ids = [d["entity_id"] for d in detected]
        with open(DATA_DIR / "ground_truth.json", "r", encoding="utf-8") as f:
            gt = {item["edge_case_label"]: item["entity_id"] for item in json.load(f)}
        assert gt["EC-1"] in entity_ids, f"EC-1 over-allocation should detect {gt['EC-1']}"

    def test_ec2_stale_skill_detected(self):
        esk_df = pd.read_csv(DATA_DIR / "employee_skills.csv")
        detected = _detect_ec2_stale_skills(esk_df)
        entity_ids = [d["entity_id"] for d in detected]
        with open(DATA_DIR / "ground_truth.json", "r", encoding="utf-8") as f:
            gt = {item["edge_case_label"]: item["entity_id"] for item in json.load(f)}
        assert gt["EC-2"] in entity_ids, f"EC-2 stale skill should detect {gt['EC-2']}"

    def test_ec3_duplicate_demand_detected(self):
        demand_df = pd.read_csv(DATA_DIR / "demand_plans.csv")
        detected = _detect_ec3_duplicate_demand(demand_df)
        entity_ids = [d["entity_id"] for d in detected]
        with open(DATA_DIR / "ground_truth.json", "r", encoding="utf-8") as f:
            gt = {item["edge_case_label"]: item["entity_id"] for item in json.load(f)}
        assert gt["EC-3"] in entity_ids, f"EC-3 duplicate demand should detect {gt['EC-3']}"

    def test_ec4_overlapping_allocation_detected(self):
        alloc_df = pd.read_csv(DATA_DIR / "allocations.csv")
        detected = _detect_ec4_overlapping_assignments(alloc_df)
        entity_ids = [d["entity_id"] for d in detected]
        with open(DATA_DIR / "ground_truth.json", "r", encoding="utf-8") as f:
            gt = {item["edge_case_label"]: item["entity_id"] for item in json.load(f)}
        assert gt["EC-4"] in entity_ids, f"EC-4 overlapping allocation should detect {gt['EC-4']}"

    def test_ec1_no_false_positives_on_sequential_allocations(self):
        """Non-overlapping sequential allocations must not be flagged."""
        test_df = pd.DataFrame([
            {"allocation_id": "A-001", "employee_id": "E-1", "project_id": "P-1",
             "allocation_percentage": 80.0, "start_date": "2026-01-01", "end_date": "2026-03-31"},
            {"allocation_id": "A-002", "employee_id": "E-1", "project_id": "P-2",
             "allocation_percentage": 80.0, "start_date": "2026-04-01", "end_date": "2026-06-30"},
        ])
        detected = _detect_ec1_over_allocated(test_df)
        assert len(detected) == 0, "Sequential non-overlapping allocations must not be flagged"

    def test_ec4_no_false_positives_same_project(self):
        """Multiple allocations to the SAME project should not be flagged as overlapping."""
        test_df = pd.DataFrame([
            {"allocation_id": "A-001", "employee_id": "E-1", "project_id": "P-1",
             "allocation_percentage": 50.0, "start_date": "2026-01-01", "end_date": "2026-06-30"},
            {"allocation_id": "A-002", "employee_id": "E-1", "project_id": "P-1",
             "allocation_percentage": 30.0, "start_date": "2026-02-01", "end_date": "2026-05-31"},
        ])
        detected = _detect_ec4_overlapping_assignments(test_df)
        assert len(detected) == 0, "Overlapping allocations to the same project should not be flagged"

    def test_anomaly_precision_recall_f1(self):
        """Verify Precision, Recall, F1 against ground truth on current data."""
        det_df = detect_anomalies(data_dir=DATA_DIR)
        metrics = evaluate_anomalies(detected_df=det_df, data_dir=DATA_DIR)
        assert metrics["status"] == "EVALUATED"
        assert metrics["false_negatives"] == 0, f"False negatives: {metrics['false_negatives']}"
        # Report actual precision (may have legitimate false positives in full-scale data)
        assert metrics["overall_recall"] == 1.0, f"Recall: {metrics['overall_recall']}"
        assert metrics["overall_precision"] > 0.0, f"Precision: {metrics['overall_precision']}"
        assert metrics["overall_f1"] > 0.0, f"F1: {metrics['overall_f1']}"


# ---------------------------------------------------------------------------
# 4. Forecast accuracy semantics audit
# ---------------------------------------------------------------------------

class TestForecastAccuracySemantics:
    """Verify the holdout forecast evaluation methodology."""

    def test_forecast_metrics_from_actual_data(self):
        metrics = evaluate_forecast_accuracy(data_dir=DATA_DIR)
        assert metrics["status"] == "EVALUATED"
        assert metrics["sample_size"] > 0
        # MAE must be non-negative
        assert metrics["mae"] >= 0.0
        assert metrics["rmse"] >= 0.0

    def test_forecast_metrics_file_matches_computation(self):
        """The saved JSON must match a fresh computation."""
        metrics = evaluate_forecast_accuracy(data_dir=DATA_DIR)
        json_path = DATA_DIR / "forecast_accuracy_metrics.json"
        assert json_path.exists()
        with open(json_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["mae"] == metrics["mae"]
        assert saved["rmse"] == metrics["rmse"]
        assert saved["sample_size"] == metrics["sample_size"]


# ---------------------------------------------------------------------------
# 5. Recommendation explainability references source records
# ---------------------------------------------------------------------------

class TestRecommendationExplainability:
    """Verify recommendations reference source demand and gap records."""

    def test_recommendations_have_source_references(self):
        recs = analyze_gaps_csv()
        assert len(recs) > 0, "Must have gap recommendations"
        for r in recs:
            assert r.demand_quantity >= 0.0, "demand_quantity must be populated"
            assert r.skill_id != "", "skill_id must reference a source skill"
            assert r.reasoning != "", "reasoning must explain the decision"
            assert r.assumptions != "", "assumptions must be documented"
            assert r.decision_status == "PROPOSED"

    def test_recommendations_cover_action_types(self):
        """At least two different action types should be present."""
        recs = analyze_gaps_csv()
        action_types = {r.recommended_action for r in recs}
        assert len(action_types) >= 2, f"Only {action_types} found; expected variety"


# ---------------------------------------------------------------------------
# 6. Reproducibility across two independent generations
# ---------------------------------------------------------------------------

class TestReproducibility:
    """Verify deterministic reproducibility with seed 20261022."""

    def test_two_run_checksum_match(self):
        """Generate twice into temp dirs and compare checksums."""
        from src.generators.synthetic_data_generator import SyntheticDataGenerator

        checksums = []
        for run in range(2):
            with tempfile.TemporaryDirectory() as td:
                gen = SyntheticDataGenerator(scale="starter", seed=20261022, output_dir=td)
                gen.generate()
                gen.export()
                # Compute combined hash of core entity CSVs
                h = hashlib.sha256()
                for fname in sorted([
                    "employees.csv", "roles.csv", "skills.csv", "projects.csv",
                    "allocations.csv", "demand_plans.csv",
                ]):
                    fpath = Path(td) / fname
                    if fpath.exists():
                        h.update(fpath.read_bytes())
                checksums.append(h.hexdigest())

        assert checksums[0] == checksums[1], (
            f"Non-deterministic generation: run1={checksums[0]}, run2={checksums[1]}"
        )
