"""
Anomaly Detection & Ground-Truth Benchmarking Service.

Independently inspects raw operational workforce records to discover:
  - EC-1: Over-allocated staff whose assignments exceed contracted capacity.
  - EC-2: Stale skill proficiencies (>18 months unverified) still marked ACTIVE.
  - EC-3: Duplicate natural demand plans (same project, role, skill, and period).
  - EC-4: Employees simultaneously allocated to multiple projects with overlapping dates.

Evaluates detected findings against ground truth to produce precision, recall, and F1 scores.
Does NOT leak ground-truth labels into detection or analytical features.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SCENARIO_DATE = pd.Timestamp("2026-11-11")


def _load_csv(filename: str, data_dir: Path) -> pd.DataFrame:
    path = data_dir / filename
    if path.exists():
        try:
            return pd.read_csv(path, low_memory=False)
        except Exception as e:
            logger.warning("Error reading %s: %s", filename, e)
    return pd.DataFrame()


def _detect_ec1_over_allocated(
    allocations_df: pd.DataFrame,
    employees_df: Optional[pd.DataFrame] = None,
    now_str: Optional[str] = None,
) -> list[dict]:
    """EC-1: Allocation exceeds contracted capacity (> 100%) within same period."""
    if allocations_df.empty:
        return []
    if now_str is None:
        now_str = datetime.now().isoformat()
    detected = []
    alloc_clean = allocations_df.copy()
    alloc_clean["_s"] = pd.to_datetime(alloc_clean.get("start_date"), errors="coerce")
    alloc_clean["_e"] = pd.to_datetime(alloc_clean.get("end_date"), errors="coerce")

    for emp_id, group in alloc_clean.groupby("employee_id"):
        # Check single allocations exceeding 100% capacity
        over_single = group[group["allocation_percentage"].astype(float) > 100.0]
        if not over_single.empty:
            for _, alloc_row in over_single.iterrows():
                detected.append(
                    {
                        "anomaly_id": f"ANO-EC1-{len(detected) + 1:04d}",
                        "issue_type": "OVER_ALLOCATED",
                        "edge_case_label": "EC-1",
                        "entity_id": str(alloc_row["allocation_id"]),
                        "employee_id": str(emp_id),
                        "project_id": str(alloc_row.get("project_id", "")),
                        "detail": f"Allocation percentage ({alloc_row['allocation_percentage']}%) exceeds 100% contracted capacity",
                        "detected_at": now_str,
                    }
                )
        elif len(group) > 1:
            # Evaluate concurrent commitments within overlapping time windows (not across whole history)
            reported_over_allocs = set()
            for _, r in group.iterrows():
                eval_t = r["_s"]
                if pd.isna(eval_t):
                    continue
                active_at_t = group[(group["_s"] <= eval_t) & (group["_e"] >= eval_t)]
                tot_pct = float(active_at_t["allocation_percentage"].astype(float).sum())
                if tot_pct > 100.0:
                    alloc_id = str(r["allocation_id"])
                    if alloc_id not in reported_over_allocs:
                        reported_over_allocs.add(alloc_id)
                        detected.append(
                            {
                                "anomaly_id": f"ANO-EC1-{len(detected) + 1:04d}",
                                "issue_type": "OVER_ALLOCATED",
                                "edge_case_label": "EC-1",
                                "entity_id": alloc_id,
                                "employee_id": str(emp_id),
                                "project_id": str(r.get("project_id", "")),
                                "detail": f"Concurrent allocation commitments ({tot_pct:.1f}%) during active period exceed 100% contracted capacity",
                                "detected_at": now_str,
                            }
                        )
                        break
    return detected


def _detect_ec2_stale_skills(
    employee_skills_df: pd.DataFrame,
    now_str: Optional[str] = None,
) -> list[dict]:
    """EC-2: Stale skill proficiency treated as current (ACTIVE > 18 months)."""
    if employee_skills_df.empty:
        return []
    if now_str is None:
        now_str = datetime.now().isoformat()
    detected = []
    active_es = employee_skills_df[employee_skills_df["status"].str.upper() == "ACTIVE"].copy()
    if "last_evaluated_date" in active_es.columns:
        eval_dt = pd.to_datetime(active_es["last_evaluated_date"], errors="coerce")
        stale_mask = (SCENARIO_DATE - eval_dt).dt.days > 548  # 18 months
        stale_rows = active_es[stale_mask]
        for _, r in stale_rows.iterrows():
            detected.append(
                {
                    "anomaly_id": f"ANO-EC2-{len(detected) + 1:04d}",
                    "issue_type": "STALE_SKILL_ACTIVE",
                    "edge_case_label": "EC-2",
                    "entity_id": str(r["employee_skill_id"]),
                    "employee_id": str(r["employee_id"]),
                    "project_id": "",
                    "detail": f"Skill evaluated on {r['last_evaluated_date']} (>18 months) but retained as ACTIVE",
                    "detected_at": now_str,
                }
            )
    return detected


def _detect_ec3_duplicate_demand(
    demand_plans_df: pd.DataFrame,
    now_str: Optional[str] = None,
) -> list[dict]:
    """EC-3: Demand double-counted (duplicate project+role+skill+start_date+end_date)."""
    if demand_plans_df.empty:
        return []
    if now_str is None:
        now_str = datetime.now().isoformat()
    detected = []
    skill_col = "required_skill_id" if "required_skill_id" in demand_plans_df.columns else "skill_id"
    demand_keys = ["project_id", "role_id", skill_col, "start_date", "end_date"]
    available_keys = [k for k in demand_keys if k in demand_plans_df.columns]
    if len(available_keys) == len(demand_keys):
        second_dups = demand_plans_df[demand_plans_df.duplicated(subset=available_keys, keep="first")]
        for _, r in second_dups.iterrows():
            detected.append(
                {
                    "anomaly_id": f"ANO-EC3-{len(detected) + 1:04d}",
                    "issue_type": "DEMAND_DOUBLE_COUNTED",
                    "edge_case_label": "EC-3",
                    "entity_id": str(r["demand_id"]),
                    "employee_id": "",
                    "project_id": str(r.get("project_id", "")),
                    "detail": f"Duplicate demand plan for project {r.get('project_id')}, role {r.get('role_id')}, skill {r.get(skill_col)} from {r.get('start_date')} to {r.get('end_date')}",
                    "detected_at": now_str,
                }
            )
    return detected


def _detect_ec4_overlapping_assignments(
    allocations_df: pd.DataFrame,
    now_str: Optional[str] = None,
) -> list[dict]:
    """EC-4: Overlapping allocations for same employee across projects (all pairs)."""
    if allocations_df.empty or "start_date" not in allocations_df.columns or "end_date" not in allocations_df.columns:
        return []
    if now_str is None:
        now_str = datetime.now().isoformat()
    detected = []
    alloc_clean = allocations_df.copy()
    alloc_clean["_s"] = pd.to_datetime(alloc_clean["start_date"], errors="coerce")
    alloc_clean["_e"] = pd.to_datetime(alloc_clean["end_date"], errors="coerce")

    for emp_id, emp_allocs in alloc_clean.groupby("employee_id"):
        if len(emp_allocs) > 1:
            alloc_list = emp_allocs.to_dict(orient="records")
            reported_conflicts = set()
            for i in range(len(alloc_list)):
                for j in range(i + 1, len(alloc_list)):
                    row_a = alloc_list[i]
                    row_b = alloc_list[j]
                    if pd.isna(row_a["_s"]) or pd.isna(row_a["_e"]) or pd.isna(row_b["_s"]) or pd.isna(row_b["_e"]):
                        continue
                    if max(row_a["_s"], row_b["_s"]) <= min(row_a["_e"], row_b["_e"]):
                        if str(row_a.get("project_id")) != str(row_b.get("project_id")):
                            conflict_pair = tuple(sorted([str(row_a["allocation_id"]), str(row_b["allocation_id"])]))
                            if conflict_pair not in reported_conflicts:
                                reported_conflicts.add(conflict_pair)
                                detected.append(
                                    {
                                        "anomaly_id": f"ANO-EC4-{len(detected) + 1:04d}",
                                        "issue_type": "OVERLAPPING_ALLOCATION",
                                        "edge_case_label": "EC-4",
                                        "entity_id": str(row_b["allocation_id"]),
                                        "employee_id": str(emp_id),
                                        "project_id": str(row_b.get("project_id", "")),
                                        "detail": f"Concurrent allocation conflict between project {row_a.get('project_id')} ({row_a.get('start_date')}→{row_a.get('end_date')}) and {row_b.get('project_id')} ({row_b.get('start_date')}→{row_b.get('end_date')})",
                                        "detected_at": now_str,
                                    }
                                )
    return detected


def detect_anomalies(data_dir: Optional[Path | str] = None) -> pd.DataFrame:
    """
    Scans source datasets to detect operational and workforce data anomalies.
    Saves results to anomaly_detection_results.csv.
    """
    d_dir = Path(data_dir) if data_dir else DATA_DIR
    detected: list[dict] = []
    now_str = datetime.now().isoformat()

    allocations_df = _load_csv("allocations.csv", d_dir)
    employees_df = _load_csv("employees.csv", d_dir)
    employee_skills_df = _load_csv("employee_skills.csv", d_dir)
    demand_plans_df = _load_csv("demand_plans.csv", d_dir)

    # 1. EC-1: Allocation exceeds contracted capacity (> 100%) within same period
    detected.extend(_detect_ec1_over_allocated(allocations_df, employees_df, now_str))

    # 2. EC-2: Stale skill proficiency treated as current (ACTIVE > 18 months)
    detected.extend(_detect_ec2_stale_skills(employee_skills_df, now_str))

    # 3. EC-3: Demand double-counted (duplicate project+role+skill+start_date+end_date)
    detected.extend(_detect_ec3_duplicate_demand(demand_plans_df, now_str))

    # 4. EC-4: Overlapping allocations for same employee across projects (all pairs)
    detected.extend(_detect_ec4_overlapping_assignments(allocations_df, now_str))

    detected_df = pd.DataFrame(detected)
    if not detected_df.empty:
        out_path = d_dir / "anomaly_detection_results.csv"
        detected_df.to_csv(out_path, index=False)
        logger.info("Saved %d detected anomalies to %s", len(detected_df), out_path)

    return detected_df


def evaluate_anomalies(
    detected_df: Optional[pd.DataFrame] = None,
    ground_truth_df: Optional[pd.DataFrame] = None,
    data_dir: Optional[Path | str] = None,
) -> dict:
    """
    Compares detected anomalies against ground truth.
    Calculates Precision, Recall, and F1-score overall and by category.
    """
    d_dir = Path(data_dir) if data_dir else DATA_DIR

    if detected_df is None or detected_df.empty:
        detected_df = detect_anomalies(d_dir)

    if ground_truth_df is None or ground_truth_df.empty:
        gt_path = d_dir / "ground_truth.json"
        if gt_path.exists():
            with open(gt_path, "r", encoding="utf-8") as f:
                ground_truth_df = pd.DataFrame(json.load(f))
        else:
            ground_truth_df = _load_csv("ground_truth.csv", d_dir)

    if ground_truth_df.empty:
        return {
            "status": "NO_GROUND_TRUTH",
            "overall_precision": 1.0,
            "overall_recall": 1.0,
            "overall_f1": 1.0,
            "categories": {},
        }

    gt_entities = set(ground_truth_df["entity_id"].astype(str))
    det_entities = set(detected_df["entity_id"].astype(str)) if not detected_df.empty else set()

    true_positives = len(gt_entities.intersection(det_entities))
    false_positives = len(det_entities - gt_entities)
    false_negatives = len(gt_entities - det_entities)

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 1.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 1.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    category_metrics = {}
    for edge_label in ["EC-1", "EC-2", "EC-3", "EC-4"]:
        gt_sub = set(ground_truth_df[ground_truth_df["edge_case_label"] == edge_label]["entity_id"].astype(str)) if "edge_case_label" in ground_truth_df.columns else set()
        det_sub = set(detected_df[detected_df["edge_case_label"] == edge_label]["entity_id"].astype(str)) if not detected_df.empty and "edge_case_label" in detected_df.columns else set()

        tp = len(gt_sub.intersection(det_sub))
        fp = len(det_sub - gt_sub)
        fn = len(gt_sub - det_sub)

        cat_prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        cat_rec = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        cat_f1 = (2 * cat_prec * cat_rec) / (cat_prec + cat_rec) if (cat_prec + cat_rec) > 0 else 0.0

        category_metrics[edge_label] = {
            "ground_truth_count": len(gt_sub),
            "detected_count": len(det_sub),
            "true_positives": tp,
            "precision": round(cat_prec, 4),
            "recall": round(cat_rec, 4),
            "f1_score": round(cat_f1, 4),
        }

    return {
        "status": "EVALUATED",
        "total_ground_truth": len(gt_entities),
        "total_detected": len(det_entities),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "overall_precision": round(precision, 4),
        "overall_recall": round(recall, 4),
        "overall_f1": round(f1, 4),
        "categories": category_metrics,
    }


if __name__ == "__main__":
    import json
    results = detect_anomalies()
    eval_metrics = evaluate_anomalies()
    print("Detected anomalies:", len(results))
    print("Evaluation:", json.dumps(eval_metrics, indent=2))

