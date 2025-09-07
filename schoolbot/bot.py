import logging
from balethon.client import Client

from schoolbot.handlers.teacher_handler import handle_teacher_message
from schoolbot.handlers.manager_handler import handle_manager_message
from schoolbot.handlers.student_handler import handle_student_message

from schoolbot.utils.keyboards import normalize_digits
from schoolbot.services.auth_service import check_login, change_password
from schoolbot.utils.log_change_password import user_bale_info, log_attributes_user_student_change_pass

# 📌 فقط خطاها (ERROR و بالاتر) لاگ شوند
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)

# برای اطمینان، لاگ سطح پایین‌تر در کتابخانه‌های جانبی هم غیرفعال شود
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("balethon").setLevel(logging.WARNING)

TOKEN = "1952224317:fzOmvajCA3B5iQ6ObL5bJymejxfqMwTbgN9ychBg"
client = Client(TOKEN)

ROLES = {
    "manager": {"key": "manager", "title": "👨‍💼 مدیر"},
    "teacher": {"key": "teacher", "title": "👩‍🏫 معلم"},
    "student": {"key": "student", "title": "🎓 دانش‌آموز"},
}

user_sessions = {}  # ذخیره اطلاعات کاربران


async def show_main_menu(chat_id, user_bale):
    try:
        session = user_sessions.get(chat_id, {})
        role = session.get("role")

        if role == ROLES["manager"]["key"]:
            await client.send_message(
                chat_id,
                "📋 منوی مدیر:\n"
                "1️⃣ ایجاد دوره کارنامه\n"
                "2️⃣ مشاهده وضعیت دانش‌آموزان\n"
                "3️⃣ تأیید دوره کارنامه\n"
                "4️⃣ بررسی وضعیت ثبت نمرات\n\n"
                "🔑 برای تغییر رمز عبور، فقط `+` بفرستید."
            )
            session["step"] = "manager_menu"

        elif role == ROLES["teacher"]["key"]:
            await client.send_message(
                chat_id,
                "📋 منوی معلم:\n"
                "1️⃣ مشاهده دوره‌ها و دروس\n"
                "🔑 برای تغییر رمز عبور، فقط `+` بفرستید."
            )
            session["step"] = "teacher_menu"

        elif role == ROLES["student"]["key"]:
            await  client.send_message(
                chat_id,
                f"{user_bale_info(user_bale)}"
            )
            await client.send_message(
                chat_id,
                "📋 منوی دانش‌آموز:\n"
                "1️⃣ مشاهده کارنامه‌ها\n"
                "🔑 برای تغییر رمز عبور، فقط `+` بفرستید."
            )
            session["step"] = "student_menu"

        user_sessions[chat_id] = session
    except Exception as e:
        logging.error(f"❌ خطا در show_main_menu: {e}")
        await client.send_message(chat_id, "⚠️ مشکلی در نمایش منو پیش آمد. لطفاً دوباره تلاش کنید.")


async def reset_bot(chat_id):
    try:
        user_sessions[chat_id] = {"step": "choose_role"}
        await client.send_message(
            chat_id,
            "🔄 *باله* آماده می باشد.\nنقش خود را انتخاب کنید:\n1️⃣ مدیر\n2️⃣ معلم\n3️⃣ دانش‌آموز"
        )
    except Exception as e:
        logging.error(f"❌ خطا در reset_bot: {e}")


