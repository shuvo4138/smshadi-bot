import logging
import re
import random
import requests
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.error import BadRequest

load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "1984916365").strip())
OTP_CHANNEL_ID = int(os.getenv("OTP_CHANNEL_ID", "-1002625886518").strip())
OTP_CHANNEL_LINK = os.getenv("OTP_CHANNEL_LINK", "https://t.me/+SWraCXOQrWM4Mzg9").strip()
JOIN_CHANNEL = os.getenv("JOIN_CHANNEL", "https://t.me/alwaysrvice24hours").strip()
API_TOKEN = os.getenv("API_TOKEN", "").strip()
API_URL = "http://147.135.212.197/crapi/had/viewstats"
NUMBERS_FILE = "numbers.json"
DATA_FILE = "bot_data.json"

SERVICES = ["Facebook", "WhatsApp", "TikTok", "Instagram", "Telegram"]
SERVICE_EMOJI = {
    "Facebook": "📘",
    "WhatsApp": "💬",
    "TikTok": "🎵",
    "Instagram": "📸",
    "Telegram": "✈️",
}

COUNTRY_FLAGS = {
    "1242": "🇧🇸", "1268": "🇦🇬", "1345": "🇰🇾", "1441": "🇧🇲", "1473": "🇬🇩",
    "1649": "🇹🇨", "1664": "🇲🇸", "1670": "🇲🇵", "1671": "🇬🇺", "1684": "🇦🇸",
    "1721": "🇸🇽", "1758": "🇱🇨", "1767": "🇩🇲", "1784": "🇻🇨", "1809": "🇩🇴",
    "1868": "🇹🇹", "1869": "🇰🇳", "1876": "🇯🇲",
    "20": "🇪🇬", "212": "🇲🇦", "213": "🇩🇿", "216": "🇹🇳", "218": "🇱🇾",
    "220": "🇬🇲", "221": "🇸🇳", "222": "🇲🇷", "223": "🇲🇱", "224": "🇬🇳",
    "225": "🇨🇮", "226": "🇧🇫", "227": "🇳🇪", "228": "🇹🇬", "229": "🇧🇯",
    "230": "🇲🇺", "231": "🇱🇷", "232": "🇸🇱", "233": "🇬🇭", "234": "🇳🇬",
    "235": "🇹🇩", "236": "🇨🇫", "237": "🇨🇲", "238": "🇨🇻", "239": "🇸🇹",
    "240": "🇬🇶", "241": "🇬🇦", "242": "🇨🇬", "243": "🇨🇩", "244": "🇦🇴",
    "245": "🇬🇼", "246": "🇮🇴", "247": "🇦🇨", "248": "🇸🇨", "249": "🇸🇩",
    "250": "🇷🇼", "251": "🇪🇹", "252": "🇸🇴", "253": "🇩🇯", "254": "🇰🇪",
    "255": "🇹🇿", "256": "🇺🇬", "257": "🇧🇮", "258": "🇲🇿", "260": "🇿🇲",
    "261": "🇲🇬", "262": "🇷🇪", "263": "🇿🇼", "264": "🇳🇦", "265": "🇲🇼",
    "266": "🇱🇸", "267": "🇧🇼", "268": "🇸🇿", "269": "🇰🇲",
    "27": "🇿🇦", "290": "🇸🇭", "291": "🇪🇷", "297": "🇦🇼", "298": "🇫🇴",
    "299": "🇬🇱", "30": "🇬🇷", "31": "🇳🇱", "32": "🇧🇪", "33": "🇫🇷",
    "34": "🇪🇸", "350": "🇬🇮", "351": "🇵🇹", "352": "🇱🇺", "353": "🇮🇪",
    "354": "🇮🇸", "355": "🇦🇱", "356": "🇲🇹", "357": "🇨🇾", "358": "🇫🇮",
    "359": "🇧🇬", "36": "🇭🇺", "370": "🇱🇹", "371": "🇱🇻", "372": "🇪🇪",
    "373": "🇲🇩", "374": "🇦🇲", "375": "🇧🇾", "376": "🇦🇩", "377": "🇲🇨",
    "378": "🇸🇲", "380": "🇺🇦", "381": "🇷🇸", "382": "🇲🇪", "385": "🇭🇷",
    "386": "🇸🇮", "387": "🇧🇦", "389": "🇲🇰", "39": "🇮🇹", "40": "🇷🇴",
    "41": "🇨🇭", "420": "🇨🇿", "421": "🇸🇰", "423": "🇱🇮", "43": "🇦🇹",
    "44": "🇬🇧", "45": "🇩🇰", "46": "🇸🇪", "47": "🇳🇴", "48": "🇵🇱",
    "49": "🇩🇪", "500": "🇫🇰", "501": "🇧🇿", "502": "🇬🇹", "503": "🇸🇻",
    "504": "🇭🇳", "505": "🇳🇮", "506": "🇨🇷", "507": "🇵🇦", "508": "🇵🇲",
    "509": "🇭🇹", "51": "🇵🇪", "52": "🇲🇽", "53": "🇨🇺", "54": "🇦🇷",
    "55": "🇧🇷", "56": "🇨🇱", "57": "🇨🇴", "58": "🇻🇪", "590": "🇬🇵",
    "591": "🇧🇴", "592": "🇬🇾", "593": "🇪🇨", "595": "🇵🇾", "597": "🇸🇷",
    "598": "🇺🇾", "599": "🇨🇼", "60": "🇲🇾", "61": "🇦🇺", "62": "🇮🇩",
    "63": "🇵🇭", "64": "🇳🇿", "65": "🇸🇬", "66": "🇹🇭", "670": "🇹🇱",
    "672": "🇳🇫", "673": "🇧🇳", "674": "🇳🇷", "675": "🇵🇬", "676": "🇹🇴",
    "677": "🇸🇧", "678": "🇻🇺", "679": "🇫🇯", "680": "🇵🇼", "681": "🇼🇫",
    "682": "🇨🇰", "683": "🇳🇺", "685": "🇼🇸", "686": "🇰🇮", "687": "🇳🇨",
    "688": "🇹🇻", "689": "🇵🇫", "690": "🇹🇰", "691": "🇫🇲", "692": "🇲🇭",
    "7": "🇷🇺", "81": "🇯🇵", "82": "🇰🇷", "84": "🇻🇳", "850": "🇰🇵",
    "852": "🇭🇰", "853": "🇲🇴", "855": "🇰🇭", "856": "🇱🇦", "86": "🇨🇳",
    "880": "🇧🇩", "886": "🇹🇼", "90": "🇹🇷", "91": "🇮🇳", "92": "🇵🇰",
    "93": "🇦🇫", "94": "🇱🇰", "95": "🇲🇲", "960": "🇲🇻", "961": "🇱🇧",
    "962": "🇯🇴", "963": "🇸🇾", "964": "🇮🇶", "965": "🇰🇼", "966": "🇸🇦",
    "967": "🇾🇪", "968": "🇴🇲", "970": "🇵🇸", "971": "🇦🇪", "972": "🇮🇱",
    "973": "🇧🇭", "974": "🇶🇦", "975": "🇧🇹", "976": "🇲🇳", "977": "🇳🇵",
    "992": "🇹🇯", "993": "🇹🇲", "994": "🇦🇿", "995": "🇬🇪", "996": "🇰🇬",
    "998": "🇺🇿", "959": "🇲🇲", "1": "🇺🇸",
}

