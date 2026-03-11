# Full OTP Panel Bot with CR API and Stats
# Complete implementation

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

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "1984916365").strip())
OTP_CHANNEL_ID = int(os.getenv("OTP_CHANNEL_ID", "-1002625886518").strip())
OTP_CHANNEL_LINK = os.getenv("OTP_CHANNEL_LINK", "https://t.me/+SWraCXOQrWM4Mzg9").strip()
JOIN_CHANNEL = os.getenv("JOIN_CHANNEL", "https://t.me/alwaysrvice24hours").strip()

CR_API_TOKEN = os.getenv("CR_API_TOKEN", "RlNYRjRSQkNrTnBXeISLioBgdlNXlmVpVHGBQ2KKckaBcmJUglFs").strip()
CR_API_URL = "http://147.135.212.197/crapi/had/viewstats"

NUMBERS_FILE = "numbers.json"
DATA_FILE = "bot_data.json"
STATS_FILE = "bot_stats.json"

# Services
SERVICES = ["Facebook", "WhatsApp", "TikTok", "Instagram", "Telegram"]
SERVICE_EMOJI = {
    "Facebook": "📘", "WhatsApp": "💬", "TikTok": "🎵",
    "Instagram": "📸", "Telegram": "✈️",
}

COUNTRY_FLAGS = {
    "1": "🇺🇸", "7": "🇷🇺", "91": "🇮🇳", "92": "🇵🇰", "95": "🇲🇲",
    "212": "🇲🇦", "234": "🇳🇬", "387": "🇧🇦", "39": "🇮🇹", "44": "🇬🇧",
}

COUNTRY_NAMES = {
    "1": "USA", "7": "Russia", "91": "India", "92": "Pakistan", "95": "Myanmar",
    "212": "Morocco", "234": "Nigeria", "387": "Bosnia", "39": "Italy", "44": "UK",
}

# Global state
numbers_pool = {s: {} for s in SERVICES}
user_numbers = {}
otp_cache = {}
banned_users = set()
all_users = set()

# Stats
stats = {
    "total_otps_processed": 0,
    "total_otps_delivered": 0,
    "total_users": 0,
    "active_assignments": 0,
    "last_otp_time": None,
}

if not BOT_TOKEN:
    logger.error("BOT_TOKEN is not set!")
    exit(1)

# ─── Helper Functions ───

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

def save_numbers():
    try:
        with open(NUMBERS_FILE, "w") as f:
            json.dump(numbers_pool, f)
    except Exception as e:
        logger.error(f"Save numbers error: {e}")

def load_numbers():
    global numbers_pool
    try:
        if os.path.exists(NUMBERS_FILE):
            with open(NUMBERS_FILE, "r") as f:
                data = json.load(f)
            for s in SERVICES:
                numbers_pool[s] = data.get(s, {})
            logger.info(f"📂 Loaded numbers pool")
    except Exception as e:
        logger.error(f"Load numbers error: {e}")

def save_stats():
    try:
        with open(STATS_FILE, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logger.error(f"Save stats error: {e}")

def load_stats():
    global stats
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, "r") as f:
                stats = json.load(f)
            logger.info(f"📊 Stats loaded")
    except Exception as e:
        logger.error(f"Load stats error: {e}")

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
        logger.error(f"Save data error: {e}")

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
        logger.error(f"Load data error: {e}")

# ─── CR API Fetch ───

def fetch_all_recent_otps():
    """Fetch OTPs from CR API"""
    try:
        now = datetime.now()
        dt1 = now.strftime("%Y-%m-%d 00:00:00")
        dt2 = now.strftime("%Y-%m-%d 23:59:59")
        
        resp = requests.get(
            CR_API_URL,
            params={
                "token": CR_API_TOKEN,
                "dt1": dt1,
                "dt2": dt2,
                "records": 1000,
            },
            timeout=10
        )
        
        if resp.status_code != 200:
            logger.error(f"CR API HTTP: {resp.status_code}")
            return []
        
        data = resp.json()
        if data.get("status") != "success":
            logger.error(f"CR API error: {data.get('msg', 'Unknown')}")
            return []
        
        rows = data.get("data", [])
        logger.info(f"📡 CR API: {len(rows)} rows | Status: {data.get('total', 0)} total")
        
        result = []
        for row in rows:
            result.append({
                "dt": str(row.get("dt", "")).strip(),
                "num": str(row.get("num", "")).strip().lstrip("+"),
                "cli": str(row.get("cli", "")).strip().upper(),
                "message": str(row.get("message", "")).strip(),
            })
        return result
    except Exception as e:
        logger.error(f"CR API fetch error: {e}")
        return []

# ─── OTP Polling ───

