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

def fetch_all_otps():
    """Fetch OTPs from CR API"""
    otps = fetch_cr_api_otps()
    return otps if otps else []

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

def extract_country_code(number):
    """Extract country code from number (first 1-3 digits)"""
    # Common country codes
    country_codes = {
        "1": "USA",
        "7": "Russia",
        "20": "Egypt",
        "27": "South Africa",
        "30": "Greece",
        "31": "Netherlands",
        "32": "Belgium",
        "33": "France",
        "34": "Spain",
        "36": "Hungary",
        "39": "Italy",
        "40": "Romania",
        "41": "Switzerland",
        "43": "Austria",
        "44": "UK",
        "45": "Denmark",
        "46": "Sweden",
        "47": "Norway",
        "48": "Poland",
        "49": "Germany",
        "51": "Peru",
        "52": "Mexico",
        "53": "Cuba",
        "54": "Argentina",
        "55": "Brazil",
        "56": "Chile",
        "57": "Colombia",
        "58": "Venezuela",
        "60": "Malaysia",
        "61": "Australia",
        "62": "Indonesia",
        "63": "Philippines",
        "64": "New Zealand",
        "65": "Singapore",
        "66": "Thailand",
        "81": "Japan",
        "82": "South Korea",
        "84": "Vietnam",
        "86": "China",
        "90": "Turkey",
        "91": "India",
        "92": "Pakistan",
        "93": "Afghanistan",
        "94": "Sri Lanka",
        "95": "Myanmar",
        "98": "Iran",
        "212": "Morocco",
        "213": "Algeria",
        "216": "Tunisia",
        "220": "Senegal",
        "222": "Mauritania",
        "223": "Mali",
        "224": "Guinea",
        "225": "Ivory Coast",
        "226": "Burkina Faso",
        "227": "Niger",
        "228": "Togo",
        "229": "Benin",
        "230": "Mauritius",
        "231": "Liberia",
        "232": "Sierra Leone",
        "233": "Ghana",
        "234": "Nigeria",
        "235": "Chad",
        "236": "Central Africa",
        "237": "Cameroon",
        "238": "Cape Verde",
        "240": "Equatorial Guinea",
        "241": "Gabon",
        "242": "Congo",
        "243": "DRC",
        "244": "Angola",
        "245": "Guinea-Bissau",
        "248": "Seychelles",
        "249": "Sudan",
        "250": "Uganda",
        "251": "Ethiopia",
        "252": "Somalia",
        "253": "Djibouti",
        "254": "Kenya",
        "255": "Tanzania",
        "256": "Uganda",
        "257": "Burundi",
        "258": "Mozambique",
        "260": "Zambia",
        "261": "Madagascar",
        "262": "Reunion",
        "263": "Zimbabwe",
        "264": "Namibia",
        "265": "Malawi",
        "266": "Lesotho",
        "267": "Botswana",
        "268": "Eswatini",
        "290": "Saint Helena",
        "291": "Eritrea",
        "297": "Aruba",
        "298": "Faroe Islands",
        "299": "Greenland",
        "350": "Gibraltar",
        "351": "Portugal",
        "352": "Luxembourg",
        "353": "Ireland",
        "354": "Iceland",
        "355": "Albania",
        "356": "Malta",
        "357": "Cyprus",
        "358": "Finland",
        "359": "Bulgaria",
        "370": "Lithuania",
        "371": "Latvia",
        "372": "Estonia",
        "373": "Moldova",
        "374": "Armenia",
        "375": "Belarus",
        "376": "Andorra",
        "377": "Monaco",
        "378": "San Marino",
        "380": "Ukraine",
        "381": "Serbia",
        "382": "Montenegro",
        "383": "Kosovo",
        "385": "Croatia",
        "386": "Slovenia",
        "387": "Bosnia",
        "389": "Macedonia",
        "420": "Czech Republic",
        "421": "Slovakia",
        "423": "Liechtenstein",
        "500": "Falkland Islands",
        "501": "Belize",
        "502": "Guatemala",
        "503": "El Salvador",
        "504": "Honduras",
        "505": "Nicaragua",
        "506": "Costa Rica",
        "507": "Panama",
        "508": "Saint Pierre",
        "509": "Haiti",
        "590": "Guadeloupe",
        "591": "Bolivia",
        "592": "Guyana",
        "593": "Ecuador",
        "594": "French Guiana",
        "595": "Paraguay",
        "596": "Martinique",
        "597": "Suriname",
        "598": "Uruguay",
        "599": "Netherlands Antilles",
        "670": "Northern Mariana Islands",
        "672": "Norfolk Island",
        "673": "Brunei",
        "674": "Nauru",
        "675": "Papua New Guinea",
        "676": "Tonga",
        "677": "Solomon Islands",
        "678": "Vanuatu",
        "679": "Fiji",
        "680": "Palau",
        "681": "Wallis and Futuna",
        "682": "Cook Islands",
        "683": "Niue",
        "684": "American Samoa",
        "685": "Samoa",
        "686": "Kiribati",
        "687": "New Caledonia",
        "688": "Tuvalu",
        "689": "French Polynesia",
        "690": "Tokelau",
        "691": "Federated States of Micronesia",
        "692": "Marshall Islands",
        "850": "North Korea",
        "852": "Hong Kong",
        "853": "Macau",
        "855": "Cambodia",
        "856": "Laos",
        "880": "Bangladesh",
        "886": "Taiwan",
        "960": "Maldives",
        "961": "Lebanon",
        "962": "Jordan",
        "963": "Syria",
        "964": "Iraq",
        "965": "Kuwait",
        "966": "Saudi Arabia",
        "967": "Yemen",
        "968": "Oman",
        "970": "Palestine",
        "971": "United Arab Emirates",
        "972": "Israel",
        "973": "Bahrain",
        "974": "Qatar",
        "975": "Bhutan",
        "976": "Mongolia",
        "977": "Nepal",
        "992": "Tajikistan",
        "993": "Turkmenistan",
        "994": "Azerbaijan",
        "995": "Georgia",
        "996": "Kyrgyzstan",
        "998": "Uzbekistan",
    }
    
    # Try 3-digit, then 2-digit, then 1-digit
    for length in [3, 2, 1]:
        code = number[:length]
        if code in country_codes:
            return code
    
    return "Unknown"

