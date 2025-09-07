# schoolbot/services/score_service.py (✨ نسخه بهینه‌سازی شده)

import math
import tempfile
from typing import List, Tuple, Optional, Dict

import arabic_reshaper
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from adjustText import adjust_text
from bidi.algorithm import get_display
from matplotlib import rcParams
from cachetools import cached, TTLCache

from schoolbot.database.data_loader import get_connection

rcParams["font.family"] = "Tahoma"

cache = TTLCache(maxsize=200, ttl=300)

# توابع کمکی که بدون تغییر باقی می‌مانند
def get_school_id_by_student(student_id: int) -> Optional[int]:
    """
        گرفتن school_id مربوط به یک دانش‌آموز
        ورودی: student_id
        خروجی: school_id یا None
        """
    query = """
            SELECT g.school_id
            FROM students s
            JOIN classes c ON s.class_id = c.id
            JOIN grades g ON c.grade_id = g.id
            WHERE s.id = ?
        """
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute(query, (student_id,)).fetchone()
    return row[0] if row else None


def get_report_periods(school_id: int) -> List[Tuple[int, str]]:
    """
    دریافت لیست دوره‌های کارنامه برای یک مدرسه مشخص
    ورودی: school_id
    خروجی: [(id, name), ...]
    """
    query = """
        SELECT id, name 
        FROM report_periods 
        WHERE approved = 1 AND school_id = ?
        ORDER BY id DESC
    """
    with get_connection() as conn:
        cur = conn.cursor()
        periods = cur.execute(query, (school_id,)).fetchall()
    return periods


