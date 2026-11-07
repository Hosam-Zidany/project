"""10_purchasing_inventory - purchase orders, vendors, inventory, work orders (production), stock vs sales."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.db import Report  # noqa: E402

r = Report(__file__, "Purchasing, inventory and production exploration")

# ---------------- Purchasing -----------------------------------------------------------
r.run(
    "1. Purchase orders by year and status (Status: 1 pending, 2 approved, 3 rejected, 4 complete - verify in 01)",
    """
    SELECT YEAR(OrderDate) AS yr, Status, COUNT(*) AS purchase_orders, SUM(SubTotal) AS subtotal, SUM(TotalDue) AS total_due
    FROM Purchasing.PurchaseOrderHeader GROUP BY YEAR(OrderDate), Status ORDER BY yr, Status
    """,
    "po_by_year_status",
)

r.run(
    "2. Top 20 vendors by purchase value",
    """
    SELECT TOP 20 v.BusinessEntityID AS vendor_id, v.Name, v.CreditRating, v.PreferredVendorStatus, v.ActiveFlag,
           COUNT(*) AS purchase_orders, SUM(h.SubTotal) AS purchase_value
    FROM Purchasing.PurchaseOrderHeader h JOIN Purchasing.Vendor v ON v.BusinessEntityID = h.VendorID
    GROUP BY v.BusinessEntityID, v.Name, v.CreditRating, v.PreferredVendorStatus, v.ActiveFlag
    ORDER BY purchase_value DESC
    """,
    "top_vendors",
)

r.run(
    "3. Purchased products: quantities, value, receipt and rejection rates",
    """
    SELECT TOP 25 p.ProductID, p.Name, SUM(d.OrderQty) AS ordered_qty, SUM(d.ReceivedQty) AS received_qty,
           SUM(d.RejectedQty) AS rejected_qty, SUM(d.LineTotal) AS purchase_value,
           CAST(SUM(d.RejectedQty) AS float) / NULLIF(SUM(d.ReceivedQty), 0) AS rejection_rate
    FROM Purchasing.PurchaseOrderDetail d JOIN Production.Product p ON p.ProductID = d.ProductID
    GROUP BY p.ProductID, p.Name ORDER BY purchase_value DESC
    """,
    "purchased_products",
)

r.run(
    "4. Vendors per product, lead times and prices (ProductVendor)",
    """
    SELECT COUNT(*) AS product_vendor_rows, COUNT(DISTINCT ProductID) AS products, COUNT(DISTINCT BusinessEntityID) AS vendors,
           AVG(CAST(AverageLeadTime AS float)) AS avg_lead_time_days, MAX(AverageLeadTime) AS max_lead_time_days
    FROM Purchasing.ProductVendor
    """,
    "product_vendor_summary",
)

r.run(
    "5. Overlap: products that are both purchased and sold",
    """
    SELECT (SELECT COUNT(DISTINCT ProductID) FROM Purchasing.PurchaseOrderDetail) AS purchased_products,
           (SELECT COUNT(DISTINCT ProductID) FROM Sales.SalesOrderDetail)         AS sold_products,
           (SELECT COUNT(DISTINCT pd.ProductID) FROM Purchasing.PurchaseOrderDetail pd
            WHERE EXISTS (SELECT 1 FROM Sales.SalesOrderDetail sd WHERE sd.ProductID = pd.ProductID)) AS purchased_and_sold
    """,
    "purchased_vs_sold",
)

# ---------------- Inventory -------------------------------------------------------------
r.run(
    "6. Inventory by location",
    """
    SELECT l.LocationID, l.Name AS location, COUNT(*) AS rows_, COUNT(DISTINCT i.ProductID) AS products, SUM(i.Quantity) AS total_quantity
    FROM Production.ProductInventory i JOIN Production.Location l ON l.LocationID = i.LocationID
    GROUP BY l.LocationID, l.Name ORDER BY total_quantity DESC
    """,
    "inventory_by_location",
)

r.run(
    "7. Stock on hand vs units sold (top 30 by stock) - inventory is a SNAPSHOT, not a history",
    """
    WITH inv AS (SELECT ProductID, SUM(Quantity) AS stock FROM Production.ProductInventory GROUP BY ProductID),
         s AS (SELECT ProductID, SUM(OrderQty) AS units_sold FROM Sales.SalesOrderDetail GROUP BY ProductID)
    SELECT TOP 30 p.ProductID, p.Name, inv.stock, ISNULL(s.units_sold, 0) AS units_sold,
           CAST(inv.stock AS float) / NULLIF(s.units_sold, 0) AS stock_to_sales_ratio
    FROM inv JOIN Production.Product p ON p.ProductID = inv.ProductID LEFT JOIN s ON s.ProductID = inv.ProductID
    ORDER BY inv.stock DESC
    """,
    "stock_vs_sales",
)

r.run(
    "8. Products with stock but never sold / sold but with no stock row",
    """
    SELECT (SELECT COUNT(DISTINCT i.ProductID) FROM Production.ProductInventory i
            WHERE NOT EXISTS (SELECT 1 FROM Sales.SalesOrderDetail d WHERE d.ProductID = i.ProductID)) AS stocked_never_sold,
           (SELECT COUNT(DISTINCT d.ProductID) FROM Sales.SalesOrderDetail d
            WHERE NOT EXISTS (SELECT 1 FROM Production.ProductInventory i WHERE i.ProductID = d.ProductID)) AS sold_no_stock_row
    """,
    "stock_sales_coverage",
)

# ---------------- Production ------------------------------------------------------------
r.run(
    "9. Work orders by year: quantities, scrap rate, duration",
    """
    SELECT YEAR(StartDate) AS yr, COUNT(*) AS work_orders, SUM(OrderQty) AS ordered_qty, SUM(ScrappedQty) AS scrapped_qty,
           CAST(SUM(ScrappedQty) AS float) / NULLIF(SUM(OrderQty), 0) AS scrap_rate,
           AVG(CAST(DATEDIFF(day, StartDate, EndDate) AS float)) AS avg_days_start_to_end
    FROM Production.WorkOrder GROUP BY YEAR(StartDate) ORDER BY yr
    """,
    "work_orders_by_year",
)

r.run(
    "10. Scrap reasons",
    """
    SELECT sr.Name AS scrap_reason, COUNT(*) AS work_orders, SUM(w.ScrappedQty) AS scrapped_qty
    FROM Production.WorkOrder w JOIN Production.ScrapReason sr ON sr.ScrapReasonID = w.ScrapReasonID
    GROUP BY sr.Name ORDER BY scrapped_qty DESC
    """,
    "scrap_reasons",
)

r.run(
    "11. Products with the highest scrap rate (min 1,000 units ordered)",
    """
    SELECT TOP 15 p.ProductID, p.Name, SUM(w.OrderQty) AS ordered_qty, SUM(w.ScrappedQty) AS scrapped_qty,
           CAST(SUM(w.ScrappedQty) AS float) / NULLIF(SUM(w.OrderQty), 0) AS scrap_rate
    FROM Production.WorkOrder w JOIN Production.Product p ON p.ProductID = w.ProductID
    GROUP BY p.ProductID, p.Name HAVING SUM(w.OrderQty) >= 1000 ORDER BY scrap_rate DESC
    """,
    "highest_scrap_products",
)

r.run(
    "12. Transaction history by type (W = work order, S = sales order, P = purchase order)",
    """
    SELECT TransactionType, COUNT(*) AS transactions, SUM(Quantity) AS total_quantity, SUM(ActualCost) AS total_cost,
           MIN(TransactionDate) AS first_date, MAX(TransactionDate) AS last_date
    FROM Production.TransactionHistory GROUP BY TransactionType
    """,
    "transaction_history_by_type",
)

r.run(
    "13. Bill of materials: assemblies with the most components",
    """
    SELECT TOP 15 b.ProductAssemblyID, p.Name, COUNT(*) AS component_rows
    FROM Production.BillOfMaterials b JOIN Production.Product p ON p.ProductID = b.ProductAssemblyID
    GROUP BY b.ProductAssemblyID, p.Name ORDER BY component_rows DESC
    """,
    "bom_top_assemblies",
)

r.finish()
