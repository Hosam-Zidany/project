"""01_schema_overview - tables, columns, keys, relationships, data dictionary."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect  # noqa: E402

from common.db import Report, get_engine  # noqa: E402

r = Report(__file__, "Schema overview")

r.run(
    "1. Tables and row counts",
    """
    SELECT s.name AS [schema], t.name AS [table], SUM(p.rows) AS row_count
    FROM sys.tables t
    JOIN sys.schemas s    ON s.schema_id = t.schema_id
    JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
    GROUP BY s.name, t.name
    ORDER BY row_count DESC
    """,
    "tables_row_counts",
    max_rows=80,
)

r.run(
    "2. Tables per schema",
    """
    SELECT s.name AS [schema], COUNT(*) AS tables
    FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
    GROUP BY s.name ORDER BY tables DESC
    """,
    "tables_per_schema",
)

r.run(
    "3. Columns of every table (full list saved to CSV)",
    """
    SELECT TABLE_SCHEMA AS [schema], TABLE_NAME AS [table], ORDINAL_POSITION AS pos,
           COLUMN_NAME AS [column], DATA_TYPE AS data_type,
           CHARACTER_MAXIMUM_LENGTH AS max_len, IS_NULLABLE AS nullable
    FROM INFORMATION_SCHEMA.COLUMNS
    ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
    """,
    "all_columns",
    max_rows=15,
)

r.run(
    "4. Primary keys",
    """
    SELECT s.name AS [schema], t.name AS [table], c.name AS pk_column, ic.key_ordinal
    FROM sys.indexes i
    JOIN sys.tables t ON t.object_id = i.object_id
    JOIN sys.schemas s ON s.schema_id = t.schema_id
    JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
    JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
    WHERE i.is_primary_key = 1
    ORDER BY s.name, t.name, ic.key_ordinal
    """,
    "primary_keys",
    max_rows=15,
)

r.run(
    "5. Foreign keys (the relationships between tables)",
    """
    SELECT fk.name AS fk_name,
           ps.name + '.' + pt.name AS child_table,  pc.name AS child_column,
           rs.name + '.' + rt.name AS parent_table, rc.name AS parent_column
    FROM sys.foreign_keys fk
    JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
    JOIN sys.tables pt  ON pt.object_id = fkc.parent_object_id
    JOIN sys.schemas ps ON ps.schema_id = pt.schema_id
    JOIN sys.columns pc ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
    JOIN sys.tables rt  ON rt.object_id = fkc.referenced_object_id
    JOIN sys.schemas rs ON rs.schema_id = rt.schema_id
    JOIN sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
    ORDER BY child_table, fk.name
    """,
    "foreign_keys",
    max_rows=25,
)

r.run(
    "6. Foreign keys around the sales tables",
    """
    SELECT ps.name + '.' + pt.name AS child_table, pc.name AS child_column,
           rs.name + '.' + rt.name AS parent_table, rc.name AS parent_column
    FROM sys.foreign_keys fk
    JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
    JOIN sys.tables pt  ON pt.object_id = fkc.parent_object_id
    JOIN sys.schemas ps ON ps.schema_id = pt.schema_id
    JOIN sys.columns pc ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
    JOIN sys.tables rt  ON rt.object_id = fkc.referenced_object_id
    JOIN sys.schemas rs ON rs.schema_id = rt.schema_id
    JOIN sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
    WHERE pt.name IN ('SalesOrderHeader', 'SalesOrderDetail', 'Customer')
    ORDER BY child_table, child_column
    """,
    "foreign_keys_sales_core",
)

r.run(
    "7. Views",
    """
    SELECT s.name AS [schema], v.name AS [view]
    FROM sys.views v JOIN sys.schemas s ON s.schema_id = v.schema_id
    ORDER BY s.name, v.name
    """,
    "views",
    max_rows=60,
)

r.run(
    "8. Computed columns (e.g. LineTotal, TotalDue) and their formulas",
    """
    SELECT s.name AS [schema], t.name AS [table], c.name AS [column], cc.definition
    FROM sys.computed_columns cc
    JOIN sys.tables t ON t.object_id = cc.object_id
    JOIN sys.schemas s ON s.schema_id = t.schema_id
    JOIN sys.columns c ON c.object_id = cc.object_id AND c.column_id = cc.column_id
    ORDER BY s.name, t.name, c.name
    """,
    "computed_columns",
    max_rows=40,
)

dd = r.run(
    "9. DATA DICTIONARY from the database's own MS_Description (answers: what does Status mean?)",
    """
    SELECT s.name AS [schema], t.name AS [table], c.name AS [column],
           CAST(ep.value AS nvarchar(1000)) AS description
    FROM sys.extended_properties ep
    JOIN sys.tables t  ON t.object_id = ep.major_id
    JOIN sys.schemas s ON s.schema_id = t.schema_id
    JOIN sys.columns c ON c.object_id = ep.major_id AND c.column_id = ep.minor_id
    WHERE ep.class = 1 AND ep.name = 'MS_Description' AND ep.minor_id > 0
    ORDER BY s.name, t.name, c.column_id
    """,
    "data_dictionary",
    max_rows=10,
)
if dd.empty:
    r.note("No MS_Description found in this restore; document column meanings manually in the README.")
else:
    key_cols = ["Status", "OnlineOrderFlag", "SubTotal", "TaxAmt", "Freight", "TotalDue", "LineTotal",
                "UnitPriceDiscount", "SalesPersonID", "TerritoryID", "SpecialOfferID"]
    sales = dd[(dd["schema"] == "Sales") & (dd["table"].isin(["SalesOrderHeader", "SalesOrderDetail"]))
               & (dd["column"].isin(key_cols))]
    r.show("9b. Key sales columns described", sales, "dictionary_key_sales_columns", max_rows=40)

r.run(
    "10. Tables with Return / Refund in the name (expected: none)",
    "SELECT s.name AS [schema], t.name AS [table] FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id "
    "WHERE t.name LIKE '%Return%' OR t.name LIKE '%Refund%'",
    "return_refund_tables",
)

# ---- Sample rows of the most important tables ----------------------------------------
for table in ["Sales.SalesOrderHeader", "Sales.SalesOrderDetail", "Sales.Customer", "Sales.Store",
              "Production.Product", "Production.ProductSubcategory", "Production.ProductCategory",
              "Sales.SalesTerritory"]:
    r.run(f"11. Sample rows: {table}", f"SELECT TOP 5 * FROM {table}", None)

# ---- SQLAlchemy reflection demo: read column metadata without writing SQL --------------
insp = inspect(get_engine())
cols = insp.get_columns("SalesOrderHeader", schema="Sales")
refl = pd.DataFrame(
    [{"column": c["name"], "type": str(c["type"]), "nullable": c["nullable"]} for c in cols]
)
r.show("12. SQLAlchemy reflection of Sales.SalesOrderHeader (inspect(engine).get_columns)", refl,
       "reflection_salesorderheader", max_rows=40)

r.finish()