# ✨ بهینه‌سازی: تابع جامع برای دریافت تمام اطلاعات یک کارنامه در یک دوره خاص
@cached(cache)
def get_student_comprehensive_report(student_id: int, report_period_id: int) -> Dict:
    """
    یک تابع جامع و بهینه که تمام اطلاعات مورد نیاز برای کارنامه یک دانش‌آموز
    در یک دوره خاص را تنها با چند کوئری بهینه از دیتابیس استخراج می‌کند.

    خروجی:
    {
        "scores": [{"subject_name", "score", "description", "coefficient", "class_average"}, ...],
        "weighted_average": 18.5,
        "ranks": {"class_rank": 1, "class_count": 25, ...},
        "top_students": {"class": [...], "grade": [...], "school": [...]}
    }
    """
    report_data = {}

    # --- کوئری ۱: دریافت لیست نمرات دانش‌آموز به همراه میانگین کلاس برای هر درس ---
    # این کوئری با استفاده از یک ساب‌کوئری، میانگین کلاس را برای هر درس محاسبه و به نمره دانش‌آموز الصاق می‌کند.
    scores_query = """
        SELECT
            s.name AS subject_name,
            sc.score,
            sc.description,
            s.coefficient,
            (
                SELECT AVG(sc_avg.score)
                FROM scores sc_avg
                JOIN students st_avg ON sc_avg.student_id = st_avg.id
                WHERE st_avg.class_id = (SELECT class_id FROM students WHERE id = ?)
                  AND sc_avg.subject_id = sc.subject_id
                  AND sc_avg.report_period_id = ?
            ) AS class_average
        FROM scores sc
        JOIN subjects s ON sc.subject_id = s.id
        WHERE sc.student_id = ? AND sc.report_period_id = ?
        ORDER BY s.name;
    """
    with get_connection() as conn:
        cur = conn.cursor()
        scores_result = cur.execute(scores_query, (student_id, report_period_id, student_id, report_period_id)).fetchall()
        report_data["scores"] = [
            {"subject_name": r[0], "score": r[1], "description": r[2], "coefficient": r[3], "class_average": r[4]}
            for r in scores_result
        ]

    # --- کوئری ۲: محاسبه معدل، رتبه‌ها و تعداد کل دانش‌آموزان با یک کوئری ---
    # این کوئری قدرتمند با استفاده از CTE و Window Functions تمام محاسبات را در دیتابیس انجام می‌دهد.
    ranks_query = """
        WITH StudentAverages AS (
            -- ابتدا معدل وزنی همه دانش‌آموزان مدرسه در این دوره را محاسبه می‌کنیم
            SELECT
                st.id AS student_id,
                st.class_id,
                c.grade_id,
                SUM(sc.score * s.coefficient) / SUM(s.coefficient) AS weighted_average
            FROM scores sc
            JOIN subjects s ON sc.subject_id = s.id
            JOIN students st ON sc.student_id = st.id
            JOIN classes c ON st.class_id = c.id
            WHERE sc.report_period_id = ? AND sc.score IS NOT NULL
            GROUP BY st.id, st.class_id, c.grade_id
        ),
        RankContext AS (
            -- سپس با استفاده از توابع پنجره‌ای، رتبه و تعداد را در هر سطح محاسبه می‌کنیم
            SELECT
                student_id,
                weighted_average,
                RANK() OVER (PARTITION BY class_id ORDER BY weighted_average DESC) AS rank_class,
                COUNT(student_id) OVER (PARTITION BY class_id) AS count_class,
                RANK() OVER (PARTITION BY grade_id ORDER BY weighted_average DESC) AS rank_grade,
                COUNT(student_id) OVER (PARTITION BY grade_id) AS count_grade,
                RANK() OVER (ORDER BY weighted_average DESC) AS rank_school,
                COUNT(student_id) OVER () AS count_school
            FROM StudentAverages
        )
        -- در نهایت، فقط اطلاعات دانش‌آموز مورد نظر را انتخاب می‌کنیم
        SELECT * FROM RankContext WHERE student_id = ?;
    """
    with get_connection() as conn:
        cur = conn.cursor()
        rank_result = cur.execute(ranks_query, (report_period_id, student_id)).fetchone()
        if rank_result:
            report_data["weighted_average"] = round(rank_result[1], 2)
            report_data["ranks"] = {
                "class_rank": rank_result[2], "class_count": rank_result[3],
                "grade_rank": rank_result[4], "grade_count": rank_result[5],
                "school_rank": rank_result[6], "school_count": rank_result[7],
            }
        else:
            report_data["weighted_average"] = None
            report_data["ranks"] = {}


    # --- کوئری ۳: دریافت نفرات برتر ---
    # تابع get_top_students از قبل بهینه است، فقط باید فراخوانی شود.
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT c.id, c.grade_id FROM students s JOIN classes c ON s.class_id = c.id WHERE s.id = ?", (student_id,))
        ids = cur.fetchone()
        class_id, grade_id = (ids[0], ids[1]) if ids else (None, None)

    if class_id and grade_id:
        report_data["top_students"] = {
            "class": get_top_students(report_period_id, "class", class_id, 3),
            "grade": get_top_students(report_period_id, "grade", grade_id, 3),
            "school": get_top_students(report_period_id, "school", None, 3),
        }
    else:
        report_data["top_students"] = {}


    return report_data


def get_top_students(report_period_id: int, scope: str, scope_id: Optional[int] = None, top_n: int = 3) -> List[Dict]:
    """
        دریافت نفرات برتر بر اساس محدوده:
        scope = "class"  → بر اساس کلاس (نیاز به class_id)
        scope = "grade"  → بر اساس پایه (نیاز به grade_id)
        scope = "school" → کل مدرسه (نیازی به scope_id ندارد)
        خروجی: [ {id, name, class, avg}, ... ]
        """
    with get_connection() as conn:
        cur = conn.cursor()

        base_query = """
                SELECT st.id, st.name, c.name,
                       ROUND(SUM(sc.score * s.coefficient) / SUM(s.coefficient), 2) AS avg_score
                FROM scores sc
                JOIN subjects s ON sc.subject_id = s.id
                JOIN students st ON st.id = sc.student_id
                JOIN classes c ON st.class_id = c.id
                WHERE sc.report_period_id = ?
            """

        params = [report_period_id]

        if scope == "class" and scope_id:
            base_query += " AND st.class_id = ?"
            params.append(scope_id)
        elif scope == "grade" and scope_id:
            base_query += " AND st.class_id IN (SELECT id FROM classes WHERE grade_id = ?)"
            params.append(scope_id)

        base_query += """
                GROUP BY st.id
                ORDER BY avg_score DESC
                LIMIT ?
            """
        params.append(top_n)

        cur.execute(base_query, tuple(params))
        rows = cur.fetchall()

    return [{"id": r[0], "name": r[1], "class": r[2], "avg": r[3]} for r in rows]


