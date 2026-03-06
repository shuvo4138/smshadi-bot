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

def main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Bottom reply keyboard — shown after /start"""
    buttons = [
        [KeyboardButton("📲 Get Number"), KeyboardButton("📋 Active Number")],
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("👑 Admin Panel")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

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

def admin_keyboard():
    buttons = [
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📤 Upload Numbers", callback_data="admin_upload"),
         InlineKeyboardButton("🗑 Delete Numbers", callback_data="admin_delete_menu")],
        [InlineKeyboardButton("👥 All Users", callback_data="admin_users")],
        [InlineKeyboardButton("🔄 Re-login Dashboard", callback_data="admin_relogin")],
    ]
    return InlineKeyboardMarkup(buttons)

def delete_service_keyboard():
    """Select service to delete numbers from"""
    buttons = []
    for s in SERVICES:
        emoji = SERVICE_EMOJI[s]
        buttons.append([InlineKeyboardButton(f"{emoji} {s}", callback_data=f"admin_del_service_{s}")])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
    return InlineKeyboardMarkup(buttons)

def delete_country_keyboard(service: str):
    """Select country to delete numbers from"""
    countries = list(numbers_pool.get(service, {}).keys())
    if not countries:
        return None
    buttons = []
    for code in countries:
        flag = COUNTRY_FLAGS.get(code, "🌍")
        name = COUNTRY_NAMES.get(code, code)
        count = len(numbers_pool[service][code])
        buttons.append([InlineKeyboardButton(
            f"{flag} {name} ({count} numbers)",
            callback_data=f"admin_del_country_{service}_{code}"
        )])
    buttons.append([InlineKeyboardButton("🗑 Delete ALL Services", callback_data="admin_del_all")])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_delete_menu")])
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
        reply_markup=main_keyboard(user.id)
    )

async def reply_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the 3 reply keyboard buttons"""
    user = update.effective_user
    text = update.message.text.strip()

    # ── 📲 Get Number ──
    if text == "📲 Get Number":
        await update.message.reply_text(
            "📲 *Select Service:*",
            parse_mode="Markdown",
            reply_markup=service_keyboard()
        )

    # ── 📋 Active Number ──
    elif text == "📋 Active Number":
        if user.id in user_numbers:
            info = user_numbers[user.id]
            num = info["number"]
            service = info["service"]
            country = info.get("country", "")
            flag = COUNTRY_FLAGS.get(country, get_flag(num))
            await update.message.reply_text(
                f"📋 *Your Active Number:*\n\n`{num}`\n\n{flag} {service}\n\n✅ Waiting for OTP...",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 OTP Channel", url=OTP_CHANNEL_LINK)],
                    [InlineKeyboardButton("❌ Release", callback_data="release")],
                ])
            )
        else:
            await update.message.reply_text(
                "❌ You don't have an active number.\n\nPress *📲 Get Number* to get one.",
                parse_mode="Markdown"
            )

    # ── 👑 Admin Panel ──
    elif text == "👑 Admin Panel":
        if user.id != ADMIN_ID:
            await update.message.reply_text("❌ Access denied.")
            return
        total_numbers = sum(
            len(nums)
            for s in SERVICES
            for nums in numbers_pool[s].values()
        )
        await update.message.reply_text(
            f"👑 *Admin Panel*\n\n"
            f"👥 Total Users: `{len(all_users)}`\n"
            f"📞 Active Assignments: `{len(user_numbers)}`\n"
            f"📱 Total Numbers: `{total_numbers}`\n"
            f"🚫 Banned: `{len(banned_users)}`",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
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

    # ── Admin callbacks ──
    elif data == "admin_stats":
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        total_numbers = sum(len(nums) for s in SERVICES for nums in numbers_pool[s].values())
        await query.edit_message_text(
            f"📊 *Stats*\n\n"
            f"👥 Total Users: `{len(all_users)}`\n"
            f"📞 Active Assignments: `{len(user_numbers)}`\n"
            f"📱 Total Numbers: `{total_numbers}`\n"
            f"🚫 Banned: `{len(banned_users)}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
        )

    elif data == "admin_users":
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        user_list = "\n".join([f"`{uid}`" for uid in list(all_users)[:20]])
        await query.edit_message_text(
            f"👥 *Users (first 20):*\n\n{user_list or 'No users yet'}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
        )

    elif data == "admin_relogin":
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        global session_cookie
        session_cookie = None
        result = login_dashboard()
        status = "✅ Re-login successful!" if result else "❌ Re-login failed!"
        await query.edit_message_text(
            status,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
        )

    elif data == "admin_upload":
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        await query.edit_message_text(
            "📤 *Upload Numbers via TXT File*\n\n"
            "Send a `.txt` file with this format:\n\n"
            "`service:country_code`\n"
            "`+959123456789`\n"
            "`+959987654321`\n\n"
            "Example file content:\n"
            "`WhatsApp:95`\n"
            "`+959111222333`\n"
            "`+959444555666`\n\n"
            "Or use command:\n`/addnumbers WhatsApp 95`\nthen paste numbers.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
        )

    elif data == "admin_delete_menu":
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        await query.edit_message_text(
            "🗑 *Delete Numbers*\n\nSelect a service:",
            parse_mode="Markdown",
            reply_markup=delete_service_keyboard()
        )

    elif data.startswith("admin_del_service_"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        service = data.replace("admin_del_service_", "")
        kb = delete_country_keyboard(service)
        if not kb:
            await query.answer(f"❌ No numbers in {service}", show_alert=True)
            return
        await query.edit_message_text(
            f"🗑 *Delete from {service}*\n\nSelect country:",
            parse_mode="Markdown",
            reply_markup=kb
        )

    elif data.startswith("admin_del_country_"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        parts = data.replace("admin_del_country_", "").split("_", 1)
        if len(parts) < 2:
            return
        service, country = parts[0], parts[1]
        count = len(numbers_pool.get(service, {}).get(country, []))
        await query.edit_message_text(
            f"⚠️ *Confirm Delete*\n\n"
            f"Service: *{service}*\n"
            f"Country: `{country}`\n"
            f"Numbers: `{count}`\n\n"
            f"Are you sure?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"admin_del_confirm_{service}_{country}")],
                [InlineKeyboardButton("🔙 Cancel", callback_data=f"admin_del_service_{service}")]
            ])
        )

    elif data.startswith("admin_del_confirm_"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        parts = data.replace("admin_del_confirm_", "").split("_", 1)
        if len(parts) < 2:
            return
        service, country = parts[0], parts[1]
        if service in numbers_pool and country in numbers_pool[service]:
            del numbers_pool[service][country]
            save_numbers()
            await query.edit_message_text(
                f"✅ Deleted all numbers for *{service}* / `{country}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
            )
        else:
            await query.edit_message_text("❌ Not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_del_all":
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        await query.edit_message_text(
            "⚠️ *Confirm Delete ALL Numbers*\n\nThis will remove ALL numbers from ALL services!\n\nAre you sure?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes, Delete All", callback_data="admin_del_all_confirm")],
                [InlineKeyboardButton("🔙 Cancel", callback_data="admin_delete_menu")]
            ])
        )

    elif data == "admin_del_all_confirm":
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        global numbers_pool
        numbers_pool = {s: {} for s in SERVICES}
        save_numbers()
        await query.edit_message_text(
            "✅ All numbers deleted.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
        )

    elif data == "admin_back":
        if user_id != ADMIN_ID:
            return
        total_numbers = sum(len(nums) for s in SERVICES for nums in numbers_pool[s].values())
        await query.edit_message_text(
            f"👑 *Admin Panel*\n\n"
            f"👥 Total Users: `{len(all_users)}`\n"
            f"📞 Active Assignments: `{len(user_numbers)}`\n"
            f"📱 Total Numbers: `{total_numbers}`\n"
            f"🚫 Banned: `{len(banned_users)}`",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )

