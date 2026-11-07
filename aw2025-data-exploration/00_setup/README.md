# 00 — الإعداد (Setup)

## الهدف
الحصول على قاعدة `AdventureWorks2025` تعمل على SQL Server، والاتصال بها من بايثون عبر SQLAlchemy.

## 1) متطلبات
- SQL Server (Developer / Express كافٍ) + SSMS أو Azure Data Studio.
- **ODBC Driver 18 for SQL Server** (أو 17 — غيّر `DB_DRIVER` في `.env`).
- Python 3.10+.

## 2) استعادة ملف `.bak`
الملف ليس CSV؛ هو نسخة احتياطية يجب استعادتها.

**من SSMS:** Databases ← Restore Database… ← Device ← اختر ملف `.bak` ← OK.

**أو بـ T-SQL** (الخطوة الأولى تُظهر أسماء الملفات المنطقية Logical Names):

```sql
RESTORE FILELISTONLY FROM DISK = N'C:\Backups\AdventureWorks2025.bak';

RESTORE DATABASE AdventureWorks2025
FROM DISK = N'C:\Backups\AdventureWorks2025.bak'
WITH MOVE N'<LogicalName_data>' TO N'C:\SQLData\AdventureWorks2025.mdf',
     MOVE N'<LogicalName_log>'  TO N'C:\SQLData\AdventureWorks2025_log.ldf',
     REPLACE, STATS = 10;
```

استبدل `<LogicalName_data>` و`<LogicalName_log>` بما أظهرته الخطوة الأولى.

## 3) إعداد الاتصال
انسخ `.env.example` إلى `.env` وعدّل:

| الحالة | القيمة |
|---|---|
| Instance افتراضي | `DB_SERVER=localhost` |
| SQL Express | `DB_SERVER=localhost\SQLEXPRESS` |
| منفذ محدد | `DB_SERVER=127.0.0.1,1433` |
| Windows Auth | `DB_TRUSTED=yes` |
| SQL Auth | `DB_TRUSTED=no` + `DB_USER` + `DB_PASSWORD` |

## 4) الاختبار
```bash
python 00_setup/test_connection.py
```
المتوقع: إصدار SQL Server، اسم القاعدة، وعدد الطلبات (31,465 في نسختنا).

## 5) أخطاء شائعة
| الخطأ | الحل |
|---|---|
| `Data source name not found` | الـ ODBC Driver غير مثبّت أو الاسم في `DB_DRIVER` خاطئ |
| `Login failed` | تأكد من نوع المصادقة؛ فعّل SQL Server and Windows Authentication mode إن لزم |
| `certificate verify failed` | الكود يضع `TrustServerCertificate=yes` مسبقاً؛ تأكد أنك تستخدم `common/db.py` |
| `Cannot open database` | لم تُستعد القاعدة بعد، أو الاسم في `DB_NAME` مختلف |
| `TCP provider timeout` | فعّل TCP/IP في SQL Server Configuration Manager وشغّل SQL Browser |

## 6) ملاحظة للفريق
اتفقوا على **اسم قاعدة واحد** (`AdventureWorks2025`) حتى لا تختلف الاستعلامات بين الأعضاء.
