"""
Workforce Intelligence Platform - Streamlit Main Entry Point
"""

from pathlib import Path
import sys
import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.db.connection import test_connection
from src.services.analytics_service import get_workforce_kpis

st.set_page_config(
    page_title="Workforce Intelligence Platform",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Workforce Intelligence Platform")
st.caption("Strategic Workforce Planning, Capability Analysis & Resource Allocation")

st.markdown("""
### Welcome to the Workforce Intelligence Platform

This platform bridges strategic organizational planning with talent supply and project execution:

- **Workforce Inventory**: Single source of truth for employees, organizational roles, and reporting structures.
- **Competency Matrix**: Multi-level skill taxonomy, verified employee proficiencies, and experience tracking.
- **Demand & Allocations**: Project requirements, capacity commitments, and billable utilization.
- **Capacity & Availability**: Bench management, leave tracking, and capacity projections.
- **Upskilling & Training**: Targeted learning journeys designed to close organizational skill shortages.
- **Gap Diagnostics**: Predictive analytics identifying capability shortfalls and recommending mitigation paths.
""")

# Quick Module Directory
st.markdown("### 🧭 Platform Navigation")
c1, c2, c3 = st.columns(3)
with c1:
    st.info("📊 **[1. Workforce Overview](Workforce_Overview)**\n\nActive headcount, department breakdown, capacity metrics.")
    st.info("📈 **[2. Demand Forecasting](Demand_Forecasting)**\n\nProject labor requirements, FTE schedules, fulfillment tracking.")
with c2:
    st.info("🎯 **[3. Skill Inventory](Skill_Matrix)**\n\nVerified competencies, proficiency heatmaps, stale skill warnings.")
    st.info("🔍 **[4. Gap Diagnostics](Gap_Analysis)**\n\nSupply vs demand deficits, hiring vs upskilling recommendations.")
with c3:
    st.info("👥 **[5. Actor Views](Actor_Views)**\n\nPersonalized views for Employee, Manager, HR, IT/Ops, and Admin.")
    st.info("📊 **[6. Analytics Dashboard](Analytics_Dashboard)**\n\n12-month utilization trends, project status, executive KPIs.")

# Live System & Data Status
kpis = get_workforce_kpis()
diag = test_connection()

with st.expander("Database Status & Configuration", expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Core Entities", value="10")
    with col2:
        st.metric(label="Tracked Workforce", value=kpis.total_headcount)
    with col3:
        st.metric(label="Active Skills", value=kpis.skills_tracked)
    with col4:
        db_state = "Connected" if diag["connected"] else "Seed Data Mode"
        st.metric(label="Data Mode", value=db_state)

st.sidebar.success("Select a module above or use the sidebar pages to begin.")
