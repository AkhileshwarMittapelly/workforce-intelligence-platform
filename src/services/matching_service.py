"""
Employee-Project Matching Engine.

Scores and ranks employees against project staffing requirements using a
weighted multi-factor scoring model:

    S = w_s * SkillMatch + w_p * Proficiency + w_a * Availability + w_e * Experience

Factors:
  - SkillMatch: fraction of project-required skills the employee possesses.
  - Proficiency: average proficiency across matched skills, normalised 0-1.
  - Availability: remaining FTE capacity after current allocations and leave.
  - Experience: breadth proxy from total active skill count, normalised 0-1.

All data is sourced from CSV files in the data/ directory.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Default scoring weights
DEFAULT_WEIGHTS = {"skill": 0.35, "proficiency": 0.25, "availability": 0.25, "experience": 0.15}

# Stale threshold: 18 months = 548 days
STALE_DAYS = 548


def _load_csv(name: str, data_dir: Optional[Path] = None) -> pd.DataFrame:
    path = (data_dir or DATA_DIR) / name
    if not path.exists():
        logger.warning("CSV %s not found", path)
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def _available_capacity(
    emp_id: str,
    scenario_date: pd.Timestamp,
    emp_fte: float,
    alloc_by_emp: dict,
    leave_by_emp: dict,
) -> float:
    """Calculate remaining FTE capacity for an employee at the scenario date."""
    committed = 0.0
    for s, e, fval in alloc_by_emp.get(emp_id, []):
        if s <= scenario_date <= e:
            committed += fval

    leave_fte = 0.0
    for s, e, fval in leave_by_emp.get(emp_id, []):
        if s <= scenario_date <= e:
            leave_fte += fval

    return max(0.0, emp_fte - committed - leave_fte)


def match_employees_to_project(
    project_id: str,
    top_n: int = 10,
    scenario_date: Optional[str] = None,
    data_dir: Optional[Path] = None,
    weights: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Match and rank employees to a project based on skill match, proficiency,
    availability, and experience.

    Returns:
        List of dicts, each containing:
          employee_id, employee_name, match_score, skill_match_pct,
          proficiency_avg, available_capacity_pct, missing_skills,
          matching_skills, reasoning
    """
    d_dir = data_dir or DATA_DIR
    w = weights or DEFAULT_WEIGHTS

    scenario_dt = pd.Timestamp(scenario_date or "2026-11-11")

    # Load data
    employees_df = _load_csv("employees.csv", d_dir)
    emp_skills_df = _load_csv("employee_skills.csv", d_dir)
    allocations_df = _load_csv("allocations.csv", d_dir)
    demand_df = _load_csv("demand_plans.csv", d_dir)
    skills_df = _load_csv("skills.csv", d_dir)
    leave_df = _load_csv("leave_events.csv", d_dir)

    if employees_df.empty or demand_df.empty:
        return []

    # Normalise columns
    for df in [employees_df, emp_skills_df, allocations_df, demand_df, skills_df, leave_df]:
        if not df.empty:
            df.columns = [c.strip().lower() for c in df.columns]

    # Required skills for this project from demand_plans
    skill_col = "required_skill_id" if "required_skill_id" in demand_df.columns else "skill_id"
    proj_demands = demand_df[demand_df["project_id"] == project_id]
    if proj_demands.empty:
        return []

    required_skill_ids = set(proj_demands[skill_col].dropna().unique())
    if not required_skill_ids:
        return []

    # Build skill name lookup
    skill_names = {}
    if not skills_df.empty and "skill_id" in skills_df.columns and "skill_name" in skills_df.columns:
        skill_names = dict(zip(skills_df["skill_id"], skills_df["skill_name"]))

    # Active employees only
    if "status" in employees_df.columns:
        active_emps = employees_df[employees_df["status"].str.upper() == "ACTIVE"].copy()
    else:
        active_emps = employees_df.copy()

    if active_emps.empty:
        return []

    emp_fte_map = dict(zip(active_emps["employee_id"].astype(str), active_emps.get("fte", 1.0).astype(float)))
    emp_name_map = dict(zip(active_emps["employee_id"].astype(str), active_emps.get("name", active_emps["employee_id"]).astype(str)))

    # Valid, non-stale employee skills
    if not emp_skills_df.empty:
        es = emp_skills_df.copy()
        if "status" in es.columns:
            es = es[es["status"].str.upper() == "ACTIVE"]
        if "last_evaluated_date" in es.columns:
            eval_dt = pd.to_datetime(es["last_evaluated_date"], errors="coerce")
            es = es[(scenario_dt - eval_dt).dt.days <= STALE_DAYS]
    else:
        es = pd.DataFrame()

    # Build per-employee skill map: {emp_id: {skill_id: proficiency}}
    emp_skill_map: Dict[str, Dict[str, int]] = {}
    if not es.empty:
        for r in es[["employee_id", "skill_id", "proficiency_level"]].to_dict(orient="records"):
            eid = str(r["employee_id"])
            sid = str(r.get("skill_id", ""))
            prof = int(r.get("proficiency_level", 3))
            if eid not in emp_skill_map:
                emp_skill_map[eid] = {}
            emp_skill_map[eid][sid] = prof

    # Pre-index allocations by employee
    alloc_by_emp: Dict[str, list] = {}
    if not allocations_df.empty:
        allocations_df["_s"] = pd.to_datetime(allocations_df.get("start_date"), errors="coerce")
        allocations_df["_e"] = pd.to_datetime(allocations_df.get("end_date"), errors="coerce")
        if "allocation_percentage" in allocations_df.columns:
            allocations_df["_fte"] = allocations_df["allocation_percentage"].astype(float) / 100.0
        elif "allocated_fte" in allocations_df.columns:
            allocations_df["_fte"] = allocations_df["allocated_fte"].astype(float)
        else:
            allocations_df["_fte"] = 0.5

        for r in allocations_df[["employee_id", "_s", "_e", "_fte"]].to_dict(orient="records"):
            s, e = r.get("_s"), r.get("_e")
            if pd.notna(s) and pd.notna(e):
                eid = str(r["employee_id"])
                alloc_by_emp.setdefault(eid, []).append((s, e, float(r["_fte"])))

    # Pre-index leave by employee
    leave_by_emp: Dict[str, list] = {}
    if not leave_df.empty:
        if "approval_status" in leave_df.columns:
            leave_df = leave_df[leave_df["approval_status"].str.upper() == "APPROVED"]
        leave_df["_s"] = pd.to_datetime(leave_df.get("start_date"), errors="coerce")
        leave_df["_e"] = pd.to_datetime(leave_df.get("end_date"), errors="coerce")
        leave_df["_fte"] = (leave_df.get("leave_hours", 0.0).astype(float) / 40.0).clip(upper=1.0)
        for r in leave_df[["employee_id", "_s", "_e", "_fte"]].to_dict(orient="records"):
            s, e = r.get("_s"), r.get("_e")
            if pd.notna(s) and pd.notna(e):
                eid = str(r["employee_id"])
                leave_by_emp.setdefault(eid, []).append((s, e, float(r["_fte"])))

    # Max skill count for experience normalisation
    max_skills = max((len(v) for v in emp_skill_map.values()), default=1)
    if max_skills == 0:
        max_skills = 1

    # Score each active employee
    results = []
    for eid in emp_fte_map:
        emp_skills = emp_skill_map.get(eid, {})
        matched_skills = set(emp_skills.keys()) & required_skill_ids
        if not matched_skills:
            continue
        missing_skills = required_skill_ids - set(emp_skills.keys())

        # Skill match score (0-1)
        skill_match = len(matched_skills) / len(required_skill_ids) if required_skill_ids else 0.0

        # Proficiency score (0-1)
        prof_avg = sum(emp_skills[s] for s in matched_skills) / len(matched_skills)
        prof_score = prof_avg / 5.0

        # Availability score (0-1)
        emp_fte = emp_fte_map[eid]
        avail = _available_capacity(eid, scenario_dt, emp_fte, alloc_by_emp, leave_by_emp)
        avail_score = min(1.0, avail / emp_fte) if emp_fte > 0 else 0.0

        # Experience score (0-1)
        exp_score = min(1.0, len(emp_skills) / max_skills)

        # Weighted score
        match_score = (
            w["skill"] * skill_match
            + w["proficiency"] * prof_score
            + w["availability"] * avail_score
            + w["experience"] * exp_score
        )

        # Skip employees with zero skill match
        if skill_match == 0.0:
            continue

        # Build reasoning
        parts = []
        parts.append(f"Matches {len(matched_skills)}/{len(required_skill_ids)} required skills ({skill_match * 100:.0f}%)")
        parts.append(f"Avg proficiency {prof_avg:.1f}/5 on matched skills")
        parts.append(f"Available capacity: {avail:.2f} FTE ({avail_score * 100:.0f}%)")
        if missing_skills:
            missing_names = [skill_names.get(s, s) for s in missing_skills]
            parts.append(f"Missing: {', '.join(missing_names[:5])}")

        results.append({
            "employee_id": eid,
            "employee_name": emp_name_map.get(eid, eid),
            "match_score": round(match_score, 4),
            "skill_match_pct": round(skill_match * 100, 1),
            "proficiency_avg": round(prof_avg, 1),
            "available_capacity_pct": round(avail_score * 100, 1),
            "available_fte": round(avail, 2),
            "missing_skills": [skill_names.get(s, s) for s in missing_skills],
            "matching_skills": [skill_names.get(s, s) for s in matched_skills],
            "reasoning": "; ".join(parts),
        })

    # Sort by match_score descending
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:top_n]


