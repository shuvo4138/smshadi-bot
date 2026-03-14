import logging
import re
import random
import requests
import os
import json
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ChatMember
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
JOIN_CHANNEL_USERNAME = os.getenv("JOIN_CHANNEL_USERNAME", "alwaysrvice24hours").strip()
JOIN_CHANNEL_LINK = f"https://t.me/{JOIN_CHANNEL_USERNAME}"
DEVELOPER_USERNAME = os.getenv("DEVELOPER_USERNAME", "Srbshuvo").strip()
MAIN_CHANNEL_LINK = "https://t.me/alwaysrvice24hours"

# CR API Configuration
CR_API_URL = "http://147.135.212.197/crapi/had/viewstats"
CR_API_TOKEN = os.getenv("CR_API_TOKEN", "SVJWSTRSQn6HYmlIa19oRmGQZYNjZWuKXlGHWoZOV3mGbmFVV3B5").strip()

NUMBERS_FILE = "numbers.json"
DATA_FILE = "bot_data.json"
USERS_FILE = "users.json"

otp_cache = {}

# ─── All Countries Data ────────────────────────────────────────────────────

COUNTRY_FLAGS = {
    "1": "🇺🇸", "7": "🇷🇺", "20": "🇪🇬", "27": "🇿🇦", "30": "🇬🇷", "31": "🇳🇱",
    "32": "🇧🇪", "33": "🇫🇷", "34": "🇪🇸", "36": "🇭🇺", "39": "🇮🇹", "40": "🇷🇴",
    "41": "🇨🇭", "43": "🇦🇹", "44": "🇬🇧", "45": "🇩🇰", "46": "🇸🇪", "47": "🇳🇴",
    "48": "🇵🇱", "49": "🇩🇪", "51": "🇵🇪", "52": "🇲🇽", "53": "🇨🇺", "54": "🇦🇷",
    "55": "🇧🇷", "56": "🇨🇱", "57": "🇨🇴", "58": "🇻🇪", "60": "🇲🇾", "61": "🇦🇺",
    "62": "🇮🇩", "63": "🇵🇭", "64": "🇳🇿", "65": "🇸🇬", "66": "🇹🇭", "81": "🇯🇵",
    "82": "🇰🇷", "84": "🇻🇳", "86": "🇨🇳", "90": "🇹🇷", "91": "🇮🇳", "92": "🇵🇰",
    "93": "🇦🇫", "94": "🇱🇰", "95": "🇲🇲", "98": "🇮🇷", "212": "🇲🇦", "213": "🇩🇿",
    "216": "🇹🇳", "218": "🇱🇾", "220": "🇬🇲", "221": "🇸🇳", "222": "🇲🇷", "223": "🇲🇱",
    "224": "🇬🇳", "225": "🇨🇮", "226": "🇧🇫", "227": "🇳🇪", "228": "🇹🇬", "229": "🇧🇯",
    "230": "🇲🇺", "231": "🇱🇷", "232": "🇸🇱", "233": "🇬🇭", "234": "🇳🇬", "235": "🇹🇩",
    "236": "🇨🇫", "237": "🇨🇲", "238": "🇨🇻", "239": "🇸🇹", "240": "🇬🇶", "241": "🇬🇦",
    "242": "🇨🇬", "243": "🇨🇩", "244": "🇦🇴", "245": "🇬🇼", "248": "🇸🇨", "249": "🇸🇩",
    "250": "🇷🇼", "251": "🇪🇹", "252": "🇸🇴", "253": "🇩🇯", "254": "🇰🇪", "255": "🇹🇿",
    "256": "🇺🇬", "257": "🇧🇮", "258": "🇲🇿", "260": "🇿🇲", "261": "🇲🇬", "263": "🇿🇼",
    "264": "🇳🇦", "265": "🇲🇼", "266": "🇱🇸", "267": "🇧🇼", "268": "🇸🇿", "269": "🇰🇲",
    "291": "🇪🇷", "297": "🇦🇼", "350": "🇬🇮", "351": "🇵🇹", "352": "🇱🇺", "353": "🇮🇪",
    "354": "🇮🇸", "355": "🇦🇱", "356": "🇲🇹", "357": "🇨🇾", "358": "🇫🇮", "359": "🇧🇬",
    "370": "🇱🇹", "371": "🇱🇻", "372": "🇪🇪", "373": "🇲🇩", "374": "🇦🇲", "375": "🇧🇾",
    "376": "🇦🇩", "377": "🇲🇨", "380": "🇺🇦", "381": "🇷🇸", "382": "🇲🇪", "385": "🇭🇷",
    "386": "🇸🇮", "387": "🇧🇦", "389": "🇲🇰", "420": "🇨🇿", "421": "🇸🇰", "501": "🇧🇿",
    "502": "🇬🇹", "503": "🇸🇻", "504": "🇭🇳", "505": "🇳🇮", "506": "🇨🇷", "507": "🇵🇦",
    "509": "🇭🇹", "591": "🇧🇴", "592": "🇬🇾", "593": "🇪🇨", "595": "🇵🇾", "597": "🇸🇷",
    "598": "🇺🇾", "670": "🇹🇱", "673": "🇧🇳", "675": "🇵🇬", "676": "🇹🇴", "677": "🇸🇧",
    "678": "🇻🇺", "679": "🇫🇯", "685": "🇼🇸", "686": "🇰🇮", "688": "🇹🇻", "850": "🇰🇵",
    "852": "🇭🇰", "853": "🇲🇴", "855": "🇰🇭", "856": "🇱🇦", "880": "🇧🇩", "886": "🇹🇼",
    "960": "🇲🇻", "961": "🇱🇧", "962": "🇯🇴", "963": "🇸🇾", "964": "🇮🇶", "965": "🇰🇼",
    "966": "🇸🇦", "967": "🇾🇪", "968": "🇴🇲", "970": "🇵🇸", "971": "🇦🇪", "972": "🇮🇱",
    "973": "🇧🇭", "974": "🇶🇦", "975": "🇧🇹", "976": "🇲🇳", "977": "🇳🇵", "992": "🇹🇯",
    "993": "🇹🇲", "994": "🇦🇿", "995": "🇬🇪", "996": "🇰🇬", "998": "🇺🇿",
}

