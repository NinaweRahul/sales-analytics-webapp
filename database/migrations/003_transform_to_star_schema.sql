-- =====================================================================
-- Migration 003: Transform raw.* into analytics.* (star schema)
-- =====================================================================
-- Run after 001 (raw tables created + loaded) and 002 (star schema
-- created). Wrapped in a transaction: all-or-nothing.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------
-- dim_customers
-- ---------------------------------------------------------------
INSERT INTO analytics.dim_customers (customer_id, customer_unique_id, customer_city, customer_state)
SELECT customer_id, customer_unique_id, customer_city, customer_state
FROM raw.customers;

-- ---------------------------------------------------------------
-- dim_products (joined with English category translation)
-- ---------------------------------------------------------------
INSERT INTO analytics.dim_products (
    product_id, category_name, category_name_english,
    weight_g, length_cm, height_cm, width_cm
)
SELECT
    p.product_id,
    p.product_category_name,
    COALESCE(ct.product_category_name_english, p.product_category_name, 'unknown'),
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm
FROM raw.products p
LEFT JOIN raw.category_translation ct
    ON p.product_category_name = ct.product_category_name;

-- ---------------------------------------------------------------
-- dim_sellers
-- ---------------------------------------------------------------
INSERT INTO analytics.dim_sellers (seller_id, seller_city, seller_state)
SELECT seller_id, seller_city, seller_state
FROM raw.sellers;

-- ---------------------------------------------------------------
-- dim_date (derived from order_purchase_timestamp across all orders)
-- ---------------------------------------------------------------
INSERT INTO analytics.dim_date (full_date, day, month, month_name, quarter, year)
SELECT DISTINCT
    order_purchase_timestamp::DATE AS full_date,
    EXTRACT(DAY FROM order_purchase_timestamp)::INTEGER,
    EXTRACT(MONTH FROM order_purchase_timestamp)::INTEGER,
    TO_CHAR(order_purchase_timestamp, 'Month'),
    EXTRACT(QUARTER FROM order_purchase_timestamp)::INTEGER,
    EXTRACT(YEAR FROM order_purchase_timestamp)::INTEGER
FROM raw.orders
WHERE order_purchase_timestamp IS NOT NULL
ON CONFLICT (full_date) DO NOTHING;

-- ---------------------------------------------------------------
-- fact_order_items
-- ---------------------------------------------------------------
INSERT INTO analytics.fact_order_items (
    order_id, order_item_id, customer_id, product_id, seller_id,
    order_purchase_date_id, order_status, price, freight_value,
    days_to_delivery, delivery_vs_estimate_days
)
SELECT
    oi.order_id,
    oi.order_item_id,
    o.customer_id,
    oi.product_id,
    oi.seller_id,
    dd.date_id,
    o.order_status,
    oi.price,
    oi.freight_value,
    EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400.0,
    EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_estimated_delivery_date)) / 86400.0
FROM raw.order_items oi
JOIN raw.orders o
    ON oi.order_id = o.order_id
LEFT JOIN analytics.dim_date dd
    ON o.order_purchase_timestamp::DATE = dd.full_date;

-- ---------------------------------------------------------------
-- fact_payments
-- ---------------------------------------------------------------
INSERT INTO analytics.fact_payments (
    order_id, payment_sequential, payment_type, payment_installments, payment_value
)
SELECT order_id, payment_sequential, payment_type, payment_installments, payment_value
FROM raw.order_payments;

-- ---------------------------------------------------------------
-- fact_reviews
-- ---------------------------------------------------------------
INSERT INTO analytics.fact_reviews (review_id, order_id, review_score, review_creation_date)
SELECT DISTINCT review_id, order_id, review_score, review_creation_date
FROM raw.order_reviews;

COMMIT;

-- ---------------------------------------------------------------
-- Verification queries (run manually, or via verify_migration.py)
-- ---------------------------------------------------------------
-- SELECT COUNT(*) FROM raw.order_items;              -- should match:
-- SELECT COUNT(*) FROM analytics.fact_order_items;
--
-- SELECT ROUND(SUM(price)::numeric, 2) FROM raw.order_items;  -- should match:
-- SELECT ROUND(SUM(price)::numeric, 2) FROM analytics.fact_order_items;
--
-- SELECT COUNT(*) FROM raw.order_payments;            -- should match:
-- SELECT COUNT(*) FROM analytics.fact_payments;
--
-- SELECT COUNT(DISTINCT customer_unique_id) FROM analytics.dim_customers;
-- -- this is your TRUE unique customer count, smaller than COUNT(customer_id)