# ✨ بهینه‌سازی: تابع جامع برای دریافت تمام تاریخچه عملکرد دانش‌آموز
@cached(cache)
def get_student_performance_history(student_id: int) -> Dict:
    """
    یک تابع جامع و بهینه که تمام تاریخچه نمرات و معدل‌های دانش‌آموز و کلاس
    را برای تمام دوره‌های تایید شده استخراج می‌کند.
    """
    history_data = {}
    class_id_query = "SELECT class_id FROM students WHERE id = ?"
    with get_connection() as conn:
        class_id = conn.execute(class_id_query, (student_id,)).fetchone()
        if not class_id: return {}
        class_id = class_id[0]

    # کوئری ۱: دریافت تاریخچه همه نمرات به همراه نام معلم و میانگین کلاس برای هر درس
    all_scores_query = """
        SELECT s.name, rp.name, sc.score, sc.description, s.coefficient,
               (SELECT AVG(sc_avg.score) FROM scores sc_avg JOIN students st_avg ON sc_avg.student_id = st_avg.id
                WHERE st_avg.class_id = ? AND sc_avg.subject_id = sc.subject_id AND sc_avg.report_period_id = sc.report_period_id) as class_subject_avg,
               t.name
        FROM scores sc
        JOIN subjects s ON sc.subject_id = s.id
        JOIN report_periods rp ON sc.report_period_id = rp.id
        LEFT JOIN teachers t ON s.teacher_id = t.id
        WHERE sc.student_id = ? AND rp.approved = 1
        ORDER BY s.name, rp.id;
    """
    with get_connection() as conn:
        scores_result = conn.execute(all_scores_query, (class_id, student_id)).fetchall()
        # ✨ بهینه‌سازی: تبدیل مستقیم به فرمت مورد نیاز generate_multi_subject_charts
        history_data["all_scores"] = scores_result

    # کوئری ۲: محاسبه معدل وزنی دانش‌آموز در تمام دوره‌ها
    student_avg_query = """
        SELECT rp.name, SUM(sc.score * s.coefficient) / SUM(s.coefficient)
        FROM scores sc
        JOIN subjects s ON s.id = sc.subject_id
        JOIN report_periods rp ON rp.id = sc.report_period_id
        WHERE sc.student_id = ? AND rp.approved = 1 AND sc.score IS NOT NULL
        GROUP BY rp.id, rp.name ORDER BY rp.id;
    """
    with get_connection() as conn:
        student_avg_result = conn.execute(student_avg_query, (student_id,)).fetchall()
        history_data["student_period_averages"] = {name: round(avg, 2) for name, avg in student_avg_result}

    # کوئری ۳: محاسبه معدل وزنی کلاس در تمام دوره‌ها
    class_avg_query = """
        SELECT rp.name, SUM(sc.score * s.coefficient) / SUM(s.coefficient)
        FROM scores sc
        JOIN subjects s ON s.id = sc.subject_id
        JOIN report_periods rp ON rp.id = sc.report_period_id
        JOIN students st ON st.id = sc.student_id
        WHERE st.class_id = ? AND rp.approved = 1 AND sc.score IS NOT NULL
        GROUP BY rp.id, rp.name ORDER BY rp.id;
    """
    with get_connection() as conn:
        class_avg_result = conn.execute(class_avg_query, (class_id,)).fetchall()
        history_data["class_period_averages"] = {name: round(avg, 2) for name, avg in class_avg_result}

    return history_data



