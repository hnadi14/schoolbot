import logging
import os

import jdatetime

from schoolbot.services.open_ai_response import get_chatbot_response
from schoolbot.services.report_service import (
    create_report_period,
    toggle_report_period_approval,
    get_all_report_periods,
    get_scores_completion_status,
    get_all_user_messages_user_id_role
)

from schoolbot.services.score_service_manager import get_school_multi_period_analysis
from schoolbot.utils.helpers import format_school_multi_period_analysis
from schoolbot.utils.keyboards import normalize_digits, to_persian_digits
from schoolbot.utils.manager_report_ai_text import extract_course_stats

# 📌 فقط خطاها ثبت شوند
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
# برای اطمینان، لاگ سطح پایین‌تر در کتابخانه‌های جانبی هم غیرفعال شود
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("balethon").setLevel(logging.WARNING)

manager_states = {}  # ذخیره وضعیت مدیران


# ---------- تابع کمکی: تغییر مرحله و نمایش منو ----------
async def set_step_and_show_menu(user_id, st, step, client, chat_id):
    try:
        st["step"] = step
        manager_states[user_id] = st
        await show_manager_menu(client, chat_id)
    except Exception as e:
        logging.error(f"❌ خطا در set_step_and_show_menu: {e}")
        await client.send_message(chat_id, "⚠️ مشکلی در تغییر مرحله پیش آمد.")


# ---------- تابع کمکی: ارسال پیام یادآوری ----------
async def send_reminder_messages(client, chat_id, incomplete_teachers, selected_period_name):
    try:
        manager_message = ""
        for teacher_id, info in incomplete_teachers.items():
            try:
                id_bale_list = get_all_user_messages_user_id_role(user_id=teacher_id, role="teacher")
                if not id_bale_list:
                    manager_message += f"\n⚠️ آیدی بله {info['teacher']} پیدا نشد."
                    continue

                lessons_text = "\n".join(info["lessons"])
                await client.send_message(
                    id_bale_list[0][0],  # اولین id_bale معتبر
                    f"{info['teacher']}\n📢 یادآوری: لطفاً هرچه سریع‌تر نمرات '{selected_period_name}' را تکمیل کنید.\n❗ موارد ناقص شما:\n{lessons_text} \n تاریخ امروز: {jdatetime.datetime.now().strftime(' %Y/%m/%d ساعت: %H:%M')}"
                )
                manager_message += f"\n✅ پیام یادآوری برای {info['teacher']} ارسال شد."
            except Exception as e:
                logging.error(f"❌ خطا در ارسال پیام یادآوری به {info['teacher']}: {e}")
                manager_message += f"\n⚠️ ارسال پیام به {info['teacher']} ممکن نبود."

        if manager_message:
            await client.send_message(chat_id, manager_message)

    except Exception as e:
        logging.error(f"❌ خطا در send_reminder_messages: {e}")
        await client.send_message(chat_id, "⚠️ خطا در ارسال پیام‌های یادآوری.")


