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

# CR API Configuration
CR_API_URL = "http://147.135.212.197/crapi/had/viewstats"
CR_API_TOKEN = os.getenv("CR_API_TOKEN", "SVJWSTRSQn6HYmlIa19oRmGQZYNjZWuKXlGHWoZOV3mGbmFVV3B5").strip()

NUMBERS_FILE = "numbers.json"
DATA_FILE = "bot_data.json"
USERS_FILE = "users.json"

otp_cache = {}

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
    country_codes = {
        "1": "USA", "7": "Russia", "20": "Egypt", "27": "South Africa",
        "30": "Greece", "31": "Netherlands", "32": "Belgium", "33": "France",
        "34": "Spain", "36": "Hungary", "39": "Italy", "40": "Romania",
        "41": "Switzerland", "43": "Austria", "44": "UK", "45": "Denmark",
        "46": "Sweden", "47": "Norway", "48": "Poland", "49": "Germany",
        "51": "Peru", "52": "Mexico", "53": "Cuba", "54": "Argentina",
        "55": "Brazil", "56": "Chile", "57": "Colombia", "58": "Venezuela",
        "60": "Malaysia", "61": "Australia", "62": "Indonesia", "63": "Philippines",
        "64": "New Zealand", "65": "Singapore", "66": "Thailand", "81": "Japan",
        "82": "South Korea", "84": "Vietnam", "86": "China", "90": "Turkey",
        "91": "India", "92": "Pakistan", "93": "Afghanistan", "94": "Sri Lanka",
        "95": "Myanmar", "98": "Iran", "212": "Morocco", "213": "Algeria",
        "216": "Tunisia", "220": "Senegal", "222": "Mauritania", "223": "Mali",
        "224": "Guinea", "225": "Ivory Coast", "226": "Burkina Faso", "227": "Niger",
        "228": "Togo", "229": "Benin", "230": "Mauritius", "231": "Liberia",
        "232": "Sierra Leone", "233": "Ghana", "234": "Nigeria", "235": "Chad",
    }
    
    for length in [3, 2, 1]:
        code = number[:length]
        if code in country_codes:
            return code
    
    return "Unknown"

def hide_number(number):
    """Hide number - show only first and last digits"""
    if len(number) <= 4:
        return number
    return number[:-4] + "★★" + number[-2:]

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
    """Check if user is member of channel"""
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
                
                country_flags = {
                    "1": "🇺🇸", "7": "🇷🇺", "20": "🇪🇬", "27": "🇿🇦",
                    "91": "🇮🇳", "92": "🇵🇰", "95": "🇲🇲", "212": "🇲🇦",
                }
                
                country_names = {
                    "1": "USA", "7": "Russia", "91": "India", "92": "Pakistan",
                    "95": "Myanmar", "212": "Morocco",
                }
                
                flag = country_flags.get(country, "🌍")
                country_name = country_names.get(country, country)
                
                msg = (
                    f"🆕 *NEW OTP - FACEBOOK*\n\n"
                    f"📱 Number: `{hidden_number}`\n"
                    f"🌍 Country: {flag} `{country_name}`\n"
                    f"🔐 OTP Code: `{otp_code}`\n"
                    f"📝 Message: `{message[:80]}...`\n"
                    f"⏰ Time: `{dt}`\n\n"
                    f"───────────────────\n"
                    f"🤖 *NUMBER PANEL NGN*\n"
                    f"👨‍💻 Developer: @{DEVELOPER_USERNAME}"
                )
                
                await context.bot.send_message(
                    chat_id=OTP_CHANNEL_ID,
                    text=msg,
                    parse_mode="Markdown"
                )
                
            except Exception as e:
                logger.error(f"Error processing OTP: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Poll OTPs Error: {e}")

