# schoolbot/handlers/student_handler.py (✨ نسخه اصلاح‌شده با مدیریت بازگشت)

import asyncio
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

# ✨ ایمپورت‌ها بدون تغییر باقی می‌مانند
from schoolbot.services.score_service import (
    get_report_periods,
    get_school_id_by_student,
    get_student_comprehensive_report,
    get_student_performance_history
)
from schoolbot.chart.chart_student.chart_student import (
    generate_multi_subject_charts,
    generate_combined_chart,
    generate_radar_chart,
    generate_average_trend_chart
)
from schoolbot.present.student_presenter.student_presenter import (
    format_periods,
    build_report_card_message,
    build_score_history_message,
    prepare_data_for_radar_chart
)
from schoolbot.utils.keyboards import normalize_digits

# ------------------ تنظیمات اولیه ------------------
logging.basicConfig(level=logging.ERROR, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)
student_states = {}


# ------------------ توابع کمکی (بدون تغییر) ------------------
# تابع generate_and_send_all_charts بدون تغییر در اینجا قرار می‌گیرد
async def generate_and_send_all_charts(loop, client, chat_id, report_data: Dict, history_data: Dict, name: str,
                                       period_name: str):
    """
    تمام نمودارها را به صورت غیرهمزمان تولید و ارسال می‌کند.
    """
    # --- نمودار مقایسه‌ای ---
    chart_path = await loop.run_in_executor(executor, generate_combined_chart, report_data.get("scores", []), name,
                                            period_name)
    if chart_path:
        try:
            with open(chart_path, "rb") as photo:
                await client.send_photo(chat_id, photo, caption=f"📊 نمودار نمرات {name} و میانگین کلاس")
        finally:
            os.unlink(chart_path)

    all_scores = history_data.get("all_scores")
    if not all_scores:
        return

    # --- نمودار روند معدل ---
    student_avgs = history_data.get("student_period_averages", {})
    class_avgs = history_data.get("class_period_averages", {})
    trend_path = await loop.run_in_executor(executor, generate_average_trend_chart, student_avgs, name, class_avgs)
    if trend_path:
        try:
            with open(trend_path, "rb") as photo:
                await client.send_photo(chat_id, photo, caption=f"📊 نمودار پیشرفت تحصیلی {name}")
        finally:
            os.unlink(trend_path)

    # --- نمودار راداری ---
    radar_data = prepare_data_for_radar_chart(all_scores)
    radar_path = await loop.run_in_executor(executor, generate_radar_chart, radar_data, name)
    if radar_path:
        try:
            with open(radar_path, "rb") as photo:
                await client.send_photo(chat_id, photo, caption=f"📊 نمودار راداری عملکرد ساحت های شش گانه {name}")
        finally:
            os.unlink(radar_path)

    # --- نمودارهای تاریخچه دروس ---
    multi_chart_paths = await loop.run_in_executor(executor, generate_multi_subject_charts, all_scores, name)
    for path in multi_chart_paths:
        try:
            with open(path, "rb") as photo:
                await client.send_photo(chat_id, photo, caption="نمودار روند نمرات دروس در دوره‌های مختلف")
        finally:
            os.unlink(path)


# ---------- نمایش منوی اصلی ----------
async def show_student_menu(client, chat_id):
    try:
        menu_text = (
            "📋 منوی دانش‌آموز:\n"
            "1️⃣ مشاهده کارنامه‌ها\n\n"
            "🔸 برای بازگشت به منوی قبلی: #\n"
            "🔸 برای خروج کامل از ربات: *"
        )
        await client.send_message(chat_id, menu_text)
    except Exception as e:
        logging.error(f"❌ خطا در show_student_menu: {e}")


# ------------------ هندل اصلی پیام‌های دانش‌آموز (نسخه جدید) ------------------

