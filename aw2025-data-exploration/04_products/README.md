# 04 — Products (المنتجات)

## الهدف
فهم الكتالوج (504 منتجاً) وما يُباع منه فعلاً (266 منتجاً)، وتوزيع الإيراد على الفئات — مرجع Dashboard وMarket Basket.

## الأسئلة التي يجيب عنها
- كم فئة وفئة فرعية ومنتج؟ وهل لبعض المنتجات فئة فرعية `NULL`؟
- أي الفئات أعلى إيراداً (Bikes ≈ 94.7M) وأيها أعلى عدد بنود (Accessories ≈ 41K بنداً بإيراد منخفض)؟
- ما المنتجات الأكثر إيراداً، والأكثر ظهوراً في الطلبات (أساس Support)؟
- ما المنتجات التي لم تُبَع إطلاقاً ولماذا (مكونات؟ مواد خام؟ غير مكتملة؟)
- ما الهامش التقريبي لكل فئة؟
- هل تغيّرت أسعار البيع للمنتج نفسه؟ متى بدأ بيع كل منتج؟
- كيف يختلف مزيج الفئات بين Individual وStore؟

## ماذا يفعل `explore.py`
13 استعلاماً (انظر العناوين المرقّمة داخل السكربت). أهم الملفات: `sales_by_category.csv`, `top_products_revenue.csv`, `top_products_orders.csv`, `never_sold_products.csv`, `margin_by_category.csv`, `category_revenue_by_year.csv`.

## فخاخ
- **الهامش تقريبي:** يستخدم `StandardCost` الحالي، بينما توجد `ProductCostHistory` للتكلفة التاريخية. لا تعرضوه في Dashboard كحقيقة قبل التحقق.
- **منتج بلا فئة فرعية** يُستبعد من أي تحليل Category باستخدام `INNER JOIN`؛ استخدمنا `LEFT JOIN` لنرى حجم المشكلة.
- **"منتج مباع" ≠ "منتج نشط":** مراجعة `SellEndDate` و`FinishedGoodsFlag`.
- `COUNT(DISTINCT d.SalesOrderID)` لعدد الطلبات التي تحوي المنتج، و`COUNT(*)` لعدد البنود؛ لا تخلطوهما.

## أسئلة مفتوحة
- السؤال 12 في `docs/open_questions.md`.

## ارتباطه بالمسارات
Dashboard (تحليل المنتج والفئة)، Market Basket (اختيار مستوى Product أم Category وتحديد Min Support)، Agent.
