"""
Database Access & CSV Fallback Service.

Provides unified DataFrame access to all 10 workforce entities.
Attempts live SQLAlchemy querying first; seamlessly falls back to local data/ CSVs
if the database is unreachable or offline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
import pandas as pd
from sqlalchemy import text

from src.db.connection import get_engine

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _read_csv(filename: str) -> pd.DataFrame:
    """Helper to read CSV from data/ with error handling."""
    file_path = DATA_DIR / filename
    if file_path.exists():
        try:
            return pd.read_csv(file_path, low_memory=False)
        except Exception as e:
            logger.warning("Error reading %s: %s", filename, e)
    return pd.DataFrame()


def _query_or_fallback(query: str, csv_name: str) -> pd.DataFrame:
    """Tries executing SQL query on SQLAlchemy engine; falls back to CSV on any error."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            df = pd.read_sql_query(text(query), conn)
            if not df.empty:
                return df
    except Exception as e:
        logger.debug("Database query failed (%s), falling back to CSV %s", e, csv_name)
    return _read_csv(csv_name)


def get_roles() -> pd.DataFrame:
    """Return all organizational roles."""
    return _query_or_fallback("SELECT * FROM role", "roles.csv")


def get_active_employees() -> pd.DataFrame:
    """Return all active employees."""
    df = _query_or_fallback(
        "SELECT * FROM employee WHERE is_current = TRUE AND status != 'TERMINATED'",
        "employees.csv"
    )
    if not df.empty and "status" in df.columns:
        return df[df["status"] != "TERMINATED"]
    return df


def get_skills() -> pd.DataFrame:
    """Return skill taxonomy catalog."""
    return _query_or_fallback("SELECT * FROM skill", "skills.csv")


def get_employee_skills(employee_id: Optional[str] = None, skill_id: Optional[str] = None) -> pd.DataFrame:
    """Return employee competency ratings."""
    df = _query_or_fallback("SELECT * FROM employee_skill", "employee_skills.csv")
    if not df.empty:
        if employee_id:
            df = df[df["employee_id"] == employee_id]
        if skill_id:
            df = df[df["skill_id"] == skill_id]
    return df


def get_projects() -> pd.DataFrame:
    """Return projects catalog."""
    return _query_or_fallback("SELECT * FROM project", "projects.csv")


def get_demand_plans(project_id: Optional[str] = None) -> pd.DataFrame:
    """Return staffing demand plans."""
    df = _query_or_fallback("SELECT * FROM demand_plan", "demand_plans.csv")
    if not df.empty and project_id:
        df = df[df["project_id"] == project_id]
    return df


def get_allocations(employee_id: Optional[str] = None, project_id: Optional[str] = None) -> pd.DataFrame:
    """Return workforce allocations."""
    df = _query_or_fallback("SELECT * FROM allocation", "allocations.csv")
    if not df.empty:
        if employee_id:
            df = df[df["employee_id"] == employee_id]
        if project_id:
            df = df[df["project_id"] == project_id]
    return df


def get_availability(employee_id: Optional[str] = None) -> pd.DataFrame:
    """Return periodic capacity and bench availability."""
    df = _query_or_fallback("SELECT * FROM availability", "availability.csv")
    if not df.empty and employee_id:
        df = df[df["employee_id"] == employee_id]
    return df


def get_training(employee_id: Optional[str] = None) -> pd.DataFrame:
    """Return training and enablement courses."""
    df = _query_or_fallback("SELECT * FROM training", "training.csv")
    if not df.empty and employee_id:
        df = df[df["employee_id"] == employee_id]
    return df


def get_gap_analyses(severity: Optional[str] = None) -> pd.DataFrame:
    """Return capability gap diagnostics."""
    df = _query_or_fallback("SELECT * FROM gap_analysis", "gap_analysis.csv")
    if not df.empty and severity:
        df = df[df["gap_severity"] == severity]
    return df
