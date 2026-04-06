import logging
import re
import random
import requests
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.error import BadRequest

load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Environment Variables ─────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "1984916365").strip())
OTP_CHANNEL_ID = int(os.getenv("OTP_CHANNEL_ID", "-1002625886518").strip())
OTP_CHANNEL_LINK = os.getenv("OTP_CHANNEL_LINK", "https://t.me/+SWraCXOQrWM4Mzg9").strip()
JOIN_CHANNEL_USERNAME = os.getenv("JOIN_CHANNEL_USERNAME", "alwaysrvice24hours").strip()
JOIN_CHANNEL_LINK = f"https://t.me/{JOIN_CHANNEL_USERNAME}"
MAIN_CHANNEL_LINK = "https://t.me/alwaysrvice24hours"
STORAGE_CHANNEL_ID = int(os.getenv("STORAGE_CHANNEL_ID", "-1003671562242").strip())

# CR API
CR_API_URL = "http://147.135.212.197/crapi/had/viewstats"
CR_API_TOKEN = os.getenv("CR_API_TOKEN", "SVJWSTRSQn6HYmlIa19oRmGQZYNjZWuKXlGHWoZOV3mGbmFVV3B5").strip()

# ─── In-Memory Storage ─────────────────────────────────────────────────────
# { pool_key: message_id }  — Telegram channel এ কোন message এ আছে
pool_message_ids = {}

# { pool_key: [number1, number2, ...] }  — memory cache
numbers_pool = {}

# { user_id: { number, pool_key } }
user_sessions = {}

# { user_id: username }
users_db = {}

# OTP duplicate check
otp_cache = {}

# ─── Country Data ──────────────────────────────────────────────────────────
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

# ─── Telegram Storage Functions ────────────────────────────────────────────

async def tg_save_pool(bot, pool_key, numbers):
    """Save number list to Telegram storage channel"""
    global pool_message_ids
    text = f"POOL:{pool_key}\n" + "\n".join(numbers)
    try:
        if pool_key in pool_message_ids:
            # Edit existing message
            await bot.edit_message_text(
                chat_id=STORAGE_CHANNEL_ID,
                message_id=pool_message_ids[pool_key],
                text=text
            )
        else:
            # Send new message
            msg = await bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=text)
            pool_message_ids[pool_key] = msg.message_id
    except Exception as e:
        logger.error(f"tg_save_pool error [{pool_key}]: {e}")

async def tg_load_all_pools(bot):
    """Bot start এ storage channel থেকে সব pool load করো"""
    global numbers_pool, pool_message_ids
    try:
        # Channel এর recent messages scan করো
        # Bot এর নিজের পাঠানো messages খুঁজতে হবে
        # আমরা একটি index message রাখব যেখানে সব pool_key → message_id আছে
        # প্রথমে index message খুঁজি
        index_msg = await tg_get_index(bot)
        if not index_msg:
            logger.info("No pool index found in storage channel. Starting fresh.")
            return
        # index parse করো
        for line in index_msg.split("\n"):
            if ":" in line:
                parts = line.split(":", 1)
                pk = parts[0].strip()
                mid = parts[1].strip()
                if pk == "__users__" and mid.isdigit():
                    await tg_load_users(bot, int(mid))
                elif pk and mid.isdigit():
                    pool_message_ids[pk] = int(mid)
        # প্রতিটি message থেকে numbers load করো
        for pool_key, msg_id in pool_message_ids.items():
            try:
                msg = await bot.forward_message(
                    chat_id=STORAGE_CHANNEL_ID,
                    from_chat_id=STORAGE_CHANNEL_ID,
                    message_id=msg_id
                )
                # forward করা message delete করো, শুধু content নাও
                text = msg.text or ""
                await msg.delete()
                lines = text.split("\n")
                nums = [l.strip() for l in lines[1:] if l.strip()]
                numbers_pool[pool_key] = nums
                logger.info(f"✅ Loaded pool [{pool_key}]: {len(nums)} numbers")
            except Exception as e:
                logger.error(f"Load pool [{pool_key}] error: {e}")
    except Exception as e:
        logger.error(f"tg_load_all_pools error: {e}")

