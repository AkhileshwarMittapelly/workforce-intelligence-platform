"""
Database connection manager, session factory, and diagnostic connectivity test for MySQL 8.0.
Reuses SQLAlchemy and PyMySQL to manage pooled connections and verify database health.
"""

import logging
from contextlib import contextmanager
from typing import Any, Generator
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import (
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.orm import sessionmaker, Session

from src.config import get_settings

logger = logging.getLogger(__name__)

# The 10 core database entities required by Workforce Intelligence Platform
CORE_TABLES: tuple[str, ...] = (
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
)

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def reset_engine() -> None:
    """Disposes existing engine and resets global connection singletons."""
    global _engine, _SessionFactory
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
    _engine = None
    _SessionFactory = None


def get_engine() -> Engine:
    """Provides a singleton SQLAlchemy engine with PyMySQL driver and connection pooling."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=True,
            echo=settings.app_debug,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    """Returns the thread-safe sessionmaker factory."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionFactory


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for managing transactional database sessions."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def test_connection(engine: Engine | None = None) -> dict[str, Any]:
    """
    Executes diagnostic connectivity test to MySQL and verifies the 10 core tables.

    Operations:
    1. Connects using SQLAlchemy and PyMySQL.
    2. Executes 'SELECT 1' to verify connectivity.
    3. Checks access to all 10 core database tables.
    4. Handles connection, credential, and query errors gracefully.

    Args:
        engine: Optional custom SQLAlchemy Engine (uses get_engine() if omitted).

    Returns:
        dict containing:
        - success (bool): True if SELECT 1 and all 10 core tables are accessible.
        - connected (bool): True if SELECT 1 succeeded.
        - select_1_result (int | None): Result of SELECT 1.
        - database (str): Name of database tested.
        - core_tables_checked (list[str]): Names of 10 required tables.
        - tables_found (list[str]): Core tables discovered in schema.
        - missing_tables (list[str]): Core tables not yet created or inaccessible.
        - all_core_tables_accessible (bool): True if all 10 core tables are present.
        - error_type (str | None): Exception type name if failed.
        - error_message (str | None): Descriptive error message if failed.
    """
    settings = get_settings()
    target_engine = engine or get_engine()

    result: dict[str, Any] = {
        "success": False,
        "connected": False,
        "select_1_result": None,
        "database": settings.db_name,
        "core_tables_checked": list(CORE_TABLES),
        "tables_found": [],
        "missing_tables": list(CORE_TABLES),
        "all_core_tables_accessible": False,
        "error_type": None,
        "error_message": None,
    }

    try:
        # Step 1: Connect and execute SELECT 1
        with target_engine.connect() as conn:
            query_result = conn.execute(text("SELECT 1")).scalar()
            result["connected"] = True
            result["select_1_result"] = query_result

            # Step 2: Inspect existing tables in the database
            inspector = inspect(target_engine)
            existing_tables = set(inspector.get_table_names())

            found_tables: list[str] = []
            missing_tables: list[str] = []

            for tbl in CORE_TABLES:
                if tbl in existing_tables:
                    try:
                        # Step 3: Verify read access to table
                        conn.execute(text(f"SELECT 1 FROM `{tbl}` LIMIT 0"))
                        found_tables.append(tbl)
                    except SQLAlchemyError as tbl_err:
                        logger.warning("Table %s found but query access failed: %s", tbl, tbl_err)
                        missing_tables.append(tbl)
                else:
                    missing_tables.append(tbl)

            result["tables_found"] = found_tables
            result["missing_tables"] = missing_tables
            result["all_core_tables_accessible"] = len(missing_tables) == 0

            # Overall success requires connectivity and all 10 tables accessible
            result["success"] = result["connected"] and result["all_core_tables_accessible"]

    except OperationalError as exc:
        err_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
        logger.error("MySQL Operational Error during test_connection: %s", err_msg)
        result["error_type"] = "OperationalError"
        result["error_message"] = err_msg

    except ProgrammingError as exc:
        err_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
        logger.error("MySQL Programming Error during test_connection: %s", err_msg)
        result["error_type"] = "ProgrammingError"
        result["error_message"] = err_msg

    except SQLAlchemyError as exc:
        err_msg = str(exc)
        logger.error("SQLAlchemy Error during test_connection: %s", err_msg)
        result["error_type"] = type(exc).__name__
        result["error_message"] = err_msg

    except Exception as exc:
        err_msg = str(exc)
        logger.error("Unexpected error during test_connection: %s", err_msg)
        result["error_type"] = type(exc).__name__
        result["error_message"] = err_msg

    return result
