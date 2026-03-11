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
PANEL_API_URL = "http://185.2.83.39/ints/agent/res/data_smscdr.php"
PANEL_SESSKEY = os.getenv("PANEL_SESSKEY", "Q05RR0FRUEJCUA==").strip()
PANEL_PHPSESSID = os.getenv("PANEL_PHPSESSID", "2u2ke8d4vgjr2d6tpqujpr98c7").strip()
NUMBERS_FILE = "numbers.json"
DATA_FILE = "bot_data.json"
STATS_FILE = "bot_stats.json"

# Stats tracking
bot_stats = {
    "total_otps_received": 0,
    "total_otps_delivered": 0,
    "total_users": 0,
    "active_numbers": 0,
    "last_otp_time": None,
    "last_otp_number": None,
    "last_otp_service": None,
    "uptime_start": datetime.now().isoformat(),
}

def save_stats():
    try:
        with open(STATS_FILE, "w") as f:
            json.dump(bot_stats, f, indent=2)
    except Exception as e:
        logger.error(f"Save stats error: {e}")

def load_stats():
    global bot_stats
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, "r") as f:
                bot_stats = json.load(f)
            logger.info("✅ Stats loaded")
    except Exception as e:
        logger.warning(f"Stats load error: {e}")

def fetch_all_recent_otps():
    """Fetch recent OTPs from CR API using token — no login needed"""
    try:
        now = datetime.now()
        dt1 = now.strftime("%Y-%m-%d 00:00:00")
        dt2 = now.strftime("%Y-%m-%d 23:59:59")
        resp = requests.get(
            "http://147.135.212.197/crapi/had/viewstats",
            params={
                "token": os.getenv("CR_API_TOKEN", "RlNYRjRSQkNrTnBXeISLioBgdlNXlmVpVHGBQ2KKckaBcmJUglFs"),
                "dt1": dt1,
                "dt2": dt2,
                "records": 200,
            },
            timeout=10
        )
        if resp.status_code != 200:
            logger.error(f"CR API HTTP: {resp.status_code}")
            return []
        data = resp.json()
        if data.get("status") != "success":
            logger.error(f"CR API error: {data}")
            return []
        rows = data.get("data", [])
        logger.info(f"📡 CR API: {len(rows)} rows")
        result = []
        for row in rows:
            result.append({
                "dt":      str(row.get("dt", "")).strip(),
                "num":     str(row.get("num", "")).strip().lstrip("+"),
                "cli":     str(row.get("cli", "")).strip().upper(),
                "message": str(row.get("message", "")).strip(),
            })
        return result
    except Exception as e:
        logger.error(f"CR API fetch error: {e}")
        return []

