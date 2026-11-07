"""07_sequence_readiness - is the data suitable for Sequential Pattern Mining (GSP / PrefixSpan)?"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.db import Report, query  # noqa: E402
from common.metrics import CUSTOMER_TYPE_H as CT  # noqa: E402

r = Report(__file__, "Sequential Pattern readiness")

r.run(
    "1. Sequence length (orders per customer) - how many customers qualify for different minimum lengths",
    f"""
    WITH c AS (SELECT h.CustomerID, {CT} AS customer_type, COUNT(*) AS n
               FROM Sales.SalesOrderHeader h GROUP BY h.CustomerID, {CT})
    SELECT customer_type, COUNT(*) AS customers,
           SUM(CASE WHEN n >= 2 THEN 1 ELSE 0 END) AS len_2_plus,
           SUM(CASE WHEN n >= 3 THEN 1 ELSE 0 END) AS len_3_plus,
           SUM(CASE WHEN n >= 4 THEN 1 ELSE 0 END) AS len_4_plus,
           SUM(CASE WHEN n >= 5 THEN 1 ELSE 0 END) AS len_5_plus
    FROM c GROUP BY customer_type
    """,
    "sequence_length_thresholds",
)

r.run(
    "2. Gap buckets between consecutive orders (days), by customer type",
    f"""
    WITH o AS (
      SELECT {CT} AS customer_type,
             DATEDIFF(day, LAG(h.OrderDate) OVER (PARTITION BY h.CustomerID ORDER BY h.OrderDate, h.SalesOrderID), h.OrderDate) AS gap
      FROM Sales.SalesOrderHeader h)
    SELECT customer_type, bucket, COUNT(*) AS pairs FROM (
      SELECT customer_type,
             CASE WHEN gap = 0 THEN '0 same day' WHEN gap <= 30 THEN '1-30' WHEN gap <= 90 THEN '31-90'
                  WHEN gap <= 180 THEN '91-180' WHEN gap <= 365 THEN '181-365' ELSE '366+' END AS bucket
      FROM o WHERE gap IS NOT NULL) x
    GROUP BY customer_type, bucket ORDER BY customer_type, MIN(CASE bucket WHEN '0 same day' THEN 0 WHEN '1-30' THEN 1
        WHEN '31-90' THEN 2 WHEN '91-180' THEN 3 WHEN '181-365' THEN 4 ELSE 5 END)
    """,
    "gap_buckets",
)

r.run(
    "3. Customers with at least one same-day pair (tie handling needed)",
    """
    WITH o AS (
      SELECT CustomerID, DATEDIFF(day, LAG(OrderDate) OVER (PARTITION BY CustomerID ORDER BY OrderDate, SalesOrderID), OrderDate) AS gap
      FROM Sales.SalesOrderHeader)
    SELECT COUNT(DISTINCT CustomerID) AS customers_with_same_day_orders, COUNT(*) AS same_day_pairs
    FROM o WHERE gap = 0
    """,
    "same_day_customers",
)

r.run(
    "4. Distinct dates vs orders per customer (if equal, order dates already separate events)",
    """
    SELECT SUM(n_orders) AS orders, SUM(n_dates) AS distinct_customer_dates
    FROM (SELECT CustomerID, COUNT(*) AS n_orders, COUNT(DISTINCT CAST(OrderDate AS date)) AS n_dates
          FROM Sales.SalesOrderHeader GROUP BY CustomerID) t
    """,
    "dates_vs_orders",
)

r.run(
    "5. Repeat customers by FIRST-order year (right-censoring: recent cohorts had less time to return)",
    """
    WITH c AS (SELECT CustomerID, MIN(OrderDate) AS first_order, COUNT(*) AS n
               FROM Sales.SalesOrderHeader GROUP BY CustomerID)
    SELECT YEAR(first_order) AS first_order_year, COUNT(*) AS customers,
           SUM(CASE WHEN n >= 2 THEN 1 ELSE 0 END) AS repeat_customers,
           CAST(100.0 * SUM(CASE WHEN n >= 2 THEN 1 ELSE 0 END) / COUNT(*) AS decimal(5,2)) AS repeat_pct
    FROM c GROUP BY YEAR(first_order) ORDER BY first_order_year
    """,
    "repeat_by_first_year",
)

# ---- Category-level transitions between consecutive orders (pandas) --------------------------
orders = query(
    f"""
    WITH oc AS (
      SELECT DISTINCT d.SalesOrderID, ISNULL(pc.Name, 'Unknown') AS cat
      FROM Sales.SalesOrderDetail d
      JOIN Production.Product p ON p.ProductID = d.ProductID
      LEFT JOIN Production.ProductSubcategory ps ON ps.ProductSubcategoryID = p.ProductSubcategoryID
      LEFT JOIN Production.ProductCategory pc ON pc.ProductCategoryID = ps.ProductCategoryID),
    sets AS (SELECT SalesOrderID, STRING_AGG(cat, ' + ') WITHIN GROUP (ORDER BY cat) AS cat_set
             FROM oc GROUP BY SalesOrderID)
    SELECT h.CustomerID, {CT} AS customer_type, h.SalesOrderID, h.OrderDate, s.cat_set
    FROM Sales.SalesOrderHeader h JOIN sets s ON s.SalesOrderID = h.SalesOrderID
    ORDER BY h.CustomerID, h.OrderDate, h.SalesOrderID
    """
)
if not orders.empty:
    orders["OrderDate"] = pd.to_datetime(orders["OrderDate"])
    g = orders.groupby("CustomerID")
    orders["next_set"] = g["cat_set"].shift(-1)
    orders["next_date"] = g["OrderDate"].shift(-1)
    trans = orders.dropna(subset=["next_set"]).copy()
    trans["gap_days"] = (trans["next_date"] - trans["OrderDate"]).dt.days
    top = (trans.groupby(["customer_type", "cat_set", "next_set"]).agg(count=("CustomerID", "size"),
                                                                       median_gap_days=("gap_days", "median"))
           .reset_index().sort_values("count", ascending=False))
    r.show("6. Most common category-set transitions between consecutive orders (what follows what)",
           top, "category_transitions", max_rows=25)

    seq_str = (orders.groupby("CustomerID")["cat_set"].apply(lambda s: " -> ".join(s.head(5)))
               .value_counts().reset_index())
    seq_str.columns = ["first_5_orders_as_category_sets", "customers"]
    r.show("7. Most common complete customer paths (first 5 orders, category level)", seq_str, "common_paths", max_rows=25)

    r.note("Category-level only. Product-level sequences are much sparser; the algorithm step must decide the level.")

r.finish()
