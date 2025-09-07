import sqlite3

import numpy as np
from typing import List, Tuple, Dict, Optional
import math
import tempfile

import pandas as pd
import arabic_reshaper
from bidi.algorithm import get_display
import matplotlib.pyplot as plt
from matplotlib import rcParams

from schoolbot.database.data_loader import get_connection


def get_teacher_school_id(teacher_id: int) -> Optional[int]:
    """
    گرفتن school_id یک معلم بر اساس id
    بازگرداندن None اگر معلم پیدا نشود
    """
    query = "SELECT school_id FROM teachers WHERE id = ?"
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute(query, (teacher_id,)).fetchone()
    return row[0] if row else None


def get_report_periods_teachers(school_id: int) -> List[Tuple[int, str]]:
    """
    دریافت لیست دوره‌های کارنامه (نسخه‌ی معلم‌ها)
    خروجی: [(id, name), ...]
    """
    query = "SELECT id, name FROM report_periods where school_id=? ORDER BY id DESC"
    with get_connection() as conn:
        cur = conn.cursor()
        periods = cur.execute(query, (school_id,)).fetchall()
    return periods