def get_project_matching_summary(
    project_id: str,
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Returns summary statistics for employee matching against a project.
    """
    d_dir = data_dir or DATA_DIR
    demand_df = _load_csv("demand_plans.csv", d_dir)
    projects_df = _load_csv("projects.csv", d_dir)
    skills_df = _load_csv("skills.csv", d_dir)

    if demand_df.empty:
        return {"project_id": project_id, "project_name": "", "required_skills": [], "total_candidates": 0, "fully_matched": 0, "partially_matched": 0, "no_match": 0}

    for df in [demand_df, projects_df, skills_df]:
        if not df.empty:
            df.columns = [c.strip().lower() for c in df.columns]

    skill_col = "required_skill_id" if "required_skill_id" in demand_df.columns else "skill_id"
    proj_demands = demand_df[demand_df["project_id"] == project_id]
    required_skill_ids = set(proj_demands[skill_col].dropna().unique()) if not proj_demands.empty else set()

    project_name = ""
    if not projects_df.empty and "project_id" in projects_df.columns:
        prow = projects_df[projects_df["project_id"] == project_id]
        if not prow.empty and "project_name" in prow.columns:
            project_name = str(prow.iloc[0]["project_name"])

    skill_names_map = {}
    if not skills_df.empty:
        skill_names_map = dict(zip(skills_df["skill_id"], skills_df["skill_name"]))

    # Get all matches (larger pool)
    all_matches = match_employees_to_project(project_id, top_n=9999, data_dir=d_dir)

    fully_matched = sum(1 for m in all_matches if m["skill_match_pct"] == 100.0)
    partially_matched = sum(1 for m in all_matches if 0 < m["skill_match_pct"] < 100.0)

    return {
        "project_id": project_id,
        "project_name": project_name,
        "required_skills": [skill_names_map.get(s, s) for s in required_skill_ids],
        "total_candidates": len(all_matches),
        "fully_matched": fully_matched,
        "partially_matched": partially_matched,
        "no_match": 0,  # Zero-match employees are already filtered out
    }


def find_best_candidates_for_skill(
    skill_id: str,
    min_proficiency: int = 3,
    top_n: int = 5,
    scenario_date: Optional[str] = None,
    data_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Find the best candidates who have a specific skill at or above the
    minimum proficiency and have available capacity.
    """
    d_dir = data_dir or DATA_DIR
    scenario_dt = pd.Timestamp(scenario_date or "2026-11-11")

    employees_df = _load_csv("employees.csv", d_dir)
    emp_skills_df = _load_csv("employee_skills.csv", d_dir)
    allocations_df = _load_csv("allocations.csv", d_dir)
    skills_df = _load_csv("skills.csv", d_dir)
    leave_df = _load_csv("leave_events.csv", d_dir)

    for df in [employees_df, emp_skills_df, allocations_df, skills_df, leave_df]:
        if not df.empty:
            df.columns = [c.strip().lower() for c in df.columns]

    if emp_skills_df.empty:
        return []

    # Filter to active, non-stale skill records for the target skill
    es = emp_skills_df.copy()
    if "status" in es.columns:
        es = es[es["status"].str.upper() == "ACTIVE"]
    if "last_evaluated_date" in es.columns:
        eval_dt = pd.to_datetime(es["last_evaluated_date"], errors="coerce")
        es = es[(scenario_dt - eval_dt).dt.days <= STALE_DAYS]

    es = es[es["skill_id"] == skill_id]
    if "proficiency_level" in es.columns:
        es = es[es["proficiency_level"].astype(int) >= min_proficiency]

    if es.empty:
        return []

    # Active employees
    if "status" in employees_df.columns:
        active_emps = employees_df[employees_df["status"].str.upper() == "ACTIVE"]
    else:
        active_emps = employees_df
    active_ids = set(active_emps["employee_id"].astype(str))
    emp_fte_map = dict(zip(active_emps["employee_id"].astype(str), active_emps.get("fte", 1.0).astype(float)))
    emp_name_map = dict(zip(active_emps["employee_id"].astype(str), active_emps.get("name", active_emps["employee_id"])))

    # Pre-index allocations
    alloc_by_emp: Dict[str, list] = {}
    if not allocations_df.empty:
        allocations_df["_s"] = pd.to_datetime(allocations_df.get("start_date"), errors="coerce")
        allocations_df["_e"] = pd.to_datetime(allocations_df.get("end_date"), errors="coerce")
        if "allocation_percentage" in allocations_df.columns:
            allocations_df["_fte"] = allocations_df["allocation_percentage"].astype(float) / 100.0
        elif "allocated_fte" in allocations_df.columns:
            allocations_df["_fte"] = allocations_df["allocated_fte"].astype(float)
        else:
            allocations_df["_fte"] = 0.5
        for r in allocations_df[["employee_id", "_s", "_e", "_fte"]].to_dict(orient="records"):
            s, e = r.get("_s"), r.get("_e")
            if pd.notna(s) and pd.notna(e):
                eid = str(r["employee_id"])
                alloc_by_emp.setdefault(eid, []).append((s, e, float(r["_fte"])))

    leave_by_emp: Dict[str, list] = {}
    if not leave_df.empty:
        if "approval_status" in leave_df.columns:
            leave_df = leave_df[leave_df["approval_status"].str.upper() == "APPROVED"]
        leave_df["_s"] = pd.to_datetime(leave_df.get("start_date"), errors="coerce")
        leave_df["_e"] = pd.to_datetime(leave_df.get("end_date"), errors="coerce")
        leave_df["_fte"] = (leave_df.get("leave_hours", 0.0).astype(float) / 40.0).clip(upper=1.0)
        for r in leave_df[["employee_id", "_s", "_e", "_fte"]].to_dict(orient="records"):
            s, e = r.get("_s"), r.get("_e")
            if pd.notna(s) and pd.notna(e):
                eid = str(r["employee_id"])
                leave_by_emp.setdefault(eid, []).append((s, e, float(r["_fte"])))

    skill_name = skill_id
    if not skills_df.empty and "skill_id" in skills_df.columns and "skill_name" in skills_df.columns:
        srow = skills_df[skills_df["skill_id"] == skill_id]
        if not srow.empty:
            skill_name = str(srow.iloc[0]["skill_name"])

    results = []
    for r in es[["employee_id", "proficiency_level"]].to_dict(orient="records"):
        eid = str(r["employee_id"])
        if eid not in active_ids:
            continue
        prof = int(r["proficiency_level"])
        emp_fte = emp_fte_map.get(eid, 1.0)
        avail = _available_capacity(eid, scenario_dt, emp_fte, alloc_by_emp, leave_by_emp)

        results.append({
            "employee_id": eid,
            "employee_name": emp_name_map.get(eid, eid),
            "skill_name": skill_name,
            "proficiency_level": prof,
            "available_fte": round(avail, 2),
            "available_capacity_pct": round((avail / emp_fte * 100) if emp_fte > 0 else 0, 1),
        })

    results.sort(key=lambda x: (-x["proficiency_level"], -x["available_fte"]))
    return results[:top_n]
