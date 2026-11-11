"""
Unit tests for Capacity & Availability calculations ensuring FTE and approved leave affect capacity.
"""

from decimal import Decimal
from src.services.capacity_service import calculate_capacity


def test_full_time_unallocated_full_capacity():
    """1.0 FTE, 40h base, no leave, no allocation -> 40h available, 100% bench."""
    metrics = calculate_capacity(base_hours=40.0, fte=1.0, approved_leave_hours=0.0, allocated_hours=0.0)
    assert metrics.contracted_capacity_hours == Decimal("40.00")
    assert metrics.net_available_hours == Decimal("40.00")
    assert metrics.availability_percentage == Decimal("100.00")
    assert metrics.availability_type == "AVAILABLE_BENCH"


def test_part_time_fte_scaling():
    """0.5 FTE scales 40h base to 20h contracted capacity."""
    metrics = calculate_capacity(base_hours=40.0, fte=0.5, approved_leave_hours=0.0, allocated_hours=0.0)
    assert metrics.contracted_capacity_hours == Decimal("20.00")
    assert metrics.net_available_hours == Decimal("20.00")
    assert metrics.availability_percentage == Decimal("100.00")


def test_approved_leave_reduces_capacity():
    """1.0 FTE (40h) with 16h approved leave leaves 24h available."""
    metrics = calculate_capacity(base_hours=40.0, fte=1.0, approved_leave_hours=16.0, allocated_hours=0.0)
    assert metrics.contracted_capacity_hours == Decimal("40.00")
    assert metrics.net_available_hours == Decimal("24.00")
    assert metrics.availability_percentage == Decimal("60.00")
    assert metrics.availability_type == "PARTIALLY_ALLOCATED"


def test_full_week_approved_leave():
    """Full week approved leave (40h) results in 0h available, ON_APPROVED_LEAVE."""
    metrics = calculate_capacity(base_hours=40.0, fte=1.0, approved_leave_hours=40.0, allocated_hours=0.0)
    assert metrics.net_available_hours == Decimal("0.00")
    assert metrics.availability_percentage == Decimal("0.00")
    assert metrics.availability_type == "ON_APPROVED_LEAVE"


def test_fte_and_leave_and_allocation_combined():
    """
    0.75 FTE (30h capacity).
    Approved leave: 10h -> Remaining capacity = 20h.
    Project allocation: 15h -> Net available = 5h.
    Availability % = (5 / 30) * 100 = 16.67%.
    """
    metrics = calculate_capacity(base_hours=40.0, fte=0.75, approved_leave_hours=10.0, allocated_hours=15.0)
    assert metrics.contracted_capacity_hours == Decimal("30.00")
    assert metrics.net_available_hours == Decimal("5.00")
    assert metrics.availability_percentage == Decimal("16.67")
    assert metrics.availability_type == "PARTIALLY_ALLOCATED"


def test_fully_allocated():
    """1.0 FTE (40h), 0h leave, 40h allocated -> 0h net, FULLY_ALLOCATED."""
    metrics = calculate_capacity(base_hours=40.0, fte=1.0, approved_leave_hours=0.0, allocated_hours=40.0)
    assert metrics.net_available_hours == Decimal("0.00")
    assert metrics.availability_percentage == Decimal("0.00")
    assert metrics.availability_type == "FULLY_ALLOCATED"


def test_over_allocation_detection():
    """1.0 FTE (40h), 0h leave, 50h allocated -> remaining -10h, 25% over-allocation."""
    metrics = calculate_capacity(base_hours=40.0, fte=1.0, approved_leave_hours=0.0, allocated_hours=50.0)
    assert metrics.contracted_capacity_hours == Decimal("40.00")
    assert metrics.net_capacity_hours == Decimal("40.00")
    assert metrics.remaining_capacity_hours == Decimal("-10.00")
    assert metrics.over_allocation_percentage == Decimal("25.00")
    assert metrics.capacity_status == "OVER_ALLOCATED"
    assert metrics.net_available_hours == Decimal("0.00")


def test_zero_capacity_boundary():
    """0 FTE or 0 base hours must not raise ZeroDivisionError and return clean zeros."""
    metrics = calculate_capacity(base_hours=0.0, fte=0.0, approved_leave_hours=0.0, allocated_hours=0.0)
    assert metrics.contracted_capacity_hours == Decimal("0.00")
    assert metrics.net_capacity_hours == Decimal("0.00")
    assert metrics.remaining_capacity_hours == Decimal("0.00")
    assert metrics.utilization_percentage == Decimal("0.00")
    assert metrics.over_allocation_percentage == Decimal("0.00")


def test_leave_exceeds_contracted_capacity_boundary():
    """Approved leave exceeding contracted capacity (e.g. 50h on 40h contract)."""
    metrics = calculate_capacity(base_hours=40.0, fte=1.0, approved_leave_hours=50.0, allocated_hours=0.0)
    assert metrics.net_capacity_hours == Decimal("-10.00")
    assert metrics.capacity_status == "ON_APPROVED_LEAVE"


def test_source_driven_weekly_reconciliation_multi_project():
    """Test period reconciliation with multiple projects and approved leave."""
    import pandas as pd
    from src.services.capacity_service import reconcile_employee_period_capacity

    allocations_df = pd.DataFrame([
        {
            "allocation_id": "AL-1",
            "employee_id": "EMP-001",
            "project_id": "PRJ-1",
            "start_date": "2026-06-01",
            "end_date": "2026-06-30",
            "allocation_percentage": 50,  # 20 hours
        },
        {
            "allocation_id": "AL-2",
            "employee_id": "EMP-001",
            "project_id": "PRJ-2",
            "start_date": "2026-06-01",
            "end_date": "2026-06-15",
            "allocation_percentage": 30,  # 12 hours
        },
    ])
    leave_df = pd.DataFrame([
        {
            "leave_id": "LV-1",
            "employee_id": "EMP-001",
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "leave_hours": 8.0,
            "approval_status": "APPROVED",
        }
    ])

    rec = reconcile_employee_period_capacity(
        employee_id="EMP-001",
        fte=1.0,
        period_start="2026-06-01",
        period_end="2026-06-07",
        allocations_df=allocations_df,
        leave_events_df=leave_df,
        base_hours=40.0,
    )

    # Contracted = 40.0h, Leave = 8.0h -> Net = 32.0h
    # Allocated = 20.0 + 12.0 = 32.0h -> Remaining = 0.0h
    # Utilization = (32 / 32) * 100 = 100% -> FULLY_ALLOCATED
    assert rec["contracted_hours"] == 40.0
    assert rec["approved_leave_hours"] == 8.0
    assert rec["net_capacity_hours"] == 32.0
    assert rec["allocated_hours"] == 32.0
    assert rec["remaining_capacity_hours"] == 0.0
    assert rec["utilization_percentage"] == 100.0
    assert rec["capacity_status"] == "FULLY_ALLOCATED"
    assert set(rec["active_allocation_ids"]) == {"AL-1", "AL-2"}

