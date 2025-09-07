
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


rcParams["font.family"] = "Tahoma"


def generate_multi_subject_charts(all_scores: List[Tuple], name: str = "") -> List[str]:
    """
    نسخه نهایی و حرفه‌ای برای ترسیم نمودارها با قابلیت‌های تحلیلی و جلوگیری از همپوشانی متن.
    """

    def fix_farsi(text: str) -> str:
        return get_display(arabic_reshaper.reshape(str(text)))

    # --- تعریف ثابت‌ها برای رنگ‌ها و استایل ---

    SUBJECT_COLORS = [
        'orange', 'deepskyblue', 'purple', 'blue'
    ]
    AVERAGE_COLOR = 'grey'
    POSITIVE_FILL_COLOR = 'mediumseagreen'
    NEGATIVE_FILL_COLOR = 'lightcoral'

    df = pd.DataFrame(
        all_scores,
        columns=["subject", "period_name", "score", "desc", "coefficient", "average_score", "teacher_name"]
    )
    df['score'] = pd.to_numeric(df['score'], errors='coerce')
    df['average_score'] = pd.to_numeric(df['average_score'], errors='coerce')
    df.dropna(subset=['score', 'average_score'], inplace=True)

    if df.empty:
        return []

    df["period_name"] = df["period_name"].apply(fix_farsi)
    subjects = list(df["subject"].unique())
    group_size = 9
    n_groups = math.ceil(len(subjects) / group_size)
    chart_files: List[str] = []

    for g in range(n_groups):
        start = g * group_size
        end = start + group_size
        group_subjects = subjects[start:end]

        fig, axes = plt.subplots(3, 3, figsize=(24, 18), sharey=True)
        axes = np.ravel(axes)

        for i, subj in enumerate(group_subjects):
            ax = axes[i]

            subj_data = df[df["subject"] == subj]
            student_scores = subj_data["score"]
            average_scores = subj_data["average_score"]
            periods = subj_data["period_name"]

            subject_color = SUBJECT_COLORS[i % len(SUBJECT_COLORS)]

            # رسم خطوط اصلی
            ax.plot(periods, student_scores, color=subject_color, marker='o', linewidth=2.5,
                    label=fix_farsi("نمره دانش‌آموز"), zorder=10)
            ax.plot(periods, average_scores, color=AVERAGE_COLOR, marker='x', linestyle='--',
                    label=fix_farsi("میانگین کلاس"), zorder=5)

            # رنگ کردن ناحیه بین دو نمودار
            ax.fill_between(periods, student_scores, average_scores, where=(student_scores >= average_scores),
                            color=POSITIVE_FILL_COLOR, alpha=0.3, interpolate=True)
            ax.fill_between(periods, student_scores, average_scores, where=(student_scores < average_scores),
                            color=NEGATIVE_FILL_COLOR, alpha=0.3, interpolate=True)

            # --- جدید: آماده‌سازی متن‌ها برای adjust_text ---
            texts = []
            bbox_props = dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.7, edgecolor='none')

            # افزودن متن نمرات دانش‌آموز به لیست
            for x, y in zip(periods, student_scores):
                texts.append(ax.text(x, y, f"{y:.1f}", ha='right', va='top',
                                     fontsize=9, fontweight="bold", color=subject_color, bbox=bbox_props, zorder=20))

            # افزودن متن میانگin کلاس به لیست
            for x, y in zip(periods, average_scores):
                texts.append(ax.text(x, y, f"{y:.1f}", ha='left', va='bottom',
                                     fontsize=7, fontweight="bold", color=AVERAGE_COLOR, bbox=bbox_props, zorder=20))

            # فراخوانی adjust_text برای جابجایی هوشمند متن‌ها
            adjust_text(texts, ax=ax, arrowprops=dict(arrowstyle='-', color='grey', lw=0.5))

            # تنظیمات ظاهری نمودار
            ax.set_title(fix_farsi(subj), fontsize=14, fontweight="bold")
            ax.grid(axis="y", linestyle="--", alpha=0.7)
            # یک مکان مشخص مانند 'بالا راست' را تعیین کنید
            ax.legend(loc='lower right')
            ax.tick_params(axis='x', rotation=15)
            ax.set_ylim(0, 21)  # کمی فضای بیشتر برای اعداد
            ax.set_yticks([0, 5, 10, 15, 20])

        for i in range(len(group_subjects), len(axes)):
            axes[i].set_visible(False)

        fig.suptitle(fix_farsi(f"تحلیل روند نمرات: {name} (درس های گروه {g + 1})"), fontsize=18, fontweight="bold")
        plt.tight_layout(rect=[0, 0, 1, 0.96])

        tmp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        plt.savefig(tmp_file.name, bbox_inches="tight", dpi=150)
        plt.close(fig)
        chart_files.append(tmp_file.name)

    return chart_files

