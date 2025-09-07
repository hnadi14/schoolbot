from datetime import datetime
from schoolbot.database.data_loader import get_connection,db_lock


# ======= دوره‌ها =======
def create_report_period(name: str, school_id: int):
    with db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            start_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                "INSERT INTO report_periods (name, start_date, school_id) VALUES (?, ?, ?)",
                (name, start_date, school_id)
            )



def get_report_periods():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM report_periods")
        return cursor.fetchall()


def get_report_period_by_name(name):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM report_periods WHERE name = ?", (name,))
        return cursor.fetchone()


def get_all_report_periods(user_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, approved FROM report_periods WHERE school_id=? ORDER BY start_date DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        return [{"id": r[0], "name": r[1], "approved": bool(r[2])} for r in rows]


def toggle_report_period_approval(period_id):
    with db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT approved FROM report_periods WHERE id=?", (period_id,))
            row = cursor.fetchone()
            if row:
                new_status = 0 if row[0] else 1
                cursor.execute("UPDATE report_periods SET approved=? WHERE id=?", (new_status, period_id))
                conn.commit()
                return bool(new_status)
    return None


# ======= کلاس‌ها =======
def get_all_classes():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM classes")
        return cursor.fetchall()


def get_class_by_id(class_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM classes WHERE id = ?", (class_id,))
        return cursor.fetchone()


# ======= درس‌ها =======
def get_all_subjects():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, class_id, teacher_id FROM subjects")
        return cursor.fetchall()


def get_subject_by_name(name):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, class_id, teacher_id FROM subjects WHERE name = ?", (name,))
        return cursor.fetchone()


def get_subjects_by_teacher(teacher_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, class_id FROM subjects WHERE teacher_id = ? ORDER BY name", (teacher_id,))
        return cursor.fetchall()


# ======= دانش‌آموزان =======
def get_students_by_class(class_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM students WHERE class_id = ? ORDER BY id", (class_id,))
        return cursor.fetchall()


# ======= ثبت نمرات =======
def save_student_score(student_id, subject_id, report_period_id, score, description=None):
    with db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM scores WHERE student_id=? AND subject_id=? AND report_period_id=?",
                (student_id, subject_id, report_period_id)
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE scores SET score=?, description=? WHERE id=?",
                    (score, description, row[0])
                )
            else:
                cursor.execute(
                    "INSERT INTO scores (student_id, subject_id, report_period_id, score, description) VALUES (?, ?, ?, ?, ?)",
                    (student_id, subject_id, report_period_id, score, description)
                )



def get_student_score(student_id, subject_id, report_period_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT score, description FROM scores WHERE student_id=? AND subject_id=? AND report_period_id=?",
            (student_id, subject_id, report_period_id)
        )
        row = cursor.fetchone()
        if row:
            return {"score": row[0], "description": row[1]}
        return None


def get_students_scores_by_class(class_id, subject_id, report_period_id):
    """
    دریافت لیست دانش‌آموزان یک کلاس به همراه نمره و توضیح
    در یک درس مشخص و یک دوره کارنامه (بهینه با یک کوئری)

    خروجی:
    [
        {"id": 1, "name": "علی رضایی", "score": 18.5, "description": "خیلی خوب"},
        {"id": 2, "name": "مینا احمدی", "score": None, "description": None},
        ...
    ]
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT s.id, s.name, sc.score, sc.description
            FROM students s
            LEFT JOIN scores sc 
                ON s.id = sc.student_id 
               AND sc.subject_id = ? 
               AND sc.report_period_id = ?
            WHERE s.class_id = ?
            ORDER BY s.id
        """
        cursor.execute(query, (subject_id, report_period_id, class_id))
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "name": row[1],
                "score": row[2],
                "description": row[3]
            })

        return results


def get_all_user_messages():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, role, id_bale, user_id FROM user_message")
        rows = cursor.fetchall()
        return rows


def get_all_user_messages_user_id_role(user_id, role):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
               SELECT id_bale 
               FROM user_message
               WHERE user_id = ? AND role = ?
           """, (user_id, role))
        rows = cursor.fetchall()
        return rows


def get_scores_completion_status(report_period_id: int, school_id: int):
    """
    وضعیت ثبت نمرات برای هر درسِ هر کلاس در یک دوره مشخص.
    شامل نام معلم، میانگین نمرات و مرتب‌سازی بر اساس نام معلم.
    """

    with get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT
                g.id        AS grade_id,
                g.name      AS grade_name,
                c.id        AS class_id,
                c.name      AS class_name,
                sub.id      AS subject_id,
                sub.name    AS subject_name,
                t.id        AS teacher_id,
                t.name      AS teacher_name,
                COUNT(DISTINCT st.id) AS total_students,
                SUM(CASE WHEN sc.id IS NOT NULL THEN 1 ELSE 0 END) AS scored_count,
                AVG(sc.score) AS avg_score
            FROM grades g
            JOIN classes  c   ON c.grade_id = g.id
            JOIN subjects sub ON sub.class_id = c.id
            JOIN teachers t   ON t.id = sub.teacher_id
            LEFT JOIN students st ON st.class_id = c.id
            LEFT JOIN scores   sc ON sc.student_id = st.id
                                  AND sc.subject_id = sub.id
                                  AND sc.report_period_id = ?
            WHERE g.school_id = ?
            GROUP BY g.id, g.name, c.id, c.name, sub.id, sub.name, t.id, t.name
            ORDER BY t.name, g.name, c.name, sub.name
        """
        cursor.execute(query, (report_period_id, school_id))
        rows = cursor.fetchall()

        results = []
        for (grade_id, grade_name, class_id, class_name,
             subject_id, subject_name, teacher_id, teacher_name,
             total_students, scored_count, avg_score) in rows:

            total = int(total_students or 0)
            scored = int(scored_count or 0)

            if total == 0:
                status = "بدون دانش‌آموز"
            else:
                status = "کامل" if scored == total else "ناقص"

            results.append({
                "grade_id": grade_id,
                "grade": grade_name,
                "class_id": class_id,
                "class": class_name,
                "subject_id": subject_id,
                "subject": subject_name,
                "teacher_id": teacher_id,
                "teacher": teacher_name,
                "total": total,
                "scored": scored,
                "status": status,
                "avg_score": float(avg_score) if avg_score is not None else None
            })

        return results
