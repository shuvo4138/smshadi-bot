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

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "1984916365").strip())
OTP_CHANNEL_ID = int(os.getenv("OTP_CHANNEL_ID", "-1002625886518").strip())
OTP_CHANNEL_LINK = os.getenv("OTP_CHANNEL_LINK", "https://t.me/+SWraCXOQrWM4Mzg9").strip()
JOIN_CHANNEL = os.getenv("JOIN_CHANNEL", "https://t.me/alwaysrvice24hours").strip()
DASHBOARD_BASE = "http://185.2.83.39/ints/agent/SMSDashboard"
DASHBOARD_USER = os.getenv("DASHBOARD_USER", "shuvo098").strip()
DASHBOARD_PASS = os.getenv("DASHBOARD_PASS", "Shuvo.99@@").strip()
NUMBERS_FILE = "numbers.json"
DATA_FILE = "bot_data.json"

SERVICES = ["Facebook", "WhatsApp", "TikTok", "Instagram", "Telegram"]
SERVICE_EMOJI = {
    "Facebook": "📘", "WhatsApp": "💬", "TikTok": "🎵",
    "Instagram": "📸", "Telegram": "✈️",
}

COUNTRY_FLAGS = {
    "1": "🇺🇸", "7": "🇷🇺", "20": "🇪🇬", "27": "🇿🇦", "30": "🇬🇷",
    "31": "🇳🇱", "32": "🇧🇪", "33": "🇫🇷", "34": "🇪🇸", "36": "🇭🇺",
    "39": "🇮🇹", "40": "🇷🇴", "41": "🇨🇭", "43": "🇦🇹", "44": "🇬🇧",
    "45": "🇩🇰", "46": "🇸🇪", "47": "🇳🇴", "48": "🇵🇱", "49": "🇩🇪",
    "51": "🇵🇪", "52": "🇲🇽", "53": "🇨🇺", "54": "🇦🇷", "55": "🇧🇷",
    "56": "🇨🇱", "57": "🇨🇴", "58": "🇻🇪", "60": "🇲🇾", "61": "🇦🇺",
    "62": "🇮🇩", "63": "🇵🇭", "64": "🇳🇿", "65": "🇸🇬", "66": "🇹🇭",
    "81": "🇯🇵", "82": "🇰🇷", "84": "🇻🇳", "86": "🇨🇳", "90": "🇹🇷",
    "91": "🇮🇳", "92": "🇵🇰", "93": "🇦🇫", "94": "🇱🇰", "95": "🇲🇲",
    "959": "🇲🇲", "880": "🇧🇩", "966": "🇸🇦", "971": "🇦🇪", "972": "🇮🇱",
    "98": "🇮🇷", "234": "🇳🇬", "254": "🇰🇪", "255": "🇹🇿", "256": "🇺🇬",
}

COUNTRY_NAMES = {
    "1": "USA/Canada", "7": "Russia", "20": "Egypt", "27": "South Africa",
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
    "95": "Myanmar", "959": "Myanmar", "880": "Bangladesh", "966": "Saudi Arabia",
    "971": "UAE", "972": "Israel", "98": "Iran", "234": "Nigeria",
    "254": "Kenya", "255": "Tanzania", "256": "Uganda",
}

if not BOT_TOKEN:
    logger.error("BOT_TOKEN is not set!")
    import time; time.sleep(10); exit(1)

numbers_pool = {s: {} for s in SERVICES}
user_numbers = {}
user_history = {}
otp_history = {}
otp_cache = {}
banned_users = set()
all_users = set()
session_cookie = None

# ─── Dashboard Login ──────────────────────────────────────────────