# ---------- تابع اصلی هندل پیام مدیر ----------
async def handle_manager_message(client, chat_id, user_id, text, name):
    try:
        text = normalize_digits(text.strip())
        st = manager_states.get(user_id, {})

        # خروج کامل
        if text == "*":
            manager_states.pop(user_id, None)
            await client.send_message(chat_id, "✅ از ربات خارج شدید.\nبرای شروع دوباره /start را ارسال کنید.")
            return "RESET_SESSION"  # ارسال سیگنال برای ریست کامل به فایل اصلی

        # بازگشت به منوی قبلی
        # -------------------- کد پیشنهادی --------------------

        # بازگشت به منوی قبلی یا خروج
        if text == "#":
            current_step = st.get("step")

            # اگر کاربر در منوی اصلی است (یا تازه وارد شده)، # به معنی خروج است
            if not current_step or current_step == "manager_menu":
                manager_states.pop(user_id, None)
                await client.send_message(chat_id,
                                      "✅ از منوی مدیر خارج شدید.\nبرای شروع دوباره /start را ارسال کنید.")
                return "RESET_SESSION"  # ارسال سیگنال برای ریست کامل به فایل اصلی

            # در غیر این صورت، اگر کاربر در مراحل داخلی‌تر باشد، # او را به منوی اصلی برمی‌گرداند
            else:
            # بازگشت به منوی اصلی و پاک کردن وضعیت‌های قبلی
                st["step"] = "manager_menu"
                # پاک کردن داده‌های موقت مراحل قبلی
                st.pop("periods", None)
                st.pop("incomplete_teachers", None)
                st.pop("selected_period", None)
                manager_states[user_id] = st
                await show_manager_menu(client, chat_id)

            return
        # if text == "#":
        #     prev_step = st.get("prev_step")
        #     if prev_step:
        #         st["step"] = prev_step
        #         st["prev_step"] = None
        #         manager_states[user_id] = st
        #         if prev_step == "manager_menu":
        #             manager_states.pop(user_id, None)
        #             await client.send_message(chat_id, "✅ از ربات خارج شدید.\nبرای شروع دوباره /start را ارسال کنید.")
        #             return "RESET_SESSION"  # ارسال سیگنال برای ریست کامل به فایل اصلی
        #
        #             # await show_manager_menu(client, chat_id)
        #         elif prev_step == "approve_report_period":
        #             await client.send_message(chat_id, "📋 لطفاً عدد دوره‌ای را وارد کنید:")
        #         elif prev_step == "create_report_period":
        #             await client.send_message(chat_id, "📝 نام دوره کارنامه جدید را وارد کنید:")
        #     else:
        #         await show_manager_menu(client, chat_id)
        #     return

        # منوی اصلی
        if not st or st.get("step") == "manager_menu":
            await handle_manager_main_menu(client, chat_id, user_id, text, st, name)
            return

        # مراحل مختلف
        step = st.get("step")
        if step == "create_report_period":
            try:
                create_report_period(text, user_id)
                await client.send_message(chat_id, f"✅ دوره «{text}» ایجاد شد.")
            except Exception as e:
                logging.error(f"❌ خطا در create_report_period: {e}")
                await client.send_message(chat_id, "⚠️ خطا در ایجاد دوره.")
            await set_step_and_show_menu(user_id, st, "manager_menu", client, chat_id)

        elif step == "approve_report_period":
            await handle_approve_report_period(client, chat_id, user_id, text, st)

        elif step == "check_scores_status":
            await handle_check_scores_status(client, chat_id, user_id, text, st)

        elif step == "manager_decision":
            await handle_manager_decision(client, chat_id, user_id, text, st)

    except Exception as e:
        logging.error(f"❌ خطا در handle_manager_message: {e}")
        await client.send_message(chat_id, "⚠️ مشکلی در پردازش پیام مدیر پیش آمد.")


