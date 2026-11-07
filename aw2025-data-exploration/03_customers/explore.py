"""03_customers - customer base, repeat behaviour, gaps between orders, cohorts, RFM."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.db import Report, query  # noqa: E402
from common.metrics import CUSTOMER_TYPE_H as CT  # noqa: E402

r = Report(__file__, "Customers exploration")

r.run(
    "1. Customer table vs customers who actually ordered",
    """
    SELECT COUNT(*) AS customers_in_table,
           SUM(CASE WHEN StoreID IS NULL THEN 1 ELSE 0 END) AS person_customers,
           SUM(CASE WHEN StoreID IS NOT NULL THEN 1 ELSE 0 END) AS store_customers,
           SUM(CASE WHEN EXISTS (SELECT 1 FROM Sales.SalesOrderHeader h WHERE h.CustomerID = c.CustomerID)
                    THEN 1 ELSE 0 END) AS with_orders
    FROM Sales.Customer c
    """,
    "customer_table_summary",
)

r.run(
    "2. Orders per customer: distribution",
    """
    SELECT n_orders, COUNT(*) AS customers
    FROM (SELECT CustomerID, COUNT(*) AS n_orders FROM Sales.SalesOrderHeader GROUP BY CustomerID) t
    GROUP BY n_orders ORDER BY n_orders
    """,
    "orders_per_customer",
    max_rows=40,
)

r.run(
    "3. Repeat customers by type",
    f"""
    SELECT customer_type, COUNT(*) AS customers,
           SUM(CASE WHEN n >= 2 THEN 1 ELSE 0 END) AS repeat_customers,
           CAST(100.0 * SUM(CASE WHEN n >= 2 THEN 1 ELSE 0 END) / COUNT(*) AS decimal(5,2)) AS repeat_pct,
           AVG(CAST(n AS float)) AS avg_orders, MAX(n) AS max_orders
    FROM (SELECT h.CustomerID, {CT} AS customer_type, COUNT(*) AS n
          FROM Sales.SalesOrderHeader h GROUP BY h.CustomerID, {CT}) t
    GROUP BY customer_type
    """,
    "repeat_by_type",
)

r.run(
    "4. Does any customer appear with BOTH channels? (expected: 0)",
    """
    SELECT COUNT(*) AS customers_in_both_channels FROM
      (SELECT CustomerID FROM Sales.SalesOrderHeader
       GROUP BY CustomerID HAVING COUNT(DISTINCT OnlineOrderFlag) > 1) t
    """,
    "customers_both_channels",
)

r.run(
    "5. Gap between consecutive orders (days): summary",
    """
    WITH g AS (
      SELECT DATEDIFF(day, LAG(OrderDate) OVER (PARTITION BY CustomerID ORDER BY OrderDate, SalesOrderID), OrderDate) AS gap
      FROM Sales.SalesOrderHeader)
    SELECT COUNT(gap) AS pairs, SUM(CASE WHEN gap = 0 THEN 1 ELSE 0 END) AS same_day_pairs,
           AVG(CAST(gap AS float)) AS mean_gap, MIN(gap) AS min_gap, MAX(gap) AS max_gap
    FROM g WHERE gap IS NOT NULL
    """,
    "gap_summary",
)

r.run(
    "6. Gap between consecutive orders (days): percentiles",
    """
    WITH g AS (
      SELECT DATEDIFF(day, LAG(OrderDate) OVER (PARTITION BY CustomerID ORDER BY OrderDate, SalesOrderID), OrderDate) AS gap
      FROM Sales.SalesOrderHeader)
    SELECT DISTINCT
           PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY gap) OVER () AS p25,
           PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY gap) OVER () AS median,
           PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY gap) OVER () AS p75,
           PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY gap) OVER () AS p90
    FROM g WHERE gap IS NOT NULL
    """,
    "gap_percentiles",
)

r.run(
    "7. Acquisition cohorts: new customers per month and how many ever came back",
    """
    WITH f AS (SELECT CustomerID, MIN(OrderDate) AS first_order, COUNT(*) AS n
               FROM Sales.SalesOrderHeader GROUP BY CustomerID)
    SELECT YEAR(first_order) AS yr, MONTH(first_order) AS mo, COUNT(*) AS new_customers,
           SUM(CASE WHEN n >= 2 THEN 1 ELSE 0 END) AS later_repeat
    FROM f GROUP BY YEAR(first_order), MONTH(first_order) ORDER BY yr, mo
    """,
    "cohorts_by_first_order_month",
    max_rows=50,
)

r.run(
    "8. Top 20 customers by revenue",
    f"""
    SELECT TOP 20 h.CustomerID, {CT} AS customer_type, COUNT(*) AS orders,
           SUM(h.SubTotal) AS revenue, MIN(h.OrderDate) AS first_order, MAX(h.OrderDate) AS last_order
    FROM Sales.SalesOrderHeader h
    GROUP BY h.CustomerID, {CT} ORDER BY revenue DESC
    """,
    "top_customers",
)

r.run(
    "9. Customer concentration: share of revenue from the top 1% / 10% of customers",
    """
    WITH c AS (SELECT CustomerID, SUM(SubTotal) AS rev FROM Sales.SalesOrderHeader GROUP BY CustomerID),
         r AS (SELECT rev, NTILE(100) OVER (ORDER BY rev DESC) AS pct_bucket FROM c)
    SELECT SUM(CASE WHEN pct_bucket = 1 THEN rev ELSE 0 END) / SUM(rev) AS top_1pct_share,
           SUM(CASE WHEN pct_bucket <= 10 THEN rev ELSE 0 END) / SUM(rev) AS top_10pct_share
    FROM r
    """,
    "revenue_concentration",
)

r.run(
    "10. Customers by territory and type",
    f"""
    SELECT t.Name AS territory, {CT} AS customer_type, COUNT(DISTINCT h.CustomerID) AS customers
    FROM Sales.SalesOrderHeader h JOIN Sales.SalesTerritory t ON t.TerritoryID = h.TerritoryID
    GROUP BY t.Name, {CT} ORDER BY t.Name, customer_type
    """,
    "customers_by_territory",
    max_rows=30,
)

r.run(
    "11. Stores: orders per store and sales person assignment",
    """
    SELECT COUNT(*) AS stores,
           SUM(CASE WHEN SalesPersonID IS NULL THEN 1 ELSE 0 END) AS stores_without_salesperson
    FROM Sales.Store
    """,
    "stores_summary",
)

# ---- RFM with pandas ----------------------------------------------------------------
rfm = query(
    f"""
    SELECT h.CustomerID, {CT} AS customer_type, MAX(h.OrderDate) AS last_order,
           COUNT(*) AS frequency, SUM(h.SubTotal) AS monetary
    FROM Sales.SalesOrderHeader h GROUP BY h.CustomerID, {CT}
    """
)
if not rfm.empty:
    rfm["last_order"] = pd.to_datetime(rfm["last_order"])
    ref_date = rfm["last_order"].max()
    rfm["recency_days"] = (ref_date - rfm["last_order"]).dt.days
    # rank(method="first") avoids qcut errors when many customers have identical values
    rfm["R"] = pd.qcut(rfm["recency_days"].rank(method="first"), 4, labels=[4, 3, 2, 1]).astype(int)
    rfm["F"] = pd.qcut(rfm["frequency"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    rfm["M"] = pd.qcut(rfm["monetary"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    rfm["RFM_score"] = rfm["R"] + rfm["F"] + rfm["M"]
    r.note(f"RFM reference date = {ref_date:%Y-%m-%d} (last order in the data)")
    summary = rfm.groupby("customer_type")[["recency_days", "frequency", "monetary"]].describe().T
    r.show("12. RFM summary by customer type", summary.reset_index(), "rfm_summary", max_rows=40)
    r.show("13. RFM score distribution", rfm.groupby(["customer_type", "RFM_score"]).size().reset_index(name="customers"),
           "rfm_score_distribution", max_rows=40)
    rfm.to_csv(r.out / "rfm_per_customer.csv", index=False, encoding="utf-8-sig")

r.finish()
