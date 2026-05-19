"""Recompute rs_rating only (Step 2) for a given calculation_date.

Usage:
    python rerun_rs_rating.py 2026-05-18
"""
import sys
from datetime import datetime
import pandas as pd
import numpy as np
from psycopg2.extras import execute_values
from store_stock_data import get_db_connection


def rerun(calc_date):
    conn = get_db_connection(statement_timeout_seconds=600)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT symbol, weighted_change
        FROM stock_indicators
        WHERE calculation_date = %s
          AND weighted_change IS NOT NULL
        ORDER BY weighted_change DESC
        """,
        (calc_date,),
    )
    rows = cur.fetchall()
    if not rows:
        print(f"No rows for {calc_date}")
        return

    df = pd.DataFrame(rows, columns=["symbol", "weighted_change"])
    df["weighted_change"] = pd.to_numeric(df["weighted_change"], errors="coerce")
    before = len(df)
    df = df[np.isfinite(df["weighted_change"])].copy()
    dropped = before - len(df)
    if dropped:
        print(f"Dropped {dropped} non-finite rows")

    df["rs_rating"] = df["weighted_change"].rank(pct=True, method="min")
    df["rs_rating"] = (df["rs_rating"] * 98 + 1).round().astype(int).clip(1, 99)

    update_values = [
        (int(r["rs_rating"]), r["symbol"], calc_date) for _, r in df.iterrows()
    ]
    execute_values(
        cur,
        """
        UPDATE stock_indicators
        SET rs_rating = v.rs_rating
        FROM (VALUES %s) AS v(rs_rating, symbol, calculation_date)
        WHERE stock_indicators.symbol = v.symbol
          AND stock_indicators.calculation_date = v.calculation_date
        """,
        update_values,
        page_size=1000,
        template="(%s::INTEGER, %s::TEXT, %s::DATE)",
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"Updated rs_rating for {len(df)} symbols on {calc_date}")
    print(f"Range: {df['rs_rating'].min()} - {df['rs_rating'].max()}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python rerun_rs_rating.py YYYY-MM-DD")
        sys.exit(1)
    rerun(datetime.strptime(sys.argv[1], "%Y-%m-%d").date())
