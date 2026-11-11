"""
Skill Inventory & Competency Matrix View.
"""

from pathlib import Path
import sys
import pandas as pd
import streamlit as st
import plotly.express as px

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.services.db_service import get_skills, get_employee_skills, get_active_employees
from app.components.kpi_cards import render_kpi_row, render_alert_banner
from app.components.charts import skill_heatmap

st.set_page_config(page_title="Skill Inventory", page_icon="🎯", layout="wide")

st.title("🎯 Competency Matrix & Skill Portfolio")
st.caption("Standardized skill taxonomy, verified proficiency levels, and capability freshness tracking")

skills_df = get_skills()
esk_df = get_employee_skills()
emp_df = get_active_employees()

if skills_df.empty or esk_df.empty:
    st.info("No skill or employee competency data found. Run the data generator first.")
    st.stop()

# Join with employee & skill details
merged_df = esk_df.merge(skills_df[["skill_id", "skill_name", "category"]], on="skill_id", how="left")
if not emp_df.empty and "first_name" in emp_df.columns:
    emp_df["full_name"] = emp_df["first_name"] + " " + emp_df["last_name"]
    merged_df = merged_df.merge(emp_df[["employee_id", "full_name", "department"]], on="employee_id", how="left")

# KPIs
total_skills = len(skills_df)
expert_ratings = len(merged_df[merged_df["proficiency_level"] >= 4])
avg_prof = round(float(merged_df["proficiency_level"].mean()), 2) if "proficiency_level" in merged_df.columns else 0.0

# Stale skills detection (last_evaluated_date > 18 months or > 540 days ago from 2026-10-22)
stale_skills_df = pd.DataFrame()
if "last_evaluated_date" in merged_df.columns:
    cutoff_date = pd.to_datetime("2025-04-22")
    merged_df["evaluated_dt"] = pd.to_datetime(merged_df["last_evaluated_date"], errors="coerce")
    stale_skills_df = merged_df[
        (merged_df["evaluated_dt"] < cutoff_date) & 
        (merged_df["status"] == "ACTIVE")
    ]
stale_count = len(stale_skills_df)

render_kpi_row({
    "Taxonomy Skills": total_skills,
    "Verified Ratings": len(merged_df),
    "Avg Proficiency (1-5)": avg_prof,
    "Stale Active Ratings": stale_count,
})

if stale_count > 0:
    render_alert_banner(
        "high",
        f"Detected {stale_count} active employee skill rating(s) with evaluation dates older than 18 months! Re-certification required."
    )

st.markdown("---")

col1, col2 = st.columns([1, 2])
with col1:
    st.subheader("Category Distribution")
    if "category" in skills_df.columns:
        cat_counts = skills_df["category"].value_counts().reset_index()
        cat_counts.columns = ["Category", "Count"]
        fig_cat = px.pie(cat_counts, names="Category", values="Count", hole=0.45, color_discrete_sequence=px.colors.qualitative.Prism)
        fig_cat.update_layout(height=350, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig_cat, use_container_width=True)

with col2:
    st.subheader("Top Skills by Certified Talent")
    top_skills = merged_df.groupby("skill_name").agg(
        total_consultants=("employee_id", "count"),
        avg_proficiency=("proficiency_level", "mean")
    ).reset_index().sort_values(by="total_consultants", ascending=False).head(10)
    top_skills["avg_proficiency"] = top_skills["avg_proficiency"].round(1)

    fig_bar = px.bar(
        top_skills, x="total_consultants", y="skill_name", orientation="h",
        color="avg_proficiency", color_continuous_scale="Viridis",
        labels={"total_consultants": "Employees Verified", "skill_name": "Skill", "avg_proficiency": "Avg Level"}
    )
    fig_bar.update_layout(yaxis=dict(autorange="reversed"), height=350, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_bar, use_container_width=True)

st.subheader("📊 Competency Portfolio Search & Directory")
filter_col1, filter_col2 = st.columns(2)
with filter_col1:
    cats = ["ALL"] + sorted(skills_df["category"].dropna().unique().tolist()) if "category" in skills_df.columns else ["ALL"]
    sel_cat = st.selectbox("Filter Category", cats)
with filter_col2:
    min_level = st.slider("Minimum Proficiency Level", 1, 5, 1)

disp_df = merged_df.copy()
if sel_cat != "ALL":
    disp_df = disp_df[disp_df["category"] == sel_cat]
disp_df = disp_df[disp_df["proficiency_level"] >= min_level]

cols_to_show = [c for c in ["employee_id", "full_name", "department", "skill_name", "category", "proficiency_level", "years_of_experience", "verification_status", "last_evaluated_date", "status"] if c in disp_df.columns]
st.dataframe(disp_df[cols_to_show].sort_values(by="proficiency_level", ascending=False), use_container_width=True, hide_index=True)

if not stale_skills_df.empty:
    with st.expander(f"⚠️ View {stale_count} Stale Skills Requiring Re-evaluation", expanded=False):
        st.dataframe(stale_skills_df[cols_to_show], use_container_width=True, hide_index=True)
