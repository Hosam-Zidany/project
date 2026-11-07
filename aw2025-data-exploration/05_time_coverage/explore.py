"""05_time_coverage - date range, missing days, seasonality, and the mid-2024 jump."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.db import Report  # noqa: E402

r = Report(__file__, "Time coverage exploration")

r.run(
    "1. Date range of the main business tables",
    """
    SELECT 'Sales.SalesOrderHeader (OrderDate)' AS source, MIN(OrderDate) AS first_date, MAX(OrderDate) AS last_date, COUNT(*) AS n FROM Sales.SalesOrderHeader
    UNION ALL SELECT 'Sales.SalesOrderHeader (ShipDate)', MIN(ShipDate), MAX(ShipDate), COUNT(*) FROM Sales.SalesOrderHeader
    UNION ALL SELECT 'Purchasing.PurchaseOrderHeader', MIN(OrderDate), MAX(OrderDate), COUNT(*) FROM Purchasing.PurchaseOrderHeader
    UNION ALL SELECT 'Production.WorkOrder (StartDate)', MIN(StartDate), MAX(StartDate), COUNT(*) FROM Production.WorkOrder
    UNION ALL SELECT 'Production.TransactionHistory', MIN(TransactionDate), MAX(TransactionDate), COUNT(*) FROM Production.TransactionHistory
    UNION ALL SELECT 'HumanResources.Employee (HireDate)', MIN(HireDate), MAX(HireDate), COUNT(*) FROM HumanResources.Employee
    """,
    "date_ranges",
)

daily = r.run(
    "2. Daily orders (full series saved to CSV)",
    """
    SELECT CAST(OrderDate AS date) AS d, COUNT(*) AS orders, SUM(SubTotal) AS revenue
    FROM Sales.SalesOrderHeader GROUP BY CAST(OrderDate AS date) ORDER BY d
    """,
    "daily_orders",
    max_rows=10,
)

if not daily.empty:
    daily["d"] = pd.to_datetime(daily["d"])
    full_range = pd.date_range(daily["d"].min(), daily["d"].max(), freq="D")
    missing = full_range.difference(daily["d"])
    r.show(
        "3. Calendar days with ZERO orders inside the covered range",
        pd.DataFrame({"missing_day": missing, "weekday": missing.day_name()}),
        "missing_days",
    )
    r.note(f"{len(missing)} missing days out of {len(full_range)} calendar days "
           f"({daily['d'].min():%Y-%m-%d} -> {daily['d'].max():%Y-%m-%d})")
    last_month = daily[daily["d"] >= daily["d"].max() - pd.Timedelta(days=14)]
    r.show("4. Last 15 days of data (is the final period complete?)", last_month, None, max_rows=20)

r.run(
    "5. Monthly orders by customer type (WHERE the mid-2024 jump comes from)",
    """
    SELECT YEAR(OrderDate) AS yr, MONTH(OrderDate) AS mo,
           SUM(CASE WHEN OnlineOrderFlag = 1 THEN 1 ELSE 0 END) AS individual_orders,
           SUM(CASE WHEN OnlineOrderFlag = 0 THEN 1 ELSE 0 END) AS store_orders,
           COUNT(*) AS total_orders
    FROM Sales.SalesOrderHeader GROUP BY YEAR(OrderDate), MONTH(OrderDate) ORDER BY yr, mo
    """,
    "monthly_by_type",
    max_rows=50,
)

r.run(
    "6. Monthly: new vs returning customers (first order of a customer = new)",
    """
    WITH o AS (
      SELECT SalesOrderID, OrderDate,
             ROW_NUMBER() OVER (PARTITION BY CustomerID ORDER BY OrderDate, SalesOrderID) AS rn
      FROM Sales.SalesOrderHeader)
    SELECT YEAR(OrderDate) AS yr, MONTH(OrderDate) AS mo,
           SUM(CASE WHEN rn = 1 THEN 1 ELSE 0 END) AS first_orders,
           SUM(CASE WHEN rn > 1 THEN 1 ELSE 0 END) AS repeat_orders
    FROM o GROUP BY YEAR(OrderDate), MONTH(OrderDate) ORDER BY yr, mo
    """,
    "monthly_new_vs_repeat",
    max_rows=50,
)

r.run(
    "7. Monthly average distinct products per order, by customer type (basket structure over time)",
    """
    WITH b AS (SELECT SalesOrderID, COUNT(DISTINCT ProductID) AS n FROM Sales.SalesOrderDetail GROUP BY SalesOrderID)
    SELECT YEAR(h.OrderDate) AS yr, MONTH(h.OrderDate) AS mo,
           CASE WHEN h.OnlineOrderFlag = 1 THEN 'Individual' ELSE 'Store' END AS customer_type,
           COUNT(*) AS orders, AVG(CAST(b.n AS float)) AS avg_products_per_order
    FROM Sales.SalesOrderHeader h JOIN b ON b.SalesOrderID = h.SalesOrderID
    GROUP BY YEAR(h.OrderDate), MONTH(h.OrderDate), CASE WHEN h.OnlineOrderFlag = 1 THEN 'Individual' ELSE 'Store' END
    ORDER BY yr, mo, customer_type
    """,
    "monthly_basket_by_type",
    max_rows=10,
)

r.run(
    "8. First date an INDIVIDUAL order contains 2+ distinct products (explains 0% multi-product in 2022-2023)",
    """
    WITH b AS (SELECT SalesOrderID, COUNT(DISTINCT ProductID) AS n FROM Sales.SalesOrderDetail GROUP BY SalesOrderID)
    SELECT MIN(h.OrderDate) AS first_multi_product_individual_order,
           SUM(CASE WHEN b.n > 1 THEN 1 ELSE 0 END) AS multi_product_orders
    FROM Sales.SalesOrderHeader h JOIN b ON b.SalesOrderID = h.SalesOrderID
    WHERE h.OnlineOrderFlag = 1 AND b.n > 1
    """,
    "first_multi_product_individual",
)

r.run(
    "9. Day of week (1 = Monday ... 7 = Sunday)",
    """
    SELECT (DATEDIFF(day, 0, CAST(OrderDate AS date)) % 7) + 1 AS weekday_num,
           COUNT(*) AS orders, SUM(SubTotal) AS revenue
    FROM Sales.SalesOrderHeader
    GROUP BY (DATEDIFF(day, 0, CAST(OrderDate AS date)) % 7) + 1 ORDER BY weekday_num
    """,
    "day_of_week",
)

r.run(
    "10. Day of month",
    """
    SELECT DAY(OrderDate) AS day_of_month, COUNT(*) AS orders
    FROM Sales.SalesOrderHeader GROUP BY DAY(OrderDate) ORDER BY day_of_month
    """,
    "day_of_month",
    max_rows=31,
)

r.run(
    "11. Does the time-of-day exist in OrderDate? (all midnight => date-only precision)",
    """
    SELECT SUM(CASE WHEN CAST(OrderDate AS time) <> '00:00:00' THEN 1 ELSE 0 END) AS orders_with_time_part,
           COUNT(*) AS orders
    FROM Sales.SalesOrderHeader
    """,
    "time_part_check",
)

r.finish()
