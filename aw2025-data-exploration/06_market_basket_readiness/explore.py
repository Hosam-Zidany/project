"""06_market_basket_readiness - basket structure + quick Support / Confidence / Lift for pairs.

This is EXPLORATION (is the data suitable? what do we expect?), not the final algorithm.
Pairs are counted in SQL, metrics are computed in pandas.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.db import Report, query  # noqa: E402

r = Report(__file__, "Market Basket readiness")

MIN_PAIR_ORDERS = 30  # ignore pairs seen in fewer orders (noise) - change and re-run to experiment
SEGMENTS = {
    "all": "",
    "individual": "WHERE h.OnlineOrderFlag = 1",
    "store": "WHERE h.OnlineOrderFlag = 0",
}

# ---- 1. Basket structure ----------------------------------------------------------------
per_order = query(
    """
    SELECT d.SalesOrderID, h.OnlineOrderFlag, COUNT(*) AS n_lines, COUNT(DISTINCT d.ProductID) AS n_products
    FROM Sales.SalesOrderDetail d JOIN Sales.SalesOrderHeader h ON h.SalesOrderID = d.SalesOrderID
    GROUP BY d.SalesOrderID, h.OnlineOrderFlag
    """
)
per_order["segment"] = per_order["OnlineOrderFlag"].map({True: "individual", False: "store", 1: "individual", 0: "store"})

dist = per_order.groupby("n_products").size().reset_index(name="orders")
dist["pct"] = (100 * dist["orders"] / dist["orders"].sum()).round(2)
r.show("1. Distinct products per order - distribution (all orders)", dist, "basket_size_distribution", max_rows=15)

stats = per_order.groupby("segment")["n_products"].describe(percentiles=[0.5, 0.9, 0.99]).reset_index()
r.show("2. Basket size statistics by segment", stats, "basket_size_by_segment")

dup = per_order.assign(has_duplicate_product_lines=per_order["n_lines"] > per_order["n_products"]) \
    .groupby("segment")["has_duplicate_product_lines"].agg(["sum", "count"]).reset_index()
dup.columns = ["segment", "orders_with_repeated_product_lines", "orders"]
r.show("3. Orders where the SAME product appears on more than one line (must be de-duplicated in a basket)",
       dup, "duplicate_product_lines")

big = pd.DataFrame({
    "threshold": [10, 20, 30, 50],
    "orders_with_more_products": [int((per_order["n_products"] > t).sum()) for t in [10, 20, 30, 50]],
})
r.show("4. Very large baskets (decide how to treat them: cap, split, or exclude)", big, "large_baskets")

# ---- 2. Item support + pair rules ---------------------------------------------------------
names = query("SELECT ProductID AS item, Name AS item_name FROM Production.Product")
names["item"] = names["item"].astype(str)


def pair_analysis(label: str, basket_cte: str, with_names: bool) -> None:
    """basket_cte must define b(SalesOrderID, item) with DISTINCT rows."""
    n_orders = int(query(f"{basket_cte} SELECT COUNT(DISTINCT SalesOrderID) AS n FROM b").iloc[0, 0])
    items = query(f"{basket_cte} SELECT item, COUNT(*) AS n FROM b GROUP BY item")
    items["item"] = items["item"].astype(str)
    pairs = query(
        f"""{basket_cte}
        SELECT a.item AS item_1, c.item AS item_2, COUNT(*) AS pair_orders
        FROM b a JOIN b c ON a.SalesOrderID = c.SalesOrderID AND a.item < c.item
        GROUP BY a.item, c.item HAVING COUNT(*) >= :min_pairs
        """,
        {"min_pairs": MIN_PAIR_ORDERS},
    )
    if pairs.empty:
        r.show(f"[{label}] pairs", pairs)
        return
    pairs["item_1"] = pairs["item_1"].astype(str)
    pairs["item_2"] = pairs["item_2"].astype(str)
    cnt = items.set_index("item")["n"]
    pairs["support"] = pairs["pair_orders"] / n_orders
    pairs["conf_1_to_2"] = pairs["pair_orders"] / pairs["item_1"].map(cnt)
    pairs["conf_2_to_1"] = pairs["pair_orders"] / pairs["item_2"].map(cnt)
    pairs["lift"] = pairs["support"] / ((pairs["item_1"].map(cnt) / n_orders) * (pairs["item_2"].map(cnt) / n_orders))
    if with_names:
        pairs = pairs.merge(names.rename(columns={"item": "item_1", "item_name": "name_1"}), on="item_1", how="left")
        pairs = pairs.merge(names.rename(columns={"item": "item_2", "item_name": "name_2"}), on="item_2", how="left")
    r.note(f"[{label}] {n_orders:,} baskets, {len(items):,} distinct items, {len(pairs):,} pairs with >= {MIN_PAIR_ORDERS} orders")
    cols = [c for c in ["item_1", "name_1", "item_2", "name_2", "pair_orders", "support",
                        "conf_1_to_2", "conf_2_to_1", "lift"] if c in pairs.columns]
    slug = label.replace(" ", "_")
    r.show(f"[{label}] top 20 pairs by number of orders", pairs.sort_values("pair_orders", ascending=False)[cols],
           f"pairs_{slug}_top_count", max_rows=20)
    r.show(f"[{label}] top 20 pairs by lift (min {MIN_PAIR_ORDERS} orders)", pairs.sort_values("lift", ascending=False)[cols],
           f"pairs_{slug}_top_lift", max_rows=20)


for seg, where in SEGMENTS.items():
    product_cte = f"""WITH b AS (
        SELECT DISTINCT d.SalesOrderID, d.ProductID AS item
        FROM Sales.SalesOrderDetail d JOIN Sales.SalesOrderHeader h ON h.SalesOrderID = d.SalesOrderID {where})"""
    pair_analysis(f"product level - {seg}", product_cte, with_names=True)

for seg, where in SEGMENTS.items():
    category_cte = f"""WITH b AS (
        SELECT DISTINCT d.SalesOrderID, pc.Name AS item
        FROM Sales.SalesOrderDetail d
        JOIN Sales.SalesOrderHeader h ON h.SalesOrderID = d.SalesOrderID
        JOIN Production.Product p ON p.ProductID = d.ProductID
        JOIN Production.ProductSubcategory ps ON ps.ProductSubcategoryID = p.ProductSubcategoryID
        JOIN Production.ProductCategory pc ON pc.ProductCategoryID = ps.ProductCategoryID {where})"""
    pair_analysis(f"category level - {seg}", category_cte, with_names=False)

r.finish()