async def handle_student_message(client, chat_id, user_id, text, name=""):
    try:
        loop = asyncio.get_running_loop()
        school_id = get_school_id_by_student(user_id)
        text = normalize_digits(text.strip())
        st = student_states.get(user_id, {})
        step = st.get("step")
        # --- مدیریت خروج ---
        if text == "*":
            student_states.pop(user_id, None)
            await client.send_message(chat_id, "✅ از منوی دانش‌آموز خارج شدید. برای شروع دوباره /start را ارسال کنید.")
            return "RESET_SESSION"

        # --- مدیریت بازگشت ---
        if text == "#":
            prev_step = st.get("prev_step")
            if not prev_step: # اگر مرحله قبلی وجود نداشت، یعنی در منوی اصلی هستیم
                student_states.pop(user_id, None)
                await client.send_message(chat_id, "✅ از منوی دانش‌آموز خارج شدید. برای شروع دوباره /start را ارسال کنید.")
                return "RESET_SESSION"

            # بازگشت به مرحله قبلی
            st["step"] = prev_step
            # منطق بازگشت را بر اساس مرحله‌ای که به آن برمی‌گردیم، تعیین می‌کنیم
            if prev_step == "main_menu":
                 st["prev_step"] = None # منوی اصلی، مرحله قبلی ندارد
                 await show_student_menu(client, chat_id)
            elif prev_step == "show_periods":
                 st["prev_step"] = "main_menu"
                 periods = get_report_periods(school_id)
                 if periods:
                    await client.send_message(chat_id, format_periods(periods))
                    st["periods_map"] = {str(i + 1): p for i, p in enumerate(periods)}
                 else:
                     await client.send_message(chat_id, "❌ هنوز دوره‌ای ایجاد نشده است.")
                     st["step"] = "main_menu" # اگر دوره‌ای نبود، به منوی اصلی برگرد
                     await show_student_menu(client, chat_id)

            student_states[user_id] = st
            return

        # ------------------ جریان اصلی ربات ------------------

        step = st.get("step")

        # --- مرحله ۱: نمایش منوی اصلی (اولین ورود) ---
        if not step:
            st = {"step": "main_menu", "prev_step": None}
            student_states[user_id] = st
            step = "main_menu"


        # --- مرحله ۲: پردازش ورودی از منوی اصلی ---
        if step == "main_menu":
            if text == "1":
                periods = get_report_periods(school_id)
                if not periods:
                    await client.send_message(chat_id, "❌ هنوز دوره‌ای برای نمایش کارنامه ایجاد نشده است.")
                    return # در همان منوی اصلی بماند

                await client.send_message(chat_id, format_periods(periods))
                st["step"] = "show_periods"
                st["prev_step"] = "main_menu"
                st["periods_map"] = {str(i + 1): p for i, p in enumerate(periods)}
                student_states[user_id] = st
            else:
                await client.send_message(chat_id, "❌ گزینه نامعتبر است. لطفاً یکی از گزینه‌های منو را انتخاب کنید.")
            return

        # --- مرحله ۳: پردازش انتخاب دوره ---
        if step == "show_periods":
            period = st.get("periods_map", {}).get(text)
            if not period:
                await client.send_message(chat_id, "❌ شماره دوره نامعتبر است. لطفاً شماره صحیح را وارد کنید.")
                return

            st["step"] = "viewing_report"
            st["prev_step"] = "show_periods" # مرحله قبل از مشاهده کارنامه، لیست دوره‌ها بود
            student_states[user_id] = st

            await client.send_message(chat_id, "⏳ در حال آماده‌سازی گزارش شما... لطفاً شکیبا باشید.")

            # ۱. دریافت داده‌های کارنامه فعلی
            report_data = get_student_comprehensive_report(user_id, period[0])
            if not report_data or not report_data.get("scores"):
                await client.send_message(chat_id, "📭 هنوز نمره‌ای برای این دوره ثبت نشده است.")
                # کاربر را به مرحله انتخاب دوره برمی‌گردانیم
                st["step"] = "show_periods"
                st["prev_step"] = "main_menu"
                student_states[user_id] = st
                await client.send_message(chat_id, "لطفاً دوره دیگری را انتخاب کنید یا برای بازگشت # را بزنید.")
                return

            # ۲. ساخت و ارسال بخش متنی کارنامه
            report_message = build_report_card_message(report_data, name, period[1])
            await client.send_message(chat_id, report_message)

            # ۳. دریافت داده‌های تاریخچه
            history_data = get_student_performance_history(user_id)

            # ۴. تولید و ارسال تمام نمودارها
            await generate_and_send_all_charts(loop, client, chat_id, report_data, history_data, name, period[1])

            # ۵. ساخت و ارسال بخش متنی تاریخچه
            if history_data.get("all_scores"):
                history_message = build_score_history_message(history_data["all_scores"], name)
                await client.send_message(chat_id, history_message)

            await client.send_message(chat_id, "✅ گزارش شما آماده شد.\n"
                                               "🔸 برای مشاهده کارنامه دوره‌ای دیگر، شماره آن را وارد کنید.\n"
                                               "🔹 برای بازگشت به لیست دوره‌ها «#» را ارسال کنید.")
            # پس از نمایش گزارش، وضعیت را برای دریافت شماره دوره جدید تنظیم می‌کنیم
            # این کار باعث می‌شود کاربر بتواند بلافاصله دوره دیگری را انتخاب کند
            st["step"] = "show_periods"
            st["prev_step"] = "main_menu"
            student_states[user_id] = st

    except Exception as e:
        logger.error(f"❌ خطا در handle_student_message (user_id={user_id}): {e}")
        await client.send_message(chat_id, "⚠️ خطای کلی در پردازش درخواست شما رخ داد. لطفاً مجدداً تلاش کنید.")