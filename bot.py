import logging
import re
import random
import requests
import os
import json
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "1984916365").strip())
OTP_CHANNEL_ID = int(os.getenv("OTP_CHANNEL_ID", "-1002625886518").strip())
OTP_CHANNEL_LINK = os.getenv("OTP_CHANNEL_LINK", "https://t.me/+SWraCXOQrWM4Mzg9").strip()
JOIN_CHANNEL = os.getenv("JOIN_CHANNEL", "https://t.me/alwaysrvice24hours").strip()
DASHBOARD_BASE = "http://185.2.83.39/ints/agent/SMSDashboard"
DASHBOARD_USER = os.getenv("DASHBOARD_USER", "shuvo098").strip()
DASHBOARD_PASS = os.getenv("DASHBOARD_PASS", "Shuvo.99@@").strip()
NUMBERS_FILE = "numbers.json"
DATA_FILE = "bot_data.json"

SERVICES = ["Facebook", "WhatsApp", "TikTok", "Instagram", "Telegram"]
SERVICE_EMOJI = {"Facebook": "📘", "WhatsApp": "💬", "TikTok": "🎵", "Instagram": "📸", "Telegram": "✈️"}
COUNTRY_FLAGS = {"95": "🇲🇲", "959": "🇲🇲", "880": "🇧🇩", "91": "🇮🇳"}
COUNTRY_NAMES = {"95": "Myanmar", "959": "Myanmar", "880": "Bangladesh", "91": "India"}

if not BOT_TOKEN:
    logger.error("BOT_TOKEN not set!")
    exit(1)

# Global state
numbers_pool = {s: {} for s in SERVICES}
user_numbers = {}
otp_cache = {}
banned_users = set()
all_users = set()
session_cookie = None

# ─── Dashboard ────────────────────────────────────────────────────

def login_dashboard():
    global session_cookie
    try:
        session = requests.Session()
        resp = session.get("http://185.2.83.39/ints/login", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        
        captcha_match = re.search(r'What is (\d+)\s*\+\s*(\d+)', resp.text)
        if captcha_match:
            a, b = int(captcha_match.group(1)), int(captcha_match.group(2))
            answer = str(a + b)
            logger.info(f"🔢 CAPTCHA: {a}+{b}={answer}")
        else:
            answer = "6"
        
        login_resp = session.post(
            "http://185.2.83.39/ints/login",
            data={"username": DASHBOARD_USER, "password": DASHBOARD_PASS, "captcha": answer},
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=True, timeout=10
        )
        
        if "PHPSESSID" in session.cookies:
            session_cookie = session.cookies["PHPSESSID"]
            logger.info(f"✅ Login: {session_cookie[:15]}...")
            return session_cookie
        logger.error("❌ Login failed")
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
    return None

def get_session():
    global session_cookie
    if not session_cookie:
        login_dashboard()
    return session_cookie

def fetch_all_recent_otps():
    global session_cookie
    cookie = get_session()
    if not cookie:
        return []
    
    try:
        resp = requests.get(
            f"{DASHBOARD_BASE}/res/data_smscdr.php",
            params={"sEcho": 1, "iDisplayStart": 0, "iDisplayLength": 100},
            headers={
                "Cookie": f"PHPSESSID={cookie}",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{DASHBOARD_BASE}/SMSCDRReports",
                "User-Agent": "Mozilla/5.0"
            },
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            rows = data.get("aaData", [])
            logger.info(f"📡 Dashboard: {len(rows)} records")
            return rows
        elif resp.status_code in [302, 401, 403]:
            logger.warning("⚠️ Session expired")
            session_cookie = None
            login_dashboard()
    except Exception as e:
        logger.error(f"❌ Fetch error: {e}")
    return []

# ─── Helpers ──────────────────────────────────────────────────────

def extract_otp(msg: str) -> str:
    if not msg:
        return ""
    msg = msg.replace("# ", "").replace("#", "")
    codes = re.findall(r'\b\d{4,8}\b', msg)
    return codes[0] if codes else ""

def mask_number(number: str) -> str:
    n = str(number)
    return n[:4] + "★★★★" + n[-4:] if len(n) >= 8 else n

def get_flag(number: str) -> str:
    number = number.lstrip("+").strip()
    for length in [4, 3, 2, 1]:
        if number[:length] in COUNTRY_FLAGS:
            return COUNTRY_FLAGS[number[:length]]
    return "🌍"

def get_available_countries(service: str) -> list:
    assigned = {v["number"] for v in user_numbers.values()}
    available = []
    for code, nums in numbers_pool.get(service, {}).items():
        if any(n not in assigned for n in nums):
            available.append(code)
    return available

def get_available_number(service: str, code: str):
    assigned = {v["number"] for v in user_numbers.values()}
    nums = numbers_pool.get(service, {}).get(code, [])
    free = [n for n in nums if n not in assigned]
    return random.choice(free) if free else None

# ─── Persistence ──────────────────────────────────────────────────

def save_numbers():
    try:
        with open(NUMBERS_FILE, "w") as f:
            json.dump(numbers_pool, f)
    except Exception as e:
        logger.error(f"Save error: {e}")

def load_numbers():
    global numbers_pool
    try:
        if os.path.exists(NUMBERS_FILE):
            with open(NUMBERS_FILE, "r") as f:
                data = json.load(f)
            for s in SERVICES:
                numbers_pool[s] = data.get(s, {})
            logger.info("📂 Numbers loaded")
    except Exception as e:
        logger.error(f"Load error: {e}")

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({
                "user_numbers": {str(k): v for k, v in user_numbers.items()},
                "banned_users": list(banned_users),
                "all_users": list(all_users),
            }, f)
    except Exception as e:
        logger.error(f"Save error: {e}")

def load_data():
    global user_numbers, banned_users, all_users
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            user_numbers = {int(k): v for k, v in data.get("user_numbers", {}).items()}
            banned_users = set(data.get("banned_users", []))
            all_users = set(data.get("all_users", []))
    except Exception as e:
        logger.error(f"Load error: {e}")

def preload_cache():
    global otp_cache
    logger.info("🔄 Preloading cache...")
    rows = fetch_all_recent_otps()
    count = 0
    for row in rows:
        try:
            if len(row) >= 6:
                number = str(row[2]).strip().lstrip("+")
                message = str(row[5] or "")
                dt = str(row[0])
                if number and message:
                    cache_key = f"{number}:{dt}:{message[:30]}"
                    otp_cache[cache_key] = True
                    count += 1
        except:
            pass
    logger.info(f"✅ Preloaded {count} OTPs")

# ─── Keyboards ────────────────────────────────────────────────────

def main_keyboard(user_id):
    buttons = [[KeyboardButton("📲 Get Number"), KeyboardButton("📋 Active Number")]]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("👑 Admin")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def service_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(f"{SERVICE_EMOJI[s]} {s}", callback_data=f"service_{s}")] for s in SERVICES])

