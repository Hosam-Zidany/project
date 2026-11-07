"""04_products - catalog, hierarchy, sales by product/category, never-sold products, margin."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.db import Report  # noqa: E402

r = Report(__file__, "Products exploration")

r.run(
    "1. Hierarchy sizes (catalog)",
    """
    SELECT (SELECT COUNT(*) FROM Production.ProductCategory)    AS categories,
           (SELECT COUNT(*) FROM Production.ProductSubcategory) AS subcategories,
           (SELECT COUNT(*) FROM Production.Product)            AS products,
           (SELECT COUNT(*) FROM Production.Product WHERE ProductSubcategoryID IS NULL) AS products_without_subcategory
    """,
    "hierarchy_sizes",
)

r.run(
    "2. Sales by category (order lines, units, revenue)",
    """
    SELECT pc.Name AS category, COUNT(DISTINCT d.ProductID) AS products_sold, COUNT(*) AS order_lines,
           SUM(d.OrderQty) AS units, SUM(d.LineTotal) AS revenue
    FROM Sales.SalesOrderDetail d
    JOIN Production.Product p            ON p.ProductID = d.ProductID
    LEFT JOIN Production.ProductSubcategory ps ON ps.ProductSubcategoryID = p.ProductSubcategoryID
    LEFT JOIN Production.ProductCategory pc    ON pc.ProductCategoryID = ps.ProductCategoryID
    GROUP BY pc.Name ORDER BY revenue DESC
    """,
    "sales_by_category",
)

r.run(
    "3. Sales by subcategory",
    """
    SELECT pc.Name AS category, ps.Name AS subcategory, COUNT(DISTINCT d.ProductID) AS products_sold,
           SUM(d.OrderQty) AS units, SUM(d.LineTotal) AS revenue
    FROM Sales.SalesOrderDetail d
    JOIN Production.Product p            ON p.ProductID = d.ProductID
    LEFT JOIN Production.ProductSubcategory ps ON ps.ProductSubcategoryID = p.ProductSubcategoryID
    LEFT JOIN Production.ProductCategory pc    ON pc.ProductCategoryID = ps.ProductCategoryID
    GROUP BY pc.Name, ps.Name ORDER BY revenue DESC
    """,
    "sales_by_subcategory",
    max_rows=45,
)

r.run(
    "4. Top 25 products by revenue",
    """
    SELECT TOP 25 p.ProductID, p.Name, pc.Name AS category, SUM(d.OrderQty) AS units,
           SUM(d.LineTotal) AS revenue, COUNT(DISTINCT d.SalesOrderID) AS orders
    FROM Sales.SalesOrderDetail d
    JOIN Production.Product p            ON p.ProductID = d.ProductID
    LEFT JOIN Production.ProductSubcategory ps ON ps.ProductSubcategoryID = p.ProductSubcategoryID
    LEFT JOIN Production.ProductCategory pc    ON pc.ProductCategoryID = ps.ProductCategoryID
    GROUP BY p.ProductID, p.Name, pc.Name ORDER BY revenue DESC
    """,
    "top_products_revenue",
    max_rows=25,
)

r.run(
    "5. Top 25 products by number of ORDERS containing them (basket support)",
    """
    SELECT TOP 25 p.ProductID, p.Name, COUNT(DISTINCT d.SalesOrderID) AS orders_containing,
           CAST(100.0 * COUNT(DISTINCT d.SalesOrderID) / (SELECT COUNT(*) FROM Sales.SalesOrderHeader) AS decimal(6,2)) AS support_pct
    FROM Sales.SalesOrderDetail d JOIN Production.Product p ON p.ProductID = d.ProductID
    GROUP BY p.ProductID, p.Name ORDER BY orders_containing DESC
    """,
    "top_products_orders",
    max_rows=25,
)

r.run(
    "6. Catalog products that were NEVER sold - summary by category and flags",
    """
    SELECT ISNULL(pc.Name, '(no category)') AS category, p.FinishedGoodsFlag, p.MakeFlag, COUNT(*) AS products
    FROM Production.Product p
    LEFT JOIN Production.ProductSubcategory ps ON ps.ProductSubcategoryID = p.ProductSubcategoryID
    LEFT JOIN Production.ProductCategory pc    ON pc.ProductCategoryID = ps.ProductCategoryID
    WHERE NOT EXISTS (SELECT 1 FROM Sales.SalesOrderDetail d WHERE d.ProductID = p.ProductID)
    GROUP BY ISNULL(pc.Name, '(no category)'), p.FinishedGoodsFlag, p.MakeFlag
    ORDER BY products DESC
    """,
    "never_sold_summary",
)

r.run(
    "7. Never-sold products: full list",
    """
    SELECT p.ProductID, p.Name, ISNULL(pc.Name, '(no category)') AS category, p.FinishedGoodsFlag, p.MakeFlag,
           p.ListPrice, p.SellStartDate, p.SellEndDate
    FROM Production.Product p
    LEFT JOIN Production.ProductSubcategory ps ON ps.ProductSubcategoryID = p.ProductSubcategoryID
    LEFT JOIN Production.ProductCategory pc    ON pc.ProductCategoryID = ps.ProductCategoryID
    WHERE NOT EXISTS (SELECT 1 FROM Sales.SalesOrderDetail d WHERE d.ProductID = p.ProductID)
    ORDER BY category, p.Name
    """,
    "never_sold_products",
    max_rows=10,
)

r.run(
    "8. Gross margin vs CURRENT StandardCost (approximation: cost history exists in ProductCostHistory)",
    """
    SELECT pc.Name AS category, SUM(d.LineTotal) AS revenue, SUM(d.OrderQty * p.StandardCost) AS std_cost,
           SUM(d.LineTotal) - SUM(d.OrderQty * p.StandardCost) AS margin,
           (SUM(d.LineTotal) - SUM(d.OrderQty * p.StandardCost)) / NULLIF(SUM(d.LineTotal), 0) AS margin_pct
    FROM Sales.SalesOrderDetail d
    JOIN Production.Product p            ON p.ProductID = d.ProductID
    LEFT JOIN Production.ProductSubcategory ps ON ps.ProductSubcategoryID = p.ProductSubcategoryID
    LEFT JOIN Production.ProductCategory pc    ON pc.ProductCategoryID = ps.ProductCategoryID
    GROUP BY pc.Name ORDER BY revenue DESC
    """,
    "margin_by_category",
)

r.run(
    "9. First sale year per product (new product introductions)",
    """
    SELECT YEAR(first_sale) AS first_sale_year, COUNT(*) AS products FROM
      (SELECT d.ProductID, MIN(h.OrderDate) AS first_sale
       FROM Sales.SalesOrderDetail d JOIN Sales.SalesOrderHeader h ON h.SalesOrderID = d.SalesOrderID
       GROUP BY d.ProductID) x
    GROUP BY YEAR(first_sale) ORDER BY first_sale_year
    """,
    "first_sale_year",
)

r.run(
    "10. Products whose sold UnitPrice changed (min <> max) - biggest relative change first",
    """
    SELECT TOP 20 d.ProductID, p.Name, p.ListPrice, MIN(d.UnitPrice) AS min_price, MAX(d.UnitPrice) AS max_price,
           COUNT(*) AS order_lines
    FROM Sales.SalesOrderDetail d JOIN Production.Product p ON p.ProductID = d.ProductID
    GROUP BY d.ProductID, p.Name, p.ListPrice
    HAVING MIN(d.UnitPrice) <> MAX(d.UnitPrice)
    ORDER BY (MAX(d.UnitPrice) - MIN(d.UnitPrice)) / NULLIF(MIN(d.UnitPrice), 0) DESC
    """,
    "price_changes",
)

r.run(
    "11. Attribute completeness in the catalog (NULL counts)",
    """
    SELECT COUNT(*) AS products, SUM(CASE WHEN Color IS NULL THEN 1 ELSE 0 END) AS no_color,
           SUM(CASE WHEN Size IS NULL THEN 1 ELSE 0 END) AS no_size,
           SUM(CASE WHEN Weight IS NULL THEN 1 ELSE 0 END) AS no_weight,
           SUM(CASE WHEN ProductSubcategoryID IS NULL THEN 1 ELSE 0 END) AS no_subcategory,
           SUM(CASE WHEN ProductModelID IS NULL THEN 1 ELSE 0 END) AS no_model,
           SUM(CASE WHEN SellEndDate IS NOT NULL THEN 1 ELSE 0 END) AS discontinued
    FROM Production.Product
    """,
    "catalog_completeness",
)

r.run(
    "12. Category revenue by year (feeds Dashboard trend charts)",
    """
    SELECT YEAR(h.OrderDate) AS yr, pc.Name AS category, SUM(d.LineTotal) AS revenue, SUM(d.OrderQty) AS units
    FROM Sales.SalesOrderDetail d
    JOIN Sales.SalesOrderHeader h        ON h.SalesOrderID = d.SalesOrderID
    JOIN Production.Product p            ON p.ProductID = d.ProductID
    LEFT JOIN Production.ProductSubcategory ps ON ps.ProductSubcategoryID = p.ProductSubcategoryID
    LEFT JOIN Production.ProductCategory pc    ON pc.ProductCategoryID = ps.ProductCategoryID
    GROUP BY YEAR(h.OrderDate), pc.Name ORDER BY yr, revenue DESC
    """,
    "category_revenue_by_year",
    max_rows=20,
)

r.run(
    "13. Category mix by customer type (revenue)",
    """
    SELECT CASE WHEN h.OnlineOrderFlag = 1 THEN 'Individual' ELSE 'Store' END AS customer_type,
           pc.Name AS category, SUM(d.LineTotal) AS revenue, SUM(d.OrderQty) AS units
    FROM Sales.SalesOrderDetail d
    JOIN Sales.SalesOrderHeader h        ON h.SalesOrderID = d.SalesOrderID
    JOIN Production.Product p            ON p.ProductID = d.ProductID
    LEFT JOIN Production.ProductSubcategory ps ON ps.ProductSubcategoryID = p.ProductSubcategoryID
    LEFT JOIN Production.ProductCategory pc    ON pc.ProductCategoryID = ps.ProductCategoryID
    GROUP BY CASE WHEN h.OnlineOrderFlag = 1 THEN 'Individual' ELSE 'Store' END, pc.Name
    ORDER BY customer_type, revenue DESC
    """,
    "category_mix_by_type",
)

r.finish()
