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

# CR API Configuration (Main Source)
CR_API_URL = "http://147.135.212.197/crapi/had/viewstats"
CR_API_TOKEN = os.getenv("CR_API_TOKEN", "SVJWSTRSQn6HYmlIa19oRmGQZYNjZWuKXlGHWoZOV3mGbmFVV3B5").strip()

# Panel API (Fallback) - Optional
PANEL_API_URL = "http://185.2.83.39/ints/agent/res/data_smscdr.php"
PANEL_SESSKEY = os.getenv("PANEL_SESSKEY", "Q05RR0FRUERCVQ==").strip()
PANEL_PHPSESSID = os.getenv("PANEL_PHPSESSID", "mt8r47orubtc6obmod56hfnvfg").strip()

NUMBERS_FILE = "numbers.json"
DATA_FILE = "bot_data.json"

# Global cache for OTPs (to prevent duplicates)
otp_cache = {}

# ─── CR API Functions ─────────────────────────────────────────────────────

def fetch_cr_api_otps():
    """Fetch OTPs from CR API (Main Source)"""
    try:
        now = datetime.now()
        # গত 24 ঘণ্টার data fetch করবো
        dt2 = now.strftime("%Y-%m-%d %H:%M:%S")
        dt1 = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        
        params = {
            "token": CR_API_TOKEN,
            "dt1": dt1,
            "dt2": dt2,
            "records": 200
        }
        
        logger.info(f"📡 CR API: Fetching OTPs from {dt1} to {dt2}")
        
        response = requests.get(CR_API_URL, params=params, timeout=15)
        
        if response.status_code != 200:
            logger.error(f"CR API HTTP Error: {response.status_code}")
            return []
        
        data = response.json()
        
        if data.get("status") != "success":
            logger.warning(f"CR API Status Error: {data.get('msg', 'Unknown')}")
            return []
        
        rows = data.get("data", [])
        logger.info(f"✅ CR API: Found {len(rows)} OTP records")
        
        result = []
        for row in rows:
            try:
                otp_dict = {
                    "dt": str(row.get("dt", "")).strip(),
                    "num": str(row.get("num", "")).strip().lstrip("+"),
                    "cli": str(row.get("cli", "")).strip().upper(),
                    "message": str(row.get("message", "")).strip(),
                }
                
                # Validate
                if otp_dict["num"] and otp_dict["message"]:
                    result.append(otp_dict)
            except Exception as e:
                logger.warning(f"Error parsing OTP row: {e}")
                continue
        
        return result
    
    except Exception as e:
        logger.error(f"❌ CR API Error: {e}")
        return []

def fetch_panel_api_otps():
    """Fetch OTPs from Panel API (Fallback Only)"""
    try:
        now = datetime.now()
        dt1 = now.strftime("%Y-%m-%d 00:00:00")
        dt2 = now.strftime("%Y-%m-%d 23:59:59")
        
        params = {
            "fdate1": dt1, "fdate2": dt2, "frange": "", "fclient": "",
            "fnum": "", "fcli": "", "fgdate": "", "fgmonth": "",
            "fgrange": "", "fgclient": "", "fgnumber": "", "fgcli": "",
            "fg": "0", "sesskey": PANEL_SESSKEY, "sEcho": "1",
            "iColumns": "9", "sColumns": ",,,,,,,,",
            "iDisplayStart": "0", "iDisplayLength": "500",
            "mDataProp_0": "0", "sSearch_0": "", "bRegex_0": "false",
            "bSearchable_0": "true", "bSortable_0": "true",
            "mDataProp_1": "1", "sSearch_1": "", "bRegex_1": "false",
            "bSearchable_1": "true", "bSortable_1": "true",
            "mDataProp_2": "2", "sSearch_2": "", "bRegex_2": "false",
            "bSearchable_2": "true", "bSortable_2": "true",
            "mDataProp_3": "3", "sSearch_3": "", "bRegex_3": "false",
            "bSearchable_3": "true", "bSortable_3": "true",
            "mDataProp_4": "4", "sSearch_4": "", "bRegex_4": "false",
            "bSearchable_4": "true", "bSortable_4": "true",
            "mDataProp_5": "5", "sSearch_5": "", "bRegex_5": "false",
            "bSearchable_5": "true", "bSortable_5": "true",
            "mDataProp_6": "6", "sSearch_6": "", "bRegex_6": "false",
            "bSearchable_6": "true", "bSortable_6": "true",
            "mDataProp_7": "7", "sSearch_7": "", "bRegex_7": "false",
            "bSearchable_7": "true", "bSortable_7": "true",
            "mDataProp_8": "8", "sSearch_8": "", "bRegex_8": "false",
            "bSearchable_8": "true", "bSortable_8": "false",
            "sSearch": "", "bRegex": "false", "iSortCol_0": "0",
            "sSortDir_0": "desc", "iSortingCols": "1",
        }
        
        response = requests.get(
            PANEL_API_URL,
            params=params,
            timeout=10,
            cookies={"PHPSESSID": PANEL_PHPSESSID}
        )
        
        if response.status_code != 200:
            logger.warning(f"Panel API HTTP: {response.status_code}")
            return []
        
        data = response.json()
        rows = data.get("aaData", [])
        logger.info(f"📡 Panel API (Fallback): {len(rows)} rows")
        
        result = []
        for row in rows:
            if len(row) >= 6:
                result.append({
                    "dt": str(row[0]).strip() if row[0] else "",
                    "num": str(row[2]).strip().lstrip("+") if row[2] else "",
                    "cli": str(row[3]).strip().upper() if row[3] else "Unknown",
                    "message": str(row[5]).strip() if row[5] else "",
                })
        return result
    except Exception as e:
        logger.warning(f"Panel API Error (Fallback): {e}")
        return []

