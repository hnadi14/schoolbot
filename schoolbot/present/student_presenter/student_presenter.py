# schoolbot/presenters/student_presenter.py

import textwrap
import jdatetime
import numpy as np
from typing import Dict, List, Tuple

from schoolbot.services.open_ai_response import get_chatbot_response
from schoolbot.utils.keyboards import to_persian_digits

# ------------------ ثابت‌ها و توابع کمکی نمایشی ------------------

SUBJECT_EMOJIS = {
    "ریاضی": "📐", "علوم": "🧪", "علوم تجربی": "🧪", "فارسی": "📖", "املا": "✍️",
    "قرآن": "📜", "عربی": "🔤", "زبان انگلیسی": "🗣️", "مطالعات اجتماعی": "🌍",
    "هنر": "🎨", "ورزش": "🏃", "کامپیوتر": "🖥️", "دینی": "🕌",
}


def get_subject_emoji(name: str) -> str:
    """یک ایموجی مناسب برای نام درس برمی‌گرداند."""
    for key, emoji in SUBJECT_EMOJIS.items():
        if key in name:
            return emoji
    return "📚"


def format_periods(periods: List[Tuple[int, str]]) -> str:
    """لیست دوره‌ها را برای انتخاب کاربر فرمت می‌کند."""
    msg = "📅 لطفاً شماره دوره را انتخاب کنید:\n"
    for i, p in enumerate(periods, 1):
        msg += f"{i}. {p[1]}\n"
    msg += "\n🔸 برای بازگشت «#» و برای خروج کامل «*»"
    return msg


def format_rank_with_total(rank: int, total: int) -> str:
    """رتبه را به فرمت 'X از Y' تبدیل می‌کند."""
    if rank is None or not total:
        return ""
    return f"{rank} از {total}"


def best_rank_format(top_students: List[Dict]) -> List[str]:
    """جدول نفرات برتر را به صورت متنی فرمت می‌کند."""
    lines = []
    col_widths = {"ردیف": 6, "نام": 15, "کلاس": 10, "معدل": 6}
    row_format = f"{{:<{col_widths['ردیف']}}} {{:<{col_widths['نام']}}} {{:<{col_widths['کلاس']}}} {{:<{col_widths['معدل']}}}"
    lines.append("━" * 20)
    lines.append(row_format.format("ردیف", "نام", "کلاس", "معدل"))
    lines.append("━" * 20)
    for i, stu in enumerate(top_students, 1):
        name_lines = textwrap.wrap(stu["name"], width=col_widths["نام"])
        name_lines = name_lines if name_lines else [""]
        for j, name_part in enumerate(name_lines):
            name_fixed = name_part.ljust(col_widths["نام"])
            line = row_format.format(i if j == 0 else "", name_fixed, stu["class"] if j == 0 else "",
                                     stu["avg"] if j == 0 else "")
            lines.append(line)
    return lines


# ------------------ توابع اصلی ساخت پیام ------------------

def build_report_card_message(report_data: Dict, student_name: str, period_name: str) -> str:
    """متن کامل کارنامه یک دوره را بر اساس داده‌های دریافتی می‌سازد."""
    lines = [f"📊 کارنامه شما: {student_name}", f"دوره: {period_name}", "━" * 20]

    for score_info in report_data.get("scores", []):
        score_txt = "—" if score_info['score'] is None else str(score_info['score'])
        desc_txt = score_info['description'] or ""
        lines.append(f"*{score_info['subject_name']:<12}* {score_info['coefficient']:<6} *{score_txt:<5}* {desc_txt}")

    avg = report_data.get("weighted_average")
    if avg is not None:
        lines.append(f"\n📌 معدل: {avg}")

    rank_info = report_data.get("ranks", {})
    if rank_info:
        lines.append("\n" + "رتبه شما" + "\n" + "━" * 20)
        rc = format_rank_with_total(rank_info.get("class_rank"), rank_info.get("class_count"))
        rg = format_rank_with_total(rank_info.get("grade_rank"), rank_info.get("grade_count"))
        rs = format_rank_with_total(rank_info.get("school_rank"), rank_info.get("school_count"))
        if rc: lines.append(f"🏅 رتبه در کلاس: {rc}")
        if rg: lines.append(f"🎓 رتبه در پایه: {rg}")
        if rs: lines.append(f"🏫 رتبه در مدرسه: {rs}")

    if "_@_error_@_" not in (response := get_chatbot_response(role="student", user_question=str(lines))):
        lines.append("\n\n" + " 🧠  مشاور:")
        lines.append(response)

    top_students = report_data.get("top_students", {})
    if top_students.get("class"):
        lines.append("\n🏅 نفرات برتر کلاس:")
        lines.extend(best_rank_format(top_students["class"]))
    if top_students.get("grade"):
        lines.append("\n🎓 نفرات برتر پایه:")
        lines.extend(best_rank_format(top_students["grade"]))
    if top_students.get("school"):
        lines.append("\n🏫 نفرات برتر مدرسه:")
        lines.extend(best_rank_format(top_students["school"]))

    return to_persian_digits("\n".join(lines))


