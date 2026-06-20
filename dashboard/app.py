"""
dashboard/app.py
─────────────────────────────────────────────
Live Streamlit dashboard for the financial reporting pipeline.

Data source priority:
  1. MySQL `ledger` table (if DATABASE_URL is set / reachable)
  2. Local parquet files in output/ (fallback, e.g. for demoing without DB)
  3. Generated sample data (last resort, so the dashboard never shows blank)

Run:
    streamlit run dashboard/app.py
"""

import os
import sys
import glob
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(
    page_title="Financial Reporting Dashboard",
    page_icon="📊",
    layout="wide",
)

# ── Data loading ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_data() -> tuple[pd.DataFrame, str]:
    """Returns (dataframe, source_label)."""

    # 1. Try MySQL
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        try:
            import sqlalchemy as sa
            engine = sa.create_engine(db_url)
            with engine.connect() as conn:
                result = conn.execute(sa.text(
                    "SELECT year, month, category, account, budget, actual FROM ledger"
                ))
                rows = result.fetchall()
                cols = result.keys()
            df = pd.DataFrame(rows, columns=list(cols))
            if len(df):
                df["budget"] = df["budget"].astype(float)
                df["actual"] = df["actual"].astype(float)
                return df, "MySQL (live)"
        except Exception as e:
            st.sidebar.warning(f"MySQL unavailable, falling back. ({type(e).__name__}: {e})")

    # 2. Try local parquet files
    parquet_files = sorted(glob.glob(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "ledger_*.parquet"
    )))
    if parquet_files:
        dfs = [pd.read_parquet(f) for f in parquet_files]
        df = pd.concat(dfs, ignore_index=True)
        return df, f"Local parquet ({len(parquet_files)} file(s))"

    # 3. Last resort — generate sample data so dashboard is never empty
    from src.data.generate_data import generate_ledger
    df = pd.concat([generate_ledger(y) for y in (2024, 2025, 2026)], ignore_index=True)
    return df, "Sample data (generated)"


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["variance"] = df["actual"] - df["budget"]
    df["variance_pct"] = (df["variance"] / df["budget"] * 100).round(2)
    df["month_name"] = pd.to_datetime(df["month"], format="%m").dt.strftime("%b")
    return df


df, source_label = load_data()
df = add_metrics(df)

# ── Sidebar filters ───────────────────────────────────────────────────────────

st.sidebar.title("Filters")
st.sidebar.caption(f"Data source: {source_label}")

years = sorted(df["year"].unique(), reverse=True)
selected_year = st.sidebar.selectbox("Year", years, index=0)

categories = sorted(df["category"].unique())
selected_categories = st.sidebar.multiselect("Category", categories, default=categories)

if st.sidebar.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()

filtered = df[(df["year"] == selected_year) & (df["category"].isin(selected_categories))]

# ── Header ─────────────────────────────────────────────────────────────────────

st.title("Financial Reporting Dashboard")
st.caption(f"Automated pipeline output · {selected_year} · {len(filtered)} line items")

# ── KPI row ────────────────────────────────────────────────────────────────────

total_budget = filtered["budget"].sum()
total_actual = filtered["actual"].sum()
total_var    = total_actual - total_budget
var_pct      = (total_var / total_budget * 100) if total_budget else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total budget", f"${total_budget:,.0f}")
c2.metric("Total actual", f"${total_actual:,.0f}")
c3.metric("Variance", f"${total_var:,.0f}", delta=f"{var_pct:+.1f}%")
over_count = filtered.groupby("account")["variance_pct"].mean().gt(10).sum()
c4.metric("Accounts over budget", int(over_count))

st.divider()

# ── Monthly trend chart ───────────────────────────────────────────────────────

st.subheader("Monthly budget vs actual")

monthly = (
    filtered.groupby(["month", "month_name"])[["budget", "actual"]]
    .sum()
    .reset_index()
    .sort_values("month")
)

fig = go.Figure()
fig.add_trace(go.Bar(x=monthly["month_name"], y=monthly["budget"], name="Budget", marker_color="#888780"))
fig.add_trace(go.Bar(x=monthly["month_name"], y=monthly["actual"], name="Actual", marker_color="#378ADD"))
fig.update_layout(
    barmode="group",
    height=400,
    margin=dict(l=20, r=20, t=20, b=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig, use_container_width=True)

# ── Two-column: category breakdown + variance table ──────────────────────────

col_a, col_b = st.columns([1, 1.4])

with col_a:
    st.subheader("Spend by category")
    cat_totals = filtered.groupby("category")["actual"].sum().reset_index()
    pie = px.pie(
        cat_totals, names="category", values="actual", hole=0.5,
        color_discrete_sequence=["#378ADD", "#1D9E75", "#D85A30"],
    )
    pie.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(pie, use_container_width=True)

with col_b:
    st.subheader("Variance by account")
    acc_summary = (
        filtered.groupby(["category", "account"])
        .agg(budget=("budget", "sum"), actual=("actual", "sum"), variance=("variance", "sum"))
        .reset_index()
    )
    acc_summary["variance_pct"] = (acc_summary["variance"] / acc_summary["budget"] * 100).round(1)
    acc_summary["status"] = acc_summary["variance_pct"].apply(
        lambda v: "Over budget" if v > 10 else ("Under budget" if v < -10 else "On track")
    )

    def highlight_status(row):
        color = {"Over budget": "#FCEBEB", "Under budget": "#FAEEDA", "On track": "#EAF3DE"}[row["status"]]
        return [f"background-color: {color}"] * len(row)

    st.dataframe(
        acc_summary[["category", "account", "budget", "actual", "variance", "variance_pct", "status"]]
        .style.apply(highlight_status, axis=1)
        .format({"budget": "${:,.0f}", "actual": "${:,.0f}", "variance": "${:,.0f}", "variance_pct": "{:+.1f}%"}),
        use_container_width=True,
        height=340,
    )

st.divider()
st.caption("Built with Streamlit · reads live from MySQL, falls back to pipeline output files")