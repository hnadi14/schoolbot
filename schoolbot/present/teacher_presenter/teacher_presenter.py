import matplotlib

from schoolbot.services.open_ai_response import get_chatbot_response

matplotlib.use('Agg')
import numpy as np
import logging

from schoolbot.services.report_service import (
    get_student_score,
)

# ------------------ Logging: فقط خطاها ------------------
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
# کاهش لاگ سطح پایین از کتابخانه‌های خارجی
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("balethon").setLevel(logging.WARNING)

teacher_states = {}  # keyed by teacher's DB id (user_id)

# # 🎨 ست کردن فونت پیش‌فرض فارسی (در صورت نصب بودن روی سیستم)
# rcParams['font.family'] = 'Tahoma'  # می‌تونی "Vazir" یا "IRANSans" هم بذاری

# کتابخانه‌های فارسی‌سازی را اینجا import می‌کنیم
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    print("WARNING: 'arabic_reshaper' or 'python-bidi' not found. Farsi text will not be displayed correctly.")
    print("Install them using: pip install arabic_reshaper python-bidi")


    # توابع جایگزین تعریف می‌کنیم تا برنامه از کار نیفتد
    def get_display(text):
        return text


    def arabic_reshaper_reshape(text):
        return text
else:
    # اگر ایمپورت موفق بود، تابع اصلی را تعریف می‌کنیم
    def arabic_reshaper_reshape(text):
        return arabic_reshaper.reshape(text)


# ----------------- توابع کمکی -----------------
# فراخوانی نمرات یک دانش اموز با در یک درس و در یک دوره
def _safe_prev_score_lookup(student_id, subject_id, report_period_id):
    try:
        prev = get_student_score(student_id, subject_id, report_period_id)
    except Exception:
        logging.exception("❌ خطا در _safe_prev_score_lookup هنگام فراخوانی get_student_score")
        return None
    if prev is None:
        return None
    if isinstance(prev, dict):
        return {"score": prev.get("score"), "description": prev.get("description")}
    if isinstance(prev, (tuple, list)):
        if len(prev) == 2:
            return {"score": prev[0], "description": prev[1]}
        if len(prev) == 3:
            return {"score": prev[1], "description": prev[2]}
    return None


# گزارش کلاس در یک درس
def summarize_class(subject_name, students_scores, class_name):
    """
    محاسبه آمار کلاس با استفاده از NumPy برای حداکثر سرعت.
    """
    try:
        # استخراج نمرات معتبر و تبدیل به آرایه NumPy تنها یک بار
        scores_array = np.array([s["score"] for s in students_scores if s["score"] is not None], dtype=float)

        if scores_array.size == 0:
            return f"📊 برای درس {subject_name} هیچ نمره‌ای ثبت نشده است.", []

        n = scores_array.size

        # --- اجرای تمام محاسبات با NumPy ---
        avg = np.mean(scores_array)
        std_dev = np.std(scores_array)
        min_score, q1, median, q3, max_score = np.percentile(scores_array, [0, 25, 50, 75, 100])

        # شمارش دسته‌ها به صورت برداری (بسیار سریع‌تر از list comprehension)
        below_10 = np.count_nonzero(scores_array < 10)
        above_15 = np.count_nonzero(scores_array >= 15)
        between_10_15 = n - below_10 - above_15

        # پیدا کردن مد (پرتکرارترین نمره)
        vals, counts = np.unique(scores_array, return_counts=True)
        index = np.argmax(counts)
        mode_score, mode_freq = vals[index], counts[index]

        summary_msg = (
            f"📊 خلاصه وضعیت کلاس {subject_name} {class_name}:\n"
            f"📊 تعداد کل دانش‌آموزان کلاس: {len(students_scores)}\n"
            f"👥 تعداد دانش‌آموزان با نمره: {n}\n"
            f"📈 میانگin: {avg:.2f}\n"  # استفاده از f-string برای گرد کردن
            f"📉 انحراف معیار: {std_dev:.2f}\n"
            f"🔽 کمترین نمره: {min_score:.2f}\n"
            f"🔼 بیشترین نمره: {max_score:.2f}\n"
            f"➗ میانه: {median:.2f}\n"
            f"📐 چارک اول: {q1:.2f}\n"
            f"📐 چارک سوم: {q3:.2f}\n"
            f"🎯 پرتکرارترین نمره: {mode_score} (تکرار {mode_freq} بار)\n"
            f"⚠️ تعداد زیر ۱۰: {below_10}\n"
            f"〰️ تعداد بین ۱۰ تا ۱۵: {between_10_15}\n"
            f"🏆 تعداد ۱۵ و بالاتر: {above_15}"
        )

        # فراخوانی OpenAI بدون تغییر باقی می‌ماند
        response = get_chatbot_response(role="teacher", user_question=" " + summary_msg)
        if "_@_error_@_" not in response:
            summary_msg += f"\n\n{'━' * 20}\n 🧠  {response}"

        return summary_msg, scores_array.tolist()  # خروجی همچنان لیست باشد

    except Exception:
        logging.exception("❌ خطا در summarize_class_numpy")
        return f"❌ خطا در محاسبه خلاصه وضعیت کلاس {subject_name}.", []
