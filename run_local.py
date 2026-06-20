"""
run_local.py
────────────────────────────────────────────
Test the full pipeline locally without Airflow.

Usage:
    pip install -r requirements.txt
    python run_local.py

The report will be saved to: output/financial_report_<year>_<month>.xlsx
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from src.data.generate_data import generate_ledger, compute_metrics
from src.report.excel_builder import generate_report


def main():
    now         = datetime.now()
    year        = now.year
    month       = now.month
    month_label = now.strftime("%B %Y")

    print(f"Generating financial report for {month_label}...")

    # 1. Generate & transform data
    df = generate_ledger(year)
    df = compute_metrics(df)
    df = df[df["month"] == month].copy()
    print(f"  Rows generated: {len(df)}")

    # 2. Build Excel report
    os.makedirs("output", exist_ok=True)
    output_path = f"output/financial_report_{year}_{month:02d}.xlsx"
    generate_report(df, output_path, month_label)

    print(f"\nDone! Open your report: {output_path}")
    print("\nNext step: set up email credentials in docker-compose.yml, then run:")
    print("  docker compose up -d")
    print("  # Visit http://localhost:8080  (user: admin / pass: admin)")
    print("  # Trigger 'financial_report_monthly' DAG manually to test end-to-end")


if __name__ == "__main__":
    main()