def login_dashboard():
    global session_cookie
    try:
        session = requests.Session()
        resp = session.get(
            "http://185.2.83.39/ints/login",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        captcha_match = re.search(r'What is (\d+)\s*\+\s*(\d+)', resp.text)
        if captcha_match:
            a, b = int(captcha_match.group(1)), int(captcha_match.group(2))
            captcha_answer = str(a + b)
            logger.info(f"🔢 Captcha: {a}+{b}={captcha_answer}")
        else:
            captcha_answer = "6"

        login_resp = session.post(
            "http://185.2.83.39/ints/login",
            data={"username": DASHBOARD_USER, "password": DASHBOARD_PASS, "captcha": captcha_answer},
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=True, timeout=10
        )
        logger.info(f"🔐 Login: {login_resp.status_code}, URL: {login_resp.url}")
        if "PHPSESSID" in session.cookies:
            session_cookie = session.cookies["PHPSESSID"]
            logger.info(f"✅ Login success: {session_cookie[:15]}...")
            return session_cookie
        else:
            logger.error(f"❌ Login failed: {login_resp.text[:200]}")
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
    return None

def get_session():
    global session_cookie
    if not session_cookie:
        login_dashboard()
    return session_cookie

def fetch_otp_for_number(number: str):
    cookie = get_session()
    if not cookie:
        return None
    try:
        clean_num = number.lstrip("+").strip()
        resp = requests.get(
            f"{DASHBOARD_BASE}/res/data_smscdr.php",
            params={"sEcho": 1, "iDisplayStart": 0, "iDisplayLength": 50, "fnumber": clean_num},
            headers={
                "Cookie": f"PHPSESSID={cookie}",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{DASHBOARD_BASE}/SMSCDRReports",
                "User-Agent": "Mozilla/5.0"
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            rows = data.get("aaData", [])
            if rows:
                latest = rows[0]
                if len(latest) >= 6:
                    return {
                        "datetime": latest[0],
                        "sender": str(latest[3] or ""),
                        "message": str(latest[5] or ""),
                        "number": clean_num
                    }
        elif resp.status_code in [302, 401, 403]:
            global session_cookie
            session_cookie = None
            login_dashboard()
    except Exception as e:
        logger.error(f"OTP fetch error: {e}")
    return None

def fetch_all_recent_otps():
    cookie = get_session()
    if not cookie:
        return []
    try:
        resp = requests.get(
            f"{DASHBOARD_BASE}/res/data_smscdr.php",
            params={"sEcho": 1, "iDisplayStart": 0, "iDisplayLength": 100},
            headers={
                "Cookie": f"PHPSESSID={cookie}",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{DASHBOARD_BASE}/SMSCDRReports",
                "User-Agent": "Mozilla/5.0"
            },
            timeout=10
        )
        logger.info(f"📡 CDR: {resp.status_code}, size: {len(resp.text)}")
        if resp.status_code == 200:
            data = resp.json()
            rows = data.get("aaData", [])
            logger.info(f"✅ Got {len(rows)} rows")
            return rows
        elif resp.status_code in [302, 401, 403]:
            global session_cookie
            session_cookie = None
            login_dashboard()
    except Exception as e:
        logger.error(f"Recent OTP error: {e}")
    return []

# ─── Helpers ──────────────────────────────────────────────────────

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

# ─── Keyboards ────────────────────────────────────────────────────

def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton("📲 Get Number"), KeyboardButton("📋 Active Number")],
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("👑 Admin Panel")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

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
        [InlineKeyboardButton("🔀 Change Number", callback_data=f"country_{service}_{country}"),
         InlineKeyboardButton("📢 OTP Group", url=OTP_CHANNEL_LINK)],
        [InlineKeyboardButton("❌ Release", callback_data="release_number"),
         InlineKeyboardButton("🔙 Main Menu", callback_data="get_number")],
    ])

async def safe_edit(query, text, parse_mode="Markdown", reply_markup=None):
    try:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise

# ─── Persistence ──────────────────────────────────────────────────

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

# ─── OTP Polling ──────────────────────────────────────────────────

async def poll_otps(context):
    now = datetime.now()
    old_keys = [k for k, v in otp_cache.items() if now - v > timedelta(hours=1)]
    for k in old_keys:
        del otp_cache[k]

    rows = fetch_all_recent_otps()
    new_count = 0

    all_pool_numbers = set()
    for s in SERVICES:
        for nums in numbers_pool[s].values():
            for n in nums:
                all_pool_numbers.add(n.lstrip("+").strip())

    for row in rows:
        try:
            if len(row) < 6:
                continue
            dt_str = str(row[0])
            number = str(row[2]).strip()
            sender = str(row[3] or "Unknown")
            message = str(row[5] or "")
            if not message or not number:
                continue

            cache_key = f"{number}:{dt_str}:{message[:30]}"
            if cache_key in otp_cache:
                continue
            otp_cache[cache_key] = datetime.now()

            clean_number = number.lstrip("+").strip()
            if clean_number not in all_pool_numbers:
                continue

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
                await asyncio.sleep(0.5)
                new_count += 1
            except Exception as e:
                err = str(e)
                if "Flood control" in err or "flood" in err.lower():
                    match = re.search(r'Retry in (\d+)', err)
                    wait = int(match.group(1)) + 2 if match else 15
                    await asyncio.sleep(wait)
                else:
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

    if new_count:
        logger.info(f"✅ Poll done: {new_count} new OTPs")
    save_data()

