# 09 — Data Quality (جودة البيانات)

## الهدف
التأكد من أن البيانات صالحة للتحليل، وتوثيق كل ما يخالف التوقعات قبل أن يتحول إلى خطأ في Dashboard أو Agent أو الخوارزميات.

## الأسئلة التي يجيب عنها
- أي الأعمدة فيها `NULL` وبأي نسبة؟ (مثلاً `SalesPersonID` في طلبات الأفراد)
- هل توجد سجلات يتيمة (Detail بلا Header، Header بلا Detail، منتج غير موجود...)؟
- هل `SubTotal` = مجموع `LineTotal` لكل طلب؟ وهل `TotalDue = SubTotal + TaxAmt + Freight`؟
- هل `LineTotal` يطابق `OrderQty × UnitPrice × (1 − Discount)`؟
- هل توجد كميات/أسعار سالبة أو صفرية، أو تواريخ شحن قبل الطلب؟
- هل `OnlineOrderFlag` متسق مع نوع العميل ووجود مندوب مبيعات؟
- **كيف يحدث تضاعف المبالغ بعد ربط Header مع Detail؟** (الاستعلام 12 يعرض الخطأ عملياً)

## ماذا يفعل `explore.py`
12 فحصاً، مخرجاتها `orphans.csv`, `subtotal_vs_linetotal.csv`, `totaldue_formula.csv`, `linetotal_formula.csv`, `channel_consistency.csv`, `double_counting_demo.csv`, و`nulls_<table>.csv` لأربعة جداول أساسية (توليد آلي عبر SQLAlchemy reflection).

## كيف نقرأ النتائج
- كل فحص "يجب أن يكون صفراً" وجدتم فيه غير ذلك → سجّلوه في `docs/findings_log.md` وحدّدوا أثره.
- `mismatched_orders` صغير جداً (فروق تقريب) مقبول إن كان `max_abs_diff` بالسنتات.
- يعالج هذا المجلد جزءاً من السؤال 3 و4 و10 في `docs/open_questions.md`.

## فخاخ
- فحص `GETDATE()` يقارن مع تاريخ الجهاز اليوم؛ بيانات 2025 ليست "مستقبلاً" الآن، لكن الفحص يعتمد على ساعة الجهاز.
- لا نصلح البيانات هنا: نكتشف ونوثّق فقط.

## ارتباطه بالمسارات
الجميع، خاصة Agent (قابلية التحقق من الإجابات) وDashboard (دقة المؤشرات).
