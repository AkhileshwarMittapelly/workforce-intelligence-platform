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
    leave_events_df: Optional[pd.DataFrame] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> list[GapRecommendation]:
    """
    Derive GapRecommendation list from DataFrames using consistent FTE accounting.
    Excludes inactive employees and stale skills (>18 months).
    Calculates bench capacity using date-overlapping allocations and approved leave
    during the relevant demand period, avoiding double-counting across demands.
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

    # Load leave events if not passed
    if leave_events_df is None or leave_events_df.empty:
        leave_events_df = _load_csv("leave_events.csv")
    if not leave_events_df.empty:
        leave_events_df = leave_events_df.copy()
        leave_events_df.columns = [c.strip().lower() for c in leave_events_df.columns]

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

    # --- 1. Active employees only ---
    if not employees_df.empty and "status" in employees_df.columns:
        active_emp = employees_df[employees_df["status"].str.upper() == "ACTIVE"].copy()
    else:
        active_emp = employees_df.copy()

    emp_contracted_map = dict(
        zip(active_emp["employee_id"], active_emp["fte"].astype(float))
    ) if "fte" in active_emp.columns else {e: 1.0 for e in active_emp.get("employee_id", [])}

    # --- 2. Valid and non-stale skills only ---
    if not employee_skills_df.empty:
        es_valid = employee_skills_df[employee_skills_df["status"].str.upper() == "ACTIVE"].copy() if "status" in employee_skills_df.columns else employee_skills_df.copy()
        if "last_evaluated_date" in es_valid.columns:
            eval_dt = pd.to_datetime(es_valid["last_evaluated_date"], errors="coerce")
            scenario_dt = pd.Timestamp("2026-11-11")
            es_valid = es_valid[(scenario_dt - eval_dt).dt.days <= 548]  # exclude > 18 months stale
        skill_lookup = es_valid[
            [c for c in ["employee_id", "skill_id", "proficiency_level"] if c in es_valid.columns]
        ].copy()
        if "proficiency_level" not in skill_lookup.columns:
            skill_lookup["proficiency_level"] = 3
    else:
        skill_lookup = pd.DataFrame(columns=["employee_id", "skill_id", "proficiency_level"])

    # --- 3. Clean allocations with dates ---
    alloc_clean = allocations_df.copy() if not allocations_df.empty else pd.DataFrame()
    if not alloc_clean.empty:
        alloc_clean["_s"] = pd.to_datetime(alloc_clean.get("start_date"), errors="coerce")
        alloc_clean["_e"] = pd.to_datetime(alloc_clean.get("end_date"), errors="coerce")
        if "allocation_percentage" in alloc_clean.columns:
            alloc_clean["_fte"] = alloc_clean["allocation_percentage"].astype(float) / 100.0
        elif "allocated_fte" in alloc_clean.columns:
            alloc_clean["_fte"] = alloc_clean["allocated_fte"].astype(float)
        else:
            alloc_clean["_fte"] = 0.5

    # --- 4. Clean approved leave with dates ---
    leave_clean = pd.DataFrame()
    if not leave_events_df.empty:
        app_col = "approval_status" if "approval_status" in leave_events_df.columns else None
        if app_col:
            leave_clean = leave_events_df[leave_events_df[app_col].str.upper() == "APPROVED"].copy()
        else:
            leave_clean = leave_events_df.copy()
        if not leave_clean.empty:
            leave_clean["_s"] = pd.to_datetime(leave_clean.get("start_date"), errors="coerce")
            leave_clean["_e"] = pd.to_datetime(leave_clean.get("end_date"), errors="coerce")
            leave_clean["_fte"] = (leave_clean.get("leave_hours", 0.0).astype(float) / 40.0).clip(upper=1.0)

    # --- 5. Critical priority projects ---
    critical_project_ids: set = set()
    if projects_df is not None and not projects_df.empty:
        priority_col = next((c for c in ("priority", "project_priority") if c in projects_df.columns), None)
        proj_id_col = "project_id" if "project_id" in projects_df.columns else None
        if priority_col and proj_id_col:
            crit = projects_df[projects_df[priority_col].str.upper() == "CRITICAL"]
            critical_project_ids = set(crit[proj_id_col].tolist())

    # --- 6. Process each demand group ---
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
    consumed_emp_capacity: dict[tuple, float] = {}

    for _, row in demand_grp.iterrows():
        skill_id = str(row[skill_demand_col]) if skill_demand_col else "UNKNOWN"
        role_id = str(row[role_col]) if role_col and role_col in row.index else "UNKNOWN"
        project_id = str(row[proj_col]) if proj_col and proj_col in row.index else "UNKNOWN"
        demand_fte = float(row["demand_fte"])
        req_prof = int(row["req_prof"]) if req_prof_col and "req_prof" in row.index else 1

        ps_ts = pd.to_datetime(row.get("period_start"))
        pe_ts = pd.to_datetime(row.get("period_end"))

        # Qualified active employees
        if not skill_lookup.empty:
            qualified_es = skill_lookup[
                (skill_lookup["skill_id"] == skill_id)
                & (skill_lookup["proficiency_level"].fillna(1) >= req_prof)
            ]
            active_ids = set(active_emp["employee_id"].tolist()) if not active_emp.empty else set()
            qualified_emp_ids = set(qualified_es["employee_id"]).intersection(active_ids)
            avg_prof = float(qualified_es["proficiency_level"].mean()) if not qualified_es.empty else 0.0
        else:
            qualified_emp_ids = set()
            avg_prof = 0.0

        proficiency_gap = max(0.0, req_prof - avg_prof)

        # Period-specific bench capacity across qualified employees
        qualified_supply_fte = 0.0
        bench_available = False

        for emp_id in qualified_emp_ids:
            contracted = emp_contracted_map.get(emp_id, 1.0)
            # Overlapping allocations
            if not alloc_clean.empty and pd.notna(ps_ts) and pd.notna(pe_ts):
                emp_allocs = alloc_clean[
                    (alloc_clean["employee_id"] == emp_id)
                    & (alloc_clean["_s"] <= pe_ts)
                    & (alloc_clean["_e"] >= ps_ts)
                ]
                committed_fte = float(emp_allocs["_fte"].sum())
            else:
                committed_fte = 0.0

            # Overlapping leave
            if not leave_clean.empty and pd.notna(ps_ts) and pd.notna(pe_ts):
                emp_leaves = leave_clean[
                    (leave_clean["employee_id"] == emp_id)
                    & (leave_clean["_s"] <= pe_ts)
                    & (leave_clean["_e"] >= ps_ts)
                ]
                leave_fte = float(emp_leaves["_fte"].sum())
            else:
                leave_fte = 0.0

            net_avail = max(0.0, contracted - committed_fte - leave_fte)
            cap_key = (emp_id, ps_ts, pe_ts)
            already_used = consumed_emp_capacity.get(cap_key, 0.0)
            remaining_usable = max(0.0, net_avail - already_used)

            if remaining_usable > 0:
                bench_available = True
                alloc_to_demand = min(remaining_usable, max(0.0, demand_fte - qualified_supply_fte))
                qualified_supply_fte += alloc_to_demand
                consumed_emp_capacity[cap_key] = already_used + alloc_to_demand

        # FTE shortage (never compare headcount to FTE)
        shortage = max(0.0, demand_fte - qualified_supply_fte)

        training_time_available = False
        if pd.notna(ps_ts) and pd.notna(pe_ts):
            weeks = (pe_ts - ps_ts).days / 7
            training_time_available = weeks >= 4

        is_critical = project_id in critical_project_ids
        severity = _gap_severity(shortage)

        action, reasoning = _recommend_action(
            shortage=shortage,
            proficiency_gap=proficiency_gap,
            bench_available=bench_available,
            training_time_available=training_time_available,
            is_critical_priority=is_critical,
        )

        ps_date = ps_ts.date() if pd.notna(ps_ts) else period_start
        pe_date = pe_ts.date() if pd.notna(pe_ts) else period_end

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
    leave_events_df = _load_csv("leave_events.csv")

    return _compute_gap_recommendations(
        demand_df=demand_df,
        employees_df=employees_df,
        employee_skills_df=employee_skills_df,
        allocations_df=allocations_df,
        projects_df=projects_df,
        leave_events_df=leave_events_df,
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
