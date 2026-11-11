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
)
from src.db.connection import test_connection
from app.components.kpi_cards import render_kpi_row, render_alert_banner

st.set_page_config(page_title="Stakeholder Persona Views", page_icon="👥", layout="wide")

st.title("👥 Stakeholder & Actor Persona Workflows")
st.caption("Tailored decision views for Employee, Manager, HR Partner, IT/Operations, and System Administrator")

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

        m1, m2, m3 = st.columns(3)
        m1.metric("Department Team Size", len(dept_emps))
        m2.metric("Total Contracted FTE", f"{dept_emps['fte'].sum():.1f}" if "fte" in dept_emps.columns else "N/A")
        m3.metric("Practice Group", sel_dept)

        st.markdown("#### Team Availability & Bench Status")
        if not avail_df.empty:
            dept_emp_ids = set(dept_emps["employee_id"])
            dept_avail = avail_df[avail_df["employee_id"].isin(dept_emp_ids)]
            if not dept_avail.empty:
                st.dataframe(dept_avail[["employee_id", "base_capacity_hours", "contracted_capacity_hours", "approved_leave_hours", "allocated_hours", "net_available_hours", "availability_percentage", "availability_type"]], use_container_width=True, hide_index=True)

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
    st.subheader("Administration & Ground-Truth Anomaly Inspection")
    gt_file = _PROJECT_ROOT / "data" / "ground_truth.json"

    if gt_file.exists():
        with open(gt_file, "r", encoding="utf-8") as f:
            gt_data = json.load(f)

        st.markdown("#### Injected Labeled Edge Cases (Evaluation Ground Truth)")
        st.info("The following anomalies were injected into synthetic data for rigorous evaluator validation without leaking into analytical models.")
        st.dataframe(pd.DataFrame(gt_data), use_container_width=True, hide_index=True)
    else:
        st.warning("Ground truth file not generated yet. Run synthetic data generator.")
