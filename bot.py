import logging
import re
import random
import requests
import os
import json
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.error import BadRequest

load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
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

# Services configuration
SERVICES = ["Facebook", "WhatsApp", "TikTok", "Instagram", "Telegram"]
SERVICE_EMOJI = {
    "Facebook": "📘", "WhatsApp": "💬", "TikTok": "🎵",
    "Instagram": "📸", "Telegram": "✈️",
}

COUNTRY_FLAGS = {
    "95": "🇲🇲", "959": "🇲🇲", "880": "🇧🇩", "91": "🇮🇳", "92": "🇵🇰",
    "1": "🇺🇸", "44": "🇬🇧", "86": "🇨🇳", "81": "🇯🇵", "82": "🇰🇷",
}

COUNTRY_NAMES = {
    "95": "Myanmar", "959": "Myanmar", "880": "Bangladesh", "91": "India",
    "92": "Pakistan", "1": "USA", "44": "UK", "86": "China", "81": "Japan", "82": "South Korea",
}

if not BOT_TOKEN:
    logger.error("BOT_TOKEN is not set!")
    exit(1)

# Global state variables
numbers_pool = {s: {} for s in SERVICES}
user_numbers = {}
user_history = {}
otp_history = {}
otp_cache = {}
banned_users = set()
all_users = set()
session_cookie = None

# ─── Dashboard Functions ──────────────────────────────────────────

def login_dashboard():
    """Login to dashboard with CAPTCHA solving"""
    global session_cookie
    try:
        session = requests.Session()
        resp = session.get("http://185.2.83.39/ints/login", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        
        # Solve CAPTCHA
        captcha_match = re.search(r'What is (\d+)\s*\+\s*(\d+)', resp.text)
        if captcha_match:
            a, b = int(captcha_match.group(1)), int(captcha_match.group(2))
            captcha_answer = str(a + b)
            logger.info(f"🔢 CAPTCHA: {a}+{b}={captcha_answer}")
        else:
            captcha_answer = "6"

        login_resp = session.post(
            "http://185.2.83.39/ints/login",
            data={"username": DASHBOARD_USER, "password": DASHBOARD_PASS, "captcha": captcha_answer},
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=True, timeout=10
        )
        
        if "PHPSESSID" in session.cookies:
            session_cookie = session.cookies["PHPSESSID"]
            logger.info(f"✅ Login successful: {session_cookie[:15]}...")
            return session_cookie
        else:
            logger.error(f"❌ Login failed")
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
    return None

def get_session():
    """Get current session, re-login if needed"""
    global session_cookie
    if not session_cookie:
        login_dashboard()
    return session_cookie

def fetch_otp_for_number(number: str):
    """Fetch OTP for specific number"""
    global session_cookie
    cookie = get_session()
    if not cookie:
        return None
    try:
        clean_num = number.lstrip("+").strip()
        resp = requests.get(
            f"{DASHBOARD_BASE}/res/data_smscdr.php",
            params={"sEcho": 1, "iDisplayStart": 0, "iDisplayLength": 50, "fnumber": clean_num},
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
            if rows and len(rows[0]) >= 6:
                latest = rows[0]
                return {
                    "datetime": str(latest[0]),
                    "sender": str(latest[3] or "Unknown"),
                    "message": str(latest[5] or ""),
                    "number": clean_num
                }
        elif resp.status_code in [302, 401, 403]:
            session_cookie = None
            login_dashboard()
    except Exception as e:
        logger.error(f"OTP fetch error: {e}")
    return None

def fetch_all_recent_otps():
    """Fetch all recent OTPs from dashboard"""
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
            return data.get("aaData", [])
        elif resp.status_code in [302, 401, 403]:
            session_cookie = None
            login_dashboard()
    except Exception as e:
        logger.error(f"Fetch error: {e}")
    return []

# ─── Helper Functions ─────────────────────────────────────────────

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
        prefix = number[:length]
        if prefix in COUNTRY_FLAGS:
            return COUNTRY_FLAGS[prefix]
    return "🌍"

def get_available_countries(service: str) -> list:
    assigned = {v["number"] for v in user_numbers.values()}
    available = []
    for country_code, nums in numbers_pool.get(service, {}).items():
        free = [n for n in nums if n not in assigned]
        if free:
            available.append(country_code)
    return available

def get_available_number(service: str, country_code: str):
    assigned = {v["number"] for v in user_numbers.values()}
    nums = numbers_pool.get(service, {}).get(country_code, [])
    free = [n for n in nums if n not in assigned]
    return random.choice(free) if free else None

# ─── Data Persistence ─────────────────────────────────────────────

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
        data = {
            "user_numbers": {str(k): v for k, v in user_numbers.items()},
            "banned_users": list(banned_users),
            "all_users": list(all_users),
        }
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)
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

# ─── Keyboards ────────────────────────────────────────────────────

def service_keyboard():
    buttons = []
    for s in SERVICES:
        emoji = SERVICE_EMOJI[s]
        buttons.append([InlineKeyboardButton(f"{emoji} {s}", callback_data=f"service_{s}")])
    return InlineKeyboardMarkup(buttons)

def country_keyboard(service: str):
    countries = get_available_countries(service)
    if not countries:
        return None
    buttons = []
    for code in countries:
        flag = COUNTRY_FLAGS.get(code, "🌍")
        name = COUNTRY_NAMES.get(code, code)
        buttons.append([InlineKeyboardButton(f"{flag} {name}", callback_data=f"country_{service}_{code}")])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="get_number")])
    return InlineKeyboardMarkup(buttons)