def generate_combined_chart(student_scores, name, report_name):
    try:
        def fix_farsi(text: str) -> str:
            return get_display(arabic_reshaper.reshape(text))

        # ✨ بهینه‌سازی: داده‌ها اکنون در قالب دیکشنری دریافت می‌شوند
        subjects = [fix_farsi(s['subject_name']) for s in student_scores]
        student_values = [float(s['score']) if s['score'] is not None else 0 for s in student_scores]
        class_avg_values = [float(s['class_average']) if s['class_average'] is not None else 0 for s in student_scores]

        x = np.arange(len(subjects))
        plt.figure(figsize=(14, 7))

        bar_colors = ['mediumseagreen' if s_val > c_val else 'tomato' if s_val < c_val else 'lightgray' for s_val, c_val
                      in zip(student_values, class_avg_values)]

        bars = plt.bar(x, class_avg_values, color=bar_colors, alpha=0.8, width=0.6, label=fix_farsi("میانگین کلاس"))
        plt.plot(x, student_values, marker='o', markersize=9, linestyle='-', color='royalblue', linewidth=2.5,
                 label=fix_farsi("نمره شما"), zorder=5)

        for i, b in enumerate(bars):
            h = b.get_height()
            plt.text(b.get_x() + b.get_width() / 2, h * 0.1, f"{h:.1f}", ha='center', va='bottom', fontsize=9,
                     color="white", fontweight="bold")
        for xi, y in zip(x, student_values):
            plt.text(xi, y + 0.5, f"{y:.1f}", ha='center', va='bottom', fontsize=9, color="blue")

        plt.xticks(x, subjects, rotation=0, fontsize=11)
        plt.yticks([0, 5, 10, 15, 20], fontsize=11)
        plt.ylim(0, 21)
        plt.xlabel(fix_farsi("دروس"), fontsize=13)
        plt.ylabel(fix_farsi("نمره"), fontsize=13)
        plt.title(fix_farsi(f" مقایسه نمرات {name} با میانگین کلاس دوره:  {report_name} "), fontsize=15,
                  fontweight="bold")
        plt.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
        for spine in ["top", "right"]: plt.gca().spines[spine].set_visible(False)
        plt.legend(fontsize=11)

        tmp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        plt.savefig(tmp_file.name, bbox_inches="tight", dpi=150)
        plt.close()
        return tmp_file.name
    except Exception as e:
        logger.error("❌ خطا در تولید نمودار مقایسه: %s", str(e))
        return None

