import jdatetime

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import logging

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

# # 🎨 ست کردن فونت پیش‌فرض فارسی (در صورت نصب بودن روی سیستم)
# rcParams['font.family'] = 'Tahoma'  # می‌تونی "Vazir" یا "IRANSans" هم بذاری

# کتابخانه‌های فارسی‌سازی را اینجا import می‌کنیم
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    print("WARNING: 'arabic_reshaper' or 'python-bidi' not found. Farsi text will not be displayed correctly.")
    print("Install them using: pip install arabic_reshaper python-bidi")


    # توابع جایگزین تعریف می‌کنیم تا برنامه از کار نیفتد
    def get_display(text):
        return text


    def arabic_reshaper_reshape(text):
        return text
else:
    # اگر ایمپورت موفق بود، تابع اصلی را تعریف می‌کنیم
    def arabic_reshaper_reshape(text):
        return arabic_reshaper.reshape(text)


def generate_class_summary_chart_robust(scores_list, class_name="", subject_name="", name=""):
    """
    نسخه نهایی و پایدار نمودار با مدیریت خطای کامل و بررسی ورودی.
    """
    # 1. بررسی ورودی قبل از شروع هر کاری
    if not scores_list:
        logging.warning("⚠️ لیست نمرات ورودی خالی است. نموداری تولید نشد.")
        return None

    try:
        def fix_farsi(text: str) -> str:
            return get_display(arabic_reshaper_reshape(text))

        # تبدیل ورودی به آرایه NumPy برای محاسبات و بررسی نوع داده
        scores = np.array(scores_list, dtype=float)
        if np.isnan(scores).any():  # بررسی وجود مقادیر نامعتبر مانند NaN
            raise ValueError("لیست نمرات حاوی مقادیر غیرعددی یا نامعتبر است.")
    except (ValueError, TypeError) as e:
        logging.error(f"❌ خطای داده ورودی: {e}")
        return None

    fig = None  # متغیر را بیرون از try تعریف می‌کنیم تا در finally قابل دسترس باشد
    try:
        def fix_farsi(text: str) -> str:
            return get_display(arabic_reshaper_reshape(text))  # <--- فرض می‌شود این تابع تعریف شده
            return text  # جایگزین موقت برای اجرا

        fig, axes = plt.subplots(1, 2, figsize=(16, 7), dpi=150)
        fig.suptitle(fix_farsi(
            f" تحلیل آماری نمرات {subject_name} {class_name}: {name} --- {jdatetime.datetime.now().strftime(' %d %m %Y')}"),
            fontsize=18, weight="bold")

        # --- Boxplot (بدون تغییر) ---
        axes[0].boxplot(
            scores, vert=True, patch_artist=True,
            boxprops=dict(facecolor="#90caf9", color="#1e88e5", linewidth=1.5),
            whiskerprops=dict(color="#1e88e5", linewidth=1.2),
            capprops=dict(color="#1e88e5", linewidth=1.2),
            medianprops=dict(color="red", linewidth=2),
            flierprops=dict(marker="o", markersize=0)
        )
        categories = {
            '#ef5350': scores[scores < 10],
            '#ffee58': scores[(scores >= 10) & (scores < 15)],
            '#66bb6a': scores[scores >= 15]
        }
        for color, score_group in categories.items():
            if score_group.size > 0:
                x_jitter = np.random.normal(1, 0.04, size=len(score_group))
                axes[0].plot(x_jitter, score_group, marker='o', linestyle='None', alpha=0.8,
                             color=color, markersize=6, markeredgecolor='black', markeredgewidth=0.5)
        axes[0].set_title(fix_farsi("پراکندگی نمرات"), fontsize=14, weight="bold")
        axes[0].set_ylabel(fix_farsi("نمره"), fontsize=12)
        axes[0].set_facecolor("#f9f9f9")
        axes[0].grid(axis="y", linestyle="--", alpha=0.4)
        stats = {
            "min": np.min(scores), "q1": np.percentile(scores, 25),
            "median": np.median(scores), "q3": np.percentile(scores, 75),
            "max": np.max(scores), "mean": np.mean(scores),
            "std": np.std(scores),
        }
        for key, value in stats.items():
            if key != "std":
                axes[0].text(1.15, value, f"{value:.1f}", va="center", ha="left", fontsize=9,
                             bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.6))
        axes[0].axhline(stats["mean"], color="green", linestyle="--", linewidth=1.5, label=fix_farsi("میانگین"))
        axes[0].axhline(stats["mean"] + stats["std"], color="orange", linestyle=":", linewidth=1.2,
                        label=fix_farsi("±σ انحراف معیار"))
        axes[0].axhline(stats["mean"] - stats["std"], color="orange", linestyle=":", linewidth=1.2)
        axes[0].plot(1, stats["min"], marker="*", color="red", markersize=12, label=fix_farsi("کمترین"))
        axes[0].plot(1, stats["q1"], marker="D", color="purple", markersize=8, label=fix_farsi("چارک اول"))
        axes[0].plot(1, stats["median"], marker="o", color="black", markersize=9, label=fix_farsi("میانه"))
        axes[0].plot(1, stats["q3"], marker="D", color="purple", markersize=8, label=fix_farsi("چارک سوم"))
        axes[0].plot(1, stats["max"], marker="*", color="blue", markersize=12, label=fix_farsi("بیشترین"))
        axes[0].legend(loc="upper right")

        # --- Histogram ---
        counts, bins, patches = axes[1].hist(scores, bins=10, edgecolor="black", alpha=0.9)
        axes[1].set_title(fix_farsi(" توزیع نمرات"), fontsize=13, weight="bold")
        axes[1].set_xlabel(fix_farsi("نمره"))
        axes[1].set_ylabel(fix_farsi("تعداد"))
        axes[1].set_facecolor("#f9f9f9")
        axes[1].grid(axis="y", linestyle="--", alpha=0.4)

        # ###################### تغییر اصلی اینجاست ######################
        # به جای حلقه if/elif/else، از np.select برای انتخاب رنگ‌ها استفاده می‌کنیم.

        # 1. مراکز هر ستون (bin) را محاسبه می‌کنیم.
        bin_centers = 0.5 * (bins[:-1] + bins[1:])

        # 2. شرایط و رنگ‌های متناظر را تعریف می‌کنیم.
        conditions = [
            bin_centers < 10,  # شرط اول: نمرات کمتر از ۱۰
            bin_centers >= 15  # شرط دوم: نمرات ۱۵ و بالاتر
        ]
        choices = [
            '#ef5350',  # رنگ برای شرط اول (قرمز)
            '#66bb6a'  # رنگ برای شرط دوم (سبز)
        ]

        # 3. با np.select، لیست رنگ‌ها را به صورت برداری ایجاد می‌کنیم.
        #    رنگ پیش‌فرض برای نمراتی است که در هیچ‌کدام از شرایط صدق نکنند.
        colors = np.select(conditions, choices, default='#ffee58')  # رنگ زرد

        # 4. رنگ‌ها را به ستون‌های نمودار (patches) اعمال می‌کنیم.
        for patch, color in zip(patches, colors):
            patch.set_facecolor(color)
        # ################### پایان بخش تغییر یافته ###################

        for count, x in zip(counts, bins):
            if count > 0:
                axes[1].text(x + (bins[1] - bins[0]) / 2, count, str(int(count)),
                             ha="center", va="bottom", fontsize=9, weight="bold")

        axes[1].axvline(stats["mean"], color="red", linestyle="--", linewidth=1.5, label=fix_farsi("میانگین"))
        axes[1].axvline(stats["mean"] + stats["std"], color="orange", linestyle=":", linewidth=1.2,
                        label=fix_farsi("±σ انحراف معیار"))
        axes[1].axvline(stats["mean"] - stats["std"], color="orange", linestyle=":", linewidth=1.2)
        axes[1].legend(loc="upper right")

        fig.text(0.5, 0.01, fix_farsi(f" تعداد دانش‌آموزان: {len(scores)}"),
                 ha="center", fontsize=11, color="gray")

        plt.tight_layout(rect=[0, 0.03, 1, 0.96])
        # tmp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False) # <--- این بخش به tempfile نیاز دارد
        # plt.savefig(tmp_file.name, bbox_inches="tight")
        # return tmp_file.name
        plt.savefig("chart_vectorized.png", bbox_inches="tight")  # برای تست محلی
        return "chart_vectorized.png"


    except Exception as e:
        # مدیریت خطاهای پیش‌بینی نشده در زمان اجرای رسم نمودار
        logging.exception(f"❌ خطای پیش‌بینی نشده در تولید نمودار: {e}")
        return None

    finally:
        # 3. اطمینان از بسته شدن نمودار در هر حالتی (موفق یا ناموفق)
        if fig:
            plt.close(fig)