# ─── OTP Polling ──────────────────────────────────────────────────

async def poll_otps(context):
    """Background task to check for new OTPs"""
    global otp_cache
    
    rows = fetch_all_recent_otps()
    if not rows:
        return
    
    all_pool_numbers = set()
    for s in SERVICES:
        for nums in numbers_pool[s].values():
            all_pool_numbers.update([n.lstrip("+").strip() for n in nums])
    
    for row in rows:
        try:
            if len(row) < 6:
                continue
            number = str(row[2]).strip().lstrip("+")
            message = str(row[5] or "")
            
            if not message or number not in all_pool_numbers:
                continue
            
            cache_key = f"{number}:{message[:30]}"
            if cache_key in otp_cache:
                continue
            otp_cache[cache_key] = True
            
            dt_str = str(row[0])
            sender = str(row[3] or "Unknown")
            otp_code = extract_otp(message)
            flag = get_flag(number)
            
            # Send to channel
            try:
                await context.bot.send_message(
                    chat_id=OTP_CHANNEL_ID,
                    text=f"📩 *New OTP*\n\n{flag} `{mask_number(number)}`\n🏢 {sender}\n🔐 `{otp_code}`\n💬 {message[:100]}",
                    parse_mode="Markdown"
                )
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Channel error: {e}")
            
            # Notify user
            for uid, info in user_numbers.items():
                if info["number"].lstrip("+") == number:
                    try:
                        await context.bot.send_message(
                            chat_id=uid,
                            text=f"✅ *OTP Received!*\n\n{flag} `{number}`\n🏢 {sender}\n🔐 `{otp_code}`\n💬 {message[:100]}",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                    break
        except Exception as e:
            logger.error(f"Poll error: {e}")

# ─── Handlers ─────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    save_data()
    
    await update.message.reply_text(
        f"👋 Welcome *{user.first_name}*!\n\n🤖 *SMS Hadi OTP Bot*\n\nSelect a service to get a number 👇",
        parse_mode="Markdown",
        reply_markup=service_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "get_number":
        await query.edit_message_text("📲 *Select Service:*", parse_mode="Markdown", reply_markup=service_keyboard())
    
    elif data.startswith("service_"):
        service = data.replace("service_", "")
        kb = country_keyboard(service)
        if not kb:
            await query.edit_message_text(f"❌ No numbers available for {service}")
            return
        await query.edit_message_text(f"📲 *{service}* — Select Country:", parse_mode="Markdown", reply_markup=kb)
    
    elif data.startswith("country_"):
        parts = data.split("_", 2)
        if len(parts) < 3:
            return
        service, country = parts[1], parts[2]
        num = get_available_number(service, country)
        if not num:
            await query.edit_message_text("❌ No numbers available")
            return
        
        if user_id in user_numbers:
            user_numbers.pop(user_id)
        user_numbers[user_id] = {"number": num, "service": service, "country": country}
        save_data()
        
        flag = COUNTRY_FLAGS.get(country, "🌍")
        await query.edit_message_text(
            f"📞 *Your Number:*\n\n`{num}`\n\n{flag} {service}\n\n✅ Active! OTPs will be sent to the channel.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 OTP Channel", url=OTP_CHANNEL_LINK)],
                [InlineKeyboardButton("❌ Release", callback_data="release")],
            ])
        )
    
    elif data == "release":
        if user_id in user_numbers:
            user_numbers.pop(user_id)
            save_data()
            await query.edit_message_text("✅ Number released", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📲 Get New", callback_data="get_number")]]))

async def upload_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    await update.message.reply_text("📤 Send: service,country_code then file\nExample: WhatsApp,95")

# ─── Main ─────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Starting bot...")
    load_numbers()
    load_data()
    login_dashboard()
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.job_queue.run_repeating(poll_otps, interval=15, first=5)
    
    logger.info("✅ Bot running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
