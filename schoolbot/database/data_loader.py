import pandas as pd
# from schoolbot.auth.auth import hash_password # فرض بر این است که این ماژول در دسترس است
import hashlib
import os
import sqlite3
import threading

# --- تابع هش کردن رمز عبور (جایگزین schoolbot.auth.auth) ---
def hash_password(password):
    """رمز عبور را با استفاده از SHA256 هش می‌کند."""
    return hashlib.sha256(password.encode()).hexdigest()

# ---------- قفل سراسری برای دسترسی به دیتابیس ----------
# این قفل تضمین می‌کند که عملیات نوشتن به صورت همزمان انجام نشود و از تداخل جلوگیری می‌کند.
db_lock = threading.Lock()

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "school.db")

def get_connection():
    """یک اتصال جدید به دیتابیس SQLite برمی‌گرداند."""
    # timeout برای جلوگیری از قفل شدن دیتابیس در زمان دسترسی‌های همزمان است.
    return sqlite3.connect(DB_PATH, timeout=10)


# 🔑 هش کردن رمز پیش‌فرض
DEFAULT_PASSWORD = hash_password("1111")


def create_tables():
    """جداول مورد نیاز در دیتابیس را ایجاد می‌کند."""
    # قبل از انجام عملیات، قفل را به دست می‌آوریم.
    with db_lock:
        # استفاده از 'with' تضمین می‌کند که اتصال به طور خودکار بسته می‌شود.
        with get_connection() as conn:
            cursor = conn.cursor()

            # ---------- جدول مدارس ----------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS schools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                manager_name TEXT,
                username TEXT UNIQUE,
                password TEXT
            )
            """)

            # ---------- جدول پایه‌ها ----------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                school_id INTEGER NOT NULL,
                UNIQUE(name, school_id),
                FOREIGN KEY(school_id) REFERENCES schools(id)
            )
            """)

            # ---------- جدول کلاس‌ها ----------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                grade_id INTEGER NOT NULL,
                UNIQUE(name, grade_id),
                FOREIGN KEY(grade_id) REFERENCES grades(id)
            )
            """)

            # ---------- جدول معلم‌ها ----------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT UNIQUE,
                password TEXT,
                school_id INTEGER,
                FOREIGN KEY(school_id) REFERENCES schools(id)
            )
            """)

            # ---------- جدول دانش‌آموزان ----------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT UNIQUE,
                password TEXT,
                class_id INTEGER,
                FOREIGN KEY(class_id) REFERENCES classes(id)
            )
            """)

            # ---------- جدول دروس ----------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                class_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                coefficient INTEGER DEFAULT 1,
                FOREIGN KEY(class_id) REFERENCES classes(id),
                FOREIGN KEY(teacher_id) REFERENCES teachers(id)
            )
            """)

            # دوره‌های کارنامه (با ارتباط به مدرسه)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS report_periods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_id INTEGER NOT NULL,          -- ارتباط با مدرسه
                name TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                approved INTEGER DEFAULT 0,          -- 0 = عدم تأیید، 1 = تأیید
                FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
            )
            """)

            # نمرات دانش اموزان
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                subject_id INTEGER,
                report_period_id INTEGER,
                score REAL,
                description TEXT,
                FOREIGN KEY (student_id) REFERENCES students(id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id),
                FOREIGN KEY (report_period_id) REFERENCES report_periods(id)
            )""")

            # ---------- جدول پیام‌های کاربر ----------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                id_bale TEXT NOT NULL,
                user_id INTEGER NOT NULL
            )
            """)
            # 'with' به طور خودکار تغییرات را commit می‌کند.
    print("✅ جداول با موفقیت ایجاد یا بررسی شدند.")


def load_data_from_excel(file_path="school_data.xlsx"):
    """داده‌ها را از فایل اکسل خوانده و در دیتابیس بارگذاری می‌کند."""
    # قبل از انجام عملیات، قفل را به دست می‌آوریم تا از تداخل جلوگیری شود.
    with db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ---------- شیت مدارس و مدیران ----------
            schools_df = pd.read_excel(file_path, sheet_name="مدرسه و مدیر", engine="openpyxl")
            for _, row in schools_df.iterrows():
                school_name = str(row["نام مدرسه"]).strip()
                manager_name = str(row["نام مدیر"]).strip()
                manager_username = str(row["نام کاربری"]).strip()

                cursor.execute("""
                    INSERT OR IGNORE INTO schools (name, manager_name, username, password)
                    VALUES (?, ?, ?, ?)
                """, (school_name, manager_name, manager_username, DEFAULT_PASSWORD))

            cursor.execute("SELECT id FROM schools WHERE name=?", (school_name,))
            school_id_result = cursor.fetchone()
            if not school_id_result:
                print(f"❌ مدرسه با نام '{school_name}' یافت نشد. بارگذاری داده‌ها متوقف شد.")
                return
            school_id = school_id_result[0]

            # ---------- شیت پایه‌ها و کلاس‌ها ----------
            grades_df = pd.read_excel(file_path, sheet_name="پایه ها و کلاس ها", engine="openpyxl")
            for _, row in grades_df.iterrows():
                grade_name = str(row["پایه"]).strip()
                cursor.execute("INSERT OR IGNORE INTO grades (name, school_id) VALUES (?, ?)", (grade_name, school_id))

            for _, row in grades_df.iterrows():
                grade_name = str(row["پایه"]).strip()
                class_name = str(row["کلاس"]).strip()
                cursor.execute("SELECT id FROM grades WHERE name=? AND school_id=?", (grade_name, school_id))
                grade_id = cursor.fetchone()[0]
                cursor.execute("INSERT OR IGNORE INTO classes (name, grade_id) VALUES (?, ?)", (class_name, grade_id))

            # ---------- شیت دروس و معلم‌ها ----------
            subjects_df = pd.read_excel(file_path, sheet_name="درس ها و معلم ها", engine="openpyxl")
            for _, row in subjects_df.iterrows():
                subject_name = str(row["درس ها"]).strip()
                class_name = str(row["کلاس"]).strip()
                teacher_name = str(row["معلم"]).strip()
                teacher_username = str(row["نام کاربری"]).strip()
                coef = int(row["ضریب درس"]) if pd.notna(row["ضریب درس"]) else 1

                cursor.execute("SELECT id FROM teachers WHERE username=?", (teacher_username,))
                t = cursor.fetchone()
                if t is None:
                    cursor.execute("""
                        INSERT INTO teachers (name, username, password, school_id)
                        VALUES (?, ?, ?, ?)
                    """, (teacher_name, teacher_username, DEFAULT_PASSWORD, school_id))
                    teacher_id = cursor.lastrowid
                else:
                    teacher_id = t[0]

                cursor.execute("""
                    SELECT classes.id FROM classes
                    JOIN grades ON grades.id = classes.grade_id
                    WHERE classes.name=? AND grades.school_id=?
                """, (class_name, school_id))
                c = cursor.fetchone()
                if c is None:
                    print(f"⚠️ کلاس «{class_name}» برای درس «{subject_name}» یافت نشد.")
                    continue
                class_id = c[0]

                cursor.execute("""
                    SELECT id FROM subjects WHERE name=? AND class_id=? AND teacher_id=?
                """, (subject_name, class_id, teacher_id))
                if cursor.fetchone() is None:
                    cursor.execute("""
                        INSERT INTO subjects (name, class_id, teacher_id, coefficient)
                        VALUES (?, ?, ?, ?)
                    """, (subject_name, class_id, teacher_id, coef))

            # ---------- شیت دانش‌آموزان ----------
            students_df = pd.read_excel(file_path, sheet_name="دانش اموزان", engine="openpyxl")
            for _, row in students_df.iterrows():
                student_name = str(row["نام و نام خانوادگی"]).strip()
                class_name = str(row["کلاس"]).strip()
                student_username = str(row["نام کاربری"]).strip()

                cursor.execute("""
                    SELECT classes.id FROM classes
                    JOIN grades ON grades.id = classes.grade_id
                    WHERE classes.name=? AND grades.school_id=?
                """, (class_name, school_id))
                c = cursor.fetchone()
                if c is None:
                    print(f"⚠️ کلاس «{class_name}» برای دانش‌آموز «{student_name}» یافت نشد.")
                    continue
                class_id = c[0]

                cursor.execute("""
                    INSERT OR IGNORE INTO students (name, username, password, class_id)
                    VALUES (?, ?, ?, ?)
                """, (student_name, student_username, DEFAULT_PASSWORD, class_id))

            # تمام تغییرات در پایان این بلاک به صورت یکجا commit می‌شوند.
        print("✅ داده‌ها با موفقیت از اکسل به دیتابیس منتقل شدند.")


if __name__ == "__main__":
    # اطمینان از وجود فایل اکسل قبل از اجرای توابع
    if os.path.exists("school_data.xlsx"):
        create_tables()
        load_data_from_excel()
    else:
        print("❌ فایل 'school_data.xlsx' یافت نشد. لطفاً فایل را در مسیر درست قرار دهید.")