# ---------- تابع کمکی: منوی اصلی ----------
async def handle_manager_main_menu(client, chat_id, user_id, text, st, name):
    try:
        if text == "1":
            st["prev_step"] = "manager_menu"
            st["step"] = "create_report_period"
            manager_states[user_id] = st
            await client.send_message(chat_id, "📝 نام دوره کارنامه جدید را وارد کنید:")


        elif text == "2":
            chart_path = None  # متغیر را برای استفاده در finally تعریف می‌کنیم
            try:
                analysis = get_school_multi_period_analysis(user_id)
                msg, chart_path = format_school_multi_period_analysis(analysis, name)

                if "_@_error_@_" not in (
                        response := get_chatbot_response(role="manager", user_question=extract_course_stats(msg))):
                    msg += "\n\n" + " 🧠  تحلیل و پیشنهاد:"
                    msg += response

                await client.send_message(chat_id, to_persian_digits(msg))

                if chart_path and os.path.exists(chart_path):
                    with open(chart_path, "rb") as photo_file:
                        await client.send_photo(chat_id, photo_file,
                                                caption=f"تحلیل و آنالیز تصویری مدرسه {name} \n {jdatetime.datetime.now().strftime(' %Y/%m/%d')} \n🔸 برای بازگشت «#» و برای خروج کامل «*»")
                else:
                    await client.send_message(chat_id, "⚠️ فایل نمودار یافت نشد.")
                st["step"] = "viewed_report"
                manager_states[user_id] = st
            except Exception as e:
                logging.error(f"❌ خطا در تحلیل کارنامه‌ها: {e}")
                await client.send_message(chat_id, "⚠️ خطا در نمایش کارنامه‌ها.")
            finally:
                # در هر صورت (موفق یا ناموفق)، فایل موقت نمودار را حذف می‌کنیم
                if chart_path and os.path.exists(chart_path):
                    try:
                        os.unlink(chart_path)
                    except Exception as e:
                        logging.error(f"❌ خطا در حذف فایل نمودار مدیر: {e}")
        elif text == "3":
            try:
                periods = get_all_report_periods(user_id)
                if not periods:
                    await client.send_message(chat_id, "⚠️ هیچ دوره‌ای وجود ندارد.")
                    return
                msg = "📋 لیست دوره‌های کارنامه:\n"
                for idx, p in enumerate(periods, start=1):
                    status = "✅ تأیید شده" if p["approved"] else "❌ عدم تأیید"
                    msg += f"{idx}. {p['name']} ({status})\n"
                msg += "\nلطفاً عدد دوره‌ای که می‌خواهید وضعیت آن را تغییر دهید وارد کنید:"
                msg += "\n🔸 برای بازگشت «#» و برای خروج کامل «*»"
                st["prev_step"] = "manager_menu"
                st["step"] = "approve_report_period"
                st["periods"] = periods
                manager_states[user_id] = st
                await client.send_message(chat_id, msg)
            except Exception as e:
                logging.error(f"❌ خطا در گرفتن دوره‌ها: {e}")
                await client.send_message(chat_id, "⚠️ خطا در دریافت دوره‌ها.")

        elif text == "4":
            try:
                periods = get_all_report_periods(user_id)
                if not periods:
                    await client.send_message(chat_id, "⚠️ هیچ دوره‌ای برای بررسی وجود ندارد.")
                    return
                msg = "📋 لیست دوره‌های کارنامه برای بررسی وضعیت نمرات:\n"
                for idx, p in enumerate(periods, start=1):
                    msg += f"{idx}. {p['name']}\n"
                msg += "\nلطفاً عدد دوره‌ای که می‌خواهید بررسی کنید را وارد کنید:"
                st["prev_step"] = "manager_menu"
                st["step"] = "check_scores_status"
                st["periods"] = periods
                manager_states[user_id] = st
                await client.send_message(chat_id, msg)
            except Exception as e:
                logging.error(f"❌ خطا در گرفتن وضعیت نمرات: {e}")
                await client.send_message(chat_id, "⚠️ خطا در دریافت وضعیت نمرات.")

        else:
            await client.send_message(chat_id, "⚠️ لطفاً عدد معتبر را وارد کنید.")
    except Exception as e:
        logging.error(f"❌ خطا در handle_manager_main_menu: {e}")
        await client.send_message(chat_id, "⚠️ مشکلی در اجرای منو پیش آمد.")


# ---------- تایید/عدم تایید دوره ----------
async def handle_approve_report_period(client, chat_id, user_id, text, st):
    try:
        choice = int(text)
        periods = st.get("periods", [])
        if 1 <= choice <= len(periods):
            selected = periods[choice - 1]
            try:
                new_status = toggle_report_period_approval(selected["id"])
                status_text = "✅ تأیید شد" if new_status else "❌ عدم تأیید شد"
                await client.send_message(chat_id, f"دوره «{selected['name']}» {status_text}.")
            except Exception as e:
                logging.error(f"❌ خطا در toggle_report_period_approval: {e}")
                await client.send_message(chat_id, "⚠️ خطا در تغییر وضعیت دوره.")
        else:
            await client.send_message(chat_id, "⚠️ عدد وارد شده معتبر نیست.")
    except ValueError:
        await client.send_message(chat_id, "⚠️ لطفاً یک عدد وارد کنید.")
    except Exception as e:
        logging.error(f"❌ خطا در handle_approve_report_period: {e}")
        await client.send_message(chat_id, "⚠️ خطا در تأیید دوره.")
    await set_step_and_show_menu(user_id, st, "manager_menu", client, chat_id)