# ─── Handlers ─────────────────────────────────────────────────────

async def is_member(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=OTP_CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    if user.id in banned_users:
        await update.message.reply_text("❌ আপনি ban হয়েছেন।")
        return
    await update.message.reply_text("👋", reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(
        f"👋 স্বাগতম *{user.first_name}*!\n\n🤖 *SMS Hadi OTP Bot*\n\nService বেছে number নিন এবং OTP receive করুন। 👇",
        parse_mode="Markdown",
        reply_markup=service_keyboard()
    )
    await update.message.reply_text("Menu:", reply_markup=get_main_keyboard(user.id))
    save_data()

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ আপনি admin না!")
        return
    await show_admin_panel(update, context)

async def show_admin_panel(update, context):
    stats = service_stats()
    total_otp = sum(len(v) for v in otp_history.values())
    text = f"👑 *Admin Panel*\n\n👥 Users: {len(all_users)} | 🚫 Banned: {len(banned_users)}\n📨 Total OTP: {total_otp}\n🔑 Session: {'✅' if session_cookie else '❌'}\n\n*📦 Number Pool:*\n"
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
             InlineKeyboardButton("🔄 Re-Login", callback_data="admin_relogin")],
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

    if context.user_data.get("waiting_country_for_upload") and user_id == ADMIN_ID:
        context.user_data["waiting_country_for_upload"] = False
        service = context.user_data.get("upload_service", "")
        code = text.strip()
        flag = COUNTRY_FLAGS.get(code, "🌍")
        name = get_country_name(code)
        context.user_data["upload_country"] = code
        await update.message.reply_text(
            f"✅ দেশ: *{flag} {name}* (`{code}`)\n\nএখন *{SERVICE_EMOJI.get(service,'')} {service}* এর TXT/CSV file পাঠান।",
            parse_mode="Markdown"
        )
        return

    if context.user_data.get("waiting_country_for_add") and user_id == ADMIN_ID:
        context.user_data["waiting_country_for_add"] = False
        service = context.user_data.pop("pending_add_service", "")
        code = text.strip()
        flag = COUNTRY_FLAGS.get(code, "🌍")
        name = get_country_name(code)
        context.user_data["add_number_mode"] = (service, code)
        await update.message.reply_text(
            f"✅ দেশ: *{flag} {name}* (`{code}`)\n\nএখন number গুলো পাঠান (space বা comma দিয়ে):",
            parse_mode="Markdown"
        )
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

    if text == "📲 Get Number":
        await update.message.reply_text("📲 *Service বেছে নিন:*", parse_mode="Markdown", reply_markup=service_keyboard())

    elif text == "📋 Active Number":
        if user_id in user_numbers:
            info = user_numbers[user_id]
            num = info["number"]
            service = info["service"]
            country = info["country"]
            flag = COUNTRY_FLAGS.get(country, "🌍")
            name = get_country_name(country)
            emoji = SERVICE_EMOJI.get(service, "")
            await update.message.reply_text(
                f"📞 *Your Number is Ready!*\n\nTap to copy: `{num}`\n\n✅ Your number is active!\n❗ OTP Group এ incoming SMS দেখুন।\n\n🔖 {emoji} {service} | {flag} {name}",
                parse_mode="Markdown",
                reply_markup=number_action_keyboard(num, service, country)
            )
        else:
            await update.message.reply_text("❌ আপনার কোনো active number নেই।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📲 Number নিন", callback_data="get_number")]]))

    elif text == "👑 Admin Panel":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ আপনি admin না!")
            return
        await show_admin_panel(update, context)

    else:
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
        if not await is_member(context.bot, user_id):
            await safe_edit(query, "⚠️ *Number নিতে আগে channel join করুন!*",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Channel Join করুন", url=JOIN_CHANNEL)],
                    [InlineKeyboardButton("✅ Join করেছি", callback_data=data)],
                ]))
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
            await safe_edit(query, "❌ এই দেশে আর number নেই।",
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
            f"📞 *Your Number is Ready!*\n\nTap to copy: `{num}`\n\n✅ Your number is active!\n❗ OTP Group এ incoming SMS দেখুন।\n\n🔖 {emoji} {service} | {flag} {name}",
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

    elif data == "release_number":
        if user_id in user_numbers:
            info = user_numbers.pop(user_id)
            save_data()
            await safe_edit(query, f"✅ `{info['number']}` ছেড়ে দেওয়া হয়েছে।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📲 নতুন Number নিন", callback_data="get_number")]]))
        else:
            await safe_edit(query, "❌ কোনো number নেই।")

    elif data == "admin_users":
        if user_id != ADMIN_ID: return
        text = f"👥 *Users ({len(all_users)})*\n\n"
        for uid in list(all_users)[:30]:
            info = user_numbers.get(uid, {})
            num = info.get("number", "—")
            svc = info.get("service", "—")
            cc = info.get("country", "")
            flag = COUNTRY_FLAGS.get(cc, "")
            banned = "🚫" if uid in banned_users else "✅"
            text += f"{banned} `{uid}` | {svc} {flag} | `{num}`\n"
        await safe_edit(query, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_otp_stats":
        if user_id != ADMIN_ID: return
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
        await safe_edit(query, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_live_otp":
        if user_id != ADMIN_ID: return
        await safe_edit(query, "🔴 *Live OTP চেক করছি...*")
        rows = fetch_all_recent_otps()
        if not rows:
            await context.bot.send_message(user_id, "❌ Dashboard থেকে OTP পাওয়া যায়নি।")
            return
        all_pool_numbers = set()
        for s in SERVICES:
            for nums in numbers_pool[s].values():
                all_pool_numbers.update(nums)
        text = f"🔴 *Live OTP* (last {min(len(rows),10)})\n\n"
        for row in rows[:10]:
            if len(row) < 6: continue
            num = str(row[2])
            sender = str(row[3] or "?")
            message = str(row[5] or "")
            dt = str(row[0])
            otp = extract_otp(message)
            flag = get_flag(num)
            in_pool = "✅" if num in all_pool_numbers else "❌"
            text += f"{in_pool}{flag} `{mask_number(num)}` | 🔐 `{otp}` | {sender}\n🕐 {dt}\n\n"
        await context.bot.send_message(user_id, text, parse_mode="Markdown")

    elif data == "admin_add_num":
        if user_id != ADMIN_ID: return
        buttons = [[InlineKeyboardButton(f"{SERVICE_EMOJI[s]} {s}", callback_data=f"addnum_{s}")] for s in SERVICES]
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
        await safe_edit(query, "➕ কোন service এ number যোগ করবেন?", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("addnum_"):
        if user_id != ADMIN_ID: return
        service = data.replace("addnum_", "")
        context.user_data["pending_add_service"] = service
        context.user_data["waiting_country_for_add"] = True
        await safe_edit(query,
            f"➕ *{SERVICE_EMOJI.get(service,'')} {service}*\n\nদেশের code দিন (যেমন: `95` Myanmar, `880` Bangladesh):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_add_num")]]))

    elif data == "admin_numlist":
        if user_id != ADMIN_ID: return
        assigned_nums = {v["number"] for v in user_numbers.values()}
        text = "📋 *Number List*\n\n"
        for s in SERVICES:
            emoji = SERVICE_EMOJI[s]
            countries = numbers_pool[s]
            if not countries: continue
            text += f"{emoji} *{s}*\n"
            for cc, nums in countries.items():
                flag = COUNTRY_FLAGS.get(cc, "🌍")
                name = get_country_name(cc)
                free = sum(1 for n in nums if n not in assigned_nums)
                text += f"  {flag} {name}: {len(nums)} total | 🟢 {free}\n"
            text += "\n"
        await safe_edit(query, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_broadcast":
        if user_id != ADMIN_ID: return
        context.user_data["broadcast_mode"] = True
        await safe_edit(query, f"📢 *Broadcast*\n{len(all_users)} জন user কে message যাবে। এখন পাঠান:")

    elif data == "admin_test":
        if user_id != ADMIN_ID: return
        await safe_edit(query, "🧪 Dashboard test করছি...")
        rows = fetch_all_recent_otps()
        if rows:
            await context.bot.send_message(user_id, f"✅ Dashboard কাজ করছে!\n📊 {len(rows)}টি SMS।\nCookie: `{session_cookie[:15] if session_cookie else 'None'}...`", parse_mode="Markdown")
        else:
            await context.bot.send_message(user_id, "❌ Dashboard কাজ করছে না! Re-Login করুন।")

    elif data == "admin_upload":
        if user_id != ADMIN_ID: return
        buttons = [[InlineKeyboardButton(f"{SERVICE_EMOJI[s]} {s}", callback_data=f"upload_{s}")] for s in SERVICES]
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
        await safe_edit(query, "📤 কোন service এর জন্য file upload করবেন?", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("upload_"):
        if user_id != ADMIN_ID: return
        service = data.replace("upload_", "")
        context.user_data["upload_service"] = service
        context.user_data["waiting_country_for_upload"] = True
        await safe_edit(query,
            f"📤 *{SERVICE_EMOJI.get(service,'')} {service}*\n\nদেশের code দিন (যেমন: `95` Myanmar, `880` Bangladesh):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_upload")]]))

    elif data == "admin_clear":
        if user_id != ADMIN_ID: return
        buttons = [[InlineKeyboardButton(f"{SERVICE_EMOJI[s]} {s}", callback_data=f"clear_{s}")] for s in SERVICES]
        buttons.append([InlineKeyboardButton("🗑 সব clear", callback_data="clear_ALL")])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
        await safe_edit(query, "🗑 কোনটা clear করবেন?", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("clear_"):
        if user_id != ADMIN_ID: return
        target = data.replace("clear_", "")
        if target == "ALL":
            for s in SERVICES:
                numbers_pool[s].clear()
            user_numbers.clear()
            save_numbers(); save_data()
            await safe_edit(query, "✅ সব clear!")
        elif target in SERVICES:
            numbers_pool[target].clear()
            save_numbers()
            await safe_edit(query, f"✅ *{target}* clear!")

    elif data == "admin_relogin":
        if user_id != ADMIN_ID: return
        global session_cookie
        session_cookie = None
        await safe_edit(query, "🔄 Re-login করছি...")
        result = login_dashboard()
        if result:
            await context.bot.send_message(user_id, f"✅ Re-login সফল!\nCookie: `{result[:15]}...`", parse_mode="Markdown")
        else:
            await context.bot.send_message(user_id, "❌ Re-login failed!")

    elif data == "admin_back":
        if user_id != ADMIN_ID: return
        stats = service_stats()
        total_otp = sum(len(v) for v in otp_history.values())
        text = f"👑 *Admin Panel*\n\n👥 Users: {len(all_users)} | 🚫 Banned: {len(banned_users)}\n📨 Total OTP: {total_otp}\n🔑 Session: {'✅' if session_cookie else '❌'}\n\n*📦 Number Pool:*\n"
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
                 InlineKeyboardButton("🔄 Re-Login", callback_data="admin_relogin")],
            ])
        )

    elif data == "admin_ban_menu":
        if user_id != ADMIN_ID: return
        await safe_edit(query, "🚫 *Ban/Unban*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Ban", callback_data="admin_ban"),
                 InlineKeyboardButton("✅ Unban", callback_data="admin_unban")],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_back")],
            ]))

    elif data == "admin_ban":
        if user_id != ADMIN_ID: return
        context.user_data["ban_mode"] = True
        await context.bot.send_message(user_id, "🚫 Ban করতে User ID পাঠান:")

    elif data == "admin_unban":
        if user_id != ADMIN_ID: return
        context.user_data["unban_mode"] = True
        await context.bot.send_message(user_id, "✅ Unban করতে User ID পাঠান:")

# ─── File Upload ──────────────────────────────────────────────────

async def upload_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.document:
        return
    if context.user_data.get("waiting_country_for_upload"):
        await update.message.reply_text("❌ আগে দেশের code দিন, তারপর file পাঠান।")
        return
    service = context.user_data.pop("upload_service", None)
    country_code = context.user_data.pop("upload_country", None)
    if not service or not country_code:
        await update.message.reply_text("❓ Admin Panel → File Upload → Service এবং দেশ select করুন।")
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

# ─── Main ─────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Starting Bot...")
    load_numbers()
    load_data()
    logger.info("🔐 Dashboard login করছি...")
    login_dashboard()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, upload_numbers))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.job_queue.run_repeating(poll_otps, interval=15, first=5, job_kwargs={"max_instances": 1})
    logger.info("✅ Bot running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
