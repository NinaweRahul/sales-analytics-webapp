# Sales Analytics — Text-to-SQL over Real E-Commerce Data

**Live demo:** [sales-analytics-webapp.vercel.app](https://sales-analytics-webapp.vercel.app)
**API:** [sales-analytics-webapp.onrender.com/docs](https://sales-analytics-webapp.onrender.com/docs)

Ask a business question in plain English. Get back the exact SQL that answered it, the raw data, and a chart — running against a real, 100K-order e-commerce dataset, not a toy table.

---

## Why I built this

This started as a follow-up to an earlier CLI project where I automated SQL generation and reporting with the Gemini API. That project proved the core idea worked, but it only ran locally from a terminal — nobody could actually try it. I wanted to see the same idea through as a real, deployed product: a proper frontend, a database schema that reflects how real analytics warehouses are modeled (not a flattened CSV), and the guardrails a system like this actually needs before you'd trust it with real traffic.

I also wanted to be honest about what "AI writes SQL for you" actually requires underneath: prompt engineering alone isn't enough — you need schema validation, a read-only database role that can't be argued with, rate limiting, and a plan for what happens when the model itself is unavailable. Building all of that, and having it break in realistic ways along the way, is most of what this README documents.

---

## What it does

- Type a question like *"Which states generate the most revenue?"* or *"How many customers have placed more than one order?"*
- Gemini converts it to SQL, using a full description of the real schema (tables, columns, relationships, and the specific gotchas in this dataset)
- The generated SQL is structurally validated before it ever touches the database
- The query runs against a read-only database connection and the results come back as an explanation, the raw SQL, a data table, and a chart
- A separate tab lets you explore the actual database schema as a live diagram, generated from the real table structure — not a static drawing

---

## Architecture

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│   React (Vercel)     │────▶│  FastAPI (Render)     │────▶│  PostgreSQL (Neon)  │
│   Landing / Ask /     │◀────│  /ask /schema /health │◀────│  analytics_readonly │
│   Schema Explorer     │     │                       │     │  (read-only role)   │
└─────────────────────┘     └──────────┬────────────┘     └─────────────────────┘
                                        │
                                        ▼
                              ┌──────────────────┐
                              │  Google Gemini    │
                              │  (SQL generation) │
                              └──────────────────┘
```

- **Frontend:** React + Vite, deployed on Vercel
- **Backend:** FastAPI, deployed on Render
- **Database:** PostgreSQL on Neon — the app connects through a dedicated read-only role, never the admin credentials
- **LLM:** Google Gemini, model configurable via environment variable (see [Why the model is configurable](#why-the-model-is-configurable) below)

---

## The database: a real star schema, not a flat file

The dataset is the [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) — ~100K real, anonymized orders from 2016–2018. I deliberately chose this over a simpler flat CSV because it has genuine transactional structure: individual order line items, multiple payment installments per order, and — critically — a real distinction between a per-order customer ID and a per-person customer ID, which makes repeat-purchase analysis genuinely possible instead of just plausible-looking.

### Schema

```
                    ┌──────────────────┐
                    │  dim_customers    │
                    │  customer_id       │◀──┐
                    │  customer_unique_id │   │
                    └──────────────────┘    │
                                             │
┌────────────────┐   ┌─────────────────────┐│   ┌────────────────┐
│  dim_products    │◀──┤  fact_order_items    ├┘   │  dim_sellers     │
│  product_id       │   │  (line-item grain)    ├──▶│  seller_id       │
└────────────────┘   └──────────┬──────────┘   └────────────────┘
                                 │
                       ┌──────────▼──────────┐
                       │      dim_date         │
                       └─────────────────────┘

     fact_payments (order grain, N installments per order)
     fact_reviews  (order grain, 0–1 review per order)
```

**Why three fact tables, not one:** order items, payments, and reviews are at genuinely different grains — an order can have multiple line items *and* multiple payment installments *and* at most one review. Merging them into a single fact table and joining across grains would silently duplicate rows and inflate revenue on any query that touched more than one — a classic star-schema mistake I deliberately designed around rather than discovered the hard way.

**The `customer_id` vs `customer_unique_id` distinction:** Olist assigns a new `customer_id` to every order, but `customer_unique_id` is stable per real person. A query that counts `DISTINCT customer_id` is counting order-slots, not people. This is the single most important thing the LLM's prompt has to get right, and it's explicitly called out in the schema context the model is given, with a worked example.

**Two real data-quality issues I found and fixed** while migrating the raw CSVs into this schema — not hypothetical edge cases, actual bugs the real data triggered:
1. Two product categories in the raw `products` CSV don't exist in Olist's own category-translation file (`pc_gamer` and a Portuguese kitchen-appliance category). My original migration had a foreign key enforcing that relationship, which meant the load failed. Fixed by removing the constraint from the raw staging layer (which shouldn't enforce business rules the source data doesn't itself guarantee) and letting the transform step fall back gracefully.
2. `review_id` is **not unique** in the source data — 814 values are reused across different orders. The primary key had to be the composite `(review_id, order_id)`, not `review_id` alone.

Both were caught by writing an actual verification script (`database/scripts/verify_migration.py`) that checks row counts, aggregate sums, and the read-only role's guardrails against real data — not by assuming the migration worked because it ran without errors.

---

## Guardrails

A system that lets an LLM generate SQL against a real database needs more than "the prompt says be careful." Three independent layers, each of which would stop a bad query even if the others failed:

1. **Database-level read-only role.** The app connects as `analytics_readonly`, a Postgres role with `SELECT` granted on the `analytics` schema only — no `INSERT`/`UPDATE`/`DELETE`/`DROP` anywhere, and no visibility into the raw staging schema at all. This is enforced by Postgres itself, not by application code, so no amount of clever prompting can talk around it.
2. **Structural SQL validation.** Before any generated query runs, it's parsed with `sqlglot` (a real SQL parser, not a regex/keyword blocklist) to confirm it's a single `SELECT` statement against known tables, with a hard row limit enforced regardless of what the model wrote.
3. **Per-visitor rate limiting.** 10 questions per 5 minutes per IP address, tracked server-side, so one visitor can't exhaust the shared Gemini quota for everyone else.

---

## Why the model is configurable

`GEMINI_MODEL` is read from an environment variable rather than hardcoded, and this isn't a minor convenience — it's a direct response to something that happened during development. The model I originally built against (`gemini-1.5-flash`) was deprecated mid-project. Then the replacement I tried next (`gemini-2.5-flash`) was *also* no longer available to new users by the time I got to it. I ended up discovering the currently-working model (`gemini-3.6-flash`) by calling Gemini's own `ListModels` endpoint live, rather than trusting any documentation or prior knowledge. Given how fast this API's model lineup moves, hardcoding a model name anywhere in this codebase would just be scheduling a future outage.

---

## Real bugs found during this build (with evidence, not just fixes)

I'm including this section deliberately. A polished README that only shows the final working state doesn't demonstrate debugging skill — the actual process of finding and fixing these is a better signal of how I work than pretending it went smoothly.

- **A stale font import survived multiple rounds of styling changes.** The CSS correctly referenced Fraunces/Outfit (my portfolio's fonts) everywhere, but the deployed `index.html` was still requesting an old, unrelated font pairing from an earlier design direction. The CSS was unambiguously correct, which is exactly why this was hard to spot — I confirmed it by opening the browser's Network tab, filtering for font requests, and reading the actual request URL, which is the only way to know for certain what's really loading versus what the code claims should load.
- **A duplicated sidebar block** turned out to be a component file that had never actually been updated on disk, despite being fixed multiple times in conversation — found by inspecting the live DOM tree directly (right-click → Inspect) rather than continuing to guess from screenshots.
- **Render's free tier cold-starts** meant the first request after idle time could take 30–60 seconds. Fixed with a background health-check ping on page load, plus a visible status indicator so the wait isn't silent.
- **Gemini's free-tier quota turned out to be far stricter for newer models** (5 requests/minute for `gemini-3.6-flash`) than the older model this project originally used (15/minute). The rate-limiting logic is tuned to the model actually in use, with a configurable override, rather than a number I picked once and left alone.

---

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React, Vite, React Flow (schema diagram) |
| Backend | FastAPI, SQLAlchemy, `sqlglot` |
| Database | PostgreSQL (Neon), star schema |
| AI | Google Gemini API |
| Hosting | Vercel (frontend), Render (backend), Neon (database) |

---

## Running it locally

```bash
# Backend
cd backend
pip install -r requirements.txt
# create .env with DATABASE_URL, READONLY_DATABASE_URL, GEMINI_API_KEY, GEMINI_MODEL
cd app
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Database setup (schema creation, Olist data loading, read-only role) is documented in `database/README.md`.

---

## What I'd add next

- An audit log of every question asked (question, generated SQL, timestamp) — partly for abuse monitoring, partly because it's genuinely useful demo material ("here's what people actually asked")
- A second Gemini call to produce a real business-insight summary, not just a technical explanation of the SQL — the current "Explanation" tab describes *why the query was written that way*, not *what it means for the business*, and I've kept that distinction honest rather than overclaiming what's there
- Caching identical questions server-side to reduce both latency and Gemini API cost for repeated demo questions

---

## Author

Rahul Ninawe — [portfolio](https://ninawerahul.github.io) · [LinkedIn](https://www.linkedin.com/in/rahulninawe/) · [GitHub](https://github.com/NinaweRahul)
