"""
seed_mysql.py
─────────────────────────────────────────────
One-time script to create and populate the `ledger` table in MySQL
with realistic sample data. Run this once after MySQL starts.

Usage:
    python seed_mysql.py
"""

import os
import numpy as np
import sqlalchemy as sa
from sqlalchemy import text

DB_URL = os.environ.get(
    "DATABASE_URL",
    "mysql+pymysql://reporter:reporter_pw@localhost:3306/financial_reporter"
)

ACCOUNTS = {
    "Revenue": ["Product Sales", "Service Revenue", "Subscription"],
    "COGS":    ["Materials", "Labor", "Shipping"],
    "OpEx":    ["Marketing", "Engineering", "G&A", "R&D"],
}

SEASONALITY = {
    1: 0.85, 2: 0.80, 3: 0.90, 4: 0.95,
    5: 1.00, 6: 1.05, 7: 1.10, 8: 1.08,
    9: 1.02, 10: 1.15, 11: 1.20, 12: 1.30,
}

BASE_BUDGETS = {
    ("Revenue", "Product Sales"):    280_000,
    ("Revenue", "Service Revenue"):  120_000,
    ("Revenue", "Subscription"):      90_000,
    ("COGS",    "Materials"):        110_000,
    ("COGS",    "Labor"):             80_000,
    ("COGS",    "Shipping"):          30_000,
    ("OpEx",    "Marketing"):         60_000,
    ("OpEx",    "Engineering"):      150_000,
    ("OpEx",    "G&A"):               50_000,
    ("OpEx",    "R&D"):               70_000,
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ledger (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    year      INT NOT NULL,
    month     INT NOT NULL,
    category  VARCHAR(50) NOT NULL,
    account   VARCHAR(100) NOT NULL,
    budget    DECIMAL(14,2) NOT NULL,
    actual    DECIMAL(14,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_year_month (year, month)
) ENGINE=InnoDB;
"""


def seed(years=(2024, 2025, 2026)):
    engine = sa.create_engine(DB_URL)

    with engine.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))

        # Avoid duplicate seeding
        existing = conn.execute(text("SELECT COUNT(*) FROM ledger")).scalar()
        if existing and existing > 0:
            print(f"[seed] ledger already has {existing} rows — skipping seed.")
            return

        rng = np.random.default_rng(seed=42)
        rows = []
        for year in years:
            for (category, account), base in BASE_BUDGETS.items():
                for month in range(1, 13):
                    seasonal = SEASONALITY[month]
                    budget = base * seasonal * rng.uniform(0.97, 1.03)
                    actual = budget * rng.uniform(0.80, 1.20)
                    rows.append({
                        "year": year, "month": month,
                        "category": category, "account": account,
                        "budget": round(budget, 2), "actual": round(actual, 2),
                    })

        conn.execute(
            text("""
                INSERT INTO ledger (year, month, category, account, budget, actual)
                VALUES (:year, :month, :category, :account, :budget, :actual)
            """),
            rows,
        )
        print(f"[seed] Inserted {len(rows)} rows into ledger across years {years}.")


if __name__ == "__main__":
    seed()
