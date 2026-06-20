import os
import pandas as pd
import numpy as np
import sqlalchemy as sa

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

def generate_ledger(year: int = 2024) -> pd.DataFrame:
    """
    Generate a synthetic monthly ledger with budget and actual figures.
    In production, replace this with a real DB query or CSV read.
    """
    rng = np.random.default_rng(seed=42)
    rows = []

    base_budgets = {
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

    for (category, account), base in base_budgets.items():
        for month in range(1, 13):
            seasonal_factor = SEASONALITY[month]
            budget = base * seasonal_factor * rng.uniform(0.97, 1.03)
            noise  = rng.uniform(0.80, 1.20)
            actual = budget * noise
            rows.append({
                "year":     year,
                "month":    month,
                "category": category,
                "account":  account,
                "budget":   round(budget, 2),
                "actual":   round(actual, 2),
            })

    return pd.DataFrame(rows)


# ── Real data source: MySQL ───────────────────────────────────────────────────

def fetch_ledger_from_db(year: int, month: int | None = None) -> pd.DataFrame:
    """
    Pull ledger rows from a real MySQL `ledger` table.

    Requires env var DATABASE_URL, e.g.:
        mysql+pymysql://reporter:reporter_pw@mysql:3306/financial_reporter

    If month is given, filters to that month only (used by the monthly DAG).
    Falls back to generate_ledger() if DATABASE_URL is not set, so local
    testing still works without a database.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("[data] DATABASE_URL not set — falling back to generate_ledger()")
        df = generate_ledger(year)
        return df[df["month"] == month] if month else df

    engine = sa.create_engine(db_url)
    query = "SELECT year, month, category, account, budget, actual FROM ledger WHERE year = :year"
    params = {"year": year}
    if month:
        query += " AND month = :month"
        params["month"] = month

    with engine.connect() as conn:
        result = conn.execute(sa.text(query), params)
        rows = result.fetchall()
        cols = result.keys()

    df = pd.DataFrame(rows, columns=list(cols))
    df["budget"] = df["budget"].astype(float)
    df["actual"] = df["actual"].astype(float)
    print(f"[data] Fetched {len(df)} rows from MySQL for year={year} month={month}")
    return df


def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add variance columns and friendly month label."""
    df = df.copy()
    df["variance"]     = (df["actual"] - df["budget"]).round(2)
    df["variance_pct"] = (df["variance"] / df["budget"] * 100).round(2)
    df["month_name"]   = pd.to_datetime(df["month"], format="%m").dt.strftime("%b")
    df["gross_profit"] = df.apply(
        lambda r: r["actual"] if r["category"] == "Revenue" else -r["actual"],
        axis=1
    ).round(2)
    return df