def fetch_otp_for_number(number: str):
    """Fetch OTP for specific number from CR API"""
    try:
        clean_num = number.lstrip("+").strip()
        resp = requests.get(
            CR_API_URL,
            params={"token": CR_API_TOKEN, "filternum": clean_num, "records": 10},
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
        logger.error(f"fetch_otp error: {e}")
    return None

# Services configuration
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
    "221": "🇸🇳", "222": "🇲🇷", "223": "🇲🇱", "224": "🇬🇳", "225": "🇨🇮", "226": "🇧🇫", "227": "🇳🇪", "228": "🇹🇬", "229": "🇧🇯", "230": "🇲🇺",
    "231": "🇱🇷", "232": "🇸🇱", "233": "🇬🇭", "234": "🇳🇬", "235": "🇹🇩", "236": "🇨🇫", "237": "🇨🇲", "238": "🇨🇻", "239": "🇸🇹", "240": "🇬🇶",
    "241": "🇬🇦", "242": "🇨🇬", "243": "🇨🇩", "244": "🇦🇴", "245": "🇬🇼", "246": "🇩🇿", "248": "🇸🇨", "249": "🇸🇩", "250": "🇺🇬", "251": "🇪🇹",
    "252": "🇸🇴", "253": "🇩🇿", "254": "🇰🇪", "255": "🇹🇿", "256": "🇺🇬", "257": "🇧🇮", "258": "🇲🇿", "260": "🇿🇲", "261": "🇲🇬", "262": "🇷🇪",
    "263": "🇿🇼", "264": "🇳🇦", "265": "🇲🇼", "266": "🇱🇸", "267": "🇧🇼", "268": "🇪🇿", "290": "🇸🇭", "291": "🇪🇷", "297": "🇦🇼", "298": "🇫🇴",
    "299": "🇬🇱", "350": "🇬🇮", "351": "🇵🇹", "352": "🇱🇺", "353": "🇮🇪", "354": "🇮🇸", "355": "🇦🇱", "356": "🇲🇹", "357": "🇨🇾", "358": "🇫🇮",
    "359": "🇧🇬", "370": "🇱🇹", "371": "🇱🇻", "372": "🇪🇪", "373": "🇲🇩", "374": "🇦🇲", "375": "🇧🇾", "376": "🇦🇩", "377": "🇲🇨", "378": "🇸🇲",
    "380": "🇺🇦", "381": "🇷🇸", "382": "🇲🇪", "383": "🇽🇰", "385": "🇭🇷", "386": "🇸🇮", "387": "🇧🇦", "389": "🇲🇰", "420": "🇨🇿", "421": "🇸🇰",
    "423": "🇱🇮", "500": "🇫🇰", "501": "🇧🇿", "502": "🇬🇹", "503": "🇸🇻", "504": "🇭🇳", "505": "🇳🇮", "506": "🇨🇷", "507": "🇵🇦", "508": "🇵🇲",
    "509": "🇭🇹", "590": "🇬🇵", "591": "🇧🇴", "592": "🇬🇾", "593": "🇪🇨", "594": "🇬🇫", "595": "🇵🇾", "596": "🇲🇶", "597": "🇸🇷", "598": "🇺🇾",
    "599": "🇧🇶", "670": "🇲🇵", "672": "🇳🇺", "673": "🇧🇳", "674": "🇳🇷", "675": "🇵🇬", "676": "🇹🇴", "677": "🇸🇧", "678": "🇻🇺", "679": "🇫🇯",
    "680": "🇵🇼", "681": "🇼🇫", "682": "🇨🇰", "683": "🇳🇺", "684": "🇦🇸", "685": "🇼🇸", "686": "🇰🇮", "687": "🇳🇨", "688": "🇹🇻", "689": "🇵🇫",
    "690": "🇹🇰", "691": "🇫🇲", "692": "🇲🇭", "850": "🇰🇵", "852": "🇭🇰", "853": "🇲🇴", "855": "🇰🇭", "856": "🇱🇦", "880": "🇧🇩", "886": "🇹🇼",
    "888": "🌍", "960": "🇲🇻", "961": "🇱🇧", "962": "🇯🇴", "963": "🇸🇾", "964": "🇮🇶", "965": "🇰🇼", "966": "🇸🇦", "967": "🇾🇪", "968": "🇴🇲",
    "970": "🇵🇸", "971": "🇦🇪", "972": "🇮🇱", "973": "🇧🇭", "974": "🇶🇦", "975": "🇧🇹", "976": "🇲🇳", "977": "🇳🇵", "992": "🇹🇯", "993": "🇹🇲",
    "994": "🇦🇿", "995": "🇬🇪", "996": "🇰🇬", "998": "🇺🇿",
}

