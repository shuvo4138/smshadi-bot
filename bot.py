import logging
import re
import random
import requests
import os
import json
import asyncio
import psycopg2
import psycopg2.extras
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
MAIN_CHANNEL_LINK = "https://t.me/alwaysrvice24hours"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# CR API Configuration
CR_API_URL = "http://147.135.212.197/crapi/had/viewstats"
CR_API_TOKEN = os.getenv("CR_API_TOKEN", "SVJWSTRSQn6HYmlIa19oRmGQZYNjZWuKXlGHWoZOV3mGbmFVV3B5").strip()

# iVAS Configuration
IVAS_SMS_URL = "https://www.ivasms.com/portal/live/my_sms"
IVAS_COOKIES_FILE = os.getenv("IVAS_COOKIES_FILE", "ivas_cookies.json")

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

# ─── PostgreSQL DB ─────────────────────────────────────────────────────────

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS numbers_pool (
                pool_key TEXT NOT NULL,
                number TEXT NOT NULL,
                PRIMARY KEY (pool_key, number)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                joined TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id TEXT PRIMARY KEY,
                number TEXT,
                pool_key TEXT,
                assigned_time TEXT
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ DB initialized")
    except Exception as e:
        logger.error(f"DB init error: {e}")

def db_get_numbers_pool():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT pool_key, number FROM numbers_pool")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        pool = {}
        for pool_key, number in rows:
            if pool_key not in pool:
                pool[pool_key] = []
            pool[pool_key].append(number)
        return pool
    except Exception as e:
        logger.error(f"db_get_numbers_pool error: {e}")
        return {}

def db_add_numbers(pool_key, numbers):
    try:
        conn = get_db()
        cur = conn.cursor()
        added = 0
        skipped = 0
        for number in numbers:
            try:
                cur.execute(
                    "INSERT INTO numbers_pool (pool_key, number) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (pool_key, number)
                )
                if cur.rowcount > 0:
                    added += 1
                else:
                    skipped += 1
            except:
                skipped += 1
        conn.commit()
        cur.close()
        conn.close()
        return added, skipped
    except Exception as e:
        logger.error(f"db_add_numbers error: {e}")
        return 0, 0

def db_remove_number(pool_key, number):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM numbers_pool WHERE pool_key=%s AND number=%s", (pool_key, number))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"db_remove_number error: {e}")

def db_count_numbers(pool_key):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM numbers_pool WHERE pool_key=%s", (pool_key,))
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count
    except:
        return 0

def db_add_user(user_id, username):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (user_id, username, joined) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (str(user_id), username, datetime.now().isoformat())
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"db_add_user error: {e}")

def db_get_all_users():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [r[0] for r in rows]
    except:
        return []

def db_get_user_count():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count
    except:
        return 0

