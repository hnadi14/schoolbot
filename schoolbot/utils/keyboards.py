

def normalize_digits(text: str) -> str:
    """
    تبدیل اعداد فارسی/عربی به اعداد انگلیسی
    """
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    english_digits = "0123456789"

    translation_table = {}
    for p, e in zip(persian_digits, english_digits):
        translation_table[ord(p)] = e
    for a, e in zip(arabic_digits, english_digits):
        translation_table[ord(a)] = e

    return text.translate(translation_table)


def to_persian_digits(text):
    """یک رشته با اعداد انگلیسی را به اعداد فارسی تبدیل می‌کند."""
    english_digits = "0123456789"
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    translation_table = str.maketrans(english_digits, persian_digits)
    return text.translate(translation_table)