COUNTRY_NAMES = {
    "93": "Afghanistan", "355": "Albania", "213": "Algeria", "376": "Andorra",
    "244": "Angola", "54": "Argentina", "374": "Armenia", "61": "Australia",
    "43": "Austria", "994": "Azerbaijan", "973": "Bahrain", "880": "Bangladesh",
    "375": "Belarus", "32": "Belgium", "501": "Belize", "229": "Benin",
    "975": "Bhutan", "591": "Bolivia", "387": "Bosnia", "267": "Botswana",
    "55": "Brazil", "673": "Brunei", "359": "Bulgaria", "226": "Burkina Faso",
    "257": "Burundi", "855": "Cambodia", "237": "Cameroon", "238": "Cape Verde",
    "236": "CAR", "235": "Chad", "56": "Chile", "86": "China",
    "57": "Colombia", "269": "Comoros", "242": "Congo", "243": "DR Congo",
    "506": "Costa Rica", "385": "Croatia", "53": "Cuba", "357": "Cyprus",
    "420": "Czech Republic", "45": "Denmark", "253": "Djibouti", "593": "Ecuador",
    "20": "Egypt", "503": "El Salvador", "240": "Equatorial Guinea", "291": "Eritrea",
    "372": "Estonia", "251": "Ethiopia", "679": "Fiji", "358": "Finland",
    "33": "France", "241": "Gabon", "220": "Gambia", "995": "Georgia",
    "49": "Germany", "233": "Ghana", "30": "Greece", "502": "Guatemala",
    "224": "Guinea", "245": "Guinea-Bissau", "592": "Guyana", "509": "Haiti",
    "504": "Honduras", "36": "Hungary", "354": "Iceland", "91": "India",
    "62": "Indonesia", "98": "Iran", "964": "Iraq", "353": "Ireland",
    "972": "Israel", "39": "Italy", "81": "Japan", "962": "Jordan",
    "7": "Russia/Kazakhstan", "254": "Kenya", "82": "South Korea", "965": "Kuwait",
    "996": "Kyrgyzstan", "856": "Laos", "371": "Latvia", "961": "Lebanon",
    "266": "Lesotho", "231": "Liberia", "218": "Libya", "370": "Lithuania",
    "352": "Luxembourg", "261": "Madagascar", "265": "Malawi", "60": "Malaysia",
    "960": "Maldives", "223": "Mali", "356": "Malta", "222": "Mauritania",
    "230": "Mauritius", "52": "Mexico", "373": "Moldova", "212": "Morocco",
    "258": "Mozambique", "95": "Myanmar", "959": "Myanmar", "264": "Namibia",
    "977": "Nepal", "31": "Netherlands", "64": "New Zealand", "505": "Nicaragua",
    "227": "Niger", "234": "Nigeria", "47": "Norway", "968": "Oman",
    "92": "Pakistan", "507": "Panama", "675": "Papua New Guinea", "595": "Paraguay",
    "51": "Peru", "63": "Philippines", "48": "Poland", "351": "Portugal",
    "970": "Palestine", "974": "Qatar", "40": "Romania", "250": "Rwanda",
    "966": "Saudi Arabia", "221": "Senegal", "381": "Serbia", "232": "Sierra Leone",
    "65": "Singapore", "421": "Slovakia", "386": "Slovenia", "252": "Somalia",
    "27": "South Africa", "34": "Spain", "94": "Sri Lanka", "249": "Sudan",
    "597": "Suriname", "46": "Sweden", "41": "Switzerland", "963": "Syria",
    "886": "Taiwan", "992": "Tajikistan", "255": "Tanzania", "66": "Thailand",
    "670": "Timor-Leste", "228": "Togo", "676": "Tonga", "1868": "Trinidad",
    "216": "Tunisia", "90": "Turkey", "993": "Turkmenistan", "256": "Uganda",
    "380": "Ukraine", "971": "UAE", "44": "UK", "598": "Uruguay",
    "998": "Uzbekistan", "678": "Vanuatu", "58": "Venezuela", "84": "Vietnam",
    "967": "Yemen", "260": "Zambia", "263": "Zimbabwe", "1": "USA/Canada",
}

