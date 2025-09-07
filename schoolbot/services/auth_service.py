# services/auth_service.py

from schoolbot.auth.auth import verify_password, hash_password
from schoolbot.database.data_loader import get_connection


def check_login(username, password, role):
    """
    بررسی ورود کاربر بر اساس نقش (مدیر، معلم، دانش‌آموز)
    خروجی: (موفق/ناموفق, user_id یا None, name یا None)
    """
    table = {"manager": "schools", "teacher": "teachers", "student": "students"}[role]

    with get_connection() as conn:  # کانکشن مخصوص thread جاری
        cursor = conn.cursor()  # فقط خواندن، نیازی به قفل نیست
        cursor.execute(
            f"SELECT id, password, name FROM {table} WHERE username=?",
            (username,),
        )
        res = cursor.fetchone()

        if not res:
            return False, None, None

        user_id, db_password, name = res
        # return db_password == password, user_id, name
        # 🔑 بررسی رمز با bcrypt
        if verify_password(password, db_password):
            return True, user_id, name
        else:
            return False, None, None


def change_password(user_id, new_password, role, id_bale):
    """
    تغییر رمز عبور کاربر با نقش مشخص
    """
    table = {"manager": "schools", "teacher": "teachers", "student": "students"}[role]

    with get_connection() as conn:
        hashed_password = hash_password(new_password)

        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE {table} SET password=? WHERE id=?",
            (hashed_password, user_id),
        )
        conn.commit()

        # بررسی اینکه آیا رکورد با هر سه فیلد وجود دارد
        cursor.execute("""
                    SELECT id, id_bale FROM user_message
                    WHERE role = ? AND user_id = ?
                """, (role, user_id))

        row = cursor.fetchone()

        if row:
            existing_id_bale = row[1]
            if existing_id_bale != id_bale:
                # آپدیت id_bale در صورت تفاوت
                cursor.execute("""
                            UPDATE user_message
                            SET id_bale = ?
                            WHERE id = ?
                        """, (id_bale, row[0]))
                conn.commit()
            # اگر id_bale یکی بود، کاری انجام نمی‌دهیم
        else:
            # درج رکورد جدید
            cursor.execute("""
                        INSERT INTO user_message (role, id_bale, user_id)
                        VALUES (?, ?, ?)
                    """, (role, id_bale, user_id))
            conn.commit()


def get_all_user_data():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_data")
        rows = cursor.fetchall()
        return rows
