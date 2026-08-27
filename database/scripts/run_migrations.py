"""
Run the full migration pipeline in order:

    1. 001_create_raw_staging_tables.sql   (DDL)
    2. load_raw_csvs.py                    (Python — loads the 9 CSVs)
    3. 002_create_star_schema.sql          (DDL)
    4. 003_transform_to_star_schema.sql    (raw -> analytics)
    5. 004_create_readonly_role.sql        (security)

This is a Python driver (not a single shell script) because step 2
is a pandas-based CSV load, not raw SQL — mixing that into a .sql
file isn't possible.

Usage:
    python run_migrations.py

Requires DATABASE_URL in .env (admin connection — migrations create
tables/roles/grants, so this must NOT be the read-only role).
"""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"
SCRIPTS_DIR = Path(__file__).parent


def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set. Add it to your .env file.")
        sys.exit(1)
    return create_engine(db_url)


def run_sql_file(engine, filepath):
    print(f"Running {filepath.name} ...")
    sql_text = filepath.read_text()
    with engine.begin() as conn:
        conn.exec_driver_sql(sql_text)
    print(f"  ✓ {filepath.name} complete\n")


def run_python_loader():
    print("Running load_raw_csvs.py ...")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "load_raw_csvs.py")],
        capture_output=False,
    )
    if result.returncode != 0:
        print("  ✗ load_raw_csvs.py failed — stopping pipeline")
        sys.exit(1)
    print("  ✓ load_raw_csvs.py complete\n")


def main():
    engine = get_engine()

    steps = [
        ("sql", MIGRATIONS_DIR / "001_create_raw_staging_tables.sql"),
        ("python", None),  # load_raw_csvs.py
        ("sql", MIGRATIONS_DIR / "002_create_star_schema.sql"),
        ("sql", MIGRATIONS_DIR / "003_transform_to_star_schema.sql"),
        ("sql", MIGRATIONS_DIR / "004_create_readonly_role.sql"),
    ]

    print("Migration pipeline:")
    for kind, path in steps:
        label = path.name if path else "load_raw_csvs.py (Python — loads 9 CSVs)"
        print(f"  - {label}")
    print()

    for kind, path in steps:
        if kind == "sql":
            run_sql_file(engine, path)
        else:
            run_python_loader()

    print("Pipeline complete. Run verify_migration.py next.")


if __name__ == "__main__":
    main()
