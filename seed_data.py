"""
Builds retail.db from schema.sql and fills it with deterministic synthetic data.

Deterministic on purpose: the random seed is fixed, so the database is identical
on every machine. Eval results are only meaningful if the data never moves.

Usage:  python seed_data.py
"""

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

SEED = 42
DB_PATH = Path(__file__).with_name("retail.db")
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

START_DATE = date(2025, 1, 1)
END_DATE = date(2026, 6, 30)

N_CUSTOMERS = 300
N_ORDERS = 2000

FIRST_NAMES = [
    "Ayse", "Mehmet", "Elif", "Mustafa", "Zeynep", "Ahmet", "Fatma", "Emre",
    "Merve", "Burak", "Selin", "Can", "Deniz", "Ece", "Kerem", "Irem",
    "Onur", "Sena", "Baris", "Naz", "Kaan", "Derya", "Umut", "Pelin",
]
LAST_NAMES = [
    "Yilmaz", "Kaya", "Demir", "Sahin", "Celik", "Yildiz", "Yildirim",
    "Ozturk", "Aydin", "Ozdemir", "Arslan", "Dogan", "Kilic", "Aslan",
    "Cetin", "Kara", "Koc", "Kurt", "Ozkan", "Simsek",
]
CITIES = [
    ("Istanbul", "Turkiye"), ("Ankara", "Turkiye"), ("Izmir", "Turkiye"),
    ("Bursa", "Turkiye"), ("Antalya", "Turkiye"), ("Berlin", "Germany"),
    ("Munich", "Germany"), ("Amsterdam", "Netherlands"), ("Vienna", "Austria"),
    ("Paris", "France"),
]
SEGMENTS = ["Individual", "SME", "Corporate"]

CATALOG = {
    "Laptops": [
        ("UltraBook 14", 28000), ("UltraBook 16", 36000),
        ("WorkStation Pro", 52000), ("Budget Notebook 15", 14500),
    ],
    "Monitors": [
        ("27in QHD Monitor", 7900), ("24in FHD Monitor", 4200),
        ("34in Ultrawide", 15800), ("32in 4K Monitor", 12400),
    ],
    "Peripherals": [
        ("Mechanical Keyboard", 2300), ("Wireless Mouse", 950),
        ("USB-C Dock", 3100), ("Webcam 1080p", 1450),
        ("Noise Cancelling Headset", 4600),
    ],
    "Storage": [
        ("1TB NVMe SSD", 2800), ("2TB NVMe SSD", 5100),
        ("4TB External HDD", 3400), ("64GB USB Drive", 420),
    ],
    "Networking": [
        ("WiFi 6 Router", 3900), ("8-Port Switch", 2100),
        ("Mesh WiFi 3-Pack", 8700),
    ],
}


def random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def main() -> None:
    rng = random.Random(SEED)

    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    # --- categories & products -------------------------------------------
    products = []  # (product_id, unit_price)
    product_id = 1
    for category_id, (category_name, items) in enumerate(CATALOG.items(), start=1):
        conn.execute(
            "INSERT INTO categories (category_id, category_name) VALUES (?, ?)",
            (category_id, category_name),
        )
        for product_name, price in items:
            cost = round(price * rng.uniform(0.55, 0.78), 2)
            is_active = 0 if rng.random() < 0.08 else 1
            conn.execute(
                """INSERT INTO products
                   (product_id, product_name, category_id, unit_price, unit_cost, is_active)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (product_id, product_name, category_id, float(price), cost, is_active),
            )
            products.append((product_id, float(price)))
            product_id += 1

    # --- customers --------------------------------------------------------
    for customer_id in range(1, N_CUSTOMERS + 1):
        city, country = rng.choice(CITIES)
        conn.execute(
            """INSERT INTO customers
               (customer_id, full_name, city, country, segment, signup_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                customer_id,
                f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                city,
                country,
                rng.choices(SEGMENTS, weights=[0.6, 0.28, 0.12])[0],
                random_date(rng, date(2024, 1, 1), END_DATE).isoformat(),
            ),
        )

    # --- orders & order items --------------------------------------------
    order_item_id = 1
    for order_id in range(1, N_ORDERS + 1):
        customer_id = rng.randint(1, N_CUSTOMERS)
        order_date = random_date(rng, START_DATE, END_DATE)
        status = rng.choices(
            ["completed", "cancelled", "returned"], weights=[0.86, 0.08, 0.06]
        )[0]
        channel = rng.choices(["web", "mobile", "store"], weights=[0.5, 0.33, 0.17])[0]

        conn.execute(
            """INSERT INTO orders (order_id, customer_id, order_date, status, channel)
               VALUES (?, ?, ?, ?, ?)""",
            (order_id, customer_id, order_date.isoformat(), status, channel),
        )

        for product_id, unit_price in rng.sample(products, rng.randint(1, 4)):
            discount = rng.choice([0.0, 0.0, 0.0, 0.05, 0.10, 0.15])
            conn.execute(
                """INSERT INTO order_items
                   (order_item_id, order_id, product_id, quantity, unit_price, discount_rate)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (order_item_id, order_id, product_id, rng.randint(1, 3), unit_price, discount),
            )
            order_item_id += 1

    conn.commit()

    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ["customers", "categories", "products", "orders", "order_items"]
    }
    conn.close()

    print(f"Created {DB_PATH.name}")
    for table, n in counts.items():
        print(f"  {table:<13} {n:>6}")


if __name__ == "__main__":
    main()
