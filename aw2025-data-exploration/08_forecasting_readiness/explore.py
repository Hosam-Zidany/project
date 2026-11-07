"""08_forecasting_readiness - weekly series, gaps, structural break, autocorrelation, baseline accuracy.

EXPLORATION only: the baselines here are reference points the real models must beat.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.db import Report, query  # noqa: E402

r = Report(__file__, "Forecasting readiness (weekly series)")

BREAK_DATE = pd.Timestamp("2024-07-01")  # suspected structural break (see 05_time_coverage)
HORIZON = 12                              # weeks held out for the baseline test

weekly = query(
    """
    SELECT week_start, COUNT(*) AS orders, SUM(SubTotal) AS revenue,
           SUM(CASE WHEN OnlineOrderFlag = 1 THEN 1 ELSE 0 END) AS individual_orders,
           SUM(CASE WHEN OnlineOrderFlag = 0 THEN 1 ELSE 0 END) AS store_orders,
           SUM(CASE WHEN OnlineOrderFlag = 1 THEN SubTotal ELSE 0 END) AS individual_revenue,
           SUM(CASE WHEN OnlineOrderFlag = 0 THEN SubTotal ELSE 0 END) AS store_revenue
    FROM (SELECT DATEADD(day, -(DATEDIFF(day, 0, CAST(OrderDate AS date)) % 7), CAST(OrderDate AS date)) AS week_start,
                 SubTotal, OnlineOrderFlag
          FROM Sales.SalesOrderHeader) x
    GROUP BY week_start ORDER BY week_start
    """
)

if weekly.empty:
    r.note("No data returned - check the connection (python 00_setup/test_connection.py).")
    r.finish()
    raise SystemExit(0)

weekly["week_start"] = pd.to_datetime(weekly["week_start"])
w = weekly.set_index("week_start")
full_index = pd.date_range(w.index.min(), w.index.max(), freq="W-MON")  # weeks start on Monday
missing_weeks = full_index.difference(w.index)
w = w.reindex(full_index).fillna(0.0)
w.index.name = "week_start"

r.show("1. Weekly series (Monday-based weeks) - head", w.reset_index(), "weekly_series", max_rows=10)
r.note(f"{len(w)} weeks from {w.index.min():%Y-%m-%d} to {w.index.max():%Y-%m-%d}; "
       f"weeks with no orders (filled with 0): {len(missing_weeks)}")

last_week_days = query(
    "SELECT COUNT(DISTINCT CAST(OrderDate AS date)) AS days_with_orders FROM Sales.SalesOrderHeader "
    "WHERE OrderDate >= :d",
    {"d": w.index.max().to_pydatetime()},
)
r.show("2. Days with orders in the LAST week (<7 means the last week may be incomplete)", last_week_days)

# ---- structural break ---------------------------------------------------------------------
before, after = w[w.index < BREAK_DATE], w[w.index >= BREAK_DATE]
brk = pd.DataFrame({
    "period": [f"before {BREAK_DATE:%Y-%m-%d}", f"from {BREAK_DATE:%Y-%m-%d}"],
    "weeks": [len(before), len(after)],
    "mean_weekly_orders": [before["orders"].mean(), after["orders"].mean()],
    "mean_weekly_revenue": [before["revenue"].mean(), after["revenue"].mean()],
    "mean_weekly_individual_orders": [before["individual_orders"].mean(), after["individual_orders"].mean()],
    "mean_weekly_store_orders": [before["store_orders"].mean(), after["store_orders"].mean()],
})
r.show("3. Structural break check (mean weekly level before vs after)", brk.round(2), "structural_break")

# ---- autocorrelation ----------------------------------------------------------------------
rows = []
for col in ["orders", "revenue"]:
    for lag in [1, 2, 4, 8, 13, 26, 52]:
        if len(w) > lag + 5:
            rows.append({"series": col, "lag_weeks": lag, "autocorr": round(float(w[col].autocorr(lag)), 3)})
r.show("4. Autocorrelation (high at lag 1 = persistence; lag 52 needs 2+ years)", pd.DataFrame(rows), "autocorrelation")

# ---- optional statistical tests -------------------------------------------------------------
try:
    from statsmodels.tsa.stattools import adfuller

    out = []
    for col in ["orders", "revenue"]:
        stat, pval, *_ = adfuller(w[col].values, autolag="AIC")
        out.append({"series": col, "adf_stat": round(stat, 3), "p_value": round(pval, 4),
                    "stationary_at_5pct": bool(pval < 0.05)})
    r.show("5. ADF stationarity test (a trend/level shift usually means NOT stationary -> differencing needed)",
           pd.DataFrame(out), "adf_test")
except ImportError:
    r.note("statsmodels not installed: skipping the ADF test (pip install statsmodels)")

# ---- baseline accuracy ---------------------------------------------------------------------
def smape(actual: np.ndarray, forecast: np.ndarray) -> float:
    return float(np.mean(2 * np.abs(forecast - actual) / (np.abs(actual) + np.abs(forecast) + 1e-9)) * 100)


results = []
for col in ["orders", "revenue"]:
    s = w[col]
    train, test = s.iloc[:-HORIZON], s.iloc[-HORIZON:]
    candidates = {
        "naive (last value)": np.repeat(train.iloc[-1], HORIZON),
        "moving average (last 4 weeks)": np.repeat(train.iloc[-4:].mean(), HORIZON),
    }
    if len(s) > 52 + HORIZON:
        candidates["seasonal naive (52 weeks ago)"] = s.shift(52).iloc[-HORIZON:].values
    for name, fc in candidates.items():
        err = test.values - fc
        results.append({"series": col, "baseline": name, "MAE": round(float(np.mean(np.abs(err))), 2),
                        "RMSE": round(float(np.sqrt(np.mean(err ** 2))), 2),
                        "sMAPE_%": round(smape(test.values, fc), 2)})
r.show(f"6. Baseline accuracy on the last {HORIZON} weeks (chronological split; any real model must beat these)",
       pd.DataFrame(results), "baseline_accuracy")

# ---- monthly view for comparison ------------------------------------------------------------
monthly = w[["orders", "revenue"]].resample("MS").sum()
r.note(f"Monthly aggregation gives only {len(monthly)} points -> weekly is the better starting granularity.")

r.finish()
