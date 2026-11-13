"""
Financial Intelligence View.

Provides cost modelling, ROI analysis, and financial impact assessment
for workforce planning decisions.
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

from src.services.financial_service import (
    get_financial_summary,
    estimate_recommendation_costs,
    get_cost_comparison_table,
)
from app.components.kpi_cards import render_kpi_row

st.set_page_config(page_title="Financial Intelligence", page_icon="💰", layout="wide")

st.title("💰 Financial Intelligence & Cost Analysis")
st.caption("Enterprise-grade financial modelling for workforce planning decisions")

# Configurable cost parameters
with st.sidebar:
    st.subheader("⚙️ Cost Parameters")
    avg_salary = st.number_input("Avg Annual Salary ($)", 50000, 200000, 95000, 5000)
    contractor_rate = st.number_input("Contractor Daily Rate ($)", 200, 2000, 800, 50)
    training_cost = st.number_input("Training Cost per Employee ($)", 1000, 20000, 5000, 500)
    revenue_per_fte = st.number_input("Revenue per FTE/Month ($)", 5000, 50000, 15000, 1000)

cost_params = {
    "avg_annual_salary": float(avg_salary),
    "contractor_daily_rate": float(contractor_rate),
    "training_cost_per_employee": float(training_cost),
    "revenue_per_fte_per_month": float(revenue_per_fte),
}

# Financial Summary
with st.spinner("Computing financial summary..."):
    summary = get_financial_summary(cost_params=cost_params)

render_kpi_row({
    "Total Headcount": summary.total_headcount,
    "Total FTE": f"{summary.total_fte:,.1f}",
    "Est. Annual Payroll": f"${summary.estimated_annual_payroll:,.0f}",
    "Revenue at Risk/Mo": f"${summary.revenue_at_risk_monthly:,.0f}",
})

st.markdown("---")

# Financial breakdown
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Cost Breakdown")
    cost_items = {
        "Hiring Pipeline": summary.external_hiring_pipeline_cost,
        "Training Investment": summary.training_investment,
        "Contractor Spend (Monthly)": summary.contractor_spend_monthly,
        "Bench Waste (Monthly)": summary.bench_waste_monthly,
    }
    non_zero = {k: v for k, v in cost_items.items() if v > 0}
    if non_zero:
        fig = px.pie(
            names=list(non_zero.keys()),
            values=list(non_zero.values()),
            hole=0.4,
            color_discrete_sequence=["#e74c3c", "#f39c12", "#3498db", "#95a5a6"],
        )
        fig.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No active cost items. Gap analysis has not generated recommendations requiring financial action.")

with col2:
    st.subheader("📈 Financial Details")
    detail_rows = [
        {"Metric": "Total Headcount", "Value": f"{summary.total_headcount:,}"},
        {"Metric": "Total FTE", "Value": f"{summary.total_fte:,.1f}"},
        {"Metric": "Annual Payroll (Est.)", "Value": f"${summary.estimated_annual_payroll:,.0f}"},
        {"Metric": "Bench FTE", "Value": f"{summary.details.get('bench_fte', 0):,.1f}"},
        {"Metric": "Bench Waste (Monthly)", "Value": f"${summary.bench_waste_monthly:,.0f}"},
        {"Metric": "Hiring Recommendations", "Value": f"{summary.details.get('hire_recommendations', 0)}"},
        {"Metric": "Training Recommendations", "Value": f"{summary.details.get('training_recommendations', 0)}"},
        {"Metric": "Contractor Recommendations", "Value": f"{summary.details.get('contractor_recommendations', 0)}"},
        {"Metric": "Total Shortage FTE", "Value": f"{summary.details.get('total_shortage_fte', 0):,.1f}"},
        {"Metric": "Revenue at Risk (Monthly)", "Value": f"${summary.revenue_at_risk_monthly:,.0f}"},
    ]
    st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

# Cost comparison table
st.markdown("---")
st.subheader("💹 Recommendation Cost-Benefit Analysis")

cost_table = get_cost_comparison_table(cost_params=cost_params)
if not cost_table.empty:
    st.dataframe(cost_table, use_container_width=True, hide_index=True)

    # ROI chart
    recs = estimate_recommendation_costs(cost_params=cost_params)
    if recs:
        roi_data = pd.DataFrame([{
            "Action": r.action,
            "Estimated Cost": r.estimated_cost,
            "Expected Savings": r.expected_annual_savings,
            "ROI %": r.roi_pct,
        } for r in recs])

        fig_roi = go.Figure()
        fig_roi.add_trace(go.Bar(
            x=roi_data["Action"], y=roi_data["Estimated Cost"],
            name="Cost", marker_color="#e74c3c",
        ))
        fig_roi.add_trace(go.Bar(
            x=roi_data["Action"], y=roi_data["Expected Savings"],
            name="Savings", marker_color="#2ecc71",
        ))
        fig_roi.update_layout(
            title="Cost vs. Expected Savings by Action",
            barmode="group",
            yaxis_title="USD ($)",
            height=400,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_roi, use_container_width=True)
else:
    st.info("No recommendation cost data available. Run gap analysis to generate actionable recommendations.")
