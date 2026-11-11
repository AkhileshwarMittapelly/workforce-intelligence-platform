"""
Primary Actor & Stakeholder Persona Views.
"""

from pathlib import Path
import json
import sys
import pandas as pd
import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.services.db_service import (
    get_active_employees,
    get_employee_skills,
    get_allocations,
    get_training,
    get_gap_analyses,
    get_projects,
    get_skills,
    get_roles,
    get_availability,
    get_leave_events,
    get_historical_event_log,
)
from src.services.anomaly_service import detect_anomalies, evaluate_anomalies
from src.db.connection import test_connection
from app.components.kpi_cards import render_kpi_row, render_alert_banner

st.set_page_config(page_title="Stakeholder Persona Views", page_icon="👥", layout="wide")

st.title("👥 Stakeholder & Actor Persona Workflows")
st.caption("Tailored decision views for Employee, Manager, HR Partner, IT/Operations, and System Administrator")

st.info("ℹ️ **Persona Switcher:** This panel provides simulated role-based interfaces to demonstrate actor-specific decision workflows and access contexts. It is an analytical workflow demonstration, not an identity authentication or authorization boundary.")

tab_emp, tab_mgr, tab_hr, tab_ops, tab_admin = st.tabs([
    "👤 Employee / Candidate",
    "👔 Manager",
    "🤝 HR Partner",
    "⚙️ IT & Operations",
    "🛡️ System Administrator",
])

# -----------------------------------------------------------------------------
# TAB 1: EMPLOYEE / CANDIDATE
# -----------------------------------------------------------------------------
with tab_emp:
    st.subheader("Employee Self-Service & Talent Profile")
    emp_df = get_active_employees()
    if not emp_df.empty and "first_name" in emp_df.columns:
        emp_df["display_name"] = emp_df["first_name"] + " " + emp_df["last_name"] + " (" + emp_df["employee_id"] + ")"
        selected_emp_name = st.selectbox("Select Employee Profile", emp_df["display_name"].tolist())
        selected_emp_id = selected_emp_name.split("(")[-1].replace(")", "")
        emp_record = emp_df[emp_df["employee_id"] == selected_emp_id].iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Department", emp_record.get("department", "N/A"))
        c2.metric("Contracted FTE", emp_record.get("fte", 1.0))
        c3.metric("Cost Rate", f"${emp_record.get('cost_rate_per_hour', 0.0)}/hr")
        c4.metric("Status", emp_record.get("status", "ACTIVE"))

        st.markdown("#### Verified Competency Portfolio")
        esk_df = get_employee_skills(employee_id=selected_emp_id)
        skills_df = get_skills()
        if not esk_df.empty and not skills_df.empty:
            merged_esk = esk_df.merge(skills_df[["skill_id", "skill_name", "category"]], on="skill_id", how="left")
            st.dataframe(merged_esk[["skill_name", "category", "proficiency_level", "verification_status", "years_of_experience", "last_evaluated_date"]], use_container_width=True, hide_index=True)
        else:
            st.info("No skill ratings recorded for this employee.")

        st.markdown("#### Active Project Allocations")
        alloc_df = get_allocations(employee_id=selected_emp_id)
        projects_df = get_projects()
        if not alloc_df.empty:
            if not projects_df.empty and "project_name" in projects_df.columns:
                alloc_df = alloc_df.merge(projects_df[["project_id", "project_name"]], on="project_id", how="left")
            st.dataframe(alloc_df[["project_name", "allocation_percentage", "billing_rate_per_hour", "start_date", "end_date", "allocation_status"]], use_container_width=True, hide_index=True)
        else:
            st.info("Currently unallocated / on bench.")

        st.markdown("#### 🏖️ Personal Leave Requests & Time-Off History")
        leave_df = get_leave_events(employee_id=selected_emp_id)
        if not leave_df.empty:
            display_leave = [c for c in ["leave_id", "leave_type", "start_date", "end_date", "leave_hours", "approval_status", "reason"] if c in leave_df.columns]
            st.dataframe(leave_df[display_leave], use_container_width=True, hide_index=True)
        else:
            st.info("No leave records submitted for this employee.")

        st.markdown("#### Upskilling & Enrolled Training")
        trn_df = get_training(employee_id=selected_emp_id)
        if not trn_df.empty:
            st.dataframe(trn_df[["training_title", "provider", "training_type", "target_proficiency_level", "expected_completion_date", "lifecycle_status"]], use_container_width=True, hide_index=True)
        else:
            st.info("No active training enrollments.")

