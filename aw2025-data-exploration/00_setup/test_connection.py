"""Quick connection test:  python 00_setup/test_connection.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.db import query, scalar  # noqa: E402

try:
    print("SQL Server :", str(scalar("SELECT @@VERSION")).splitlines()[0])
    print("Database   :", scalar("SELECT DB_NAME()"))
    print("Orders     :", f"{scalar('SELECT COUNT(*) FROM Sales.SalesOrderHeader'):,}")
    print("Tables     :", scalar("SELECT COUNT(*) FROM sys.tables"))
    print("\nConnection OK")
except Exception as exc:  # noqa: BLE001
    print("Connection FAILED:", type(exc).__name__)
    print(str(exc)[:600])
    print("\nSee 00_setup/README.md -> common errors")
    raise SystemExit(1)
