"""
Demand Forecasting & Capacity Planning View.
"""

from pathlib import Path
import sys
import pandas as pd
import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.services.db_service import get_demand_plans, get_projects, get_roles, get_skills
from src.services.forecast_service import get_demand_forecast, ForecastResult
from app.components.kpi_cards import render_kpi_row, render_alert_banner
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Demand Forecasting", page_icon="📈", layout="wide")

st.title("📈 Forward-Looking Staffing Demand & Forecasting")
st.caption("Forecast project labor requirements by role, skill, and schedule vs. workforce supply")

demand_df = get_demand_plans()
projects_df = get_projects()
roles_df = get_roles()
skills_df = get_skills()

if demand_df.empty:
    st.info("No demand plan data found. Run the data generator from the Admin panel or CLI.")
    st.stop()

# Enrich demand with project, role, skill names
if not projects_df.empty and "project_name" in projects_df.columns:
    demand_df = demand_df.merge(projects_df[["project_id", "project_name"]], on="project_id", how="left")
if not roles_df.empty and "role_name" in roles_df.columns:
    demand_df = demand_df.merge(roles_df[["role_id", "role_name"]], on="role_id", how="left")
if not skills_df.empty and "skill_name" in skills_df.columns:
    demand_df = demand_df.merge(skills_df[["skill_id", "skill_name"]], left_on="required_skill_id", right_on="skill_id", how="left")

# High-level KPIs
total_demand_records = len(demand_df)
total_required_fte = demand_df["required_fte"].sum() if "required_fte" in demand_df.columns else 0.0
total_headcount = demand_df["headcount_required"].sum() if "headcount_required" in demand_df.columns else 0
unfulfilled = len(demand_df[demand_df["fulfillment_status"] == "UNFULFILLED"]) if "fulfillment_status" in demand_df.columns else 0

render_kpi_row({
    "Demand Records": total_demand_records,
    "Total Required FTE": f"{total_required_fte:.1f}",
    "Total Headcount Req": total_headcount,
    "Unfulfilled Requests": unfulfilled,
})

st.markdown("---")

# Filters
col1, col2, col3 = st.columns(3)
with col1:
    priorities = ["ALL"] + sorted(demand_df["priority"].dropna().unique().tolist()) if "priority" in demand_df.columns else ["ALL"]
    sel_priority = st.selectbox("Filter Priority", priorities)
with col2:
    status_opts = ["ALL"] + sorted(demand_df["fulfillment_status"].dropna().unique().tolist()) if "fulfillment_status" in demand_df.columns else ["ALL"]
    sel_status = st.selectbox("Fulfillment Status", status_opts)
with col3:
    role_opts = ["ALL"] + sorted(demand_df["role_name"].dropna().unique().tolist()) if "role_name" in demand_df.columns else ["ALL"]
    sel_role = st.selectbox("Role Filter", role_opts)

filtered_df = demand_df.copy()
if sel_priority != "ALL":
    filtered_df = filtered_df[filtered_df["priority"] == sel_priority]
if sel_status != "ALL":
    filtered_df = filtered_df[filtered_df["fulfillment_status"] == sel_status]
if sel_role != "ALL" and "role_name" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["role_name"] == sel_role]

# Charts Section
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("FTE Demand by Role")
    if "role_name" in filtered_df.columns and "required_fte" in filtered_df.columns:
        role_sum = filtered_df.groupby("role_name")["required_fte"].sum().reset_index().sort_values(by="required_fte", ascending=False).head(10)
        fig_role = px.bar(
            role_sum, x="required_fte", y="role_name", orientation="h",
            color="required_fte", color_continuous_scale="Blues",
            labels={"required_fte": "Total Required FTE", "role_name": "Role"}
        )
        fig_role.update_layout(yaxis=dict(autorange="reversed"), height=350, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_role, use_container_width=True)

with col_chart2:
    st.subheader("Demand Fulfillment Breakdown")
    if "fulfillment_status" in filtered_df.columns:
        fig_pie = px.pie(
            filtered_df, names="fulfillment_status",
            color_discrete_sequence=["#e74c3c", "#f39c12", "#2ecc71", "#95a5a6"],
            hole=0.4
        )
        fig_pie.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_pie, use_container_width=True)

# Forecast Table
st.subheader("📋 Staffing Demand Schedule & Timeline")
display_cols = [c for c in ["demand_id", "project_name", "role_name", "skill_name", "headcount_required", "required_fte", "priority", "fulfillment_status", "start_date", "end_date"] if c in filtered_df.columns]
st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)

# CSV Download
csv_data = filtered_df[display_cols].to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 Download Filtered Demand Schedule as CSV",
    data=csv_data,
    file_name="demand_forecast.csv",
    mime="text/csv",
)
