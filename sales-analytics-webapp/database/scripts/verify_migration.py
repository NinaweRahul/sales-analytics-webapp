"""
Verify the Olist star schema migration:
  1. Row counts match between raw.* and analytics.fact_* tables
  2. Aggregate sums match (price, payment_value) — catches silent JOIN loss
  3. customer_unique_id count < customer_id count (proves repeat customers
     exist and were preserved correctly — this is THE reason we picked
     this dataset over the flat-file version)
  4. The read-only role genuinely cannot write, and cannot see raw.*

Usage:
    python verify_migration.py

Requires in .env:
    DATABASE_URL=...              (admin connection)
    READONLY_DATABASE_URL=...     (analytics_readonly connection)
"""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError, DBAPIError

load_dotenv()


def check_row_counts(engine):
    print("=" * 60)
    print("CHECK 1: Row counts (raw -> analytics)")
    print("=" * 60)

    checks = [
        ("raw.order_items", "analytics.fact_order_items"),
        ("raw.order_payments", "analytics.fact_payments"),
        ("raw.order_reviews", "analytics.fact_reviews"),
    ]

    all_pass = True
    with engine.connect() as conn:
        for raw_table, fact_table in checks:
            raw_count = conn.execute(text(f"SELECT COUNT(*) FROM {raw_table}")).scalar()
            fact_count = conn.execute(text(f"SELECT COUNT(*) FROM {fact_table}")).scalar()

            status = "✓ PASS" if raw_count == fact_count else "✗ FAIL"
            if raw_count != fact_count:
                all_pass = False

            print(f"  {raw_table:28s} {raw_count:>8,}  vs  {fact_table:28s} {fact_count:>8,}  [{status}]")

    print()
    return all_pass


def check_aggregate_sums(engine):
    print("=" * 60)
    print("CHECK 2: Aggregate sums (price, payment_value)")
    print("=" * 60)

    with engine.connect() as conn:
        raw_price = conn.execute(text("SELECT SUM(price) FROM raw.order_items")).scalar()
        fact_price = conn.execute(text("SELECT SUM(price) FROM analytics.fact_order_items")).scalar()

        raw_payment = conn.execute(text("SELECT SUM(payment_value) FROM raw.order_payments")).scalar()
        fact_payment = conn.execute(text("SELECT SUM(payment_value) FROM analytics.fact_payments")).scalar()

    price_ok = abs(raw_price - fact_price) < 0.01
    payment_ok = abs(raw_payment - fact_payment) < 0.01

    print(f"  price          — raw: {raw_price:>14,.2f}  |  fact: {fact_price:>14,.2f}  [{'✓ PASS' if price_ok else '✗ FAIL'}]")
    print(f"  payment_value  — raw: {raw_payment:>14,.2f}  |  fact: {fact_payment:>14,.2f}  [{'✓ PASS' if payment_ok else '✗ FAIL'}]")
    print()

    return price_ok and payment_ok


def check_customer_identity(engine):
    print("=" * 60)
    print("CHECK 3: Customer identity (customer_id vs customer_unique_id)")
    print("=" * 60)

    with engine.connect() as conn:
        order_level_count = conn.execute(
            text("SELECT COUNT(DISTINCT customer_id) FROM analytics.dim_customers")
        ).scalar()
        person_level_count = conn.execute(
            text("SELECT COUNT(DISTINCT customer_unique_id) FROM analytics.dim_customers")
        ).scalar()

    repeat_customers = order_level_count - person_level_count

    print(f"  Distinct customer_id (per-order):        {order_level_count:,}")
    print(f"  Distinct customer_unique_id (per-person): {person_level_count:,}")
    print(f"  Implied repeat-purchase orders:            {repeat_customers:,}")

    if person_level_count < order_level_count:
        print("  ✓ PASS — customer_unique_id correctly collapses repeat customers\n")
        return True
    else:
        print("  ✗ FAIL — expected person_level_count < order_level_count\n")
        return False


def check_readonly_guardrail():
    print("=" * 60)
    print("CHECK 4: Read-only role guardrails")
    print("=" * 60)

    readonly_url = os.getenv("READONLY_DATABASE_URL")
    if not readonly_url:
        print("  ⚠ SKIPPED — READONLY_DATABASE_URL not set in .env\n")
        return None

    readonly_engine = create_engine(readonly_url)
    all_pass = True

    # 4a: Should be able to SELECT from analytics schema
    try:
        with readonly_engine.connect() as conn:
            conn.execute(text("SELECT * FROM analytics.fact_order_items LIMIT 1"))
        print("  ✓ PASS — can SELECT from analytics.fact_order_items")
    except (ProgrammingError, DBAPIError) as e:
        print(f"  ✗ FAIL — could not SELECT from analytics schema: {e}")
        all_pass = False

    # 4b: Should NOT be able to see raw schema at all
    try:
        with readonly_engine.connect() as conn:
            conn.execute(text("SELECT * FROM raw.customers LIMIT 1"))
        print("  ✗ FAIL — read-only role can access raw.customers (should be invisible)")
        all_pass = False
    except (ProgrammingError, DBAPIError) as e:
        if "permission denied" in str(e).lower() or "does not exist" in str(e).lower():
            print("  ✓ PASS — raw schema correctly inaccessible")
        else:
            print(f"  ⚠ Unexpected error: {e}")
            all_pass = False

    # 4c: Should NOT be able to INSERT
    try:
        with readonly_engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO analytics.dim_sellers (seller_id) VALUES ('test')"
            ))
        print("  ✗ FAIL — read-only role was able to INSERT")
        all_pass = False
    except (ProgrammingError, DBAPIError) as e:
        if "permission denied" in str(e).lower():
            print("  ✓ PASS — INSERT correctly rejected")
        else:
            print(f"  ⚠ Unexpected error (not a permission error): {e}")
            all_pass = False

    print()
    return all_pass


def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set.")
        sys.exit(1)

    engine = create_engine(db_url)

    results = [
        check_row_counts(engine),
        check_aggregate_sums(engine),
        check_customer_identity(engine),
        check_readonly_guardrail(),
    ]

    results = [r for r in results if r is not None]

    print("=" * 60)
    if all(results):
        print("ALL CHECKS PASSED ✓")
    else:
        print("SOME CHECKS FAILED ✗ — review output above")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
