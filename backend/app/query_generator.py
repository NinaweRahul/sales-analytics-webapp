"""
Natural language -> SQL, using Google Gemini, against the analytics
star schema. Validates every generated query with sql_validator before
returning it, and retries once with error feedback if validation fails.
"""

import json
import os
import time

from google import genai
from google.genai.errors import ServerError

from schema_context import render_schema_for_prompt
from sql_validator import validate_and_prepare, SQLValidationError


FEW_SHOT_EXAMPLES = """
EXAMPLE 1 — simple revenue aggregation:
Q: "What are the top 10 products by revenue?"
A: SELECT product_id, SUM(price) AS total_revenue
   FROM analytics.fact_order_items
   GROUP BY product_id
   ORDER BY total_revenue DESC
   LIMIT 10;

EXAMPLE 2 — repeat customer analysis (uses customer_unique_id, NOT customer_id):
Q: "How many customers have placed more than one order?"
A: SELECT COUNT(*) AS repeat_customer_count
   FROM (
       SELECT customer_unique_id
       FROM analytics.dim_customers
       GROUP BY customer_unique_id
       HAVING COUNT(*) > 1
   ) repeat_customers;

EXAMPLE 3 — JOIN across fact and dimension tables:
Q: "What is the average review score by product category?"
A: SELECT p.category_name_english, AVG(r.review_score) AS avg_review_score
   FROM analytics.fact_reviews r
   JOIN analytics.fact_order_items oi ON r.order_id = oi.order_id
   JOIN analytics.dim_products p ON oi.product_id = p.product_id
   GROUP BY p.category_name_english
   ORDER BY avg_review_score DESC;

EXAMPLE 4 — geographic breakdown using a dimension table:
Q: "Which states generate the most revenue?"
A: SELECT c.customer_state, SUM(oi.price) AS total_revenue
   FROM analytics.fact_order_items oi
   JOIN analytics.dim_customers c ON oi.customer_id = c.customer_id
   GROUP BY c.customer_state
   ORDER BY total_revenue DESC
   LIMIT 10;

EXAMPLE 5 — delivery performance (precomputed column, no timestamp math needed):
Q: "What percentage of orders were delivered late?"
A: SELECT
       ROUND(100.0 * SUM(CASE WHEN delivery_vs_estimate_days > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_late
   FROM analytics.fact_order_items
   WHERE delivery_vs_estimate_days IS NOT NULL;

EXAMPLE 6 — aggregating two fact tables separately before joining (avoids the
row-multiplication trap described in the schema notes):
Q: "Compare total item revenue and total payment value by month."
A: WITH monthly_items AS (
       SELECT d.year, d.month, SUM(oi.price) AS item_revenue
       FROM analytics.fact_order_items oi
       JOIN analytics.dim_date d ON oi.order_purchase_date_id = d.date_id
       GROUP BY d.year, d.month
   ),
   monthly_payments AS (
       SELECT o.order_purchase_date_id, SUM(p.payment_value) AS payment_total
       FROM analytics.fact_payments p
       JOIN (SELECT DISTINCT order_id, order_purchase_date_id FROM analytics.fact_order_items) o
           ON p.order_id = o.order_id
       GROUP BY o.order_purchase_date_id
   )
   SELECT mi.year, mi.month, mi.item_revenue
   FROM monthly_items mi
   ORDER BY mi.year, mi.month;
"""

SYSTEM_PROMPT_TEMPLATE = """You are a PostgreSQL expert generating SQL queries against a star schema analytics database.

{schema}

{examples}

RULES:
- Only generate SELECT statements. Never INSERT, UPDATE, DELETE, DROP, or ALTER.
- Always fully qualify table names with the "analytics." schema prefix (e.g. analytics.fact_order_items).
- For "top N" or "best/worst" questions, always GROUP BY and aggregate with SUM/AVG/COUNT — never return raw unaggregated rows.
- For customer-count or repeat-purchase questions, use customer_unique_id, not customer_id (see dim_customers notes above).
- Use category_name_english for product category questions, not the Portuguese category_name.
- If joining fact_order_items with fact_payments or fact_reviews, aggregate each separately first (see Example 6) — do not join them directly and then SUM(price), as this multiplies rows and inflates revenue.
- Always include a reasonable LIMIT for "top N" style questions.

Respond with ONLY valid JSON in this exact format, no markdown formatting, no code fences:
{{"sql": "...", "explanation": "..."}}
"""


