"""
common/db.py
============
Shared helpers used by EVERY exploration script in this repo.

* get_engine()  -> one SQLAlchemy engine configured from the .env file
* query()       -> run a read-only SQL statement and return a pandas DataFrame
* scalar()      -> run SQL that returns a single value
* Report        -> prints results nicely AND saves them (CSV per query + report.txt)

Usage inside a script:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.db import Report

    r = Report(__file__, "My exploration title")
    df = r.run("1. Orders per year", "SELECT YEAR(OrderDate) yr, COUNT(*) n FROM Sales.SalesOrderHeader GROUP BY YEAR(OrderDate)", "orders_per_year")
    r.finish()
"""
from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

try:  # python-dotenv is optional: env vars can also be set in the shell
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:  # pragma: no cover
    pass

_ENGINE: Engine | None = None


# --------------------------------------------------------------------------- #
# Connection
# --------------------------------------------------------------------------- #
def get_engine() -> Engine:
    """Create (once) and return the SQLAlchemy engine for SQL Server."""
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    server = os.getenv("DB_SERVER", "localhost")
    database = os.getenv("DB_NAME", "AdventureWorks2025")
    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    trusted = os.getenv("DB_TRUSTED", "yes").strip().lower() in ("yes", "true", "1")

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
        "TrustServerCertificate=yes",  # local SQL Server uses a self-signed cert
    ]
    if trusted:
        parts.append("Trusted_Connection=yes")  # Windows authentication
    else:
        parts.append(f"UID={os.getenv('DB_USER', '')}")
        parts.append(f"PWD={{{os.getenv('DB_PASSWORD', '')}}}")

    url = "mssql+pyodbc:///?odbc_connect=" + quote_plus(";".join(parts))
    _ENGINE = create_engine(url)
    return _ENGINE


# --------------------------------------------------------------------------- #
# Query helpers
# --------------------------------------------------------------------------- #
def _assert_read_only(sql: str) -> None:
    """The repo is for EXPLORATION only: allow SELECT / WITH statements."""
    first = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
    if first not in ("SELECT", "WITH"):
        raise ValueError("Only read-only SELECT / WITH statements are allowed in this repo.")


def _decimals_to_float(df: pd.DataFrame) -> pd.DataFrame:
    """SQL Server DECIMAL/MONEY arrive as Decimal objects -> convert to float."""
    for col in df.columns:
        if df[col].dtype == object:
            sample = df[col].dropna()
            if not sample.empty and isinstance(sample.iloc[0], Decimal):
                df[col] = df[col].astype(float)
    return df


def query(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Run a read-only query and return a DataFrame. Use :name for parameters."""
    _assert_read_only(sql)
    with get_engine().connect() as conn:
        df = pd.read_sql(text(sql), conn, params=params)
    return _decimals_to_float(df)


def scalar(sql: str, params: dict[str, Any] | None = None) -> Any:
    """Run a query that returns one value (first column of first row)."""
    df = query(sql, params)
    return None if df.empty else df.iloc[0, 0]


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
class Report:
    """Prints sections/tables to the console and stores them next to the script.

    Output goes to  <script folder>/outputs/
        report.txt        full text of everything printed
        <name>.csv        one CSV per query that was given a `name`
    """

    def __init__(self, script_file: str, title: str):
        self.dir = Path(script_file).resolve().parent
        self.out = self.dir / "outputs"
        self.out.mkdir(exist_ok=True)
        self.lines: list[str] = []
        self._emit("#" * 90)
        self._emit(f"{title}")
        self._emit(f"folder: {self.dir.name}   |   run at: {datetime.now():%Y-%m-%d %H:%M}")
        self._emit("#" * 90)

    # -- low level ---------------------------------------------------------- #
    def _emit(self, line: str = "") -> None:
        print(line)
        self.lines.append(line)

    def section(self, title: str) -> None:
        self._emit("")
        self._emit("=" * 90)
        self._emit(title)
        self._emit("=" * 90)

    def note(self, message: str) -> None:
        self._emit(f"NOTE: {message}")

    # -- tables ------------------------------------------------------------- #
    def show(self, title: str, df: pd.DataFrame, name: str | None = None, max_rows: int = 30) -> pd.DataFrame:
        """Print a DataFrame you already have (e.g. computed with pandas)."""
        self.section(title)
        if df is None or df.empty:
            self._emit("(no rows)")
            return df
        pd.set_option("display.width", 200)
        pd.set_option("display.max_columns", 50)
        self._emit(df.head(max_rows).to_string(index=False))
        if len(df) > max_rows:
            self._emit(f"... {len(df):,} rows in total (showing {max_rows})")
        if name:
            df.to_csv(self.out / f"{name}.csv", index=False, encoding="utf-8-sig")
            self._emit(f"[saved] outputs/{name}.csv")
        return df

    def run(
        self,
        title: str,
        sql: str,
        name: str | None = None,
        params: dict[str, Any] | None = None,
        max_rows: int = 30,
    ) -> pd.DataFrame:
        """Run SQL, print the result, save it as CSV when `name` is given.

        A failing query never stops the script: the error is logged and an empty
        DataFrame is returned, so one wrong column name does not hide other results.
        """
        try:
            df = query(sql, params)
        except Exception as exc:  # noqa: BLE001
            self.section(title)
            self._emit(f"[ERROR] {type(exc).__name__}: {str(exc)[:500]}")
            return pd.DataFrame()
        return self.show(title, df, name, max_rows)

    def finish(self) -> None:
        (self.out / "report.txt").write_text("\n".join(self.lines), encoding="utf-8")
        print(f"\nDone. Report saved to {self.out / 'report.txt'}")