COUNTRY_NAMES = {
    "1": "USA", "7": "Russia", "20": "Egypt", "27": "South Africa", "30": "Greece", "31": "Netherlands", "32": "Belgium", "33": "France", "34": "Spain", "36": "Hungary",
    "39": "Italy", "40": "Romania", "41": "Switzerland", "43": "Austria", "44": "UK", "45": "Denmark", "46": "Sweden", "47": "Norway", "48": "Poland", "49": "Germany",
    "51": "Peru", "52": "Mexico", "53": "Cuba", "54": "Argentina", "55": "Brazil", "56": "Chile", "57": "Colombia", "58": "Venezuela", "60": "Malaysia", "61": "Australia",
    "62": "Indonesia", "63": "Philippines", "64": "New Zealand", "65": "Singapore", "66": "Thailand", "81": "Japan", "82": "South Korea", "84": "Vietnam", "86": "China", "90": "Turkey",
    "91": "India", "92": "Pakistan", "93": "Afghanistan", "94": "Sri Lanka", "95": "Myanmar", "959": "Myanmar", "98": "Iran", "212": "Morocco", "213": "Algeria", "216": "Tunisia",
    "220": "Senegal", "221": "Senegal", "222": "Mauritania", "223": "Mali", "224": "Guinea", "225": "Ivory Coast", "226": "Burkina Faso", "227": "Niger", "228": "Togo", "229": "Benin",
    "230": "Mauritius", "231": "Liberia", "232": "Sierra Leone", "233": "Ghana", "234": "Nigeria", "235": "Chad", "236": "Central Africa", "237": "Cameroon", "238": "Cape Verde", "239": "Sao Tome",
    "240": "Equatorial Guinea", "241": "Gabon", "242": "Congo", "243": "DRC", "244": "Angola", "245": "Guinea-Bissau", "246": "Algeria", "248": "Seychelles", "249": "Sudan", "250": "Uganda",
    "251": "Ethiopia", "252": "Somalia", "253": "Djibouti", "254": "Kenya", "255": "Tanzania", "256": "Uganda", "257": "Burundi", "258": "Mozambique", "261": "Madagascar", "262": "Reunion",
    "263": "Zimbabwe", "264": "Namibia", "265": "Malawi", "266": "Lesotho", "267": "Botswana", "268": "Eswatini", "290": "Saint Helena", "291": "Eritrea", "297": "Aruba", "298": "Faroe Islands",
    "299": "Greenland", "350": "Gibraltar", "351": "Portugal", "352": "Luxembourg", "353": "Ireland", "354": "Iceland", "355": "Albania", "356": "Malta", "357": "Cyprus", "358": "Finland",
    "359": "Bulgaria", "370": "Lithuania", "371": "Latvia", "372": "Estonia", "373": "Moldova", "374": "Armenia", "375": "Belarus", "376": "Andorra", "377": "Monaco", "378": "San Marino",
    "380": "Ukraine", "381": "Serbia", "382": "Montenegro", "383": "Kosovo", "385": "Croatia", "386": "Slovenia", "387": "Bosnia", "389": "Macedonia", "420": "Czech Republic", "421": "Slovakia",
    "423": "Liechtenstein", "500": "Falkland Islands", "501": "Belize", "502": "Guatemala", "503": "El Salvador", "504": "Honduras", "505": "Nicaragua", "506": "Costa Rica", "507": "Panama", "508": "Saint Pierre",
    "509": "Haiti", "590": "Guadeloupe", "591": "Bolivia", "592": "Guyana", "593": "Ecuador", "594": "French Guiana", "595": "Paraguay", "596": "Martinique", "597": "Suriname", "598": "Uruguay",
    "599": "Curacao", "670": "Northern Mariana", "672": "Norfolk Island", "673": "Brunei", "674": "Nauru", "675": "Papua New Guinea", "676": "Tonga", "677": "Solomon Islands", "678": "Vanuatu", "679": "Fiji",
    "680": "Palau", "681": "Wallis Futuna", "682": "Cook Islands", "683": "Niue", "684": "American Samoa", "685": "Samoa", "686": "Kiribati", "687": "New Caledonia", "688": "Tuvalu", "689": "French Polynesia",
    "690": "Tokelau", "691": "Micronesia", "692": "Marshall Islands", "850": "North Korea", "852": "Hong Kong", "853": "Macau", "855": "Cambodia", "856": "Laos", "880": "Bangladesh", "886": "Taiwan",
    "960": "Maldives", "961": "Lebanon", "962": "Jordan", "963": "Syria", "964": "Iraq", "965": "Kuwait", "966": "Saudi Arabia", "967": "Yemen", "968": "Oman", "970": "Palestine",
    "971": "UAE", "972": "Israel", "973": "Bahrain", "974": "Qatar", "975": "Bhutan", "976": "Mongolia", "977": "Nepal", "992": "Tajikistan", "993": "Turkmenistan", "994": "Azerbaijan",
    "995": "Georgia", "996": "Kyrgyzstan", "998": "Uzbekistan",
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
    """Get a free number — from pool first, then from API"""
    assigned = {v["number"].lstrip("+") for v in user_numbers.values()}
    
    # Try pool first
    nums = numbers_pool.get(service, {}).get(country_code, [])
    free = [n for n in nums if n.lstrip("+") not in assigned]
    if free:
        return random.choice(free)
    
    # Fallback: fetch from API and pick one not assigned
    try:
        rows = fetch_all_recent_otps()
        api_numbers = list({
            str(r.get("num", "")).strip().lstrip("+")
            for r in rows
            if str(r.get("num", "")).strip().lstrip("+").startswith(country_code)
        })
        free_api = [n for n in api_numbers if n not in assigned]
        if free_api:
            chosen = random.choice(free_api)
            # Save to pool for future use
            if country_code not in numbers_pool[service]:
                numbers_pool[service][country_code] = []
            full = f"+{chosen}"
            if full not in numbers_pool[service][country_code]:
                numbers_pool[service][country_code].append(full)
                save_numbers()
            return full
    except Exception as e:
        logger.error(f"API number fetch error: {e}")
    
    return None

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

def check_api_status():
    """Check if CR API is reachable"""
    try:
        resp = requests.get(
            "http://147.135.212.197/crapi/had/viewstats",
            params={"token": os.getenv("CR_API_TOKEN", "RlNYRjRSQkNrTnBXeISLioBgdlNXlmVpVHGBQ2KKckaBcmJUglFs"), "records": 1},
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("status") == "success"
        return False
    except:
        return False

def extract_captcha(html: str) -> tuple:
    """Extract CAPTCHA question from login page — 'What is 8 + 9 = ?'"""
    try:
        # Pattern: "What is 8 + 9 = ?"
        match = re.search(r'What is\s+(\d+)\s*\+\s*(\d+)\s*=', html, re.IGNORECASE)
        if match:
            return int(match.group(1)), int(match.group(2))
        # Fallback: any "X + Y" pattern
        match = re.search(r'(\d+)\s*\+\s*(\d+)', html)
        if match:
            return int(match.group(1)), int(match.group(2))
        logger.warning("⚠️ CAPTCHA pattern not found")
    except Exception as e:
        logger.error(f"CAPTCHA extract error: {e}")
    return None, None


def panel_login() -> bool:
    """Login to panel and update global PHPSESSID and sesskey"""
    global PANEL_PHPSESSID, PANEL_SESSKEY
    try:
        s = requests.Session()
        resp = s.get("http://185.2.83.39/ints/login", timeout=10)
        a, b = extract_captcha(resp.text)
        if a is None:
            logger.error("❌ CAPTCHA not found during login")
            return False

        captcha_answer = str(a + b)
        logger.info(f"🔢 CAPTCHA: {a}+{b}={captcha_answer}")

        login_resp = s.post(
            "http://185.2.83.39/ints/login",
            data={
                "username": DASHBOARD_USER,
                "password": DASHBOARD_PASS,
                "captcha": captcha_answer
            },
            timeout=10,
            allow_redirects=True
        )

        if "PHPSESSID" in s.cookies:
            PANEL_PHPSESSID = s.cookies["PHPSESSID"]
            # Extract sesskey from redirect URL or page
            sesskey_match = re.search(r'sesskey=([^&"\']+)', login_resp.url + login_resp.text)
            if sesskey_match:
                PANEL_SESSKEY = sesskey_match.group(1)
            logger.info(f"✅ Panel login OK! PHPSESSID={PANEL_PHPSESSID[:10]}...")
            return True
        else:
            logger.error("❌ Panel login failed")
            return False
    except Exception as e:
        logger.error(f"❌ Panel login error: {e}")
        return False

async def login_panel_admin(context, user_id: int):
    """Admin button handler — login panel and notify"""
    ok = panel_login()
    if ok:
        await context.bot.send_message(
            user_id,
            f"✅ *Panel login successful!*\n\n"
            f"🔑 PHPSESSID: `{PANEL_PHPSESSID}`\n"
            f"🗝 Sesskey: `{PANEL_SESSKEY}`\n\n"
            f"OTP fetch ready",
            parse_mode="Markdown"
        )
    else:
        try:
            resp = requests.get("http://185.2.83.39/ints/login", timeout=10)
            snippet = resp.text[:300]
            await context.bot.send_message(
                user_id,
                f"❌ *Panel login failed*\n\nHTTP: `{resp.status_code}`\nPreview:\n`{snippet[:200]}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            await context.bot.send_message(user_id, f"❌ Panel login failed\nError: `{e}`", parse_mode="Markdown")
    return ok

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
        [InlineKeyboardButton("🔐 Login Panel", callback_data="admin_login_panel")],
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📤 Upload Numbers", callback_data="admin_upload"),
         InlineKeyboardButton("🗑 Delete Numbers", callback_data="admin_delete_menu")],
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
    """Fetch OTPs from Panel and forward to channel + user inbox"""
    global otp_cache

    rows = fetch_all_recent_otps()
    if not rows:
        return

    # Get all pool numbers
    all_numbers = set()
    for service in SERVICES:
        for country_nums in numbers_pool[service].values():
            all_numbers.update([n.lstrip("+").strip() for n in country_nums])

    if not all_numbers:
        logger.warning("⚠️ No numbers in pool")
        return

    # Build assigned map: number -> user_id
    assigned = {}
    for uid, info in user_numbers.items():
        n = str(info.get("number", "")).lstrip("+").strip()
        if n:
            assigned[n] = uid

    new_count = 0

    for row in rows:
        try:
            dt      = str(row.get("dt", "")).strip()
            number  = str(row.get("num", "")).strip().lstrip("+")
            cli     = str(row.get("cli", "Unknown")).strip().upper()
            message = str(row.get("message", "")).strip()

            if not number or not message:
                continue

            if number not in all_numbers:
                continue

            otp_code = extract_otp(message)
            if not otp_code:
                continue

            # Duplicate check
            cache_key = f"{number}:{otp_code}:{dt}"
            if cache_key in otp_cache:
                continue
            otp_cache[cache_key] = True

            # Cache cleanup
            if len(otp_cache) > 1000:
                for k in list(otp_cache.keys())[:300]:
                    del otp_cache[k]

            # Country info
            flag = get_flag(number)
            country_name = "Unknown"
            for code, name in COUNTRY_NAMES.items():
                if number.startswith(code):
                    country_name = name
                    break

            logger.info(f"🔔 NEW OTP! +{number} | {otp_code} | {cli}")
            new_count += 1
            
            # ✅ Update stats
            bot_stats["total_otps_received"] += 1
            bot_stats["last_otp_time"] = datetime.now().isoformat()
            bot_stats["last_otp_number"] = number
            bot_stats["last_otp_service"] = cli

            # ── CHANNEL (masked) ─────────────────────────────────
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

            await asyncio.sleep(0.3)

            # ── USER INBOX (full number) ──────────────────────────
            owner_id = assigned.get(number)
            if owner_id:
                inbox_msg = (
                    f"🔔 *New OTP*\n\n"
                    f"📱 App: {cli}\n"
                    f"🌎 Country: {country_name} {flag}\n"
                    f"📞 Number: `+{number}`\n"
                    f"🔑 OTP: `{otp_code}`\n"
                    f"🕐 {dt}"
                )
                try:
                    await context.bot.send_message(
                        chat_id=owner_id,
                        text=inbox_msg,
                        parse_mode="Markdown"
                    )
                    logger.info(f"✅ User {owner_id} notified")
                    bot_stats["total_otps_delivered"] += 1
                except Exception as e:
                    logger.error(f"❌ User {owner_id} error: {e}")

        except Exception as e:
            logger.error(f"❌ Poll error: {e}")

    if new_count > 0:
        logger.info(f"✅ Forwarded {new_count} OTPs ⚡")
    else:
        logger.debug(f"📊 {len(rows)} rows checked, no new OTPs")

# ─── Handlers ─────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    save_data()
    
    # Admin only - show admin panel
    if user.id == ADMIN_ID:
        await update.message.reply_text(
            f"👋 Welcome *Admin*!\n\n"
            f"🤖 *OTP PANEL BOT NGN*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_back")],
                [InlineKeyboardButton("📢 Channel Join করো", url=JOIN_CHANNEL)]
            ])
        )
    else:
        # Regular user
        await update.message.reply_text(
            f"👋 Welcome *{user.first_name}*!\n\n"
            f"🤖 *OTP PANEL BOT NGN*",
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
                    [InlineKeyboardButton("🔄 Change Number", callback_data="change_number_fast")],
                    [InlineKeyboardButton("↗️ OTP Channel", url=OTP_CHANNEL_LINK)],
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
            f"📱 Total Numbers: `{total_numbers}`",
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
        country_name = COUNTRY_NAMES.get(country, country)
        
        await query.edit_message_text(
            f"📱 *Your Number is Ready!*\n\n"
            f"`{num}`\n\n"
            f"✅ *Your number is active!*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Change Number", callback_data="get_number")],
                [InlineKeyboardButton("↗️ OTP Channel", url=OTP_CHANNEL_LINK)],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
            ])
        )
    
    elif data == "main_menu":
        await query.edit_message_text(
            f"👋 Welcome!\n\n"
            f"🤖 *OTP PANEL BOT NGN*\n\n"
            f"🔔 OTPs আসবে channel এ এবং তুমার inbox এ",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Channel Join করো", url=JOIN_CHANNEL)],
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_back")]
            ])
        )
    
    elif data == "change_number_fast":
        if user_id not in user_numbers:
            await query.answer("❌ No active number")
            return
        
        # Get current info
        current_info = user_numbers[user_id]
        service = current_info["service"]
        country = current_info["country"]
        
        # Get new number from same service/country
        new_num = get_available_number(service, country)
        if not new_num:
            await query.answer("❌ No more numbers available", show_alert=True)
            return
        
        # Update
        user_numbers[user_id] = {"number": new_num, "service": service, "country": country}
        save_data()
        
        flag = COUNTRY_FLAGS.get(country, "🌍")
        await query.edit_message_text(
            f"📱 *Your Number is Ready!*\n\n"
            f"`{new_num}`\n\n"
            f"✅ *Your number is active!*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Change Number", callback_data="change_number_fast")],
                [InlineKeyboardButton("↗️ OTP Channel", url=OTP_CHANNEL_LINK)],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
            ])
        )
    
    elif data == "release":
        if user_id in user_numbers:
            user_numbers.pop(user_id)
            save_data()
            await query.edit_message_text("✅ Number released", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📲 Get New", callback_data="get_number")]]))

    # ── Admin callbacks ──
    elif data == "admin_login_panel":
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        await query.answer("🔐 Logging in...")
        success = await login_panel_admin(context, user_id)
        if success:
            await query.edit_message_text(
                "✅ *Panel Login Successful!*\n\n🔑 OTP fetch ready",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
            )
        else:
            await query.edit_message_text(
                "❌ *Login Failed*\n\nCheck credentials and try again",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
            )
    
    elif data == "admin_stats":
        if user_id != ADMIN_ID:
            await query.answer("❌ Access denied", show_alert=True)
            return
        total_numbers = sum(len(nums) for s in SERVICES for nums in numbers_pool[s].values())
        
        # Check API status
        api_ok = check_api_status()
        api_status = "✅ Connected" if api_ok else "❌ Offline"
        
        await query.edit_message_text(
            f"📊 *Stats*\n\n"
            f"📡 API Status: {api_status}\n"
            f"📱 Total Numbers: `{total_numbers}`\n"
            f"👥 Total Users: `{len(all_users)}`\n"
            f"📞 Active: `{len(user_numbers)}`",
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

    elif data == "admin_stats":
        if query.from_user.id != ADMIN_ID:
            return
        
        # ✅ Calculate stats
        total_numbers = sum(
            len(nums)
            for s in SERVICES
            for nums in numbers_pool[s].values()
        )
        
        uptime = datetime.fromisoformat(bot_stats["uptime_start"])
        uptime_duration = datetime.now() - uptime
        hours = uptime_duration.seconds // 3600
        minutes = (uptime_duration.seconds % 3600) // 60
        
        stats_msg = (
            f"📊 *BOT STATISTICS*\n\n"
            f"👥 Total Users: `{len(all_users)}`\n"
            f"📱 Total Numbers: `{total_numbers}`\n"
            f"🔌 Active Assignments: `{len(user_numbers)}`\n\n"
            f"📈 *OTP Stats:*\n"
            f"✅ Received: `{bot_stats['total_otps_received']}`\n"
            f"📨 Delivered: `{bot_stats['total_otps_delivered']}`\n"
            f"🕐 Last OTP: `{bot_stats['last_otp_time']}`\n"
            f"📱 Last Number: `{bot_stats['last_otp_number']}`\n"
            f"🔑 Last Service: `{bot_stats['last_otp_service']}`\n\n"
            f"⏱️ *Uptime:*\n"
            f"`{hours}h {minutes}m`"
        )
        
        await query.edit_message_text(
            stats_msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_back")],
            ])
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
    if not update or not update.effective_user or not update.message:
        return
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

async def set_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setsession PHPSESSID [sesskey]"""
    global PANEL_PHPSESSID, PANEL_SESSKEY
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "📋 *Usage:*\n`/setsession PHPSESSID sesskey`\n\n"
            "Browser F12 → Application → Cookies থেকে নাও।",
            parse_mode="Markdown"
        )
        return
    PANEL_PHPSESSID = args[0].strip()
    if len(args) >= 2:
        PANEL_SESSKEY = args[1].strip()
    await update.message.reply_text(
        f"✅ *Session Updated!*\n\n"
        f"PHPSESSID: `{PANEL_PHPSESSID[:15]}...`",
        parse_mode="Markdown"
    )


def main():
    load_stats()
    logger.info("🚀 Starting bot...")
    load_numbers()
    load_data()

    # Auto login to panel on startup
    if panel_login():
        logger.info("✅ Panel login successful on startup")
    else:
        logger.warning("⚠️ Panel login failed, will retry during polling")

    # Preload cache so old OTPs don't resend on restart
    global otp_cache
    rows = fetch_all_recent_otps()
    for row in rows:
        try:
            number   = str(row.get("num", "")).strip().lstrip("+")
            message  = str(row.get("message", "")).strip()
            dt       = str(row.get("dt", "")).strip()
            otp_code = extract_otp(message)
            if number and otp_code and dt:
                otp_cache[f"{number}:{otp_code}:{dt}"] = True
        except:
            pass
    logger.info(f"✅ Preloaded {len(otp_cache)} OTPs into cache")
    logger.info("✅ Panel API ready")
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addnumbers", add_numbers_command))
    app.add_handler(CommandHandler("setsession", set_session_command))
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

    app.job_queue.run_repeating(poll_otps, interval=5, first=2)
    
    # Save stats periodically
    app.job_queue.run_repeating(lambda ctx: save_stats(), interval=60, first=1)
    logger.info("✅ Bot running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
