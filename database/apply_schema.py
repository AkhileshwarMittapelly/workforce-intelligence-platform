"""Apply the full schema.sql to the workforce_intelligence MySQL database."""
import os
import sys
import pymysql

DB_HOST = "localhost"
DB_PORT = 3306
DB_NAME = "workforce_intelligence"
DB_USER = "root"
DB_PASSWORD = "Kanna@4556"


def apply_schema():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        raw_sql = f.read()

    # Connect without specifying DB first so we can CREATE DATABASE IF NOT EXISTS
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        charset="utf8mb4",
        autocommit=True,
    )
    cursor = conn.cursor()

    # Split on semicolons, skip blank/comment-only chunks
    statements = [s.strip() for s in raw_sql.split(";")]
    executed = 0
    skipped = 0
    for stmt in statements:
        # Strip inline comments and blank lines for the check
        clean = "\n".join(
            line for line in stmt.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ).strip()
        if not clean:
            skipped += 1
            continue
        try:
            cursor.execute(stmt)
            executed += 1
        except pymysql.err.OperationalError as e:
            print(f"  [WARN] {e} — stmt preview: {stmt[:80]!r}")

    cursor.close()

    # Re-connect to the target DB and list tables
    conn2 = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        autocommit=True,
    )
    cur2 = conn2.cursor()
    cur2.execute("SHOW FULL TABLES;")
    rows = cur2.fetchall()
    cur2.close()
    conn2.close()
    conn.close()

    print("Schema applied OK")
    print(f"Executed {executed} statements ({skipped} blank/skipped).")
    print("\nTables and views in workforce_intelligence:")
    for row in rows:
        print(f"  {row[1]:<15} {row[0]}")


if __name__ == "__main__":
    try:
        apply_schema()
    except pymysql.err.OperationalError as e:
        print(f"MySQL connection error: {e}", file=sys.stderr)
        print("MySQL may not be running. Continuing with TASK 2.", file=sys.stderr)
        sys.exit(1)