COUNTRY_NAMES = {
    "1": "USA", "7": "Russia", "20": "Egypt", "27": "South Africa", "30": "Greece",
    "31": "Netherlands", "32": "Belgium", "33": "France", "34": "Spain", "36": "Hungary",
    "39": "Italy", "40": "Romania", "41": "Switzerland", "43": "Austria", "44": "UK",
    "45": "Denmark", "46": "Sweden", "47": "Norway", "48": "Poland", "49": "Germany",
    "51": "Peru", "52": "Mexico", "53": "Cuba", "54": "Argentina", "55": "Brazil",
    "56": "Chile", "57": "Colombia", "58": "Venezuela", "60": "Malaysia", "61": "Australia",
    "62": "Indonesia", "63": "Philippines", "64": "New Zealand", "65": "Singapore",
    "66": "Thailand", "81": "Japan", "82": "South Korea", "84": "Vietnam", "86": "China",
    "90": "Turkey", "91": "India", "92": "Pakistan", "93": "Afghanistan", "94": "Sri Lanka",
    "95": "Myanmar", "98": "Iran", "212": "Morocco", "213": "Algeria", "216": "Tunisia",
    "218": "Libya", "220": "Gambia", "221": "Senegal", "222": "Mauritania", "223": "Mali",
    "224": "Guinea", "225": "Ivory Coast", "226": "Burkina Faso", "227": "Niger",
    "228": "Togo", "229": "Benin", "230": "Mauritius", "231": "Liberia", "232": "Sierra Leone",
    "233": "Ghana", "234": "Nigeria", "235": "Chad", "236": "CAR", "237": "Cameroon",
    "238": "Cape Verde", "239": "Sao Tome", "240": "Eq. Guinea", "241": "Gabon",
    "242": "Congo", "243": "DR Congo", "244": "Angola", "245": "Guinea-Bissau",
    "248": "Seychelles", "249": "Sudan", "250": "Rwanda", "251": "Ethiopia", "252": "Somalia",
    "253": "Djibouti", "254": "Kenya", "255": "Tanzania", "256": "Uganda", "257": "Burundi",
    "258": "Mozambique", "260": "Zambia", "261": "Madagascar", "263": "Zimbabwe",
    "264": "Namibia", "265": "Malawi", "266": "Lesotho", "267": "Botswana", "268": "Eswatini",
    "269": "Comoros", "291": "Eritrea", "297": "Aruba", "350": "Gibraltar", "351": "Portugal",
    "352": "Luxembourg", "353": "Ireland", "354": "Iceland", "355": "Albania", "356": "Malta",
    "357": "Cyprus", "358": "Finland", "359": "Bulgaria", "370": "Lithuania", "371": "Latvia",
    "372": "Estonia", "373": "Moldova", "374": "Armenia", "375": "Belarus", "376": "Andorra",
    "377": "Monaco", "380": "Ukraine", "381": "Serbia", "382": "Montenegro", "385": "Croatia",
    "386": "Slovenia", "387": "Bosnia", "389": "N. Macedonia", "420": "Czech Republic",
    "421": "Slovakia", "501": "Belize", "502": "Guatemala", "503": "El Salvador",
    "504": "Honduras", "505": "Nicaragua", "506": "Costa Rica", "507": "Panama",
    "509": "Haiti", "591": "Bolivia", "592": "Guyana", "593": "Ecuador", "595": "Paraguay",
    "597": "Suriname", "598": "Uruguay", "670": "Timor-Leste", "673": "Brunei",
    "675": "Papua New Guinea", "676": "Tonga", "677": "Solomon Islands", "678": "Vanuatu",
    "679": "Fiji", "685": "Samoa", "686": "Kiribati", "688": "Tuvalu", "850": "North Korea",
    "852": "Hong Kong", "853": "Macau", "855": "Cambodia", "856": "Laos", "880": "Bangladesh",
    "886": "Taiwan", "960": "Maldives", "961": "Lebanon", "962": "Jordan", "963": "Syria",
    "964": "Iraq", "965": "Kuwait", "966": "Saudi Arabia", "967": "Yemen", "968": "Oman",
    "970": "Palestine", "971": "UAE", "972": "Israel", "973": "Bahrain", "974": "Qatar",
    "975": "Bhutan", "976": "Mongolia", "977": "Nepal", "992": "Tajikistan",
    "993": "Turkmenistan", "994": "Azerbaijan", "995": "Georgia", "996": "Kyrgyzstan",
    "998": "Uzbekistan",
}