if not BOT_TOKEN:
    logger.error("BOT_TOKEN is not set!")
    import time
    time.sleep(10)
    exit(1)

# numbers_pool structure: {service: {country_code: [numbers]}}
numbers_pool = {s: {} for s in SERVICES}

user_numbers = {}   # user_id -> {"number": ..., "service": ..., "country": ...}
user_history = {}   # user_id -> list of records
otp_history = {}    # number -> list of otp records
otp_cache = {}      # cache_key -> datetime
banned_users = set()
all_users = set()

# ─── Helpers ─────────────────────────────────────────────────────

def get_flag(number: str) -> str:
    number = number.lstrip("+").strip()
    for length in [4, 3, 2, 1]:
        prefix = number[:length]
        if prefix in COUNTRY_FLAGS:
            return COUNTRY_FLAGS[prefix]
    return "🌍"

def get_country_code(number: str) -> str:
    number = number.lstrip("+").strip()
    for length in [4, 3, 2, 1]:
        prefix = number[:length]
        if prefix in COUNTRY_NAMES:
            return prefix
    return "unknown"

def get_country_name(code: str) -> str:
    return COUNTRY_NAMES.get(code, code)

def mask_number(number: str) -> str:
    n = str(number)
    return n[:4] + "★★★★" + n[-4:] if len(n) >= 8 else n

def extract_otp(msg: str) -> str:
    if not msg:
        return ""
    msg = msg.replace("# ", "").replace("#", "")
    codes = re.findall(r'\b\d{4,8}\b', msg)
    return codes[0] if codes else ""

def get_available_countries(service: str) -> list:
    """Service এ কোন কোন দেশের number আছে"""
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

def is_cache_fresh(cache_key: str) -> bool:
    if cache_key not in otp_cache:
        return False
    return datetime.now() - otp_cache[cache_key] < timedelta(minutes=30)

def add_otp_to_history(number: str, record: dict):
    if number not in otp_history:
        otp_history[number] = []
    otp_history[number].insert(0, record)
    otp_history[number] = otp_history[number][:20]

def service_stats():
    assigned = {v["number"] for v in user_numbers.values()}
    stats = {}
    for s in SERVICES:
        total = sum(len(nums) for nums in numbers_pool[s].values())
        busy = sum(1 for nums in numbers_pool[s].values() for n in nums if n in assigned)
        stats[s] = {"total": total, "available": total - busy, "busy": busy}
    return stats

# ─── Keyboards ───────────────────────────────────────────────────

