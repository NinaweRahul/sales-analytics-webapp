# Database: Olist Star Schema

Source data: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(~100K real, anonymized orders, 2016–2018, CC BY-NC-SA license — free for
portfolio/research use).

## Why this dataset

The project originally used a flat, pre-aggregated table with no
individual customer identity (see project history). This star schema
uses Olist instead because it has genuine transaction-level rows and
a real per-person customer key (`customer_unique_id`), which makes
repeat-purchase and customer-lifetime questions actually answerable —
not just plausible-looking.

## Setup

### 1. Download the data (manual step — not automatable)

Get all 9 CSVs from Kaggle (requires a free account) and place them,
unmodified, in `database/data/raw/`:

```
database/data/raw/
├── olist_customers_dataset.csv
├── olist_orders_dataset.csv
├── olist_order_items_dataset.csv
├── olist_order_payments_dataset.csv
├── olist_order_reviews_dataset.csv
├── olist_products_dataset.csv
├── olist_sellers_dataset.csv
├── olist_geolocation_dataset.csv
└── product_category_name_translation.csv
```

### 2. Configure environment

```bash
cd database
pip install sqlalchemy psycopg2-binary python-dotenv pandas
```

`.env`:
```
DATABASE_URL=postgresql://postgres:password@localhost:5432/olist_analytics
READONLY_DATABASE_URL=postgresql://analytics_readonly:PASSWORD@localhost:5432/olist_analytics
```

Create the database first: `createdb olist_analytics`

### 3. Run the pipeline

```bash
python scripts/run_migrations.py
```

This runs, in order:
1. `001_create_raw_staging_tables.sql` — creates the `raw` schema (9 tables matching the CSVs exactly)
2. `load_raw_csvs.py` — loads all 9 CSVs into `raw.*`
3. `002_create_star_schema.sql` — creates the `analytics` schema (star schema)
4. `003_transform_to_star_schema.sql` — transforms `raw.*` → `analytics.*`
5. `004_create_readonly_role.sql` — creates `analytics_readonly` (SELECT-only, `analytics` schema only)

### 4. Verify

```bash
python scripts/verify_migration.py
```

## Schema

Two Postgres schemas: `raw` (staging, mirrors the CSVs) and `analytics`
(the star schema — this is what the app queries).

```
                    ┌─────────────────┐
                    │  dim_customers   │
                    │  customer_id     │◄──┐
                    │  customer_unique_id│  │
                    └─────────────────┘   │
                                            │
┌──────────────┐    ┌──────────────────┐   │    ┌──────────────┐
│  dim_products │◄───┤ fact_order_items ├───┘    │ dim_sellers   │
│  product_id   │    │ (line-item grain) ├───────►│ seller_id     │
└──────────────┘    └────────┬─────────┘         └──────────────┘
                              │
                     ┌────────▼────────┐
                     │    dim_date      │
                     └─────────────────┘

     fact_payments (order grain, N installments per order)
     fact_reviews  (order grain, 0-1 review per order)
```

**Why three fact tables, not one:** order items, payments, and reviews
are at different grains (an order can have multiple line items *and*
multiple payment installments *and* at most one review). Merging them
into a single fact table would duplicate rows on any join and inflate
sums — a standard star-schema mistake worth avoiding deliberately.

| Table | Grain | Row count (approx) |
|---|---|---|
| `analytics.fact_order_items` | one line item | ~112K |
| `analytics.fact_payments` | one payment installment | ~104K |
| `analytics.fact_reviews` | one review | ~99K |
| `analytics.dim_customers` | one per order (`customer_id`) | ~99K |
| `analytics.dim_products` | one per SKU | ~33K |
| `analytics.dim_sellers` | one per seller | ~3K |
| `analytics.dim_date` | one per calendar date with an order | ~700 |

## Key design decisions

- **`customer_id` vs `customer_unique_id`** — Olist assigns a new
  `customer_id` per *order*, but `customer_unique_id` is stable per
  *person*. Any repeat-purchase or customer-lifetime-value query must
  group by `customer_unique_id`, not `customer_id`. `verify_migration.py`
  explicitly checks that `COUNT(DISTINCT customer_unique_id) <
  COUNT(DISTINCT customer_id)` to confirm repeat customers are actually
  present and preserved.
- **Category names pre-translated** — `dim_products.category_name_english`
  is joined in at transform time so the SQL-generation LLM never has to
  reason about Portuguese category strings.
- **Delivery performance precomputed** — `fact_order_items` includes
  `days_to_delivery` and `delivery_vs_estimate_days` so "was delivery
  late" questions don't require the LLM to write timestamp arithmetic.
- **`raw` schema is intentionally invisible to the app** — the
  `analytics_readonly` role has no `USAGE` grant on `raw` at all, not
  just no write access. The LLM should only ever see and query the
  clean star schema.

## Security

The app connects as `analytics_readonly`, which:
- Can `SELECT` from `analytics.*` only
- Cannot see `raw.*` exists (no schema-level `USAGE` grant)
- Cannot `INSERT`/`UPDATE`/`DELETE`/`DROP` anywhere

**Change the password** in `004_create_readonly_role.sql` before
deploying anywhere beyond local dev.

## Re-running

`003_transform_to_star_schema.sql` is **not** safe to re-run as-is —
`fact_order_items`/`fact_payments`/`fact_reviews` have no dedup logic
and will duplicate rows on a second run. If you need to re-run the
transform, `TRUNCATE` the `analytics.*` tables first (or drop and
recreate via `002` + `003`).