# ─── File Storage ─────────────────────────────────────────────────────────

numbers_pool = {}  # Format: {country: [numbers]}
bot_data = {"last_number": {}}

def load_numbers():
    """Load numbers from JSON file"""
    global numbers_pool
    try:
        if os.path.exists(NUMBERS_FILE):
            with open(NUMBERS_FILE, 'r') as f:
                numbers_pool = json.load(f)
        else:
            numbers_pool = {}
            save_numbers()
        logger.info(f"✅ Loaded numbers pool: {len(numbers_pool)} countries")
    except Exception as e:
        logger.error(f"Error loading numbers: {e}")
        numbers_pool = {}

def save_numbers():
    """Save numbers to JSON file"""
    try:
        with open(NUMBERS_FILE, 'w') as f:
            json.dump(numbers_pool, f, indent=2)
        logger.info(f"✅ Saved {sum(len(v) for v in numbers_pool.values())} numbers")
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
                country = extract_country_code(number)
                
                # Country flags
                country_flags = {
                    "1": "🇺🇸", "7": "🇷🇺", "20": "🇪🇬", "27": "🇿🇦", "30": "🇬🇷",
                    "31": "🇳🇱", "32": "🇧🇪", "33": "🇫🇷", "34": "🇪🇸", "36": "🇭🇺",
                    "39": "🇮🇹", "40": "🇷🇴", "41": "🇨🇭", "43": "🇦🇹", "44": "🇬🇧",
                    "45": "🇩🇰", "46": "🇸🇪", "47": "🇳🇴", "48": "🇵🇱", "49": "🇩🇪",
                    "91": "🇮🇳", "92": "🇵🇰", "95": "🇲🇲", "212": "🇲🇦", "213": "🇩🇿",
                }
                
                flag = country_flags.get(country, "🌍")
                
                # Get country name from extraction
                country_names = {
                    "1": "USA", "7": "Russia", "20": "Egypt", "27": "South Africa",
                    "91": "India", "92": "Pakistan", "95": "Myanmar", "212": "Morocco",
                }
                country_name = country_names.get(country, country)
                
                # Format message for Telegram
                msg = (
                    f"🆕 *NEW OTP - FACEBOOK*\n\n"
                    f"📱 Number: `{number}`\n"
                    f"🌍 Country: {flag} `{country_name}`\n"
                    f"🔐 OTP Code: `{otp_code}`\n"
                    f"📝 Message: `{message[:80]}...`\n"
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
        f"📘 *Facebook OTP Number Provider*\n\n"
        f"আমরা real Facebook verification numbers provide করি।",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def reply_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reply keyboard buttons"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "📲 Get Number":
        # Show country selection
        countries = list(numbers_pool.keys())
        
        if not countries:
            await update.message.reply_text("❌ No numbers available yet!")
            return
        
        # Country flags mapping
        country_flags = {
            "1": "🇺🇸", "7": "🇷🇺", "20": "🇪🇬", "27": "🇿🇦", "91": "🇮🇳",
            "92": "🇵🇰", "95": "🇲🇲", "212": "🇲🇦", "213": "🇩🇿",
        }
        
        country_names = {
            "1": "USA", "7": "Russia", "20": "Egypt", "27": "South Africa",
            "91": "India", "92": "Pakistan", "95": "Myanmar", "212": "Morocco",
            "213": "Algeria",
        }
        
        # Create buttons (max 8 per row)
        buttons = []
        for country in sorted(countries):
            flag = country_flags.get(country, "🌍")
            name = country_names.get(country, country)
            buttons.append(InlineKeyboardButton(
                f"{flag} {name} ({len(numbers_pool[country])} numbers)",
                callback_data=f"country:{country}"
            ))
        
        # Split into rows (2 per row)
        keyboard_buttons = [[buttons[i], buttons[i+1]] if i+1 < len(buttons) else [buttons[i]] 
                           for i in range(0, len(buttons), 2)]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        await update.message.reply_text(
            "🌍 *Select Country:*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    elif text == "📋 Active Numbers":
        # Show active numbers
        msg = "📱 *Your Active Numbers:*\n\n"
        
        user_key = str(user_id)
        if user_key in bot_data.get("last_number", {}):
            number = bot_data["last_number"][user_key]
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
            [InlineKeyboardButton("➕ Add Numbers (TXT)", callback_data="admin:addnumbers")],
            [InlineKeyboardButton("📊 Statistics", callback_data="admin:stats")],
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
    
    if data.startswith("country:"):
        country = data.split(":")[1]
        
        numbers = numbers_pool.get(country, [])
        
        if not numbers:
            await query.answer("❌ No numbers available for this country")
            return
        
        # Get random number
        number = random.choice(numbers)
        
        # Save last number
        bot_data["last_number"][str(user_id)] = number
        save_data()
        
        country_flags = {
            "1": "🇺🇸", "7": "🇷🇺", "91": "🇮🇳", "92": "🇵🇰", "95": "🇲🇲"
        }
        country_names = {
            "1": "USA", "91": "India", "92": "Pakistan", "95": "Myanmar"
        }
        
        flag = country_flags.get(country, "🌍")
        name = country_names.get(country, country)
        
        await query.edit_message_text(
            f"📘 *Facebook* | {flag} *{name}*\n\n"
            f"📱 Number: `{number}`\n\n"
            f"⏰ Valid for 10 minutes\n"
            f"🔗 Join: {OTP_CHANNEL_LINK}",
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
                "📌 *Format:*\n"
                "• File name: `country_code.txt` (e.g., `91.txt`, `1.txt`, `95.txt`)\n"
                "• Content: One number per line\n\n"
                "📌 *Example:*\n"
                "File: `91.txt`\n"
                "Content:\n```\n9876543210\n9876543211\n9876543212\n```\n\n"
                "All numbers will be added as Facebook numbers for that country."
            )
        
        elif action == "stats":
            total = sum(len(v) for v in numbers_pool.values())
            countries = len(numbers_pool)
            await query.edit_message_text(
                f"📊 *Bot Statistics*\n\n"
                f"📱 Total Numbers: `{total}`\n"
                f"🌍 Countries: `{countries}`\n"
                f"📘 Service: Facebook Only"
            )

async def handle_txt_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle TXT file upload"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    file = await update.message.document.get_file()
    content = await file.download_as_bytearray()
    text = content.decode('utf-8', errors='ignore')
    
    # Extract country code from filename
    filename = update.message.document.file_name
    country_match = re.match(r'(\d+)', filename)
    
    if not country_match:
        await update.message.reply_text(
            "❌ *Invalid filename!*\n\n"
            "Format: `country_code.txt`\n"
            "Example: `91.txt`, `1.txt`, `95.txt`",
            parse_mode="Markdown"
        )
        return
    
    country = country_match.group(1)
    
    # Initialize country if not exists
    if country not in numbers_pool:
        numbers_pool[country] = []
    
    added = 0
    skipped = 0
    
    for line in text.split('\n'):
        number = line.strip()
        
        if not number or len(number) < 7:  # Minimum number length
            skipped += 1
            continue
        
        # Remove common prefixes
        number = number.lstrip('+')
        
        # Check if it starts with country code, if not add it
        if not number.startswith(country):
            # This might be a local number, prepend country code
            if not number.startswith('+'):
                number = country + number
        
        if number not in numbers_pool[country]:
            numbers_pool[country].append(number)
            added += 1
        else:
            skipped += 1
    
    save_numbers()
    
    country_names = {
        "1": "USA", "7": "Russia", "91": "India", "92": "Pakistan",
        "95": "Myanmar", "212": "Morocco", "213": "Algeria",
    }
    country_name = country_names.get(country, country)
    
    await update.message.reply_text(
        f"✅ *Upload Complete!*\n\n"
        f"🌍 Country: `{country_name}`\n"
        f"✅ Added: `{added}` numbers\n"
        f"⏭ Skipped (duplicates): `{skipped}`\n"
        f"📱 Total now: `{len(numbers_pool[country])}`",
        parse_mode="Markdown"
    )

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Starting Telegram OTP Bot - Facebook Only...")
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