# -----------------------------------------------------------------------------
# TAB 2: MANAGER
# -----------------------------------------------------------------------------
with tab_mgr:
    st.subheader("Team Capacity & Project Staffing Oversight")
    emp_df = get_active_employees()
    avail_df = get_availability()
    if not emp_df.empty and "department" in emp_df.columns:
        depts = sorted(emp_df["department"].dropna().unique().tolist())
        sel_dept = st.selectbox("Select Managing Department", depts)
        dept_emps = emp_df[emp_df["department"] == sel_dept]
        dept_emp_ids = set(dept_emps["employee_id"])

        m1, m2, m3 = st.columns(3)
        m1.metric("Department Team Size", len(dept_emps))
        m2.metric("Total Contracted FTE", f"{dept_emps['fte'].sum():.1f}" if "fte" in dept_emps.columns else "N/A")
        m3.metric("Practice Group", sel_dept)

        st.markdown("#### Team Availability & Bench Status")
        if not avail_df.empty:
            dept_avail = avail_df[avail_df["employee_id"].isin(dept_emp_ids)]
            if not dept_avail.empty:
                st.dataframe(dept_avail[["employee_id", "base_capacity_hours", "contracted_capacity_hours", "approved_leave_hours", "allocated_hours", "net_available_hours", "availability_percentage", "availability_type"]], use_container_width=True, hide_index=True)
            else:
                st.info("No availability metrics for this department.")

        st.markdown("#### 📅 Team Leave Requests & Planned Time-Off")
        all_leaves = get_leave_events()
        if not all_leaves.empty:
            dept_leaves = all_leaves[all_leaves["employee_id"].isin(dept_emp_ids)]
            if not dept_leaves.empty:
                st.dataframe(dept_leaves[["leave_id", "employee_id", "leave_type", "start_date", "end_date", "leave_hours", "approval_status", "reason"]], use_container_width=True, hide_index=True)
            else:
                st.info("No active leave requests for team members.")

# -----------------------------------------------------------------------------
# TAB 3: HR PARTNER
# -----------------------------------------------------------------------------
with tab_hr:
    st.subheader("Strategic Workforce Planning & Talent Development")
    gaps_df = get_gap_analyses()
    skills_df = get_skills()
    roles_df = get_roles()

    if not gaps_df.empty:
        if not skills_df.empty:
            gaps_df = gaps_df.merge(skills_df[["skill_id", "skill_name"]], on="skill_id", how="left")
        if not roles_df.empty:
            gaps_df = gaps_df.merge(roles_df[["role_id", "role_name"]], on="role_id", how="left")

        h1, h2 = st.columns(2)
        with h1:
            st.markdown("#### 🎯 External Recruitment Pipeline Needed")
            recruits = gaps_df[gaps_df["recommended_action"] == "HIRE_EXTERNAL"]
            if not recruits.empty:
                st.dataframe(recruits[["role_name", "skill_name", "shortage_headcount", "gap_severity"]], use_container_width=True, hide_index=True)
            else:
                st.success("No critical external recruitment backlogs.")
        with h2:
            st.markdown("#### 📚 Internal Upskilling Cohorts Recommended")
            upskill = gaps_df[gaps_df["recommended_action"] == "UPSKILL_INTERNAL"]
            if not upskill.empty:
                st.dataframe(upskill[["role_name", "skill_name", "shortage_headcount", "required_proficiency_level"]], use_container_width=True, hide_index=True)
            else:
                st.info("No active upskilling campaigns pending.")

# -----------------------------------------------------------------------------
# TAB 4: IT & OPERATIONS
# -----------------------------------------------------------------------------
with tab_ops:
    st.subheader("System Infrastructure, Database & Pipeline Health")
    db_status = test_connection()

    col_stat1, col_stat2 = st.columns(2)
    with col_stat1:
        st.markdown("#### Database Connectivity Diagnostic")
        st.write(f"**Target Database:** `{db_status['database']}`")
        if db_status["connected"]:
            st.success("Database Server Connected (SELECT 1 OK)")
        else:
            st.warning(f"Database Unreachable / Offline: {db_status.get('error_type', 'OperationalError')}")
            st.info("Running seamlessly in high-performance local seed / CSV mode.")

    with col_stat2:
        st.markdown("#### Schema & Core Entities Verification")
        st.metric("Tables Verified", len(db_status["tables_found"]), f"{len(db_status['missing_tables'])} Missing / Unseeded")

    with st.expander("Show Diagnostic Details"):
        st.json(db_status)

