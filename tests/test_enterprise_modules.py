"""
Tests for Enterprise Modules:
- Matching Service
- What-If Simulation Service
- Financial Intelligence Service
- Time-Series Forecasting Models
- Configurable Scenario Evaluation Date
"""

import pytest
import pandas as pd
from pathlib import Path

from src.config import get_settings
from src.services.matching_service import (
    match_employees_to_project,
    get_project_matching_summary,
    find_best_candidates_for_skill,
)
from src.services.simulation_service import (
    simulate_demand_change,
    simulate_resignations,
    simulate_new_hires,
    simulate_training_completion,
    simulate_deadline_shift,
    run_scenario_comparison,
)
from src.services.financial_service import (
    get_financial_summary,
    estimate_recommendation_costs,
    get_cost_comparison_table,
)
from src.services.forecast_service import (
    compute_time_series_models,
    get_demand_time_series_forecast,
)


class TestConfigurableScenarioDate:
    def test_scenario_date_exists_and_defaults(self):
        settings = get_settings()
        assert hasattr(settings, "scenario_date")
        assert isinstance(settings.scenario_date, str)
        assert len(settings.scenario_date) == 10  # YYYY-MM-DD


class TestTimeSeriesForecasting:
    def test_compute_time_series_models_basic(self):
        periods = [f"2026-W{i:02d}" for i in range(1, 21)]
        values = [10.0 + i * 0.5 for i in range(1, 21)]

        res = compute_time_series_models(periods=periods, values=values, test_size=4, future_horizon=4)
        assert res["status"] == "EVALUATED"
        assert res["best_model"] in ["NAIVE", "MOVING_AVERAGE", "EXPONENTIAL_SMOOTHING", "HOLT_WINTERS"]
        assert len(res["models"]) == 4
        assert "NAIVE" in res["models"]
        assert "MOVING_AVERAGE" in res["models"]
        assert "EXPONENTIAL_SMOOTHING" in res["models"]
        assert "HOLT_WINTERS" in res["models"]

        for m_name, m_data in res["models"].items():
            metrics = m_data["metrics"]
            assert "mae" in metrics
            assert "rmse" in metrics
            assert "wape_pct" in metrics
            assert "forecast_bias_pct" in metrics

        assert len(res["future_periods"]) == 4
        assert len(res["future_forecast"]) == 4
        assert len(res["confidence_lower"]) == 4
        assert len(res["confidence_upper"]) == 4

    def test_compute_time_series_insufficient_data(self):
        periods = ["2026-W01", "2026-W02"]
        values = [10.0, 12.0]
        res = compute_time_series_models(periods=periods, values=values)
        assert res["status"] == "INSUFFICIENT_SERIES"

    def test_get_demand_time_series_forecast_live(self):
        res = get_demand_time_series_forecast()
        assert res["status"] in ["EVALUATED", "NO_DATA", "FILTER_MATCHED_ZERO_ROWS"]
        if res["status"] == "EVALUATED":
            assert len(res["future_forecast"]) > 0
            assert res["best_model"] in res["models"]


class TestMatchingService:
    @pytest.fixture
    def sample_project_id(self):
        projects_path = Path("data/projects.csv")
        if projects_path.exists():
            df = pd.read_csv(projects_path, nrows=5)
            if not df.empty and "project_id" in df.columns:
                return str(df.iloc[0]["project_id"])
        return "PRJ-2026-000001"

    def test_match_employees_to_project(self, sample_project_id):
        matches = match_employees_to_project(sample_project_id, top_n=5)
        assert isinstance(matches, list)
        if matches:
            first = matches[0]
            assert "employee_id" in first
            assert "employee_name" in first
            assert "match_score" in first
            assert 0.0 <= first["match_score"] <= 1.0
            assert "skill_match_pct" in first
            assert "proficiency_avg" in first
            assert "available_capacity_pct" in first
            assert "reasoning" in first

    def test_get_project_matching_summary(self, sample_project_id):
        summary = get_project_matching_summary(sample_project_id)
        assert "project_id" in summary
        assert "total_candidates" in summary
        assert "fully_matched" in summary
        assert "partially_matched" in summary

    def test_find_best_candidates_for_skill(self):
        skills_path = Path("data/skills.csv")
        if skills_path.exists():
            df = pd.read_csv(skills_path, nrows=5)
            if not df.empty and "skill_id" in df.columns:
                sid = str(df.iloc[0]["skill_id"])
                candidates = find_best_candidates_for_skill(sid, min_proficiency=1, top_n=5)
                assert isinstance(candidates, list)
                if candidates:
                    first = candidates[0]
                    assert "employee_id" in first
                    assert "proficiency_level" in first
                    assert first["proficiency_level"] >= 1


class TestSimulationService:
    def test_simulate_demand_change(self):
        res_plus = simulate_demand_change(20.0)
        assert res_plus.simulated_demand_fte > res_plus.baseline_demand_fte
        assert res_plus.gap_delta >= 0.0

        res_minus = simulate_demand_change(-10.0)
        assert res_minus.simulated_demand_fte < res_minus.baseline_demand_fte

    def test_simulate_resignations(self):
        res = simulate_resignations(resignation_count=5)
        assert res.simulated_supply_fte <= res.baseline_supply_fte
        assert res.gap_delta >= 0.0

    def test_simulate_new_hires(self):
        res = simulate_new_hires(hire_count=10, avg_fte=1.0)
        assert res.simulated_supply_fte >= res.baseline_supply_fte
        assert res.gap_delta <= 0.0

    def test_simulate_training_completion(self):
        skills_path = Path("data/skills.csv")
        sid = "SKILL-0001"
        if skills_path.exists():
            df = pd.read_csv(skills_path, nrows=5)
            if not df.empty and "skill_id" in df.columns:
                sid = str(df.iloc[0]["skill_id"])
        res = simulate_training_completion(skill_id=sid, trainees_count=5)
        assert res.gap_delta <= 0.0

    def test_simulate_deadline_shift(self):
        projects_path = Path("data/projects.csv")
        pid = "PRJ-2026-000001"
        if projects_path.exists():
            df = pd.read_csv(projects_path, nrows=5)
            if not df.empty and "project_id" in df.columns:
                pid = str(df.iloc[0]["project_id"])
        res = simulate_deadline_shift(project_id=pid, shift_weeks=4)
        assert res.simulated_demand_fte <= res.baseline_demand_fte

    def test_run_scenario_comparison(self):
        results = run_scenario_comparison()
        assert len(results) >= 5
        for r in results:
            assert hasattr(r, "scenario_name")
            assert hasattr(r, "gap_delta")


class TestFinancialService:
    def test_get_financial_summary(self):
        summary = get_financial_summary()
        assert summary.total_headcount > 0
        assert summary.total_fte > 0.0
        assert summary.estimated_annual_payroll > 0.0
        assert summary.revenue_at_risk_monthly >= 0.0

    def test_estimate_recommendation_costs(self):
        costs = estimate_recommendation_costs()
        assert isinstance(costs, list)
        for c in costs:
            assert hasattr(c, "action")
            assert hasattr(c, "estimated_cost")
            assert hasattr(c, "roi_pct")

    def test_get_cost_comparison_table(self):
        df = get_cost_comparison_table()
        assert isinstance(df, pd.DataFrame)
        expected_cols = ["Action", "FTE Required", "Estimated Cost ($)", "Lead Time (Weeks)",
                         "Expected Annual Savings ($)", "ROI %", "Confidence"]
        for col in expected_cols:
            assert col in df.columns