async def tg_get_index(bot):
    """Storage channel থেকে index message content পাও"""
    global pool_message_ids
    # Index message ID টা আমরা একটা fixed কিছুতে রাখব না
    # বরং channel এ "INDEX" দিয়ে শুরু হওয়া message খুঁজব
    # সহজ approach: bot data তে রাখা (restart এ হারিয়ে যাবে)
    # তাই আমরা channel এ একটা pinned message রাখব
    try:
        chat = await bot.get_chat(STORAGE_CHANNEL_ID)
        if chat.pinned_message and chat.pinned_message.text and chat.pinned_message.text.startswith("INDEX\n"):
            return chat.pinned_message.text[6:]  # "INDEX\n" সরিয়ে বাকিটা
    except Exception as e:
        logger.error(f"tg_get_index error: {e}")
    return None

async def tg_save_index(bot):
    """pool_message_ids + USERS_MSG_ID কে storage channel এ pinned message হিসেবে save করো"""
    try:
        lines = [f"{pk}:{mid}" for pk, mid in pool_message_ids.items()]
        if USERS_MSG_ID:
            lines.append(f"__users__:{USERS_MSG_ID}")
        text = "INDEX\n" + "\n".join(lines)
        chat = await bot.get_chat(STORAGE_CHANNEL_ID)
        if chat.pinned_message and chat.pinned_message.text and chat.pinned_message.text.startswith("INDEX"):
            await bot.edit_message_text(
                chat_id=STORAGE_CHANNEL_ID,
                message_id=chat.pinned_message.message_id,
                text=text
            )
        else:
            msg = await bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=text)
            await bot.pin_chat_message(chat_id=STORAGE_CHANNEL_ID, message_id=msg.message_id)
    except Exception as e:
        logger.error(f"tg_save_index error: {e}")

# ─── Pool Helper Functions ─────────────────────────────────────────────────

def get_numbers_pool():
    return numbers_pool

def get_pool_numbers(pool_key):
    return numbers_pool.get(pool_key, [])

async def add_numbers_to_pool(bot, pool_key, new_numbers):
    existing = set(numbers_pool.get(pool_key, []))
    added = 0
    skipped = 0
    for n in new_numbers:
        if n not in existing:
            existing.add(n)
            added += 1
        else:
            skipped += 1
    numbers_pool[pool_key] = list(existing)
    await tg_save_pool(bot, pool_key, numbers_pool[pool_key])
    await tg_save_index(bot)
    return added, skipped

async def remove_number_from_pool(bot, pool_key, number):
    nums = numbers_pool.get(pool_key, [])
    if number in nums:
        nums.remove(number)
        numbers_pool[pool_key] = nums
        await tg_save_pool(bot, pool_key, nums)

def count_numbers(pool_key):
    return len(numbers_pool.get(pool_key, []))

# ─── User/Session Functions ────────────────────────────────────────────────

USERS_MSG_ID = None  # storage channel এ users list এর message id

async def tg_save_users(bot):
    global USERS_MSG_ID
    try:
        # FORMAT: USERS\nuid1:username1\nuid2:username2...
        lines = [f"{uid}:{uname}" for uid, uname in users_db.items()]
        text = "USERS\n" + "\n".join(lines) if lines else "USERS\n"
        if USERS_MSG_ID:
            await bot.edit_message_text(
                chat_id=STORAGE_CHANNEL_ID,
                message_id=USERS_MSG_ID,
                text=text
            )
        else:
            msg = await bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=text)
            USERS_MSG_ID = msg.message_id
            await tg_save_index(bot)
    except Exception as e:
        logger.error(f"tg_save_users error: {e}")

async def tg_load_users(bot, users_msg_id):
    global users_db, USERS_MSG_ID
    try:
        USERS_MSG_ID = users_msg_id
        msg = await bot.forward_message(
            chat_id=STORAGE_CHANNEL_ID,
            from_chat_id=STORAGE_CHANNEL_ID,
            message_id=users_msg_id
        )
        text = msg.text or ""
        await msg.delete()
        for line in text.split("\n")[1:]:
            if ":" in line:
                uid, uname = line.split(":", 1)
                users_db[uid.strip()] = uname.strip()
        logger.info(f"✅ Loaded {len(users_db)} users")
    except Exception as e:
        logger.error(f"tg_load_users error: {e}")

def add_user(user_id, username, bot=None):
    uid = str(user_id)
    if uid not in users_db:
        users_db[uid] = username or str(user_id)
        return True  # new user
    return False  # existing

def is_new_user(user_id):
    return str(user_id) not in users_db

def get_all_users():
    return list(users_db.keys())

def get_user_count():
    return len(users_db)

def set_session(user_id, number, pool_key):
    user_sessions[str(user_id)] = {
        "number": number,
        "pool_key": pool_key,
        "assigned_time": datetime.now().isoformat()
    }

