"""
KPI display components for Workforce Intelligence Platform.
"""

import streamlit as st


def render_kpi_row(metrics_dict: dict) -> None:
    """
    Display up to 4 KPI metrics in a horizontal column layout using st.metric().

    Args:
        metrics_dict: Dict mapping label -> value (or label -> {value, delta, help}).
                      Supports up to 4 entries; extra entries are ignored.
    Example:
        render_kpi_row({
            "Total Headcount": {"value": 240, "delta": "+5"},
            "Active Employees": 215,
            "Avg Utilization": {"value": "78.4%", "delta": "-2.1%"},
            "Bench Available": 25,
        })
    """
    items = list(metrics_dict.items())[:4]
    cols = st.columns(len(items))

    for col, (label, val) in zip(cols, items):
        with col:
            if isinstance(val, dict):
                value = val.get("value", "—")
                delta = val.get("delta", None)
                help_text = val.get("help", None)
                delta_color = val.get("delta_color", "normal")
                st.metric(label=label, value=value, delta=delta, delta_color=delta_color, help=help_text)
            else:
                st.metric(label=label, value=val)


def render_alert_banner(severity: str, message: str) -> None:
    """
    Render a colored alert banner using the appropriate Streamlit alert function.

    Args:
        severity: One of 'critical', 'high', 'warning', 'info', 'success'.
        message: The message text to display.
    """
    severity_lower = severity.lower()

    if severity_lower in ("critical", "error"):
        st.error(f"🔴 **{severity.upper()}** — {message}")
    elif severity_lower in ("high", "warning", "medium"):
        st.warning(f"🟠 **{severity.upper()}** — {message}")
    elif severity_lower in ("low", "info"):
        st.info(f"🔵 **{severity.upper()}** — {message}")
    elif severity_lower == "success":
        st.success(f"🟢 **SUCCESS** — {message}")
    else:
        st.info(f"ℹ️ {message}")


def render_recommendation_card(rec_dict: dict) -> None:
    """
    Render a formatted card for a gap recommendation.

    Args:
        rec_dict: Dict with keys from gap_analysis data:
            - skill_name (str)
            - role_title (str)
            - project_name (str)
            - shortage_headcount (int)
            - severity (str)
            - recommended_action (str)  e.g. 'HIRE', 'UPSKILL', 'REALLOCATE'
            - reasoning (str)
            - gap_id (str, optional)
    """
    severity = rec_dict.get("severity", "MEDIUM")
    action = rec_dict.get("recommended_action", "REVIEW")
    skill = rec_dict.get("skill_name", "Unknown Skill")
    role = rec_dict.get("role_title", "Unknown Role")
    project = rec_dict.get("project_name", "Unknown Project")
    shortage = rec_dict.get("shortage_headcount", 0)
    reasoning = rec_dict.get("reasoning", "No reasoning provided.")
    gap_id = rec_dict.get("gap_id", "")

    sev_colors = {
        "CRITICAL": "🔴",
        "HIGH": "🟠",
        "MEDIUM": "🟡",
        "LOW": "🟢",
    }
    action_icons = {
        "HIRE": "👤",
        "UPSKILL": "📚",
        "REALLOCATE": "🔄",
        "TRAIN": "🎓",
        "REVIEW": "🔍",
    }

    sev_icon = sev_colors.get(severity, "⚪")
    act_icon = action_icons.get(action, "📋")

    with st.container():
        st.markdown(
            f"""
<div style="
    border-left: 4px solid {'#d63031' if severity == 'CRITICAL' else '#e17055' if severity == 'HIGH' else '#fdcb6e' if severity == 'MEDIUM' else '#00b894'};
    padding: 12px 16px;
    margin-bottom: 10px;
    background: rgba(0,0,0,0.02);
    border-radius: 4px;
">
<b>{sev_icon} {severity}</b> &nbsp;|&nbsp; {act_icon} <b>Action: {action}</b>
{'&nbsp;&nbsp;<code>' + gap_id + '</code>' if gap_id else ''}<br>
<b>Skill:</b> {skill} &nbsp;•&nbsp; <b>Role:</b> {role} &nbsp;•&nbsp; <b>Project:</b> {project}<br>
<b>Shortage:</b> {shortage} headcount<br>
<small style="color:#555;">{reasoning}</small>
</div>
""",
            unsafe_allow_html=True,
        )
