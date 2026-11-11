"""
Capacity and Availability Calculation Service.

Implements business logic ensuring FTE and approved leave properly affect capacity,
without relying on cross-table MySQL generated columns.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


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
    2. Net available capacity = max(0, contracted_capacity - approved_leave - allocated)
    3. Availability % = (net_available / contracted_capacity) * 100 (capped at 100%, 0% if no contracted capacity)
    4. Categorizes availability type based on leave, allocation, and remaining bench hours.
    """
    base = Decimal(str(base_hours)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    f = Decimal(str(fte)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    leave = Decimal(str(approved_leave_hours)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    allocated = Decimal(str(allocated_hours)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 1. Contracted capacity adjusted by FTE
    contracted = (base * f).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 2. Net available hours after approved leave and committed allocations
    remaining_after_leave = max(Decimal("0.00"), contracted - leave)
    net_available = max(Decimal("0.00"), remaining_after_leave - allocated).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 3. Availability percentage
    if contracted > Decimal("0.00"):
        raw_pct = (net_available / contracted) * Decimal("100.00")
        pct = min(Decimal("100.00"), max(Decimal("0.00"), raw_pct)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        pct = Decimal("0.00")

    # 4. Determine availability classification
    if leave >= contracted and contracted > Decimal("0.00"):
        avail_type = "ON_APPROVED_LEAVE"
    elif net_available == Decimal("0.00"):
        avail_type = "FULLY_ALLOCATED"
    elif net_available < contracted:
        avail_type = "PARTIALLY_ALLOCATED"
    else:
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
    )