def fetch_all_otps():
    """
    Fetch OTPs: CR API (Primary) → Panel API (Fallback)
    """
    # প্রথমে CR API থেকে try করবো (Main Source)
    otps = fetch_cr_api_otps()
    
    # যদি CR API fail হয় বা empty হয়
    if not otps or len(otps) == 0:
        logger.warning("⚠️ CR API empty, trying Panel API fallback...")
        otps = fetch_panel_api_otps()
    
    return otps

def extract_otp(message):
    """Extract OTP from message"""
    if not message:
        return None
    
    # Different OTP patterns
    patterns = [
        r'\b(\d{4,8})\b',  # 4-8 digit code
        r'code[:\s]+(\d{4,8})',  # "code: 1234"
        r'verification[:\s]+(\d{4,8})',  # "verification: 1234"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

# ─── Services configuration ─────────────────────────────────────────────────

SERVICES = ["Facebook", "WhatsApp", "TikTok", "Instagram", "Telegram"]
SERVICE_EMOJI = {
    "Facebook": "📘", "WhatsApp": "💬", "TikTok": "🎵",
    "Instagram": "📸", "Telegram": "✈️",
}

COUNTRY_FLAGS = {
    "1": "🇺🇸", "7": "🇷🇺", "20": "🇪🇬", "27": "🇿🇦", "30": "🇬🇷", "31": "🇳🇱", "32": "🇧🇪", "33": "🇫🇷", "34": "🇪🇸", "36": "🇭🇺",
    "39": "🇮🇹", "40": "🇷🇴", "41": "🇨🇭", "43": "🇦🇹", "44": "🇬🇧", "45": "🇩🇰", "46": "🇸🇪", "47": "🇳🇴", "48": "🇵🇱", "49": "🇩🇪",
    "51": "🇵🇪", "52": "🇲🇽", "53": "🇨🇺", "54": "🇦🇷", "55": "🇧🇷", "56": "🇨🇱", "57": "🇨🇴", "58": "🇻🇪", "60": "🇲🇾", "61": "🇦🇺",
    "62": "🇮🇩", "63": "🇵🇭", "64": "🇳🇿", "65": "🇸🇬", "66": "🇹🇭", "81": "🇯🇵", "82": "🇰🇷", "84": "🇻🇳", "86": "🇨🇳", "90": "🇹🇷",
    "91": "🇮🇳", "92": "🇵🇰", "93": "🇦🇫", "94": "🇱🇰", "95": "🇲🇲", "98": "🇮🇷", "212": "🇲🇦", "213": "🇩🇿", "216": "🇹🇳", "220": "🇸🇳",
}

COUNTRY_NAMES = {
    "1": "USA", "7": "Russia", "20": "Egypt", "27": "South Africa", "30": "Greece", "31": "Netherlands",
    "91": "India", "92": "Pakistan", "212": "Morocco", "213": "Algeria",
}

# ─── File Storage ─────────────────────────────────────────────────────────

numbers_pool = {}
bot_data = {"last_number": {}}

def load_numbers():
    """Load numbers from JSON file"""
    global numbers_pool
    try:
        if os.path.exists(NUMBERS_FILE):
            with open(NUMBERS_FILE, 'r') as f:
                numbers_pool = json.load(f)
        else:
            # Initialize structure
            numbers_pool = {service: {} for service in SERVICES}
            save_numbers()
    except Exception as e:
        logger.error(f"Error loading numbers: {e}")
        numbers_pool = {service: {} for service in SERVICES}

def save_numbers():
    """Save numbers to JSON file"""
    try:
        with open(NUMBERS_FILE, 'w') as f:
            json.dump(numbers_pool, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving numbers: {e}")

def load_data():
    """Load bot data"""
    global bot_data
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                bot_data = json.load(f)
        else:
            bot_data = {"last_number": {}}
            save_data()
    except Exception as e:
        logger.error(f"Error loading data: {e}")

def save_data():
    """Save bot data"""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(bot_data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

# ─── Polling OTPs ─────────────────────────────────────────────────────────

async def poll_otps(context):
    """Poll CR API for new OTPs and send to channel"""
    try:
        otps = fetch_all_otps()
        
        if not otps:
            return
        
        # Process each OTP
        for otp_data in otps:
            try:
                number = otp_data.get("num", "").strip()
                message = otp_data.get("message", "").strip()
                cli = otp_data.get("cli", "").strip().upper()
                dt = otp_data.get("dt", "").strip()
                
                # Extract OTP code
                otp_code = extract_otp(message)
                
                if not number or not otp_code or not dt:
                    continue
                
                # Create unique key
                cache_key = f"{number}:{otp_code}:{dt}"
                
                # Check if already sent
                if cache_key in otp_cache:
                    continue
                
                # Mark as sent
                otp_cache[cache_key] = True
                
                # Determine country code
                country_code = re.match(r'^(\d+)', number)
                country = country_code.group(1) if country_code else "Unknown"
                
                flag = COUNTRY_FLAGS.get(country, "🌍")
                country_name = COUNTRY_NAMES.get(country, country)
                
                # Format message for Telegram
                msg = (
                    f"🆕 *NEW OTP*\n\n"
                    f"📱 Number: `{number}`\n"
                    f"🌍 Country: {flag} `{country_name}`\n"
                    f"🔧 Service: `{cli}`\n"
                    f"🔐 OTP Code: `{otp_code}`\n"
                    f"📝 Message: `{message[:100]}...`\n"
                    f"⏰ Time: `{dt}`"
                )
                
                # Send to channel
                await context.bot.send_message(
                    chat_id=OTP_CHANNEL_ID,
                    text=msg,
                    parse_mode="Markdown"
                )
                
                logger.info(f"✅ OTP sent: {number} - {otp_code}")
            
            except Exception as e:
                logger.error(f"Error processing OTP: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Poll OTPs Error: {e}")

# ─── Telegram Handlers ─────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user = update.effective_user
    
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📲 Get Number"), KeyboardButton("📋 Active Numbers")],
         [KeyboardButton("👑 Admin Panel")]],
        resize_keyboard=True
    )
    
    await update.message.reply_text(
        f"🤖 *Welcome {user.first_name}!*\n\n"
        f"আমি একটি OTP Number Provider Bot\n\n"
        f"আপনি এখানে Facebook, WhatsApp, Instagram ইত্যাদির জন্য real OTP নম্বর পাবেন।",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def reply_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reply keyboard buttons"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "📲 Get Number":
        # Show service selection
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{SERVICE_EMOJI.get(s, '')} {s}", callback_data=f"service:{s}")]
            for s in SERVICES
        ])
        await update.message.reply_text(
            "🔧 *Select Service:*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    elif text == "📋 Active Numbers":
        # Show active numbers
        msg = "📱 *Your Active Numbers:*\n\n"
        
        user_key = str(user_id)
        for service in SERVICES:
            if service in bot_data.get("last_number", {}) and user_key in bot_data["last_number"][service]:
                number = bot_data["last_number"][service][user_key]
                msg += f"{SERVICE_EMOJI.get(service, '')} {service}: `{number}`\n"
        
        if msg == "📱 *Your Active Numbers:*\n\n":
            msg += "❌ No active numbers"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    elif text == "👑 Admin Panel":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ Admin only!")
            return
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Numbers", callback_data="admin:addnumbers")],
            [InlineKeyboardButton("📊 Stats", callback_data="admin:stats")],
            [InlineKeyboardButton("🔑 Set Session", callback_data="admin:setsession")],
        ])
        await update.message.reply_text(
            "👑 *Admin Panel*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline buttons"""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    
    if data.startswith("service:"):
        service = data.split(":")[1]
        
        # Show country selection
        countries = list(set(
            [c for s in numbers_pool.get(service, {}) for c in numbers_pool[service].keys()]
        ))
        
        if not countries:
            await query.answer("❌ No numbers available for this service")
            return
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{COUNTRY_FLAGS.get(c, '🌍')} {COUNTRY_NAMES.get(c, c)}", callback_data=f"country:{service}:{c}")]
            for c in sorted(countries)[:8]
        ])
        
        await query.edit_message_text(
            f"🌍 *Select Country for {service}:*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    elif data.startswith("country:"):
        parts = data.split(":")
        service = parts[1]
        country = parts[2]
        
        numbers = numbers_pool.get(service, {}).get(country, [])
        
        if not numbers:
            await query.answer("❌ No numbers available")
            return
        
        # Get random number
        number = random.choice(numbers)
        
        # Save last number
        if service not in bot_data["last_number"]:
            bot_data["last_number"][service] = {}
        bot_data["last_number"][service][str(user_id)] = number
        save_data()
        
        flag = COUNTRY_FLAGS.get(country, "🌍")
        await query.edit_message_text(
            f"{SERVICE_EMOJI.get(service, '')} *{service}* | {flag} *{COUNTRY_NAMES.get(country, country)}*\n\n"
            f"📱 Number: `{number}`\n\n"
            f"⏰ Valid for 10 minutes\n"
            f"🔗 Join channel: {OTP_CHANNEL_LINK}",
            parse_mode="Markdown"
        )
    
    elif data.startswith("admin:"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Admin only!")
            return
        
        action = data.split(":")[1]
        
        if action == "addnumbers":
            await query.edit_message_text(
                "📝 *Send numbers.txt file*\n\n"
                "Format: service,country,number (one per line)\n"
                "Example: Facebook,91,9876543210"
            )
        
        elif action == "stats":
            total_numbers = sum(
                len(numbers_pool[s].get(c, []))
                for s in numbers_pool
                for c in numbers_pool[s]
            )
            await query.edit_message_text(
                f"📊 *Bot Statistics*\n\n"
                f"📱 Total Numbers: `{total_numbers}`\n"
                f"🔧 Services: `{len(SERVICES)}`"
            )

async def handle_txt_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle TXT file upload"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    file = await update.message.document.get_file()
    content = await file.download_as_bytearray()
    text = content.decode('utf-8')
    
    added = 0
    skipped = 0
    
    for line in text.split('\n'):
        if not line.strip():
            continue
        
        parts = line.strip().split(',')
        if len(parts) < 3:
            skipped += 1
            continue
        
        service = parts[0].strip()
        country = parts[1].strip()
        number = parts[2].strip()
        
        if service not in SERVICES or not number:
            skipped += 1
            continue
        
        if service not in numbers_pool:
            numbers_pool[service] = {}
        if country not in numbers_pool[service]:
            numbers_pool[service][country] = []
        
        if number not in numbers_pool[service][country]:
            numbers_pool[service][country].append(number)
            added += 1
        else:
            skipped += 1
    
    save_numbers()
    
    await update.message.reply_text(
        f"✅ *Upload Complete!*\n\n"
        f"✅ Added: `{added}`\n"
        f"⏭ Skipped: `{skipped}`",
        parse_mode="Markdown"
    )

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Starting Telegram OTP Bot with CR API...")
    load_numbers()
    load_data()
    
    # Preload cache
    global otp_cache
    otps = fetch_all_otps()
    for otp_data in otps:
        try:
            number = otp_data.get("num", "").strip()
            message = otp_data.get("message", "").strip()
            dt = otp_data.get("dt", "").strip()
            otp_code = extract_otp(message)
            if number and otp_code and dt:
                otp_cache[f"{number}:{otp_code}:{dt}"] = True
        except:
            pass
    
    logger.info(f"✅ Preloaded {len(otp_cache)} OTPs into cache")
    logger.info("✅ CR API Ready!")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), handle_txt_file))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'^(📲 Get Number|📋 Active Numbers|👑 Admin Panel)$'),
        reply_keyboard_handler
    ))
    
    # Polling job
    app.job_queue.run_repeating(poll_otps, interval=5, first=2)
    
    logger.info("✅ Bot running! Polling OTPs every 5 seconds...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
