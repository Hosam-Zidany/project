"""11_person_hr - people, geography, employees, sales staff, contact coverage."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.db import Report  # noqa: E402

r = Report(__file__, "Person, geography and HR exploration")

r.run(
    "1. Person types (IN individual customer, SC store contact, EM employee, SP sales person, VC vendor contact, GC general contact)",
    "SELECT PersonType, COUNT(*) AS people FROM Person.Person GROUP BY PersonType ORDER BY people DESC",
    "person_types",
)

r.run(
    "2. Customers linked to a Person vs to a Store",
    """
    SELECT SUM(CASE WHEN PersonID IS NOT NULL AND StoreID IS NULL THEN 1 ELSE 0 END) AS person_only,
           SUM(CASE WHEN PersonID IS NULL AND StoreID IS NOT NULL THEN 1 ELSE 0 END) AS store_only,
           SUM(CASE WHEN PersonID IS NOT NULL AND StoreID IS NOT NULL THEN 1 ELSE 0 END) AS person_and_store,
           SUM(CASE WHEN PersonID IS NULL AND StoreID IS NULL THEN 1 ELSE 0 END) AS neither
    FROM Sales.Customer
    """,
    "customer_links",
)

r.run(
    "3. Addresses by country",
    """
    SELECT cr.Name AS country, COUNT(*) AS addresses
    FROM Person.Address a
    JOIN Person.StateProvince sp ON sp.StateProvinceID = a.StateProvinceID
    JOIN Person.CountryRegion cr ON cr.CountryRegionCode = sp.CountryRegionCode
    GROUP BY cr.Name ORDER BY addresses DESC
    """,
    "addresses_by_country",
)

r.run(
    "4. Top 20 states / provinces by addresses",
    """
    SELECT TOP 20 cr.Name AS country, sp.Name AS state_province, COUNT(*) AS addresses
    FROM Person.Address a
    JOIN Person.StateProvince sp ON sp.StateProvinceID = a.StateProvinceID
    JOIN Person.CountryRegion cr ON cr.CountryRegionCode = sp.CountryRegionCode
    GROUP BY cr.Name, sp.Name ORDER BY addresses DESC
    """,
    "addresses_by_state",
)

r.run(
    "5. Contact data coverage (people with email / phone)",
    """
    SELECT (SELECT COUNT(*) FROM Person.Person) AS people,
           (SELECT COUNT(DISTINCT BusinessEntityID) FROM Person.EmailAddress) AS with_email,
           (SELECT COUNT(DISTINCT BusinessEntityID) FROM Person.PersonPhone) AS with_phone,
           (SELECT COUNT(DISTINCT BusinessEntityID) FROM Person.BusinessEntityAddress) AS entities_with_address
    """,
    "contact_coverage",
)

r.run(
    "6. Email promotion setting (0 none, 1 AdventureWorks, 2 partners)",
    "SELECT EmailPromotion, COUNT(*) AS people FROM Person.Person GROUP BY EmailPromotion ORDER BY EmailPromotion",
    "email_promotion",
)

# ---------------- HR -------------------------------------------------------------------
r.run(
    "7. Employees: headline",
    """
    SELECT COUNT(*) AS employees, SUM(CASE WHEN CurrentFlag = 1 THEN 1 ELSE 0 END) AS current_employees,
           SUM(CASE WHEN SalariedFlag = 1 THEN 1 ELSE 0 END) AS salaried,
           MIN(HireDate) AS first_hire, MAX(HireDate) AS last_hire
    FROM HumanResources.Employee
    """,
    "employees_headline",
)

r.run(
    "8. Current employees by department",
    """
    SELECT d.GroupName, d.Name AS department, COUNT(*) AS employees
    FROM HumanResources.EmployeeDepartmentHistory edh
    JOIN HumanResources.Department d ON d.DepartmentID = edh.DepartmentID
    WHERE edh.EndDate IS NULL
    GROUP BY d.GroupName, d.Name ORDER BY employees DESC
    """,
    "employees_by_department",
)

r.run(
    "9. Top 20 job titles",
    """
    SELECT TOP 20 JobTitle, COUNT(*) AS employees FROM HumanResources.Employee
    GROUP BY JobTitle ORDER BY employees DESC
    """,
    "job_titles",
)

r.run(
    "10. Hires per year",
    "SELECT YEAR(HireDate) AS hire_year, COUNT(*) AS hires FROM HumanResources.Employee GROUP BY YEAR(HireDate) ORDER BY hire_year",
    "hires_per_year",
)

r.run(
    "11. Pay rate summary (aggregate only)",
    """
    SELECT COUNT(DISTINCT BusinessEntityID) AS employees_with_pay_history, COUNT(*) AS pay_changes,
           MIN(Rate) AS min_rate, AVG(Rate) AS avg_rate, MAX(Rate) AS max_rate
    FROM HumanResources.EmployeePayHistory
    """,
    "pay_summary",
)

# ---------------- Sales staff ------------------------------------------------------------
r.run(
    "12. Sales people: quota, bonus, YTD per territory",
    """
    SELECT TerritoryID, COUNT(*) AS sales_people, SUM(SalesQuota) AS total_quota, SUM(SalesYTD) AS sales_ytd,
           SUM(SalesLastYear) AS sales_last_year
    FROM Sales.SalesPerson GROUP BY TerritoryID ORDER BY sales_ytd DESC
    """,
    "salespeople_by_territory",
)

r.run(
    "13. Sales quota history coverage",
    """
    SELECT COUNT(*) AS quota_rows, COUNT(DISTINCT BusinessEntityID) AS sales_people,
           MIN(QuotaDate) AS first_quota, MAX(QuotaDate) AS last_quota
    FROM Sales.SalesPersonQuotaHistory
    """,
    "quota_history",
)

r.finish()
