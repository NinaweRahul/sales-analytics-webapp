-- =====================================================================
-- Migration 002: Star Schema (built from raw.* staging tables)
-- =====================================================================
-- Design decisions worth knowing:
--
-- 1. THREE fact tables, not one. Order items, payments, and reviews
--    are at genuinely different grains (one order can have multiple
--    line items, multiple payment installments, and at most one
--    review). Forcing them into a single fact table would mean
--    duplicating rows and double-counting revenue on any query that
--    joins reviews or payments — a classic star-schema mistake.
--
-- 2. dim_customers keeps BOTH customer_id (per-order) and
--    customer_unique_id (per-person). This is the field that makes
--    repeat-purchase / customer lifetime analysis possible — Olist
--    assigns a new customer_id to every order, so naive queries on
--    customer_id alone will never find a repeat customer.
--
-- 3. dim_products joins in the English category name at build time,
--    so downstream SQL generation never has to reason about
--    untranslated Portuguese category strings.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS analytics;

-- ---------------------------------------------------------------
-- analytics.dim_customers
-- ---------------------------------------------------------------
CREATE TABLE analytics.dim_customers (
    customer_id         VARCHAR(64) PRIMARY KEY,
    customer_unique_id  VARCHAR(64) NOT NULL,
    customer_city        VARCHAR(100),
    customer_state       VARCHAR(2)
);

CREATE INDEX idx_dim_customers_unique_id ON analytics.dim_customers(customer_unique_id);
CREATE INDEX idx_dim_customers_state ON analytics.dim_customers(customer_state);

COMMENT ON COLUMN analytics.dim_customers.customer_unique_id IS
    'Stable per-person identifier. Group by this column (not customer_id)
     to compute repeat purchase rate / customer lifetime value.';

-- ---------------------------------------------------------------
-- analytics.dim_products
-- ---------------------------------------------------------------
CREATE TABLE analytics.dim_products (
    product_id          VARCHAR(64) PRIMARY KEY,
    category_name        VARCHAR(100),
    category_name_english VARCHAR(100),
    weight_g              NUMERIC,
    length_cm             NUMERIC,
    height_cm             NUMERIC,
    width_cm               NUMERIC
);

CREATE INDEX idx_dim_products_category ON analytics.dim_products(category_name_english);

-- ---------------------------------------------------------------
-- analytics.dim_sellers
-- ---------------------------------------------------------------
CREATE TABLE analytics.dim_sellers (
    seller_id      VARCHAR(64) PRIMARY KEY,
    seller_city     VARCHAR(100),
    seller_state    VARCHAR(2)
);

CREATE INDEX idx_dim_sellers_state ON analytics.dim_sellers(seller_state);

-- ---------------------------------------------------------------
-- analytics.dim_date
-- ---------------------------------------------------------------
CREATE TABLE analytics.dim_date (
    date_id        SERIAL PRIMARY KEY,
    full_date       DATE NOT NULL UNIQUE,
    day             INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    month_name      VARCHAR(20) NOT NULL,
    quarter         INTEGER NOT NULL,
    year            INTEGER NOT NULL
);

CREATE INDEX idx_dim_date_year ON analytics.dim_date(year);

-- ---------------------------------------------------------------
-- analytics.fact_order_items
-- ---------------------------------------------------------------
-- Grain: one row per line item. This is the primary fact table for
-- revenue, product, and delivery-performance questions.
CREATE TABLE analytics.fact_order_items (
    fact_id                     SERIAL PRIMARY KEY,
    order_id                    VARCHAR(64) NOT NULL,
    order_item_id                INTEGER NOT NULL,
    customer_id                  VARCHAR(64) NOT NULL REFERENCES analytics.dim_customers(customer_id),
    product_id                   VARCHAR(64) NOT NULL REFERENCES analytics.dim_products(product_id),
    seller_id                     VARCHAR(64) NOT NULL REFERENCES analytics.dim_sellers(seller_id),
    order_purchase_date_id        INTEGER REFERENCES analytics.dim_date(date_id),

    order_status                  VARCHAR(20),
    price                          NUMERIC(10,2) NOT NULL,
    freight_value                  NUMERIC(10,2) NOT NULL,

    -- Delivery performance (nullable — not every order reaches these states)
    days_to_delivery                NUMERIC,       -- purchase -> delivered_customer
    delivery_vs_estimate_days       NUMERIC,       -- negative = early, positive = late

    UNIQUE (order_id, order_item_id)
);

CREATE INDEX idx_fact_order_items_customer ON analytics.fact_order_items(customer_id);
CREATE INDEX idx_fact_order_items_product ON analytics.fact_order_items(product_id);
CREATE INDEX idx_fact_order_items_seller ON analytics.fact_order_items(seller_id);
CREATE INDEX idx_fact_order_items_date ON analytics.fact_order_items(order_purchase_date_id);

-- ---------------------------------------------------------------
-- analytics.fact_payments
-- ---------------------------------------------------------------
-- Grain: one row per payment installment. Kept separate from
-- fact_order_items because summing price there and joining payments
-- naively would multiply rows (one order -> many items x many
-- installments) and inflate both revenue and payment totals.
CREATE TABLE analytics.fact_payments (
    payment_fact_id       SERIAL PRIMARY KEY,
    order_id               VARCHAR(64) NOT NULL,
    payment_sequential      INTEGER NOT NULL,
    payment_type             VARCHAR(30),
    payment_installments     INTEGER,
    payment_value             NUMERIC(10,2),

    UNIQUE (order_id, payment_sequential)
);

CREATE INDEX idx_fact_payments_order ON analytics.fact_payments(order_id);

-- ---------------------------------------------------------------
-- analytics.fact_reviews
-- ---------------------------------------------------------------
-- Grain: one row per review (effectively one per order).
CREATE TABLE analytics.fact_reviews (
    review_id          VARCHAR(64) PRIMARY KEY,
    order_id            VARCHAR(64) NOT NULL,
    review_score          INTEGER,
    review_creation_date  TIMESTAMP
);

CREATE INDEX idx_fact_reviews_order ON analytics.fact_reviews(order_id);
CREATE INDEX idx_fact_reviews_score ON analytics.fact_reviews(review_score);