# ─── Telegram Handlers ─────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user = update.effective_user
    user_id = user.id
    
    # Check if user is verified
    if str(user_id) not in bot_data.get("verified_users", []):
        # Not verified - show join channel message
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Join Channel", url=JOIN_CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Verify", callback_data="verify_channel")],
        ])
        
        await update.message.reply_text(
            f"🔐 *Channel Verification Required*\n\n"
            f"আপনাকে bot use করার জন্য আমাদের channel এ join করতে হবে।\n\n"
            f"👇 নিচের button গুলো follow করুন:\n\n"
            f"1️⃣ 🔗 Join Channel button click করুন\n"
            f"2️⃣ Channel এ join করুন\n"
            f"3️⃣ ✅ Verify button click করুন",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        # Verified - show main menu
        add_user(user_id, user.username or user.first_name)
        
        buttons = [[KeyboardButton("📲 Get Number"), KeyboardButton("📋 Active Numbers")]]
        
        if user_id == ADMIN_ID:
            buttons.append([KeyboardButton("👑 Admin Panel")])
        
        keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        
        await update.message.reply_text(
            f"🤖 *Welcome to NUMBER PANEL NGN!*\n\n"
            f"👋 Welcome {user.first_name}!",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

async def reply_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reply keyboard buttons"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "📲 Get Number":
        countries = list(numbers_pool.keys())
        
        if not countries:
            await update.message.reply_text("❌ No numbers available yet!")
            return
        
        country_flags = {
            "1": "🇺🇸", "7": "🇷🇺", "91": "🇮🇳", "92": "🇵🇰",
            "95": "🇲🇲", "212": "🇲🇦", "213": "🇩🇿",
        }
        
        country_names = {
            "1": "USA", "7": "Russia", "91": "India", "92": "Pakistan",
            "95": "Myanmar", "212": "Morocco", "213": "Algeria",
        }
        
        buttons = []
        for country in sorted(countries):
            flag = country_flags.get(country, "🌍")
            name = country_names.get(country, country)
            buttons.append(InlineKeyboardButton(
                f"{flag} {name}",
                callback_data=f"getcountry:{country}"
            ))
        
        keyboard_buttons = [[buttons[i], buttons[i+1]] if i+1 < len(buttons) else [buttons[i]] 
                           for i in range(0, len(buttons), 2)]
        
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
            
            country_flags = {"1": "🇺🇸", "91": "🇮🇳", "92": "🇵🇰", "95": "🇲🇲"}
            flag = country_flags.get(country, "🌍")
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
    """Handle inline buttons"""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    user_key = str(user_id)
    
    if data == "verify_channel":
        # Check if user joined channel
        is_member = await check_channel_membership(context, user_id, JOIN_CHANNEL_USERNAME)
        
        if is_member:
            # Add to verified users
            if str(user_id) not in bot_data.get("verified_users", []):
                bot_data["verified_users"].append(str(user_id))
                save_data()
            
            # Show main menu
            buttons = [[KeyboardButton("📲 Get Number"), KeyboardButton("📋 Active Numbers")]]
            
            if user_id == ADMIN_ID:
                buttons.append([KeyboardButton("👑 Admin Panel")])
            
            keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
            
            await query.edit_message_text(
                f"✅ *Verification Successful!*\n\n"
                f"🤖 Welcome to NUMBER PANEL NGN!\n\n"
                f"👋 Welcome {update.effective_user.first_name}!",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
            add_user(user_id, update.effective_user.username or update.effective_user.first_name)
        else:
            # Not joined yet
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Join Channel", url=JOIN_CHANNEL_LINK)],
                [InlineKeyboardButton("✅ Verify Again", callback_data="verify_channel")],
            ])
            
            await query.edit_message_text(
                f"❌ *Channel Join করা হয়নি*\n\n"
                f"আপনি এখনও channel এ join করেননি।\n\n"
                f"👇 আগে channel এ join করুন, তারপর verify করুন।",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
    
    elif data.startswith("getcountry:"):
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
        
        country_flags = {
            "1": "🇺🇸", "91": "🇮🇳", "92": "🇵🇰", "95": "🇲🇲"
        }
        country_names = {
            "1": "USA", "91": "India", "92": "Pakistan", "95": "Myanmar"
        }
        
        flag = country_flags.get(country, "🌍")
        name = country_names.get(country, country)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change Number", callback_data=f"change:{country}")],
            [InlineKeyboardButton("🌍 Change Country", callback_data="changecountry")],
            [InlineKeyboardButton("📱 OTP Group", callback_data="otpgroup")],
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
        
        # Remove old number
        if user_key in bot_data["last_number"]:
            old_data = bot_data["last_number"][user_key]
            if isinstance(old_data, dict):
                old_number = old_data.get("number")
            else:
                old_number = old_data
            
            if old_number and old_number in numbers_pool.get(country, []):
                numbers_pool[country].remove(old_number)
                save_numbers()
        
        # Get new number
        number = random.choice(numbers)
        bot_data["last_number"][user_key] = {
            "number": number,
            "country": country,
            "time": datetime.now().isoformat()
        }
        save_data()
        
        country_flags = {
            "1": "🇺🇸", "91": "🇮🇳", "92": "🇵🇰", "95": "🇲🇲"
        }
        country_names = {
            "1": "USA", "91": "India", "92": "Pakistan", "95": "Myanmar"
        }
        
        flag = country_flags.get(country, "🌍")
        name = country_names.get(country, country)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change Number", callback_data=f"change:{country}")],
            [InlineKeyboardButton("🌍 Change Country", callback_data="changecountry")],
            [InlineKeyboardButton("📱 OTP Group", callback_data="otpgroup")],
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
        
        country_flags = {
            "1": "🇺🇸", "91": "🇮🇳", "92": "🇵🇰", "95": "🇲🇲"
        }
        country_names = {
            "1": "USA", "91": "India", "92": "Pakistan", "95": "Myanmar"
        }
        
        buttons = []
        for country in sorted(countries):
            flag = country_flags.get(country, "🌍")
            name = country_names.get(country, country)
            buttons.append(InlineKeyboardButton(
                f"{flag} {name}",
                callback_data=f"getcountry:{country}"
            ))
        
        keyboard_buttons = [[buttons[i], buttons[i+1]] if i+1 < len(buttons) else [buttons[i]] 
                           for i in range(0, len(buttons), 2)]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        await query.edit_message_text(
            "🌍 *Select Country for Facebook:*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    elif data == "otpgroup":
        # Direct redirect to OTP group
        await context.bot.send_message(
            chat_id=user_id,
            text=f"[Open OTP Group]({OTP_CHANNEL_LINK})",
            parse_mode="Markdown"
        )
        await query.answer("✅ Opening OTP Group...")
    
    elif data.startswith("admin_"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Admin only!")
            return
        
        action = data.split("_")[1]
        
        if action == "stats":
            total_numbers = sum(len(v) for v in numbers_pool.values())
            countries = len(numbers_pool)
            total_users = bot_data.get("total_users", 0)
            active_sessions = len([u for u in bot_data.get("last_number", {}).keys()])
            
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
            await query.edit_message_text(
                f"📈 *Analytics*\n\n"
                f"Coming soon..."
            )
        
        elif action == "delete":
            await query.edit_message_text(
                f"🗑️ *Delete Numbers*\n\n"
                f"Coming soon..."
            )
        
        elif action == "settings":
            await query.edit_message_text(
                f"⚙️ *Settings*\n\n"
                f"Coming soon..."
            )

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
            "❌ *Invalid filename!*\n\n"
            "Format: `country_code.txt`",
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
    
    country_names = {
        "1": "USA", "91": "India", "92": "Pakistan", "95": "Myanmar",
    }
    country_name = country_names.get(country, country)
    
    await update.message.reply_text(
        f"✅ *Upload Complete!*\n\n"
        f"🌍 Country: `{country_name}`\n"
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
