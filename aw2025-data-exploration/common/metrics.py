"""
common/metrics.py
=================
ONE place for the team's metric definitions (SQL snippets).

Rule: if a number appears in more than one component (Dashboard, Agent, notebooks...),
its definition lives here and everybody imports it. See 12_metric_definitions/README.md.

Naming convention for aliases in the snippets: h = Sales.SalesOrderHeader, d = Sales.SalesOrderDetail.
"""

# Customer type is derived from the sales channel flag (verified in 09_data_quality):
#   OnlineOrderFlag = 1 -> Individual (online)    OnlineOrderFlag = 0 -> Store (reseller)
CUSTOMER_TYPE_H = "CASE WHEN h.OnlineOrderFlag = 1 THEN 'Individual' ELSE 'Store' END"

# Each KPI: key -> (description, SQL returning ONE scalar)
KPIS: dict[str, tuple[str, str]] = {
    "orders": (
        "Number of orders (Order level = one row per SalesOrderID in SalesOrderHeader)",
        "SELECT COUNT(*) FROM Sales.SalesOrderHeader",
    ),
    "customers": (
        "Customers with at least one order",
        "SELECT COUNT(DISTINCT CustomerID) FROM Sales.SalesOrderHeader",
    ),
    "order_lines": (
        "Order lines (Order Line level = rows of SalesOrderDetail)",
        "SELECT COUNT(*) FROM Sales.SalesOrderDetail",
    ),
    "units_sold": (
        "Units sold = SUM(OrderQty)",
        "SELECT SUM(OrderQty) FROM Sales.SalesOrderDetail",
    ),
    "products_sold": (
        "Distinct products that appear in at least one order line",
        "SELECT COUNT(DISTINCT ProductID) FROM Sales.SalesOrderDetail",
    ),
    "revenue_line_total": (
        "Revenue (net of discounts, before tax & freight) = SUM(LineTotal) at line level",
        "SELECT SUM(LineTotal) FROM Sales.SalesOrderDetail",
    ),
    "revenue_subtotal": (
        "Same revenue at header level = SUM(SubTotal). Must equal revenue_line_total",
        "SELECT SUM(SubTotal) FROM Sales.SalesOrderHeader",
    ),
    "total_due": (
        "Total billed = SubTotal + TaxAmt + Freight (includes tax and freight; NOT revenue)",
        "SELECT SUM(TotalDue) FROM Sales.SalesOrderHeader",
    ),
    "avg_order_value": (
        "Average order value = AVG(SubTotal) per order",
        "SELECT AVG(SubTotal) FROM Sales.SalesOrderHeader",
    ),
    "avg_products_per_order": (
        "Average DISTINCT products per order",
        """SELECT AVG(CAST(n AS float)) FROM
           (SELECT SalesOrderID, COUNT(DISTINCT ProductID) AS n
            FROM Sales.SalesOrderDetail GROUP BY SalesOrderID) t""",
    ),
    "repeat_customer_rate": (
        "Share of customers with 2+ orders",
        """SELECT CAST(SUM(CASE WHEN n >= 2 THEN 1 ELSE 0 END) AS float) / COUNT(*) FROM
           (SELECT CustomerID, COUNT(*) AS n
            FROM Sales.SalesOrderHeader GROUP BY CustomerID) t""",
    ),
}

# Values taken from aw2025_exploration_report.txt -> used as a regression check.
# (key, expected value, relative tolerance)
EXPECTED_FROM_FIRST_EXPLORATION: dict[str, tuple[float, float]] = {
    "orders": (31465, 0.0),
    "customers": (19119, 0.0),
    "order_lines": (121317, 0.0),
    "products_sold": (266, 0.0),
    "revenue_line_total": (109846381.40, 1e-6),
    "revenue_subtotal": (109846381.40, 1e-6),
    "total_due": (123216786.12, 1e-6),
    "repeat_customer_rate": (0.3907, 1e-3),
}
