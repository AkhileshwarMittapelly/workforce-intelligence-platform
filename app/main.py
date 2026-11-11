"""
Workforce Intelligence Platform - Streamlit Main Entry Point
"""

import streamlit as st

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

with st.expander("Database Status & Configuration", expanded=True):
    st.info("MySQL 8.0 schema is defined in `database/schema.sql`.")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Core Entities", value="10")
    with col2:
        st.metric(label="Target Engine", value="InnoDB")
    with col3:
        st.metric(label="Target RDBMS", value="MySQL 8.0+")

st.sidebar.success("Select a module above to begin.")