def country_keyboard(service):
    countries = get_available_countries(service)
    if not countries:
        return None
    buttons = [[InlineKeyboardButton(f"{COUNTRY_FLAGS.get(c,'🌍')} {COUNTRY_NAMES.get(c,c)}", callback_data=f"country_{service}_{c}")] for c in countries]
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="get_number")])
    return InlineKeyboardMarkup(buttons)

# ─── Polling ──────────────────────────────────────────────────────

async def poll_otps(context):
    global otp_cache
    
    rows = fetch_all_recent_otps()
    if not rows:
        return
    
    all_pool_numbers = set()
    for s in SERVICES:
        for nums in numbers_pool[s].values():
            all_pool_numbers.update([n.lstrip("+").strip() for n in nums])
    
    new_count = 0
    current_time = datetime.now()
    
    for row in rows:
        try:
            if len(row) < 6:
                continue
            
            dt_str = str(row[0])
            number = str(row[2]).strip().lstrip("+")
            sender = str(row[3] or "Unknown")
            message = str(row[5] or "")
            
            if not message or not number:
                continue
            
            # Only process last 5 minutes
            try:
                msg_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                if (current_time - msg_time).total_seconds() > 300:
                    continue
            except:
                pass
            
            cache_key = f"{number}:{dt_str}:{message[:30]}"
            if cache_key in otp_cache:
                continue
            
            if number not in all_pool_numbers:
                continue
            
            otp_cache[cache_key] = True
            otp_code = extract_otp(message)
            flag = get_flag(number)
            
            logger.info(f"🔔 NEW! {number} | {otp_code}")
            new_count += 1
            
            # Channel
            try:
                await context.bot.send_message(
                    OTP_CHANNEL_ID,
                    f"📩 *New OTP*\n\n{flag} `{mask_number(number)}`\n🏢 {sender}\n🔐 `{otp_code}`\n💬 {message[:100]}",
                    parse_mode="Markdown"
                )
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ Channel: {e}")
            
            # User
            for uid, info in user_numbers.items():
                if info["number"].lstrip("+").strip() == number:
                    try:
                        await context.bot.send_message(uid, f"✅ *OTP!*\n\n{flag} `{number}`\n🏢 {sender}\n🔐 `{otp_code}`\n💬 {message[:100]}", parse_mode="Markdown")
                    except:
                        pass
                    break
        except Exception as e:
            logger.error(f"❌ Poll: {e}")
    
    if new_count > 0:
        logger.info(f"✅ Sent {new_count} OTPs")

