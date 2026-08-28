"""
Single source of truth describing the analytics star schema.

Used by:
  - query_generator.py    (rendered into the LLM prompt)
  - sql_validator.py      (table/column allowlist)
  - (future) /api/schema  (feeds the frontend's schema explorer tab)

Keeping this as structured data rather than a hardcoded prompt string
means the prompt, the validator, and the schema-explorer API can never
drift out of sync with each other.
"""

from dataclasses import dataclass, field


@dataclass
class Column:
    name: str
    dtype: str
    description: str = ""


@dataclass
class Table:
    name: str  # fully qualified, e.g. "analytics.dim_customers"
    grain: str  # what one row represents — critical for the LLM to avoid double-counting
    columns: list[Column]
    notes: str = ""


SCHEMA: list[Table] = [
    Table(
        name="analytics.dim_customers",
        grain="one row per order (customer_id), NOT one row per person",
        columns=[
            Column("customer_id", "VARCHAR", "Per-order customer identifier. Primary key of this table."),
            Column("customer_unique_id", "VARCHAR",
                   "Per-PERSON identifier, stable across multiple orders. "
                   "Use this column (not customer_id) for repeat-purchase, "
                   "customer count, or customer-lifetime-value questions."),
            Column("customer_city", "VARCHAR", ""),
            Column("customer_state", "VARCHAR", "2-letter Brazilian state code"),
        ],
        notes=(
            "CRITICAL: a single real customer can appear as multiple rows here "
            "(one per order they placed), each with a different customer_id but "
            "the SAME customer_unique_id. COUNT(DISTINCT customer_id) counts orders' "
            "worth of customer slots, not real people. COUNT(DISTINCT customer_unique_id) "
            "counts real people."
        ),
    ),
    Table(
        name="analytics.dim_products",
        grain="one row per product SKU",
        columns=[
            Column("product_id", "VARCHAR", "Primary key"),
            Column("category_name_english", "VARCHAR", "Use this for category filtering/grouping, not category_name (Portuguese)"),
            Column("category_name", "VARCHAR", "Original Portuguese category name — avoid unless specifically asked for"),
            Column("weight_g", "NUMERIC", ""),
            Column("length_cm", "NUMERIC", ""),
            Column("height_cm", "NUMERIC", ""),
            Column("width_cm", "NUMERIC", ""),
        ],
    ),
    Table(
        name="analytics.dim_sellers",
        grain="one row per seller",
        columns=[
            Column("seller_id", "VARCHAR", "Primary key"),
            Column("seller_city", "VARCHAR", ""),
            Column("seller_state", "VARCHAR", "2-letter Brazilian state code"),
        ],
    ),
    Table(
        name="analytics.dim_date",
        grain="one row per calendar date that appears in the order data",
        columns=[
            Column("date_id", "INTEGER", "Primary key"),
            Column("full_date", "DATE", ""),
            Column("day", "INTEGER", ""),
            Column("month", "INTEGER", "1-12"),
            Column("month_name", "VARCHAR", ""),
            Column("quarter", "INTEGER", "1-4"),
            Column("year", "INTEGER", ""),
        ],
    ),
    Table(
        name="analytics.fact_order_items",
        grain="one row per line item within an order (an order can have multiple items)",
        columns=[
            Column("fact_id", "INTEGER", "Primary key"),
            Column("order_id", "VARCHAR", ""),
            Column("order_item_id", "INTEGER", ""),
            Column("customer_id", "VARCHAR", "Foreign key -> dim_customers.customer_id"),
            Column("product_id", "VARCHAR", "Foreign key -> dim_products.product_id"),
            Column("seller_id", "VARCHAR", "Foreign key -> dim_sellers.seller_id"),
            Column("order_purchase_date_id", "INTEGER", "Foreign key -> dim_date.date_id"),
            Column("order_status", "VARCHAR", "e.g. delivered, shipped, canceled"),
            Column("price", "NUMERIC", "Item price — this is the revenue figure, use SUM(price) for total revenue"),
            Column("freight_value", "NUMERIC", "Shipping cost for this item"),
            Column("days_to_delivery", "NUMERIC", "Purchase date to delivered date, in days. NULL if not yet delivered."),
            Column("delivery_vs_estimate_days", "NUMERIC",
                   "Actual delivery minus estimated delivery, in days. "
                   "POSITIVE means late, NEGATIVE means early/on-time."),
        ],
        notes=(
            "This is the PRIMARY fact table for revenue, product, and delivery questions. "
            "Do NOT join fact_payments or fact_reviews onto this table and then SUM(price) — "
            "an order with 2 items and 3 payment installments would multiply price by 3, "
            "inflating revenue. If a question needs items AND payments/reviews together, "
            "aggregate each fact table separately first, then join the aggregates."
        ),
    ),
    Table(
        name="analytics.fact_payments",
        grain="one row per payment installment (an order can have multiple)",
        columns=[
            Column("payment_fact_id", "INTEGER", "Primary key"),
            Column("order_id", "VARCHAR", ""),
            Column("payment_sequential", "INTEGER", ""),
            Column("payment_type", "VARCHAR", "e.g. credit_card, boleto, voucher"),
            Column("payment_installments", "INTEGER", ""),
            Column("payment_value", "NUMERIC", ""),
        ],
        notes="Separate grain from fact_order_items — see warning there before joining.",
    ),
    Table(
        name="analytics.fact_reviews",
        grain="one row per review",
        columns=[
            Column("fact_review_id", "INTEGER", "Primary key"),
            Column("review_id", "VARCHAR", "NOT unique alone in source data — see notes"),
            Column("order_id", "VARCHAR", ""),
            Column("review_score", "INTEGER", "1-5"),
            Column("review_creation_date", "TIMESTAMP", ""),
        ],
        notes="Not every order has a review. Use LEFT JOIN from orders/items if reviews are optional context.",
    ),
]


RELATIONSHIPS = """
analytics.fact_order_items.customer_id           -> analytics.dim_customers.customer_id
analytics.fact_order_items.product_id            -> analytics.dim_products.product_id
analytics.fact_order_items.seller_id             -> analytics.dim_sellers.seller_id
analytics.fact_order_items.order_purchase_date_id -> analytics.dim_date.date_id
analytics.fact_payments.order_id                 -> analytics.fact_order_items.order_id (via orders, not a direct FK)
analytics.fact_reviews.order_id                  -> analytics.fact_order_items.order_id (via orders, not a direct FK)
"""


def render_schema_for_prompt() -> str:
    """Render the schema as text for injection into the LLM prompt."""
    lines = []
    for table in SCHEMA:
        lines.append(f"\nTABLE: {table.name}")
        lines.append(f"GRAIN: {table.grain}")
        lines.append("COLUMNS:")
        for col in table.columns:
            desc = f" — {col.description}" if col.description else ""
            lines.append(f"  - {col.name} ({col.dtype}){desc}")
        if table.notes:
            lines.append(f"NOTES: {table.notes}")

    lines.append("\nRELATIONSHIPS (for JOINs):")
    lines.append(RELATIONSHIPS)

    return "\n".join(lines)


def get_all_table_names() -> set[str]:
    """Used by the validator's table allowlist."""
    return {t.name for t in SCHEMA} | {t.name.split(".")[-1] for t in SCHEMA}


def get_all_column_names() -> set[str]:
    """Used by the validator's column allowlist (unqualified names)."""
    names = set()
    for t in SCHEMA:
        for c in t.columns:
            names.add(c.name)
    return names