# -----------------------------------------------------------------------------
# TAB 5: SYSTEM ADMINISTRATOR
# -----------------------------------------------------------------------------
with tab_admin:
    st.subheader("System Administration, Anomaly Benchmarking & Audit Trail")

    st.markdown("### 🔍 Model-Based Anomaly Detection & Benchmarking")
    st.caption("Independent anomaly detection executed against raw operational data and evaluated against isolated ground truth.")

    # Execute independent anomaly detection
    det_df = detect_anomalies()
    eval_res = evaluate_anomalies()

    if eval_res.get("status") == "EVALUATED":
        c_k1, c_k2, c_k3, c_k4 = st.columns(4)
        c_k1.metric("Ground Truth Injected", eval_res.get("total_ground_truth", 0))
        c_k2.metric("Anomalies Detected", eval_res.get("total_detected", 0))
        c_k3.metric("True Positives", eval_res.get("true_positives", 0))
        c_k4.metric("Precision / Recall / F1", f"{eval_res.get('overall_precision', 1.0) * 100:.0f}% / {eval_res.get('overall_recall', 1.0) * 100:.0f}% / {eval_res.get('overall_f1', 1.0) * 100:.0f}%")

        st.markdown("#### Category-by-Category Benchmark Evaluation")
        cat_rows = []
        for code, cat_info in eval_res.get("categories", {}).items():
            cat_rows.append({
                "Edge Case": code,
                "Ground Truth Count": cat_info["ground_truth_count"],
                "Detected Count": cat_info["detected_count"],
                "True Positives": cat_info["true_positives"],
                "Precision": f"{cat_info['precision'] * 100:.1f}%",
                "Recall": f"{cat_info['recall'] * 100:.1f}%",
                "F1 Score": f"{cat_info['f1_score'] * 100:.1f}%",
            })
        st.dataframe(pd.DataFrame(cat_rows), use_container_width=True, hide_index=True)

    if not det_df.empty:
        st.markdown("#### 🚨 Detected Operational Anomalies (Model Output)")
        display_det = [c for c in ["anomaly_id", "edge_case_label", "issue_type", "entity_id", "employee_id", "project_id", "detail", "detected_at"] if c in det_df.columns]
        st.dataframe(det_df[display_det], use_container_width=True, hide_index=True)
    else:
        st.success("No anomalies detected in active dataset.")

    st.markdown("---")
    st.markdown("### 🎯 Ground Truth Labeled Edge Cases (Reference Baseline)")
    gt_file = _PROJECT_ROOT / "data" / "ground_truth.json"
    if gt_file.exists():
        with open(gt_file, "r", encoding="utf-8") as f:
            gt_data = json.load(f)
        st.dataframe(pd.DataFrame(gt_data), use_container_width=True, hide_index=True)
    else:
        st.info("Ground truth file not available.")

    st.markdown("---")
    st.markdown("### 📜 Immutable Historical Event Log & Audit Trail")
    events_df = get_historical_event_log()
    if not events_df.empty:
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            entity_types = ["ALL"] + sorted(events_df["entity_type"].dropna().unique().tolist()) if "entity_type" in events_df.columns else ["ALL"]
            sel_ent_type = st.selectbox("Filter Entity Type", entity_types)
        with f_col2:
            change_types = ["ALL"] + sorted(events_df["event_type"].dropna().unique().tolist()) if "event_type" in events_df.columns else ["ALL"]
            sel_chg_type = st.selectbox("Filter Change Type", change_types)

        f_events = events_df.copy()
        if sel_ent_type != "ALL":
            f_events = f_events[f_events["entity_type"] == sel_ent_type]
        if sel_chg_type != "ALL":
            f_events = f_events[f_events["event_type"] == sel_chg_type]

        display_evt = [c for c in ["event_id", "event_timestamp", "entity_type", "entity_id", "event_type", "performed_by", "reason", "old_state", "new_state"] if c in f_events.columns]
        st.dataframe(f_events[display_evt].head(100), use_container_width=True, hide_index=True)
        st.caption(f"Showing {min(len(f_events), 100)} of {len(f_events)} audit events recorded.")
    else:
        st.info("No historical event logs recorded.")