def get_session(user_id):
    return user_sessions.get(str(user_id))

def get_active_sessions_count():
    return len(user_sessions)

def find_users_by_number(number):
    """কোন user এই number নিয়েছে খুঁজে বের করো"""
    matched = []
    for uid, session in user_sessions.items():
        if session.get("number") == number:
            matched.append(uid)
    return matched

# ─── Helper Functions ──────────────────────────────────────────────────────

def parse_pool_key(pool_key):
    parts = pool_key.split("_")
    code = parts[0]
    slot = parts[1].upper() if len(parts) >= 2 else ""
    return code, slot

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
        result = []
        for row in data.get("data", []):
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

# ─── OTP Polling ───────────────────────────────────────────────────────────

async def poll_otps(context):
    try:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🤖 Number Bot", url="https://t.me/pc_clonev1_bot"),
            InlineKeyboardButton("📢 Our Channel", url=MAIN_CHANNEL_LINK)
        ]])

        for otp_data in fetch_cr_api_otps():
            try:
                number = otp_data.get("num", "").strip()
                message = otp_data.get("message", "").strip()
                dt = otp_data.get("dt", "").strip()
                otp_code = extract_otp(message)
                if not number or not otp_code or not dt:
                    continue

                # Duplicate check: number+otp_code+dt তিনটা মিলিয়ে unique
                cache_key = f"hadi:{number}:{otp_code}:{dt}"
                if cache_key in otp_cache:
                    continue
                otp_cache[cache_key] = True

                country = extract_country_code(number)
                flag = COUNTRY_FLAGS.get(country, "🌍")
                hidden = hide_number(number)

                # ── Channel message (quoted raw SMS) ──
                channel_msg = (
                    f"🆕 *NEW OTP — FACEBOOK*\n\n"
                    f"📱 Number : {flag} `+{hidden}`\n"
                    f"🔐 OTP Code : `{otp_code}`\n"
                    f"⏰ Time : `{dt}`\n\n"
                    f"❝ {message} ❞"
                )
                await context.bot.send_message(
                    chat_id=OTP_CHANNEL_ID,
                    text=channel_msg,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )

                # ── Inbox notification (full number) ──
                matched_users = find_users_by_number(number)
                if matched_users:
                    inbox_msg = (
                        f"🔔 *আপনার OTP এসেছে!*\n\n"
                        f"📱 Number : {flag} `+{number}`\n"
                        f"🔐 OTP Code : `{otp_code}`\n"
                        f"⏰ Time : `{dt}`\n\n"
                        f"❝ {message} ❞"
                    )
                    for uid in matched_users:
                        try:
                            await context.bot.send_message(
                                chat_id=int(uid),
                                text=inbox_msg,
                                parse_mode="Markdown"
                            )
                        except Exception as e:
                            logger.error(f"Inbox send error [{uid}]: {e}")

            except Exception as e:
                logger.error(f"CR OTP error: {e}")

    except Exception as e:
        logger.error(f"Poll OTPs Error: {e}")

# ─── Telegram Handlers ─────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_new = is_new_user(user.id)
    add_user(user.id, user.username or user.first_name)
    if is_new:
        asyncio.create_task(tg_save_users(context.bot))

    buttons = [[KeyboardButton("📲 Get Number"), KeyboardButton("📋 Active Numbers")]]
    if user.id == ADMIN_ID:
        buttons.append([KeyboardButton("👑 Admin Panel")])
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)

    if is_new:
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
            parse_mode="Markdown", reply_markup=keyboard
        )
    else:
        loading_msg = await update.message.reply_text("🔄 Loading...")
        await asyncio.sleep(0.7)
        await loading_msg.delete()
        await update.message.reply_text(
            f"👋 *Welcome Back, {user.first_name}!*\n\n"
            f"🤖 NUMBER PANEL NGN — Ready!",
            parse_mode="Markdown", reply_markup=keyboard
        )

