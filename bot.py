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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "1984916365").strip())
OTP_CHANNEL_ID = int(os.getenv("OTP_CHANNEL_ID", "-1002625886518").strip())
JOIN_CHANNEL = os.getenv("JOIN_CHANNEL", "https://t.me/alwaysrvice24hours").strip()
DASHBOARD_BASE = os.getenv("DASHBOARD_BASE", "http://185.2.83.39/ints/agent").strip()
DASHBOARD_USER = os.getenv("DASHBOARD_USER", "shuvo098").strip()
DASHBOARD_PASS = os.getenv("DASHBOARD_PASS", "Shuvo.99@@").strip()
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
        logger.info(f"💾 Saved {len(numbers_pool)} numbers")
    except Exception as e:
        logger.error(f"Save error: {e}")

def load_numbers():
    global numbers_pool
    try:
        if os.path.exists(NUMBERS_FILE):
            with open(NUMBERS_FILE, "r") as f:
                numbers_pool = json.load(f)
            logger.info(f"📂 Loaded {len(numbers_pool)} numbers")
    except Exception as e:
        logger.error(f"Load error: {e}")

def login_dashboard():
    global session_cookie
    try:
        session = requests.Session()
        # Direct login without captcha
        login_resp = session.post(
            "http://185.2.83.39/ints/agent/",
            data={
                "username": DASHBOARD_USER,
                "password": DASHBOARD_PASS,
            },
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            allow_redirects=True,
            timeout=10
        )
        
        logger.info(f"🔐 Login response: {login_resp.status_code}, URL: {login_resp.url}")
        
        if "PHPSESSID" in session.cookies:
            session_cookie = session.cookies["PHPSESSID"]
            logger.info(f"✅ Login success: {session_cookie[:15]}...")
            return session_cookie
        else:
            logger.error(f"❌ Login failed - no PHPSESSID cookie")
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
    return None

def get_session():
    global session_cookie
    if not session_cookie:
        login_dashboard()
    return session_cookie