# ---------- بررسی وضعیت نمرات ----------
async def handle_check_scores_status(client, chat_id, user_id, text, st):
    try:
        choice = int(text)
        periods = st.get("periods", [])
        if not (1 <= choice <= len(periods)):
            await client.send_message(chat_id, "⚠️ عدد وارد شده معتبر نیست.")
            return

        selected = periods[choice - 1]
        try:
            status_list = get_scores_completion_status(selected["id"], user_id)
        except Exception as e:
            logging.error(f"❌ خطا در get_scores_completion_status: {e}")
            await client.send_message(chat_id, "⚠️ خطا در دریافت وضعیت نمرات.")
            return

        lines = []
        incomplete_teachers = {}
        for item in status_list:
            lines.append(f"📌 کلاس {item['class']} - {item['subject']}: "
                         f"{item['scored']}/{item['total']} -- {item['status']}⇐  میانگین: {round(item['avg_score'], 2) if item['avg_score'] is not None else 'ثبت نشده'}⟸ دبیر: {item['teacher']}")

            if item["status"] == "ناقص":
                teacher_id = item["teacher_id"]
                lesson_info = f" {item['subject']}  {item['class']}"
                incomplete_teachers.setdefault(teacher_id, {"teacher": item["teacher"], "lessons": []})[
                    "lessons"].append(lesson_info)

        msg = f"📊 وضعیت ثبت نمرات (دوره: {selected['name']}):\n\n" + jdatetime.datetime.now().strftime(
            ' %Y/%m/%d') + "\n" + "\n".join(lines)

        if incomplete_teachers:
            msg += "\n\n❌ معلمانی که نمرات ناقص دارند:\n"
            for teacher_id, info in incomplete_teachers.items():
                lessons_text = ", ".join(info["lessons"])
                msg += f"   • نام دبیر: {info['teacher']}: {lessons_text}\n"

            msg += "\n⚡ لطفاً یکی از گزینه‌های زیر را انتخاب کنید:\n"
            msg += f"1️⃣ ارسال پیام یادآوری در 'بله' به معلمانی که نمرات ناقص دارند.\n"
            msg += "2️⃣ بازگشت به منوی مدیر"

            st["step"] = "manager_decision"
            st["incomplete_teachers"] = incomplete_teachers
            st["selected_period"] = selected
            manager_states[user_id] = st
        else:
            msg += "\n✅ همه معلمان نمرات را کامل ثبت کرده‌اند."
            msg += "\n🔸 برای بازگشت «#» و برای خروج کامل «*»"
            await set_step_and_show_menu(user_id, st, "manager_menu", client, chat_id)

        await client.send_message(chat_id, msg)

    except ValueError:
        await client.send_message(chat_id, "⚠️ لطفاً یک عدد وارد کنید.")
    except Exception as e:
        logging.error(f"❌ خطا در handle_check_scores_status: {e}")
        await client.send_message(chat_id, "⚠️ خطا در بررسی وضعیت نمرات.")


# ---------- تصمیم مدیر ----------
async def handle_manager_decision(client, chat_id, user_id, text, st):
    try:
        if text == "1":
            await send_reminder_messages(client, chat_id, st.get("incomplete_teachers", {}),
                                         st['selected_period']['name'])
            await set_step_and_show_menu(user_id, st, "manager_menu", client, chat_id)
        elif text == "2":
            await set_step_and_show_menu(user_id, st, "manager_menu", client, chat_id)
        else:
            await client.send_message(chat_id, "⚠️ لطفاً فقط 1 یا 2 را انتخاب کنید.")
    except Exception as e:
        logging.error(f"❌ خطا در handle_manager_decision: {e}")
        await client.send_message(chat_id, "⚠️ خطا در تصمیم‌گیری مدیر.")


# ---------- نمایش منوی اصلی ----------
async def show_manager_menu(client, chat_id):
    try:
        menu_text = (
            "📋 منوی مدیر:\n"
            "1️⃣ ایجاد دوره کارنامه\n"
            "2️⃣ مشاهده وضعیت دانش‌آموزان\n"
            "3️⃣ تأیید دوره کارنامه\n"
            "4️⃣ بررسی وضعیت ثبت نمرات\n\n"
            "🔸 برای بازگشت ⬅️ #\n"
            "🔸 برای خروج از ربات ❌ *"
        )
        await client.send_message(chat_id, menu_text)
    except Exception as e:
        logging.error(f"❌ خطا در show_manager_menu: {e}")
