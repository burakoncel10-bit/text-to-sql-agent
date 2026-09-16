-- Retail analytics schema
-- Designed for text-to-SQL experimentation: small enough to fit in a prompt,
-- rich enough to require multi-table joins, aggregation and date filtering.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    full_name     TEXT    NOT NULL,
    city          TEXT    NOT NULL,
    country       TEXT    NOT NULL,
    segment       TEXT    NOT NULL CHECK (segment IN ('Individual', 'SME', 'Corporate')),
    signup_date   DATE    NOT NULL
);

CREATE TABLE categories (
    category_id   INTEGER PRIMARY KEY,
    category_name TEXT    NOT NULL UNIQUE
);

CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY,
    product_name  TEXT    NOT NULL,
    category_id   INTEGER NOT NULL REFERENCES categories(category_id),
    unit_price    REAL    NOT NULL CHECK (unit_price > 0),
    unit_cost     REAL    NOT NULL CHECK (unit_cost > 0),
    is_active     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE orders (
    order_id      INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date    DATE    NOT NULL,
    status        TEXT    NOT NULL CHECK (status IN ('completed', 'cancelled', 'returned')),
    channel       TEXT    NOT NULL CHECK (channel IN ('web', 'mobile', 'store'))
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id),
    product_id    INTEGER NOT NULL REFERENCES products(product_id),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    unit_price    REAL    NOT NULL,
    discount_rate REAL    NOT NULL DEFAULT 0 CHECK (discount_rate >= 0 AND discount_rate < 1)
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_date     ON orders(order_date);
CREATE INDEX idx_items_order     ON order_items(order_id);
CREATE INDEX idx_items_product   ON order_items(product_id);
CREATE INDEX idx_products_cat    ON products(category_id);
