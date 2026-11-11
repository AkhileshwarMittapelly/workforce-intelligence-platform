"""
Unit and integration tests for Python-MySQL connection and diagnostic test_connection().
"""

import os
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from src.config import Settings
from src.db.connection import (
    CORE_TABLES,
    get_engine,
    get_settings,
    reset_engine,
    test_connection as run_test_connection,
)


def test_settings_database_url_formatting():
    """Validates that database URL uses SQLAlchemy + PyMySQL and URL-encodes special characters."""
    settings = Settings(
        db_host="127.0.0.1",
        db_port=3306,
        db_name="workforce_intelligence",
        db_user="admin",
        db_password="P@ss#word/1!$",
    )
    url = settings.database_url
    assert url.startswith("mysql+pymysql://admin:P%40ss%23word%2F1%21%24@127.0.0.1:3306/workforce_intelligence")
    assert "charset=utf8mb4" in url


def test_default_database_name():
    """Validates that target database name defaults to workforce_intelligence."""
    settings = Settings()
    assert settings.db_name == "workforce_intelligence"


def test_core_tables_list_completeness():
    """Ensures all 10 core tables are defined for connectivity verification."""
    expected = {
        "role",
        "employee",
        "skill",
        "employee_skill",
        "project",
        "demand_plan",
        "allocation",
        "availability",
        "training",
        "gap_analysis",
    }
    assert set(CORE_TABLES) == expected
    assert len(CORE_TABLES) == 10


def test_connection_graceful_error_handling_unreachable():
    """Verifies that invalid host/port does not crash and returns structured error details."""
    dummy_engine = create_engine(
        "mysql+pymysql://invalid_user:invalid_pwd@127.0.0.1:9999/workforce_intelligence",
        connect_args={"connect_timeout": 1},
    )
    diag = run_test_connection(dummy_engine)

    assert diag["success"] is False
    assert diag["connected"] is False
    assert diag["select_1_result"] is None
    assert diag["all_core_tables_accessible"] is False
    assert diag["error_type"] is not None
    assert diag["error_message"] is not None
    assert len(diag["missing_tables"]) == 10


def test_connection_mocked_success_all_tables():
    """Tests test_connection() logic when SELECT 1 succeeds and all 10 tables exist."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # SELECT 1 returns 1
    mock_scalar = MagicMock()
    mock_scalar.scalar.return_value = 1
    mock_conn.execute.return_value = mock_scalar

    # Mock inspector to report all 10 core tables exist
    with patch("src.db.connection.inspect") as mock_inspect:
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = list(CORE_TABLES)
        mock_inspect.return_value = mock_inspector

        diag = run_test_connection(mock_engine)

        assert diag["connected"] is True
        assert diag["select_1_result"] == 1
        assert diag["all_core_tables_accessible"] is True
        assert diag["success"] is True
        assert len(diag["tables_found"]) == 10
        assert len(diag["missing_tables"]) == 0
        assert diag["error_type"] is None


def test_connection_mocked_partial_tables():
    """Tests test_connection() when some tables are missing."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    mock_scalar = MagicMock()
    mock_scalar.scalar.return_value = 1
    mock_conn.execute.return_value = mock_scalar

    with patch("src.db.connection.inspect") as mock_inspect:
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["role", "employee", "skill"]
        mock_inspect.return_value = mock_inspector

        diag = run_test_connection(mock_engine)

        assert diag["connected"] is True
        assert diag["select_1_result"] == 1
        assert diag["all_core_tables_accessible"] is False
        assert diag["success"] is False
        assert set(diag["tables_found"]) == {"role", "employee", "skill"}
        assert len(diag["missing_tables"]) == 7


def test_live_database_connection():
    """
    Executes live database test_connection() using current environment configuration.
    Verifies that test_connection executes cleanly, returns the expected dictionary contract,
    and handles live connection status without unhandled exceptions.
    """
    reset_engine()
    diag = run_test_connection()

    # The dictionary contract must always be respected
    assert isinstance(diag, dict)
    assert "success" in diag
    assert "connected" in diag
    assert "select_1_result" in diag
    assert "database" in diag
    assert "core_tables_checked" in diag
    assert "tables_found" in diag
    assert "missing_tables" in diag
    assert "all_core_tables_accessible" in diag
    assert "error_type" in diag
    assert "error_message" in diag

    assert diag["database"] == "workforce_intelligence"
    assert len(diag["core_tables_checked"]) == 10

    # Output live diagnostic for visibility in test report
    print("\n--- Live Database Diagnostic Result ---")
    print(f"Target Database: {diag['database']}")
    print(f"Connected: {diag['connected']}")
    print(f"SELECT 1 Result: {diag['select_1_result']}")
    print(f"Tables Found: {diag['tables_found']}")
    print(f"Missing Tables: {diag['missing_tables']}")
    if diag["error_message"]:
        print(f"Connection Note/Error: [{diag['error_type']}] {diag['error_message']}")
