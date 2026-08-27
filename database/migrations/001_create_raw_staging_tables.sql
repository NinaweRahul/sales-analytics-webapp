-- =====================================================================
-- Migration 001: Raw Staging Tables (Olist Brazilian E-Commerce)
-- =====================================================================
-- These tables mirror the 9 Kaggle CSVs column-for-column. No business
-- logic or transformation happens here — that's migration 003.
-- Keeping a raw staging layer separate from the star schema means:
--   1. Re-running the transform doesn't require re-downloading data
--   2. You can always trace a star-schema row back to its raw source
--   3. Loading is a dumb CSV -> table copy, easy to debug in isolation
--
-- Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
-- =====================================================================

DROP SCHEMA IF EXISTS raw CASCADE;
CREATE SCHEMA raw;

-- ---------------------------------------------------------------
-- raw.customers  (olist_customers_dataset.csv)
-- ---------------------------------------------------------------
CREATE TABLE raw.customers (
    customer_id             VARCHAR(64) PRIMARY KEY,
    customer_unique_id      VARCHAR(64) NOT NULL,
    customer_zip_code_prefix VARCHAR(10),
    customer_city           VARCHAR(100),
    customer_state          VARCHAR(2)
);

COMMENT ON TABLE raw.customers IS
    'customer_id is per-order; customer_unique_id is per-person and repeats
     across multiple orders by the same customer. Use customer_unique_id
     for repeat-purchase / customer lifetime analysis.';

-- ---------------------------------------------------------------
-- raw.orders  (olist_orders_dataset.csv)
-- ---------------------------------------------------------------
CREATE TABLE raw.orders (
    order_id                       VARCHAR(64) PRIMARY KEY,
    customer_id                    VARCHAR(64) NOT NULL REFERENCES raw.customers(customer_id),
    order_status                   VARCHAR(20),
    order_purchase_timestamp       TIMESTAMP,
    order_approved_at              TIMESTAMP,
    order_delivered_carrier_date   TIMESTAMP,
    order_delivered_customer_date  TIMESTAMP,
    order_estimated_delivery_date  TIMESTAMP
);

-- ---------------------------------------------------------------
-- raw.sellers  (olist_sellers_dataset.csv)
-- ---------------------------------------------------------------
CREATE TABLE raw.sellers (
    seller_id               VARCHAR(64) PRIMARY KEY,
    seller_zip_code_prefix  VARCHAR(10),
    seller_city             VARCHAR(100),
    seller_state            VARCHAR(2)
);

-- ---------------------------------------------------------------
-- raw.category_translation  (product_category_name_translation.csv)
-- ---------------------------------------------------------------
CREATE TABLE raw.category_translation (
    product_category_name          VARCHAR(100) PRIMARY KEY,
    product_category_name_english  VARCHAR(100)
);

-- ---------------------------------------------------------------
-- raw.products  (olist_products_dataset.csv)
-- ---------------------------------------------------------------
CREATE TABLE raw.products (
    product_id                  VARCHAR(64) PRIMARY KEY,
    product_category_name       VARCHAR(100) REFERENCES raw.category_translation(product_category_name),
    product_name_length         INTEGER,
    product_description_length  INTEGER,
    product_photos_qty          INTEGER,
    product_weight_g            NUMERIC,
    product_length_cm           NUMERIC,
    product_height_cm           NUMERIC,
    product_width_cm            NUMERIC
);

-- ---------------------------------------------------------------
-- raw.order_items  (olist_order_items_dataset.csv)
-- ---------------------------------------------------------------
-- Grain: one row per item within an order (order_id, order_item_id)
CREATE TABLE raw.order_items (
    order_id             VARCHAR(64) NOT NULL REFERENCES raw.orders(order_id),
    order_item_id         INTEGER NOT NULL,
    product_id            VARCHAR(64) NOT NULL REFERENCES raw.products(product_id),
    seller_id              VARCHAR(64) NOT NULL REFERENCES raw.sellers(seller_id),
    shipping_limit_date    TIMESTAMP,
    price                  NUMERIC(10,2) NOT NULL,
    freight_value          NUMERIC(10,2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);

-- ---------------------------------------------------------------
-- raw.order_payments  (olist_order_payments_dataset.csv)
-- ---------------------------------------------------------------
-- Grain: one row per payment installment (an order can have multiple)
CREATE TABLE raw.order_payments (
    order_id              VARCHAR(64) NOT NULL REFERENCES raw.orders(order_id),
    payment_sequential    INTEGER NOT NULL,
    payment_type          VARCHAR(30),
    payment_installments  INTEGER,
    payment_value         NUMERIC(10,2),
    PRIMARY KEY (order_id, payment_sequential)
);

-- ---------------------------------------------------------------
-- raw.order_reviews  (olist_order_reviews_dataset.csv)
-- ---------------------------------------------------------------
CREATE TABLE raw.order_reviews (
    review_id                VARCHAR(64) PRIMARY KEY,
    order_id                 VARCHAR(64) NOT NULL REFERENCES raw.orders(order_id),
    review_score             INTEGER,
    review_comment_title     TEXT,
    review_comment_message   TEXT,
    review_creation_date     TIMESTAMP,
    review_answer_timestamp  TIMESTAMP
);

-- ---------------------------------------------------------------
-- raw.geolocation  (olist_geolocation_dataset.csv)
-- ---------------------------------------------------------------
-- Note: many rows per zip_code_prefix (multiple lat/lng samples).
-- No single-column primary key — dedupe happens in the transform step.
CREATE TABLE raw.geolocation (
    geolocation_zip_code_prefix  VARCHAR(10),
    geolocation_lat              NUMERIC(10,6),
    geolocation_lng              NUMERIC(10,6),
    geolocation_city             VARCHAR(100),
    geolocation_state            VARCHAR(2)
);

CREATE INDEX idx_geolocation_zip ON raw.geolocation(geolocation_zip_code_prefix);
