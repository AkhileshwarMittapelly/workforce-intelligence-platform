"""
Capacity and Availability Calculation Service.

Implements source-driven, employee-level, period-level capacity engine ensuring FTE and
approved leave properly affect capacity without premature clamping of negative balances.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@dataclass(frozen=True)
class CapacityMetrics:
    base_capacity_hours: Decimal
    fte: Decimal
    contracted_capacity_hours: Decimal
    approved_leave_hours: Decimal
    allocated_hours: Decimal
    net_available_hours: Decimal
    availability_percentage: Decimal
    availability_type: str
    utilization_percentage: Decimal = Decimal("0.00")
    net_capacity_hours: Decimal = Decimal("0.00")
    remaining_capacity_hours: Decimal = Decimal("0.00")
    over_allocation_percentage: Decimal = Decimal("0.00")
    capacity_status: str = "AVAILABLE_BENCH"


def calculate_capacity(
    base_hours: float | Decimal = 40.0,
    fte: float | Decimal = 1.0,
    approved_leave_hours: float | Decimal = 0.0,
    allocated_hours: float | Decimal = 0.0,
) -> CapacityMetrics:
    """
    Computes capacity and availability for an employee over a specific period.

    Rules:
    1. Contracted capacity = base_hours * fte
    2. Net capacity = contracted_capacity - approved_leave
    3. Remaining capacity = net_capacity - allocated_hours (NOT clamped before checking over-allocation)
    4. Over-allocation % = abs(remaining_capacity) / contracted_capacity * 100 when remaining_capacity < 0
    5. Utilization % = (allocated / net_capacity) * 100 (when net_capacity > 0)
    """
    base = Decimal(str(base_hours)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    f = Decimal(str(fte)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    leave = Decimal(str(approved_leave_hours)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    allocated = Decimal(str(allocated_hours)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 1. Contracted capacity adjusted by FTE
    contracted = (base * f).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 2. Net capacity after leave (unclamped)
    net_capacity = (contracted - leave).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 3. Remaining capacity after allocation (unclamped: negative indicates over-allocation)
    remaining_capacity = (net_capacity - allocated).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Clamped net available hours (for legacy availability percentage display)
    net_available = max(Decimal("0.00"), remaining_capacity)

    # 4. Availability Percentage (0% to 100%)
    if contracted > Decimal("0.00"):
        raw_pct = (net_available / contracted) * Decimal("100.00")
        pct = min(Decimal("100.00"), max(Decimal("0.00"), raw_pct)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        pct = Decimal("0.00")

    # 5. Utilization Percentage
    if net_capacity > Decimal("0.00"):
        util_pct = ((allocated / net_capacity) * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    elif allocated > Decimal("0.00"):
        util_pct = Decimal("100.00")
    else:
        util_pct = Decimal("0.00")

    # 6. Over-allocation Percentage
    if remaining_capacity < Decimal("0.00") and contracted > Decimal("0.00"):
        over_pct = ((abs(remaining_capacity) / contracted) * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        over_pct = Decimal("0.00")

    # 7. Status classification
    if leave >= contracted and contracted > Decimal("0.00") and allocated == Decimal("0.00"):
        cap_status = "ON_APPROVED_LEAVE"
        avail_type = "ON_APPROVED_LEAVE"
    elif remaining_capacity < Decimal("0.00"):
        cap_status = "OVER_ALLOCATED"
        avail_type = "PARTIALLY_ALLOCATED" if net_available > Decimal("0.00") else "FULLY_ALLOCATED"
    elif leave >= contracted and contracted > Decimal("0.00"):
        cap_status = "ON_APPROVED_LEAVE"
        avail_type = "ON_APPROVED_LEAVE"
    elif net_available == Decimal("0.00") and allocated > Decimal("0.00"):
        cap_status = "FULLY_ALLOCATED"
        avail_type = "FULLY_ALLOCATED"
    elif net_available < contracted:
        cap_status = "PARTIALLY_ALLOCATED"
        avail_type = "PARTIALLY_ALLOCATED"
    else:
        cap_status = "AVAILABLE_BENCH"
        avail_type = "AVAILABLE_BENCH"

    return CapacityMetrics(
        base_capacity_hours=base,
        fte=f,
        contracted_capacity_hours=contracted,
        approved_leave_hours=leave,
        allocated_hours=allocated,
        net_available_hours=net_available,
        availability_percentage=pct,
        availability_type=avail_type,
        utilization_percentage=util_pct,
        net_capacity_hours=net_capacity,
        remaining_capacity_hours=remaining_capacity,
        over_allocation_percentage=over_pct,
        capacity_status=cap_status,
    )


def reconcile_employee_period_capacity(
    employee_id: str,
    fte: float,
    period_start: str | date,
    period_end: str | date,
    allocations_df: Optional[pd.DataFrame] = None,
    leave_events_df: Optional[pd.DataFrame] = None,
    base_hours: float = 40.0,
    emp_allocations: Optional[list[dict]] = None,
    emp_leaves: Optional[list[dict]] = None,
) -> Dict[str, Any]:
    """
    Source-driven reconciliation for an individual employee during a specific period.
    Filters source allocations and approved leave strictly within the period interval.
    """
    ps_ts = pd.to_datetime(period_start)
    pe_ts = pd.to_datetime(period_end)

    # 1. Reconcile approved leave hours during period
    leave_hours = 0.0
    if emp_leaves is not None:
        for l_item in emp_leaves:
            s = l_item.get("_s")
            e = l_item.get("_e")
            if (s is None or s <= pe_ts) and (e is None or e >= ps_ts):
                leave_hours += float(l_item.get("leave_hours", 0.0))
    elif leave_events_df is not None and not leave_events_df.empty:
        l_df = leave_events_df.copy()
        l_df.columns = [c.strip().lower() for c in l_df.columns]
        app_col = next((c for c in ("approval_status", "status") if c in l_df.columns), None)
        if app_col:
            l_df = l_df[l_df[app_col].astype(str).str.upper() == "APPROVED"]

        if not l_df.empty and "start_date" in l_df.columns and "end_date" in l_df.columns:
            l_df["_s"] = pd.to_datetime(l_df["start_date"], errors="coerce")
            l_df["_e"] = pd.to_datetime(l_df["end_date"], errors="coerce")
            emp_leaves_df = l_df[
                (l_df["employee_id"] == employee_id)
                & (l_df["_s"] <= pe_ts)
                & (l_df["_e"] >= ps_ts)
            ]
            if not emp_leaves_df.empty:
                leave_hours = float(emp_leaves_df["leave_hours"].astype(float).sum())

    # 2. Reconcile allocated hours during period
    allocated_hours = 0.0
    allocation_ids = []
    contracted_hrs = base_hours * fte

    if emp_allocations is not None:
        for a_item in emp_allocations:
            s = a_item.get("_s")
            e = a_item.get("_e")
            if (s is None or s <= pe_ts) and (e is None or e >= ps_ts):
                if a_item.get("allocation_id"):
                    allocation_ids.append(a_item["allocation_id"])
                if "allocation_percentage" in a_item and pd.notna(a_item["allocation_percentage"]):
                    allocated_hours += float(a_item["allocation_percentage"]) / 100.0 * contracted_hrs
                elif "allocated_fte" in a_item and pd.notna(a_item["allocated_fte"]):
                    allocated_hours += float(a_item["allocated_fte"]) * 40.0
                elif "allocated_hours" in a_item and pd.notna(a_item["allocated_hours"]):
                    allocated_hours += float(a_item["allocated_hours"])
    elif allocations_df is not None and not allocations_df.empty:
        a_df = allocations_df.copy()
        a_df.columns = [c.strip().lower() for c in a_df.columns]
        if "start_date" in a_df.columns and "end_date" in a_df.columns:
            a_df["_s"] = pd.to_datetime(a_df["start_date"], errors="coerce")
            a_df["_e"] = pd.to_datetime(a_df["end_date"], errors="coerce")
            emp_allocs = a_df[
                (a_df["employee_id"] == employee_id)
                & (a_df["_s"] <= pe_ts)
                & (a_df["_e"] >= ps_ts)
            ]
            if not emp_allocs.empty:
                allocation_ids = emp_allocs["allocation_id"].tolist()
                if "allocation_percentage" in emp_allocs.columns:
                    allocated_hours = float(
                        (emp_allocs["allocation_percentage"].astype(float) / 100.0 * contracted_hrs).sum()
                    )
                elif "allocated_fte" in emp_allocs.columns:
                    allocated_hours = float((emp_allocs["allocated_fte"].astype(float) * 40.0).sum())
                elif "allocated_hours" in emp_allocs.columns:
                    allocated_hours = float(emp_allocs["allocated_hours"].astype(float).sum())

    metrics = calculate_capacity(
        base_hours=base_hours,
        fte=fte,
        approved_leave_hours=leave_hours,
        allocated_hours=allocated_hours,
    )

    return {
        "employee_id": employee_id,
        "period_start": str(period_start),
        "period_end": str(period_end),
        "fte": fte,
        "base_hours": float(metrics.base_capacity_hours),
        "contracted_hours": float(metrics.contracted_capacity_hours),
        "approved_leave_hours": float(metrics.approved_leave_hours),
        "net_capacity_hours": float(metrics.net_capacity_hours),
        "allocated_hours": float(metrics.allocated_hours),
        "remaining_capacity_hours": float(metrics.remaining_capacity_hours),
        "utilization_percentage": float(metrics.utilization_percentage),
        "over_allocation_percentage": float(metrics.over_allocation_percentage),
        "capacity_status": metrics.capacity_status,
        "active_allocation_ids": allocation_ids,
    }


def reconcile_weekly_capacities_df(
    data_dir: Optional[Path | str] = None,
    period_start: Optional[str | date] = None,
    period_end: Optional[str | date] = None,
) -> pd.DataFrame:
    """
    Source-driven weekly capacity reconciliation engine across all employees.
    """
    d_dir = Path(data_dir) if data_dir else DATA_DIR
    emp_file = d_dir / "employees.csv"
    alloc_file = d_dir / "allocations.csv"
    leave_file = d_dir / "leave_events.csv"

    if not emp_file.exists():
        return pd.DataFrame()

    emp_df = pd.read_csv(emp_file, low_memory=False)
    alloc_df = pd.read_csv(alloc_file, low_memory=False) if alloc_file.exists() else pd.DataFrame()
    leave_df = pd.read_csv(leave_file, low_memory=False) if leave_file.exists() else pd.DataFrame()

    # Determine default evaluation week if not provided
    p_start = period_start if period_start else "2026-06-01"
    p_end = period_end if period_end else "2026-06-07"

    # Pre-filter allocations and leave to the target period for high performance
    p_s_ts = pd.to_datetime(p_start)
    p_e_ts = pd.to_datetime(p_end)
    if not alloc_df.empty and "start_date" in alloc_df.columns and "end_date" in alloc_df.columns:
        alloc_df.columns = [c.strip().lower() for c in alloc_df.columns]
        alloc_df["_s"] = pd.to_datetime(alloc_df["start_date"], errors="coerce")
        alloc_df["_e"] = pd.to_datetime(alloc_df["end_date"], errors="coerce")
        alloc_df = alloc_df[(alloc_df["_s"] <= p_e_ts) & (alloc_df["_e"] >= p_s_ts)].copy()

    if not leave_df.empty and "start_date" in leave_df.columns and "end_date" in leave_df.columns:
        leave_df.columns = [c.strip().lower() for c in leave_df.columns]
        app_col = next((c for c in ("approval_status", "status") if c in leave_df.columns), None)
        if app_col:
            leave_df = leave_df[leave_df[app_col].astype(str).str.upper() == "APPROVED"]
        leave_df["_s"] = pd.to_datetime(leave_df["start_date"], errors="coerce")
        leave_df["_e"] = pd.to_datetime(leave_df["end_date"], errors="coerce")
        leave_df = leave_df[(leave_df["_s"] <= p_e_ts) & (leave_df["_e"] >= p_s_ts)].copy()

    # Pre-index allocations and leave into dicts for O(1) employee lookup
    alloc_by_emp: dict[str, list[dict]] = {}
    if not alloc_df.empty:
        for r in alloc_df.to_dict(orient="records"):
            eid = str(r.get("employee_id", ""))
            alloc_by_emp.setdefault(eid, []).append(r)

    leave_by_emp: dict[str, list[dict]] = {}
    if not leave_df.empty:
        for r in leave_df.to_dict(orient="records"):
            eid = str(r.get("employee_id", ""))
            leave_by_emp.setdefault(eid, []).append(r)

    records = []
    active_emps = emp_df[emp_df["status"].astype(str).str.upper() == "ACTIVE"] if "status" in emp_df.columns else emp_df
    for emp in active_emps.to_dict(orient="records"):
        eid = str(emp["employee_id"])
        fte = float(emp.get("fte", 1.0))
        rec = reconcile_employee_period_capacity(
            employee_id=eid,
            fte=fte,
            period_start=p_start,
            period_end=p_end,
            base_hours=float(emp.get("standard_hours_per_week", 40.0)),
            emp_allocations=alloc_by_emp.get(eid, []),
            emp_leaves=leave_by_emp.get(eid, []),
        )
        rec["department"] = emp.get("department", "Unknown")
        rec["employee_name"] = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
        records.append(rec)

    return pd.DataFrame(records)
