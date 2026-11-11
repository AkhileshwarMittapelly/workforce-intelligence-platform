"""
Reusable Plotly chart components for Workforce Intelligence Platform.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.graph_objects import Figure


def utilization_gauge(value: float, title: str = "Utilization") -> Figure:
    """
    Gauge chart displaying utilization percentage 0-100%.

    Args:
        value: Utilization percentage (0-100).
        title: Chart title.

    Returns:
        Plotly Figure with a gauge chart.
    """
    color = "#2ecc71" if value < 70 else ("#f39c12" if value < 90 else "#e74c3c")

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=value,
            title={"text": title, "font": {"size": 16}},
            number={"suffix": "%", "font": {"size": 24}},
            delta={"reference": 80, "increasing": {"color": "#e74c3c"}, "decreasing": {"color": "#2ecc71"}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#555"},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 70], "color": "#d5f5e3"},
                    {"range": [70, 90], "color": "#fdebd0"},
                    {"range": [90, 100], "color": "#fadbd8"},
                ],
                "threshold": {
                    "line": {"color": "#e74c3c", "width": 3},
                    "thickness": 0.75,
                    "value": 95,
                },
            },
        )
    )
    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#333"},
    )
    return fig


def skill_heatmap(df: pd.DataFrame) -> Figure:
    """
    Employee vs skill proficiency heatmap.

    Args:
        df: DataFrame with columns [employee_name, skill_name, proficiency_level].
            proficiency_level should be numeric (1-5) or will be mapped from strings.

    Returns:
        Plotly Figure with a heatmap.
    """
    proficiency_map = {"BEGINNER": 1, "INTERMEDIATE": 2, "ADVANCED": 3, "EXPERT": 4, "MASTER": 5}

    df = df.copy()
    if df["proficiency_level"].dtype == object:
        df["proficiency_level"] = df["proficiency_level"].map(proficiency_map).fillna(1)

    pivot = df.pivot_table(
        index="employee_name",
        columns="skill_name",
        values="proficiency_level",
        aggfunc="mean",
    ).fillna(0)

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[
                [0.0, "#f0f4f8"],
                [0.2, "#bde0fe"],
                [0.4, "#74b9ff"],
                [0.6, "#0984e3"],
                [0.8, "#6c5ce7"],
                [1.0, "#2d3436"],
            ],
            zmin=0,
            zmax=5,
            colorbar=dict(
                title="Proficiency",
                tickvals=[0, 1, 2, 3, 4, 5],
                ticktext=["N/A", "Beginner", "Intermediate", "Advanced", "Expert", "Master"],
            ),
            hoverongaps=False,
            hovertemplate="<b>%{y}</b><br>Skill: %{x}<br>Proficiency: %{z:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Employee-Skill Proficiency Matrix",
        xaxis={"title": "Skills", "tickangle": -45},
        yaxis={"title": "Employees"},
        height=max(400, len(pivot) * 25 + 100),
        margin=dict(l=120, r=40, t=60, b=120),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def demand_vs_supply_bar(df: pd.DataFrame) -> Figure:
    """
    Grouped bar chart showing demand vs supply by role.

    Args:
        df: DataFrame with columns [role, required_headcount, available_headcount].

    Returns:
        Plotly Figure with grouped bar chart.
    """
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Required (Demand)",
            x=df["role"],
            y=df["required_headcount"],
            marker_color="#6c5ce7",
            text=df["required_headcount"],
            textposition="outside",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Available (Supply)",
            x=df["role"],
            y=df["available_headcount"],
            marker_color="#00b894",
            text=df["available_headcount"],
            textposition="outside",
        )
    )

    # Add gap annotation
    if "gap" in df.columns:
        fig.add_trace(
            go.Bar(
                name="Gap",
                x=df["role"],
                y=df["gap"],
                marker_color="#d63031",
                text=df["gap"],
                textposition="outside",
            )
        )

    fig.update_layout(
        title="Demand vs Supply by Role",
        barmode="group",
        xaxis={"title": "Role", "tickangle": -30},
        yaxis={"title": "Headcount"},
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=420,
        margin=dict(l=60, r=40, t=80, b=100),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def gap_severity_pie(df: pd.DataFrame) -> Figure:
    """
    Pie chart of gap severity distribution.

    Args:
        df: DataFrame with columns [severity, count] or just [severity] for value_counts.

    Returns:
        Plotly Figure with pie chart.
    """
    color_map = {
        "CRITICAL": "#d63031",
        "HIGH": "#e17055",
        "MEDIUM": "#fdcb6e",
        "LOW": "#00b894",
    }

    if "count" not in df.columns:
        counts = df["severity"].value_counts().reset_index()
        counts.columns = ["severity", "count"]
    else:
        counts = df[["severity", "count"]].copy()

    colors = [color_map.get(s, "#74b9ff") for s in counts["severity"]]

    fig = go.Figure(
        data=go.Pie(
            labels=counts["severity"],
            values=counts["count"],
            hole=0.4,
            marker=dict(colors=colors, line=dict(color="white", width=2)),
            hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Share: %{percent}<extra></extra>",
            textinfo="label+percent",
        )
    )
    fig.update_layout(
        title="Gap Severity Distribution",
        height=350,
        margin=dict(l=20, r=20, t=60, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
    )
    return fig


def workforce_trend_line(df: pd.DataFrame) -> Figure:
    """
    Monthly headcount/utilization trend line chart.

    Args:
        df: DataFrame with columns [month, headcount, utilization_pct] (utilization optional).

    Returns:
        Plotly Figure with line chart.
    """
    fig = go.Figure()

    if "headcount" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["headcount"],
                mode="lines+markers",
                name="Headcount",
                line=dict(color="#6c5ce7", width=2),
                marker=dict(size=6),
                yaxis="y",
            )
        )

    if "utilization_pct" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["month"],
                y=df["utilization_pct"],
                mode="lines+markers",
                name="Utilization %",
                line=dict(color="#e17055", width=2, dash="dot"),
                marker=dict(size=6, symbol="diamond"),
                yaxis="y2",
            )
        )

    fig.update_layout(
        title="Workforce Trend (Monthly)",
        xaxis={"title": "Month"},
        yaxis={"title": "Headcount", "side": "left"},
        yaxis2={"title": "Utilization %", "side": "right", "overlaying": "y", "range": [0, 110]},
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=380,
        margin=dict(l=60, r=60, t=80, b=60),
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
    )
    return fig


def department_capacity_bar(df: pd.DataFrame) -> Figure:
    """
    Horizontal bar chart of department capacity utilization.

    Args:
        df: DataFrame with columns [department, capacity_pct] and optionally [headcount].

    Returns:
        Plotly Figure with horizontal bar chart.
    """
    df_sorted = df.sort_values("capacity_pct", ascending=True)

    colors = [
        "#d63031" if v >= 95 else ("#e17055" if v >= 80 else ("#fdcb6e" if v >= 60 else "#00b894"))
        for v in df_sorted["capacity_pct"]
    ]

    hover_text = []
    for _, row in df_sorted.iterrows():
        txt = f"Dept: {row['department']}<br>Capacity: {row['capacity_pct']:.1f}%"
        if "headcount" in df_sorted.columns:
            txt += f"<br>Headcount: {row['headcount']}"
        hover_text.append(txt)

    fig = go.Figure(
        go.Bar(
            x=df_sorted["capacity_pct"],
            y=df_sorted["department"],
            orientation="h",
            marker_color=colors,
            text=[f"{v:.1f}%" for v in df_sorted["capacity_pct"]],
            textposition="outside",
            hovertext=hover_text,
            hoverinfo="text",
        )
    )

    fig.add_vline(x=80, line_dash="dash", line_color="#e17055", annotation_text="80% threshold")
    fig.add_vline(x=95, line_dash="dash", line_color="#d63031", annotation_text="95% critical")

    fig.update_layout(
        title="Department Capacity Utilization",
        xaxis={"title": "Utilization %", "range": [0, 115]},
        yaxis={"title": "Department"},
        height=max(350, len(df_sorted) * 35 + 100),
        margin=dict(l=120, r=60, t=60, b=60),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
