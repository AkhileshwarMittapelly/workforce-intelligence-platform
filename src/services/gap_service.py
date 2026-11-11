"""
Gap Analysis & Recommendation Service.

Identifies capability gaps and utilisation risks, then generates ranked
GapRecommendation objects with actionable recommendations.
Supports CSV mode (data/ folder) and DB mode (SQLAlchemy session).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Severity ordering for sorting
_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}


@dataclass
class GapRecommendation:
    """Represents a single gap finding with an actionable recommendation."""

    gap_analysis_id: str
    skill_id: str
    role_id: str
    project_id: str
    shortage_headcount: float
    gap_severity: str           # NONE / LOW / MEDIUM / HIGH / CRITICAL
    recommended_action: str     # HIRE_EXTERNAL / UPSKILL_INTERNAL / REASSIGN_BENCH /
                                # ENGAGE_CONTRACTOR / CROSS_TRAIN / NO_ACTION
    reasoning: str
    period_start: Optional[date]
    period_end: Optional[date]


# ---------------------------------------------------------------------------
# Severity helpers
# ---------------------------------------------------------------------------

def _gap_severity(shortage: float, utilization_pct: float = 0.0) -> str:
    """Derive gap severity from shortage headcount and utilisation."""
    if shortage <= 0 and utilization_pct < 100:
        return "NONE"
    if shortage > 5 or utilization_pct > 120:
        return "CRITICAL"
    if shortage > 3 or utilization_pct > 100:
        return "HIGH"
    if shortage > 1:
        return "MEDIUM"
    if shortage > 0:
        return "LOW"
    return "NONE"


def _recommend_action(
    shortage: float,
    proficiency_gap: float,
    bench_available: bool,
    training_time_available: bool,
    is_critical_priority: bool,
) -> tuple[str, str]:
    """
    Apply recommendation logic and return (action, reasoning) tuple.

    Rules (evaluated in priority order):
    1. shortage > 5 AND proficiency_gap > 2 → HIRE_EXTERNAL
    2. shortage > 2 AND bench available → REASSIGN_BENCH
    3. shortage 1–2 AND training time available → UPSKILL_INTERNAL
    4. critical priority project → ENGAGE_CONTRACTOR
    5. else → CROSS_TRAIN
    """
    if shortage <= 0:
        return ("NO_ACTION", "No shortage detected; workforce meets current demand.")

    if shortage > 5 and proficiency_gap > 2:
        return (
            "HIRE_EXTERNAL",
            f"Shortage of {shortage:.1f} FTE with a proficiency gap of {proficiency_gap:.1f} "
            "exceeds internal reskilling capacity. External hiring is recommended.",
        )

    if shortage > 2 and bench_available:
        return (
            "REASSIGN_BENCH",
            f"Shortage of {shortage:.1f} FTE but bench employees with matching skills are available. "
            "Reassigning bench resources is the fastest resolution.",
        )

    if 0 < shortage <= 2 and training_time_available:
        return (
            "UPSKILL_INTERNAL",
            f"Shortage of {shortage:.1f} FTE is small enough to address through targeted upskilling "
            "within the available training window.",
        )

    if is_critical_priority:
        return (
            "ENGAGE_CONTRACTOR",
            f"Project is critical priority. Engaging a contractor for the {shortage:.1f} FTE gap "
            "ensures delivery timelines are not compromised.",
        )

    return (
        "CROSS_TRAIN",
        f"Shortage of {shortage:.1f} FTE can be addressed by cross-training employees "
        "from adjacent skill areas.",
    )


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _load_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        logger.warning("CSV %s not found; returning empty DataFrame", path)
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


# ---------------------------------------------------------------------------
# Core gap analysis logic
# ---------------------------------------------------------------------------

def _compute_gap_recommendations(
    demand_df: pd.DataFrame,
    employees_df: pd.DataFrame,
    employee_skills_df: pd.DataFrame,
    allocations_df: pd.DataFrame,
    projects_df: Optional[pd.DataFrame] = None,
    gap_analyses_df: Optional[pd.DataFrame] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> list[GapRecommendation]:
    """
    Derive GapRecommendation list from DataFrames.

    Priority logic (see _recommend_action for details):
    shortage > 5 AND proficiency_gap > 2 → HIRE_EXTERNAL
    shortage > 2 AND bench available     → REASSIGN_BENCH
    shortage 1-2 AND training available  → UPSKILL_INTERNAL
    critical priority project             → ENGAGE_CONTRACTOR
    else                                  → CROSS_TRAIN
    """
    if demand_df.empty:
        return []

    # Normalise column names
    for df_ref in [demand_df, employees_df, employee_skills_df, allocations_df]:
        df_ref.columns = [c.strip().lower() for c in df_ref.columns]

    if projects_df is not None and not projects_df.empty:
        projects_df = projects_df.copy()
        projects_df.columns = [c.strip().lower() for c in projects_df.columns]

    if gap_analyses_df is not None and not gap_analyses_df.empty:
        gap_analyses_df = gap_analyses_df.copy()
        gap_analyses_df.columns = [c.strip().lower() for c in gap_analyses_df.columns]

    # Date filtering on demand
    start_c = "start_date" if "start_date" in demand_df.columns else ("period_start" if "period_start" in demand_df.columns else None)
    end_c = "end_date" if "end_date" in demand_df.columns else ("period_end" if "period_end" in demand_df.columns else None)
    if start_c:
        demand_df["_start_dt"] = pd.to_datetime(demand_df[start_c], errors="coerce")
    if end_c:
        demand_df["_end_dt"] = pd.to_datetime(demand_df[end_c], errors="coerce")
    if period_start and "_start_dt" in demand_df.columns:
        demand_df = demand_df[demand_df["_start_dt"] >= pd.Timestamp(period_start)]
    if period_end and "_end_dt" in demand_df.columns:
        demand_df = demand_df[demand_df["_end_dt"] <= pd.Timestamp(period_end)]

    if demand_df.empty:
        return []

    # --- Active employees ---
    if not employees_df.empty and "status" in employees_df.columns:
        active_emp = employees_df[employees_df["status"].str.upper() == "ACTIVE"]
    else:
        active_emp = employees_df

    # --- Skill lookup ---
    skill_col_emp = "skill_id" if "skill_id" in employee_skills_df.columns else None

    if skill_col_emp and not employee_skills_df.empty:
        skill_lookup = employee_skills_df[
            [c for c in ["employee_id", "skill_id", "proficiency_level"] if c in employee_skills_df.columns]
        ].copy()
        if "proficiency_level" not in skill_lookup.columns:
            skill_lookup["proficiency_level"] = 3
    else:
        skill_lookup = pd.DataFrame(columns=["employee_id", "skill_id", "proficiency_level"])

    # --- Bench employees: low allocation ---
    if not allocations_df.empty:
        alloc_col = next((c for c in ("allocation_percentage", "allocated_fte", "allocation_pct", "fte") if c in allocations_df.columns), None)
        if alloc_col and "employee_id" in allocations_df.columns:
            alloc_temp = allocations_df.copy()
            if alloc_col == "allocation_percentage":
                alloc_temp["_alloc_rate"] = alloc_temp[alloc_col].astype(float) / 100.0
            else:
                alloc_temp["_alloc_rate"] = alloc_temp[alloc_col].astype(float)

            emp_alloc_sum = (
                alloc_temp.groupby("employee_id")["_alloc_rate"]
                .sum()
                .reset_index()
                .rename(columns={"_alloc_rate": "total_alloc"})
            )
            bench_emp_ids = set(
                emp_alloc_sum[emp_alloc_sum["total_alloc"] < 0.5]["employee_id"].tolist()
            )
        else:
            bench_emp_ids = set(active_emp["employee_id"].tolist()) if not active_emp.empty else set()
    else:
        bench_emp_ids = set(active_emp["employee_id"].tolist()) if not active_emp.empty else set()

    # --- Critical priority projects ---
    critical_project_ids: set = set()
    if projects_df is not None and not projects_df.empty:
        priority_col = next((c for c in ("priority", "project_priority") if c in projects_df.columns), None)
        proj_id_col = "project_id" if "project_id" in projects_df.columns else None
        if priority_col and proj_id_col:
            crit = projects_df[projects_df[priority_col].str.upper() == "CRITICAL"]
            critical_project_ids = set(crit[proj_id_col].tolist())

    # --- Process each demand row ---
    skill_demand_col = next(
        (c for c in ("required_skill_id", "skill_id") if c in demand_df.columns), None
    )
    role_col = "role_id" if "role_id" in demand_df.columns else None
    proj_col = next((c for c in ("project_id", "proj_id") if c in demand_df.columns), None)
    fte_col = next((c for c in ("required_fte", "demand_fte", "fte") if c in demand_df.columns), None)
    req_prof_col = next(
        (c for c in ("min_proficiency_level", "required_proficiency", "proficiency_level") if c in demand_df.columns), None
    )

    if skill_demand_col is None or fte_col is None:
        logger.warning("demand_df missing required_skill_id/fte columns; cannot compute gaps.")
        return []

    # Group demand by skill / role / project
    group_keys = [k for k in [skill_demand_col, role_col, proj_col] if k is not None]
    demand_grp = demand_df.groupby(group_keys).agg(
        demand_fte=(fte_col, "sum"),
        req_prof=(req_prof_col, "max") if req_prof_col else (fte_col, "count"),
        period_start=("_start_dt", "min") if "_start_dt" in demand_df.columns else (fte_col, "count"),
        period_end=("_end_dt", "max") if "_end_dt" in demand_df.columns else (fte_col, "count"),
    ).reset_index()

    recommendations: list[GapRecommendation] = []

    for _, row in demand_grp.iterrows():
        skill_id = str(row[skill_demand_col]) if skill_demand_col else "UNKNOWN"
        role_id = str(row[role_col]) if role_col and role_col in row.index else "UNKNOWN"
        project_id = str(row[proj_col]) if proj_col and proj_col in row.index else "UNKNOWN"
        demand_fte = float(row["demand_fte"])

        req_prof = int(row["req_prof"]) if req_prof_col and "req_prof" in row.index else 1

        # Supply: qualified employees' available FTE
        if not skill_lookup.empty:
            qualified_emps = skill_lookup[
                (skill_lookup["skill_id"] == skill_id)
                & (skill_lookup["proficiency_level"].fillna(1) >= req_prof)
            ]
        else:
            qualified_emps = pd.DataFrame(columns=["employee_id", "skill_id", "proficiency_level"])

        # Intersect with active employees
        if not active_emp.empty and not qualified_emps.empty:
            active_ids = set(active_emp["employee_id"].tolist())
            qualified_emps = qualified_emps[qualified_emps["employee_id"].isin(active_ids)]

        qualified_count = len(qualified_emps)

        # Average proficiency of qualified employees (for gap calc)
        if not qualified_emps.empty and "proficiency_level" in qualified_emps.columns:
            avg_prof = float(qualified_emps["proficiency_level"].mean())
        else:
            avg_prof = 0.0

        proficiency_gap = max(0.0, req_prof - avg_prof)

        # Bench check: any qualified employee on bench?
        if not qualified_emps.empty:
            bench_qualified = qualified_emps["employee_id"].isin(bench_emp_ids).any()
        else:
            bench_qualified = len(bench_emp_ids) > 0  # generic bench

        shortage = max(0.0, demand_fte - qualified_count)

        # Training time heuristic: if shortage <= 2 and period allows > 4 weeks
        training_time_available = False
        if "period_start" in demand_df.columns and not demand_df.empty:
            ps = row.get("period_start")
            pe = row.get("period_end")
            if pd.notna(ps) and pd.notna(pe):
                weeks = (pd.Timestamp(pe) - pd.Timestamp(ps)).days / 7
                training_time_available = weeks >= 4

        is_critical = project_id in critical_project_ids

        severity = _gap_severity(shortage)
        action, reasoning = _recommend_action(
            shortage=shortage,
            proficiency_gap=proficiency_gap,
            bench_available=bool(bench_qualified),
            training_time_available=training_time_available,
            is_critical_priority=is_critical,
        )

        ps_date = row["period_start"].date() if "period_start" in row.index and pd.notna(row.get("period_start")) else period_start
        pe_date = row["period_end"].date() if "period_end" in row.index and pd.notna(row.get("period_end")) else period_end

        rec = GapRecommendation(
            gap_analysis_id=f"GAP-{uuid.uuid4().hex[:8].upper()}",
            skill_id=skill_id,
            role_id=role_id,
            project_id=project_id,
            shortage_headcount=round(shortage, 2),
            gap_severity=severity,
            recommended_action=action,
            reasoning=reasoning,
            period_start=ps_date if isinstance(ps_date, date) else None,
            period_end=pe_date if isinstance(pe_date, date) else None,
        )
        recommendations.append(rec)

    # Sort: highest severity first
    recommendations.sort(key=lambda r: _SEVERITY_ORDER.get(r.gap_severity, 99))
    return recommendations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_gaps_csv(
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> list[GapRecommendation]:
    """
    Run gap analysis using CSV files from the data/ folder.

    Returns:
        List of GapRecommendation sorted by severity (CRITICAL first).
    """
    demand_df = _load_csv("demand_plans.csv")
    employees_df = _load_csv("employees.csv")
    employee_skills_df = _load_csv("employee_skills.csv")
    allocations_df = _load_csv("allocations.csv")
    projects_df = _load_csv("projects.csv")

    return _compute_gap_recommendations(
        demand_df=demand_df,
        employees_df=employees_df,
        employee_skills_df=employee_skills_df,
        allocations_df=allocations_df,
        projects_df=projects_df,
        period_start=period_start,
        period_end=period_end,
    )


def analyze_gaps_db(
    session,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> list[GapRecommendation]:
    """
    Run gap analysis using a live SQLAlchemy DB session.

    Falls back to CSV mode on any DB error.
    """
    try:
        from sqlalchemy import text as sa_text

        where_clauses = []
        params: dict = {}
        if period_start:
            where_clauses.append("dp.period_start >= :period_start")
            params["period_start"] = period_start
        if period_end:
            where_clauses.append("dp.period_end <= :period_end")
            params["period_end"] = period_end
        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        demand_df = pd.read_sql(
            sa_text(f"SELECT * FROM demand_plan dp {where_sql}"),
            session.bind,
            params=params,
        )
        employees_df = pd.read_sql(sa_text("SELECT * FROM employee"), session.bind)
        employee_skills_df = pd.read_sql(sa_text("SELECT * FROM employee_skill"), session.bind)
        allocations_df = pd.read_sql(sa_text("SELECT * FROM allocation"), session.bind)
        projects_df = pd.read_sql(sa_text("SELECT * FROM project"), session.bind)

        return _compute_gap_recommendations(
            demand_df=demand_df,
            employees_df=employees_df,
            employee_skills_df=employee_skills_df,
            allocations_df=allocations_df,
            projects_df=projects_df,
            period_start=period_start,
            period_end=period_end,
        )

    except Exception as exc:
        logger.warning("DB gap analysis failed (%s); falling back to CSV mode.", exc)
        return analyze_gaps_csv(period_start=period_start, period_end=period_end)


def analyze_gaps(
    session=None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> list[GapRecommendation]:
    """
    Entry point: use DB session when provided, otherwise fall back to CSV.
    """
    if session is not None:
        return analyze_gaps_db(session, period_start=period_start, period_end=period_end)
    return analyze_gaps_csv(period_start=period_start, period_end=period_end)
