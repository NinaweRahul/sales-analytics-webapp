-- =====================================================================
-- Migration 004: Read-Only Application Role
-- =====================================================================
-- The web app connects as this role. It can SELECT from analytics.*
-- only — no access to raw.* (source data, not meant to be queried by
-- the LLM), and no write access anywhere. This is the real guardrail;
-- everything in the application layer (sqlglot validation etc.) is a
-- second line of defense on top of this.
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'analytics_readonly') THEN
        CREATE ROLE analytics_readonly WITH LOGIN PASSWORD 'CHANGE_ME_BEFORE_DEPLOY';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE olist_analytics TO analytics_readonly;
GRANT USAGE ON SCHEMA analytics TO analytics_readonly;

GRANT SELECT ON analytics.dim_customers      TO analytics_readonly;
GRANT SELECT ON analytics.dim_products       TO analytics_readonly;
GRANT SELECT ON analytics.dim_sellers        TO analytics_readonly;
GRANT SELECT ON analytics.dim_date           TO analytics_readonly;
GRANT SELECT ON analytics.fact_order_items   TO analytics_readonly;
GRANT SELECT ON analytics.fact_payments      TO analytics_readonly;
GRANT SELECT ON analytics.fact_reviews       TO analytics_readonly;

-- Explicitly NOT granted:
--   - USAGE on schema `raw` at all — the role can't even see raw.* exists
--   - Any INSERT/UPDATE/DELETE/TRUNCATE/DROP anywhere

ALTER DEFAULT PRIVILEGES IN SCHEMA analytics
    GRANT SELECT ON TABLES TO analytics_readonly;

-- ---------------------------------------------------------------
-- Verification (connect as analytics_readonly and confirm):
-- ---------------------------------------------------------------
-- Should succeed:
--   SELECT * FROM analytics.fact_order_items LIMIT 5;
--
-- Should fail (permission denied):
--   SELECT * FROM raw.customers LIMIT 5;
--   INSERT INTO analytics.dim_products (product_id) VALUES ('test');
--   DROP TABLE analytics.fact_order_items;
