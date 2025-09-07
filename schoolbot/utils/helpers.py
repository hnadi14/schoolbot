import logging
import jdatetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import tempfile
import arabic_reshaper
from bidi.algorithm import get_display

# A logger for this specific module
log = logging.getLogger(__name__)


def format_school_multi_period_analysis(analysis: dict, name: str):
    """
    نسخه بهینه‌شده: تولید متن تحلیلی چند دوره‌ای + نمودارها برای مدیر.
    عملکرد خروجی کاملاً مشابه نسخه اصلی است.
    """

    # ----------------- توابع کمکی -----------------
    def fix_farsi(text: str) -> str:
        """اصلاح متن فارسی برای نمایش صحیح در نمودار."""
        try:
            return get_display(arabic_reshaper.reshape(str(text)))
        except Exception:
            return str(text)

    def _safe_get(data: dict, key: str, default_value, target_type):
        """
        استخراج و تبدیل امن یک مقدار از دیکشنری.
        - None را به مقدار پیش‌فرض تبدیل می‌کند.
        - خطا در تبدیل نوع را مدیریت می‌کند.
        - مقادیر نامتناهی (inf, nan) را مدیریت می‌کند.
        """
        value = (data or {}).get(key, default_value)
        if value is None:
            return default_value
        try:
            converted = target_type(value)
            if target_type is float and not np.isfinite(converted):
                return default_value
            return converted
        except (ValueError, TypeError):
            return default_value

    # ----------------- اعتبارسنجی ورودی -----------------
    if not isinstance(analysis, dict):
        return "⚠️ داده‌ی تحلیل نامعتبر است.", None
    if "message" in analysis:
        return str(analysis.get("message") or ""), None

    # ----------------- 1. استخراج و پردازش داده‌ها -----------------
    # ابتدا تمام داده‌ها را به ساختارهای تمیز منتقل می‌کنیم.
    periods = analysis.get("periods") or {}
    comparisons = analysis.get("comparisons") or []

    period_names, overall_avgs, above_10_list, below_10_list = [], [], [], []
    ranges_dict = {}
    report_parts = [
        f"📊 گزارش تحلیلی مدرسه {name} در تمام دوره‌ها:\n{jdatetime.datetime.now().strftime(' %Y/%m/%d')} \n"]

    for period_name, stats in periods.items():
        if isinstance(stats, dict) and "message" in stats:
            report_parts.append(f"📌 {period_name}: {stats.get('message')}\n\n")
            continue

        # استخراج امن داده‌ها با تابع کمکی
        total_students = _safe_get(stats, "total_students", 0, int)
        count_with_scores = _safe_get(stats, "count_with_scores", 0, int)
        overall_avg = _safe_get(stats, "overall_avg", 0.0, float)
        above_10 = _safe_get(stats, "above_10", 0, int)
        below_10 = _safe_get(stats, "below_10", 0, int)
        max_avg = _safe_get(stats, "max_avg", 0.0, float)
        min_avg = _safe_get(stats, "min_avg", 0.0, float)
        ranges = _safe_get(stats, "ranges", {}, dict)
        subjects = _safe_get(stats, "subjects", {}, dict)

        # ذخیره داده‌ها برای نمودار
        period_names.append(str(period_name))
        overall_avgs.append(overall_avg)
        above_10_list.append(above_10)
        below_10_list.append(below_10)
        for rng, cnt in (ranges or {}).items():
            ranges_dict.setdefault(rng, []).append(_safe_get(ranges, rng, 0, int))

        # ----------------- 2. تولید گزارش متنی (بخش دوره‌ها) -----------------
        report_parts.extend([
            f"📌 دوره: {period_name}\n",
            f"👥 تعداد کل دانش‌آموزان: {total_students}\n",
            f"📝 تعداد با نمره ثبت‌شده: {count_with_scores}\n",
            f"📈 میانگین کل: {overall_avg}\n",
            f"✅ قبولی‌ها (>=10): {above_10}\n",
            f"❌ مردودی‌ها (<10): {below_10}\n",
            f"🔝 بیشترین معدل: {max_avg}\n",
            f"🔻 کمترین معدل: {min_avg}\n",
            "📊 پراکندگی نمرات:\n" + "━" * 20 + "\n     بازه| تعداد\n"
        ])
        for rng, cnt in (ranges or {}).items():
            report_parts.append(f"   • {rng}: {_safe_get(ranges, rng, 0, int)} نفر\n")
        if subjects:
            report_parts.append("📚 آمار هر درس:\n" + "━" * 20 + "\n     درس             | تعداد نمرات| میانگین\n")
            for subj, data in (subjects or {}).items():
                cnt = _safe_get(data, "count", 0, int)
                avg = _safe_get(data, "avg", 0.0, float)
                report_parts.append(f"   • {str(subj).ljust(15)} {str(cnt).ljust(11)}, {str(avg).rjust(7)}\n")
        report_parts.append("\n")

    # ----------------- 2. تولید گزارش متنی (بخش مقایسه‌ها) -----------------
    if comparisons:
        report_parts.append("━" * 20 + "\n📌 مقایسه دوره‌ها:\n")
        for comp in comparisons:
            prev_p = comp.get("prev_period", "?")
            curr_p = comp.get("curr_period", "?")
            report_parts.append(f"🔸 از «{prev_p}» تا «{curr_p}»:\n")
            avg_change = _safe_get(comp, "avg_change", 0.0, float)
            avg_sign = "📈 پیشرفت" if avg_change > 0 else ("📉 افت" if avg_change < 0 else "➖ بدون تغییر")
            report_parts.append(f"   • تغییر میانگین کل: {avg_change} ({avg_sign})\n")

            success_change = _safe_get(comp, "success_change", 0.0, float)
            success_sign = "📈 افزایش قبولی" if success_change > 0 else (
                "📉 کاهش قبولی" if success_change < 0 else "➖ بدون تغییر")
            report_parts.append(f"   • تغییر تعداد قبولی‌ها: {success_change} ({success_sign})\n\n")

    txt = "".join(report_parts)
    if not period_names:
        return txt.strip(), None

    # ----------------- 3. تولید نمودارها -----------------
    chart_path = None
    try:
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        axes = axes.flatten()
        fig.suptitle(
            fix_farsi(f"تحلیل تصویری چند دوره‌ای مدرسه {name}  {jdatetime.datetime.now().strftime(' %Y/%m/%d')}"),
            fontsize=18, weight="bold"
        )
        x_labels = [fix_farsi(name) for name in period_names]

        # تبدیل به آرایه‌های NumPy برای محاسبات بهینه
        overall_avgs_np = np.array(overall_avgs, dtype=float)
        above_10_np = np.array(above_10_list, dtype=int)
        below_10_np = np.array(below_10_list, dtype=int)

        # 📈 نمودار 1: میانگین کل هر دوره
        try:
            ax = axes[0]
            ax.plot(x_labels, overall_avgs_np, marker="o", linewidth=2, markersize=8, label=fix_farsi("میانگین کل"))
            finite_mask = np.isfinite(overall_avgs_np)
            if np.sum(finite_mask) >= 2:
                xs = np.arange(len(overall_avgs_np))[finite_mask]
                ys = overall_avgs_np[finite_mask]
                if np.ptp(xs) > 0:
                    z = np.polyfit(xs, ys, 1)
                    p = np.poly1d(z)
                    ax.plot(x_labels, p(np.arange(len(x_labels))), linestyle="--", linewidth=1.5,
                            label=fix_farsi("روند کلی"))

            if np.any(finite_mask):
                max_idx, min_idx = np.nanargmax(overall_avgs_np), np.nanargmin(overall_avgs_np)
                ax.plot(max_idx, overall_avgs_np[max_idx], marker="*", markersize=12, label=fix_farsi("بیشترین"))
                ax.plot(min_idx, overall_avgs_np[min_idx], marker="*", markersize=12, label=fix_farsi("کمترین"))

            for i, avg in enumerate(overall_avgs_np):
                if np.isfinite(avg):
                    ax.text(i, avg + 0.1, f"{avg:.1f}", ha="center", va="bottom", fontsize=10, weight="bold")

            ax.set_title(fix_farsi("میانگین کل هر دوره"), fontsize=12, weight="bold")
            ax.set_ylabel(fix_farsi("میانگین"))
            ax.grid(axis="y", linestyle="--", alpha=0.3)
            ax.set_xticks(range(len(x_labels)))
            ax.legend()
        except Exception as e:
            log.error(f"panel[0] error: {e}", exc_info=True)

        # 🥧 نمودار 2: درصد قبولی/مردودی
        try:
            ax = axes[1]
            totals_np = above_10_np + below_10_np  # محاسبه برداری
            if np.any(totals_np > 0):
                max_total = totals_np.max()
                x_positions = np.linspace(0, len(period_names) * 2, len(period_names))
                wedges_for_legend, legend_labels = None, [fix_farsi("قبولی"), fix_farsi("مردودی")]
                pass_colors, fail_color = ['#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd'], '#d62728'

                for i, (a, b, total, name, x) in enumerate(
                        zip(above_10_np, below_10_np, totals_np, period_names, x_positions)):
                    if total <= 0: continue
                    radius = 0.5 + 0.3 * (total / max_total)
                    wedges, _, autotexts = ax.pie(
                        [a, b], autopct="%1.0f%%", startangle=90, center=(x, 0), radius=radius,
                        colors=[pass_colors[i % len(pass_colors)], fail_color]
                    )
                    for autotext in autotexts: autotext.set_color('black')
                    if wedges_for_legend is None: wedges_for_legend = wedges
                    ax.text(x, -radius - 0.2, fix_farsi(name), ha="center", va="center", fontsize=10, weight="bold")

                if wedges_for_legend:
                    ax.legend(wedges_for_legend, legend_labels, loc="upper right", fontsize=10)
                ax.set_title(fix_farsi("درصد قبولی / مردودی"), fontsize=12, weight="bold")
                ax.axis("equal");
                ax.axis("off");
                ax.set_ylim(-1.5, 1)
            else:
                ax.set_title(fix_farsi("داده‌ای برای درصد قبولی/مردودی موجود نیست"));
                ax.axis("off")
        except Exception as e:
            log.error(f"panel[1] error: {e}", exc_info=True)

        # 📈 نمودار 3: پراکندگی نمرات (بدون تغییر عمده در منطق)
        try:
            ax = axes[2]
            # (منطق این بخش نسبتاً پیچیده است و تغییرات کمی دارد)
            for rng in list(ranges_dict.keys()):
                if len(ranges_dict[rng]) < len(period_names):
                    ranges_dict[rng].extend([0] * (len(period_names) - len(ranges_dict[rng])))

            if ranges_dict:
                colors = ["#d62728", "#ff7f0e", "#1f77b4", "#2ca02c", "#9467bd"]
                all_counts = [c for counts in ranges_dict.values() for c in counts]
                offset = (max(all_counts) - min(all_counts)) * 0.03 + 0.1 if all_counts else 0.1

                for idx, (rng, counts) in enumerate(ranges_dict.items()):
                    line_color = colors[idx % len(colors)]
                    ax.plot(x_labels, counts, marker="o", linewidth=2, label=fix_farsi(rng), color=line_color)
                    for i, val in enumerate(counts):
                        ax.text(i, val + offset, str(val), ha="center", va="bottom", fontsize=9, weight="bold",
                                color=line_color,
                                bbox=dict(boxstyle="round,pad=0.2", fc='white', alpha=0.5, ec='none'))

                ax.set_title(fix_farsi("پراکندگی نمرات"), fontsize=12, weight="bold")
                ax.legend(fontsize=10, loc="upper left")
                ax.grid(True, which='both', linestyle='--', linewidth=0.3)
            else:
                ax.set_title(fix_farsi("پراکندگی در دسترس نیست"));
                ax.axis("off")
        except Exception as e:
            log.error(f"panel[2] error: {e}", exc_info=True)

        # 📊 نمودار 4: تغییرات بین دوره‌ها (بدون تغییر عمده در منطق)
        try:
            ax = axes[3]
            if comparisons:
                avg_changes = [_safe_get(c, "avg_change", 0.0, float) for c in comparisons]
                success_changes = [_safe_get(c, "success_change", 0, int) for c in comparisons]
                comp_labels = [fix_farsi(f"{c.get('prev_period')}→{c.get('curr_period')}") for c in comparisons]

                ax.plot(comp_labels, avg_changes, marker="o", linewidth=2, label=fix_farsi("تغییر میانگین"))
                ax.plot(comp_labels, success_changes, marker="s", linewidth=2, label=fix_farsi("تغییر قبولی"))

                bbox_props = dict(boxstyle="round,pad=0.2", fc='white', alpha=0.8, ec='none')
                for i, (a, s) in enumerate(zip(avg_changes, success_changes)):
                    ax.text(i, a, f"{a:+.1f}", ha="center", va="bottom", fontsize=9, bbox=bbox_props)
                    ax.text(i, s, f"{s:+.0f}", ha="center", va="top", fontsize=9, bbox=bbox_props)

                ax.set_title(fix_farsi("تغییرات بین دوره‌ها"), fontsize=12, weight="bold")
                ax.tick_params(axis='x', rotation=45, labelsize=10)
                ax.legend(loc="upper right", fontsize=10)
                ax.axhline(0, color='grey', linewidth=0.8, linestyle='--')
                ax.grid(axis="y", linestyle="--", alpha=0.3)
            else:
                ax.set_title(fix_farsi("داده‌ای برای مقایسه‌ی دوره‌ها موجود نیست"));
                ax.axis("off")
        except Exception as e:
            log.error(f"panel[3] error: {e}", exc_info=True)

        plt.tight_layout(rect=[0, 0.03, 1, 0.96])
        tmp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        plt.savefig(tmp_file.name, bbox_inches="tight", dpi=150)
        chart_path = tmp_file.name

    except Exception as e:
        log.error(f"figure build error: {e}", exc_info=True)
        chart_path = None
    finally:
        plt.close('all')  # بستن تمام نمودارها برای اطمینان

    return txt.strip(), chart_path