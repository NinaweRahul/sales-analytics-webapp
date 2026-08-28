"""
Validate LLM-generated SQL before it ever reaches the database.

This is a SECOND line of defense — the real backstop is the
analytics_readonly Postgres role (see database/migrations/004), which
physically cannot write regardless of what SQL is generated. This
validator exists to:
  1. Reject anything that isn't a single, clean SELECT (before wasting
     a database round-trip on something that would fail anyway)
  2. Reject queries against tables/columns outside the known schema
     (catches hallucinated table names early, with a clear error)
  3. Enforce a hard row LIMIT regardless of what the LLM wrote

Using sqlglot (an actual SQL parser) instead of regex/keyword matching
because keyword blocklists are trivially bypassed by obfuscation
(comments, string concatenation, alternate casing) — a parser that
understands SQL structure cannot be talked around the same way.
"""

import sqlglot
from sqlglot import exp

from schema_context import get_all_table_names, get_all_column_names

MAX_ROW_LIMIT = 1000


class SQLValidationError(Exception):
    """Raised when generated SQL fails validation. Message is safe to show the user."""
    pass


def validate_and_prepare(sql: str) -> str:
    """
    Validate a generated SQL string and return a safe-to-execute version
    (with a row limit enforced). Raises SQLValidationError on any
    violation, with a message describing what's wrong — this message
    can be fed back to the LLM for a regeneration attempt.
    """
    sql = sql.strip().rstrip(";")

    if not sql:
        raise SQLValidationError("Generated SQL is empty.")

    # --- Parse ---
    try:
        parsed = sqlglot.parse_one(sql, read="postgres")
    except Exception as e:
        raise SQLValidationError(f"SQL does not parse: {e}")

    # --- Must be a single SELECT statement ---
    if not isinstance(parsed, exp.Select):
        raise SQLValidationError(
            f"Only SELECT statements are allowed. Got: {type(parsed).__name__}"
        )

    # --- Reject multiple statements smuggled via semicolons ---
    # sqlglot.parse() (plural) returns a list of statements; if there's
    # more than one, something was concatenated that shouldn't be.
    all_statements = sqlglot.parse(sql, read="postgres")
    if len(all_statements) > 1:
        raise SQLValidationError(
            "Multiple SQL statements detected. Only one SELECT is allowed."
        )

    # --- Reject any write/DDL keywords anywhere in the parse tree ---
    # (belt-and-suspenders on top of "must be exp.Select" above — this
    # catches write operations hidden inside subqueries or CTEs)
    forbidden_types = (
        exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
        exp.Alter, exp.TruncateTable,
    )
    for node in parsed.walk():
        if isinstance(node[0], forbidden_types):
            raise SQLValidationError(
                f"Query contains a forbidden operation: {type(node[0]).__name__}"
            )

    # --- Table allowlist ---
    valid_tables = get_all_table_names()
    referenced_tables = {t.name for t in parsed.find_all(exp.Table)}

    unknown_tables = {
        t for t in referenced_tables
        if t not in valid_tables and f"analytics.{t}" not in valid_tables
    }
    if unknown_tables:
        raise SQLValidationError(
            f"Query references unknown table(s): {', '.join(unknown_tables)}. "
            f"Valid tables are: {', '.join(sorted(valid_tables))}"
        )

    # --- Enforce row limit ---
    existing_limit = parsed.args.get("limit")
    if existing_limit is not None:
        try:
            limit_value = int(existing_limit.expression.this)
            if limit_value > MAX_ROW_LIMIT:
                parsed.set("limit", exp.Limit(expression=exp.Literal.number(MAX_ROW_LIMIT)))
        except (AttributeError, ValueError):
            # Can't parse the existing limit value safely — override it
            parsed.set("limit", exp.Limit(expression=exp.Literal.number(MAX_ROW_LIMIT)))
    else:
        parsed.set("limit", exp.Limit(expression=exp.Literal.number(MAX_ROW_LIMIT)))

    return parsed.sql(dialect="postgres")


if __name__ == "__main__":
    # Quick manual test cases — run directly with: python sql_validator.py
    test_cases = [
        ("SELECT product_id, SUM(price) as revenue FROM analytics.fact_order_items GROUP BY product_id ORDER BY revenue DESC LIMIT 10", True),
        ("SELECT * FROM analytics.fact_order_items; DROP TABLE analytics.fact_order_items;", False),
        ("DELETE FROM analytics.dim_customers", False),
        ("SELECT * FROM raw.customers", False),  # raw schema not in allowlist
        ("SELECT customer_state, COUNT(DISTINCT customer_unique_id) FROM analytics.dim_customers GROUP BY customer_state", True),
        ("SELECT * FROM analytics.fact_order_items LIMIT 999999", True),  # should get clamped to 1000
    ]

    for sql, should_pass in test_cases:
        print(f"\nInput:    {sql}")
        try:
            result = validate_and_prepare(sql)
            status = "PASSED" if should_pass else "UNEXPECTEDLY PASSED (should have failed!)"
            print(f"  [{status}]")
            print(f"  Output:   {result}")
        except SQLValidationError as e:
            status = "REJECTED (expected)" if not should_pass else "UNEXPECTEDLY REJECTED (should have passed!)"
            print(f"  [{status}]")
            print(f"  Reason:   {e}")