class QueryGenerationError(Exception):
    """Raised when SQL generation fails after all retries."""
    pass


class QueryGenerator:
    def __init__(self, api_key: str | None = None, model_id: str | None = None, min_delay: float | None = None):
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set (pass explicitly or set in environment).")

        self.client = genai.Client(api_key=api_key)
        # Use an alias ("-latest") rather than a dated model name where possible —
        # dated names get deprecated periodically (this happened once already
        # during this project's earlier CLI version). Overridable via .env so a
        # future deprecation is a one-line config change, not a code edit.
        self.model_id = model_id or os.getenv("GEMINI_MODEL", "gemini-flash-latest")

        # Free tier quota is per-model and can be quite restrictive for newer
        # models -- observed 5 requests/minute for gemini-3.6-flash (vs. 15/min
        # for the older gemini-1.5-flash this project originally used). 13s
        # gives a small buffer under the 12s/request implied by 5-per-minute.
        # Override via GEMINI_MIN_DELAY_SECONDS in .env if your model/tier differs.
        self.min_delay = min_delay if min_delay is not None else float(
            os.getenv("GEMINI_MIN_DELAY_SECONDS", "13")
        )
        self._last_request_time = 0.0

        self._system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            schema=render_schema_for_prompt(),
            examples=FEW_SHOT_EXAMPLES,
        )

    def _wait_for_rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self._last_request_time = time.time()

    def _call_llm(self, question: str, error_context: str | None = None) -> dict:
        prompt = self._system_prompt + f"\n\nUser question: {question}\n"
        if error_context:
            prompt += (
                f"\nThe previous attempt failed validation with this error:\n{error_context}\n"
                f"Generate a corrected query.\n"
            )

        self._wait_for_rate_limit()

        # Retry on transient server-side overload (503). This is a real,
        # documented Gemini behavior around newly-released models and demand
        # spikes -- not something our code causes, but a well-behaved client
        # should retry transient failures rather than surface them immediately.
        max_retries = 3
        backoff_seconds = 2

        for retry in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                )
                break
            except ServerError as e:
                if "UNAVAILABLE" in str(e) or "503" in str(e):
                    if retry < max_retries - 1:
                        wait = backoff_seconds * (2 ** retry)
                        time.sleep(wait)
                        continue
                raise

        raw_text = response.text.strip()
        # Strip markdown code fences if the model added them despite instructions
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`")
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise QueryGenerationError(f"Model did not return valid JSON: {e}\nRaw response: {raw_text[:300]}")

    def generate_sql(self, question: str, max_attempts: int = 2) -> dict:
        """
        Generate and validate SQL for a natural language question.

        Returns: {"sql": <validated, safe-to-execute SQL>, "explanation": <str>, "attempts": <int>}
        Raises: QueryGenerationError if all attempts fail validation.
        """
        last_error = None

        for attempt in range(1, max_attempts + 1):
            result = self._call_llm(question, error_context=last_error)

            if "sql" not in result:
                last_error = "Response JSON missing 'sql' key."
                continue

            try:
                safe_sql = validate_and_prepare(result["sql"])
                return {
                    "sql": safe_sql,
                    "explanation": result.get("explanation", ""),
                    "attempts": attempt,
                }
            except SQLValidationError as e:
                last_error = str(e)

        raise QueryGenerationError(
            f"Failed to generate valid SQL after {max_attempts} attempts. Last error: {last_error}"
        )