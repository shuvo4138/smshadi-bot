import logging
import re
import io
import csv
import random
import requests
import os
import json
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "1984916365").strip())
OTP_CHANNEL_ID = int(os.getenv("OTP_CHANNEL_ID", "-1002625886518").strip())
JOIN_CHANNEL = os.getenv("JOIN_CHANNEL", "https://t.me/alwaysrvice24hours").strip()
DASHBOARD_BASE = "http://185.2.83.39/ints/agent"
API_URL = f"{DASHBOARD_BASE}/SMSDashboard/res/data_smscdr.php"
DASHBOARD_USER = os.getenv("DASHBOARD_USER", "").strip()
DASHBOARD_PASS = os.getenv("DASHBOARD_PASS", "").strip()
NUMBERS_FILE = "numbers.json"

if not BOT_TOKEN:
    logger.error("BOT_TOKEN is not set!")
    import time
    time.sleep(10)
    exit(1)

numbers_pool = []
user_numbers = {}
otp_cache = {}
session_cookie = None

def save_numbers():
    try:
        with open(NUMBERS_FILE, "w") as f:
            json.dump(numbers_pool, f)
        logger.info(f"Saved {len(numbers_pool)} numbers")
    except Exception as e:
        logger.error(f"Save error: {e}")

def load_numbers():
    global numbers_pool
    try:
        if os.path.exists(NUMBERS_FILE):
            with open(NUMBERS_FILE, "r") as f:
                numbers_pool = json.load(f)
            logger.info(f"Loaded {len(numbers_pool)} numbers")
    except Exception as e:
        logger.error(f"Load error: {e}")

def solve_captcha(question: str) -> str:
    try:
        match = re.search(r'(\d+)\s*\+\s*(\d+)', question)
        if match:
            return str(int(match.group(1)) + int(match.group(2)))
        match = re.search(r'(\d+)\s*-\s*(\d+)', question)
        if match:
            return str(int(match.group(1)) - int(match.group(2)))
        match = re.search(r'(\d+)\s*[*×]\s*(\d+)', question)
        if match:
            return str(int(match.group(1)) * int(match.group(2)))
    except Exception as e:
        logger.error(f"Captcha error: {e}")
    return ""

def login_dashboard():
    global session_cookie
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        login_url = "http://185.2.83.39/ints/login"
        resp = session.get(login_url, headers=headers, timeout=15)

        captcha_answer = ""
        match = re.search(r'(\d+)\s*[\+\-\*×]\s*(\d+)', resp.text)
        if match:
            captcha_answer = solve_captcha(match.group(0))
        if not captcha_answer:
            captcha_answer = "15"

        login_data = {
            "username": DASHBOARD_USER,
            "password": DASHBOARD_PASS,
            "captcha": captcha_answer,
            "submit": "LOGIN"
        }
        login_resp = session.post(login_url, data=login_data, headers=headers, allow_redirects=True, timeout=15)

        if "PHPSESSID" in session.cookies:
            session_cookie = session.cookies["PHPSESSID"]
            logger.info("Login success!")
            return session_cookie

        logger.error("Login failed!")
        return None

    except Exception as e:
        logger.error(f"Login error: {e}")
        return None

def get_session():
    global session_cookie
    if not session_cookie:
        login_dashboard()
    return session_cookie

