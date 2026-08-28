-- =====================================================================
-- Migration 005: Read-Only Role Grants (Neon / Production)
-- =====================================================================
-- The analytics_readonly role was already created separately (via a
-- one-off command with the password typed directly in terminal, never
-- saved to this file). This file only grants permissions to it.
-- =====================================================================

GRANT CONNECT ON DATABASE neondb TO analytics_readonly;
GRANT USAGE ON SCHEMA analytics TO analytics_readonly;

GRANT SELECT ON analytics.dim_customers      TO analytics_readonly;
GRANT SELECT ON analytics.dim_products       TO analytics_readonly;
GRANT SELECT ON analytics.dim_sellers        TO analytics_readonly;
GRANT SELECT ON analytics.dim_date           TO analytics_readonly;
GRANT SELECT ON analytics.fact_order_items   TO analytics_readonly;
GRANT SELECT ON analytics.fact_payments      TO analytics_readonly;
GRANT SELECT ON analytics.fact_reviews       TO analytics_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA analytics
    GRANT SELECT ON TABLES TO analytics_readonly;