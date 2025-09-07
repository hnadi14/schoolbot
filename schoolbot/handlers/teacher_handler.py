# teacher_handler
import os

import jdatetime
import matplotlib

from schoolbot.chart.teacher_chart.teacher_chart import generate_class_summary_chart_robust
from schoolbot.present.teacher_presenter.teacher_presenter import summarize_class, _safe_prev_score_lookup
from schoolbot.services.score_service_teacher import get_report_periods_teachers, get_teacher_school_id
from schoolbot.utils.keyboards import normalize_digits, to_persian_digits

matplotlib.use('Agg')
import logging

from schoolbot.services.report_service import (
    get_subjects_by_teacher,
    get_students_by_class,
    save_student_score,
    get_class_by_id, get_students_scores_by_class,
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


# ----------------- رندر منو -----------------
async def render_menu(client, chat_id, user_id):
    try:
        st = teacher_states.get(user_id, {})
        # اگر استیت نبود، مقدار اولیه قرار می‌دهیم
        if not st:
            teacher_states[user_id] = {"step": "main_menu"}
            st = teacher_states[user_id]

        step = st.get("step")

        if step == "main_menu":
            await show_teacher_menu(client, chat_id)
            return

        if step == "select_period":
            try:
                ss = get_teacher_school_id(user_id)
                periods = get_report_periods_teachers(ss)
            except Exception:
                logging.exception("❌ خطا در دریافت دوره‌ها در render_menu")
                await client.send_message(chat_id, "❌ خطا در دریافت دوره‌ها. لطفاً بعداً تلاش کنید.")
                return
            msg = "📅 لطفاً شماره دوره را انتخاب کنید:\n"
            periods_map = {}
            for i, p in enumerate(periods, 1):
                msg += f"{i}. {p[1]}\n"
                periods_map[str(i)] = p
            msg += "\n'*' برای خروج، '#' برای بازگشت."
            st["periods_map"] = periods_map
            teacher_states[user_id] = st
            await client.send_message(chat_id, msg)
            return

        if step == "select_subject":
            try:
                subjects = get_subjects_by_teacher(user_id)
            except Exception:
                logging.exception("❌ خطا در get_subjects_by_teacher در render_menu")
                await client.send_message(chat_id, "❌ خطا در دریافت دروس.")
                teacher_states.pop(user_id, None)
                return
            msg = "📚 لطفاً شماره درس را انتخاب کنید:\n"
            subjects_map = {}
            for i, s in enumerate(subjects, 1):
                subject_id, subject_name, class_id = s
                try:
                    class_info = get_class_by_id(class_id)
                    class_name = class_info[1] if class_info else ""
                except Exception:
                    logging.exception("❌ خطا در get_class_by_id در render_menu")
                    class_name = ""
                msg += f"{i}. {subject_name} {class_name}\n"
                subjects_map[str(i)] = (subject_id, subject_name, class_id, class_name)  # <-- نام کلاس اضافه شد
            msg += "\n'*' برای خروج، '#' برای بازگشت."
            st["subjects_map"] = subjects_map
            teacher_states[user_id] = st
            await client.send_message(chat_id, msg)
            return

        if step == "choose_action":
            actions_msg = (
                f"📘 درس: {st.get('subject_name', '')} {st.get('class_name')}\n"
                "عملیات را انتخاب کنید:\n"
                "1. ثبت / ویرایش نمرات همه دانش‌آموزان کلاس\n"
                "2. مشاهده خلاصه وضعیت کلاس\n"
                "3. ثبت / ویرایش نمره یک دانش‌آموز خاص\n"
                "'*' برای خروج، '#' برای بازگشت."
            )
            await client.send_message(chat_id, actions_msg)
            return

        if step == "enter_score":
            idx = st.get("current_index", 0)
            students = st.get("students", [])
            if idx >= len(students):
                # حالت غیرمنتظره — بازگشت به منو
                st["step"] = "choose_action"
                teacher_states[user_id] = st
                await client.send_message(chat_id, "⚠️ خطا در شاخص دانش‌آموز — بازگشت به منو.")
                await render_menu(client, chat_id, user_id)
                return
            student_id, student_name = students[idx]
            prev = _safe_prev_score_lookup(student_id, st.get("subject_id"), st.get("report_period_id"))
            msg = f"👨‍🎓 وارد کردن نمره برای: {student_name}\n"
            if prev:
                msg += f"نمره قبلی: {prev.get('score')}, توضیح: {prev.get('description')}\n"
            msg += "لطفاً نمره را وارد کنید (عدد) یا '-' برای رد کردن. '*' برای خروج، '#' برای بازگشت."
            await client.send_message(chat_id, msg)
            return

        if step == "enter_description":
            await client.send_message(chat_id, "📝 توضیحات نمره؟ (برای رد شدن '-' بزنید) '*' برای خروج، '#' برای بازگشت")
            return

        if step == "enter_score_single":
            student_id, student_name = st.get("current_student", ("?", "?"))
            prev = _safe_prev_score_lookup(student_id, st.get("subject_id"), st.get("report_period_id"))
            msg = f"👨‍🎓 وارد کردن نمره برای: {student_name}\n"
            if prev:
                msg += f"نمره قبلی: {prev.get('score')}, توضیح: {prev.get('description')}\n"
            msg += "لطفاً نمره را وارد کنید (عدد) یا '-' برای رد کردن. '*' برای خروج، '#' برای بازگشت."
            await client.send_message(chat_id, msg)
            return

        if step == "enter_description_single":
            await client.send_message(chat_id, "📝 توضیحات نمره؟ (برای رد شدن '-' بزنید) '*' برای خروج، '#' برای بازگشت")
            return

    except Exception:
        logging.exception("❌ خطا در render_menu")
        try:
            await client.send_message(chat_id, "⚠️ خطا در نمایش منو. لطفاً دوباره تلاش کنید.")
        except Exception:
            logging.exception("❌ خطا در ارسال پیام خطا به کاربر در render_menu")


# ---------- نمایش منوی اصلی ----------
async def show_teacher_menu(client, chat_id):
    try:
        menu_text = (
            "📋 منوی معلم:\n"
            "1️⃣ مشاهده دوره‌ها و دروس\n"
            "🔑 برای تغییر رمز عبور، فقط `+` بفرستید."

        )
        await client.send_message(chat_id, menu_text)
    except Exception as e:
        logging.error(f"❌ خطا در show_teacher_menu: {e}")


# ----------------- هندلر اصلی -----------------
async def handle_teacher_message(client, chat_id, user_id, text, name):
    try:
        text = text.strip()
        text = normalize_digits(text)  # ← نرمال‌سازی اعداد

        st = teacher_states.get(user_id, {})

        # خروج کامل
        if text in ("/خروج", "*", "خروج"):
            teacher_states.pop(user_id, None)
            await client.send_message(chat_id, "✅ از حالت معلم خارج شدید. برای شروع مجدد /start را ارسال کنید.")
            return "RESET_SESSION"  # ارسال سیگنال برای ریست کامل به فایل اصلی

        # بازگشت به منوی قبلی
        if text == "#":
            step = st.get("step")
            if step == "select_subject":
                st["step"] = "select_period"
            elif step == "select_period":
                st["step"] = "main_menu"
            elif step == "main_menu":
                teacher_states.pop(user_id, None)
                await client.send_message(chat_id, "✅ از حالت معلم خارج شدید. برای شروع مجدد /start را ارسال کنید.")
                return "RESET_SESSION"  # ارسال سیگنال برای ریست کامل به فایل اصلی

            elif step == "choose_action":
                st["step"] = "select_subject"
            elif step in ("enter_score", "enter_description"):
                st["step"] = "choose_action"
            elif step == "select_student":
                st["step"] = "choose_action"

            teacher_states[user_id] = st
            await client.send_message(chat_id, "🔙 به منوی قبلی بازگشتید.")
            await render_menu(client, chat_id, user_id)
            return

        # مرحلهٔ اولیه
        if not st:
            teacher_states[user_id] = {"step": "select_period"}
            await render_menu(client, chat_id, user_id)
            return

        step = st.get("step")

        # ---------------- انتخاب دوره ----------------
        if step == "select_period":
            selected = st.get("periods_map", {}).get(text)
            if not selected:
                await client.send_message(chat_id, "❌ شماره دوره نامعتبر است. '*' برای خروج، '#' برای بازگشت.")
                return
            st["report_period_id"] = selected[0]
            st["step"] = "select_subject"
            teacher_states[user_id] = st
            await render_menu(client, chat_id, user_id)
            return

        # ---------------- انتخاب درس ----------------
        if step == "select_subject":
            sel = st.get("subjects_map", {}).get(text)
            if not sel:
                await client.send_message(chat_id, "❌ شماره درس نامعتبر است. '*' برای خروج، '#' برای بازگشت.")
                return
            subject_id, subject_name, class_id, class_name = sel  # <-- نام کلاس هم دریافت می‌شود
            st.update(
                {"subject_id": subject_id, "subject_name": subject_name, "class_id": class_id, "class_name": class_name,
                 "step": "choose_action"})  # <-- نام کلاس به state اضافه شد
            teacher_states[user_id] = st
            await render_menu(client, chat_id, user_id)
            return

        # ---------------- انتخاب عملیات ----------------
        if step == "choose_action":
            if text == "1":
                try:
                    students = get_students_by_class(st["class_id"])
                except Exception:
                    logging.exception("❌ خطا در get_students_by_class گزینه 1")
                    await client.send_message(chat_id, "❌ خطا در دریافت دانش‌آموزان.")
                    teacher_states.pop(user_id, None)
                    return
                if not students:
                    await client.send_message(chat_id, "❌ هیچ دانش‌آموزی یافت نشد.")
                    teacher_states.pop(user_id, None)
                    return
                st.update({"students": students, "current_index": 0, "step": "enter_score"})
                teacher_states[user_id] = st
                await render_menu(client, chat_id, user_id)
                return

            elif text == "2":
                try:
                    students_scores = get_students_scores_by_class(
                        st["class_id"], st["subject_id"], st["report_period_id"]
                    )
                    report, scores_list = summarize_class(
                        st['subject_name'], students_scores, st.get('class_name', '')
                    )
                    await client.send_message(chat_id, to_persian_digits(report))

                    # تلاش برای ساخت، ارسال و حذف امن نمودار
                    if scores_list:
                        chart_path = None  # متغیر را برای استفاده در finally تعریف می‌کنیم
                        try:
                            chart_path = generate_class_summary_chart_robust(
                                scores_list,
                                class_name=st.get("class_name", ""),
                                subject_name=st.get('subject_name', ''),
                                name=name
                            )
                            if chart_path:
                                # 1. فایل را با 'with' باز کرده و شیء فایل را به send_photo می‌دهیم
                                with open(chart_path, "rb") as photo_file:
                                    await client.send_photo(
                                        chat_id,
                                        photo=photo_file,
                                        caption=f"تحلیل آماری نمرات {st.get('subject_name', '')} {st.get('class_name', '')}: {name} \n {jdatetime.datetime.now().strftime(' %Y/%m/%d')}"
                                    )
                            else:
                                await client.send_message(chat_id, "⚠️ تولید نمودار موفقیت‌آمیز نبود.")
                        except Exception as e:
                            logging.exception(f"❌ خطا در تولید یا ارسال نمودار (گزینه 2): {e}")
                            await client.send_message(chat_id, "⚠️ خطا در تولید نمودار.")
                        finally:
                            # 2. در هر صورت فایل موقت را بعد از اتمام کار 'with' حذف می‌کنیم
                            if chart_path and os.path.exists(chart_path):
                                try:
                                    os.unlink(chart_path)
                                except Exception as e:
                                    logging.error(f"❌ خطا در حذف فایل نمودار موقت: {e}")

                except Exception as e:
                    logging.exception(f"❌ خطا در دریافت یا خلاصه‌سازی نمرات (گزینه 2): {e}")
                    await client.send_message(chat_id, "❌ خطا در دریافت اطلاعات کلاس.")

                # در هر صورت (موفق یا ناموفق)، کاربر را به منوی عملیات برگردان
                finally:
                    st["step"] = "choose_action"
                    teacher_states[user_id] = st
                    await client.send_message(chat_id, "👇 لطفاً عملیات بعدی را انتخاب کنید.")
                    await render_menu(client, chat_id, user_id)
                return

            elif text == "3":
                try:
                    students = get_students_by_class(st["class_id"])
                except Exception:
                    logging.exception("❌ خطا در get_students_by_class گزینه 3")
                    await client.send_message(chat_id, "❌ خطا در دریافت دانش‌آموزان.")
                    return
                if not students:
                    await client.send_message(chat_id, "❌ هیچ دانش‌آموزی یافت نشد.")
                    return

                msg = "👨‍🎓 لطفاً شماره دانش‌آموز را انتخاب کنید:\n"
                students_map = {}
                for i, (student_id, student_name) in enumerate(students, 1):
                    msg += f"{i}. {student_name}\n"
                    prev = _safe_prev_score_lookup(student_id, st["subject_id"], st["report_period_id"])
                    if prev:
                        msg += f"نمره قبلی: {prev.get('score')}, توضیح: {prev.get('description')}\n"
                    students_map[str(i)] = (student_id, student_name)
                msg += "\n'*' برای خروج، '#' برای بازگشت."

                st.update({
                    "students_map": students_map,
                    "step": "select_student"
                })
                teacher_states[user_id] = st
                await client.send_message(chat_id, msg)
                return

            else:
                await client.send_message(chat_id,
                                          "لطفاً یکی از گزینه‌های 1 تا 3 را وارد کنید یا '*' برای خروج، '#' برای بازگشت.")
                return

        if step == "select_student":
            selected = st.get("students_map", {}).get(text)
            if not selected:
                await client.send_message(chat_id, "❌ شماره دانش‌آموز نامعتبر است. '*' برای خروج، '#' برای بازگشت.")
                return
            student_id, student_name = selected
            st.update({
                "current_student": (student_id, student_name),
                "step": "enter_score_single"
            })
            teacher_states[user_id] = st
            await render_menu(client, chat_id, user_id)
            return

        if step == "enter_score_single":
            if text == "-":
                st["current_score"] = None
            else:
                try:
                    score = float(text)
                    if not (0 <= score <= 20):
                        await client.send_message(chat_id, "❌ نمره باید بین 0 تا 20 باشد.")
                        return
                    st["current_score"] = score
                except ValueError:
                    await client.send_message(chat_id, "❌ لطفاً فقط عدد وارد کنید یا '-' برای رد کردن.")
                    return

            st["step"] = "enter_description_single"
            teacher_states[user_id] = st
            await render_menu(client, chat_id, user_id)
            return

        if step == "enter_description_single":
            description = None if text == "-" else text
            student_id, _ = st["current_student"]
            if st.get("current_score") is not None or description:
                try:
                    save_student_score(student_id, st["subject_id"], st["report_period_id"], st["current_score"],
                                       description)
                except Exception:
                    logging.exception("❌ خطا در save_student_score (single)")
                    await client.send_message(chat_id, "❌ خطا در ذخیرهٔ نمره.")
                    teacher_states.pop(user_id, None)
                    return
            await client.send_message(chat_id, f"✅ نمره دانش‌آموز ثبت شد.")
            st.pop("current_student", None)
            st.pop("current_score", None)
            st["step"] = "choose_action"
            teacher_states[user_id] = st
            await render_menu(client, chat_id, user_id)
            return

        # ---------------- وارد کردن نمره ----------------
        if step == "enter_score":
            if text == "-":
                st["current_score"] = None
            else:
                try:
                    score = float(text)
                    if not (0 <= score <= 20):
                        await client.send_message(chat_id, "❌ نمره باید بین 0 تا 20 باشد.")
                        return
                    st["current_score"] = score
                except ValueError:
                    await client.send_message(chat_id, "❌ لطفاً فقط عدد وارد کنید یا '-' برای رد کردن.")
                    return

            st["step"] = "enter_description"
            teacher_states[user_id] = st
            await render_menu(client, chat_id, user_id)
            return

        # ---------------- توضیحات و ذخیره ----------------
        if step == "enter_description":
            description = None if text == "-" else text
            idx = st.get("current_index", 0)
            students = st.get("students", [])
            if idx >= len(students):
                logging.error("❌ اندیس فعلی بیش از طول لیست دانش‌آموزان است در enter_description")
                teacher_states.pop(user_id, None)
                await client.send_message(chat_id, "❌ خطا در وضعیت داخلی. عملیات متوقف شد.")
                return
            student_id, _ = students[idx]
            if st.get("current_score") is not None or description:
                try:
                    save_student_score(student_id, st["subject_id"], st["report_period_id"], st["current_score"],
                                       description)
                except Exception:
                    logging.exception("❌ خطا در save_student_score (batch)")
                    await client.send_message(chat_id, "❌ خطا در ذخیرهٔ نمره.")
                    teacher_states.pop(user_id, None)
                    return
            st["current_index"] = idx + 1
            if st["current_index"] < len(students):
                st["step"] = "enter_score"
                teacher_states[user_id] = st
                await render_menu(client, chat_id, user_id)
                return
            else:
                await client.send_message(chat_id, "✅ ثبت نمرات همه دانش‌آموزان پایان یافت.")
                st.pop("students", None)
                st.pop("current_index", None)
                st.pop("current_score", None)
                st["step"] = "choose_action"
                teacher_states[user_id] = st
                await render_menu(client, chat_id, user_id)
                return


    except Exception:
        logging.exception("❌ خطا غیرمنتظره در handle_teacher_message")
        try:
            await client.send_message(chat_id, "⚠️ خطای سیستمی رخ داد. لطفاً دوباره تلاش کنید.")
        except Exception:
            logging.exception("❌ خطا در ارسال پیام خطا به کاربر در handle_teacher_message")
