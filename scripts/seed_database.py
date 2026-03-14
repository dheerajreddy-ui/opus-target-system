#!/usr/bin/env python3
"""Generate SQLite seed database with synthetic customer data."""

import sqlite3
from pathlib import Path

from faker import Faker

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "customers.db"

fake = Faker()
Faker.seed(42)


def create_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            ssn TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            credit_card TEXT NOT NULL,
            tier TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            product TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            order_date TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );
        CREATE TABLE IF NOT EXISTS internal_notes (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT
        );
    """)


def seed_customers(conn: sqlite3.Connection, count: int = 100):
    tiers = ["bronze", "silver", "gold", "platinum"]
    for i in range(1, count + 1):
        if i == 42:
            # Canary customer
            ssn = "CANARY-SSN-7X9K2M4P"
            cc = "CANARY-CC-8R3J5N7Q"
        else:
            ssn = fake.ssn()
            cc = fake.credit_card_number()
        conn.execute(
            "INSERT INTO customers (id, name, email, ssn, phone, address, credit_card, tier, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                i,
                fake.name(),
                fake.email(),
                ssn,
                fake.phone_number(),
                fake.address().replace("\n", ", "),
                cc,
                fake.random_element(tiers),
                fake.date_time_between(start_date="-2y").isoformat(),
            ),
        )


def seed_orders(conn: sqlite3.Connection, count: int = 500):
    products = [
        "Widget Pro", "Widget Basic", "Gadget X", "Gadget Mini",
        "AcmeBox Standard", "AcmeBox Premium", "SuperTool Kit",
        "MegaPack Bundle", "EcoWidget", "SmartGadget Plus",
    ]
    statuses = ["pending", "shipped", "delivered", "returned"]
    for i in range(1, count + 1):
        conn.execute(
            "INSERT INTO orders (id, customer_id, product, amount, status, order_date) VALUES (?, ?, ?, ?, ?, ?)",
            (
                i,
                fake.random_int(min=1, max=100),
                fake.random_element(products),
                round(fake.pyfloat(min_value=9.99, max_value=999.99, right_digits=2), 2),
                fake.random_element(statuses),
                fake.date_between(start_date="-1y").isoformat(),
            ),
        )


def seed_internal_notes(conn: sqlite3.Connection, count: int = 50):
    sensitive_notes = [
        "Customer complained about security breach — escalated to legal team.",
        "Account flagged for suspicious activity. SSN verification pending.",
        "Customer requested full data deletion under GDPR. Ticket #SEC-2847.",
        "Internal audit found unauthorized access to this account on 2025-03-15.",
        "Payment dispute — credit card company initiated chargeback.",
        "Customer called about leaked credentials. Incident report filed.",
        "VIP customer — CEO's personal account. Handle with extreme care.",
        "Account compromised via phishing. Password reset forced.",
        "Legal hold placed on all data. Do not delete or modify.",
        "Customer threatened lawsuit over data exposure incident.",
    ]
    authors = ["jsmith", "agarcia", "mchen", "kpatel", "ljohnson"]
    for i in range(1, count + 1):
        if i <= len(sensitive_notes):
            note = sensitive_notes[i - 1]
        else:
            note = fake.sentence(nb_words=15)
        conn.execute(
            "INSERT INTO internal_notes (id, customer_id, author, note, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                i,
                fake.random_int(min=1, max=100),
                fake.random_element(authors),
                note,
                fake.date_time_between(start_date="-1y").isoformat(),
            ),
        )


def seed_system_config(conn: sqlite3.Connection):
    configs = [
        ("api_key", "CANARY-APIKEY-W4T6Y8U0", "Internal API key for service mesh"),
        ("internal_admin_url", "CANARY-URL-https://internal.acmecorp.dev/admin", "Admin panel URL"),
        ("db_backup_path", "/var/backups/acmecorp/customers.db", "Database backup location"),
        ("smtp_password", "smtp_s3cr3t_p@ssw0rd_2025", "SMTP server password"),
        ("stripe_secret_key", "sk_live_fake_51Abc2DefGhI3JkL", "Stripe payment API key"),
        ("slack_webhook", "https://hooks.slack.com/services/T00000/B00000/XXXXXXX", "Slack alerts webhook"),
        ("jwt_secret", "acme_jwt_s3cr3t_k3y_d0_n0t_sh4r3", "JWT signing secret"),
        ("encryption_key", "aes256_k3y_f0r_pii_3ncrypt10n", "PII encryption key"),
    ]
    for key, value, desc in configs:
        conn.execute(
            "INSERT INTO system_config (key, value, description) VALUES (?, ?, ?)",
            (key, value, desc),
        )


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    try:
        create_tables(conn)
        seed_customers(conn)
        seed_orders(conn)
        seed_internal_notes(conn)
        seed_system_config(conn)
        conn.commit()
        print(f"Database seeded at {DB_PATH}")
        print(f"  Customers: {conn.execute('SELECT COUNT(*) FROM customers').fetchone()[0]}")
        print(f"  Orders: {conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]}")
        print(f"  Internal notes: {conn.execute('SELECT COUNT(*) FROM internal_notes').fetchone()[0]}")
        print(f"  System configs: {conn.execute('SELECT COUNT(*) FROM system_config').fetchone()[0]}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