def fetch_otp_for_number(number: str):
    cookie = get_session()
    if not cookie:
        logger.error("❌ No session for fetch_otp!")
        return None
    try:
        clean_num = number.lstrip("+")
        resp = requests.get(
            "http://185.2.83.39/ints/agent/SMSCDRStats",
            params={"fnumber": clean_num},
            headers={
                "Cookie": f"PHPSESSID={cookie}",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            timeout=10
        )
        logger.info(f"📡 OTP fetch status: {resp.status_code}")
        if resp.status_code == 200:
            try:
                data = resp.json()
                rows = data.get("aaData", [])
                if rows:
                    latest = rows[0]
                    if len(latest) >= 6:
                        return {
                            "datetime": latest[0],
                            "sender": str(latest[3] or ""),
                            "message": str(latest[5] or ""),
                            "number": clean_num
                        }
            except Exception as e:
                logger.error(f"JSON error: {e}")
        elif resp.status_code in [302, 401, 403]:
            global session_cookie
            session_cookie = None
            login_dashboard()
    except Exception as e:
        logger.error(f"❌ OTP fetch error: {e}")
    return None

def fetch_all_recent_otps():
    cookie = get_session()
    if not cookie:
        logger.error("❌ No session for poll!")
        return []
    try:
        resp = requests.get(
            "http://185.2.83.39/ints/agent/SMSCDRStats",
            params={"iDisplayLength": 100},
            headers={
                "Cookie": f"PHPSESSID={cookie}",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            timeout=10
        )
        logger.info(f"📡 CDR Status: {resp.status_code}, Size: {len(resp.text)}")

        if resp.status_code == 200:
            try:
                data = resp.json()
                rows = data.get("aaData", [])
                logger.info(f"✅ Got {len(rows)} SMS rows")
                return rows
            except Exception as e:
                logger.error(f"JSON parse error: {e}")
        elif resp.status_code in [302, 401, 403]:
            global session_cookie
            session_cookie = None
            logger.warning("⚠️ Session expired! Re-login...")
            login_dashboard()
    except Exception as e:
        logger.error(f"❌ Recent OTP error: {e}")
    return []

def extract_otp(msg: str) -> str:
    msg = msg.replace("# ", "").replace("#", "")
    codes = re.findall(r'\b\d{4,8}\b', msg)
    return codes[0] if codes else ""

def mask_number(number: str) -> str:
    n = str(number)
    if len(n) >= 8:
        return n[:4] + "★★★★" + n[-4:]
    return n

def get_available_number():
    assigned = set(user_numbers.values())
    available = [n for n in numbers_pool if n not in assigned]
    return random.choice(available) if available else None

async def poll_otps(context):
    rows = fetch_all_recent_otps()
    for row in rows:
        if len(row) < 6:
            continue
        dt_str = str(row[0])
        number = str(row[2])
        sender = str(row[3] or "")
        message = str(row[5] or "")
        if not message or not number:
            continue
        cache_key = f"{number}:{message[:20]}"
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
            f"📩 *নতুন OTP*\n"
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
            keyboard = [[InlineKeyboardButton("📢 OTP Channel", url=JOIN_CHANNEL)]]
            user_text = (
                f"✅ *OTP এসেছে!*\n\n"
                f"📞 Number: `{number}`\n"
                f"🏢 From: *{sender}*\n"
                f"🔐 OTP: `{otp_code}`\n"
                f"💬 SMS: _{message[:100]}_\n"
                f"🕐 {dt_str}"
            )
            try:
                await context.bot.send_message(chat_id=owner_id, text=user_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
                logger.info(f"✅ Notified user {owner_id} about OTP for {number}")
            except Exception as e:
                logger.error(f"User notify error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton("📲 Get Number"), KeyboardButton("🔍 Check OTP")],
            [KeyboardButton("📋 My Number"), KeyboardButton("📢 OTP Channel")],
            [KeyboardButton("👑 Admin Panel")]
        ],
        resize_keyboard=True
    )
    await update.message.reply_text(
        f"👋 স্বাগতম {user.first_name}!\n\n🤖 *SMS Hadi OTP Bot*\n\nMyanmar number নিন এবং OTP receive করুন।",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "📲 Get Number":
        if not numbers_pool:
            await update.message.reply_text("❌ এখন কোনো number নেই। Admin কে জানান।")
            return
        if user_id in user_numbers:
            num = user_numbers[user_id]
            keyboard = [
                [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
                [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
            ]
            await update.message.reply_text(f"✅ আপনার number:\n`{num}`\n\nOTP আসলে notify করা হবে।", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        num = get_available_number()
        if not num:
            await update.message.reply_text("❌ সব number busy। পরে try করুন।")
            return
        user_numbers[user_id] = num
        keyboard = [
            [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
            [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
        ]
        await update.message.reply_text(f"✅ *আপনার Number:*\n\n`{num}`\n\nOTP আসলে সাথে সাথে notify করা হবে! 🔔", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "🔍 Check OTP":
        if user_id not in user_numbers:
            await update.message.reply_text("❌ আগে number নিন।")
            return
        num = user_numbers[user_id]
        await update.message.reply_text(f"🔍 `{num}` এর OTP খুঁজছি...", parse_mode="Markdown")
        result = fetch_otp_for_number(num)
        if result:
            otp_code = extract_otp(result["message"])
            keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{num}")]]
            await update.message.reply_text(
                f"✅ *Latest OTP:*\n\n📞 `{num}`\n🏢 From: *{result['sender']}*\n🔐 OTP: `{otp_code}`\n💬 _{result['message'][:100]}_\n🕐 {result['datetime']}",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(f"⏳ `{num}` এ এখনো OTP আসেনি।", parse_mode="Markdown")

    elif text == "📋 My Number":
        if user_id in user_numbers:
            num = user_numbers[user_id]
            keyboard = [
                [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
                [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
            ]
            await update.message.reply_text(f"📋 আপনার number:\n`{num}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("❌ আপনার কোনো number নেই। আগে number নিন।")

    elif text == "👑 Admin Panel":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ আপনি admin না!")
            return
        assigned = len(user_numbers)
        available = len(numbers_pool) - assigned
        keyboard = [
            [InlineKeyboardButton("📤 Numbers Upload", callback_data="admin_upload")],
            [InlineKeyboardButton("🗑 সব Clear", callback_data="admin_clear")],
            [InlineKeyboardButton("🔄 Re-Login", callback_data="admin_relogin")],
        ]
        await update.message.reply_text(
            f"👑 *Admin Panel*\n\n"
            f"📦 Total: {len(numbers_pool)}\n"
            f"✅ Available: {available}\n"
            f"👥 Assigned: {assigned}\n"
            f"🔑 Session: {'✅ Active' if session_cookie else '❌ None'}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "get_number":
        if not numbers_pool:
            await query.edit_message_text("❌ এখন কোনো number নেই।")
            return
        if user_id in user_numbers:
            num = user_numbers[user_id]
            keyboard = [
                [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
                [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
            ]
            await query.edit_message_text(f"✅ আপনার number:\n`{num}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        num = get_available_number()
        if not num:
            await query.edit_message_text("❌ সব number busy।")
            return
        user_numbers[user_id] = num
        keyboard = [
            [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
            [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
        ]
        await query.edit_message_text(f"✅ *আপনার Number:*\n\n`{num}`\n\nOTP আসলে notify করা হবে! 🔔", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "check_otp":
        if user_id not in user_numbers:
            await query.edit_message_text("❌ আগে number নিন।")
            return
        num = user_numbers[user_id]
        await query.edit_message_text("🔍 খুঁজছি...")
        result = fetch_otp_for_number(num)
        if result:
            otp_code = extract_otp(result["message"])
            keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{num}")]]
            await query.edit_message_text(
                f"✅ *Latest OTP:*\n\n📞 `{num}`\n🏢 From: *{result['sender']}*\n🔐 OTP: `{otp_code}`\n💬 _{result['message'][:100]}_\n🕐 {result['datetime']}",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [[InlineKeyboardButton("🔄 আবার Check", callback_data="check_otp")]]
            await query.edit_message_text("⏳ এখনো OTP আসেনি।", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("refresh_"):
        num = data.replace("refresh_", "")
        result = fetch_otp_for_number(num)
        if result:
            otp_code = extract_otp(result["message"])
            keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{num}")]]
            await query.edit_message_text(
                f"✅ *Latest OTP:*\n\n📞 `{num}`\n🏢 From: *{result['sender']}*\n🔐 OTP: `{otp_code}`\n💬 _{result['message'][:100]}_\n🕐 {result['datetime']}",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [[InlineKeyboardButton("🔄 আবার Check", callback_data=f"refresh_{num}")]]
            await query.edit_message_text("⏳ এখনো OTP নেই।", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "release_number":
        if user_id in user_numbers:
            num = user_numbers.pop(user_id)
            await query.edit_message_text(f"✅ `{num}` ছেড়ে দেওয়া হয়েছে।", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ আপনার কোনো number নেই।")

    elif data == "admin_upload":
        if user_id != ADMIN_ID:
            return
        await query.edit_message_text("📤 TXT বা CSV file পাঠান।\n\nFormat:\n```\n959655653869\n959654946028\n```", parse_mode="Markdown")

    elif data == "admin_clear":
        if user_id != ADMIN_ID:
            return
        numbers_pool.clear()
        user_numbers.clear()
        save_numbers()
        await query.edit_message_text("✅ সব numbers clear হয়েছে।")

    elif data == "admin_relogin":
        if user_id != ADMIN_ID:
            return
        global session_cookie
        session_cookie = None
        await query.edit_message_text("🔄 Re-login করছি...")
        result = login_dashboard()
        if result:
            await context.bot.send_message(chat_id=user_id, text="✅ Re-login সফল!")
        else:
            await context.bot.send_message(chat_id=user_id, text="❌ Re-login failed!")

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
    load_numbers()
    app = Application.builder().token(BOT_TOKEN).build()
    logger.info("🔐 Auto-login করছি...")
    login_dashboard()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, upload_numbers))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.job_queue.run_repeating(poll_otps, interval=15, first=5)
    logger.info("🤖 Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