def service_keyboard():
    buttons = []
    row = []
    for i, s in enumerate(SERVICES):
        emoji = SERVICE_EMOJI[s]
        row.append(InlineKeyboardButton(f"{emoji} {s}", callback_data=f"service_{s}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)

def country_keyboard(service: str):
    countries = get_available_countries(service)
    if not countries:
        return None
    buttons = []
    row = []
    for i, code in enumerate(countries):
        flag = COUNTRY_FLAGS.get(code, "🌍")
        name = get_country_name(code)
        row.append(InlineKeyboardButton(f"{flag} {name}", callback_data=f"country_{service}_{code}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="get_number")])
    return InlineKeyboardMarkup(buttons)

def number_action_keyboard(number: str, service: str, country: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{number}"),
         InlineKeyboardButton("📜 OTP History", callback_data=f"history_{number}")],
        [InlineKeyboardButton("❌ Number ছাড়ুন", callback_data="release_number")],
    ])

async def safe_edit(query, text, parse_mode="Markdown", reply_markup=None):
    try:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise

# ─── Persistence ─────────────────────────────────────────────────

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
            logger.info("Numbers loaded.")
    except Exception as e:
        logger.error(f"Load error: {e}")

def save_data():
    try:
        data = {
            "user_numbers": {str(k): v for k, v in user_numbers.items()},
            "user_history": {str(k): v for k, v in user_history.items()},
            "otp_history": otp_history,
            "banned_users": list(banned_users),
            "all_users": list(all_users),
        }
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Data save error: {e}")

def load_data():
    global user_numbers, user_history, otp_history, banned_users, all_users
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            user_numbers = {int(k): v for k, v in data.get("user_numbers", {}).items()}
            user_history = {int(k): v for k, v in data.get("user_history", {}).items()}
            otp_history = data.get("otp_history", {})
            banned_users = set(data.get("banned_users", []))
            all_users = set(data.get("all_users", []))
    except Exception as e:
        logger.error(f"Data load error: {e}")

# ─── API ─────────────────────────────────────────────────────────

def fetch_otp_for_number(number: str):
    try:
        clean_num = number.lstrip("+").strip()
        resp = requests.get(API_URL, params={"token": API_TOKEN, "filternum": clean_num, "records": 10}, timeout=15)
        data = resp.json()
        if data.get("status") == "success" and data.get("data"):
            latest = data["data"][0]
            return {
                "datetime": latest.get("dt", ""),
                "sender": latest.get("cli", "Unknown"),
                "message": latest.get("message", ""),
                "number": latest.get("num", clean_num)
            }
    except Exception as e:
        logger.error(f"Fetch OTP error: {e}")
    return None

def fetch_all_recent_otps():
    try:
        resp = requests.get(API_URL, params={"token": API_TOKEN, "records": 100}, timeout=15)
        data = resp.json()
        if data.get("status") == "success":
            return data.get("data", [])
    except Exception as e:
        logger.error(f"Polling error: {e}")
    return []

async def is_member(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=OTP_CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

# ─── Polling Job ─────────────────────────────────────────────────

async def poll_otps(context):
    rows = fetch_all_recent_otps()
    for row in rows:
        try:
            dt_str = row.get("dt", "")
            number = str(row.get("num", "")).strip()
            sender = row.get("cli", "Unknown")
            message = row.get("message", "")
            if not message or not number:
                continue
            cache_key = f"{number}:{dt_str}:{message[:30]}"
            if is_cache_fresh(cache_key):
                continue
            otp_cache[cache_key] = datetime.now()
            otp_code = extract_otp(message)
            add_otp_to_history(number, {"datetime": dt_str, "sender": sender, "message": message, "otp": otp_code})

            owner_id = None
            for uid, info in user_numbers.items():
                if info["number"].lstrip("+") == number.lstrip("+"):
                    owner_id = uid
                    break

            flag = get_flag(number)
            try:
                await context.bot.send_message(
                    chat_id=OTP_CHANNEL_ID,
                    text=f"📩 *নতুন OTP*\n\n{flag} Number: `{mask_number(number)}`\n🏢 From: {sender}\n🔐 OTP: `{otp_code}`\n💬 {message[:100]}\n🕐 {dt_str}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Channel error: {e}")

            if owner_id:
                try:
                    await context.bot.send_message(
                        chat_id=owner_id,
                        text=f"✅ *OTP এসেছে!*\n\n{flag} `{number}`\n🏢 From: *{sender}*\n🔐 OTP: `{otp_code}`\n💬 _{message[:100]}_\n🕐 {dt_str}",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{number}")]])
                    )
                except Exception as e:
                    logger.error(f"User notify error: {e}")
        except Exception as e:
            logger.error(f"OTP process error: {e}")
    save_data()

# ─── Handlers ────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    if user.id in banned_users:
        await update.message.reply_text("❌ আপনি ban হয়েছেন।")
        return
    await update.message.reply_text(
        f"👋 স্বাগতম *{user.first_name}*!\n\n🤖 *SMS Hadi OTP Bot*\n\nService বেছে number নিন এবং OTP receive করুন। 👇",
        parse_mode="Markdown",
        reply_markup=service_keyboard()
    )
    save_data()

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ আপনি admin না!")
        return
    await show_admin_panel(update, context)

async def show_admin_panel(update, context):
    stats = service_stats()
    total_otp = sum(len(v) for v in otp_history.values())
    text = f"👑 *Admin Panel*\n\n👥 Users: {len(all_users)} | 🚫 Banned: {len(banned_users)}\n📨 Total OTP: {total_otp}\n\n*📦 Number Pool:*\n"
    for s in SERVICES:
        st = stats[s]
        emoji = SERVICE_EMOJI[s]
        text += f"{emoji} {s}: {st['total']} | 🟢 {st['available']} | 🔴 {st['busy']}\n"
    await update.message.reply_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 User List", callback_data="admin_users"),
             InlineKeyboardButton("📊 OTP Stats", callback_data="admin_otp_stats")],
            [InlineKeyboardButton("➕ Number যোগ", callback_data="admin_add_num"),
             InlineKeyboardButton("📋 Number List", callback_data="admin_numlist")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
             InlineKeyboardButton("🧪 Test API", callback_data="admin_test")],
            [InlineKeyboardButton("🔴 Live OTP", callback_data="admin_live_otp"),
             InlineKeyboardButton("📤 File Upload", callback_data="admin_upload")],
            [InlineKeyboardButton("🗑 Clear", callback_data="admin_clear"),
             InlineKeyboardButton("🚫 Ban/Unban", callback_data="admin_ban_menu")],
        ])
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text
    user_id = update.effective_user.id
    all_users.add(user_id)

    if user_id in banned_users and user_id != ADMIN_ID:
        await update.message.reply_text("❌ আপনি ban হয়েছেন।")
        return

    if context.user_data.get("broadcast_mode") and user_id == ADMIN_ID:
        context.user_data["broadcast_mode"] = False
        sent = failed = 0
        for uid in list(all_users):
            if uid in banned_users:
                continue
            try:
                await context.bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
                sent += 1
            except Exception:
                failed += 1
        await update.message.reply_text(f"📢 Broadcast!\n✅ Sent: {sent} | ❌ Failed: {failed}")
        return

    if context.user_data.get("ban_mode") and user_id == ADMIN_ID:
        context.user_data["ban_mode"] = False
        try:
            target = int(text.strip())
            banned_users.add(target)
            save_data()
            await update.message.reply_text(f"🚫 `{target}` ban!", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Valid User ID দিন।")
        return

    if context.user_data.get("unban_mode") and user_id == ADMIN_ID:
        context.user_data["unban_mode"] = False
        try:
            target = int(text.strip())
            banned_users.discard(target)
            save_data()
            await update.message.reply_text(f"✅ `{target}` unban!", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Valid User ID দিন।")
        return

    if context.user_data.get("add_number_mode") and user_id == ADMIN_ID:
        service, country_code = context.user_data.pop("add_number_mode")
        tokens = re.split(r'[\s,;]+', text)
        added = []
        for token in tokens:
            token = token.strip().replace("+", "")
            if token.isdigit() and 8 <= len(token) <= 15:
                if country_code not in numbers_pool[service]:
                    numbers_pool[service][country_code] = []
                if token not in numbers_pool[service][country_code]:
                    numbers_pool[service][country_code].append(token)
                    added.append(token)
        save_numbers()
        flag = COUNTRY_FLAGS.get(country_code, "🌍")
        name = get_country_name(country_code)
        await update.message.reply_text(
            f"✅ *{SERVICE_EMOJI.get(service,'')} {service}* → *{flag} {name}* এ *{len(added)}টি* number যোগ!\n📦 Total: {len(numbers_pool[service].get(country_code, []))}",
            parse_mode="Markdown"
        )
        return

    await start(update, context)

# ─── Button Handler ───────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if user_id in banned_users and user_id != ADMIN_ID:
        await safe_edit(query, "❌ আপনি ban হয়েছেন।")
        return

    if data == "get_number":
        await safe_edit(query, "📲 *Service বেছে নিন:*", reply_markup=service_keyboard())

    elif data.startswith("service_"):
        service = data.replace("service_", "")
        if service not in SERVICES:
            return
        # Join check
        if not await is_member(context.bot, user_id):
            await safe_edit(query,
                f"⚠️ *Number নিতে আগে channel join করুন!*",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Channel Join করুন", url=JOIN_CHANNEL)],
                    [InlineKeyboardButton("✅ Join করেছি", callback_data=data)],
                ])
            )
            return
        kb = country_keyboard(service)
        if not kb:
            await safe_edit(query, f"❌ *{SERVICE_EMOJI.get(service,'')} {service}* এ এখন কোনো number নেই।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="get_number")]]))
            return
        await safe_edit(query, f"{SERVICE_EMOJI.get(service,'')} *{service}* — দেশ বেছে নিন 👇", reply_markup=kb)

    elif data.startswith("country_"):
        parts = data.split("_", 2)
        if len(parts) < 3:
            return
        _, service, country_code = parts
        num = get_available_number(service, country_code)
        if not num:
            await safe_edit(query,
                f"❌ এই দেশে আর number নেই।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"service_{service}")]]))
            return
        if user_id in user_numbers:
            user_numbers.pop(user_id)
        user_numbers[user_id] = {"number": num, "service": service, "country": country_code}
        if user_id not in user_history:
            user_history[user_id] = []
        user_history[user_id].insert(0, {"number": num, "service": service, "country": country_code, "time": datetime.now().strftime("%Y-%m-%d %H:%M")})
        all_users.add(user_id)
        save_data()
        flag = COUNTRY_FLAGS.get(country_code, "🌍")
        name = get_country_name(country_code)
        emoji = SERVICE_EMOJI.get(service, "")
        await safe_edit(query,
            f"📞 *Your Number is Ready!*\n\n"
            f"Tap to copy: `{num}`\n\n"
            f"✅ Your number is active!\n"
            f"❗ Go to our OTP Group to see your incoming SMS.\n\n"
            f"🔖 {emoji} {service} | {flag} {name}",
            reply_markup=number_action_keyboard(num, service, country_code)
        )

    elif data.startswith("refresh_"):
        num = data.replace("refresh_", "")
        info = user_numbers.get(user_id, {})
        result = fetch_otp_for_number(num)
        if result:
            otp_code = extract_otp(result["message"])
            await safe_edit(query,
                f"✅ *Latest OTP:*\n\n📞 `{num}`\n🏢 From: *{result['sender']}*\n🔐 OTP: `{otp_code}`\n💬 _{result['message'][:100]}_\n🕐 {result['datetime']}",
                reply_markup=number_action_keyboard(num, info.get("service",""), info.get("country",""))
            )
        else:
            await safe_edit(query, f"⏳ `{num}` এ এখনো OTP আসেনি।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 আবার", callback_data=f"refresh_{num}")]]))

    elif data.startswith("history_"):
        num = data.replace("history_", "")
        info = user_numbers.get(user_id, {})
        history = otp_history.get(num, [])
        if not history:
            await safe_edit(query, f"📜 কোনো OTP history নেই।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"refresh_{num}")]]))
            return
        text = f"📜 *OTP History*\n📞 `{mask_number(num)}`\n\n"
        for i, h in enumerate(history[:10], 1):
            text += f"{i}. 🔐 `{h['otp']}` | {h['sender']} | {h['datetime']}\n"
        await safe_edit(query, text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"refresh_{num}")]]))

    elif data == "release_number":
        if user_id in user_numbers:
            info = user_numbers.pop(user_id)
            save_data()
            await safe_edit(query, f"✅ `{info['number']}` ছেড়ে দেওয়া হয়েছে।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📲 নতুন Number নিন", callback_data="get_number")]]))
        else:
            await safe_edit(query, "❌ কোনো number নেই।")

    # ─── Admin ───

    elif data == "admin_users":
        if user_id != ADMIN_ID:
            return
        text = f"👥 *Users ({len(all_users)})*\n\n"
        for uid in list(all_users)[:30]:
            info = user_numbers.get(uid, {})
            num = info.get("number", "—")
            svc = info.get("service", "—")
            cc = info.get("country", "")
            flag = COUNTRY_FLAGS.get(cc, "")
            banned = "🚫" if uid in banned_users else "✅"
            text += f"{banned} `{uid}` | {svc} {flag} | `{num}`\n"
        if len(all_users) > 30:
            text += f"\n...আরো {len(all_users)-30} জন"
        await safe_edit(query, text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_otp_stats":
        if user_id != ADMIN_ID:
            return
        total_otp = sum(len(v) for v in otp_history.values())
        text = f"📊 *OTP Stats* — Total: {total_otp}\n\n*সাম্প্রতিক (10):*\n"
        recent = []
        for num, records in otp_history.items():
            for r in records:
                recent.append((r.get("datetime",""), num, r.get("otp",""), r.get("sender","")))
        recent.sort(reverse=True, key=lambda x: x[0])
        for dt, num, otp, sender in recent[:10]:
            flag = get_flag(num)
            text += f"{flag} `{mask_number(num)}` | 🔐 `{otp}` | {sender}\n"
        await safe_edit(query, text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_live_otp":
        if user_id != ADMIN_ID:
            return
        await safe_edit(query, "🔴 *Live OTP চেক করছি...*")
        rows = fetch_all_recent_otps()
        if not rows:
            await context.bot.send_message(user_id, "❌ API থেকে OTP পাওয়া যায়নি।")
            return
        all_pool_numbers = set()
        for s in SERVICES:
            for nums in numbers_pool[s].values():
                all_pool_numbers.update(nums)
        text = f"🔴 *Live OTP* (last {min(len(rows),10)})\n\n"
        for row in rows[:10]:
            num = str(row.get("num", ""))
            sender = row.get("cli", "?")
            message = row.get("message", "")
            dt = row.get("dt", "")
            otp = extract_otp(message)
            flag = get_flag(num)
            in_pool = "✅" if num in all_pool_numbers else "❌"
            text += f"{in_pool}{flag} `{mask_number(num)}` | 🔐 `{otp}` | {sender}\n🕐 {dt}\n\n"
        await context.bot.send_message(user_id, text, parse_mode="Markdown")

    elif data == "admin_add_num":
        if user_id != ADMIN_ID:
            return
        buttons = [[InlineKeyboardButton(f"{SERVICE_EMOJI[s]} {s}", callback_data=f"addnum_{s}")] for s in SERVICES]
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
        await safe_edit(query, "➕ কোন service এ number যোগ করবেন?", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("addnum_"):
        if user_id != ADMIN_ID:
            return
        service = data.replace("addnum_", "")
        context.user_data["pending_add_service"] = service
        await safe_edit(query,
            f"➕ *{SERVICE_EMOJI.get(service,'')} {service}*\n\nকোন দেশের number?\nদেশের code দিন (যেমন: `95` Myanmar, `51` Peru, `93` Afghanistan)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_add_num")]]))
        context.user_data["waiting_country_for_add"] = True

    elif data == "admin_numlist":
        if user_id != ADMIN_ID:
            return
        assigned_nums = {v["number"] for v in user_numbers.values()}
        text = "📋 *Number List*\n\n"
        for s in SERVICES:
            emoji = SERVICE_EMOJI[s]
            countries = numbers_pool[s]
            if not countries:
                continue
            text += f"{emoji} *{s}*\n"
            for cc, nums in countries.items():
                flag = COUNTRY_FLAGS.get(cc, "🌍")
                name = get_country_name(cc)
                free = sum(1 for n in nums if n not in assigned_nums)
                text += f"  {flag} {name}: {len(nums)} total | 🟢 {free}\n"
            text += "\n"
        await safe_edit(query, text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_broadcast":
        if user_id != ADMIN_ID:
            return
        context.user_data["broadcast_mode"] = True
        await safe_edit(query, f"📢 *Broadcast*\n{len(all_users)} জন user কে message যাবে। এখন পাঠান:")

    elif data == "admin_test":
        if user_id != ADMIN_ID:
            return
        await safe_edit(query, "🧪 API test করছি...")
        rows = fetch_all_recent_otps()
        if rows:
            await context.bot.send_message(user_id, f"✅ API কাজ করছে!\n📊 {len(rows)}টি SMS।")
        else:
            await context.bot.send_message(user_id, "❌ API কাজ করছে না!")

    elif data == "admin_upload":
        if user_id != ADMIN_ID:
            return
        buttons = [[InlineKeyboardButton(f"{SERVICE_EMOJI[s]} {s}", callback_data=f"upload_{s}")] for s in SERVICES]
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
        await safe_edit(query, "📤 কোন service এর জন্য file upload করবেন?", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("upload_"):
        if user_id != ADMIN_ID:
            return
        service = data.replace("upload_", "")
        context.user_data["upload_service"] = service
        await safe_edit(query,
            f"📤 *{SERVICE_EMOJI.get(service,'')} {service}*\n\nকোন দেশের number?\nদেশের code দিন (যেমন: `95` Myanmar, `51` Peru):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_upload")]]))
        context.user_data["waiting_country_for_upload"] = True

    elif data == "admin_clear":
        if user_id != ADMIN_ID:
            return
        buttons = [[InlineKeyboardButton(f"{SERVICE_EMOJI[s]} {s}", callback_data=f"clear_{s}")] for s in SERVICES]
        buttons.append([InlineKeyboardButton("🗑 সব clear", callback_data="clear_ALL")])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
        await safe_edit(query, "🗑 কোনটা clear করবেন?", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("clear_"):
        if user_id != ADMIN_ID:
            return
        target = data.replace("clear_", "")
        if target == "ALL":
            for s in SERVICES:
                numbers_pool[s].clear()
            user_numbers.clear()
            save_numbers()
            save_data()
            await safe_edit(query, "✅ সব clear!")
        elif target in SERVICES:
            numbers_pool[target].clear()
            save_numbers()
            await safe_edit(query, f"✅ *{target}* clear!")

    elif data == "admin_ban_menu":
        if user_id != ADMIN_ID:
            return
        await safe_edit(query, "🚫 *Ban/Unban*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Ban", callback_data="admin_ban"),
                 InlineKeyboardButton("✅ Unban", callback_data="admin_unban")],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_back")],
            ]))

    elif data == "admin_ban":
        if user_id != ADMIN_ID:
            return
        context.user_data["ban_mode"] = True
        await context.bot.send_message(user_id, "🚫 Ban করতে User ID পাঠান:")

    elif data == "admin_unban":
        if user_id != ADMIN_ID:
            return
        context.user_data["unban_mode"] = True
        await context.bot.send_message(user_id, "✅ Unban করতে User ID পাঠান:")

    elif data == "admin_back":
        if user_id != ADMIN_ID:
            return
        stats = service_stats()
        total_otp = sum(len(v) for v in otp_history.values())
        text = f"👑 *Admin Panel*\n\n👥 Users: {len(all_users)} | 🚫 Banned: {len(banned_users)}\n📨 Total OTP: {total_otp}\n\n*📦 Number Pool:*\n"
        for s in SERVICES:
            st = stats[s]
            emoji = SERVICE_EMOJI[s]
            text += f"{emoji} {s}: {st['total']} | 🟢 {st['available']} | 🔴 {st['busy']}\n"
        await safe_edit(query, text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 User List", callback_data="admin_users"),
                 InlineKeyboardButton("📊 OTP Stats", callback_data="admin_otp_stats")],
                [InlineKeyboardButton("➕ Number যোগ", callback_data="admin_add_num"),
                 InlineKeyboardButton("📋 Number List", callback_data="admin_numlist")],
                [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                 InlineKeyboardButton("🧪 Test API", callback_data="admin_test")],
                [InlineKeyboardButton("🔴 Live OTP", callback_data="admin_live_otp"),
                 InlineKeyboardButton("📤 File Upload", callback_data="admin_upload")],
                [InlineKeyboardButton("🗑 Clear", callback_data="admin_clear"),
                 InlineKeyboardButton("🚫 Ban/Unban", callback_data="admin_ban_menu")],
            ])
        )

