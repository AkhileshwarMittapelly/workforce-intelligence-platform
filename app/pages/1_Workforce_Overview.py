"""
Workforce Overview — Streamlit page.
Displays headcount KPIs, department breakdown, employment type distribution,
workforce table, and per-department utilization gauges.
"""

import sys
from pathlib import Path

# Allow imports from project src/
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px

from app.components.charts import department_capacity_bar, utilization_gauge
from app.components.kpi_cards import render_kpi_row, render_alert_banner

st.set_page_config(page_title="Workforce Overview", page_icon="👥", layout="wide")

DATA_DIR = Path(__file__).parent.parent.parent / "data"


@st.cache_data(ttl=300)
def load_employees() -> pd.DataFrame | None:
    path = DATA_DIR / "employees.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


@st.cache_data(ttl=300)
def load_availability() -> pd.DataFrame | None:
    path = DATA_DIR / "availability.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


# ── Page header ──────────────────────────────────────────────────────────────
st.title("👥 Workforce Overview")
st.caption("Headcount, utilization and workforce composition at a glance")

employees = load_employees()
availability = load_availability()

if employees is None:
    st.info(
        "📂 **No employee data found.**  "
        "Run the data generator first:  \n"
        "`python src/generators/synthetic_data_generator.py --scale starter`"
    )
    st.stop()

# ── KPI Row ───────────────────────────────────────────────────────────────────
total_headcount = len(employees)
status_col = "status" if "status" in employees.columns else ("employment_status" if "employment_status" in employees.columns else None)
active_employees = int(employees[status_col].eq("ACTIVE").sum()) if status_col else total_headcount

avg_utilization = 0.0
bench_available = 0
avail_pct_col = "availability_percentage" if availability is not None and "availability_percentage" in availability.columns else ("availability_pct" if availability is not None and "availability_pct" in availability.columns else None)
if availability is not None and avail_pct_col:
    avg_utilization = round(float(100.0 - availability[avail_pct_col].mean()), 1)
    avg_utilization = max(0.0, min(100.0, avg_utilization))
    bench_col = "availability_type" if "availability_type" in availability.columns else None
    if bench_col:
        bench_available = int(availability[availability[bench_col] == "AVAILABLE_BENCH"].shape[0])

render_kpi_row({
    "Total Headcount": {"value": total_headcount},
    "Active Employees": {"value": active_employees, "delta": f"{active_employees - total_headcount}"},
    "Avg Utilization %": {"value": f"{avg_utilization}%"},
    "Bench Available": {"value": bench_available},
})

st.divider()

# ── Department breakdown + Employment type ────────────────────────────────────
col_left, col_right = st.columns([2, 1])

dept_col = "department" if "department" in employees.columns else None

with col_left:
    st.subheader("Department Breakdown")
    if dept_col:
        dept_counts = employees[dept_col].value_counts().reset_index()
        dept_counts.columns = ["department", "headcount"]
        fig_dept = px.bar(
            dept_counts,
            x="department",
            y="headcount",
            color="headcount",
            color_continuous_scale="Blues",
            labels={"department": "Department", "headcount": "Headcount"},
        )
        fig_dept.update_layout(
            height=350,
            margin=dict(l=40, r=20, t=20, b=80),
            xaxis_tickangle=-30,
            showlegend=False,
            coloraxis_showscale=False,
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_dept, use_container_width=True)
    else:
        st.info("No 'department' column in employees.csv")

