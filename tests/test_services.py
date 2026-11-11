"""
Unit tests for Forecast, Gap Analysis, DB, and Analytics Services.
"""

from decimal import Decimal
import pandas as pd
import pytest

from src.services.forecast_service import _risk_level, _compute_forecasts
from src.services.gap_service import _gap_severity, _recommend_action, analyze_gaps
from src.services.db_service import get_active_employees, get_skills, get_roles, get_demand_plans
from src.services.analytics_service import get_workforce_kpis, get_department_breakdown, get_monthly_utilization_trend


def test_forecast_risk_levels():
    """Validates risk category thresholds."""
    assert _risk_level(95.0) == "CRITICAL"
    assert _risk_level(85.0) == "HIGH"
    assert _risk_level(70.0) == "MEDIUM"
    assert _risk_level(50.0) == "LOW"


def test_gap_severity_rules():
    """Validates gap severity derivation."""
    assert _gap_severity(shortage=6.0) == "CRITICAL"
    assert _gap_severity(shortage=4.0) == "HIGH"
    assert _gap_severity(shortage=2.0) == "MEDIUM"
    assert _gap_severity(shortage=1.0) == "LOW"
    assert _gap_severity(shortage=0.0) == "NONE"


def test_gap_recommendation_logic():
    """Validates actionable recommendation rules."""
    # Large shortage + high proficiency gap -> Hire external
    action, reasoning = _recommend_action(
        shortage=6.0,
        proficiency_gap=3.0,
        bench_available=False,
        training_time_available=False,
        is_critical_priority=False,
    )
    assert action == "HIRE_EXTERNAL"

    # Moderate shortage + bench available -> Reassign bench
    action, reasoning = _recommend_action(
        shortage=3.0,
        proficiency_gap=1.0,
        bench_available=True,
        training_time_available=True,
        is_critical_priority=False,
    )
    assert action == "REASSIGN_BENCH"

    # Small shortage + training time -> Upskill internal
    action, reasoning = _recommend_action(
        shortage=1.5,
        proficiency_gap=1.0,
        bench_available=False,
        training_time_available=True,
        is_critical_priority=False,
    )
    assert action == "UPSKILL_INTERNAL"

    # No shortage -> No action
    action, reasoning = _recommend_action(
        shortage=0.0,
        proficiency_gap=0.0,
        bench_available=False,
        training_time_available=False,
        is_critical_priority=False,
    )
    assert action == "NO_ACTION"


def test_db_service_fallback():
    """Verifies that DB service returns DataFrames without throwing exceptions."""
    roles = get_roles()
    assert isinstance(roles, pd.DataFrame)
    employees = get_active_employees()
    assert isinstance(employees, pd.DataFrame)
    skills = get_skills()
    assert isinstance(skills, pd.DataFrame)


def test_analytics_kpis():
    """Validates calculation of enterprise workforce KPIs."""
    kpis = get_workforce_kpis()
    assert kpis.total_headcount >= 0
    assert 0.0 <= kpis.avg_utilization_pct <= 100.0
    dept_df = get_department_breakdown()
    assert isinstance(dept_df, pd.DataFrame)
    trend_df = get_monthly_utilization_trend()
    assert len(trend_df) == 12