# ─── CR API Functions ─────────────────────────────────────────────────────

def fetch_cr_api_otps():
    """Fetch OTPs from CR API"""
    try:
        now = datetime.now()
        dt2 = now.strftime("%Y-%m-%d %H:%M:%S")
        dt1 = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        
        params = {
            "token": CR_API_TOKEN,
            "dt1": dt1,
            "dt2": dt2,
            "records": 200
        }
        
        response = requests.get(CR_API_URL, params=params, timeout=15)
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        
        if data.get("status") != "success":
            return []
        
        rows = data.get("data", [])
        
        result = []
        for row in rows:
            try:
                otp_dict = {
                    "dt": str(row.get("dt", "")).strip(),
                    "num": str(row.get("num", "")).strip().lstrip("+"),
                    "cli": str(row.get("cli", "")).strip().upper(),
                    "message": str(row.get("message", "")).strip(),
                }
                if otp_dict["num"] and otp_dict["message"]:
                    result.append(otp_dict)
            except:
                continue
        
        return result
    
    except Exception as e:
        logger.error(f"CR API Error: {e}")
        return []

def extract_otp(message):
    """Extract OTP from message"""
    if not message:
        return None
    
    patterns = [
        r'\b(\d{4,8})\b',
        r'code[:\s]+(\d{4,8})',
        r'verification[:\s]+(\d{4,8})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def extract_country_code(number):
    """Extract country code from number"""
    for length in [3, 2, 1]:
        code = number[:length]
        if code in COUNTRY_NAMES:
            return code
    return "Unknown"

def hide_number(number):
    """Hide number - show only last 3 digits"""
    if len(number) <= 5:
        return number
    return number[:-5] + "★★" + number[-3:]

# ─── File Operations ─────────────────────────────────────────────────────

numbers_pool = {}
bot_data = {"last_number": {}, "total_users": 0, "verified_users": []}
users_db = {}

def load_numbers():
    global numbers_pool
    try:
        if os.path.exists(NUMBERS_FILE):
            with open(NUMBERS_FILE, 'r') as f:
                numbers_pool = json.load(f)
        else:
            numbers_pool = {}
            save_numbers()
    except Exception as e:
        logger.error(f"Error loading numbers: {e}")
        numbers_pool = {}

def save_numbers():
    try:
        with open(NUMBERS_FILE, 'w') as f:
            json.dump(numbers_pool, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving numbers: {e}")

def load_data():
    global bot_data
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                bot_data = json.load(f)
        else:
            bot_data = {"last_number": {}, "total_users": 0, "verified_users": []}
            save_data()
    except Exception as e:
        logger.error(f"Error loading data: {e}")

def save_data():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(bot_data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def load_users():
    global users_db
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                users_db = json.load(f)
        else:
            users_db = {}
            save_users()
    except Exception as e:
        logger.error(f"Error loading users: {e}")

def save_users():
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users_db, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving users: {e}")

def add_user(user_id, username):
    if str(user_id) not in users_db:
        users_db[str(user_id)] = {
            "username": username,
            "joined": datetime.now().isoformat()
        }
        bot_data["total_users"] = len(users_db)
        save_users()
        save_data()

# ─── Channel Join Verification ─────────────────────────────────────────────

async def check_channel_membership(context, user_id, channel_username):
    try:
        member = await context.bot.get_chat_member(f"@{channel_username}", user_id)
        if member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.CREATOR]:
            return True
        return False
    except:
        return False

# ─── Polling OTPs ─────────────────────────────────────────────────────────

async def poll_otps(context):
    """Poll CR API for new OTPs"""
    try:
        otps = fetch_cr_api_otps()
        
        if not otps:
            return
        
        for otp_data in otps:
            try:
                number = otp_data.get("num", "").strip()
                message = otp_data.get("message", "").strip()
                cli = otp_data.get("cli", "").strip().upper()
                dt = otp_data.get("dt", "").strip()
                
                otp_code = extract_otp(message)
                
                if not number or not otp_code or not dt:
                    continue
                
                cache_key = f"{number}:{otp_code}:{dt}"
                
                if cache_key in otp_cache:
                    continue
                
                otp_cache[cache_key] = True
                
                country = extract_country_code(number)
                hidden_number = hide_number(number)
                flag = COUNTRY_FLAGS.get(country, "🌍")
                
                msg = (
                    f"🆕 *NEW OTP - FACEBOOK*\n\n"
                    f"📱 Number : {flag}`+{hidden_number}`\n"
                    f"🔐 OTP Code : `{otp_code}`\n"
                    f"📝 Message : `{message[:100]}`\n"
                    f"⏰ Time : `{dt}`"
                )
                
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🤖 Number Bot", url="https://t.me/pc_clonev1_bot"),
                        InlineKeyboardButton("📢 Our Channel", url=MAIN_CHANNEL_LINK)
                    ]
                ])
                
                await context.bot.send_message(
                    chat_id=OTP_CHANNEL_ID,
                    text=msg,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                
            except Exception as e:
                logger.error(f"Error processing OTP: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Poll OTPs Error: {e}")

# ─── Telegram Handlers ─────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    add_user(user_id, user.username or user.first_name)
    
    buttons = [
        [KeyboardButton("📲 Get Number"), KeyboardButton("📋 Active Numbers")],
    ]
    
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("👑 Admin Panel")])
    
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)
    
    await update.message.reply_text(
        f"🤖 *Welcome to NUMBER PANEL NGN!*\n\n"
        f"👋 Welcome {user.first_name}!",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def reply_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "📲 Get Number":
        countries = list(numbers_pool.keys())
        
        if not countries:
            await update.message.reply_text("❌ No numbers available yet!")
            return
        
        buttons = []
        for country in sorted(countries):
            flag = COUNTRY_FLAGS.get(country, "🌍")
            name = COUNTRY_NAMES.get(country, country)
            buttons.append(InlineKeyboardButton(
                f"{flag} {name} Facebook",
                callback_data=f"getcountry:{country}"
            ))
        
        keyboard_buttons = [[btn] for btn in buttons]
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await update.message.reply_text(
            "🌍 *Select Country for Facebook:*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    elif text == "📋 Active Numbers":
        msg = "📱 *Your Active Numbers:*\n\n"
        
        user_key = str(user_id)
        if user_key in bot_data.get("last_number", {}):
            data = bot_data["last_number"][user_key]
            if isinstance(data, dict):
                number = data.get("number", "")
                country = data.get("country", "")
            else:
                number = data
                country = extract_country_code(number)
            
            flag = COUNTRY_FLAGS.get(country, "🌍")
            msg += f"📘 Facebook: `{number}` ({flag})"
        else:
            msg += "❌ No active numbers"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    elif text == "👑 Admin Panel":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ Admin only!")
            return
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
            [InlineKeyboardButton("➕ Add Numbers", callback_data="admin_addnumbers")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📈 Analytics", callback_data="admin_analytics")],
            [InlineKeyboardButton("🗑️ Delete Numbers", callback_data="admin_delete")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")],
        ])
        await update.message.reply_text(
            "👑 *Admin Panel*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    user_key = str(user_id)
    
    if data.startswith("getcountry:"):
        country = data.split(":")[1]
        numbers = numbers_pool.get(country, [])
        
        if not numbers:
            await query.answer("❌ No numbers available")
            return
        
        number = random.choice(numbers)
        bot_data["last_number"][user_key] = {
            "number": number,
            "country": country,
            "time": datetime.now().isoformat()
        }
        save_data()
        
        flag = COUNTRY_FLAGS.get(country, "🌍")
        name = COUNTRY_NAMES.get(country, country)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change Number", callback_data=f"change:{country}")],
            [InlineKeyboardButton("🌍 Change Country", callback_data="changecountry")],
            [InlineKeyboardButton("📱 OTP Group", url=OTP_CHANNEL_LINK)],
        ])
        
        await query.edit_message_text(
            f"✅ *Number Successfully Reserved!*\n\n"
            f"📘 Facebook | {flag} *{name}*\n"
            f"📱 Number: `{number}`\n\n"
            f"⏰ Valid for 10 minutes\n"
            f"⏳ Waiting for SMS...",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    elif data.startswith("change:"):
        country = data.split(":")[1]
        numbers = numbers_pool.get(country, [])
        
        if not numbers:
            await query.answer("❌ No numbers available")
            return
        
        if user_key in bot_data["last_number"]:
            old_data = bot_data["last_number"][user_key]
            if isinstance(old_data, dict):
                old_number = old_data.get("number")
            else:
                old_number = old_data
            
            if old_number and old_number in numbers_pool.get(country, []):
                numbers_pool[country].remove(old_number)
                save_numbers()
        
        number = random.choice(numbers)
        bot_data["last_number"][user_key] = {
            "number": number,
            "country": country,
            "time": datetime.now().isoformat()
        }
        save_data()
        
        flag = COUNTRY_FLAGS.get(country, "🌍")
        name = COUNTRY_NAMES.get(country, country)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change Number", callback_data=f"change:{country}")],
            [InlineKeyboardButton("🌍 Change Country", callback_data="changecountry")],
            [InlineKeyboardButton("📱 OTP Group", url=OTP_CHANNEL_LINK)],
        ])
        
        await query.edit_message_text(
            f"✅ *Number Changed!*\n\n"
            f"📘 Facebook | {flag} *{name}*\n"
            f"📱 New Number: `{number}`\n\n"
            f"⏰ Valid for 10 minutes\n"
            f"⏳ Waiting for SMS...",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    elif data == "changecountry":
        countries = list(numbers_pool.keys())
        
        if not countries:
            await query.answer("❌ No countries available")
            return
        
        buttons = []
        for country in sorted(countries):
            flag = COUNTRY_FLAGS.get(country, "🌍")
            name = COUNTRY_NAMES.get(country, country)
            buttons.append(InlineKeyboardButton(
                f"{flag} {name} Facebook",
                callback_data=f"getcountry:{country}"
            ))
        
        keyboard_buttons = [[btn] for btn in buttons]
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await query.edit_message_text(
            "🌍 *Select Country for Facebook:*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    elif data == "otpgroup":
        await query.answer()
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Change Number", callback_data=f"change:{query.message.text}")],
                [InlineKeyboardButton("🌍 Change Country", callback_data="changecountry")],
                [InlineKeyboardButton("📱 OTP Group", url=OTP_CHANNEL_LINK)],
            ])
        )
    
    elif data.startswith("admin_"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Admin only!")
            return
        
        action = data.split("_")[1]
        
        if action == "stats":
            total_numbers = sum(len(v) for v in numbers_pool.values())
            countries = len(numbers_pool)
            total_users = bot_data.get("total_users", 0)
            active_sessions = len(bot_data.get("last_number", {}).keys())
            
            await query.edit_message_text(
                f"📊 *Statistics*\n\n"
                f"👥 Total Users: `{total_users}`\n"
                f"📱 Total Numbers: `{total_numbers}`\n"
                f"🌍 Countries: `{countries}`\n"
                f"📡 Active Sessions: `{active_sessions}`",
                parse_mode="Markdown"
            )
        
        elif action == "addnumbers":
            await query.edit_message_text(
                "📝 *Send numbers.txt file*\n\n"
                "📌 Format: `country_code.txt`\n"
                "📌 Content: One number per line"
            )
        
        elif action == "broadcast":
            await query.edit_message_text(
                "📢 *Broadcast Feature*\n\n"
                "Reply with message to send to all users."
            )
        
        elif action == "analytics":
            await query.edit_message_text("📈 *Analytics*\n\nComing soon...")
        
        elif action == "delete":
            await query.edit_message_text("🗑️ *Delete Numbers*\n\nComing soon...")
        
        elif action == "settings":
            await query.edit_message_text("⚙️ *Settings*\n\nComing soon...")

async def handle_txt_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle TXT file upload"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    file = await update.message.document.get_file()
    content = await file.download_as_bytearray()
    text = content.decode('utf-8', errors='ignore')
    
    filename = update.message.document.file_name
    country_match = re.match(r'(\d+)', filename)
    
    if not country_match:
        await update.message.reply_text(
            "❌ *Invalid filename!*\n\nFormat: `country_code.txt`",
            parse_mode="Markdown"
        )
        return
    
    country = country_match.group(1)
    
    if country not in numbers_pool:
        numbers_pool[country] = []
    
    added = 0
    skipped = 0
    
    for line in text.split('\n'):
        number = line.strip()
        if not number or len(number) < 7:
            skipped += 1
            continue
        number = number.lstrip('+')
        if number not in numbers_pool[country]:
            numbers_pool[country].append(number)
            added += 1
        else:
            skipped += 1
    
    save_numbers()
    
    country_name = COUNTRY_NAMES.get(country, country)
    flag = COUNTRY_FLAGS.get(country, "🌍")
    
    await update.message.reply_text(
        f"✅ *Upload Complete!*\n\n"
        f"🌍 Country: {flag} `{country_name}`\n"
        f"✅ Added: `{added}` numbers\n"
        f"⏭ Skipped: `{skipped}`\n"
        f"📱 Total: `{len(numbers_pool[country])}`",
        parse_mode="Markdown"
    )

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Starting NUMBER PANEL NGN Bot...")
    load_numbers()
    load_data()
    load_users()
    
    global otp_cache
    otps = fetch_cr_api_otps()
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
    
    logger.info(f"✅ Preloaded {len(otp_cache)} OTPs")
    logger.info("✅ Bot Ready!")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), handle_txt_file))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'^(📲 Get Number|📋 Active Numbers|👑 Admin Panel)$'),
        reply_keyboard_handler
    ))
    
    app.job_queue.run_repeating(poll_otps, interval=5, first=2)
    
    logger.info("✅ NUMBER PANEL NGN running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