# ─── File Upload ──────────────────────────────────────────────────

async def upload_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.document:
        return

    # Country code waiting
    if context.user_data.get("waiting_country_for_upload"):
        await update.message.reply_text("❌ আগে দেশের code দিন, তারপর file পাঠান।")
        return

    service = context.user_data.pop("upload_service", None)
    country_code = context.user_data.pop("upload_country", None)

    if not service or not country_code:
        buttons = [[InlineKeyboardButton(f"{SERVICE_EMOJI[s]} {s}", callback_data=f"upload_{s}")] for s in SERVICES]
        await update.message.reply_text("❓ আগে Admin Panel → File Upload → Service এবং দেশ select করুন।",
            reply_markup=InlineKeyboardMarkup(buttons))
        return

    doc = update.message.document
    file = await doc.get_file()
    content = await file.download_as_bytearray()
    text = content.decode("utf-8", errors="ignore")
    tokens = re.split(r'[\s,;]+', text)
    added = []
    for token in tokens:
        token = token.strip().replace("+", "")
        if token.isdigit() and 8 <= len(token) <= 15:
            if country_code not in numbers_pool[service]:
                numbers_pool[service][country_code] = []
            if token not in numbers_pool[service][country_code]:
                numbers_pool[service][country_code].append(token)
                added.append(token)
    save_numbers()
    flag = COUNTRY_FLAGS.get(country_code, "🌍")
    name = get_country_name(country_code)
    await update.message.reply_text(
        f"✅ *{SERVICE_EMOJI.get(service,'')} {service}* → *{flag} {name}* এ *{len(added)}টি* number যোগ!\n📦 Total: {len(numbers_pool[service].get(country_code, []))}",
        parse_mode="Markdown"
    )