# ─── Handlers ─────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    save_data()
    await update.message.reply_text(
        f"👋 Welcome *{user.first_name}*!\n\n🤖 *SMS Hadi OTP Bot*",
        parse_mode="Markdown",
        reply_markup=main_keyboard(user.id)
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    if context.user_data.get("waiting_upload") and user_id == ADMIN_ID:
        context.user_data["waiting_upload"] = False
        service = context.user_data.get("upload_service", "")
        code = text.strip()
        context.user_data["upload_country"] = code
        await update.message.reply_text(f"✅ Country: {code}\n\nSend TXT/CSV file")
        return
    
    if text == "📲 Get Number":
        await update.message.reply_text("📲 *Select:*", parse_mode="Markdown", reply_markup=service_keyboard())
    elif text == "📋 Active Number":
        if user_id in user_numbers:
            info = user_numbers[user_id]
            await update.message.reply_text(
                f"📞 `{info['number']}`\n\n{SERVICE_EMOJI[info['service']]} {info['service']}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Release", callback_data="release")]])
            )
        else:
            await update.message.reply_text("❌ No number")
    elif text == "👑 Admin" and user_id == ADMIN_ID:
        total = sum(sum(len(nums) for nums in numbers_pool[s].values()) for s in SERVICES)
        await update.message.reply_text(
            f"👑 *Admin*\n\n📦 Numbers: {total}\n🔑 Session: {'✅' if session_cookie else '❌'}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Upload", callback_data="admin_upload")],
                [InlineKeyboardButton("🔄 Re-login", callback_data="admin_relogin")],
            ])
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, user_id = query.data, query.from_user.id
    
    if data == "get_number":
        await query.edit_message_text("📲 *Select:*", parse_mode="Markdown", reply_markup=service_keyboard())
    elif data.startswith("service_"):
        service = data.replace("service_", "")
        kb = country_keyboard(service)
        if not kb:
            await query.edit_message_text(f"❌ No numbers")
            return
        await query.edit_message_text(f"{SERVICE_EMOJI[service]} *{service}*", parse_mode="Markdown", reply_markup=kb)
    elif data.startswith("country_"):
        parts = data.split("_", 2)
        if len(parts) < 3:
            return
        service, country = parts[1], parts[2]
        num = get_available_number(service, country)
        if not num:
            await query.edit_message_text("❌ No numbers")
            return
        if user_id in user_numbers:
            user_numbers.pop(user_id)
        user_numbers[user_id] = {"number": num, "service": service, "country": country}
        save_data()
        await query.edit_message_text(
            f"📞 `{num}`\n\n{SERVICE_EMOJI[service]} {service}\n\n✅ Active!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Release", callback_data="release")]])
        )
    elif data == "release":
        if user_id in user_numbers:
            user_numbers.pop(user_id)
            save_data()
            await query.edit_message_text("✅ Released")
    elif data == "admin_upload" and user_id == ADMIN_ID:
        buttons = [[InlineKeyboardButton(f"{SERVICE_EMOJI[s]} {s}", callback_data=f"upload_{s}")] for s in SERVICES]
        await query.edit_message_text("📤 Service:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data.startswith("upload_") and user_id == ADMIN_ID:
        service = data.replace("upload_", "")
        context.user_data["upload_service"] = service
        context.user_data["waiting_upload"] = True
        await query.edit_message_text(f"📤 {service}\n\nCountry code (e.g., 95):")
    elif data == "admin_relogin" and user_id == ADMIN_ID:
        global session_cookie
        session_cookie = None
        result = login_dashboard()
        await context.bot.send_message(user_id, "✅ Success!" if result else "❌ Failed!")

async def upload_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not update.message.document:
        return
    service = context.user_data.pop("upload_service", None)
    country = context.user_data.pop("upload_country", None)
    if not service or not country:
        return
    
    doc = update.message.document
    file = await doc.get_file()
    content = await file.download_as_bytearray()
    text = content.decode("utf-8", errors="ignore")
    
    added = []
    for token in re.split(r'[\s,;]+', text):
        token = token.strip().replace("+", "")
        if token.isdigit() and 8 <= len(token) <= 15:
            if country not in numbers_pool[service]:
                numbers_pool[service][country] = []
            if token not in numbers_pool[service][country]:
                numbers_pool[service][country].append(token)
                added.append(token)
    
    save_numbers()
    await update.message.reply_text(f"✅ Added {len(added)}\n📦 Total: {len(numbers_pool[service][country])}")

# ─── Main ─────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Starting...")
    load_numbers()
    load_data()
    login_dashboard()
    preload_cache()
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, upload_numbers))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.job_queue.run_repeating(poll_otps, interval=15, first=10)
    
    logger.info("✅ Running! Polling every 15s for NEW OTPs (last 5 min)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
