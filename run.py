#!/usr/bin/env python
"""
Workforce Intelligence Platform - Quickstart Entry Script.

Usage:
    python run.py             # Verifies seed data & starts Streamlit app on port 8501
    python run.py --datagen   # Regenerates starter synthetic data
    python run.py --test      # Executes full automated test suite
"""

import argparse
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent


def ensure_seed_data() -> None:
    """Generates synthetic baseline data if not present."""
    data_dir = PROJECT_ROOT / "data"
    employees_csv = data_dir / "employees.csv"
    if not employees_csv.exists():
        print("[Workforce Intelligence] Seed data not found. Generating starter dataset (seed: 20261022)...")
        subprocess.run([
            sys.executable,
            str(PROJECT_ROOT / "src" / "generators" / "synthetic_data_generator.py"),
            "--scale", "starter",
            "--seed", "20261022",
        ], check=True)
        print("[Workforce Intelligence] Starter data ready.")


def run_tests() -> None:
    """Runs full automated pytest suite."""
    print("[Workforce Intelligence] Running automated test suite...")
    cmd = [sys.executable, "-m", "pytest", "tests/", "-v"]
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def run_streamlit() -> None:
    """Launches Streamlit dashboard on port 8501."""
    ensure_seed_data()
    print("[Workforce Intelligence] Launching Streamlit web application on http://localhost:8501 ...")
    cmd = [
        sys.executable,
        "-m", "streamlit", "run",
        str(PROJECT_ROOT / "app" / "main.py"),
        "--server.port", "8501",
        "--server.headless", "true",
    ]
    subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(description="Workforce Intelligence Platform Runner")
    parser.add_argument("--datagen", action="store_true", help="Force regenerate synthetic data")
    parser.add_argument("--scale", default="starter", choices=["starter", "full"], help="Dataset scale")
    parser.add_argument("--test", action="store_true", help="Run automated tests")
    args = parser.parse_args()

    if args.test:
        run_tests()
    elif args.datagen:
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "src" / "generators" / "synthetic_data_generator.py"),
            "--scale", args.scale,
            "--seed", "20261022",
        ]
        subprocess.run(cmd, check=True)
    else:
        run_streamlit()


if __name__ == "__main__":
    main()
