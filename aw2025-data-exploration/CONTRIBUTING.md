# دليل المساهمة

## القواعد

1. **مجلد لكل موضوع:** الاسم `NN_topic_name` (رقمان ثم snake_case بالإنجليزية).
2. **كل مجلد = ملفان على الأقل:** `README.md` (بالعربية مع المصطلحات الإنجليزية) و `explore.py`.
3. **الاتصال بالقاعدة فقط عبر `common/db.py`.** لا تكتب كلمات مرور أو سلاسل اتصال داخل السكربتات. الإعدادات في `.env` (غير مرفوع).
4. **قراءة فقط:** `query()` يرفض أي شيء غير `SELECT`/`WITH`.
5. **كل استعلام له عنوان ورقم واسم ملف:** `r.run("3. Revenue by year", sql, "revenue_by_year")`.
6. **المقاييس المشتركة** (إيراد، AOV، نوع العميل...) تُعرَّف في `common/metrics.py` ولا تُعاد كتابتها بأشكال مختلفة.
7. **الفخ الأول:** عند ربط Header مع Detail اسأل نفسك: هل أضاعف الطلبات أو المبالغ؟ استخدم `COUNT(DISTINCT ...)` أو اجمع كل مستوى على حدة.
8. **لا نتائج بدون تحقق:** كل رقم تضعه في README أو في `findings_log.md` يجب أن يأتي من `outputs/report.txt`.
9. **اكتب ما لا تعرفه:** إن ظهر شيء غريب أضفه إلى `docs/open_questions.md` بدل تفسيره بالتخمين.

## إضافة مجلد جديد

```bash
cp -r _template 13_my_topic          # Windows: xcopy /E /I _template 13_my_topic
# عدّل 13_my_topic/README.md و 13_my_topic/explore.py
python 13_my_topic/explore.py
git add 13_my_topic && git commit -m "explore: my topic"
```

## هيكل `explore.py` المعتمد

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.db import Report

r = Report(__file__, "Title")
r.run("1. Question", "SELECT ...", "file_name")
# تحليل إضافي بـ pandas:  r.show("2. Title", df, "name")
r.finish()
```

## سير العمل على Git

- فرع لكل مساهمة: `git checkout -b explore/<topic>`.
- ارفع `README.md` و `explore.py` و `outputs/report.txt`. ملفات CSV تتجاهلها `.gitignore`.
- راجع زميلاً واحداً على الأقل قبل الدمج في `main`.
- المشرفون يُضافون كـ **Read** فقط.

## قالب رسالة Commit

`explore(<folder>): <what you checked>` — مثال: `explore(05_time_coverage): identify 2024 order jump source`