def test_session():
    global session_cookie
    cookie = get_session()
    if not cookie:
        return False
    try:
        resp = requests.get(
            f"{DASHBOARD_BASE}/res/data_smscdr.php",
            params={"sEcho": 1, "iDisplayStart": 0, "iDisplayLength": 10},
            headers={"Cookie": f"PHPSESSID={cookie}", "X-Requested-With": "XMLHttpRequest"},
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Session test error: {e}")
        return False

def fetch_otp_for_number(number: str):
    global session_cookie
    cookie = get_session()
    if not cookie:
        return None
    try:
        clean_num = number.lstrip("+").strip()
        resp = requests.get(
            API_URL,
            params={"sEcho": 1, "iDisplayStart": 0, "iDisplayLength": 50, "fnumber": clean_num},
            headers={"Cookie": f"PHPSESSID={cookie}", "X-Requested-With": "XMLHttpRequest", "Referer": f"{DASHBOARD_BASE}/SMSDashboard/SMSCDRReports"},
            timeout=15
        )
        if resp.status_code in [302, 401, 403]:
            session_cookie = None
            login_dashboard()
            return None
        data = resp.json()
        rows = data.get("aaData", [])
        if rows and len(rows[0]) >= 6:
            latest = rows[0]
            return {
                "datetime": str(latest[0] or ""),
                "sender": str(latest[3] or "Unknown"),
                "message": str(latest[5] or ""),
                "number": clean_num
            }
    except Exception as e:
        logger.error(f"Fetch OTP error: {e}")
        session_cookie = None
    return None

def fetch_all_recent_otps():
    global session_cookie
    cookie = get_session()
    if not cookie:
        return []
    try:
        resp = requests.get(
            API_URL,
            params={"sEcho": 1, "iDisplayStart": 0, "iDisplayLength": 100},
            headers={"Cookie": f"PHPSESSID={cookie}", "X-Requested-With": "XMLHttpRequest", "Referer": f"{DASHBOARD_BASE}/SMSDashboard/SMSCDRReports"},
            timeout=15
        )
        if resp.status_code in [302, 401, 403]:
            session_cookie = None
            login_dashboard()
            return []
        return resp.json().get("aaData", [])
    except Exception as e:
        logger.error(f"Polling error: {e}")
        session_cookie = None
    return []

def extract_otp(msg: str) -> str:
    if not msg:
        return ""
    msg = msg.replace("# ", "").replace("#", "")
    codes = re.findall(r'\b\d{4,8}\b', msg)
    return codes[0] if codes else ""

def mask_number(number: str) -> str:
    n = str(number)
    return n[:4] + "★★★★" + n[-4:] if len(n) >= 8 else n

def get_available_number():
    assigned = set(user_numbers.values())
    available = [n for n in numbers_pool if n not in assigned]
    return random.choice(available) if available else None

def get_user_keyboard(user_id):
    if user_id == ADMIN_ID:
        return ReplyKeyboardMarkup([
            [KeyboardButton("🏠 Home"), KeyboardButton("📲 Get Number")],
            [KeyboardButton("🔍 Check OTP"), KeyboardButton("📋 My Number")],
            [KeyboardButton("👑 Admin Panel")]
        ], resize_keyboard=True)
    return ReplyKeyboardMarkup([
        [KeyboardButton("🏠 Home"), KeyboardButton("📲 Get Number")],
        [KeyboardButton("🔍 Check OTP"), KeyboardButton("📋 My Number")],
    ], resize_keyboard=True)

async def poll_otps(context):
    rows = fetch_all_recent_otps()
    for row in rows:
        if len(row) < 6:
            continue
        try:
            dt_str = str(row[0] or "")
            number = str(row[2] or "").strip()
            sender = str(row[3] or "Unknown")
            message = str(row[5] or "")
            if not message or not number:
                continue
            cache_key = f"{number}:{message[:30]}"
            if cache_key in otp_cache:
                continue
            otp_cache[cache_key] = True
            otp_code = extract_otp(message)
            owner_id = None
            for uid, num in user_numbers.items():
                if num == number or num.lstrip("+") == number.lstrip("+"):
                    owner_id = uid
                    break
            channel_text = (
                f"📩 *নতুন OTP*\n\n"
                f"📞 Number: `{mask_number(number)}`\n"
                f"🏢 From: {sender}\n"
                f"🔐 OTP: `{otp_code}`\n"
                f"💬 SMS: {message[:100]}\n"
                f"🕐 {dt_str}"
            )
            try:
                await context.bot.send_message(chat_id=OTP_CHANNEL_ID, text=channel_text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Channel error: {e}")
            if owner_id:
                try:
                    await context.bot.send_message(
                        chat_id=owner_id,
                        text=f"✅ *OTP এসেছে!*\n\n📞 `{number}`\n🏢 From: *{sender}*\n🔐 OTP: `{otp_code}`\n💬 _{message[:100]}_\n🕐 {dt_str}",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 OTP Channel", url=JOIN_CHANNEL)]])
                    )
                except Exception as e:
                    logger.error(f"User notify error: {e}")
        except Exception as e:
            logger.error(f"OTP process error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 স্বাগতম {user.first_name}!\n\n🤖 *SMS Hadi OTP Bot*\n\nMyanmar number নিন এবং OTP receive করুন।",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📲 Number নিন", callback_data="get_number")],
            [InlineKeyboardButton("🔍 OTP Check করুন", callback_data="check_otp")],
            [InlineKeyboardButton("📢 OTP Channel", url=JOIN_CHANNEL)],
        ])
    )
    await update.message.reply_text("নিচের menu থেকে option বেছে নিন:", reply_markup=get_user_keyboard(user.id))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🏠 Home":
        await start(update, context)

    elif text == "📲 Get Number":
        if not numbers_pool:
            await update.message.reply_text("❌ এখন কোনো number নেই। Admin কে জানান।")
            return
        if user_id in user_numbers:
            num = user_numbers[user_id]
            await update.message.reply_text(f"✅ আপনার number:\n`{num}`", parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
                    [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
                ]))
            return
        num = get_available_number()
        if not num:
            await update.message.reply_text("❌ সব number busy। পরে try করুন।")
            return
        user_numbers[user_id] = num
        await update.message.reply_text(
            f"✅ *আপনার Number:*\n\n`{num}`\n\nOTP আসলে সাথে সাথে notify করা হবে! 🔔",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
                [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
            ])
        )

    elif text == "🔍 Check OTP":
        if user_id not in user_numbers:
            await update.message.reply_text("❌ আগে number নিন।")
            return
        num = user_numbers[user_id]
        msg = await update.message.reply_text(f"🔍 `{num}` এর OTP খুঁজছি...", parse_mode="Markdown")
        result = fetch_otp_for_number(num)
        if result:
            otp_code = extract_otp(result["message"])
            await msg.edit_text(
                f"✅ *Latest OTP:*\n\n📞 `{num}`\n🏢 From: *{result['sender']}*\n🔐 OTP: `{otp_code}`\n💬 _{result['message'][:100]}_\n🕐 {result['datetime']}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{num}")]])
            )
        else:
            await msg.edit_text(f"⏳ `{num}` এ এখনো OTP আসেনি।", parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 আবার Check", callback_data=f"refresh_{num}")]]))

    elif text == "📋 My Number":
        if user_id in user_numbers:
            num = user_numbers[user_id]
            await update.message.reply_text(f"📋 আপনার number:\n`{num}`", parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
                    [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
                ]))
        else:
            await update.message.reply_text("❌ আপনার কোনো number নেই।")

    elif text == "👑 Admin Panel":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ আপনি admin না!")
            return
        assigned = len(user_numbers)
        available = len(numbers_pool) - assigned
        await update.message.reply_text(
            f"👑 *Admin Panel*\n\n"
            f"📦 Total: {len(numbers_pool)}\n"
            f"✅ Available: {available}\n"
            f"👥 Assigned: {assigned}\n"
            f"🔑 Session: {'✅ Active' if session_cookie else '❌ None'}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Numbers Upload", callback_data="admin_upload")],
                [InlineKeyboardButton("🗑 Clear All", callback_data="admin_clear")],
                [InlineKeyboardButton("🔄 Re-Login", callback_data="admin_relogin")],
                [InlineKeyboardButton("🧪 Test Session", callback_data="admin_test")],
            ])
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global session_cookie
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "get_number":
        if not numbers_pool:
            await query.edit_message_text("❌ কোনো number নেই।")
            return
        if user_id in user_numbers:
            num = user_numbers[user_id]
            await query.edit_message_text(f"✅ আপনার number:\n`{num}`", parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
                    [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
                ]))
            return
        num = get_available_number()
        if not num:
            await query.edit_message_text("❌ সব busy।")
            return
        user_numbers[user_id] = num
        await query.edit_message_text(
            f"✅ *Number:*\n\n`{num}`\n\nOTP আসলে notify হবে! 🔔",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
                [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
            ])
        )

    elif data == "check_otp":
        if user_id not in user_numbers:
            await query.edit_message_text("❌ আগে number নিন।")
            return
        num = user_numbers[user_id]
        await query.edit_message_text("🔍 খুঁজছি...")
        result = fetch_otp_for_number(num)
        if result:
            otp_code = extract_otp(result["message"])
            await query.edit_message_text(
                f"✅ *Latest OTP:*\n\n📞 `{num}`\n🏢 From: *{result['sender']}*\n🔐 OTP: `{otp_code}`\n💬 _{result['message'][:100]}_\n🕐 {result['datetime']}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{num}")]])
            )
        else:
            await query.edit_message_text("⏳ এখনো OTP নেই।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 আবার", callback_data="check_otp")]]))

    elif data.startswith("refresh_"):
        num = data.replace("refresh_", "")
        result = fetch_otp_for_number(num)
        if result:
            otp_code = extract_otp(result["message"])
            await query.edit_message_text(
                f"✅ *Latest OTP:*\n\n📞 `{num}`\n🏢 From: *{result['sender']}*\n🔐 OTP: `{otp_code}`\n💬 _{result['message'][:100]}_\n🕐 {result['datetime']}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{num}")]])
            )
        else:
            await query.edit_message_text("⏳ OTP নেই।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 আবার", callback_data=f"refresh_{num}")]]))

    elif data == "release_number":
        if user_id in user_numbers:
            num = user_numbers.pop(user_id)
            await query.edit_message_text(f"✅ `{num}` ছেড়ে দেওয়া হয়েছে।", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ কোনো number নেই।")

    elif data == "admin_upload":
        if user_id != ADMIN_ID:
            return
        await query.edit_message_text("📤 TXT/CSV file পাঠান।\n\n```\n959655653869\n959654946028\n```", parse_mode="Markdown")

    elif data == "admin_clear":
        if user_id != ADMIN_ID:
            return
        numbers_pool.clear()
        user_numbers.clear()
        save_numbers()
        await query.edit_message_text("✅ সব clear!")

    elif data == "admin_relogin":
        if user_id != ADMIN_ID:
            return
        await query.edit_message_text("🔄 Re-login করছি...")
        session_cookie = None
        result = login_dashboard()
        await context.bot.send_message(
            user_id,
            f"✅ Re-login সফল!\n🔑 Session: `{result[:20]}...`" if result else "❌ Re-login failed!",
            parse_mode="Markdown"
        )

    elif data == "admin_test":
        if user_id != ADMIN_ID:
            return
        await query.edit_message_text("🧪 Testing session...")
        valid = test_session()
        await context.bot.send_message(user_id, "✅ Session valid!" if valid else "❌ Session invalid!")

async def upload_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.document:
        return
    doc = update.message.document
    file = await doc.get_file()
    content = await file.download_as_bytearray()
    text = content.decode("utf-8", errors="ignore")
    new_numbers = []
    tokens = re.split(r'[\s,;]+', text)
    for token in tokens:
        token = token.strip().replace("+", "")
        if token.isdigit() and 8 <= len(token) <= 15:
            new_numbers.append(token)
    existing = set(numbers_pool)
    added = [n for n in new_numbers if n not in existing]
    numbers_pool.extend(added)
    save_numbers()
    await update.message.reply_text(
        f"✅ *Upload সফল!*\n\n📥 নতুন: {len(added)}\n📦 Total: {len(numbers_pool)}",
        parse_mode="Markdown"
    )

def main():
    logger.info("🚀 Starting Bot...")
    load_numbers()
    login_dashboard()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, upload_numbers))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.job_queue.run_repeating(poll_otps, interval=15, first=5)
    logger.info(f"✅ Bot running! {len(numbers_pool)} numbers loaded.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