async def reply_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "📲 Get Number":
        pool = get_numbers_pool()
        if not pool:
            await update.message.reply_text("❌ No numbers available yet!")
            return
        buttons = [
            InlineKeyboardButton(get_button_label(pk), callback_data=f"getcountry:{pk}")
            for pk in sorted(pool.keys())
        ]
        keyboard = InlineKeyboardMarkup([[btn] for btn in buttons])
        await update.message.reply_text(
            "🌍 *Select Country for Facebook:*",
            parse_mode="Markdown", reply_markup=keyboard
        )

    elif text == "📋 Active Numbers":
        session = get_session(user_id)
        msg = "📱 *Your Active Numbers:*\n\n"
        if session:
            msg += f"📘 {get_button_label(session['pool_key'])}\n📱 `{session['number']}`"
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
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("getcountry:"):
        pool_key = data.split(":", 1)[1]
        numbers = get_pool_numbers(pool_key)
        if not numbers:
            await query.answer("❌ No numbers available", show_alert=True)
            return
        number = random.choice(numbers)
        set_session(user_id, number, pool_key)
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
            parse_mode="Markdown", reply_markup=keyboard
        )

    elif data.startswith("change:"):
        pool_key = data.split(":", 1)[1]
        session = get_session(user_id)
        if session and session.get("number"):
            await remove_number_from_pool(context.bot, pool_key, session["number"])
        numbers = get_pool_numbers(pool_key)
        if not numbers:
            await query.answer("❌ No more numbers available", show_alert=True)
            return
        number = random.choice(numbers)
        set_session(user_id, number, pool_key)
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
            parse_mode="Markdown", reply_markup=keyboard
        )

    elif data == "changecountry":
        pool = get_numbers_pool()
        if not pool:
            await query.answer("❌ No countries available", show_alert=True)
            return
        buttons = [
            InlineKeyboardButton(get_button_label(pk), callback_data=f"getcountry:{pk}")
            for pk in sorted(pool.keys())
        ]
        keyboard = InlineKeyboardMarkup([[btn] for btn in buttons])
        await query.edit_message_text(
            "🌍 *Select Country for Facebook:*",
            parse_mode="Markdown", reply_markup=keyboard
        )

    elif data.startswith("admin_"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Admin only!", show_alert=True)
            return
        action = data.split("_", 1)[1]

        if action == "stats":
            pool = get_numbers_pool()
            total_numbers = sum(len(v) for v in pool.values())
            await query.edit_message_text(
                f"📊 *Statistics*\n\n"
                f"👥 Total Users: `{get_user_count()}`\n"
                f"📱 Total Numbers: `{total_numbers}`\n"
                f"🌍 Pools: `{len(pool)}`\n"
                f"📡 Active Sessions: `{get_active_sessions_count()}`",
                parse_mode="Markdown"
            )

        elif action == "addnumbers":
            await query.edit_message_text(
                "📝 *Send numbers.txt file*\n\n"
                "📌 Format: `91.txt` or `91_s2.txt`\n"
                "📌 Content: One number per line",
                parse_mode="Markdown"
            )

        elif action == "broadcast":
            context.bot_data["pending_broadcast"] = True
            await query.edit_message_text(
                "📢 *Broadcast*\n\n"
                "এখন যে message পাঠাবে সেটা সব user কে send হবে।\n"
                "পাঠাও:",
                parse_mode="Markdown"
            )

        elif action == "analytics":
            await query.edit_message_text("📈 *Analytics*\n\nComing soon...", parse_mode="Markdown")

        elif action == "delete":
            await query.edit_message_text("🗑️ *Delete Numbers*\n\nComing soon...", parse_mode="Markdown")

        elif action == "settings":
            await query.edit_message_text("⚙️ *Settings*\n\nComing soon...", parse_mode="Markdown")

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.bot_data.get("pending_broadcast"):
        return
    context.bot_data["pending_broadcast"] = False
    broadcast_text = update.message.text
    user_ids = get_all_users()
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
    new_numbers = [
        line.strip().lstrip('+')
        for line in text.split('\n')
        if line.strip() and len(line.strip()) >= 7
    ]
    added, skipped = await add_numbers_to_pool(context.bot, pool_key, new_numbers)
    await update.message.reply_text(
        f"✅ *Upload Complete!*\n\n"
        f"🌍 Pool: *{get_button_label(pool_key)}*\n"
        f"✅ Added: `{added}` numbers\n"
        f"⏭ Skipped: `{skipped}`\n"
        f"📱 Total: `{count_numbers(pool_key)}`",
        parse_mode="Markdown"
    )

# ─── Main ──────────────────────────────────────────────────────────────────

async def post_init(app):
    """Bot start হওয়ার পর Telegram storage থেকে data load করো"""
    logger.info("📦 Loading pools from Telegram storage...")
    await tg_load_all_pools(app.bot)
    logger.info(f"✅ Loaded {len(numbers_pool)} pools, {sum(len(v) for v in numbers_pool.values())} total numbers")

    # OTP preload
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

def main():
    logger.info("🚀 Starting NUMBER PANEL NGN Bot...")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
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
