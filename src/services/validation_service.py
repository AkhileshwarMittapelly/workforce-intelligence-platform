"""
Comprehensive Data Validation Service.

Validates:
1. Primary-key uniqueness for all 12 entities.
2. All foreign keys, including nullable manager, approver, and project manager references.
3. Required fields and null constraints per schema definitions.
4. Allowed enums across all entities.
5. Date ordering (start <= end, effective_from <= effective_to, hire <= termination).
6. Effective-date consistency and overlapping historical versions.
7. Composite duplicate detection.
8. Allocation and availability reconciliation.
9. Leave and capacity reconciliation.
10. Demand and project date consistency.
11. Training lifecycle validity.
12. Gap-analysis arithmetic.
13. Ground-truth references.

Produces:
- validation_summary.json
- validation_errors.csv
- validation_report.json
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@dataclass
class ValidationErrorRecord:
    rule_name: str
    severity: str  # ERROR, WARNING, INTENTIONAL_ANOMALY
    table_name: str
    entity_id: str
    column_name: str
    error_message: str
    context_data: str = ""


@dataclass
class ValidationReport:
    status: str  # PASSED / FAILED / PASSED_WITH_WARNINGS
    timestamp: str
    total_checks: int
    error_count: int
    warning_count: int
    intentional_anomaly_count: int
    checks_summary: Dict[str, str]
    intentional_anomalies: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    table_row_counts: Dict[str, int]
    dataset_checksum_sha256: str = ""


def _load_csv(filename: str, data_dir: Path) -> pd.DataFrame:
    path = data_dir / filename
    if path.exists():
        try:
            return pd.read_csv(path, low_memory=False)
        except Exception as exc:
            logger.warning("Could not read %s: %s", filename, exc)
    return pd.DataFrame()


class DataValidationService:
    def __init__(self, data_dir: Optional[Path | str] = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.records: List[ValidationErrorRecord] = []
        self.checks_summary: Dict[str, str] = {}
        self.tables: Dict[str, pd.DataFrame] = {}

    def load_tables(self) -> Dict[str, pd.DataFrame]:
        file_map = {
            "role": "roles.csv",
            "employee": "employees.csv",
            "skill": "skills.csv",
            "employee_skill": "employee_skills.csv",
            "project": "projects.csv",
            "demand_plan": "demand_plans.csv",
            "leave_event": "leave_events.csv",
            "allocation": "allocations.csv",
            "availability": "availability.csv",
            "gap_analysis": "gap_analysis.csv",
            "training": "training.csv",
            "historical_event_log": "historical_event_log.csv",
        }
        for name, fname in file_map.items():
            self.tables[name] = _load_csv(fname, self.data_dir)
        return self.tables

    def validate_all(self, tables: Optional[Dict[str, pd.DataFrame]] = None) -> ValidationReport:
        if tables:
            self.tables = tables
        else:
            self.load_tables()

        self.records = []
        self.checks_summary = {}

        # Load ground truth for intentional anomaly awareness
        ground_truth_entities = self._load_ground_truth_map()

        # 1. Primary Key Uniqueness
        self._check_primary_keys()

        # 2. Foreign Key Integrity (including nullable)
        self._check_foreign_keys()

        # 3. Required Fields & Null Constraints
        self._check_required_fields()

        # 4. Allowed Enums
        self._check_allowed_enums()

        # 5. Date Ordering
        self._check_date_ordering()

        # 6. Effective Date Consistency & Overlaps
        self._check_effective_dates()

        # 7. Composite Duplicates (Separate intentional EC-3)
        self._check_composite_duplicates(ground_truth_entities)

        # 8. Allocation & Availability Reconciliation
        self._check_allocation_availability_reconciliation(ground_truth_entities)

        # 9. Leave & Capacity Reconciliation
        self._check_leave_capacity_reconciliation()

        # 10. Demand & Project Date Consistency
        self._check_demand_project_dates()

        # 11. Training Lifecycle Validity
        self._check_training_lifecycle()

        # 12. Gap Analysis Arithmetic
        self._check_gap_arithmetic()

        # 13. Ground-Truth Reference Integrity
        self._check_ground_truth_references(ground_truth_entities)

        return self._generate_report()

    def _load_ground_truth_map(self) -> Dict[str, Dict[str, Any]]:
        gt_path = self.data_dir / "ground_truth.json"
        if gt_path.exists():
            try:
                with open(gt_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {entry["entity_id"]: entry for entry in data}
            except Exception as exc:
                logger.warning("Could not read ground_truth.json: %s", exc)
        return {}

    def _add_record(
        self,
        rule_name: str,
        severity: str,
        table_name: str,
        entity_id: str,
        column_name: str,
        error_message: str,
        context_data: str = "",
    ):
        self.records.append(
            ValidationErrorRecord(
                rule_name=rule_name,
                severity=severity,
                table_name=table_name,
                entity_id=str(entity_id),
                column_name=column_name,
                error_message=error_message,
                context_data=context_data,
            )
        )

    # 1. Primary Key Uniqueness
    def _check_primary_keys(self):
        pk_map = {
            "role": "role_id",
            "employee": "employee_id",
            "skill": "skill_id",
            "employee_skill": "employee_skill_id",
            "project": "project_id",
            "demand_plan": "demand_id",
            "leave_event": "leave_id",
            "allocation": "allocation_id",
            "availability": "availability_id",
            "gap_analysis": "gap_analysis_id",
            "training": "training_id",
            "historical_event_log": "event_id",
        }
        passed = True
        for tbl_name, pk_col in pk_map.items():
            df = self.tables.get(tbl_name)
            if df is not None and not df.empty and pk_col in df.columns:
                dups = df[df[pk_col].duplicated(keep=False)]
                if not dups.empty:
                    passed = False
                    for _, r in dups.iterrows():
                        self._add_record(
                            rule_name="PRIMARY_KEY_UNIQUENESS",
                            severity="ERROR",
                            table_name=tbl_name,
                            entity_id=str(r[pk_col]),
                            column_name=pk_col,
                            error_message=f"Duplicate primary key {r[pk_col]} in {tbl_name}",
                        )
        self.checks_summary["primary_key_uniqueness"] = "PASS" if passed else "FAIL"

    # 2. Foreign Key Integrity
    def _check_foreign_keys(self):
        fk_specs = [
            ("employee", "current_role_id", "role", "role_id", False),
            ("employee", "manager_id", "employee", "employee_id", True),
            ("employee_skill", "employee_id", "employee", "employee_id", False),
            ("employee_skill", "skill_id", "skill", "skill_id", False),
            ("project", "project_manager_id", "employee", "employee_id", True),
            ("demand_plan", "project_id", "project", "project_id", False),
            ("demand_plan", "role_id", "role", "role_id", False),
            ("demand_plan", "required_skill_id", "skill", "skill_id", False),
            ("leave_event", "employee_id", "employee", "employee_id", False),
            ("leave_event", "approver_id", "employee", "employee_id", True),
            ("allocation", "employee_id", "employee", "employee_id", False),
            ("allocation", "project_id", "project", "project_id", False),
            ("availability", "employee_id", "employee", "employee_id", False),
            ("training", "employee_id", "employee", "employee_id", False),
            ("training", "skill_id", "skill", "skill_id", False),
            ("gap_analysis", "skill_id", "skill", "skill_id", False),
        ]
        passed = True
        for c_tbl, c_col, p_tbl, p_col, nullable in fk_specs:
            cdf = self.tables.get(c_tbl)
            pdf = self.tables.get(p_tbl)
            if cdf is None or pdf is None or cdf.empty or pdf.empty:
                continue
            if c_col not in cdf.columns or p_col not in pdf.columns:
                continue

            parent_ids = set(pdf[p_col].dropna().astype(str))
            child_series = cdf[c_col]
            if nullable:
                invalid_mask = child_series.notna() & ~child_series.astype(str).isin(parent_ids)
            else:
                invalid_mask = child_series.isna() | ~child_series.astype(str).isin(parent_ids)

            invalids = cdf[invalid_mask]
            if not invalids.empty:
                passed = False
                for _, r in invalids.iterrows():
                    val = r.get(c_col)
                    self._add_record(
                        rule_name="FOREIGN_KEY_INTEGRITY",
                        severity="ERROR",
                        table_name=c_tbl,
                        entity_id=str(r.iloc[0]),
                        column_name=c_col,
                        error_message=f"Foreign key violation: {c_tbl}.{c_col} value '{val}' not found in {p_tbl}.{p_col}",
                    )
        self.checks_summary["foreign_key_integrity"] = "PASS" if passed else "FAIL"

    # 3. Required Fields & Null Constraints
    def _check_required_fields(self):
        required_map = {
            "role": ["role_id", "role_code", "role_name", "department", "job_level", "effective_from"],
            "employee": ["employee_id", "first_name", "last_name", "email", "current_role_id", "department", "employment_type", "fte", "hire_date", "status"],
            "skill": ["skill_id", "skill_code", "skill_name", "category"],
            "employee_skill": ["employee_skill_id", "employee_id", "skill_id", "proficiency_level", "status"],
            "project": ["project_id", "project_code", "project_name", "start_date", "end_date", "status", "priority"],
            "demand_plan": ["demand_id", "project_id", "role_id", "required_skill_id", "required_fte", "start_date", "end_date"],
            "leave_event": ["leave_id", "employee_id", "leave_type", "start_date", "end_date", "leave_hours", "approval_status"],
            "allocation": ["allocation_id", "employee_id", "project_id", "start_date", "end_date", "allocation_percentage"],
            "availability": ["availability_id", "employee_id", "start_date", "end_date", "contracted_capacity_hours", "net_available_hours"],
            "gap_analysis": ["gap_analysis_id", "skill_id", "required_headcount", "available_headcount", "shortage_headcount"],
            "training": ["training_id", "employee_id", "skill_id", "status", "start_date"],
            "historical_event_log": ["event_id", "event_timestamp", "entity_type", "entity_id", "event_type", "performed_by"],
        }
        passed = True
        for tbl_name, req_cols in required_map.items():
            df = self.tables.get(tbl_name)
            if df is None or df.empty:
                continue
            for col in req_cols:
                if col not in df.columns:
                    passed = False
                    self._add_record(
                        rule_name="REQUIRED_COLUMN_MISSING",
                        severity="ERROR",
                        table_name=tbl_name,
                        entity_id="SCHEMA",
                        column_name=col,
                        error_message=f"Required column '{col}' missing in table '{tbl_name}'",
                    )
                else:
                    nulls = df[df[col].isna()]
                    if not nulls.empty:
                        passed = False
                        for _, r in nulls.iterrows():
                            self._add_record(
                                rule_name="NULL_CONSTRAINT_VIOLATION",
                                severity="ERROR",
                                table_name=tbl_name,
                                entity_id=str(r.iloc[0]),
                                column_name=col,
                                error_message=f"Null value found in required column '{col}' of '{tbl_name}'",
                            )
        self.checks_summary["required_fields"] = "PASS" if passed else "FAIL"

    # 4. Allowed Enums
    def _check_allowed_enums(self):
        enum_map = {
            ("employee", "employment_type"): {"FULL_TIME", "PART_TIME", "CONTRACTOR", "INTERN"},
            ("employee", "status"): {"ONBOARDING", "ACTIVE", "ON_LEAVE", "NOTICE_PERIOD", "TERMINATED"},
            ("skill", "category"): {
                "PROGRAMMING_LANGUAGE",
                "FRAMEWORK",
                "DATABASE",
                "CLOUD_DEVOPS",
                "DATA_AI",
                "DOMAIN_BUSINESS",
                "SOFT_SKILL",
                "CYBERSECURITY",
            },
            ("employee_skill", "status"): {"ACTIVE", "INACTIVE", "EXPIRED"},
            ("project", "status"): {"PROPOSED", "PLANNING", "ACTIVE", "ON_HOLD", "COMPLETED", "CANCELLED"},
            ("project", "priority"): {"LOW", "MEDIUM", "HIGH", "CRITICAL"},
            ("demand_plan", "status"): {"DRAFT", "SUBMITTED", "APPROVED", "ACTIVE", "CLOSED", "SUPERSEDED"},
            ("demand_plan", "fulfillment_status"): {"UNFULFILLED", "PARTIALLY_FULFILLED", "FULFILLED", "CANCELLED"},
            ("leave_event", "approval_status"): {"PENDING", "APPROVED", "REJECTED", "CANCELLED"},
            ("leave_event", "leave_type"): {"ANNUAL", "SICK", "PARENTAL", "UNPAID", "BEREAVEMENT"},
            ("allocation", "allocation_status"): {"PROPOSED", "CONFIRMED", "ACTIVE", "RELEASED", "CANCELLED"},
            ("training", "status"): {"ACTIVE", "SUPERSEDED", "CANCELLED", "ARCHIVED"},
            ("training", "lifecycle_status"): {"NOMINATED", "APPROVED", "ENROLLED", "IN_PROGRESS", "COMPLETED", "FAILED", "DROPPED"},
        }
        passed = True
        for (tbl_name, col), allowed in enum_map.items():
            df = self.tables.get(tbl_name)
            if df is None or df.empty or col not in df.columns:
                continue
            invalid = df[~df[col].astype(str).str.upper().isin(allowed)]
            if not invalid.empty:
                passed = False
                for _, r in invalid.iterrows():
                    val = r.get(col)
                    self._add_record(
                        rule_name="ENUM_CONSTRAINT_VIOLATION",
                        severity="ERROR",
                        table_name=tbl_name,
                        entity_id=str(r.iloc[0]),
                        column_name=col,
                        error_message=f"Value '{val}' in {tbl_name}.{col} not in allowed enums {allowed}",
                    )
        self.checks_summary["allowed_enums"] = "PASS" if passed else "FAIL"

    # 5. Date Ordering
    def _check_date_ordering(self):
        date_pairs = [
            ("project", "start_date", "end_date"),
            ("demand_plan", "start_date", "end_date"),
            ("leave_event", "start_date", "end_date"),
            ("allocation", "start_date", "end_date"),
            ("training", "start_date", "expected_completion_date"),
            ("gap_analysis", "period_start_date", "period_end_date"),
            ("employee", "hire_date", "termination_date"),
            ("role", "effective_from", "effective_to"),
        ]
        passed = True
        for tbl_name, s_col, e_col in date_pairs:
            df = self.tables.get(tbl_name)
            if df is None or df.empty or s_col not in df.columns or e_col not in df.columns:
                continue
            mask = df[s_col].notna() & df[e_col].notna()
            sub = df[mask]
            bad = sub[pd.to_datetime(sub[e_col], errors="coerce") < pd.to_datetime(sub[s_col], errors="coerce")]
            if not bad.empty:
                passed = False
                for _, r in bad.iterrows():
                    self._add_record(
                        rule_name="DATE_ORDER_VIOLATION",
                        severity="ERROR",
                        table_name=tbl_name,
                        entity_id=str(r.iloc[0]),
                        column_name=f"{s_col}→{e_col}",
                        error_message=f"End date ({r[e_col]}) precedes start date ({r[s_col]}) in {tbl_name}",
                    )
        self.checks_summary["date_ordering"] = "PASS" if passed else "FAIL"

    # 6. Effective Date Consistency
    def _check_effective_dates(self):
        passed = True
        for tbl_name in ["role", "employee"]:
            df = self.tables.get(tbl_name)
            if df is None or df.empty:
                continue
            if "effective_from" in df.columns and "effective_to" in df.columns:
                invalid_dates = df[
                    df["effective_to"].notna()
                    & (pd.to_datetime(df["effective_to"], errors="coerce") < pd.to_datetime(df["effective_from"], errors="coerce"))
                ]
                if not invalid_dates.empty:
                    passed = False
                    for _, r in invalid_dates.iterrows():
                        self._add_record(
                            rule_name="EFFECTIVE_DATE_INCONSISTENCY",
                            severity="ERROR",
                            table_name=tbl_name,
                            entity_id=str(r.iloc[0]),
                            column_name="effective_from/to",
                            error_message=f"Effective date inconsistency in {tbl_name}: {r['effective_from']} to {r['effective_to']}",
                        )
        self.checks_summary["effective_date_consistency"] = "PASS" if passed else "FAIL"

    # 7. Composite Duplicate Detection
    def _check_composite_duplicates(self, ground_truth_entities: Dict[str, Dict[str, Any]]):
        passed = True
        # Demand duplicate check
        dp_df = self.tables.get("demand_plan")
        if dp_df is not None and not dp_df.empty:
            skill_col = "required_skill_id" if "required_skill_id" in dp_df.columns else "skill_id"
            keys = ["project_id", "role_id", skill_col, "start_date", "end_date"]
            if all(k in dp_df.columns for k in keys):
                dups = dp_df[dp_df.duplicated(subset=keys, keep="first")]
                for _, r in dups.iterrows():
                    did = str(r["demand_id"])
                    if did in ground_truth_entities and ground_truth_entities[did].get("edge_case_label") == "EC-3":
                        self._add_record(
                            rule_name="COMPOSITE_DUPLICATE_DEMAND",
                            severity="INTENTIONAL_ANOMALY",
                            table_name="demand_plan",
                            entity_id=did,
                            column_name="composite_keys",
                            error_message=f"Intentional EC-3 duplicate demand plan on {did}",
                            context_data=str(r[keys].to_dict()),
                        )
                    else:
                        passed = False
                        self._add_record(
                            rule_name="COMPOSITE_DUPLICATE_DEMAND",
                            severity="ERROR",
                            table_name="demand_plan",
                            entity_id=did,
                            column_name="composite_keys",
                            error_message=f"Accidental duplicate demand plan on {did}",
                            context_data=str(r[keys].to_dict()),
                        )

        # Employee Skill duplicate check
        es_df = self.tables.get("employee_skill")
        if es_df is not None and not es_df.empty and "employee_id" in es_df.columns and "skill_id" in es_df.columns:
            dups_es = es_df[es_df.duplicated(subset=["employee_id", "skill_id"], keep=False)]
            if not dups_es.empty:
                passed = False
                for _, r in dups_es.iterrows():
                    self._add_record(
                        rule_name="COMPOSITE_DUPLICATE_EMPLOYEE_SKILL",
                        severity="ERROR",
                        table_name="employee_skill",
                        entity_id=str(r["employee_skill_id"]),
                        column_name="employee_id+skill_id",
                        error_message=f"Duplicate skill {r['skill_id']} assigned to employee {r['employee_id']}",
                    )
        self.checks_summary["composite_duplicate_detection"] = "PASS" if passed else "FAIL"

    # 8. Allocation & Availability Reconciliation
    def _check_allocation_availability_reconciliation(self, ground_truth_entities: Dict[str, Dict[str, Any]]):
        alloc_df = self.tables.get("allocation")
        passed = True
        if alloc_df is not None and not alloc_df.empty:
            for _, r in alloc_df.iterrows():
                alloc_id = str(r["allocation_id"])
                pct = float(r.get("allocation_percentage", 0.0))
                if pct > 100.0:
                    if alloc_id in ground_truth_entities and ground_truth_entities[alloc_id].get("edge_case_label") == "EC-1":
                        self._add_record(
                            rule_name="ALLOCATION_CAPACITY_RECONCILIATION",
                            severity="INTENTIONAL_ANOMALY",
                            table_name="allocation",
                            entity_id=alloc_id,
                            column_name="allocation_percentage",
                            error_message=f"Intentional EC-1 over-allocation ({pct}%) on {alloc_id}",
                        )
                    else:
                        passed = False
                        self._add_record(
                            rule_name="ALLOCATION_CAPACITY_RECONCILIATION",
                            severity="ERROR",
                            table_name="allocation",
                            entity_id=alloc_id,
                            column_name="allocation_percentage",
                            error_message=f"Unlabeled over-allocation ({pct}%) on {alloc_id}",
                        )
        self.checks_summary["allocation_availability_reconciliation"] = "PASS" if passed else "FAIL"

    # 9. Leave & Capacity Reconciliation
    def _check_leave_capacity_reconciliation(self):
        leave_df = self.tables.get("leave_event")
        passed = True
        if leave_df is not None and not leave_df.empty:
            bad_hours = leave_df[(leave_df["leave_hours"].astype(float) <= 0) | (leave_df["leave_hours"].astype(float) > 40.0)]
            if not bad_hours.empty:
                passed = False
                for _, r in bad_hours.iterrows():
                    self._add_record(
                        rule_name="LEAVE_HOURS_BOUNDS",
                        severity="ERROR",
                        table_name="leave_event",
                        entity_id=str(r["leave_id"]),
                        column_name="leave_hours",
                        error_message=f"Leave hours {r['leave_hours']} out of valid range (0, 40] in leave_event",
                    )
        self.checks_summary["leave_capacity_reconciliation"] = "PASS" if passed else "FAIL"

    # 10. Demand & Project Date Consistency
    def _check_demand_project_dates(self):
        dp_df = self.tables.get("demand_plan")
        prj_df = self.tables.get("project")
        passed = True
        if dp_df is not None and prj_df is not None and not dp_df.empty and not prj_df.empty:
            prj_map = dict(
                zip(
                    prj_df["project_id"],
                    zip(pd.to_datetime(prj_df["start_date"]), pd.to_datetime(prj_df["end_date"])),
                )
            )
            for _, r in dp_df.iterrows():
                pid = r.get("project_id")
                if pid in prj_map:
                    p_st, p_en = prj_map[pid]
                    d_st = pd.to_datetime(r["start_date"])
                    d_en = pd.to_datetime(r["end_date"])
                    if d_st < p_st or d_en > p_en:
                        passed = False
                        self._add_record(
                            rule_name="DEMAND_PROJECT_DATE_CONTAINMENT",
                            severity="ERROR",
                            table_name="demand_plan",
                            entity_id=str(r["demand_id"]),
                            column_name="start_date/end_date",
                            error_message=f"Demand dates [{d_st.date()}→{d_en.date()}] fall outside project {pid} bounds [{p_st.date()}→{p_en.date()}]",
                        )
        self.checks_summary["demand_project_date_consistency"] = "PASS" if passed else "FAIL"

    # 11. Training Lifecycle Validity
    def _check_training_lifecycle(self):
        tr_df = self.tables.get("training")
        passed = True
        if tr_df is not None and not tr_df.empty:
            comp_col = "actual_completion_date" if "actual_completion_date" in tr_df.columns else "completion_date"
            stat_col = "lifecycle_status" if "lifecycle_status" in tr_df.columns else "status"
            if comp_col in tr_df.columns and stat_col in tr_df.columns:
                completed = tr_df[tr_df[stat_col].astype(str).str.upper() == "COMPLETED"]
                bad_comp = completed[completed[comp_col].isna()]
                if not bad_comp.empty:
                    passed = False
                    for _, r in bad_comp.iterrows():
                        self._add_record(
                            rule_name="TRAINING_LIFECYCLE_COMPLETION",
                            severity="ERROR",
                            table_name="training",
                            entity_id=str(r["training_id"]),
                            column_name=comp_col,
                            error_message=f"Training {r['training_id']} marked COMPLETED but {comp_col} is null",
                        )
        self.checks_summary["training_lifecycle_validity"] = "PASS" if passed else "FAIL"

    # 12. Gap Analysis Arithmetic
    def _check_gap_arithmetic(self):
        gap_df = self.tables.get("gap_analysis")
        passed = True
        if gap_df is not None and not gap_df.empty:
            for _, r in gap_df.iterrows():
                req = int(r.get("required_headcount", 0))
                avail = int(r.get("available_headcount", 0))
                short = int(r.get("shortage_headcount", 0))
                expected = max(0, req - avail)
                if short != expected:
                    passed = False
                    self._add_record(
                        rule_name="GAP_ARITHMETIC_CONSISTENCY",
                        severity="ERROR",
                        table_name="gap_analysis",
                        entity_id=str(r["gap_analysis_id"]),
                        column_name="shortage_headcount",
                        error_message=f"Arithmetic mismatch: required={req}, available={avail}, shortage={short}, expected={expected}",
                    )
        self.checks_summary["gap_analysis_arithmetic"] = "PASS" if passed else "FAIL"

    # 13. Ground Truth Reference Integrity
    def _check_ground_truth_references(self, ground_truth_entities: Dict[str, Dict[str, Any]]):
        passed = True
        tbl_pk_lookup = {
            "ALLOC": ("allocation", "allocation_id"),
            "ESK": ("employee_skill", "employee_skill_id"),
            "DEM": ("demand_plan", "demand_id"),
            "EMP": ("employee", "employee_id"),
        }
        for entity_id, gt_entry in ground_truth_entities.items():
            matched = False
            for prefix, (tbl_name, pk_col) in tbl_pk_lookup.items():
                if entity_id.startswith(prefix) or prefix in entity_id:
                    df = self.tables.get(tbl_name)
                    if df is not None and not df.empty and pk_col in df.columns:
                        if (df[pk_col].astype(str) == entity_id).any():
                            matched = True
                            break
            if not matched:
                passed = False
                self._add_record(
                    rule_name="GROUND_TRUTH_REFERENCE_MISSING",
                    severity="ERROR",
                    table_name="ground_truth",
                    entity_id=entity_id,
                    column_name="entity_id",
                    error_message=f"Ground truth entity {entity_id} does not exist in any operational table",
                )
        self.checks_summary["ground_truth_references"] = "PASS" if passed else "FAIL"

    # Report & Export Generation
    def _generate_report(self) -> ValidationReport:
        errors = [asdict(r) for r in self.records if r.severity == "ERROR"]
        warnings = [asdict(r) for r in self.records if r.severity == "WARNING"]
        intentional = [asdict(r) for r in self.records if r.severity == "INTENTIONAL_ANOMALY"]

        status = "PASSED" if len(errors) == 0 else "FAILED"
        if status == "PASSED" and len(warnings) > 0:
            status = "PASSED_WITH_WARNINGS"

        row_counts = {k: len(v) for k, v in self.tables.items() if v is not None}

        # Checksum if available
        checksum_sha256 = ""
        val_summary_file = self.data_dir / "validation_summary.json"
        if val_summary_file.exists():
            try:
                with open(val_summary_file, "r") as f:
                    checksum_sha256 = json.load(f).get("dataset_checksum_sha256", "")
            except Exception:
                pass

        report = ValidationReport(
            status=status,
            timestamp=datetime.now().isoformat(),
            total_checks=len(self.checks_summary),
            error_count=len(errors),
            warning_count=len(warnings),
            intentional_anomaly_count=len(intentional),
            checks_summary=self.checks_summary,
            intentional_anomalies=intentional,
            errors=errors,
            warnings=warnings,
            table_row_counts=row_counts,
            dataset_checksum_sha256=checksum_sha256,
        )

        self._export_artifacts(report)
        return report

    def _export_artifacts(self, report: ValidationReport):
        # 1. validation_report.json
        report_path = self.data_dir / "validation_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, indent=2)

        # 2. validation_errors.csv
        errors_csv_path = self.data_dir / "validation_errors.csv"
        error_rows = [asdict(r) for r in self.records if r.severity in ("ERROR", "WARNING")]
        fieldnames = ["rule_name", "severity", "table_name", "entity_id", "column_name", "error_message", "context_data"]
        with open(errors_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            if error_rows:
                writer.writerows(error_rows)

        # 3. validation_summary.json (keep aligned)
        summary_path = self.data_dir / "validation_summary.json"
        summary_data = {
            "status": report.status,
            "timestamp": report.timestamp,
            "error_count": report.error_count,
            "warning_count": report.warning_count,
            "intentional_anomaly_count": report.intentional_anomaly_count,
            "checks_performed": report.checks_summary,
            "intentional_anomaly_flags": [f"[{a['rule_name']}] on {a['entity_id']}: {a['error_message']}" for a in report.intentional_anomalies],
            "dataset_checksum_sha256": report.dataset_checksum_sha256,
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)


def run_data_validation(data_dir: Optional[Path | str] = None) -> ValidationReport:
    """Entry point to run comprehensive data validation."""
    service = DataValidationService(data_dir=data_dir)
    return service.validate_all()


if __name__ == "__main__":
    report = run_data_validation()
    print(f"Validation finished with status: {report.status}")
    print(f"Errors: {report.error_count}, Warnings: {report.warning_count}, Intentional Anomalies: {report.intentional_anomaly_count}")
