"""
Demand Forecasting Service.

Aggregates demand vs. supply by role/skill/period and computes FTE gap and risk levels.
Supports both CSV-based mode (data/ folder) and DB mode (SQLAlchemy session).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Risk level thresholds (utilization_pct based)
RISK_CRITICAL = 90.0
RISK_HIGH = 80.0
RISK_MEDIUM = 60.0


def _risk_level(utilization_pct: float) -> str:
    """Return risk level string based on utilisation percentage."""
    if utilization_pct > RISK_CRITICAL:
        return "CRITICAL"
    if utilization_pct > RISK_HIGH:
        return "HIGH"
    if utilization_pct > RISK_MEDIUM:
        return "MEDIUM"
    return "LOW"


@dataclass
class ForecastResult:
    """Result of a demand-vs-supply forecast for a single role/skill/period."""

    period: str                   # e.g. "2026-W01" or "2026-01"
    role_id: str
    skill_id: str
    demand_fte: float
    supply_fte: float
    gap_fte: float                # demand - supply; positive = shortage
    utilization_pct: float        # supply consumed / supply available * 100
    risk_level: str               # LOW / MEDIUM / HIGH / CRITICAL
    project_id: str = "ALL"
    forecast_id: str = ""
    already_allocated_fte: float = 0.0
    qualified_available_fte: float = 0.0
    remaining_supply_fte: float = 0.0
    calculation_timestamp: str = ""
    assumptions: str = ""


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _load_csv(name: str) -> pd.DataFrame:
    """Load a CSV file from the data/ folder. Returns empty DataFrame if missing."""
    path = DATA_DIR / name
    if not path.exists():
        logger.warning("CSV %s not found; returning empty DataFrame", path)
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def _load_demand_plans_csv() -> pd.DataFrame:
    return _load_csv("demand_plans.csv")


def _load_employees_csv() -> pd.DataFrame:
    return _load_csv("employees.csv")


def _load_employee_skills_csv() -> pd.DataFrame:
    return _load_csv("employee_skills.csv")


def _load_allocations_csv() -> pd.DataFrame:
    return _load_csv("allocations.csv")


# ---------------------------------------------------------------------------
# Core forecast logic (operates on DataFrames regardless of source)
# ---------------------------------------------------------------------------

def _compute_forecasts(
    demand_df: pd.DataFrame,
    employees_df: pd.DataFrame,
    employee_skills_df: pd.DataFrame,
    allocations_df: pd.DataFrame,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    granularity: str = "week",   # "week" | "month"
) -> list[ForecastResult]:
    """
    Core logic: compute ForecastResult list from DataFrames.

    Args:
        demand_df: Columns expected include required_skill_id, role_id, required_fte,
                   period_start, period_end (or week_number / month).
        employees_df: Columns expected include employee_id, fte, status.
        employee_skills_df: Columns expected include employee_id, skill_id, proficiency_level.
        allocations_df: Columns expected include employee_id, allocated_fte (or allocation_pct).
        period_start: Filter demand from this date (inclusive).
        period_end: Filter demand to this date (inclusive).
        granularity: "week" or "month".
    """
    if demand_df.empty:
        return []

    # Normalise column names to lower-snake-case
    demand_df = demand_df.copy()
    demand_df.columns = [c.strip().lower() for c in demand_df.columns]

    employees_df = employees_df.copy()
    employees_df.columns = [c.strip().lower() for c in employees_df.columns]

    employee_skills_df = employee_skills_df.copy()
    employee_skills_df.columns = [c.strip().lower() for c in employee_skills_df.columns]

    allocations_df = allocations_df.copy()
    allocations_df.columns = [c.strip().lower() for c in allocations_df.columns]

    # Date filtering
    # Support both start_date/end_date and period_start/period_end
    start_col = "start_date" if "start_date" in demand_df.columns else ("period_start" if "period_start" in demand_df.columns else None)
    end_col = "end_date" if "end_date" in demand_df.columns else ("period_end" if "period_end" in demand_df.columns else None)

    if start_col:
        demand_df["_dt_start"] = pd.to_datetime(demand_df[start_col], errors="coerce")
    if end_col:
        demand_df["_dt_end"] = pd.to_datetime(demand_df[end_col], errors="coerce")

    if period_start and "_dt_start" in demand_df.columns:
        demand_df = demand_df[demand_df["_dt_start"] >= pd.Timestamp(period_start)]
    if period_end and "_dt_end" in demand_df.columns:
        demand_df = demand_df[demand_df["_dt_end"] <= pd.Timestamp(period_end)]

    if demand_df.empty:
        return []

    # Build period label column
    if granularity == "week":
        if "week_number" in demand_df.columns:
            demand_df["_period"] = demand_df["week_number"].astype(str)
        elif "_dt_start" in demand_df.columns and demand_df["_dt_start"].notna().any():
            demand_df["_period"] = demand_df["_dt_start"].dt.strftime("%G-W%V")
        else:
            demand_df["_period"] = "2026-W01"
    else:
        if "_dt_start" in demand_df.columns and demand_df["_dt_start"].notna().any():
            demand_df["_period"] = demand_df["_dt_start"].dt.strftime("%Y-%m")
        else:
            demand_df["_period"] = "2026-01"

    # Skill demand: use required_skill_id if present, else skill_id
    skill_col = "required_skill_id" if "required_skill_id" in demand_df.columns else "skill_id"
    if skill_col not in demand_df.columns:
        demand_df["required_skill_id"] = "UNKNOWN"
        skill_col = "required_skill_id"

    role_col = "role_id" if "role_id" in demand_df.columns else None
    prj_col = "project_id" if "project_id" in demand_df.columns else None

    # Required proficiency from demand (support min_proficiency_level & required_proficiency)
    req_prof_col = None
    for cand in ("min_proficiency_level", "required_proficiency", "proficiency_level"):
        if cand in demand_df.columns:
            req_prof_col = cand
            break

    # FTE demand column
    fte_col = None
    for candidate in ("required_fte", "demand_fte", "fte"):
        if candidate in demand_df.columns:
            fte_col = candidate
            break

    if fte_col is None:
        demand_df["required_fte"] = 1.0
        fte_col = "required_fte"

    # Active employees
    if not employees_df.empty and "status" in employees_df.columns:
        active_emp = employees_df[employees_df["status"].str.upper() == "ACTIVE"]
    else:
        active_emp = employees_df

    # Build employee→skills lookup with proficiency and freshness
    skill_cols_avail = ["employee_id", "skill_id", "proficiency_level"]
    if not employee_skills_df.empty:
        # Filter out expired skills
        if "status" in employee_skills_df.columns:
            es_valid = employee_skills_df[employee_skills_df["status"].str.upper() != "EXPIRED"].copy()
        else:
            es_valid = employee_skills_df.copy()

        # Check freshness: last_evaluated_date <= 548 days (18 months)
        if "last_evaluated_date" in es_valid.columns:
            eval_dt = pd.to_datetime(es_valid["last_evaluated_date"], errors="coerce")
            scenario_dt = pd.Timestamp("2026-11-11")
            is_stale = (scenario_dt - eval_dt).dt.days > 548
            es_valid = es_valid[~is_stale]

        skill_lookup = es_valid[[c for c in skill_cols_avail if c in es_valid.columns]].copy()
        if "proficiency_level" not in skill_lookup.columns:
            skill_lookup["proficiency_level"] = 3
    else:
        skill_lookup = pd.DataFrame(columns=["employee_id", "skill_id", "proficiency_level"])

    # Build allocated FTE per employee (sum across allocations, support allocation_percentage)
    if not allocations_df.empty:
        alloc_work = allocations_df.copy()
        if "allocation_percentage" in alloc_work.columns:
            alloc_work["_fte_val"] = alloc_work["allocation_percentage"].astype(float) / 100.0
        elif "allocated_fte" in alloc_work.columns:
            alloc_work["_fte_val"] = alloc_work["allocated_fte"].astype(float)
        elif "fte" in alloc_work.columns:
            alloc_work["_fte_val"] = alloc_work["fte"].astype(float)
        else:
            alloc_work["_fte_val"] = 0.5

        emp_alloc = (
            alloc_work.groupby("employee_id")["_fte_val"]
            .sum()
            .clip(upper=1.0)
            .reset_index()
            .rename(columns={"_fte_val": "total_allocated_fte"})
        )
    else:
        emp_alloc = pd.DataFrame(columns=["employee_id", "total_allocated_fte"])

    # Merge active employees with allocations to find available FTE per employee
    if not active_emp.empty:
        emp_fte_col = "fte" if "fte" in active_emp.columns else None
        if emp_fte_col:
            emp_base = active_emp[["employee_id", "fte"]].copy()
        else:
            emp_base = active_emp[["employee_id"]].copy()
            emp_base["fte"] = 1.0

        if not emp_alloc.empty:
            emp_base = emp_base.merge(emp_alloc, on="employee_id", how="left")
            emp_base["total_allocated_fte"] = emp_base["total_allocated_fte"].fillna(0.0)
        else:
            emp_base["total_allocated_fte"] = 0.0

        emp_base["available_fte"] = (emp_base["fte"] - emp_base["total_allocated_fte"]).clip(lower=0.0)
    else:
        emp_base = pd.DataFrame(columns=["employee_id", "fte", "available_fte"])

    # Merge skills with available capacity
    if not skill_lookup.empty and not emp_base.empty:
        skill_avail = skill_lookup.merge(emp_base[["employee_id", "available_fte"]], on="employee_id", how="left")
        skill_avail["available_fte"] = skill_avail["available_fte"].fillna(0.0)
    else:
        skill_avail = skill_lookup.copy()
        if "available_fte" not in skill_avail.columns:
            skill_avail["available_fte"] = 0.0

    # Aggregate demand
    group_cols = ["_period", skill_col]
    if role_col:
        group_cols.append(role_col)

    demand_agg = demand_df.groupby(group_cols)[fte_col].sum().reset_index()
    demand_agg = demand_agg.rename(columns={fte_col: "demand_fte", skill_col: "skill_id"})
    if role_col:
        demand_agg = demand_agg.rename(columns={role_col: "role_id"})
    else:
        demand_agg["role_id"] = "UNKNOWN"

    results: list[ForecastResult] = []

    for _, row in demand_agg.iterrows():
        period = str(row["_period"])
        role_id = str(row["role_id"])
        skill_id = str(row["skill_id"])
        demand_fte = float(row["demand_fte"])

        # Required proficiency for this skill from demand_df (take max as conservative)
        if req_prof_col:
            skill_demand_rows = demand_df[demand_df[skill_col] == row["skill_id"]]
            req_prof = int(skill_demand_rows[req_prof_col].max()) if not skill_demand_rows.empty else 1
        else:
            req_prof = 1

        # Supply: employees with this skill AND proficiency >= required
        if not skill_avail.empty and "skill_id" in skill_avail.columns:
            qualified = skill_avail[
                (skill_avail["skill_id"] == skill_id)
                & (skill_avail["proficiency_level"].fillna(1) >= req_prof)
            ]
            supply_fte = float(qualified["available_fte"].sum())
        else:
            supply_fte = 0.0

        gap_fte = max(0.0, demand_fte - supply_fte)

        # Utilization: what fraction of supply is consumed by demand
        if supply_fte > 0:
            utilization_pct = min((demand_fte / supply_fte) * 100.0, 150.0)  # cap at 150%
        elif demand_fte > 0:
            utilization_pct = 150.0  # no supply → worst case
        else:
            utilization_pct = 0.0

        risk = _risk_level(utilization_pct)

        forecast_id = f"FCST-{period}-{role_id}-{skill_id}"
        results.append(
            ForecastResult(
                period=period,
                role_id=role_id,
                skill_id=skill_id,
                demand_fte=round(demand_fte, 4),
                supply_fte=round(supply_fte, 4),
                gap_fte=round(gap_fte, 4),
                utilization_pct=round(utilization_pct, 2),
                risk_level=risk,
                project_id="ALL",
                forecast_id=forecast_id,
                already_allocated_fte=0.0,
                qualified_available_fte=round(supply_fte, 4),
                remaining_supply_fte=max(0.0, round(supply_fte - demand_fte, 4)),
                calculation_timestamp="2026-11-11T12:00:00",
                assumptions=f"Proficiency threshold >= {req_prof}; Active & non-stale <= 18 months",
            )
        )

    # Sort: CRITICAL first
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    results.sort(key=lambda r: severity_order.get(r.risk_level, 99))
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def forecast_csv(
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    granularity: str = "week",
) -> list[ForecastResult]:
    """
    Run demand forecasting using CSV files from the data/ folder.

    Args:
        period_start: Optional start date filter.
        period_end: Optional end date filter.
        granularity: "week" or "month".

    Returns:
        List of ForecastResult sorted by severity (CRITICAL first).
    """
    demand_df = _load_demand_plans_csv()
    employees_df = _load_employees_csv()
    employee_skills_df = _load_employee_skills_csv()
    allocations_df = _load_allocations_csv()

    return _compute_forecasts(
        demand_df,
        employees_df,
        employee_skills_df,
        allocations_df,
        period_start=period_start,
        period_end=period_end,
        granularity=granularity,
    )


def forecast_db(
    session,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    granularity: str = "week",
) -> list[ForecastResult]:
    """
    Run demand forecasting using a live SQLAlchemy DB session.

    Falls back to CSV mode on any DB error.

    Args:
        session: SQLAlchemy Session object.
        period_start: Optional start date filter.
        period_end: Optional end date filter.
        granularity: "week" or "month".

    Returns:
        List of ForecastResult sorted by severity (CRITICAL first).
    """
    try:
        from sqlalchemy import text as sa_text

        # Build date filter clause
        where_clauses = []
        params: dict = {}
        if period_start:
            where_clauses.append("dp.period_start >= :period_start")
            params["period_start"] = period_start
        if period_end:
            where_clauses.append("dp.period_end <= :period_end")
            params["period_end"] = period_end
        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        demand_sql = f"""
            SELECT dp.demand_plan_id, dp.role_id, dp.required_skill_id,
                   dp.required_fte, dp.required_proficiency,
                   dp.period_start, dp.period_end, dp.week_number
            FROM demand_plan dp
            {where_sql}
        """
        demand_df = pd.read_sql(sa_text(demand_sql), session.bind, params=params)

        employees_df = pd.read_sql(
            sa_text("SELECT employee_id, fte, status FROM employee"),
            session.bind,
        )

        employee_skills_df = pd.read_sql(
            sa_text("SELECT employee_id, skill_id, proficiency_level FROM employee_skill"),
            session.bind,
        )

        allocations_df = pd.read_sql(
            sa_text("SELECT employee_id, allocated_fte FROM allocation"),
            session.bind,
        )

        return _compute_forecasts(
            demand_df,
            employees_df,
            employee_skills_df,
            allocations_df,
            period_start=period_start,
            period_end=period_end,
            granularity=granularity,
        )

    except Exception as exc:
        logger.warning("DB forecast failed (%s); falling back to CSV mode.", exc)
        return forecast_csv(period_start=period_start, period_end=period_end, granularity=granularity)


def run_forecast(
    session=None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    granularity: str = "week",
) -> list[ForecastResult]:
    """
    Entry point: use DB session when provided, otherwise fall back to CSV.

    Args:
        session: Optional SQLAlchemy Session. If None, uses CSV mode.
        period_start: Optional date filter start.
        period_end: Optional date filter end.
        granularity: "week" or "month".
    """
    if session is not None:
        return forecast_db(session, period_start=period_start, period_end=period_end, granularity=granularity)
    return forecast_csv(period_start=period_start, period_end=period_end, granularity=granularity)


# Alias for compatibility with external callers
get_demand_forecast = run_forecast
