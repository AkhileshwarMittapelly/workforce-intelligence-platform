"""
Financial Intelligence Service.

Provides cost modelling and financial impact analysis for workforce decisions:
  - External hiring cost estimation
  - Internal upskilling cost estimation
  - Contractor engagement cost estimation
  - Bench waste quantification
  - Financial shortfall impact
  - ROI comparison across workforce strategies

All cost parameters are configurable. Financial calculations use source records
from the data/ directory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Default cost parameters (USD, annual unless noted)
DEFAULT_COSTS = {
    "avg_annual_salary": 95_000.0,
    "hiring_cost_multiplier": 0.25,       # 25% of annual salary
    "hiring_lead_time_weeks": 8,
    "contractor_daily_rate": 800.0,
    "contractor_markup_pct": 30.0,
    "training_cost_per_employee": 5_000.0,
    "training_duration_weeks": 4,
    "bench_cost_per_fte_per_month": 8_000.0,
    "cross_training_cost_per_employee": 3_000.0,
    "onboarding_cost_per_hire": 5_000.0,
    "revenue_per_fte_per_month": 15_000.0,
}


def _load_csv(name: str, data_dir: Optional[Path] = None) -> pd.DataFrame:
    path = (data_dir or DATA_DIR) / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


@dataclass
class FinancialSummary:
    """Financial overview of the workforce."""
    total_headcount: int
    total_fte: float
    estimated_annual_payroll: float
    bench_waste_monthly: float
    external_hiring_pipeline_cost: float
    training_investment: float
    contractor_spend_monthly: float
    revenue_at_risk_monthly: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecommendationCost:
    """Cost estimate for a single recommendation action."""
    action: str
    fte_required: float
    estimated_cost: float
    implementation_time_weeks: int
    expected_annual_savings: float
    roi_pct: float
    confidence: str
    breakdown: Dict[str, float] = field(default_factory=dict)


def get_financial_summary(
    data_dir: Optional[Path] = None,
    cost_params: Optional[Dict[str, float]] = None,
) -> FinancialSummary:
    """
    Calculate overall financial summary of the workforce.
    """
    d_dir = data_dir or DATA_DIR
    costs = {**DEFAULT_COSTS, **(cost_params or {})}

    employees_df = _load_csv("employees.csv", d_dir)
    allocations_df = _load_csv("allocations.csv", d_dir)
    gap_df = _load_csv("gap_analyses.csv", d_dir)

    for df in [employees_df, allocations_df, gap_df]:
        if not df.empty:
            df.columns = [c.strip().lower() for c in df.columns]

    # Headcount & FTE
    if not employees_df.empty and "status" in employees_df.columns:
        active = employees_df[employees_df["status"].str.upper() == "ACTIVE"]
    else:
        active = employees_df
    total_hc = len(active)
    total_fte = float(active["fte"].astype(float).sum()) if "fte" in active.columns else float(total_hc)

    # Estimated payroll
    annual_payroll = total_fte * costs["avg_annual_salary"]

    # Bench waste (employees below 50% utilisation)
    bench_fte = 0.0
    if not allocations_df.empty and not active.empty:
        allocated_emps = set(allocations_df["employee_id"].unique()) if "employee_id" in allocations_df.columns else set()
        bench_emps = active[~active["employee_id"].isin(allocated_emps)]
        bench_fte = float(bench_emps["fte"].astype(float).sum()) if "fte" in bench_emps.columns else float(len(bench_emps))
    bench_waste = bench_fte * costs["bench_cost_per_fte_per_month"]

    # Hiring pipeline cost from gaps
    hire_recs = 0
    training_recs = 0
    contractor_recs = 0
    shortage_fte = 0.0
    if not gap_df.empty:
        if "recommended_action" in gap_df.columns:
            hire_recs = len(gap_df[gap_df["recommended_action"] == "HIRE_EXTERNAL"])
            training_recs = len(gap_df[gap_df["recommended_action"].isin(["UPSKILL_INTERNAL", "CROSS_TRAIN"])])
            contractor_recs = len(gap_df[gap_df["recommended_action"] == "ENGAGE_CONTRACTOR"])
        if "shortage_headcount" in gap_df.columns:
            shortage_fte = float(gap_df["shortage_headcount"].astype(float).clip(lower=0).sum())

    hiring_cost = hire_recs * (costs["avg_annual_salary"] * costs["hiring_cost_multiplier"] + costs["onboarding_cost_per_hire"])
    training_cost = training_recs * costs["training_cost_per_employee"]
    contractor_monthly = contractor_recs * costs["contractor_daily_rate"] * 22  # ~22 working days/month

    # Revenue at risk from unfilled positions
    revenue_risk = shortage_fte * costs["revenue_per_fte_per_month"]

    return FinancialSummary(
        total_headcount=total_hc,
        total_fte=round(total_fte, 2),
        estimated_annual_payroll=round(annual_payroll, 2),
        bench_waste_monthly=round(bench_waste, 2),
        external_hiring_pipeline_cost=round(hiring_cost, 2),
        training_investment=round(training_cost, 2),
        contractor_spend_monthly=round(contractor_monthly, 2),
        revenue_at_risk_monthly=round(revenue_risk, 2),
        details={
            "bench_fte": round(bench_fte, 2),
            "hire_recommendations": hire_recs,
            "training_recommendations": training_recs,
            "contractor_recommendations": contractor_recs,
            "total_shortage_fte": round(shortage_fte, 2),
        },
    )


def estimate_recommendation_costs(
    data_dir: Optional[Path] = None,
    cost_params: Optional[Dict[str, float]] = None,
) -> List[RecommendationCost]:
    """
    Estimate costs for each recommendation action type from gap analysis.
    """
    d_dir = data_dir or DATA_DIR
    costs = {**DEFAULT_COSTS, **(cost_params or {})}
    gap_df = _load_csv("gap_analyses.csv", d_dir)

    if gap_df.empty:
        return []

    gap_df.columns = [c.strip().lower() for c in gap_df.columns]
    if "recommended_action" not in gap_df.columns:
        return []

    results = []
    action_groups = gap_df.groupby("recommended_action")

    for action, group in action_groups:
        if action == "NO_ACTION":
            continue

        shortage_col = "shortage_headcount" if "shortage_headcount" in group.columns else None
        total_fte = float(group[shortage_col].astype(float).clip(lower=0).sum()) if shortage_col else float(len(group))
        count = len(group)

        if action == "HIRE_EXTERNAL":
            per_hire = costs["avg_annual_salary"] * costs["hiring_cost_multiplier"] + costs["onboarding_cost_per_hire"]
            est_cost = count * per_hire
            lead_time = int(costs["hiring_lead_time_weeks"])
            savings = total_fte * costs["revenue_per_fte_per_month"] * 12
            confidence = "HIGH"
        elif action == "UPSKILL_INTERNAL":
            est_cost = count * costs["training_cost_per_employee"]
            lead_time = int(costs["training_duration_weeks"])
            savings = total_fte * costs["revenue_per_fte_per_month"] * 12 * 0.7  # 70% effectiveness
            confidence = "MEDIUM"
        elif action == "REASSIGN_BENCH":
            est_cost = count * 1_000  # Minimal transition cost
            lead_time = 2
            savings = total_fte * costs["bench_cost_per_fte_per_month"] * 12
            confidence = "HIGH"
        elif action == "ENGAGE_CONTRACTOR":
            est_cost = count * costs["contractor_daily_rate"] * 22 * 3  # 3 months
            lead_time = 2
            savings = total_fte * costs["revenue_per_fte_per_month"] * 3
            confidence = "MEDIUM"
        elif action == "CROSS_TRAIN":
            est_cost = count * costs["cross_training_cost_per_employee"]
            lead_time = int(costs["training_duration_weeks"])
            savings = total_fte * costs["revenue_per_fte_per_month"] * 12 * 0.5
            confidence = "LOW"
        else:
            est_cost = 0.0
            lead_time = 0
            savings = 0.0
            confidence = "LOW"

        roi = ((savings - est_cost) / est_cost * 100) if est_cost > 0 else 0.0

        results.append(RecommendationCost(
            action=action,
            fte_required=round(total_fte, 2),
            estimated_cost=round(est_cost, 2),
            implementation_time_weeks=lead_time,
            expected_annual_savings=round(savings, 2),
            roi_pct=round(roi, 1),
            confidence=confidence,
            breakdown={
                "recommendation_count": count,
                "total_shortage_fte": round(total_fte, 2),
                "unit_cost": round(est_cost / max(1, count), 2),
            },
        ))

    results.sort(key=lambda x: x.roi_pct, reverse=True)
    return results


def get_cost_comparison_table(
    data_dir: Optional[Path] = None,
    cost_params: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    """
    Returns a comparison table of all recommendation costs as a DataFrame.
    """
    recs = estimate_recommendation_costs(data_dir, cost_params)
    if not recs:
        return pd.DataFrame(columns=["Action", "FTE Required", "Estimated Cost ($)", "Lead Time (Weeks)",
                                      "Expected Annual Savings ($)", "ROI %", "Confidence"])

    rows = []
    for r in recs:
        rows.append({
            "Action": r.action,
            "FTE Required": r.fte_required,
            "Estimated Cost ($)": f"${r.estimated_cost:,.0f}",
            "Lead Time (Weeks)": r.implementation_time_weeks,
            "Expected Annual Savings ($)": f"${r.expected_annual_savings:,.0f}",
            "ROI %": f"{r.roi_pct:.1f}%",
            "Confidence": r.confidence,
        })
    return pd.DataFrame(rows)
