"""
Workforce Analytics & Metrics Computation Service.

Calculates enterprise workforce KPIs, skill coverage, department capacity breakdowns,
and historical/projected utilization trends.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from src.services.db_service import (
    get_active_employees,
    get_availability,
    get_skills,
    get_employee_skills,
    get_allocations,
    get_demand_plans,
    get_gap_analyses,
    get_training,
    get_leave_events,
)

logger = logging.getLogger(__name__)


@dataclass
class WorkforceKPIs:
    total_headcount: int
    active_headcount: int
    contractors_count: int
    avg_utilization_pct: float
    bench_count: int
    on_leave_count: int
    skills_tracked: int
    active_gaps_count: int


def get_workforce_kpis() -> WorkforceKPIs:
    """Calculates high-level executive dashboard metrics."""
    emp_df = get_active_employees()
    avail_df = get_availability()
    skills_df = get_skills()
    gaps_df = get_gap_analyses()

    total = len(emp_df)
    active = len(emp_df[emp_df["status"] == "ACTIVE"]) if "status" in emp_df.columns else total
    contractors = len(emp_df[emp_df["employment_type"] == "CONTRACTOR"]) if "employment_type" in emp_df.columns else 0

    avg_util = 0.0
    bench = 0
    on_leave = 0

    if not avail_df.empty:
        if "availability_percentage" in avail_df.columns:
            # utilization = 100 - availability %
            avg_util = round(float(100.0 - avail_df["availability_percentage"].mean()), 1)
            avg_util = max(0.0, min(100.0, avg_util))
        if "availability_type" in avail_df.columns:
            bench = len(avail_df[avail_df["availability_type"] == "AVAILABLE_BENCH"])
            on_leave = len(avail_df[avail_df["availability_type"] == "ON_APPROVED_LEAVE"])

    active_gaps = 0
    if not gaps_df.empty:
        if "status" in gaps_df.columns:
            active_gaps = len(gaps_df[gaps_df["status"].isin(["OPEN", "IN_REVIEW", "ACTION_PLANNED"])])
        else:
            active_gaps = len(gaps_df)

    return WorkforceKPIs(
        total_headcount=total,
        active_headcount=active,
        contractors_count=contractors,
        avg_utilization_pct=avg_util,
        bench_count=bench,
        on_leave_count=on_leave,
        skills_tracked=len(skills_df),
        active_gaps_count=active_gaps,
    )


def get_department_breakdown() -> pd.DataFrame:
    """Calculates department-level headcount and average capacity."""
    emp_df = get_active_employees()
    if emp_df.empty or "department" not in emp_df.columns:
        return pd.DataFrame(columns=["department", "headcount", "avg_fte"])

    dept_summary = emp_df.groupby("department").agg(
        headcount=("employee_id", "count"),
        avg_fte=("fte", "mean") if "fte" in emp_df.columns else ("employee_id", lambda x: 1.0)
    ).reset_index()

    dept_summary["avg_fte"] = dept_summary["avg_fte"].round(2)
    return dept_summary.sort_values(by="headcount", ascending=False)


def get_skill_coverage_matrix() -> pd.DataFrame:
    """Aggregates skills with verified employee proficiency distribution."""
    skills_df = get_skills()
    esk_df = get_employee_skills()

    if skills_df.empty or esk_df.empty:
        return pd.DataFrame(columns=["skill_name", "category", "expert_count", "proficient_count", "beginner_count", "total_trained"])

    merged = pd.merge(esk_df, skills_df, on="skill_id", how="inner")
    
    summary = merged.groupby(["skill_name", "category"]).agg(
        total_trained=("employee_id", "count"),
        expert_count=("proficiency_level", lambda p: (p >= 4).sum()),
        proficient_count=("proficiency_level", lambda p: (p == 3).sum()),
        beginner_count=("proficiency_level", lambda p: (p <= 2).sum()),
        avg_proficiency=("proficiency_level", "mean"),
    ).reset_index()

    summary["avg_proficiency"] = summary["avg_proficiency"].round(1)
    return summary.sort_values(by="total_trained", ascending=False)


def get_monthly_utilization_trend() -> pd.DataFrame:
    """
    Calculates 12-month workforce capacity vs allocation trend from actual data.

    For each calendar month in 2026:
      - Total contracted capacity = sum of (standard_hours_per_week * fte * weeks_in_month)
        across all active employees.
      - Approved leave hours deducted from contracted capacity to yield net capacity.
      - Allocated hours derived from actual project allocations overlapping the month.
      - Utilization % = allocated_hours / net_capacity_hours * 100 (0% when net_capacity is zero).
    """
    import calendar

    emp_df = get_active_employees()
    alloc_df = get_allocations()
    leave_df = get_leave_events()

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    rows = []

    if emp_df.empty:
        return pd.DataFrame(columns=[
            "month", "period", "total_capacity_hours", "net_capacity_hours",
            "allocated_hours", "bench_hours", "utilization_pct",
        ])

    # Prepare employee FTE and weekly hours
    emp_clean = emp_df.copy()
    emp_clean["_fte"] = emp_clean["fte"].astype(float) if "fte" in emp_clean.columns else 1.0
    emp_clean["_weekly_hrs"] = (
        emp_clean["standard_hours_per_week"].astype(float)
        if "standard_hours_per_week" in emp_clean.columns else 40.0
    )
    emp_contracted_map = dict(zip(emp_clean["employee_id"], emp_clean["_weekly_hrs"] * emp_clean["_fte"]))
    total_weekly_contracted = float((emp_clean["_weekly_hrs"] * emp_clean["_fte"]).sum())

    # Prepare allocations with dates and precomputed fte/pct
    alloc_records = []
    if not alloc_df.empty:
        a_df = alloc_df.copy()
        a_df["_s"] = pd.to_datetime(a_df.get("start_date"), errors="coerce")
        a_df["_e"] = pd.to_datetime(a_df.get("end_date"), errors="coerce")
        for _, r in a_df.iterrows():
            if pd.notna(r["_s"]) and pd.notna(r["_e"]):
                eid = r.get("employee_id")
                pct = float(r["allocation_percentage"]) if "allocation_percentage" in r.index and pd.notna(r["allocation_percentage"]) else None
                fte_val = float(r["allocated_fte"]) if "allocated_fte" in r.index and pd.notna(r["allocated_fte"]) else None
                alloc_records.append((r["_s"], r["_e"], eid, pct, fte_val))

    # Prepare approved leave with dates
    leave_records = []
    if not leave_df.empty:
        l_df = leave_df.copy()
        app_col = "approval_status" if "approval_status" in l_df.columns else None
        if app_col:
            l_df = l_df[l_df[app_col].astype(str).str.upper() == "APPROVED"].copy()
        l_df["_s"] = pd.to_datetime(l_df.get("start_date"), errors="coerce")
        l_df["_e"] = pd.to_datetime(l_df.get("end_date"), errors="coerce")
        for _, r in l_df.iterrows():
            if pd.notna(r["_s"]) and pd.notna(r["_e"]):
                leave_records.append((r["_s"], r["_e"], float(r.get("leave_hours", 0.0) or 0.0)))

    for month_idx in range(1, 13):
        month_label = months[month_idx - 1]
        _, days_in_month = calendar.monthrange(2026, month_idx)
        m_start = pd.Timestamp(2026, month_idx, 1)
        m_end = pd.Timestamp(2026, month_idx, days_in_month)
        approx_weeks = days_in_month / 7.0

        # 1. Total contracted capacity for the month
        total_contracted = total_weekly_contracted * approx_weeks

        # 2. Approved leave hours overlapping this month
        total_leave_hours = sum(hrs for s, e, hrs in leave_records if s <= m_end and e >= m_start)

        # 3. Net capacity after leave
        net_capacity = max(0.0, total_contracted - total_leave_hours)

        # 4. Allocated hours from project allocations overlapping the month
        total_allocated = 0.0
        for s, e, eid, pct, fte_val in alloc_records:
            if s <= m_end and e >= m_start:
                contracted_weekly = emp_contracted_map.get(eid)
                if contracted_weekly is None:
                    continue
                if pct is not None:
                    total_allocated += contracted_weekly * approx_weeks * (pct / 100.0)
                elif fte_val is not None:
                    total_allocated += fte_val * 40.0 * approx_weeks
                else:
                    total_allocated += contracted_weekly * approx_weeks * 0.5

        # 5. Utilization %
        if net_capacity > 0.0:
            util_pct = round(min(100.0, (total_allocated / net_capacity) * 100.0), 1)
        else:
            util_pct = 0.0 if total_allocated == 0.0 else 100.0

        bench_hours = round(max(0.0, net_capacity - total_allocated), 1)

        rows.append({
            "month": month_label,
            "period": f"2026-{month_idx:02d}",
            "total_capacity_hours": round(total_contracted, 1),
            "net_capacity_hours": round(net_capacity, 1),
            "allocated_hours": round(total_allocated, 1),
            "bench_hours": bench_hours,
            "utilization_pct": util_pct,
        })

    return pd.DataFrame(rows)


def get_recommendation_action_split() -> pd.DataFrame:
    """Aggregates hiring vs upskilling recommendation breakdown from gap analysis."""
    gaps_df = get_gap_analyses()
    if gaps_df.empty or "recommended_action" not in gaps_df.columns:
        return pd.DataFrame(columns=["action", "count", "pct"])
    
    counts = gaps_df["recommended_action"].value_counts().reset_index()
    counts.columns = ["action", "count"]
    total = counts["count"].sum()
    counts["pct"] = ((counts["count"] / total) * 100).round(1)
    return counts
