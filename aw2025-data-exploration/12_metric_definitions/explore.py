"""12_metric_definitions - run every canonical KPI from common/metrics.py and compare with the first exploration report."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.db import Report, scalar  # noqa: E402
from common.metrics import EXPECTED_FROM_FIRST_EXPLORATION, KPIS  # noqa: E402

r = Report(__file__, "Metric definitions - canonical KPIs and regression check")

rows = []
values: dict[str, float] = {}
for key, (description, sql) in KPIS.items():
    try:
        value = scalar(sql)
        value = float(value) if value is not None else None
    except Exception as exc:  # noqa: BLE001
        rows.append({"kpi": key, "value": None, "description": description, "check": f"ERROR {type(exc).__name__}"})
        continue
    values[key] = value
    check = ""
    if key in EXPECTED_FROM_FIRST_EXPLORATION and value is not None:
        expected, tol = EXPECTED_FROM_FIRST_EXPLORATION[key]
        ok = abs(value - expected) <= abs(expected) * tol
        check = f"PASS (expected {expected:,})" if ok else f"MISMATCH (expected {expected:,})"
    rows.append({"kpi": key, "value": value, "description": description, "check": check})

r.show("1. Canonical KPIs (definitions live in common/metrics.py)", pd.DataFrame(rows), "kpi_values", max_rows=30)

# ---- relationships between the money fields ---------------------------------------------
if {"revenue_line_total", "revenue_subtotal", "total_due"} <= values.keys():
    diff_rev = values["revenue_line_total"] - values["revenue_subtotal"]
    extra = values["total_due"] - values["revenue_subtotal"]
    rel = pd.DataFrame([
        {"relationship": "SUM(LineTotal) - SUM(SubTotal)  (expected ~0)", "value": round(diff_rev, 2)},
        {"relationship": "SUM(TotalDue) - SUM(SubTotal)  (= tax + freight)", "value": round(extra, 2)},
        {"relationship": "tax + freight as % of revenue", "value": round(100 * extra / values["revenue_subtotal"], 2)},
    ])
    r.show("2. How the money fields relate", rel, "money_field_relationships")

r.run(
    "3. Tax + freight totals (must equal TotalDue - SubTotal above)",
    "SELECT SUM(TaxAmt) AS tax, SUM(Freight) AS freight, SUM(TaxAmt) + SUM(Freight) AS tax_plus_freight FROM Sales.SalesOrderHeader",
    "tax_freight_totals",
)

r.run(
    "4. KPI by year - the SAME definitions, ready for Dashboard (2025 partial)",
    """
    SELECT YEAR(OrderDate) AS yr, COUNT(*) AS orders, COUNT(DISTINCT CustomerID) AS customers,
           SUM(SubTotal) AS revenue, AVG(SubTotal) AS avg_order_value
    FROM Sales.SalesOrderHeader GROUP BY YEAR(OrderDate) ORDER BY yr
    """,
    "kpi_by_year",
)

r.finish()
