"""
What-If Scenario Simulation Service.

Provides non-destructive simulation capabilities for workforce planning:
  - Demand change simulation (+10/20/30%)
  - Employee resignation impact
  - New hire impact
  - Training completion impact
  - Deadline shift impact

All simulations operate on copies of source data and never mutate production files.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _load_csv(name: str, data_dir: Optional[Path] = None) -> pd.DataFrame:
    path = (data_dir or DATA_DIR) / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


@dataclass
class SimulationResult:
    """Result of a what-if simulation."""
    scenario_name: str
    baseline_demand_fte: float
    simulated_demand_fte: float
    baseline_supply_fte: float
    simulated_supply_fte: float
    baseline_gap: float
    simulated_gap: float
    gap_delta: float
    impact_summary: str
    details: List[Dict[str, Any]] = field(default_factory=list)


def _compute_baseline(data_dir: Optional[Path] = None) -> Dict[str, float]:
    """Compute baseline demand, supply, gap from current data."""
    d_dir = data_dir or DATA_DIR
    demand_df = _load_csv("demand_plans.csv", d_dir)
    employees_df = _load_csv("employees.csv", d_dir)
    allocations_df = _load_csv("allocations.csv", d_dir)

    total_demand = 0.0
    if not demand_df.empty:
        demand_df.columns = [c.strip().lower() for c in demand_df.columns]
        fte_col = "required_fte" if "required_fte" in demand_df.columns else "demand_fte"
        if fte_col in demand_df.columns:
            total_demand = float(demand_df[fte_col].sum())

    total_supply = 0.0
    if not employees_df.empty:
        employees_df.columns = [c.strip().lower() for c in employees_df.columns]
        if "status" in employees_df.columns:
            active = employees_df[employees_df["status"].str.upper() == "ACTIVE"]
        else:
            active = employees_df
        if "fte" in active.columns:
            total_supply = float(active["fte"].astype(float).sum())
        else:
            total_supply = float(len(active))

    return {
        "demand_fte": total_demand,
        "supply_fte": total_supply,
        "gap": max(0.0, total_demand - total_supply),
    }


def simulate_demand_change(
    change_pct: float = 10.0,
    data_dir: Optional[Path] = None,
) -> SimulationResult:
    """
    Simulate a percentage change in workforce demand.

    Args:
        change_pct: Percentage change (positive = increase, negative = decrease).
    """
    baseline = _compute_baseline(data_dir)
    multiplier = 1.0 + (change_pct / 100.0)
    sim_demand = baseline["demand_fte"] * multiplier
    sim_gap = max(0.0, sim_demand - baseline["supply_fte"])

    return SimulationResult(
        scenario_name=f"Demand {'Increase' if change_pct > 0 else 'Decrease'} {change_pct:+.0f}%",
        baseline_demand_fte=round(baseline["demand_fte"], 2),
        simulated_demand_fte=round(sim_demand, 2),
        baseline_supply_fte=round(baseline["supply_fte"], 2),
        simulated_supply_fte=round(baseline["supply_fte"], 2),
        baseline_gap=round(baseline["gap"], 2),
        simulated_gap=round(sim_gap, 2),
        gap_delta=round(sim_gap - baseline["gap"], 2),
        impact_summary=(
            f"A {change_pct:+.0f}% demand change moves total demand from "
            f"{baseline['demand_fte']:.1f} to {sim_demand:.1f} FTE, "
            f"{'increasing' if sim_gap > baseline['gap'] else 'decreasing'} the gap by "
            f"{abs(sim_gap - baseline['gap']):.1f} FTE."
        ),
    )


def simulate_resignations(
    resignation_count: int = 5,
    department: Optional[str] = None,
    data_dir: Optional[Path] = None,
) -> SimulationResult:
    """
    Simulate the impact of employee resignations on workforce capacity.
    """
    d_dir = data_dir or DATA_DIR
    baseline = _compute_baseline(d_dir)
    employees_df = _load_csv("employees.csv", d_dir)

    if employees_df.empty:
        return SimulationResult(
            scenario_name=f"Resignations ({resignation_count})",
            baseline_demand_fte=baseline["demand_fte"],
            simulated_demand_fte=baseline["demand_fte"],
            baseline_supply_fte=baseline["supply_fte"],
            simulated_supply_fte=baseline["supply_fte"],
            baseline_gap=baseline["gap"],
            simulated_gap=baseline["gap"],
            gap_delta=0.0,
            impact_summary="No employee data available for simulation.",
        )

    employees_df.columns = [c.strip().lower() for c in employees_df.columns]
    if "status" in employees_df.columns:
        active = employees_df[employees_df["status"].str.upper() == "ACTIVE"].copy()
    else:
        active = employees_df.copy()

    if department and "department" in active.columns:
        active = active[active["department"] == department]

    n = min(resignation_count, len(active))
    resigned = active.head(n)
    fte_lost = float(resigned["fte"].astype(float).sum()) if "fte" in resigned.columns else float(n)

    sim_supply = max(0.0, baseline["supply_fte"] - fte_lost)
    sim_gap = max(0.0, baseline["demand_fte"] - sim_supply)

    dept_msg = f" from {department}" if department else ""
    return SimulationResult(
        scenario_name=f"Resignations ({n} employees{dept_msg})",
        baseline_demand_fte=round(baseline["demand_fte"], 2),
        simulated_demand_fte=round(baseline["demand_fte"], 2),
        baseline_supply_fte=round(baseline["supply_fte"], 2),
        simulated_supply_fte=round(sim_supply, 2),
        baseline_gap=round(baseline["gap"], 2),
        simulated_gap=round(sim_gap, 2),
        gap_delta=round(sim_gap - baseline["gap"], 2),
        impact_summary=(
            f"Losing {n} employees{dept_msg} reduces supply by {fte_lost:.1f} FTE, "
            f"increasing the gap by {sim_gap - baseline['gap']:.1f} FTE."
        ),
        details=[{"resigned_count": n, "fte_lost": round(fte_lost, 2), "department": department or "ALL"}],
    )


def simulate_new_hires(
    hire_count: int = 10,
    avg_fte: float = 1.0,
    data_dir: Optional[Path] = None,
) -> SimulationResult:
    """Simulate the impact of new hires on supply capacity."""
    baseline = _compute_baseline(data_dir)
    fte_gained = hire_count * avg_fte
    sim_supply = baseline["supply_fte"] + fte_gained
    sim_gap = max(0.0, baseline["demand_fte"] - sim_supply)

    return SimulationResult(
        scenario_name=f"New Hires ({hire_count} @ {avg_fte} FTE each)",
        baseline_demand_fte=round(baseline["demand_fte"], 2),
        simulated_demand_fte=round(baseline["demand_fte"], 2),
        baseline_supply_fte=round(baseline["supply_fte"], 2),
        simulated_supply_fte=round(sim_supply, 2),
        baseline_gap=round(baseline["gap"], 2),
        simulated_gap=round(sim_gap, 2),
        gap_delta=round(sim_gap - baseline["gap"], 2),
        impact_summary=(
            f"Hiring {hire_count} employees adds {fte_gained:.1f} FTE, "
            f"{'closing' if sim_gap == 0 else 'reducing'} the gap by {baseline['gap'] - sim_gap:.1f} FTE."
        ),
    )


def simulate_training_completion(
    skill_id: str,
    trainees_count: int = 5,
    proficiency_gain: int = 1,
    data_dir: Optional[Path] = None,
) -> SimulationResult:
    """Simulate the impact of completing training for a specific skill."""
    d_dir = data_dir or DATA_DIR
    baseline = _compute_baseline(d_dir)
    demand_df = _load_csv("demand_plans.csv", d_dir)
    skills_df = _load_csv("skills.csv", d_dir)

    skill_name = skill_id
    if not skills_df.empty:
        skills_df.columns = [c.strip().lower() for c in skills_df.columns]
        srow = skills_df[skills_df["skill_id"] == skill_id]
        if not srow.empty and "skill_name" in srow.columns:
            skill_name = str(srow.iloc[0]["skill_name"])

    # Calculate skill-specific demand
    skill_demand = 0.0
    if not demand_df.empty:
        demand_df.columns = [c.strip().lower() for c in demand_df.columns]
        s_col = "required_skill_id" if "required_skill_id" in demand_df.columns else "skill_id"
        skill_demands = demand_df[demand_df[s_col] == skill_id]
        fte_col = "required_fte" if "required_fte" in demand_df.columns else "demand_fte"
        if fte_col in skill_demands.columns:
            skill_demand = float(skill_demands[fte_col].sum())

    addressable = min(trainees_count, skill_demand)

    return SimulationResult(
        scenario_name=f"Training Completion: {skill_name} ({trainees_count} trainees)",
        baseline_demand_fte=round(baseline["demand_fte"], 2),
        simulated_demand_fte=round(baseline["demand_fte"], 2),
        baseline_supply_fte=round(baseline["supply_fte"], 2),
        simulated_supply_fte=round(baseline["supply_fte"], 2),
        baseline_gap=round(baseline["gap"], 2),
        simulated_gap=round(max(0.0, baseline["gap"] - addressable), 2),
        gap_delta=round(-addressable, 2),
        impact_summary=(
            f"Training {trainees_count} employees in {skill_name} (+{proficiency_gain} proficiency levels) "
            f"can address up to {addressable:.1f} FTE of demand for that skill."
        ),
        details=[{
            "skill_id": skill_id,
            "skill_name": skill_name,
            "trainees": trainees_count,
            "proficiency_gain": proficiency_gain,
            "skill_specific_demand_fte": round(skill_demand, 2),
            "addressable_fte": round(addressable, 2),
        }],
    )


def simulate_deadline_shift(
    project_id: str,
    shift_weeks: int = 4,
    data_dir: Optional[Path] = None,
) -> SimulationResult:
    """Simulate extending a project deadline by N weeks."""
    d_dir = data_dir or DATA_DIR
    baseline = _compute_baseline(d_dir)
    demand_df = _load_csv("demand_plans.csv", d_dir)
    projects_df = _load_csv("projects.csv", d_dir)

    project_name = project_id
    if not projects_df.empty:
        projects_df.columns = [c.strip().lower() for c in projects_df.columns]
        prow = projects_df[projects_df["project_id"] == project_id]
        if not prow.empty and "project_name" in prow.columns:
            project_name = str(prow.iloc[0]["project_name"])

    # Extended deadline means demand is spread over a longer period
    # resulting in lower peak FTE requirement
    proj_demand = 0.0
    if not demand_df.empty:
        demand_df.columns = [c.strip().lower() for c in demand_df.columns]
        proj_rows = demand_df[demand_df["project_id"] == project_id]
        fte_col = "required_fte" if "required_fte" in demand_df.columns else "demand_fte"
        if fte_col in proj_rows.columns:
            proj_demand = float(proj_rows[fte_col].sum())

    # Spreading demand reduces peak FTE proportionally
    if not demand_df.empty and not proj_rows.empty:
        start_c = "start_date" if "start_date" in proj_rows.columns else "period_start"
        end_c = "end_date" if "end_date" in proj_rows.columns else "period_end"
        if start_c in proj_rows.columns and end_c in proj_rows.columns:
            starts = pd.to_datetime(proj_rows[start_c], errors="coerce").dropna()
            ends = pd.to_datetime(proj_rows[end_c], errors="coerce").dropna()
            if not starts.empty and not ends.empty:
                orig_weeks = max(1, (ends.max() - starts.min()).days / 7)
                new_weeks = orig_weeks + shift_weeks
                reduction_ratio = orig_weeks / new_weeks
                demand_reduction = proj_demand * (1.0 - reduction_ratio)
            else:
                demand_reduction = 0.0
        else:
            demand_reduction = 0.0
    else:
        demand_reduction = 0.0

    sim_demand = baseline["demand_fte"] - demand_reduction
    sim_gap = max(0.0, sim_demand - baseline["supply_fte"])

    return SimulationResult(
        scenario_name=f"Deadline Extension: {project_name} (+{shift_weeks} weeks)",
        baseline_demand_fte=round(baseline["demand_fte"], 2),
        simulated_demand_fte=round(sim_demand, 2),
        baseline_supply_fte=round(baseline["supply_fte"], 2),
        simulated_supply_fte=round(baseline["supply_fte"], 2),
        baseline_gap=round(baseline["gap"], 2),
        simulated_gap=round(sim_gap, 2),
        gap_delta=round(sim_gap - baseline["gap"], 2),
        impact_summary=(
            f"Extending {project_name} by {shift_weeks} weeks spreads demand, "
            f"reducing peak FTE requirement by {demand_reduction:.1f} FTE."
        ),
    )


def run_scenario_comparison(
    scenarios: Optional[List[Dict[str, Any]]] = None,
    data_dir: Optional[Path] = None,
) -> List[SimulationResult]:
    """
    Run a standard set of scenarios for comparison.

    Default scenarios: +10%, +20%, +30% demand changes, 5 resignations, 10 hires.
    """
    if scenarios is None:
        results = [
            simulate_demand_change(10.0, data_dir),
            simulate_demand_change(20.0, data_dir),
            simulate_demand_change(30.0, data_dir),
            simulate_demand_change(-10.0, data_dir),
            simulate_resignations(5, data_dir=data_dir),
            simulate_resignations(20, data_dir=data_dir),
            simulate_new_hires(10, data_dir=data_dir),
            simulate_new_hires(50, data_dir=data_dir),
        ]
        return results

    results = []
    for s in scenarios:
        stype = s.get("type", "demand_change")
        if stype == "demand_change":
            results.append(simulate_demand_change(s.get("change_pct", 10.0), data_dir))
        elif stype == "resignations":
            results.append(simulate_resignations(s.get("count", 5), s.get("department"), data_dir))
        elif stype == "new_hires":
            results.append(simulate_new_hires(s.get("count", 10), s.get("avg_fte", 1.0), data_dir))
        elif stype == "training":
            results.append(simulate_training_completion(s["skill_id"], s.get("count", 5), s.get("gain", 1), data_dir))
        elif stype == "deadline_shift":
            results.append(simulate_deadline_shift(s["project_id"], s.get("weeks", 4), data_dir))
    return results
