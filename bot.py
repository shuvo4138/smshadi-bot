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

# Suppress SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "1984916365").strip())
OTP_CHANNEL_ID = int(os.getenv("OTP_CHANNEL_ID", "-1002625886518").strip())
JOIN_CHANNEL = os.getenv("JOIN_CHANNEL", "https://t.me/alwaysrvice24hours").strip()
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
session = None

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
    global session
    try:
        session = requests.Session()
        session.verify = False
        
        login_resp = session.post(
            "http://185.2.83.39/ints/agent/",
            data={"username": DASHBOARD_USER, "password": DASHBOARD_PASS},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            allow_redirects=True,
            timeout=10,
            verify=False
        )
        
        logger.info(f"🔐 Login: {login_resp.status_code}")
        if "PHPSESSID" in session.cookies:
            logger.info(f"✅ Login success!")
            return True
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
    return False

def get_session_instance():
    global session
    if session is None:
        login_dashboard()
    return session

def fetch_all_recent_otps():
    sess = get_session_instance()
    if sess is None:
        return []
    try:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        resp = sess.get(
            "http://185.2.83.39/ints/agent/res/data_smscdr.php",
            params={"fdate1": f"{today} 00:00:00", "fdate2": f"{today} 23:59:59", "iDisplayStart": "0", "iDisplayLength": "100", "sEcho": "1"},
            headers={"X-Requested-With": "XMLHttpRequest", "User-Agent": "Mozilla/5.0"},
            timeout=10,
            verify=False
        )
        
        logger.info(f"📡 CDR Status: {resp.status_code}")
        if resp.status_code == 200:
            try:
                data = resp.json()
                rows = data.get("aaData", [])
                logger.info(f"✅ Got {len(rows)} SMS rows")
                return rows
            except:
                logger.error(f"JSON error")
        elif resp.status_code in [302, 401, 403]:
            global session
            session = None
            login_dashboard()
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    return []

def extract_otp(msg: str) -> str:
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

async def poll_otps(context):
    rows = fetch_all_recent_otps()
    for row in rows:
        if len(row) < 6:
            continue
        dt_str, number, sender, message = str(row[0]), str(row[2]), str(row[3] or ""), str(row[5] or "")
        if not message or not number:
            continue
        cache_key = f"{number}:{message[:20]}"
        if cache_key in otp_cache:
            continue
        otp_cache[cache_key] = True
        otp_code = extract_otp(message)
        owner_id = next((uid for uid, num in user_numbers.items() if num == number or num.lstrip("+") == number.lstrip("+")), None)
        
        try:
            await context.bot.send_message(chat_id=OTP_CHANNEL_ID, text=f"📩 *নতুন OTP*\n📞 `{mask_number(number)}`\n🏢 {sender}\n🔐 `{otp_code}`\n💬 {message[:100]}\n🕐 {dt_str}", parse_mode="Markdown")
        except:
            pass
        
        if owner_id:
            try:
                await context.bot.send_message(chat_id=owner_id, text=f"✅ *OTP এসেছে!*\n\n📞 `{number}`\n🏢 *{sender}*\n🔐 `{otp_code}`\n💬 _{message[:100]}_\n🕐 {dt_str}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Channel", url=JOIN_CHANNEL)]]))
            except:
                pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"👋 স্বাগতম!\n\n🤖 *SMS Hadi OTP Bot*", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📲 Get Number"), KeyboardButton("🔍 Check OTP")], [KeyboardButton("📋 My Number")], [KeyboardButton("👑 Admin Panel")]], resize_keyboard=True))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, text = update.effective_user.id, update.message.text
    
    if text == "📲 Get Number":
        if not numbers_pool:
            await update.message.reply_text("❌ কোনো number নেই")
            return
        if user_id in user_numbers:
            await update.message.reply_text(f"✅ `{user_numbers[user_id]}`", parse_mode="Markdown")
            return
        num = get_available_number()
        if not num:
            await update.message.reply_text("❌ সব busy")
            return
        user_numbers[user_id] = num
        await update.message.reply_text(f"✅ `{num}`", parse_mode="Markdown")
    
    elif text == "👑 Admin Panel":
        if user_id != ADMIN_ID:
            return
        await update.message.reply_text(f"📦 Total: {len(numbers_pool)}\n👥 Assigned: {len(user_numbers)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 Upload", callback_data="admin_upload")], [InlineKeyboardButton("🔄 Re-Login", callback_data="admin_relogin")]]))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "admin_relogin" and query.from_user.id == ADMIN_ID:
        global session
        session = None
        login_dashboard()
        await context.bot.send_message(chat_id=query.from_user.id, text="✅ Re-login done")

async def upload_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not update.message.document:
        return
    file = await update.message.document.get_file()
    content = (await file.download_as_bytearray()).decode("utf-8", errors="ignore")
    new_numbers = [t.strip().replace("+", "") for t in re.split(r'[\s,;]+', content) if t.strip().replace("+", "").isdigit() and 8 <= len(t.strip().replace("+", "")) <= 15]
    added = [n for n in new_numbers if n not in numbers_pool]
    numbers_pool.extend(added)
    save_numbers()
    await update.message.reply_text(f"✅ নতুন: {len(added)}\n📦 Total: {len(numbers_pool)}")

def main():
    load_numbers()
    app = Application.builder().token(BOT_TOKEN).build()
    logger.info("🔐 Logging in...")
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
