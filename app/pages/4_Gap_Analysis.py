"""
Capability Gap Diagnostics & Action Recommendations View.
"""

from pathlib import Path
import sys
import pandas as pd
import streamlit as st
import plotly.express as px

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.services.db_service import get_gap_analyses, get_skills, get_roles, get_projects
from src.services.gap_service import analyze_gaps
from app.components.kpi_cards import render_kpi_row, render_alert_banner, render_recommendation_card

st.set_page_config(page_title="Capability Gap Diagnostics", page_icon="🔍", layout="wide")

st.title("🔍 Capability Gap Diagnostics & Decision Matrix")
st.caption("AI-driven shortfall detection, risk severity analysis, and evidence-backed hiring vs. upskilling recommendations")

gaps_df = get_gap_analyses()
skills_df = get_skills()
roles_df = get_roles()
projects_df = get_projects()

if gaps_df.empty:
    st.info("No capability gap analyses found. Run data generation or analytics service.")
    st.stop()

# Enrich gap data with descriptive names
if not skills_df.empty and "skill_name" in skills_df.columns:
    gaps_df = gaps_df.merge(skills_df[["skill_id", "skill_name"]], on="skill_id", how="left")
if not roles_df.empty and "role_name" in roles_df.columns:
    gaps_df = gaps_df.merge(roles_df[["role_id", "role_name"]], on="role_id", how="left")
if not projects_df.empty and "project_name" in projects_df.columns:
    gaps_df = gaps_df.merge(projects_df[["project_id", "project_name"]], on="project_id", how="left")

# High-level KPIs
total_gaps = len(gaps_df)
crit_gaps = len(gaps_df[gaps_df["gap_severity"] == "CRITICAL"]) if "gap_severity" in gaps_df.columns else 0
high_gaps = len(gaps_df[gaps_df["gap_severity"] == "HIGH"]) if "gap_severity" in gaps_df.columns else 0
hire_actions = len(gaps_df[gaps_df["recommended_action"] == "HIRE_EXTERNAL"]) if "recommended_action" in gaps_df.columns else 0

render_kpi_row({
    "Total Analyzed Gaps": total_gaps,
    "Critical Severities": crit_gaps,
    "High Severities": high_gaps,
    "External Hires Advised": hire_actions,
})

if crit_gaps > 0:
    render_alert_banner("critical", f"Immediate action needed: {crit_gaps} critical staffing shortage(s) currently jeopardize active deliverables!")

st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Severity Distribution")
    if "gap_severity" in gaps_df.columns:
        sev_counts = gaps_df["gap_severity"].value_counts().reset_index()
        sev_counts.columns = ["Severity", "Count"]
        color_map = {"CRITICAL": "#e74c3c", "HIGH": "#e67e22", "MEDIUM": "#f1c40f", "LOW": "#2ecc71", "NONE": "#95a5a6"}
        fig_sev = px.pie(
            sev_counts, names="Severity", values="Count", hole=0.45,
            color="Severity", color_discrete_map=color_map
        )
        fig_sev.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_sev, use_container_width=True)

with col2:
    st.subheader("Recommended Action Breakdown")
    if "recommended_action" in gaps_df.columns:
        act_counts = gaps_df["recommended_action"].value_counts().reset_index()
        act_counts.columns = ["Action", "Count"]
        fig_act = px.bar(
            act_counts, x="Count", y="Action", orientation="h",
            color="Action", color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig_act.update_layout(yaxis=dict(autorange="reversed"), height=320, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
        st.plotly_chart(fig_act, use_container_width=True)

st.subheader("📋 Actionable Gaps & Mitigation Decision Matrix")
filter_c1, filter_c2 = st.columns(2)
with filter_c1:
    sev_list = ["ALL"] + sorted(gaps_df["gap_severity"].dropna().unique().tolist()) if "gap_severity" in gaps_df.columns else ["ALL"]
    sel_sev = st.selectbox("Filter by Severity", sev_list)
with filter_c2:
    act_list = ["ALL"] + sorted(gaps_df["recommended_action"].dropna().unique().tolist()) if "recommended_action" in gaps_df.columns else ["ALL"]
    sel_act = st.selectbox("Filter by Recommended Action", act_list)

filtered = gaps_df.copy()
if sel_sev != "ALL":
    filtered = filtered[filtered["gap_severity"] == sel_sev]
if sel_act != "ALL":
    filtered = filtered[filtered["recommended_action"] == sel_act]

show_cols = [c for c in ["gap_analysis_id", "project_name", "role_name", "skill_name", "shortage_headcount", "gap_severity", "recommended_action", "required_proficiency_level", "avg_current_proficiency_level", "notes"] if c in filtered.columns]
st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)

# Detailed inspection card
if not filtered.empty:
    st.markdown("### 💡 Decision & Traceability Inspector")
    gap_ids = filtered["gap_analysis_id"].tolist()
    chosen_id = st.selectbox("Select Gap ID to inspect rationale & evidence:", gap_ids)
    chosen_row = filtered[filtered["gap_analysis_id"] == chosen_id].iloc[0]

    render_recommendation_card({
        "gap_id": chosen_row.get("gap_analysis_id", ""),
        "severity": chosen_row.get("gap_severity", "MEDIUM"),
        "recommended_action": chosen_row.get("recommended_action", "UPSKILL_INTERNAL"),
        "skill_name": chosen_row.get("skill_name", "N/A"),
        "role_title": chosen_row.get("role_name", "N/A"),
        "project_name": chosen_row.get("project_name", "General Demand"),
        "shortage_headcount": chosen_row.get("shortage_headcount", 1),
        "reasoning": chosen_row.get("notes", "Rule-based recommendation derived from capacity deficit and timeline feasibility.")
    })
