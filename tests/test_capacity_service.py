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
