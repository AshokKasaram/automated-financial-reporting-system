"""
financial_report_dag.py
─────────────────────────────────────────────
Monthly automated financial reporting pipeline.

Schedule: 7am on the 1st of every month.
Tasks:
  1. extract_transform  — generate ledger data, compute metrics, save to parquet
  2. build_excel        — produce formatted 3-sheet .xlsx report
  3. send_email         — attach and email report to recipients

XCom keys passed between tasks:
  parquet_path  → str  (task 1 → task 2)
  report_path   → str  (task 2 → task 3)
  month_label   → str  (task 1 → tasks 2 & 3)
"""

import os
import sys

sys.path.insert(0, "/opt/airflow")

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# ── Config ────────────────────────────────────────────────────────────────────

OUTPUT_DIR  = "/opt/airflow/output"
RECIPIENTS  = os.environ.get("REPORT_RECIPIENTS", "you@example.com").split(",")

DEFAULT_ARGS = {
    "owner":            "data-team",
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
    "email_on_failure": False,   # set True + configure email in Airflow UI for alerts
}

# ── Task functions ─────────────────────────────────────────────────────────────

def task_extract_transform(**ctx):
    from src.data.generate_data import fetch_ledger_from_db, compute_metrics

    logical_date = ctx["logical_date"]
    year         = logical_date.year
    month        = logical_date.month
    month_label  = logical_date.strftime("%B %Y")

    df = fetch_ledger_from_db(year, month)
    df = compute_metrics(df)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    parquet_path = f"{OUTPUT_DIR}/ledger_{year}_{month:02d}.parquet"
    df.to_parquet(parquet_path, index=False)

    ctx["ti"].xcom_push(key="parquet_path", value=parquet_path)
    ctx["ti"].xcom_push(key="month_label",  value=month_label)

    print(f"[extract] Wrote {len(df)} rows → {parquet_path}")


def task_build_excel(**ctx):
    import pandas as pd
    from src.report.excel_builder import generate_report

    ti           = ctx["ti"]
    parquet_path = ti.xcom_pull(key="parquet_path", task_ids="extract_transform")
    month_label  = ti.xcom_pull(key="month_label",  task_ids="extract_transform")
    logical_date = ctx["logical_date"]

    df = pd.read_parquet(parquet_path)

    report_path = (
        f"{OUTPUT_DIR}/financial_report_"
        f"{logical_date.year}_{logical_date.month:02d}.xlsx"
    )
    generate_report(df, report_path, month_label)

    ti.xcom_push(key="report_path", value=report_path)


def task_send_email(**ctx):
    from src.notify.emailer import send_report

    ti          = ctx["ti"]
    report_path = ti.xcom_pull(key="report_path",  task_ids="build_excel")
    month_label = ti.xcom_pull(key="month_label",  task_ids="extract_transform")

    send_report(report_path, RECIPIENTS, month_label)


# ── DAG definition ─────────────────────────────────────────────────────────────

with DAG(
    dag_id       = "financial_report_monthly",
    default_args = DEFAULT_ARGS,
    description  = "Auto-generate and email a monthly financial report",
    schedule     = "0 7 1 * *",
    start_date   = datetime(2024, 1, 1),
    catchup      = False,
    tags         = ["finance", "reporting", "openpyxl"],
) as dag:

    extract_transform = PythonOperator(
        task_id          = "extract_transform",
        python_callable  = task_extract_transform,
        provide_context  = True,
    )

    build_excel = PythonOperator(
        task_id          = "build_excel",
        python_callable  = task_build_excel,
        provide_context  = True,
    )

    send_email = PythonOperator(
        task_id          = "send_email",
        python_callable  = task_send_email,
        provide_context  = True,
    )

    extract_transform >> build_excel >> send_email