def db_set_session(user_id, number, pool_key):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_sessions (user_id, number, pool_key, assigned_time)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
            SET number=EXCLUDED.number, pool_key=EXCLUDED.pool_key, assigned_time=EXCLUDED.assigned_time
        """, (str(user_id), number, pool_key, datetime.now().isoformat()))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"db_set_session error: {e}")

def db_get_session(user_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT number, pool_key FROM user_sessions WHERE user_id=%s", (str(user_id),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {"number": row[0], "pool_key": row[1]}
        return None
    except:
        return None

def db_get_active_sessions_count():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM user_sessions")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count
    except:
        return 0

# ─── Helper Functions ──────────────────────────────────────────────────────

def parse_pool_key(pool_key):
    parts = pool_key.split("_")
    code = parts[0]
    if len(parts) >= 2:
        slot = parts[1].upper()
        return code, slot
    return code, ""

def get_button_label(pool_key):
    code, slot = parse_pool_key(pool_key)
    flag = COUNTRY_FLAGS.get(code, "🌍")
    name = COUNTRY_NAMES.get(code, code)
    if slot:
        return f"{flag} {name} Facebook {slot}"
    return f"{flag} {name} Facebook"

def extract_otp(message):
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
    for length in [3, 2, 1]:
        code = number[:length]
        if code in COUNTRY_NAMES:
            return code
    return "Unknown"

def hide_number(number):
    if len(number) <= 5:
        return number
    return number[:-5] + "★★" + number[-3:]

# ─── CR API ────────────────────────────────────────────────────────────────

def fetch_cr_api_otps():
    try:
        now = datetime.now()
        dt2 = now.strftime("%Y-%m-%d %H:%M:%S")
        dt1 = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        params = {"token": CR_API_TOKEN, "dt1": dt1, "dt2": dt2, "records": 200}
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

# ─── iVAS SMS Fetch ────────────────────────────────────────────────────────

def load_ivas_cookies():
    try:
        if not os.path.exists(IVAS_COOKIES_FILE):
            logger.warning(f"iVAS cookies file not found: {IVAS_COOKIES_FILE}")
            return None
        with open(IVAS_COOKIES_FILE, "r") as f:
            cookies_list = json.load(f)
        cookies = {}
        for c in cookies_list:
            cookies[c["name"]] = c["value"]
        return cookies
    except Exception as e:
        logger.error(f"load_ivas_cookies error: {e}")
        return None

def fetch_ivas_otps():
    try:
        cookies = load_ivas_cookies()
        if not cookies:
            return []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": IVAS_SMS_URL,
        }
        r = requests.get(IVAS_SMS_URL, cookies=cookies, headers=headers, timeout=15)
        if r.status_code != 200:
            logger.warning(f"iVAS fetch status: {r.status_code}")
            return []
        if "login" in r.url.lower():
            logger.warning("iVAS cookie expired! Please update ivas_cookies.json")
            return []
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        rows = soup.select("table tbody tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 5:
                number = cols[0].get_text(strip=True)
                sid = cols[1].get_text(strip=True)
                message = cols[4].get_text(strip=True)
                if number and message:
                    results.append({
                        "num": number.lstrip("+"),
                        "message": message,
                        "dt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "sid": sid,
                        "source": "iVAS"
                    })
        return results
    except Exception as e:
        logger.error(f"fetch_ivas_otps error: {e}")
        return []

async def poll_otps(context):
    try:
        # ── CR API OTPs ──
        otps = fetch_cr_api_otps()
        for otp_data in otps:
            try:
                number = otp_data.get("num", "").strip()
                message = otp_data.get("message", "").strip()
                dt = otp_data.get("dt", "").strip()
                otp_code = extract_otp(message)
                if not number or not otp_code or not dt:
                    continue
                cache_key = f"hadi:{number}:{otp_code}:{dt}"
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
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🤖 Number Bot", url="https://t.me/pc_clonev1_bot"),
                    InlineKeyboardButton("📢 Our Channel", url=MAIN_CHANNEL_LINK)
                ]])
                await context.bot.send_message(
                    chat_id=OTP_CHANNEL_ID,
                    text=msg,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Error processing CR OTP: {e}")
                continue

        # ── iVAS OTPs ──
        ivas_otps = fetch_ivas_otps()
        for otp_data in ivas_otps:
            try:
                number = otp_data.get("num", "").strip()
                message = otp_data.get("message", "").strip()
                dt = otp_data.get("dt", "").strip()
                sid = otp_data.get("sid", "").strip()
                otp_code = extract_otp(message)
                if not number or not otp_code:
                    continue
                cache_key = f"ivas:{number}:{otp_code}:{sid}"
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
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🤖 Number Bot", url="https://t.me/pc_clonev1_bot"),
                    InlineKeyboardButton("📢 Our Channel", url=MAIN_CHANNEL_LINK)
                ]])
                await context.bot.send_message(
                    chat_id=OTP_CHANNEL_ID,
                    text=msg,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Error processing iVAS OTP: {e}")
                continue

    except Exception as e:
        logger.error(f"Poll OTPs Error: {e}")

# ─── Telegram Handlers ─────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check if new or returning user
    existing_users = db_get_all_users()
    is_new = str(user.id) not in existing_users
    
    db_add_user(user.id, user.username or user.first_name)
    
    buttons = [[KeyboardButton("📲 Get Number"), KeyboardButton("📋 Active Numbers")]]
    if user.id == ADMIN_ID:
        buttons.append([KeyboardButton("👑 Admin Panel")])
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)
    
    if is_new:
        # New user - slow animated welcome
        loading_msg = await update.message.reply_text("⏳")
        await asyncio.sleep(0.8)
        await loading_msg.edit_text("🔄 Initializing...")
        await asyncio.sleep(0.8)
        await loading_msg.edit_text("✅ Account Created!")
        await asyncio.sleep(0.6)
        await loading_msg.delete()
        
        await update.message.reply_text(
            f"🎉 *Welcome to NUMBER PANEL NGN!*\n\n"
            f"👋 হ্যালো {user.first_name}! তুমি নতুন member!\n\n"
            f"📲 Get Number — Facebook number নাও\n"
            f"📋 Active Numbers — তোমার active number দেখো\n\n"
            f"🚀 শুরু করো!",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        # Returning user
        loading_msg = await update.message.reply_text("🔄 Loading...")
        await asyncio.sleep(0.7)
        await loading_msg.delete()
        
        await update.message.reply_text(
            f"👋 *Welcome Back, {user.first_name}!*\n\n"
            f"🤖 NUMBER PANEL NGN — Ready!",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

async def reply_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "📲 Get Number":
        pool = db_get_numbers_pool()
        if not pool:
            await update.message.reply_text("❌ No numbers available yet!")
            return
        buttons = []
        for pool_key in sorted(pool.keys()):
            label = get_button_label(pool_key)
            buttons.append(InlineKeyboardButton(label, callback_data=f"getcountry:{pool_key}"))
        keyboard = InlineKeyboardMarkup([[btn] for btn in buttons])
        await update.message.reply_text(
            "🌍 *Select Country for Facebook:*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    elif text == "📋 Active Numbers":
        session = db_get_session(user_id)
        msg = "📱 *Your Active Numbers:*\n\n"
        if session:
            number = session.get("number", "")
            pool_key = session.get("pool_key", "")
            label = get_button_label(pool_key)
            msg += f"📘 {label}\n📱 `{number}`"
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
        await update.message.reply_text("👑 *Admin Panel*", parse_mode="Markdown", reply_markup=keyboard)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("getcountry:"):
        pool_key = data.split(":", 1)[1]
        pool = db_get_numbers_pool()
        numbers = pool.get(pool_key, [])
        if not numbers:
            await query.answer("❌ No numbers available")
            return
        number = random.choice(numbers)
        db_set_session(user_id, number, pool_key)
        label = get_button_label(pool_key)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change Number", callback_data=f"change:{pool_key}")],
            [InlineKeyboardButton("🌍 Change Country", callback_data="changecountry")],
            [InlineKeyboardButton("📱 OTP Group", url=OTP_CHANNEL_LINK)],
        ])
        await query.edit_message_text(
            f"✅ *Number Successfully Reserved!*\n\n"
            f"📘 {label}\n"
            f"📱 Number: `{number}`\n\n"
            f"⏰ Valid for 10 minutes\n"
            f"⏳ Waiting for SMS...",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    elif data.startswith("change:"):
        pool_key = data.split(":", 1)[1]
        pool = db_get_numbers_pool()
        numbers = pool.get(pool_key, [])
        if not numbers:
            await query.answer("❌ No numbers available")
            return
        # Remove old number
        session = db_get_session(user_id)
        if session and session.get("number"):
            db_remove_number(pool_key, session["number"])
            pool = db_get_numbers_pool()
            numbers = pool.get(pool_key, [])
            if not numbers:
                await query.answer("❌ No more numbers available")
                return
        number = random.choice(numbers)
        db_set_session(user_id, number, pool_key)
        label = get_button_label(pool_key)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Change Number", callback_data=f"change:{pool_key}")],
            [InlineKeyboardButton("🌍 Change Country", callback_data="changecountry")],
            [InlineKeyboardButton("📱 OTP Group", url=OTP_CHANNEL_LINK)],
        ])
        await query.edit_message_text(
            f"✅ *Number Changed!*\n\n"
            f"📘 {label}\n"
            f"📱 New Number: `{number}`\n\n"
            f"⏰ Valid for 10 minutes\n"
            f"⏳ Waiting for SMS...",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    elif data == "changecountry":
        pool = db_get_numbers_pool()
        if not pool:
            await query.answer("❌ No countries available")
            return
        buttons = []
        for pool_key in sorted(pool.keys()):
            label = get_button_label(pool_key)
            buttons.append(InlineKeyboardButton(label, callback_data=f"getcountry:{pool_key}"))
        keyboard = InlineKeyboardMarkup([[btn] for btn in buttons])
        await query.edit_message_text(
            "🌍 *Select Country for Facebook:*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    elif data.startswith("admin_"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Admin only!")
            return
        action = data.split("_")[1]

        if action == "stats":
            pool = db_get_numbers_pool()
            total_numbers = sum(len(v) for v in pool.values())
            total_users = db_get_user_count()
            active_sessions = db_get_active_sessions_count()
            await query.edit_message_text(
                f"📊 *Statistics*\n\n"
                f"👥 Total Users: `{total_users}`\n"
                f"📱 Total Numbers: `{total_numbers}`\n"
                f"🌍 Pools: `{len(pool)}`\n"
                f"📡 Active Sessions: `{active_sessions}`",
                parse_mode="Markdown"
            )

        elif action == "addnumbers":
            await query.edit_message_text(
                "📝 *Send numbers.txt file*\n\n"
                "📌 Format: `91.txt` or `91_s2.txt`\n"
                "📌 Content: One number per line"
            )

        elif action == "broadcast":
            context.bot_data["pending_broadcast"] = True
            await query.edit_message_text(
                "📢 *Broadcast*\n\n"
                "এখন যে message পাঠাবে সেটা সব user কে send হবে।\n"
                "পাঠাও:"
            )

        elif action == "analytics":
            await query.edit_message_text("📈 *Analytics*\n\nComing soon...")

        elif action == "delete":
            await query.edit_message_text("🗑️ *Delete Numbers*\n\nComing soon...")

        elif action == "settings":
            await query.edit_message_text("⚙️ *Settings*\n\nComing soon...")

async def update_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    context.bot_data["waiting_cookie"] = True
    await update.message.reply_text(
        "🍪 *Cookie Update Mode*\n\n"
        "Cookie Editor থেকে JSON export করে এখানে paste করুন:\n\n"
        "_(Chrome → iVAS portal → Cookie Editor → Export → Copy)_",
        parse_mode="Markdown"
    )

async def handle_cookie_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.bot_data.get("waiting_cookie"):
        return
    try:
        text = update.message.text.strip()
        cookies = json.loads(text)
        with open(IVAS_COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=2)
        context.bot_data["waiting_cookie"] = False
        await update.message.reply_text(
            f"✅ *Cookie Updated!*\n\n"
            f"🍪 {len(cookies)} ta cookie save hoyeche.\n"
            f"✅ iVAS panel er sathe connection restore hoyeche!",
            parse_mode="Markdown"
        )
        logger.info("iVAS cookies updated via Telegram!")
    except json.JSONDecodeError:
        await update.message.reply_text(
            "❌ *Invalid JSON!*\n\nCookie Editor থেকে সঠিকভাবে export করুন।",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if context.bot_data.get("waiting_cookie"):
        await handle_cookie_input(update, context)
        return
    if not context.bot_data.get("pending_broadcast"):
        return
    context.bot_data["pending_broadcast"] = False
    broadcast_text = update.message.text
    user_ids = db_get_all_users()
    success = 0
    failed = 0
    await update.message.reply_text(f"📢 Broadcasting to {len(user_ids)} users...")
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=int(uid), text=broadcast_text)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"✅ *Broadcast Done!*\n\n✅ Sent: `{success}`\n❌ Failed: `{failed}`",
        parse_mode="Markdown"
    )

async def handle_txt_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    file = await update.message.document.get_file()
    content = await file.download_as_bytearray()
    text = content.decode('utf-8', errors='ignore')
    filename = update.message.document.file_name
    country_match = re.match(r'(\d+(?:_s\d+)?)', filename, re.IGNORECASE)
    if not country_match:
        await update.message.reply_text(
            "❌ *Invalid filename!*\n\nFormat: `91.txt` or `91_s2.txt`",
            parse_mode="Markdown"
        )
        return
    pool_key = country_match.group(1).lower()
    numbers = []
    for line in text.split('\n'):
        number = line.strip().lstrip('+')
        if number and len(number) >= 7:
            numbers.append(number)
    added, skipped = db_add_numbers(pool_key, numbers)
    total = db_count_numbers(pool_key)
    label = get_button_label(pool_key)
    await update.message.reply_text(
        f"✅ *Upload Complete!*\n\n"
        f"🌍 Pool: *{label}*\n"
        f"✅ Added: `{added}` numbers\n"
        f"⏭ Skipped: `{skipped}`\n"
        f"📱 Total: `{total}`",
        parse_mode="Markdown"
    )

# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Starting NUMBER PANEL NGN Bot...")
    init_db()

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
    app.add_handler(CommandHandler("updatecookie", update_cookie))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), handle_txt_file))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'^(📲 Get Number|📋 Active Numbers|👑 Admin Panel)$'),
        reply_keyboard_handler
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.User(ADMIN_ID) & ~filters.COMMAND,
        handle_broadcast
    ))
    app.job_queue.run_repeating(poll_otps, interval=5, first=2)
    logger.info("✅ NUMBER PANEL NGN running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
