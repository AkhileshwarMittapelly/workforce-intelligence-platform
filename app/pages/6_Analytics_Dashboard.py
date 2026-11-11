"""
Executive Analytics & Workforce Intelligence Dashboard.
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

from src.services.analytics_service import (
    get_workforce_kpis,
    get_department_breakdown,
    get_skill_coverage_matrix,
    get_monthly_utilization_trend,
    get_recommendation_action_split,
)
from src.services.db_service import get_projects
from app.components.kpi_cards import render_kpi_row
from app.components.charts import utilization_gauge

st.set_page_config(page_title="Executive Analytics", page_icon="📊", layout="wide")

st.title("📊 Strategic Workforce Analytics & KPIs")
st.caption("Macro workforce trends, capacity utilization trajectory, and talent supply-demand equilibrium")

kpis = get_workforce_kpis()

render_kpi_row({
    "Total Headcount": kpis.total_headcount,
    "Avg Utilization": f"{kpis.avg_utilization_pct}%",
    "Bench Available": kpis.bench_count,
    "Active Gaps": kpis.active_gaps_count,
})

st.markdown("---")

# Monthly Utilization Trend
st.subheader("📈 12-Month Workforce Capacity vs. Utilization Trend (2026)")
trend_df = get_monthly_utilization_trend()

if not trend_df.empty:
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Bar(
        x=trend_df["month"], y=trend_df["allocated_hours"],
        name="Allocated Project Hours", marker_color="#3498db"
    ))
    fig_trend.add_trace(go.Bar(
        x=trend_df["month"], y=trend_df["bench_hours"],
        name="Available Bench Hours", marker_color="#2ecc71"
    ))
    fig_trend.add_trace(go.Scatter(
        x=trend_df["month"], y=trend_df["utilization_pct"],
        name="Utilization %", yaxis="y2", mode="lines+markers",
        line=dict(color="#e74c3c", width=3)
    ))
    fig_trend.update_layout(
        barmode="stack",
        yaxis=dict(title="Hours"),
        yaxis2=dict(title="Utilization %", overlaying="y", side="right", range=[0, 100]),
        height=380,
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_trend, use_container_width=True)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Hiring vs. Upskilling Decision Split")
    rec_split = get_recommendation_action_split()
    if not rec_split.empty:
        fig_donut = px.pie(
            rec_split, names="action", values="count", hole=0.5,
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig_donut.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.info("No gap analysis recommendations are available yet. Run a data generation cycle to populate gap analysis records.")

with col2:
    st.subheader("Departmental Talent Distribution")
    dept_df = get_department_breakdown()
    if not dept_df.empty:
        fig_dept = px.bar(
            dept_df, x="headcount", y="department", orientation="h",
            color="headcount", color_continuous_scale="Purples"
        )
        fig_dept.update_layout(yaxis=dict(autorange="reversed"), height=320, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_dept, use_container_width=True)

st.subheader("🏢 Active Project Engagement Statuses")
prj_df = get_projects()
if not prj_df.empty and "status" in prj_df.columns:
    col_prj1, col_prj2 = st.columns([1, 2])
    with col_prj1:
        prj_status = prj_df["status"].value_counts().reset_index()
        prj_status.columns = ["Status", "Count"]
        fig_ps = px.pie(prj_status, names="Status", values="Count", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_ps.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_ps, use_container_width=True)
    with col_prj2:
        st.dataframe(prj_df[["project_id", "project_name", "business_unit", "planned_budget", "priority", "status", "start_date"]].head(15), use_container_width=True, hide_index=True)