def build_score_history_message(all_scores: List[Tuple], student_name: str) -> str:
    """متن کامل تاریخچه نمرات را می‌سازد."""
    score_text = ["📚 تاریخچه نمرات شما:\n",
                  f"{student_name} تاریخ: {jdatetime.datetime.now().strftime(' %Y/%m/%d ساعت: %H:%M')}"]
    last_scores = {}
    current_subject = ""

    for subject, period_name, score, desc, _, average_score, teacher_name in all_scores:
        if current_subject != subject:
            current_subject = subject
            score_text.extend(["\n" + "━" * 20, f"{get_subject_emoji(subject)} {subject} دبیر: *{teacher_name}*",
                               "نام دوره: نمره --> توضیحات دبیر"])

        delta_str = ""
        if score is not None:
            if subject in last_scores and last_scores[subject] is not None:
                delta = score - last_scores[subject]
                if delta > 0.01:
                    delta_str = f" (+{delta:.2f})"
                elif delta < -0.01:
                    delta_str = f" ({delta:.2f})"
            last_scores[subject] = score

        score_show = "—" if score is None else f"{score}{delta_str}"
        add_note = f" 👨‍🏫 {desc}" if desc else ""
        avg_str = f"{average_score:.2f}" if average_score is not None else "N/A"
        score_text.append(f"• {period_name}: {score_show} -->{add_note} --> میانگین کلاس: {avg_str}")

    return to_persian_digits("\n".join(score_text))


def prepare_data_for_radar_chart(all_scores: List[Tuple]) -> Dict:
    """داده‌های خام تاریخچه را برای نمودار راداری پردازش می‌کند."""
    period_data = {}
    RADAR_SUBJECTS = ['ریاضی', 'علوم', 'ورزش', 'هدیه']

    for subject, period, score, _, _, avg_score, _ in all_scores:
        if period not in period_data:
            period_data[period] = {
                'student': {subj: [] for subj in RADAR_SUBJECTS},
                'average': {subj: [] for subj in RADAR_SUBJECTS}
            }
        if subject in RADAR_SUBJECTS:
            if score is not None: period_data[period]['student'][subject].append(score)
            if avg_score is not None: period_data[period]['average'][subject].append(avg_score)

    processed_for_radar = {}
    for period, data in period_data.items():
        student_scores = data['student']
        avg_scores = data['average']

        # محاسبه ساحت‌ها برای دانش‌آموز
        s_math_sci = np.mean(student_scores['ریاضی'] + student_scores['علوم']) if student_scores['ریاضی'] or \
                                                                                  student_scores['علوم'] else 0
        s_sport = np.mean(student_scores['ورزش']) if student_scores['ورزش'] else 0
        s_hediyeh = np.mean(student_scores['هدیه']) if student_scores['هدیه'] else 0

        # محاسبه ساحت‌ها برای کلاس
        a_math_sci = np.mean(avg_scores['ریاضی'] + avg_scores['علوم']) if avg_scores['ریاضی'] or avg_scores[
            'علوم'] else 0
        a_sport = np.mean(avg_scores['ورزش']) if avg_scores['ورزش'] else 0
        a_hediyeh = np.mean(avg_scores['هدیه']) if avg_scores['هدیه'] else 0

        processed_for_radar[period] = {
            'student_scores': {
                "علمی": round(s_math_sci, 2), "زیستی بدنی": round(s_sport, 2),
                "اعتقادی عبادی": round(s_hediyeh, 2),
                "اجتماعی سیاسی": round(np.mean(student_scores['ریاضی']) if student_scores['ریاضی'] else 0, 2),
                "اقتصادی حرفه ای": round(np.mean(student_scores['علوم']) if student_scores['علوم'] else 0, 2),
                "هنری زیبائی": round(s_sport, 2)
            },
            'average_scores': {
                "علمی": round(a_math_sci, 2), "زیستی بدنی": round(a_sport, 2),
                "اعتقادی عبادی": round(a_hediyeh, 2),
                "اجتماعی سیاسی": round(np.mean(avg_scores['ریاضی']) if avg_scores['ریاضی'] else 0, 2),
                "اقتصادی حرفه ای": round(np.mean(avg_scores['علوم']) if avg_scores['علوم'] else 0, 2),
                "هنری زیبائی": round(a_sport, 2)
            }
        }
    return processed_for_radar