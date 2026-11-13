"""
What-If Scenario Simulator View.

Provides interactive scenario modelling for workforce planning decisions.
"""

from pathlib import Path
import sys
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.services.simulation_service import (
    simulate_demand_change,
    simulate_resignations,
    simulate_new_hires,
    simulate_training_completion,
    simulate_deadline_shift,
    run_scenario_comparison,
)
from src.services.db_service import get_projects, get_skills
from app.components.kpi_cards import render_kpi_row

st.set_page_config(page_title="Scenario Simulator", page_icon="🔮", layout="wide")

st.title("🔮 What-If Scenario Simulator")
st.caption("Model the impact of workforce changes before making decisions — all simulations are non-destructive")

# Standard comparison
st.subheader("📊 Standard Scenario Comparison")
with st.spinner("Running scenario comparison..."):
    comparisons = run_scenario_comparison()

if comparisons:
    comp_data = []
    for r in comparisons:
        comp_data.append({
            "Scenario": r.scenario_name,
            "Baseline Gap (FTE)": r.baseline_gap,
            "Simulated Gap (FTE)": r.simulated_gap,
            "Gap Change (FTE)": r.gap_delta,
            "Impact": r.impact_summary,
        })
    comp_df = pd.DataFrame(comp_data)

    # Waterfall chart
    fig = go.Figure(go.Bar(
        x=comp_df["Scenario"],
        y=comp_df["Gap Change (FTE)"],
        marker_color=comp_df["Gap Change (FTE)"].apply(
            lambda x: "#e74c3c" if x > 0 else "#2ecc71"
        ),
        text=comp_df["Gap Change (FTE)"].apply(lambda x: f"{x:+,.0f}"),
        textposition="outside",
    ))
    fig.update_layout(
        title="Gap Impact by Scenario",
        yaxis_title="FTE Gap Change",
        height=400,
        margin=dict(l=20, r=20, t=40, b=100),
        xaxis_tickangle=-30,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(comp_df, use_container_width=True, hide_index=True)

st.markdown("---")

# Custom Scenarios
st.subheader("⚙️ Custom Scenario Builder")
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Demand Change", "🚪 Resignations", "👥 New Hires",
    "📚 Training", "📅 Deadline Shift"
])

with tab1:
    change_pct = st.slider("Demand Change (%)", -50, 100, 20, 5)
    if st.button("Run Demand Simulation", key="btn_demand"):
        result = simulate_demand_change(change_pct)
        render_kpi_row({
            "Baseline Demand": f"{result.baseline_demand_fte:,.0f} FTE",
            "Simulated Demand": f"{result.simulated_demand_fte:,.0f} FTE",
            "Baseline Gap": f"{result.baseline_gap:,.0f} FTE",
            "Simulated Gap": f"{result.simulated_gap:,.0f} FTE",
            "Gap Delta": f"{result.gap_delta:+,.0f} FTE",
        })
        st.info(result.impact_summary)

with tab2:
    col1, col2 = st.columns(2)
    with col1:
        resign_count = st.number_input("Number of Resignations", 1, 500, 10)
    with col2:
        dept_filter = st.text_input("Department (optional)", "")
    if st.button("Run Resignation Simulation", key="btn_resign"):
        result = simulate_resignations(resign_count, dept_filter or None)
        render_kpi_row({
            "Supply Before": f"{result.baseline_supply_fte:,.0f} FTE",
            "Supply After": f"{result.simulated_supply_fte:,.0f} FTE",
            "Gap Delta": f"{result.gap_delta:+,.0f} FTE",
        })
        st.info(result.impact_summary)

with tab3:
    col1, col2 = st.columns(2)
    with col1:
        hire_count = st.number_input("Number of Hires", 1, 500, 10)
    with col2:
        avg_fte = st.number_input("Average FTE per Hire", 0.5, 1.0, 1.0, 0.1)
    if st.button("Run Hiring Simulation", key="btn_hire"):
        result = simulate_new_hires(hire_count, avg_fte)
        render_kpi_row({
            "Supply Before": f"{result.baseline_supply_fte:,.0f} FTE",
            "Supply After": f"{result.simulated_supply_fte:,.0f} FTE",
            "Gap Delta": f"{result.gap_delta:+,.0f} FTE",
        })
        st.info(result.impact_summary)

with tab4:
    skills_df = get_skills()
    if not skills_df.empty:
        skill_opts = dict(zip(skills_df["skill_id"], skills_df["skill_name"]))
        col1, col2, col3 = st.columns(3)
        with col1:
            train_skill = st.selectbox("Skill", list(skill_opts.keys()),
                                        format_func=lambda x: skill_opts[x], key="train_skill")
        with col2:
            train_count = st.number_input("Trainees", 1, 100, 5)
        with col3:
            prof_gain = st.slider("Proficiency Gain", 1, 3, 1)
        if st.button("Run Training Simulation", key="btn_train"):
            result = simulate_training_completion(train_skill, train_count, prof_gain)
            render_kpi_row({
                "Gap Delta": f"{result.gap_delta:+,.0f} FTE",
            })
            st.info(result.impact_summary)
            if result.details:
                st.json(result.details[0])
    else:
        st.info("No skills data available.")

with tab5:
    projects_df = get_projects()
    if not projects_df.empty:
        proj_opts = dict(zip(projects_df["project_id"], projects_df["project_name"]))
        col1, col2 = st.columns(2)
        with col1:
            dl_project = st.selectbox("Project", list(proj_opts.keys()),
                                       format_func=lambda x: proj_opts[x], key="dl_project")
        with col2:
            shift_weeks = st.slider("Weeks to Extend", 1, 26, 4)
        if st.button("Run Deadline Simulation", key="btn_deadline"):
            result = simulate_deadline_shift(dl_project, shift_weeks)
            render_kpi_row({
                "Demand Before": f"{result.baseline_demand_fte:,.0f} FTE",
                "Demand After": f"{result.simulated_demand_fte:,.0f} FTE",
                "Gap Delta": f"{result.gap_delta:+,.0f} FTE",
            })
            st.info(result.impact_summary)
    else:
        st.info("No project data available.")