async def poll_otps(context):
    """Poll CR API and deliver OTPs"""
    global otp_cache, stats
    
    rows = fetch_all_recent_otps()
    if not rows:
        return

    all_numbers = set()
    for row in rows:
        num = str(row.get("num", "")).strip().lstrip("+")
        if num:
            all_numbers.add(num)

    if not all_numbers:
        logger.warning("⚠️ No numbers from CR API")
        return

    logger.info(f"📱 Available: {len(all_numbers)} unique numbers")

    assigned = {}
    for uid, info in user_numbers.items():
        n = str(info.get("number", "")).lstrip("+").strip()
        if n:
            assigned[n] = uid

    new_count = 0

    for row in rows:
        try:
            dt = str(row.get("dt", "")).strip()
            number = str(row.get("num", "")).strip().lstrip("+")
            cli = str(row.get("cli", "Unknown")).strip().upper()
            message = str(row.get("message", "")).strip()

            if not number or not message:
                continue

            if number not in all_numbers:
                continue

            otp_code = extract_otp(message)
            if not otp_code:
                continue

            cache_key = f"{number}:{otp_code}:{dt}"
            if cache_key in otp_cache:
                continue
            otp_cache[cache_key] = True

            if len(otp_cache) > 1000:
                for k in list(otp_cache.keys())[:300]:
                    del otp_cache[k]

            flag = get_flag(number)
            country_name = "Unknown"
            for code, name in COUNTRY_NAMES.items():
                if number.startswith(code):
                    country_name = name
                    break

            logger.info(f"🔔 NEW OTP! +{number} | {otp_code} | {cli}")
            new_count += 1
            stats["total_otps_processed"] += 1

            masked_num = mask_number(number)
            channel_msg = (
                f"🔔 *New OTP*\n\n"
                f"📱 App: {cli}\n"
                f"🌎 Country: {country_name} {flag}\n"
                f"📞 Number: `{masked_num}`\n"
                f"🔑 OTP: `{otp_code}`\n"
                f"🕐 {dt}"
            )
            try:
                await context.bot.send_message(
                    chat_id=OTP_CHANNEL_ID,
                    text=channel_msg,
                    parse_mode="Markdown"
                )
                logger.info("✅ Channel notified")
            except Exception as e:
                logger.error(f"❌ Channel error: {e}")

            await asyncio.sleep(0.2)

            owner_id = assigned.get(number)
            if owner_id:
                inbox_msg = (
                    f"🔔 *New OTP*\n\n"
                    f"📱 App: {cli}\n"
                    f"🌎 Country: {country_name} {flag}\n"
                    f"📞 Number: `+{number}`\n"
                    f"🔑 OTP: `{otp_code}`"
                )
                try:
                    await context.bot.send_message(
                        chat_id=owner_id,
                        text=inbox_msg,
                        parse_mode="Markdown"
                    )
                    logger.info(f"✅ User {owner_id} notified")
                    stats["total_otps_delivered"] += 1
                except Exception as e:
                    logger.error(f"❌ User {owner_id} error: {e}")

        except Exception as e:
            logger.error(f"❌ Poll error: {e}")

    if new_count > 0:
        logger.info(f"✅ Processed {new_count} OTPs ⚡")
        stats["last_otp_time"] = datetime.now().isoformat()
        save_stats()

# ─── Bot Handlers ───

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    stats["total_users"] = len(all_users)
    save_data()
    save_stats()
    
    if user.id == ADMIN_ID:
        await update.message.reply_text(
            f"👋 Welcome *Admin*!\n\n🤖 *OTP PANEL BOT*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_back")],
                [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
            ])
        )
    else:
        await update.message.reply_text(
            f"👋 Welcome *{user.first_name}*!\n\n🤖 *OTP PANEL BOT*\n\nPress /start to continue",
            parse_mode="Markdown"
        )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin stats"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Access denied")
        return
    
    total_numbers = sum(
        len(nums)
        for s in SERVICES
        for nums in numbers_pool[s].values()
    )
    
    stats_msg = (
        f"📊 *BOT STATISTICS*\n\n"
        f"👥 Total Users: `{stats.get('total_users', 0)}`\n"
        f"📱 Total Numbers: `{total_numbers}`\n"
        f"🔔 Active Assignments: `{len(user_numbers)}`\n"
        f"✅ OTPs Processed: `{stats.get('total_otps_processed', 0)}`\n"
        f"📨 OTPs Delivered: `{stats.get('total_otps_delivered', 0)}`\n"
        f"🕐 Last OTP: `{stats.get('last_otp_time', 'None')}`"
    )
    
    await query.edit_message_text(stats_msg, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_back":
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ Access denied")
            return
        
        total_numbers = sum(
            len(nums)
            for s in SERVICES
            for nums in numbers_pool[s].values()
        )
        
        await query.edit_message_text(
            f"👑 *Admin Panel*\n\n"
            f"📱 Total Numbers: `{total_numbers}`\n"
            f"👥 Active Users: `{len(user_numbers)}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
                [InlineKeyboardButton("📤 Upload Numbers", callback_data="admin_upload")],
            ])
        )
    
    elif query.data == "admin_stats":
        await admin_stats(update, context)

async def main():
    logger.info("🚀 Starting OTP Panel Bot...")
    load_numbers()
    load_data()
    load_stats()
    
    logger.info("✅ CR API Ready")
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Poll CR API every 3 seconds
    app.job_queue.run_repeating(poll_otps, interval=3, first=1)
    
    logger.info("✅ Bot running!")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
