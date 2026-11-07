"""02_sales - revenue, orders, channels, territories, discounts, shipping."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.db import Report  # noqa: E402
from common.metrics import CUSTOMER_TYPE_H as CT  # noqa: E402

r = Report(__file__, "Sales exploration")

r.run(
    "1. Headline numbers (Order level: one row per order)",
    """
    SELECT COUNT(*) AS orders, COUNT(DISTINCT CustomerID) AS customers,
           SUM(SubTotal) AS subtotal, SUM(TaxAmt) AS tax, SUM(Freight) AS freight,
           SUM(TotalDue) AS total_due, AVG(SubTotal) AS avg_order_subtotal
    FROM Sales.SalesOrderHeader
    """,
    "headline",
)

r.run(
    "2. By year (2025 is PARTIAL: data ends 2025-06-29)",
    """
    SELECT YEAR(OrderDate) AS yr, COUNT(*) AS orders,
           COUNT(DISTINCT CAST(OrderDate AS date)) AS active_days,
           SUM(SubTotal) AS revenue, SUM(TotalDue) AS total_due, AVG(SubTotal) AS avg_order_value
    FROM Sales.SalesOrderHeader
    GROUP BY YEAR(OrderDate) ORDER BY yr
    """,
    "by_year",
)

r.run(
    "3. Like-for-like comparison: Jan 1 - Jun 29 of each full year (2023 onward)",
    """
    SELECT YEAR(OrderDate) AS yr, COUNT(*) AS orders, SUM(SubTotal) AS revenue,
           AVG(SubTotal) AS avg_order_value
    FROM Sales.SalesOrderHeader
    WHERE YEAR(OrderDate) >= 2023 AND MONTH(OrderDate) * 100 + DAY(OrderDate) <= 629
    GROUP BY YEAR(OrderDate) ORDER BY yr
    """,
    "same_period_jan_jun",
)

r.run(
    "4. Monthly orders and revenue",
    """
    SELECT YEAR(OrderDate) AS yr, MONTH(OrderDate) AS mo, COUNT(*) AS orders,
           COUNT(DISTINCT CustomerID) AS customers, SUM(SubTotal) AS revenue,
           AVG(SubTotal) AS avg_order_value
    FROM Sales.SalesOrderHeader
    GROUP BY YEAR(OrderDate), MONTH(OrderDate) ORDER BY yr, mo
    """,
    "monthly",
    max_rows=50,
)

r.run(
    "5. Channel / customer type",
    f"""
    SELECT {CT} AS customer_type, COUNT(*) AS orders, COUNT(DISTINCT h.CustomerID) AS customers,
           SUM(h.SubTotal) AS revenue, AVG(h.SubTotal) AS avg_order_value
    FROM Sales.SalesOrderHeader h
    GROUP BY {CT}
    """,
    "by_customer_type",
)

r.run(
    "6. Customer type x year",
    f"""
    SELECT YEAR(h.OrderDate) AS yr, {CT} AS customer_type, COUNT(*) AS orders,
           SUM(h.SubTotal) AS revenue, AVG(h.SubTotal) AS avg_order_value
    FROM Sales.SalesOrderHeader h
    GROUP BY YEAR(h.OrderDate), {CT} ORDER BY yr, customer_type
    """,
    "type_by_year",
)

r.run(
    "7. Territory",
    """
    SELECT t.TerritoryID, t.Name AS territory, t.CountryRegionCode AS country, t.[Group] AS region_group,
           COUNT(*) AS orders, COUNT(DISTINCT h.CustomerID) AS customers, SUM(h.SubTotal) AS revenue
    FROM Sales.SalesOrderHeader h JOIN Sales.SalesTerritory t ON t.TerritoryID = h.TerritoryID
    GROUP BY t.TerritoryID, t.Name, t.CountryRegionCode, t.[Group]
    ORDER BY revenue DESC
    """,
    "by_territory",
)

r.run(
    "8. Territory x customer type (revenue)",
    f"""
    SELECT t.Name AS territory, {CT} AS customer_type, COUNT(*) AS orders, SUM(h.SubTotal) AS revenue
    FROM Sales.SalesOrderHeader h JOIN Sales.SalesTerritory t ON t.TerritoryID = h.TerritoryID
    GROUP BY t.Name, {CT} ORDER BY t.Name, customer_type
    """,
    "territory_by_type",
    max_rows=30,
)

r.run(
    "9. Order value distribution (SubTotal percentiles) by customer type",
    f"""
    SELECT DISTINCT {CT} AS customer_type,
           PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY h.SubTotal) OVER (PARTITION BY h.OnlineOrderFlag) AS p10,
           PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY h.SubTotal) OVER (PARTITION BY h.OnlineOrderFlag) AS median,
           PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY h.SubTotal) OVER (PARTITION BY h.OnlineOrderFlag) AS p90,
           PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY h.SubTotal) OVER (PARTITION BY h.OnlineOrderFlag) AS p99
    FROM Sales.SalesOrderHeader h
    """,
    "order_value_percentiles",
)

r.run(
    "10. Sales people (Store orders only: online orders have no sales person)",
    """
    SELECT TOP 20 SalesPersonID, TerritoryID, COUNT(*) AS orders,
           COUNT(DISTINCT CustomerID) AS customers, SUM(SubTotal) AS revenue
    FROM Sales.SalesOrderHeader
    WHERE SalesPersonID IS NOT NULL
    GROUP BY SalesPersonID, TerritoryID ORDER BY revenue DESC
    """,
    "top_salespeople",
)

r.run(
    "11. Discounts at line level (Order Line level)",
    """
    SELECT CASE WHEN UnitPriceDiscount > 0 THEN 'discounted' ELSE 'full price' END AS line_type,
           COUNT(*) AS order_lines, SUM(LineTotal) AS revenue, AVG(UnitPriceDiscount) AS avg_discount_rate
    FROM Sales.SalesOrderDetail
    GROUP BY CASE WHEN UnitPriceDiscount > 0 THEN 'discounted' ELSE 'full price' END
    """,
    "discounts",
)

r.run(
    "12. Special offers",
    """
    SELECT so.SpecialOfferID, so.Description, so.Type, so.Category, so.DiscountPct,
           COUNT(*) AS order_lines, SUM(d.LineTotal) AS revenue
    FROM Sales.SalesOrderDetail d JOIN Sales.SpecialOffer so ON so.SpecialOfferID = d.SpecialOfferID
    GROUP BY so.SpecialOfferID, so.Description, so.Type, so.Category, so.DiscountPct
    ORDER BY revenue DESC
    """,
    "special_offers",
)

r.run(
    "13. Sales reasons (an order can have several reasons)",
    """
    SELECT sr.Name AS reason, sr.ReasonType, COUNT(DISTINCT x.SalesOrderID) AS orders
    FROM Sales.SalesOrderHeaderSalesReason x JOIN Sales.SalesReason sr ON sr.SalesReasonID = x.SalesReasonID
    GROUP BY sr.Name, sr.ReasonType ORDER BY orders DESC
    """,
    "sales_reasons",
)

r.run(
    "14. Ship method and fulfilment lags (days)",
    """
    SELECT sm.Name AS ship_method, COUNT(*) AS orders,
           AVG(CAST(DATEDIFF(day, h.OrderDate, h.ShipDate) AS float)) AS avg_days_to_ship,
           AVG(CAST(DATEDIFF(day, h.OrderDate, h.DueDate) AS float)) AS avg_days_to_due,
           AVG(h.Freight) AS avg_freight
    FROM Sales.SalesOrderHeader h JOIN Purchasing.ShipMethod sm ON sm.ShipMethodID = h.ShipMethodID
    GROUP BY sm.Name ORDER BY orders DESC
    """,
    "ship_methods",
)

r.run(
    "15. Tax and freight as a share of SubTotal, by customer type",
    f"""
    SELECT {CT} AS customer_type,
           SUM(h.TaxAmt) / SUM(h.SubTotal) AS tax_share, SUM(h.Freight) / SUM(h.SubTotal) AS freight_share
    FROM Sales.SalesOrderHeader h GROUP BY {CT}
    """,
    "tax_freight_share",
)

r.run(
    "16. Currency: how many orders carry a CurrencyRateID",
    """
    SELECT COUNT(*) AS orders, SUM(CASE WHEN CurrencyRateID IS NOT NULL THEN 1 ELSE 0 END) AS with_currency_rate
    FROM Sales.SalesOrderHeader
    """,
    "currency_usage",
)

r.finish()