@client.on_message()
async def handle_message(message):
    try:
        text = normalize_digits(message.text.strip())  # ← نرمال‌سازی اعداد
        chat_id = message.chat.id
        # ریست با /start یا /خروج
        if text.lower() in ["/start", "/خروج"]:
            await reset_bot(chat_id)
            return

        session = user_sessions.get(chat_id)
        if not session:
            await reset_bot(chat_id)
            return

        if message.author['is_bot']:
            print("you are a bot")
            return
        # انتخاب نقش
        if session.get("step") == "choose_role":
            roles = {"1": ROLES["manager"]["key"], "2": ROLES["teacher"]["key"], "3": ROLES["student"]["key"]}
            role = roles.get(text)
            if not role:
                await client.send_message(chat_id, "لطفاً عدد ۱ تا ۳ را وارد کنید.")
                return
            session["role"] = role
            session["step"] = "ask_username"
            await client.send_message(chat_id, "نام کاربری خود را وارد کنید:")
            return

        if session.get("step") == "ask_username":
            session["username"] = text
            session["step"] = "ask_password"
            await client.send_message(chat_id, "رمز عبور خود را وارد کنید:")
            return

        if session.get("step") == "ask_password":
            try:
                ok, db_user_id, name = check_login(session["username"], text, session["role"])
            except Exception as e:
                logging.error(f"❌ خطا در check_login: {e}")
                await client.send_message(chat_id, "⚠️ خطا در ورود. لطفاً بعداً تلاش کنید.")
                return

            if not ok:
                await client.send_message(chat_id, "❌ نام کاربری یا رمز عبور اشتباه است. دوباره تلاش کنید. \n می توانید با /start به منوی قبل باز گردید.")
                await client.send_message(chat_id, "نام کاربری خود را وارد کنید:")
                session["step"] = "ask_username"
                return

            session["user_id"] = db_user_id
            session["name"] = name
            role_title = ROLES[session["role"]]["title"]

            await client.send_message(
                chat_id,
                f"✅ ورود موفق!\n\n"
                f"🔹 نقش شما: {role_title}\n"
                f"🔹 نام: {name}\n\n"
                f"🌟 خوش آمدید! آماده استفاده از امکانات *باله* باشید."
            )

            await show_main_menu(chat_id, message.author)
            return

        # تغییر رمز عبور
        if session.get("step") == "ask_new_password":
            if session["role"] == "student":
                log_attributes_user_student_change_pass(message.author, session["username"])

            new_password = text
            try:
                change_password(session["user_id"], new_password, session["role"], message.author['id'])
                await client.send_message(chat_id, "✅ رمز عبور با موفقیت تغییر یافت.")
            except Exception as e:
                logging.error(f"❌ خطا در change_password: {e}")
                await client.send_message(chat_id, "⚠️ خطا در تغییر رمز عبور. لطفاً دوباره تلاش کنید.")
            await show_main_menu(chat_id, message.author)
            return

        # تغییر رمز با "+"
        if text == "+":
            session["step"] = "ask_new_password"
            await client.send_message(chat_id, "🔑 لطفاً رمز عبور جدید خود را وارد کنید:")
            return

        # فراخوانی هندلر بر اساس نقش
        role = session.get("role")
        user_id = session.get("user_id")
        name = session.get("name")

        try:
            result = None  # تعریف متغیر برای دریافت نتیجه
            if role == ROLES["manager"]["key"]:
                result = await handle_manager_message(client, chat_id, user_id, text, name)
            elif role == ROLES["teacher"]["key"]:
                result = await handle_teacher_message(client, chat_id, user_id, text, name)
            elif role == ROLES["student"]["key"]:
                result = await handle_student_message(client, chat_id, user_id, text, name)

            # بررسی سیگنال بازگشتی از هندلر
            if result == "RESET_SESSION":
                user_sessions.pop(chat_id, None)
                await reset_bot(chat_id)
                return  # اجرای تابع را متوقف می‌کنیم تا کد دیگری اجرا نشود


        except Exception as e:
            logging.error(f"❌ خطا در هندلر {role}: {e}")
            await client.send_message(chat_id, "⚠️ خطا در پردازش پیام. لطفاً دوباره تلاش کنید.")

    except Exception as e:
        logging.error(f"❌ خطا در handle_message: {e}")


if __name__ == "__main__":

    print("--- Client is ready ---")
    try:
        client.run()
    except Exception as e:
        logging.critical(f"❌ خطای بحرانی در اجرای کلاینت: {e}")