async def upload_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("📤 Send: service,country_code then file\nExample: WhatsApp,95")

async def add_numbers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /addnumbers <service> <country_code>"""
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /addnumbers <service> <country_code>")
        return
    service = args[0].capitalize()
    country_code = args[1]
    if service not in SERVICES:
        await update.message.reply_text(f"❌ Invalid service. Use: {', '.join(SERVICES)}")
        return
    context.user_data["pending_upload"] = {"service": service, "country": country_code}
    await update.message.reply_text(
        f"✅ Ready! Now send numbers for *{service}* / `{country_code}` (one per line):",
        parse_mode="Markdown"
    )

async def handle_number_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pasted numbers after /addnumbers"""
    if update.effective_user.id != ADMIN_ID:
        return
    pending = context.user_data.get("pending_upload")
    if not pending:
        return
    text = update.message.text.strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    numbers = [l if l.startswith("+") else f"+{l}" for l in lines if re.match(r'^\+?\d{7,15}$', l)]
    if not numbers:
        await update.message.reply_text("❌ No valid numbers found.")
        return
    service = pending["service"]
    country = pending["country"]
    if country not in numbers_pool[service]:
        numbers_pool[service][country] = []
    added = 0
    for n in numbers:
        if n not in numbers_pool[service][country]:
            numbers_pool[service][country].append(n)
            added += 1
    save_numbers()
    context.user_data.pop("pending_upload", None)
    await update.message.reply_text(
        f"✅ Added *{added}* numbers for *{service}* / `{country}`\n"
        f"📱 Total: `{len(numbers_pool[service][country])}`",
        parse_mode="Markdown"
    )

