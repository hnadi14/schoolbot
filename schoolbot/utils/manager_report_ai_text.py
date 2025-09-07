import re

def extract_course_stats(report_text: str) -> str:
    """
    گزارش متنی مدرسه را دریافت کرده و از هر دوره، عنوان و بخش آمار دروس را استخراج می‌کند.
    خروجی نهایی یک رشته تک‌خطی بدون فاصله‌های اضافه و کاراکترهای '━' است.

    Args:
        report_text (str): رشته کامل گزارش مدرسه.

    Returns:
        str: یک رشته فرمت‌بندی شده، تک‌خطی و کاملا تمیز شده.
    """
    # بخش مقایسه را از ابتدای کار حذف می‌کنیم
    stop_marker = "📌 مقایسه دوره‌ها:"
    if stop_marker in report_text:
        report_text = report_text.split(stop_marker)[0]

    # متن را بر اساس جداکننده "📌 دوره:" به بخش‌های مختلف تقسیم می‌کنیم
    sections = report_text.split("📌 دوره:")[1:]

    final_output_list = []

    # روی هر بخش حلقه می‌زنیم تا اطلاعات مورد نظر را استخراج کنیم
    for section in sections:
        if "📚 آمار هر درس:" in section:
            period_title = section.split('\n')[0].strip()
            stats_block = section.split("📚 آمار هر درس:")[1]

            extracted_part = (
                f"📌 دوره: {period_title}\n"
                f"📚 آمار هر درس:{stats_block.rstrip()}"
            )
            final_output_list.append(extracted_part)

    # --- تغییر نهایی اینجاست ---
    # 1. تمام بخش‌ها را به یک رشته واحد تبدیل می‌کنیم
    combined_text = " ".join(final_output_list)

    # 2. کاراکترهای '━' را حذف می‌کنیم (با جایگزینی با هیچی)
    text_without_lines = combined_text.replace('━', '')

    # 3. حالا تمام فضاهای خالی اضافه (فاصله، خط جدید و...) را به یک فاصله تبدیل می‌کنیم
    cleaned_text = re.sub(r'\s+', ' ', text_without_lines).strip()

    return cleaned_text