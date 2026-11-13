"""
Demand Forecasting & Capacity Planning View.
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

from src.services.db_service import get_demand_plans, get_projects, get_roles, get_skills
from src.services.forecast_service import run_forecast, ForecastResult
from app.components.kpi_cards import render_kpi_row, render_alert_banner

st.set_page_config(page_title="Demand Forecasting", page_icon="📈", layout="wide")

st.title("📈 Forward-Looking Staffing Demand & Forecasting")
st.caption("Forecast project labor requirements by role, skill, and schedule vs. workforce supply with risk analysis")

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

# Execute live demand vs supply forecast
forecast_records = run_forecast()
fcst_df = pd.DataFrame([vars(r) for r in forecast_records]) if forecast_records else pd.DataFrame()

# Enrich forecast with role and skill names
if not fcst_df.empty:
    if not roles_df.empty and "role_name" in roles_df.columns:
        fcst_df = fcst_df.merge(roles_df[["role_id", "role_name"]], on="role_id", how="left")
    if not skills_df.empty and "skill_name" in skills_df.columns:
        fcst_df = fcst_df.merge(skills_df[["skill_id", "skill_name"]], on="skill_id", how="left")

# High-level KPIs
total_demand_records = len(demand_df)
total_required_fte = demand_df["required_fte"].sum() if "required_fte" in demand_df.columns else 0.0
total_headcount = int(demand_df["headcount_required"].sum()) if "headcount_required" in demand_df.columns else 0
unfulfilled = len(demand_df[demand_df["fulfillment_status"] == "UNFULFILLED"]) if "fulfillment_status" in demand_df.columns else 0

total_shortage_fte = fcst_df[fcst_df["gap_fte"] > 0]["gap_fte"].sum() if not fcst_df.empty else 0.0
critical_risks = len(fcst_df[fcst_df["risk_level"] == "CRITICAL"]) if not fcst_df.empty else 0

render_kpi_row({
    "Demand Plans": total_demand_records,
    "Required FTE": f"{total_required_fte:.1f}",
    "Total Shortage FTE": f"{total_shortage_fte:.1f}",
    "Critical Risk Periods": critical_risks,
    "Unfulfilled Requests": unfulfilled,
})

if critical_risks > 0:
    render_alert_banner("critical", f"Detected {critical_risks} critical shortage periods where demand outstrips active workforce capacity!")

st.markdown("---")

# Filters
col1, col2, col3, col4 = st.columns(4)
with col1:
    priorities = ["ALL"] + sorted(demand_df["priority"].dropna().unique().tolist()) if "priority" in demand_df.columns else ["ALL"]
    sel_priority = st.selectbox("Demand Priority", priorities)
with col2:
    status_opts = ["ALL"] + sorted(demand_df["fulfillment_status"].dropna().unique().tolist()) if "fulfillment_status" in demand_df.columns else ["ALL"]
    sel_status = st.selectbox("Fulfillment Status", status_opts)
with col3:
    role_opts = ["ALL"] + sorted(demand_df["role_name"].dropna().unique().tolist()) if "role_name" in demand_df.columns else ["ALL"]
    sel_role = st.selectbox("Role Filter", role_opts)
with col4:
    risk_opts = ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"]
    sel_risk = st.selectbox("Forecast Risk Level", risk_opts)

filtered_df = demand_df.copy()
if sel_priority != "ALL":
    filtered_df = filtered_df[filtered_df["priority"] == sel_priority]
if sel_status != "ALL":
    filtered_df = filtered_df[filtered_df["fulfillment_status"] == sel_status]
if sel_role != "ALL" and "role_name" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["role_name"] == sel_role]

filtered_fcst = fcst_df.copy() if not fcst_df.empty else pd.DataFrame()
if not filtered_fcst.empty:
    if sel_role != "ALL" and "role_name" in filtered_fcst.columns:
        filtered_fcst = filtered_fcst[filtered_fcst["role_name"] == sel_role]
    if sel_risk != "ALL" and "risk_level" in filtered_fcst.columns:
        filtered_fcst = filtered_fcst[filtered_fcst["risk_level"] == sel_risk]

# Charts Section
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("FTE Demand vs. Shortage by Role")
    if not filtered_fcst.empty and "role_name" in filtered_fcst.columns:
        role_agg = filtered_fcst.groupby("role_name").agg({
            "demand_fte": "sum",
            "gap_fte": "sum",
        }).reset_index().sort_values(by="demand_fte", ascending=False).head(10)
        
        fig_role = go.Figure()
        fig_role.add_trace(go.Bar(
            y=role_agg["role_name"], x=role_agg["demand_fte"],
            name="Demand FTE", orientation="h", marker_color="#3498db"
        ))
        fig_role.add_trace(go.Bar(
            y=role_agg["role_name"], x=role_agg["gap_fte"],
            name="Shortage FTE", orientation="h", marker_color="#e74c3c"
        ))
        fig_role.update_layout(
            barmode="group",
            yaxis=dict(autorange="reversed"),
            height=350,
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_role, use_container_width=True)
    elif "role_name" in filtered_df.columns and "required_fte" in filtered_df.columns:
        role_sum = filtered_df.groupby("role_name")["required_fte"].sum().reset_index().sort_values(by="required_fte", ascending=False).head(10)
        fig_role = px.bar(
            role_sum, x="required_fte", y="role_name", orientation="h",
            color="required_fte", color_continuous_scale="Blues",
            labels={"required_fte": "Total Required FTE", "role_name": "Role"}
        )
        fig_role.update_layout(yaxis=dict(autorange="reversed"), height=350, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_role, use_container_width=True)

with col_chart2:
    st.subheader("Forecast Risk Severity Distribution")
    if not filtered_fcst.empty and "risk_level" in filtered_fcst.columns:
        risk_counts = filtered_fcst["risk_level"].value_counts().reset_index()
        risk_counts.columns = ["Risk Level", "Count"]
        color_map = {"CRITICAL": "#e74c3c", "HIGH": "#e67e22", "MEDIUM": "#f1c40f", "LOW": "#2ecc71"}
        fig_pie = px.pie(
            risk_counts, names="Risk Level", values="Count",
            color="Risk Level", color_discrete_map=color_map, hole=0.4
        )
        fig_pie.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_pie, use_container_width=True)
    elif "fulfillment_status" in filtered_df.columns:
        fig_pie = px.pie(
            filtered_df, names="fulfillment_status",
            color_discrete_sequence=["#e74c3c", "#f39c12", "#2ecc71", "#95a5a6"],
            hole=0.4
        )
        fig_pie.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_pie, use_container_width=True)

# Forecast Table
st.subheader("📊 Forecast Model Output & Supply-Demand Equilibrium")
if not filtered_fcst.empty:
    display_fcst_cols = [c for c in [
        "period", "role_name", "skill_name", "demand_fte", "supply_fte",
        "gap_fte", "utilization_pct", "risk_level", "assumptions"
    ] if c in filtered_fcst.columns]
    st.dataframe(filtered_fcst[display_fcst_cols], use_container_width=True, hide_index=True)

    fcst_csv = filtered_fcst[display_fcst_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Forecast Model Output (CSV)",
        data=fcst_csv,
        file_name="forecast_model_results.csv",
        mime="text/csv",
    )
else:
    st.info("No forecast results available for current filter criteria.")

# Staffing Demand Schedule Table
st.subheader("📋 Staffing Demand Schedule & Timeline")
display_cols = [c for c in ["demand_id", "project_name", "role_name", "skill_name", "headcount_required", "required_fte", "priority", "fulfillment_status", "start_date", "end_date"] if c in filtered_df.columns]
st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)

# CSV Download
csv_data = filtered_df[display_cols].to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 Download Staffing Demand Schedule (CSV)",
    data=csv_data,
    file_name="demand_schedule.csv",
    mime="text/csv",
)

# ── Demand Duplication & Forecast Comparison ──────────────────────────────────
st.divider()
st.subheader("🔍 Demand Duplication Analysis & Corrected Forecast Comparison")
st.caption("Composite duplicate detection on: Project + Role + Required Skill + Period Start + Period End")

try:
    from src.services.forecast_service import forecast_comparison, evaluate_forecast_accuracy
    comparison = forecast_comparison()

    c_dup1, c_dup2, c_dup3 = st.columns(3)
    c_dup1.metric("Original Demanded FTE (Raw)", f"{comparison['original_total_demand_fte']:.2f}")
    c_dup2.metric("Corrected Demanded FTE (Deduplicated)", f"{comparison['corrected_total_demand_fte']:.2f}")
    c_dup3.metric("Double-Counted FTE Removed", f"{comparison['double_counted_fte_delta']:.2f}", delta=f"-{comparison['double_counted_fte_delta']:.2f}", delta_color="inverse")

    dup_list = comparison.get("duplicate_exceptions", [])
    if dup_list:
        st.warning(f"⚠️ **{len(dup_list)} duplicate demand record(s) detected and flagged for exclusion from corrected planning horizons.**")
        st.dataframe(pd.DataFrame(dup_list), use_container_width=True, hide_index=True)
    else:
        st.success("✓ No composite duplicate demand records detected in current horizon.")

    # ── Holdout Forecast Accuracy Evaluation ──────────────────────────────────
    st.divider()
    st.subheader("🎯 Statistical Forecast Accuracy Metrics (Empirical Holdout)")
    st.caption("Standard statistical evaluation comparing forward labor requirements against empirical committed allocations")

    acc = evaluate_forecast_accuracy()
    if acc.get("status") == "EVALUATED":
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Mean Absolute Error (MAE)", f"{acc['mae']} FTE")
        a2.metric("Root Mean Squared Error (RMSE)", f"{acc['rmse']} FTE")
        a3.metric("WAPE %", f"{acc['wape_pct']}%")
        a4.metric("Forecast Bias %", f"{acc['forecast_bias_pct']}%")
        st.info(f"**Target Variable**: {acc['target_variable']} | **Evaluation Horizon**: Sample of {acc['sample_size']} active delivery initiatives | **Assumptions**: {acc['assumptions']}")
except Exception as exc:
    st.info(f"Duplicate comparison & accuracy evaluation preview unavailable: {exc}")

# ── Time-Series Forecasting Models ──────────────────────────────────────────
st.divider()
st.subheader("📈 Advanced Time-Series Forecasting Models")
st.caption("Chronological holdout evaluation of Naive, Moving Average, Exponential Smoothing, and Holt's Linear Trend")

try:
    from src.services.forecast_service import get_demand_time_series_forecast
    ts_result = get_demand_time_series_forecast()

    if ts_result.get("status") == "EVALUATED":
        best_model = ts_result.get("best_model_name", "N/A")
        models_info = ts_result.get("models", {})

        ts1, ts2, ts3 = st.columns(3)
        ts1.metric("Best Model", best_model)
        best_key = ts_result.get("best_model", "")
        if best_key in models_info:
            ts2.metric("WAPE", f"{models_info[best_key]['metrics']['wape_pct']}%")
            ts3.metric("RMSE", f"{models_info[best_key]['metrics']['rmse']}")

        # Model comparison table
        model_rows = []
        for mkey, mdata in models_info.items():
            model_rows.append({
                "Model": mdata["name"],
                "MAE": mdata["metrics"]["mae"],
                "RMSE": mdata["metrics"]["rmse"],
                "WAPE %": mdata["metrics"]["wape_pct"],
                "Bias %": mdata["metrics"]["forecast_bias_pct"],
            })
        if model_rows:
            model_df = pd.DataFrame(model_rows)
            st.dataframe(model_df, use_container_width=True, hide_index=True)

        # Actual vs Forecast chart
        hist_periods = ts_result.get("historical_periods", [])
        hist_values = ts_result.get("historical_values", [])
        future_periods = ts_result.get("future_periods", [])
        future_forecast = ts_result.get("future_forecast", [])
        conf_lower = ts_result.get("confidence_lower", [])
        conf_upper = ts_result.get("confidence_upper", [])

        if hist_periods and future_periods:
            fig_ts = go.Figure()
            fig_ts.add_trace(go.Scatter(
                x=hist_periods, y=hist_values,
                mode="lines+markers", name="Historical Demand",
                line=dict(color="#3498db", width=2),
            ))
            fig_ts.add_trace(go.Scatter(
                x=future_periods, y=future_forecast,
                mode="lines+markers", name="Forecast",
                line=dict(color="#e74c3c", width=2, dash="dash"),
            ))
            if conf_lower and conf_upper:
                fig_ts.add_trace(go.Scatter(
                    x=future_periods + future_periods[::-1],
                    y=conf_upper + conf_lower[::-1],
                    fill="toself", fillcolor="rgba(231,76,60,0.1)",
                    line=dict(color="rgba(231,76,60,0)"),
                    name="95% Confidence Interval",
                ))
            fig_ts.update_layout(
                title="Demand Forecast with Confidence Intervals",
                xaxis_title="Period",
                yaxis_title="Demand FTE",
                height=400,
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_ts, use_container_width=True)

        st.info(ts_result.get("explanation", ""))
    elif ts_result.get("status") == "INSUFFICIENT_SERIES":
        st.warning("Insufficient historical data points for time-series model evaluation.")
    else:
        st.info("Time-series forecast not available.")
except Exception as exc:
    st.info(f"Time-series forecast unavailable: {exc}")