async def handle_txt_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle .txt file upload from admin to add numbers"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    doc = update.message.document
    if not doc or not doc.file_name.endswith(".txt"):
        return
    
    try:
        file = await context.bot.get_file(doc.file_id)
        content = bytes()
        # Download file content
        import io
        buf = io.BytesIO()
        await file.download_to_memory(buf)
        buf.seek(0)
        text = buf.read().decode("utf-8", errors="ignore")
    except Exception as e:
        await update.message.reply_text(f"❌ File read error: {e}")
        return
    
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        await update.message.reply_text("❌ File is empty.")
        return
    
    # Parse header line: service:country_code
    header = lines[0]
    if ":" not in header:
        await update.message.reply_text(
            "❌ First line must be `service:country_code`\n\nExample: `WhatsApp:95`",
            parse_mode="Markdown"
        )
        return
    
    service_raw, country_code = header.split(":", 1)
    service = service_raw.strip().capitalize()
    country_code = country_code.strip()
    
    if service not in SERVICES:
        await update.message.reply_text(f"❌ Invalid service: `{service}`\n\nUse: {', '.join(SERVICES)}", parse_mode="Markdown")
        return
    
    number_lines = lines[1:]
    numbers = [l if l.startswith("+") else f"+{l}" for l in number_lines if re.match(r'^\+?\d{7,15}$', l)]
    
    if not numbers:
        await update.message.reply_text("❌ No valid numbers found in file.")
        return
    
    if country_code not in numbers_pool[service]:
        numbers_pool[service][country_code] = []
    
    added = 0
    skipped = 0
    for n in numbers:
        if n not in numbers_pool[service][country_code]:
            numbers_pool[service][country_code].append(n)
            added += 1
        else:
            skipped += 1
    
    save_numbers()
    flag = COUNTRY_FLAGS.get(country_code, "🌍")
    await update.message.reply_text(
        f"✅ *Upload Complete!*\n\n"
        f"Service: *{service}* {flag}\n"
        f"Country: `{country_code}`\n"
        f"✅ Added: `{added}`\n"
        f"⏭ Skipped (duplicate): `{skipped}`\n"
        f"📱 Total now: `{len(numbers_pool[service][country_code])}`",
        parse_mode="Markdown"
    )

# ─── Main ─────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Starting bot...")
    load_numbers()
    load_data()
    login_dashboard()
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addnumbers", add_numbers_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    # TXT file upload handler (admin)
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), handle_txt_file))

    # Reply keyboard buttons handler (must be before generic text handler)
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'^(📲 Get Number|📋 Active Number|👑 Admin Panel)$'),
        reply_keyboard_handler
    ))

    # Number upload handler for admin (after /addnumbers)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_number_upload
    ))

    app.job_queue.run_repeating(poll_otps, interval=15, first=5)
    
    logger.info("✅ Bot running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
