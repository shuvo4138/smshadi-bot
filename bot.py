import asyncio
import logging
import re
import io
import csv
import random
import requests
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
BOT_TOKEN = os.getenv(" ", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1984916365"))
OTP_CHANNEL_ID = int(os.getenv("OTP_CHANNEL_ID", "-1002625886518"))
JOIN_CHANNEL = os.getenv("JOIN_CHANNEL", "https://t.me/alwaysrvice24hours")
DASHBOARD_BASE = os.getenv("DASHBOARD_BASE", "http://185.2.83.39/ints/agent/SMSDashboard")
DASHBOARD_USER = os.getenv("DASHBOARD_USER", "")
DASHBOARD_PASS = os.getenv("DASHBOARD_PASS", "")

if not BOT_TOKEN:
    logger.error("BOT_TOKEN is not set in environment variables!")
    exit(1)

numbers_pool = []
user_numbers = {}
otp_cache = {}
session_cookie = None

def login_dashboard():
    global session_cookie
    try:
        session = requests.Session()
        resp = session.post(
            "http://185.2.83.39/ints/agent/",
            data={"username": DASHBOARD_USER, "password": DASHBOARD_PASS},
            allow_redirects=True,
            timeout=10
        )
        if "PHPSESSID" in session.cookies:
            session_cookie = session.cookies["PHPSESSID"]
            logger.info(f"Login success: {session_cookie}")
            return session_cookie
    except Exception as e:
        logger.error(f"Login error: {e}")
    return None

def get_session():
    global session_cookie
    if not session_cookie:
        login_dashboard()
    return session_cookie

def fetch_otp_for_number(number: str):
    cookie = get_session()
    if not cookie:
        return None
    try:
        clean_num = number.lstrip("+")
        resp = requests.get(
            f"{DASHBOARD_BASE}/res/data_smscdr.php",
            params={"sEcho": 1, "iDisplayStart": 0, "iDisplayLength": 50, "fnumber": clean_num},
            headers={"Cookie": f"PHPSESSID={cookie}", "X-Requested-With": "XMLHttpRequest", "Referer": f"{DASHBOARD_BASE}/SMSCDRReports"},
            timeout=10
        )
        data = resp.json()
        rows = data.get("aaData", [])
        if rows:
            latest = rows[0]
            if len(latest) >= 6:
                return {"datetime": latest[0], "sender": str(latest[3] or ""), "message": str(latest[5] or ""), "number": clean_num}
    except Exception as e:
        logger.error(f"OTP fetch error: {e}")
        global session_cookie
        session_cookie = None
    return None

def fetch_all_recent_otps():
    cookie = get_session()
    if not cookie:
        return []
    try:
        resp = requests.get(
            f"{DASHBOARD_BASE}/res/data_smscdr.php",
            params={"sEcho": 1, "iDisplayStart": 0, "iDisplayLength": 100},
            headers={"Cookie": f"PHPSESSID={cookie}", "X-Requested-With": "XMLHttpRequest", "Referer": f"{DASHBOARD_BASE}/SMSCDRReports"},
            timeout=10
        )
        data = resp.json()
        return data.get("aaData", [])
    except Exception as e:
        logger.error(f"Recent OTP error: {e}")
        global session_cookie
        session_cookie = None
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
            except Exception as e:
                logger.error(f"User notify error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📲 Number নিন", callback_data="get_number")],
        [InlineKeyboardButton("🔍 OTP Check করুন", callback_data="check_otp")],
        [InlineKeyboardButton("📢 OTP Channel", url=JOIN_CHANNEL)],
    ]
    await update.message.reply_text(
        f"👋 স্বাগতম {user.first_name}!\n\n🤖 *SMS Hadi OTP Bot*\n\nMyanmar number নিন এবং OTP receive করুন।",
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
            await query.edit_message_text("❌ এখন কোনো number নেই। Admin কে জানান।")
            return
        if user_id in user_numbers:
            num = user_numbers[user_id]
            keyboard = [
                [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
                [InlineKeyboardButton("📢 OTP Channel", url=JOIN_CHANNEL)],
                [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
            ]
            await query.edit_message_text(f"✅ আপনার number:\n`{num}`\n\nOTP আসলে notify করা হবে।", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        num = get_available_number()
        if not num:
            await query.edit_message_text("❌ সব number busy। পরে try করুন।")
            return
        user_numbers[user_id] = num
        keyboard = [
            [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
            [InlineKeyboardButton("📢 OTP Channel", url=JOIN_CHANNEL)],
            [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
        ]
        await query.edit_message_text(f"✅ *আপনার Number:*\n\n`{num}`\n\nOTP আসলে সাথে সাথে notify করা হবে! 🔔", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "check_otp":
        if user_id not in user_numbers:
            keyboard = [[InlineKeyboardButton("📲 Number নিন", callback_data="get_number")]]
            await query.edit_message_text("❌ আগে number নিন।", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        num = user_numbers[user_id]
        await query.edit_message_text(f"🔍 `{num}` এর OTP খুঁজছি...", parse_mode="Markdown")
        result = fetch_otp_for_number(num)
        if result:
            otp_code = extract_otp(result["message"])
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{num}")],
                [InlineKeyboardButton("📢 OTP Channel", url=JOIN_CHANNEL)],
            ]
            await query.edit_message_text(
                f"✅ *Latest OTP:*\n\n📞 `{num}`\n🏢 From: *{result['sender']}*\n🔐 OTP: `{otp_code}`\n💬 _{result['message'][:100]}_\n🕐 {result['datetime']}",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [[InlineKeyboardButton("🔄 আবার Check", callback_data="check_otp")]]
            await query.edit_message_text(f"⏳ `{num}` এ এখনো OTP আসেনি।", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("refresh_"):
        num = data.replace("refresh_", "")
        result = fetch_otp_for_number(num)
        if result:
            otp_code = extract_otp(result["message"])
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{num}")],
                [InlineKeyboardButton("📢 OTP Channel", url=JOIN_CHANNEL)],
            ]
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

async def upload_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.document:
        await update.message.reply_text("📤 CSV বা TXT file পাঠান।\n\nFormat:\n```\n959655653869\n959654946028\n```", parse_mode="Markdown")
        return
    doc = update.message.document
    file = await doc.get_file()
    content = await file.download_as_bytearray()
    text = content.decode("utf-8", errors="ignore")
    new_numbers = []
    if doc.file_name.endswith(".csv"):
        reader = csv.reader(io.StringIO(text))
        for row in reader:
            for cell in row:
                cell = cell.strip().replace("+", "").replace(" ", "")
                if cell.isdigit() and 8 <= len(cell) <= 15:
                    new_numbers.append(cell)
    else:
        for line in text.splitlines():
            line = line.strip().replace("+", "").replace(" ", "")
            if line.isdigit() and 8 <= len(line) <= 15:
                new_numbers.append(line)
    existing = set(numbers_pool)
    added = [n for n in new_numbers if n not in existing]
    numbers_pool.extend(added)
    await update.message.reply_text(f"✅ *Upload সফল!*\n\n📥 নতুন: {len(added)}\n📦 Total: {len(numbers_pool)}", parse_mode="Markdown")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    assigned = len(user_numbers)
    available = len(numbers_pool) - assigned
    text = f"📊 *Bot Statistics*\n\n📦 Total: {len(numbers_pool)}\n✅ Available: {available}\n👥 Assigned: {assigned}\n🔑 Session: {'✅' if session_cookie else '❌'}"
    await update.message.reply_text(text, parse_mode="Markdown")

async def clear_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    numbers_pool.clear()
    user_numbers.clear()
    await update.message.reply_text("✅ সব numbers clear হয়েছে।")

async def relogin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    global session_cookie
    session_cookie = None
    result = login_dashboard()
    await update.message.reply_text("✅ Re-login সফল!" if result else "❌ Login failed!")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    login_dashboard()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("clear", clear_numbers))
    app.add_handler(CommandHandler("relogin", relogin_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, upload_numbers))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.job_queue.run_repeating(poll_otps, interval=15, first=5)
    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
