"""NN_topic - short description of what this script explores."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.db import Report  # noqa: E402

r = Report(__file__, "TITLE OF THE EXPLORATION")

r.run(
    "1. Example question",
    """
    SELECT YEAR(OrderDate) AS yr, COUNT(*) AS orders
    FROM Sales.SalesOrderHeader
    GROUP BY YEAR(OrderDate)
    ORDER BY yr
    """,
    "example_orders_per_year",
)

r.finish()
