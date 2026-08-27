"""
Load the 9 Olist CSVs into the raw.* staging tables.

Prerequisite: download the dataset from
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
and place all 9 CSVs, unmodified, in database/data/raw/

Usage:
    python load_raw_csvs.py

Requires DATABASE_URL in .env, and that migration 001
(001_create_raw_staging_tables.sql) has already been run.
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data" / "raw"

# Maps: CSV filename -> (staging table name, column rename dict)
# Column renames handle the couple of Kaggle typos (e.g. "lenght") and
# align with our staging DDL.
FILES = {
    "olist_customers_dataset.csv": (
        "raw.customers",
        {},
    ),
    "olist_orders_dataset.csv": (
        "raw.orders",
        {},
    ),
    "olist_sellers_dataset.csv": (
        "raw.sellers",
        {},
    ),
    "product_category_name_translation.csv": (
        "raw.category_translation",
        {},
    ),
    "olist_products_dataset.csv": (
        "raw.products",
        {
            "product_name_lenght": "product_name_length",
            "product_description_lenght": "product_description_length",
        },
    ),
    "olist_order_items_dataset.csv": (
        "raw.order_items",
        {},
    ),
    "olist_order_payments_dataset.csv": (
        "raw.order_payments",
        {},
    ),
    "olist_order_reviews_dataset.csv": (
        "raw.order_reviews",
        {},
    ),
    "olist_geolocation_dataset.csv": (
        "raw.geolocation",
        {},
    ),
}

# Load order matters: parents before children (FK dependencies)
LOAD_ORDER = [
    "olist_customers_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
    "olist_products_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_geolocation_dataset.csv",
]


def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)
    return create_engine(db_url)


def check_files_present():
    missing = [f for f in LOAD_ORDER if not (DATA_DIR / f).exists()]
    if missing:
        print(f"ERROR: Missing CSV files in {DATA_DIR}:")
        for f in missing:
            print(f"  - {f}")
        print(
            "\nDownload the dataset from "
            "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce "
            "and place all 9 CSVs in that folder."
        )
        sys.exit(1)


def load_file(engine, filename):
    table_name, renames = FILES[filename]
    schema, table = table_name.split(".")
    filepath = DATA_DIR / filename

    print(f"Loading {filename} -> {table_name} ...")

    df = pd.read_csv(filepath)

    if renames:
        df = df.rename(columns=renames)

    # Parse timestamp columns where present (pandas infers dtype=object otherwise)
    timestamp_cols = [c for c in df.columns if "date" in c or "timestamp" in c]
    for col in timestamp_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    rows_before = len(df)

    df.to_sql(
        table,
        engine,
        schema=schema,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=5000,
    )

    print(f"  ✓ Loaded {rows_before:,} rows\n")


def main():
    check_files_present()
    engine = get_engine()

    print(f"Loading Olist dataset from {DATA_DIR}\n")

    for filename in LOAD_ORDER:
        load_file(engine, filename)

    print("All raw tables loaded successfully.")
    print("Next: run 002_create_star_schema.sql, then 003_transform_to_star_schema.sql")


if __name__ == "__main__":
    main()
