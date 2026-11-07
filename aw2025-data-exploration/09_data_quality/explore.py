"""09_data_quality - NULLs, orphans, duplicates, reconciliation, sanity checks."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect  # noqa: E402

from common.db import Report, get_engine, query  # noqa: E402

r = Report(__file__, "Data quality exploration")


# ---- 1. NULL profile of the key tables (generated from SQLAlchemy reflection) ---------------
def null_profile(schema: str, table: str) -> pd.DataFrame:
    cols = [c["name"] for c in inspect(get_engine()).get_columns(table, schema=schema)]
    selects = ", ".join(f"SUM(CASE WHEN [{c}] IS NULL THEN 1 ELSE 0 END) AS [{c}]" for c in cols)
    row = query(f"SELECT COUNT(*) AS __total, {selects} FROM {schema}.{table}").iloc[0]
    total = int(row["__total"])
    out = pd.DataFrame({"column": cols, "null_count": [int(row[c]) for c in cols]})
    out["null_pct"] = (100 * out["null_count"] / total).round(2)
    out["table_rows"] = total
    return out[out["null_count"] > 0].sort_values("null_count", ascending=False)


for schema, table in [("Sales", "SalesOrderHeader"), ("Sales", "SalesOrderDetail"),
                      ("Sales", "Customer"), ("Production", "Product")]:
    try:
        prof = null_profile(schema, table)
        r.show(f"1. Columns with NULLs: {schema}.{table}", prof, f"nulls_{table}", max_rows=40)
    except Exception as exc:  # noqa: BLE001
        r.section(f"1. NULL profile {schema}.{table}")
        r.note(f"failed: {type(exc).__name__}: {str(exc)[:300]}")

# ---- 2. Orphans ------------------------------------------------------------------------------
r.run(
    "2. Orphan checks (all should be 0)",
    """
    SELECT 'detail without header' AS check_name, COUNT(*) AS n FROM Sales.SalesOrderDetail d
      WHERE NOT EXISTS (SELECT 1 FROM Sales.SalesOrderHeader h WHERE h.SalesOrderID = d.SalesOrderID)
    UNION ALL SELECT 'header without any detail', COUNT(*) FROM Sales.SalesOrderHeader h
      WHERE NOT EXISTS (SELECT 1 FROM Sales.SalesOrderDetail d WHERE d.SalesOrderID = h.SalesOrderID)
    UNION ALL SELECT 'header with unknown customer', COUNT(*) FROM Sales.SalesOrderHeader h
      WHERE NOT EXISTS (SELECT 1 FROM Sales.Customer c WHERE c.CustomerID = h.CustomerID)
    UNION ALL SELECT 'detail with unknown product', COUNT(*) FROM Sales.SalesOrderDetail d
      WHERE NOT EXISTS (SELECT 1 FROM Production.Product p WHERE p.ProductID = d.ProductID)
    UNION ALL SELECT 'header with unknown territory', COUNT(*) FROM Sales.SalesOrderHeader h
      WHERE h.TerritoryID IS NOT NULL AND NOT EXISTS (SELECT 1 FROM Sales.SalesTerritory t WHERE t.TerritoryID = h.TerritoryID)
    """,
    "orphans",
)

# ---- 3. Reconciliation -----------------------------------------------------------------------
r.run(
    "3. Header vs Detail: SubTotal should equal SUM(LineTotal) per order",
    """
    WITH d AS (SELECT SalesOrderID, SUM(LineTotal) AS line_sum FROM Sales.SalesOrderDetail GROUP BY SalesOrderID)
    SELECT COUNT(*) AS orders_compared,
           SUM(CASE WHEN ABS(h.SubTotal - d.line_sum) > 0.01 THEN 1 ELSE 0 END) AS mismatched_orders,
           MAX(ABS(h.SubTotal - d.line_sum)) AS max_abs_diff
    FROM Sales.SalesOrderHeader h JOIN d ON d.SalesOrderID = h.SalesOrderID
    """,
    "subtotal_vs_linetotal",
)

r.run(
    "4. TotalDue should equal SubTotal + TaxAmt + Freight",
    """
    SELECT COUNT(*) AS orders,
           SUM(CASE WHEN ABS(TotalDue - (SubTotal + TaxAmt + Freight)) > 0.01 THEN 1 ELSE 0 END) AS mismatched_orders,
           MAX(ABS(TotalDue - (SubTotal + TaxAmt + Freight))) AS max_abs_diff
    FROM Sales.SalesOrderHeader
    """,
    "totaldue_formula",
)

r.run(
    "5. LineTotal should equal OrderQty * UnitPrice * (1 - UnitPriceDiscount)",
    """
    SELECT COUNT(*) AS lines,
           SUM(CASE WHEN ABS(LineTotal - OrderQty * UnitPrice * (1 - UnitPriceDiscount)) > 0.01 THEN 1 ELSE 0 END) AS mismatched_lines
    FROM Sales.SalesOrderDetail
    """,
    "linetotal_formula",
)

# ---- 4. Duplicates ---------------------------------------------------------------------------
r.run(
    "6. Same product on several lines of the SAME order (relevant for basket building)",
    """
    SELECT COUNT(*) AS order_product_pairs_with_multiple_lines FROM
      (SELECT SalesOrderID, ProductID FROM Sales.SalesOrderDetail
       GROUP BY SalesOrderID, ProductID HAVING COUNT(*) > 1) t
    """,
    "duplicate_product_lines",
)

# ---- 5. Value sanity -------------------------------------------------------------------------
r.run(
    "7. Value sanity on order lines",
    """
    SELECT SUM(CASE WHEN OrderQty <= 0 THEN 1 ELSE 0 END) AS qty_le_0,
           SUM(CASE WHEN UnitPrice <= 0 THEN 1 ELSE 0 END) AS price_le_0,
           SUM(CASE WHEN LineTotal <= 0 THEN 1 ELSE 0 END) AS line_total_le_0,
           SUM(CASE WHEN UnitPriceDiscount < 0 OR UnitPriceDiscount > 1 THEN 1 ELSE 0 END) AS bad_discount,
           MIN(OrderQty) AS min_qty, MAX(OrderQty) AS max_qty, MAX(UnitPrice) AS max_unit_price
    FROM Sales.SalesOrderDetail
    """,
    "line_value_sanity",
)

r.run(
    "8. Date sanity on orders",
    """
    SELECT SUM(CASE WHEN ShipDate < OrderDate THEN 1 ELSE 0 END) AS ship_before_order,
           SUM(CASE WHEN DueDate < OrderDate THEN 1 ELSE 0 END) AS due_before_order,
           SUM(CASE WHEN OrderDate > GETDATE() THEN 1 ELSE 0 END) AS order_in_future,
           SUM(CASE WHEN ShipDate IS NULL THEN 1 ELSE 0 END) AS no_ship_date
    FROM Sales.SalesOrderHeader
    """,
    "date_sanity",
)

# ---- 6. Consistency of derived business fields -------------------------------------------------
r.run(
    "9. Is OnlineOrderFlag consistent with the Customer type (StoreID)? and with SalesPersonID?",
    """
    SELECT h.OnlineOrderFlag,
           CASE WHEN c.StoreID IS NULL THEN 'person customer' ELSE 'store customer' END AS customer_kind,
           CASE WHEN h.SalesPersonID IS NULL THEN 'no sales person' ELSE 'has sales person' END AS sales_person,
           COUNT(*) AS orders
    FROM Sales.SalesOrderHeader h JOIN Sales.Customer c ON c.CustomerID = h.CustomerID
    GROUP BY h.OnlineOrderFlag,
             CASE WHEN c.StoreID IS NULL THEN 'person customer' ELSE 'store customer' END,
             CASE WHEN h.SalesPersonID IS NULL THEN 'no sales person' ELSE 'has sales person' END
    ORDER BY h.OnlineOrderFlag
    """,
    "channel_consistency",
)

r.run(
    "10. Status values present (meaning: see data dictionary in 01_schema_overview)",
    "SELECT Status, COUNT(*) AS orders FROM Sales.SalesOrderHeader GROUP BY Status ORDER BY Status",
    "status_values",
)

r.run(
    "11. Orders whose customer's territory differs from the order's territory",
    """
    SELECT COUNT(*) AS orders,
           SUM(CASE WHEN c.TerritoryID <> h.TerritoryID THEN 1 ELSE 0 END) AS different_territory
    FROM Sales.SalesOrderHeader h JOIN Sales.Customer c ON c.CustomerID = h.CustomerID
    """,
    "territory_consistency",
)

r.run(
    "12. Double-counting demo: join Header to Detail and sum SubTotal (WRONG) vs correct",
    """
    SELECT (SELECT SUM(SubTotal) FROM Sales.SalesOrderHeader) AS correct_sum_subtotal,
           (SELECT SUM(h.SubTotal) FROM Sales.SalesOrderHeader h
            JOIN Sales.SalesOrderDetail d ON d.SalesOrderID = h.SalesOrderID) AS wrong_sum_after_join,
           (SELECT SUM(LineTotal) FROM Sales.SalesOrderDetail) AS sum_line_total
    """,
    "double_counting_demo",
)

r.finish()