with col_right:
    st.subheader("Employment Type")
    emp_type_col = "employment_type" if "employment_type" in employees.columns else None
    if emp_type_col:
        type_counts = employees[emp_type_col].value_counts().reset_index()
        type_counts.columns = ["employment_type", "count"]
        fig_type = px.pie(
            type_counts,
            names="employment_type",
            values="count",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_type.update_layout(
            height=350,
            margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_type, use_container_width=True)
    else:
        st.info("No 'employment_type' column in employees.csv")

st.divider()

# ── Workforce Table with Filters ──────────────────────────────────────────────
st.subheader("🗂️ Active Workforce")

filter_col1, filter_col2, filter_col3 = st.columns(3)

dept_options = ["All"] + sorted(employees[dept_col].dropna().unique().tolist()) if dept_col else ["All"]
role_col = "current_role_id" if "current_role_id" in employees.columns else ("role_title" if "role_title" in employees.columns else ("role_id" if "role_id" in employees.columns else None))

with filter_col1:
    sel_dept = st.selectbox("Department", dept_options)
with filter_col2:
    role_options = ["All"] + sorted(employees[role_col].dropna().unique().tolist()) if role_col else ["All"]
    sel_role = st.selectbox("Role", role_options)
with filter_col3:
    status_options = ["All"] + sorted(employees[status_col].dropna().unique().tolist()) if status_col else ["All"]
    sel_status = st.selectbox("Status", status_options)

filtered = employees.copy()
if sel_dept != "All" and dept_col:
    filtered = filtered[filtered[dept_col] == sel_dept]
if sel_role != "All" and role_col:
    filtered = filtered[filtered[role_col] == sel_role]
if sel_status != "All" and status_col:
    filtered = filtered[filtered[status_col] == sel_status]

# Pagination
PAGE_SIZE = 20
total_rows = len(filtered)
total_pages = max(1, (total_rows + PAGE_SIZE - 1) // PAGE_SIZE)
page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
start = (page - 1) * PAGE_SIZE
end = start + PAGE_SIZE

st.caption(f"Showing {min(end, total_rows)} of {total_rows} employees (page {page}/{total_pages})")
st.dataframe(filtered.iloc[start:end], use_container_width=True, height=460)

# ── Department Utilization Gauges ─────────────────────────────────────────────
st.divider()
st.subheader("📊 Department Utilization Gauges")

if availability is not None and dept_col and avail_pct_col:
    # Merge to get department
    emp_id_col = "employee_id" if "employee_id" in employees.columns else employees.columns[0]
    avl_id_col = "employee_id" if "employee_id" in availability.columns else availability.columns[0]

    if avl_id_col in availability.columns and emp_id_col in employees.columns:
        merged = availability.merge(employees[[emp_id_col, dept_col]], left_on=avl_id_col, right_on=emp_id_col, how="left")
        # Calculate utilization as 100 - availability_percentage
        merged["utilization_pct"] = (100.0 - merged[avail_pct_col]).clip(lower=0.0, upper=100.0)
        dept_util = (
            merged.groupby(dept_col)["utilization_pct"]
            .mean()
            .reset_index()
            .rename(columns={"utilization_pct": "capacity_pct"})
        )

        # Show bar chart
        st.plotly_chart(department_capacity_bar(dept_util), use_container_width=True)

        # Gauges per department (up to 6)
        gauge_depts = dept_util.head(6)
        gauge_cols = st.columns(min(3, len(gauge_depts)))
        for i, (_, row) in enumerate(gauge_depts.iterrows()):
            with gauge_cols[i % 3]:
                st.plotly_chart(
                    utilization_gauge(float(row["capacity_pct"]), row[dept_col]),
                    use_container_width=True,
                )
    else:
        st.info("Employee-availability join not possible — check column names.")
elif availability is None:
    render_alert_banner("info", "availability.csv not found — utilization gauges unavailable.")
else:
    st.info("Missing required columns for utilization breakdown.")

# ── Weekly Capacity Reconciliation & Exceptions ─────────────────────────────
st.divider()
st.subheader("⚖️ Weekly Capacity Reconciliation & Over-Allocation Exceptions")
st.caption("Source-driven reconciliation: Contracted = Base × FTE | Net = Contracted − Leave | Remaining = Net − Allocated (Unclamped)")

try:
    from src.services.capacity_service import reconcile_weekly_capacities_df
    recon_df = reconcile_weekly_capacities_df(data_dir=DATA_DIR)
    if not recon_df.empty:
        c1, c2, c3, c4 = st.columns(4)
        over_allocated = recon_df[recon_df["capacity_status"] == "OVER_ALLOCATED"]
        on_leave = recon_df[recon_df["capacity_status"] == "ON_APPROVED_LEAVE"]
        fully_alloc = recon_df[recon_df["capacity_status"] == "FULLY_ALLOCATED"]
        bench_free = recon_df[recon_df["capacity_status"] == "AVAILABLE_BENCH"]

        c1.metric("Total Reconciled Staff", len(recon_df))
        c2.metric("Over-Allocated Exceptions", len(over_allocated), delta=f"-{len(over_allocated)}" if len(over_allocated) > 0 else "0", delta_color="inverse")
        c3.metric("On Approved Leave", len(on_leave))
        c4.metric("Available on Bench", len(bench_free))

        if not over_allocated.empty:
            render_alert_banner("warning", f"**Over-Allocation Alert**: {len(over_allocated)} employee(s) have negative remaining capacity after factoring contracted FTE, approved leave, and project allocations.")
            st.dataframe(
                over_allocated[["employee_id", "employee_name", "department", "fte", "contracted_hours", "approved_leave_hours", "allocated_hours", "remaining_capacity_hours", "over_allocation_percentage", "capacity_status"]],
                use_container_width=True,
                hide_index=True,
            )

        with st.expander("📋 View Full Period Capacity Reconciliation Table", expanded=False):
            st.dataframe(recon_df, use_container_width=True, hide_index=True)
except Exception as exc:
    st.info(f"Capacity reconciliation preview unavailable: {exc}")