async def handle_country_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Country code input handler — upload এবং add number দুইটার জন্য"""
    if update.effective_user.id != ADMIN_ID:
        return
    text = update.message.text.strip()

    if context.user_data.get("waiting_country_for_upload"):
        context.user_data["waiting_country_for_upload"] = False
        service = context.user_data.get("upload_service", "")
        flag = COUNTRY_FLAGS.get(text, "🌍")
        name = get_country_name(text)
        context.user_data["upload_country"] = text
        await update.message.reply_text(
            f"✅ দেশ: *{flag} {name}*\n\nএখন *{SERVICE_EMOJI.get(service,'')} {service}* এর জন্য TXT/CSV file পাঠান।",
            parse_mode="Markdown"
        )
        return

    if context.user_data.get("waiting_country_for_add"):
        context.user_data["waiting_country_for_add"] = False
        service = context.user_data.pop("pending_add_service", "")
        flag = COUNTRY_FLAGS.get(text, "🌍")
        name = get_country_name(text)
        context.user_data["add_number_mode"] = (service, text)
        await update.message.reply_text(
            f"✅ দেশ: *{flag} {name}*\n\nএখন number গুলো পাঠান (space বা comma দিয়ে):",
            parse_mode="Markdown"
        )
        return

# ─── Main ─────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Starting Bot...")
    load_numbers()
    load_data()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, upload_numbers))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.job_queue.run_repeating(poll_otps, interval=10, first=5)
    logger.info("✅ Bot running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
