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
CR_API_URL = "http://147.135.212.197/crapi/had/viewstats"
CR_API_TOKEN = "RlNYRjRSQkNrTnBXeISLioBgdlNXlmVpVHGBQ2KKckaBcmJUglFs"
NUMBERS_FILE = "numbers.json"
DATA_FILE = "bot_data.json"

# ─── CR API Functions ─────────────────────────────────────────────

def fetch_all_recent_otps():
    """Fetch recent OTPs from CR API"""
    try:
        resp = requests.get(
            CR_API_URL,
            params={
                "token": CR_API_TOKEN,
                "records": 100,
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                return data.get("data", [])
            else:
                msg = data.get("msg", "Unknown")
                if "No Records" in msg:
                    return []
                logger.error(f"CR API error: {msg}")
        else:
            logger.error(f"CR API HTTP error: {resp.status_code}")
    except Exception as e:
        logger.error(f"CR API fetch error: {e}")
    return []

def fetch_otp_for_number(number: str):
    """Fetch OTP for specific number from CR API"""
    try:
        clean_num = number.lstrip("+").strip()
        now = datetime.utcnow()
        dt1 = (now - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        dt2 = now.strftime("%Y-%m-%d %H:%M:%S")
        resp = requests.get(
            CR_API_URL,
            params={
                "token": CR_API_TOKEN,
                "filternum": clean_num,
                "dt1": dt1,
                "dt2": dt2,
                "records": 10,
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                rows = data.get("data", [])
                if rows:
                    latest = rows[0]
                    return {
                        "datetime": latest.get("dt", ""),
                        "sender": latest.get("cli", "Unknown"),
                        "message": latest.get("message", ""),
                        "number": latest.get("num", clean_num),
                    }
    except Exception as e:
        logger.error(f"CR API fetch_otp error: {e}")
    return None

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
    """Background task to check for new OTPs via CR API"""
    global otp_cache
    
    rows = fetch_all_recent_otps()
    if not rows:
        logger.warning("⚠️ poll_otps: No rows returned from CR API")
        return
    
    all_pool_numbers = set()
    for s in SERVICES:
        for nums in numbers_pool[s].values():
            all_pool_numbers.update([n.lstrip("+").strip() for n in nums])
    
    logger.info(f"🔍 poll_otps: {len(rows)} rows | Pool: {len(all_pool_numbers)} numbers")
    
    for row in rows:
        try:
            number = str(row.get("num", "")).strip().lstrip("+")
            message = str(row.get("message", "")).strip()
            sender = str(row.get("cli", "Unknown"))
            dt_str = str(row.get("dt", ""))
            
            if not message or not number:
                continue
            
            if number not in all_pool_numbers:
                continue
            
            cache_key = f"{number}:{message[:30]}"
            if cache_key in otp_cache:
                continue
            otp_cache[cache_key] = True
            
            otp_code = extract_otp(message)
            flag = get_flag(number)
            
            logger.info(f"✅ OTP matched! Number: {number} | OTP: {otp_code}")
            
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
    global numbers_pool, session_cookie
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
        rows = fetch_all_recent_otps()
        status = f"✅ CR API OK! Got {len(rows)} records." if rows is not None else "❌ CR API failed!"
        await query.edit_message_text(
            status,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
        )

    elif data == "admin_upload":
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        # Show service selection buttons
        buttons = []
        for s in SERVICES:
            emoji = SERVICE_EMOJI[s]
            buttons.append([InlineKeyboardButton(f"{emoji} {s}", callback_data=f"upload_service_{s}")])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
        await query.edit_message_text(
            "📤 *Upload Numbers*\n\nStep 1: Select Service:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("upload_service_"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        service = data.replace("upload_service_", "")
        context.user_data["upload_service"] = service
        context.user_data["waiting_country"] = True
        await query.edit_message_text(
            f"📤 *Upload Numbers*\n\n"
            f"Service: *{SERVICE_EMOJI.get(service,'')} {service}*\n\n"
            f"Step 2: Send the *country code*\n\n"
            f"Example: `95` (Myanmar), `880` (Bangladesh), `91` (India)",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_upload")]])
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
    """Handle country code input or pasted numbers after service selection"""
    if update.effective_user.id != ADMIN_ID:
        return

    text = update.message.text.strip()

    # ── Step 2: waiting for country code ──
    if context.user_data.get("waiting_country"):
        country_code = text
        service = context.user_data.get("upload_service")
        if not service:
            return
        context.user_data["upload_country"] = country_code
        context.user_data["waiting_country"] = False
        context.user_data["waiting_file"] = True
        flag = COUNTRY_FLAGS.get(country_code, "🌍")
        await update.message.reply_text(
            f"✅ Service: *{SERVICE_EMOJI.get(service,'')} {service}*\n"
            f"✅ Country: {flag} `{country_code}`\n\n"
            f"Step 3: Now send the *.txt file* with numbers (one per line).",
            parse_mode="Markdown"
        )
        return

    # ── Fallback: pasted numbers (old /addnumbers flow) ──
    pending = context.user_data.get("pending_upload")
    if not pending:
        return
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
    """Handle .txt file — just numbers, service/country already selected"""
    if update.effective_user.id != ADMIN_ID:
        return

    doc = update.message.document
    if not doc or not doc.file_name.endswith(".txt"):
        return

    service = context.user_data.get("upload_service")
    country = context.user_data.get("upload_country")
    waiting_file = context.user_data.get("waiting_file")

    if not waiting_file or not service or not country:
        await update.message.reply_text(
            "❌ Please select service and country first.\n\n"
            "Go to *👑 Admin Panel → 📤 Upload Numbers*",
            parse_mode="Markdown"
        )
        return

    try:
        import io
        file = await context.bot.get_file(doc.file_id)
        buf = io.BytesIO()
        await file.download_to_memory(buf)
        buf.seek(0)
        text = buf.read().decode("utf-8", errors="ignore")
    except Exception as e:
        await update.message.reply_text(f"❌ File read error: {e}")
        return

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    numbers = [l if l.startswith("+") else f"+{l}" for l in lines if re.match(r'^\+?\d{7,15}$', l)]

    if not numbers:
        await update.message.reply_text("❌ No valid numbers found in file.\n\nMake sure each line has a number like `+959111222333`", parse_mode="Markdown")
        return

    if country not in numbers_pool[service]:
        numbers_pool[service][country] = []

    added = 0
    skipped = 0
    for n in numbers:
        if n not in numbers_pool[service][country]:
            numbers_pool[service][country].append(n)
            added += 1
        else:
            skipped += 1

    save_numbers()

    # Clear state
    context.user_data.pop("upload_service", None)
    context.user_data.pop("upload_country", None)
    context.user_data.pop("waiting_file", None)

    flag = COUNTRY_FLAGS.get(country, "🌍")
    await update.message.reply_text(
        f"✅ *Upload Complete!*\n\n"
        f"Service: *{SERVICE_EMOJI.get(service,'')} {service}*\n"
        f"Country: {flag} `{country}`\n"
        f"✅ Added: `{added}`\n"
        f"⏭ Skipped (duplicate): `{skipped}`\n"
        f"📱 Total now: `{len(numbers_pool[service][country])}`",
        parse_mode="Markdown"
    )

# ─── Main ─────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Starting bot...")
    load_numbers()
    load_data()
    logger.info("✅ CR API ready")
    
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
