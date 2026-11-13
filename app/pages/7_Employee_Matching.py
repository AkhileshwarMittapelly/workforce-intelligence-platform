"""
Employee-Project Matching View.

Provides an interactive interface for matching employees to projects based on
skill requirements, proficiency, availability, and experience.
"""

from pathlib import Path
import sys
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.services.matching_service import (
    match_employees_to_project,
    get_project_matching_summary,
    find_best_candidates_for_skill,
)
from src.services.db_service import get_projects, get_skills
from app.components.kpi_cards import render_kpi_row

st.set_page_config(page_title="Employee Matching", page_icon="🎯", layout="wide")

st.title("🎯 Intelligent Employee-Project Matching")
st.caption("Score and rank employees against project staffing requirements using a weighted multi-factor model")

projects_df = get_projects()
skills_df = get_skills()

if projects_df.empty:
    st.info("No project data found. Run the data generator first.")
    st.stop()

# --- Project Matching Tab ---
tab1, tab2 = st.tabs(["🔍 Project Matching", "🛠️ Skill Search"])

with tab1:
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        project_options = projects_df[["project_id", "project_name"]].drop_duplicates()
        project_display = dict(zip(project_options["project_id"], project_options["project_name"]))
        selected_project = st.selectbox(
            "Select Project",
            options=list(project_display.keys()),
            format_func=lambda x: f"{project_display[x]} ({x})",
        )
    with col2:
        top_n = st.slider("Top N Candidates", 5, 50, 10)
    with col3:
        st.markdown("**Scoring Weights**")
        # Use defaults

    if selected_project:
        with st.spinner("Computing matches..."):
            matches = match_employees_to_project(selected_project, top_n=top_n)
            summary = get_project_matching_summary(selected_project)

        # Summary KPIs
        render_kpi_row({
            "Required Skills": len(summary.get("required_skills", [])),
            "Total Candidates": summary.get("total_candidates", 0),
            "Full Match": summary.get("fully_matched", 0),
            "Partial Match": summary.get("partially_matched", 0),
        })

        st.markdown("---")

        if matches:
            st.subheader(f"Top {len(matches)} Matching Employees")

            # Match score chart
            match_df = pd.DataFrame(matches)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=match_df["employee_name"],
                x=match_df["match_score"],
                orientation="h",
                marker_color=match_df["match_score"].apply(
                    lambda x: "#2ecc71" if x > 0.7 else "#f39c12" if x > 0.4 else "#e74c3c"
                ),
                text=match_df["match_score"].apply(lambda x: f"{x:.2f}"),
                textposition="outside",
            ))
            fig.update_layout(
                title="Match Score by Employee",
                xaxis_title="Composite Match Score",
                yaxis=dict(autorange="reversed"),
                height=max(300, len(matches) * 35),
                margin=dict(l=20, r=80, t=40, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Detail breakdown
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("Skill Match & Proficiency")
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(
                    name="Skill Match %",
                    y=match_df["employee_name"],
                    x=match_df["skill_match_pct"],
                    orientation="h",
                    marker_color="#3498db",
                ))
                fig2.add_trace(go.Bar(
                    name="Proficiency Avg (x20)",
                    y=match_df["employee_name"],
                    x=match_df["proficiency_avg"] * 20,
                    orientation="h",
                    marker_color="#9b59b6",
                ))
                fig2.update_layout(
                    barmode="group",
                    yaxis=dict(autorange="reversed"),
                    height=max(300, len(matches) * 35),
                    margin=dict(l=20, r=20, t=30, b=20),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig2, use_container_width=True)

            with col_b:
                st.subheader("Available Capacity")
                fig3 = px.bar(
                    match_df, y="employee_name", x="available_capacity_pct",
                    orientation="h",
                    color="available_capacity_pct",
                    color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
                    labels={"available_capacity_pct": "Available %", "employee_name": "Employee"},
                )
                fig3.update_layout(
                    yaxis=dict(autorange="reversed"),
                    height=max(300, len(matches) * 35),
                    margin=dict(l=20, r=20, t=30, b=20),
                )
                st.plotly_chart(fig3, use_container_width=True)

            # Full results table
            st.subheader("📋 Detailed Match Results")
            display_cols = ["employee_name", "match_score", "skill_match_pct", "proficiency_avg",
                            "available_capacity_pct", "available_fte", "reasoning"]
            disp_df = match_df[[c for c in display_cols if c in match_df.columns]]
            st.dataframe(disp_df, use_container_width=True, hide_index=True)

            csv_data = disp_df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download Match Results (CSV)", csv_data, "employee_matches.csv", "text/csv")
        else:
            st.warning("No matching employees found for this project. This may indicate a significant skill gap.")

with tab2:
    st.subheader("🛠️ Find Candidates by Skill")
    if not skills_df.empty:
        skill_options = skills_df[["skill_id", "skill_name"]].drop_duplicates()
        skill_display = dict(zip(skill_options["skill_id"], skill_options["skill_name"]))
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            sel_skill = st.selectbox(
                "Select Skill",
                options=list(skill_display.keys()),
                format_func=lambda x: f"{skill_display[x]} ({x})",
            )
        with col_s2:
            min_prof = st.slider("Minimum Proficiency", 1, 5, 3)
        with col_s3:
            skill_top_n = st.slider("Results", 5, 25, 10, key="skill_top_n")

        if sel_skill:
            candidates = find_best_candidates_for_skill(sel_skill, min_proficiency=min_prof, top_n=skill_top_n)
            if candidates:
                cand_df = pd.DataFrame(candidates)
                st.dataframe(cand_df, use_container_width=True, hide_index=True)
            else:
                st.info(f"No candidates found with proficiency ≥ {min_prof} for this skill.")
    else:
        st.info("No skills data available.")