def generate_radar_chart(data: Dict[str, Dict[str, Dict[str, float]]], name: str) -> Optional[str]:
    """
    برای هر دوره یک نمودار راداری برای دانش‌آموز و میانگین کلاس تولید کرده
    و همه را در یک تصویر نمایش می‌دهد.
    """

    def fix_farsi(text: str) -> str:
        return get_display(arabic_reshaper.reshape(str(text)))

    if not data or not list(data.values()):
        return None

    # استخراج لیبل‌ها از اولین آیتم
    first_period_data = list(data.values())[0]
    labels = list(first_period_data['student_scores'].keys())
    # ✨ تغییر اصلی اینجاست
    # برای دو برچسب خاص، یک خط جدید در ابتدا اضافه می‌کنیم تا فاصله بگیرند
    farsi_labels = [
        fix_farsi('\n\n' + label) if label in ['علمی', 'اجتماعی سیاسی'] else fix_farsi(label)
        for label in labels
    ]

    num_vars = len(labels)

    color_map = {
        'زیستی بدنی': 'green', 'علمی': 'deepskyblue', 'اعتقادی عبادی': 'orange',
        'اجتماعی سیاسی': 'purple', 'اقتصادی حرفه ای': 'red', 'هنری زیبائی': 'blue'
    }

    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1]

    num_plots = len(data)
    cols = int(np.ceil(np.sqrt(num_plots)))
    rows = int(np.ceil(num_plots / cols))

    fig, axes = plt.subplots(figsize=(cols * 6, rows * 6), nrows=rows, ncols=cols,
                             subplot_kw=dict(polar=True))
    axes = np.ravel(axes)

    for i, (period_name, period_scores) in enumerate(data.items()):
        ax = axes[i]

        student_scores = period_scores['student_scores']
        average_scores = period_scores['average_scores']

        # --- آماده‌سازی داده‌های دانش‌آموز ---
        values_student = [student_scores.get(label, 0) for label in labels]
        closed_values_student = values_student + values_student[:1]

        # --- آماده‌سازی داده‌های میانگین کلاس ---
        values_avg = [average_scores.get(label, 0) for label in labels]
        closed_values_avg = values_avg + values_avg[:1]

        # --- رسم نمودار دانش‌آموز (خط ممتد و ناحیه پر شده) ---
        ax.plot(angles, closed_values_student, color='royalblue', linewidth=2, label=fix_farsi('نمره دانش‌آموز'))
        ax.fill(angles, closed_values_student, color='royalblue', alpha=0.2)

        # --- رسم نمودار میانگین کلاس (خط‌چین) ---
        ax.plot(angles, closed_values_avg, color='darkorange', linewidth=2, linestyle='--',
                label=fix_farsi('میانگین کلاس'))

        # نقاط رنگی و متن فقط برای نمرات دانش‌آموز (برای جلوگیری از شلوغی)
        plot_colors = [color_map.get(label, 'gray') for label in labels]
        ax.scatter(angles[:-1], values_student, c=plot_colors, s=80, zorder=10)


        for j, (angle, value) in enumerate(zip(angles[:-1], values_student)):
            label_name = labels[j]
            ha_align = 'center'  # حالت پیش‌فرض

            if label_name == 'علمی':
                ha_align = 'left'  # متن به سمت راست نقطه منتقل می‌شود
            elif label_name == 'اجتماعی سیاسی':
                ha_align = 'right'  # متن به سمت چپ نقطه منتقل می‌شود

            # فاصله عمودی (value + 1.8) و سایر پارامترها ثابت باقی مانده‌اند
            ax.text(angle, value + 1.8, f'{value}', ha=ha_align, va='center', fontweight='bold', color='black')

        ax.set_yticks([0, 5, 10, 15, 20])
        ax.set_ylim(0, 20)

        ax.set_thetagrids(np.degrees(angles[:-1]), farsi_labels)
        ax.set_title(fix_farsi(period_name), y=1.15, fontdict={'fontsize': 14})
        ax.tick_params(axis='x', pad=15)

        # جدید: افزودن راهنمای نمودار (legend)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))

    for i in range(num_plots, len(axes)):
        axes[i].set_visible(False)

    fig.suptitle(fix_farsi(f"نمودار راداری عملکرد: {name}"), fontsize=18, y=0.98)
    plt.tight_layout(pad=3.0)

    tmp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    plt.savefig(tmp_file.name, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return tmp_file.name


def generate_average_trend_chart(averages: Dict[str, float], name: str,
                                 class_averages_for_all_periods: Optional[Dict[str, float]] = None) -> Optional[str]:
    if not averages:
        return None

    def fix_farsi(text: str) -> str:
        return get_display(arabic_reshaper.reshape(text))

    periods = list(averages.keys())
    scores = list(averages.values())
    x_pos = np.arange(len(periods))
    scores_np = np.array(scores)

    plt.figure(figsize=(12, 7))
    ax = plt.gca()
    # texts = [] <-- حذف شد

    bbox_props = dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8, edgecolor='none')

    if class_averages_for_all_periods:
        class_scores = [class_averages_for_all_periods.get(p, np.nan) for p in periods]
        class_scores_np = np.array(class_scores)

        plt.fill_between(x_pos, scores_np, class_scores_np, where=(scores_np >= class_scores_np), color='#98d898',
                         alpha=0.5, interpolate=True, label=fix_farsi("بالاتر از میانگین"))
        plt.fill_between(x_pos, scores_np, class_scores_np, where=(scores_np < class_scores_np), color='#f7a7a4',
                         alpha=0.6, interpolate=True, label=fix_farsi("پایین‌تر از میانگین"))
        plt.plot(x_pos, class_scores_np, '--', color='#ff7f0e', linewidth=2.5, label=fix_farsi("میانگین کلاس"))

        for i, class_avg in enumerate(class_scores_np):
            if not np.isnan(class_avg):
                plt.text(x_pos[i], class_avg, f'{class_avg:.2f}', ha='left', va="top", fontweight='bold',
                         fontsize=8, color='#b35900',
                         bbox=bbox_props, zorder=20) # texts.append() حذف شد

    else:
        plt.fill_between(x_pos, scores, color="skyblue", alpha=0.2, zorder=1)

    plt.plot(x_pos, scores, marker='o', markersize=9, linestyle='none', color='royalblue', zorder=5)

    if len(scores) > 1:
        for i in range(1, len(scores)):
            segment_color = 'royalblue'
            delta = scores[i] - scores[i - 1]
            if delta > 0.01:
                segment_color = 'green'
            elif delta < -0.01:
                segment_color = 'red'
            plt.plot([x_pos[i - 1], x_pos[i]], [scores[i - 1], scores[i]], color=segment_color, linewidth=3.5,
                     solid_capstyle='round', zorder=3)
            sign = "+" if delta > 0 else ""
            if abs(delta) > 0.01:
                plt.text(x_pos[i], scores[i], f'({sign}{delta:.2f})', ha='right', va="bottom", fontweight='bold',
                         fontsize=8, color=segment_color,
                         bbox=bbox_props, zorder=20) # texts.append() حذف شد

    for i, score in enumerate(scores):
        plt.text(x_pos[i], score, f'{score}', ha='left', va="top", fontweight='bold', color='navy',
                 fontsize=10,
                 bbox=bbox_props, zorder=20) # texts.append() حذف شد

    if len(scores) > 1:
        z = np.polyfit(x_pos, scores, 1)
        p = np.poly1d(z)
        plt.plot(x_pos, p(x_pos), "--", linewidth=2, color='gray', alpha=0.8, label=fix_farsi("روند کلی دانش‌آموز"))
        slope = z[0]
        if slope > 0.1:
            trend_text, trend_color = fix_farsi("روند کلی: صعودی"), 'darkgreen'
        elif slope < -0.1:
            trend_text, trend_color = fix_farsi("روند کلی: نزولی"), 'darkred'
        else:
            trend_text, trend_color = fix_farsi("روند کلی: ثابت"), 'darkblue'
        ax.text(0.04, 0.04, trend_text, transform=ax.transAxes, fontsize=12, verticalalignment='top', color='white',
                bbox=dict(boxstyle='round,pad=0.4', fc=trend_color, alpha=0.8))

    ax.set_facecolor('#f9f9f9')
    plt.title(fix_farsi(f"تحلیل پیشرفت تحصیلی {name}"), fontsize=18, fontweight='bold', color='#333333')
    plt.xlabel(fix_farsi("دوره‌های تحصیلی"), fontsize=14, color='#555555')
    plt.ylabel(fix_farsi("معدل"), fontsize=14, color='#555555')
    plt.xticks(x_pos, [fix_farsi(p) for p in periods], rotation=0, fontsize=12)
    plt.yticks(np.arange(0, 21, 2), fontsize=11)
    plt.ylim(bottom=-0.5)
    for spine in ["top", "right"]: ax.spines[spine].set_visible(False)
    plt.legend(fontsize=12, loc='lower right')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout(pad=1.5)

    try:
        tmp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        plt.savefig(tmp_file.name, bbox_inches="tight", dpi=150)
        plt.close()
        return tmp_file.name
    except Exception as e:
        print(f"Error saving chart: {e}")
        return None




