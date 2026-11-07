# 12 — Metric Definitions (تعريف المقاييس)

## الهدف
تعريف واحد لكل مقياس يظهر في أكثر من مكوّن (مبدأ العمل المشترك في دليل المشروع)، والتحقق الآلي من أن أرقام قاعدتنا تطابق التقرير الأول.

## القاعدة
> أي مقياس يستخدمه Dashboard أو Agent أو أي تحليل، يُعرَّف **مرة واحدة** في `common/metrics.py`، ويستورده الجميع. لا نعيد كتابة SQL مختلف لنفس الرقم.

## جدول التعريفات المعتمدة (مبدئياً)
| المقياس | التعريف | مستوى البيانات |
|---|---|---|
| `orders` | `COUNT(*)` من `SalesOrderHeader` | Order |
| `customers` | `COUNT(DISTINCT CustomerID)` من `SalesOrderHeader` | Order |
| `order_lines` | `COUNT(*)` من `SalesOrderDetail` | Line |
| `units_sold` | `SUM(OrderQty)` | Line |
| `products_sold` | `COUNT(DISTINCT ProductID)` في `SalesOrderDetail` | Line |
| **`revenue`** | `SUM(LineTotal)` ≡ `SUM(SubTotal)` — **قبل الضريبة والشحن** | Line / Order |
| `total_due` | `SUM(TotalDue)` = SubTotal + TaxAmt + Freight — **ليس إيراداً** | Order |
| `avg_order_value` | `AVG(SubTotal)` لكل طلب | Order |
| `avg_products_per_order` | متوسط `COUNT(DISTINCT ProductID)` لكل طلب | Order |
| `repeat_customer_rate` | عملاء لديهم 2+ طلبات ÷ كل العملاء الذين لديهم طلب | Order |
| `customer_type` | `OnlineOrderFlag = 1` ⇒ Individual، `0` ⇒ Store | Order |

> هذه تعريفات **مقترحة** من تقرير الاستكشاف: تُعتمد رسمياً بعد موافقة الفريق وحسم السؤال 4 في `docs/open_questions.md`.

## ماذا يفعل `explore.py`
1. يشغّل كل KPI من `common/metrics.py` ويقارنه بالقيم المتوقعة من التقرير الأول: `PASS` أو `MISMATCH`.
2. يعرض العلاقة بين `LineTotal` و`SubTotal` و`TotalDue` (الفرق = ضريبة + شحن).
3. يعطي KPIs سنوية بنفس التعريفات لتغذية Dashboard.

الملفات: `kpi_values.csv`, `money_field_relationships.csv`, `kpi_by_year.csv`.

## كيف نضيف مقياساً جديداً
1. أضف مدخلاً في `KPIS` داخل `common/metrics.py` (وصف + SQL يعيد قيمة واحدة).
2. شغّل `python 12_metric_definitions/explore.py` وتأكد أن الرقم منطقي.
3. وثّق التعريف في الجدول أعلاه.

## فخاخ
- `MISMATCH` يعني أن نسخة القاعدة عندكم تختلف عن التي استُخرج منها التقرير الأول: أبلغوا الفريق قبل متابعة العمل.
- لا تجمعوا `SubTotal` بعد ربط Header مع Detail (يتضاعف): انظر `09_data_quality` الاستعلام 12.

## ارتباطه بالمسارات
الجميع: Dashboard وAgent يجب أن يعيدا نفس الأرقام لنفس السؤال.
