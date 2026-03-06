import logging
import re
import random
import requests
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.error import BadRequest

load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "1984916365").strip())
OTP_CHANNEL_ID = int(os.getenv("OTP_CHANNEL_ID", "-1002625886518").strip())
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
    "93": "🇦🇫", "355": "🇦🇱", "213": "🇩🇿", "376": "🇦🇩", "244": "🇦🇴",
    "54": "🇦🇷", "374": "🇦🇲", "61": "🇦🇺", "43": "🇦🇹", "994": "🇦🇿",
    "1242": "🇧🇸", "973": "🇧🇭", "880": "🇧🇩", "375": "🇧🇾", "32": "🇧🇪",
    "501": "🇧🇿", "229": "🇧🇯", "975": "🇧🇹", "591": "🇧🇴", "387": "🇧🇦",
    "267": "🇧🇼", "55": "🇧🇷", "673": "🇧🇳", "359": "🇧🇬", "226": "🇧🇫",
    "257": "🇧🇮", "855": "🇰🇭", "237": "🇨🇲", "1": "🇺🇸", "238": "🇨🇻",
    "236": "🇨🇫", "235": "🇹🇩", "56": "🇨🇱", "86": "🇨🇳", "57": "🇨🇴",
    "269": "🇰🇲", "242": "🇨🇬", "243": "🇨🇩", "506": "🇨🇷", "385": "🇭🇷",
    "53": "🇨🇺", "357": "🇨🇾", "420": "🇨🇿", "45": "🇩🇰", "253": "🇩🇯",
    "593": "🇪🇨", "20": "🇪🇬", "503": "🇸🇻", "240": "🇬🇶", "291": "🇪🇷",
    "372": "🇪🇪", "251": "🇪🇹", "679": "🇫🇯", "358": "🇫🇮", "33": "🇫🇷",
    "241": "🇬🇦", "220": "🇬🇲", "995": "🇬🇪", "49": "🇩🇪", "233": "🇬🇭",
    "30": "🇬🇷", "502": "🇬🇹", "224": "🇬🇳", "245": "🇬🇼", "592": "🇬🇾",
    "509": "🇭🇹", "504": "🇭🇳", "36": "🇭🇺", "354": "🇮🇸", "91": "🇮🇳",
    "62": "🇮🇩", "98": "🇮🇷", "964": "🇮🇶", "353": "🇮🇪", "972": "🇮🇱",
    "39": "🇮🇹", "225": "🇨🇮", "81": "🇯🇵", "962": "🇯🇴", "7": "🇷🇺",
    "254": "🇰🇪", "686": "🇰🇮", "850": "🇰🇵", "82": "🇰🇷", "965": "🇰🇼",
    "996": "🇰🇬", "856": "🇱🇦", "371": "🇱🇻", "961": "🇱🇧", "266": "🇱🇸",
    "231": "🇱🇷", "218": "🇱🇾", "423": "🇱🇮", "370": "🇱🇹", "352": "🇱🇺",
    "261": "🇲🇬", "265": "🇲🇼", "60": "🇲🇾", "960": "🇲🇻", "223": "🇲🇱",
    "356": "🇲🇹", "692": "🇲🇭", "222": "🇲🇷", "230": "🇲🇺", "52": "🇲🇽",
    "691": "🇫🇲", "373": "🇲🇩", "377": "🇲🇨", "976": "🇲🇳", "382": "🇲🇪",
    "212": "🇲🇦", "258": "🇲🇿", "95": "🇲🇲", "264": "🇳🇦", "674": "🇳🇷",
    "977": "🇳🇵", "31": "🇳🇱", "64": "🇳🇿", "505": "🇳🇮", "227": "🇳🇪",
    "234": "🇳🇬", "47": "🇳🇴", "968": "🇴🇲", "92": "🇵🇰", "680": "🇵🇼",
    "970": "🇵🇸", "507": "🇵🇦", "675": "🇵🇬", "595": "🇵🇾", "51": "🇵🇪",
    "63": "🇵🇭", "48": "🇵🇱", "351": "🇵🇹", "974": "🇶🇦", "40": "🇷🇴",
    "250": "🇷🇼", "966": "🇸🇦", "221": "🇸🇳", "381": "🇷🇸", "232": "🇸🇱",
    "65": "🇸🇬", "421": "🇸🇰", "386": "🇸🇮", "677": "🇸🇧", "252": "🇸🇴",
    "27": "🇿🇦", "34": "🇪🇸", "94": "🇱🇰", "249": "🇸🇩", "597": "🇸🇷",
    "268": "🇸🇿", "46": "🇸🇪", "41": "🇨🇭", "963": "🇸🇾", "886": "🇹🇼",
    "992": "🇹🇯", "255": "🇹🇿", "66": "🇹🇭", "670": "🇹🇱", "228": "🇹🇬",
    "676": "🇹🇴", "1868": "🇹🇹", "216": "🇹🇳", "90": "🇹🇷", "993": "🇹🇲",
    "688": "🇹🇻", "256": "🇺🇬", "380": "🇺🇦", "971": "🇦🇪", "44": "🇬🇧",
    "598": "🇺🇾", "998": "🇺🇿", "678": "🇻🇺", "58": "🇻🇪", "84": "🇻🇳",
    "967": "🇾🇪", "260": "🇿🇲", "263": "🇿🇼", "959": "🇲🇲",
}

def get_flag(number: str) -> str:
    number = number.lstrip("+").strip()
    # দীর্ঘ prefix আগে check করো
    for length in [4, 3, 2, 1]:
        prefix = number[:length]
        if prefix in COUNTRY_FLAGS:
            return COUNTRY_FLAGS[prefix]
    return "🌍"
    logger.error("BOT_TOKEN is not set!")
    import time
    time.sleep(10)
    exit(1)

# service -> list of numbers
numbers_pool = {s: [] for s in SERVICES}

user_numbers = {}       # user_id -> {"number": ..., "service": ...}
user_history = {}       # user_id -> list of {number, service, time}
otp_history = {}        # number -> list of otp records
otp_cache = {}          # cache_key -> datetime
banned_users = set()
all_users = set()

# ─── Persistence ────────────────────────────────────────────────

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
                numbers_pool[s] = data.get(s, [])
            logger.info(f"Loaded numbers: { {s: len(numbers_pool[s]) for s in SERVICES} }")
    except Exception as e:
        logger.error(f"Load numbers error: {e}")

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
            logger.info("Data loaded.")
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
        logger.warning(f"API error: {data.get('msg')}")
    except Exception as e:
        logger.error(f"Polling error: {e}")
    return []

# ─── Helpers ─────────────────────────────────────────────────────

def extract_otp(msg: str) -> str:
    if not msg:
        return ""
    msg = msg.replace("# ", "").replace("#", "")
    codes = re.findall(r'\b\d{4,8}\b', msg)
    return codes[0] if codes else ""

def mask_number(number: str) -> str:
    n = str(number)
    return n[:4] + "★★★★" + n[-4:] if len(n) >= 8 else n

def get_available_number(service: str):
    assigned = {v["number"] for v in user_numbers.values()}
    available = [n for n in numbers_pool.get(service, []) if n not in assigned]
    return random.choice(available) if available else None

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
        total = len(numbers_pool[s])
        busy = sum(1 for n in numbers_pool[s] if n in assigned)
        stats[s] = {"total": total, "available": total - busy, "busy": busy}
    return stats

async def is_member(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=OTP_CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

async def safe_edit(query, text, parse_mode="Markdown", reply_markup=None):
    try:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise

def get_user_keyboard(user_id):
    if user_id == ADMIN_ID:
        return ReplyKeyboardMarkup([
            [KeyboardButton("🏠 Home"), KeyboardButton("📲 Get Number")],
            [KeyboardButton("🔍 Check OTP"), KeyboardButton("📋 My Number")],
            [KeyboardButton("👑 Admin Panel")]
        ], resize_keyboard=True)
    return ReplyKeyboardMarkup([
        [KeyboardButton("🏠 Home"), KeyboardButton("📲 Get Number")],
        [KeyboardButton("🔍 Check OTP"), KeyboardButton("📋 My Number")],
    ], resize_keyboard=True)

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
    buttons.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

def number_action_keyboard(number: str, service: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{number}"),
         InlineKeyboardButton("📜 OTP History", callback_data=f"history_{number}")],
        [InlineKeyboardButton("🔀 Change Number", callback_data=f"change_{service}"),
         InlineKeyboardButton("❌ Number ছাড়ুন", callback_data="release_number")],
        [InlineKeyboardButton("📢 OTP Group", url=JOIN_CHANNEL),
         InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")],
    ])

# ─── Polling ─────────────────────────────────────────────────────

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
            record = {"datetime": dt_str, "sender": sender, "message": message, "otp": otp_code}
            add_otp_to_history(number, record)

            owner_id = None
            owner_service = None
            for uid, info in user_numbers.items():
                if info["number"].lstrip("+") == number.lstrip("+"):
                    owner_id = uid
                    owner_service = info.get("service", "")
                    break

            flag = get_flag(number)
            channel_text = (
                f"📩 *নতুন OTP*\n\n"
                f"{flag} Number: `{mask_number(number)}`\n"
                f"🏢 From: {sender}\n"
                f"🔐 OTP: `{otp_code}`\n"
                f"💬 SMS: {message[:100]}\n"
                f"🕐 {dt_str}"
            )
            try:
                await context.bot.send_message(chat_id=OTP_CHANNEL_ID, text=channel_text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Channel error: {e}")

            if owner_id:
                try:
                    await context.bot.send_message(
                        chat_id=owner_id,
                        text=(
                            f"✅ *OTP এসেছে!*\n\n"
                            f"📞 `{number}`\n"
                            f"🏢 From: *{sender}*\n"
                            f"🔐 OTP: `{otp_code}`\n"
                            f"💬 _{message[:100]}_\n"
                            f"🕐 {dt_str}"
                        ),
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("📢 OTP Group", url=JOIN_CHANNEL)],
                            [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{number}")]
                        ])
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
        f"👋 স্বাগতম *{user.first_name}*!\n\n🤖 *SMS Hadi OTP Bot*\n\nMyanmar number নিন এবং OTP receive করুন।\n\nনিচে service বেছে নিন 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📲 Number নিন", callback_data="get_number")],
            [InlineKeyboardButton("📢 OTP Group", url=JOIN_CHANNEL)],
        ])
    )
    await update.message.reply_text("Menu:", reply_markup=get_user_keyboard(user.id))
    save_data()

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
        await update.message.reply_text(f"📢 Broadcast সম্পন্ন!\n✅ Sent: {sent}\n❌ Failed: {failed}")
        return

    if context.user_data.get("ban_mode") and user_id == ADMIN_ID:
        context.user_data["ban_mode"] = False
        try:
            target = int(text.strip())
            banned_users.add(target)
            save_data()
            await update.message.reply_text(f"🚫 `{target}` ban করা হয়েছে।", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Valid User ID দিন।")
        return

    if context.user_data.get("unban_mode") and user_id == ADMIN_ID:
        context.user_data["unban_mode"] = False
        try:
            target = int(text.strip())
            banned_users.discard(target)
            save_data()
            await update.message.reply_text(f"✅ `{target}` unban করা হয়েছে।", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Valid User ID দিন।")
        return

    if context.user_data.get("add_number_mode") and user_id == ADMIN_ID:
        service = context.user_data.pop("add_number_mode")
        tokens = re.split(r'[\s,;]+', text)
        added = []
        for token in tokens:
            token = token.strip().replace("+", "")
            if token.isdigit() and 8 <= len(token) <= 15:
                if token not in numbers_pool[service]:
                    numbers_pool[service].append(token)
                    added.append(token)
        save_numbers()
        await update.message.reply_text(
            f"✅ *{SERVICE_EMOJI.get(service,'')} {service}* এ *{len(added)}টি* number যোগ!\n📦 Total: {len(numbers_pool[service])}",
            parse_mode="Markdown"
        )
        return

    if text == "🏠 Home":
        await start(update, context)

    elif text == "📲 Get Number":
        await update.message.reply_text(
            "📲 *Service বেছে নিন:*",
            parse_mode="Markdown",
            reply_markup=service_keyboard()
        )

    elif text == "🔍 Check OTP":
        if user_id not in user_numbers:
            await update.message.reply_text("❌ আগে number নিন।")
            return
        info = user_numbers[user_id]
        num = info["number"]
        msg = await update.message.reply_text(f"🔍 `{num}` এর OTP খুঁজছি...", parse_mode="Markdown")
        result = fetch_otp_for_number(num)
        if result:
            otp_code = extract_otp(result["message"])
            await msg.edit_text(
                f"✅ *Latest OTP:*\n\n📞 `{num}`\n🏢 From: *{result['sender']}*\n🔐 OTP: `{otp_code}`\n💬 _{result['message'][:100]}_\n🕐 {result['datetime']}",
                parse_mode="Markdown",
                reply_markup=number_action_keyboard(num, info["service"])
            )
        else:
            await msg.edit_text(f"⏳ `{num}` এ এখনো OTP আসেনি।", parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 আবার Check", callback_data=f"refresh_{num}")]]))

    elif text == "📋 My Number":
        if user_id in user_numbers:
            info = user_numbers[user_id]
            num = info["number"]
            service = info["service"]
            emoji = SERVICE_EMOJI.get(service, "")
            await update.message.reply_text(
                f"📞 *Your Number is Ready!*\n\n"
                f"Tap to copy: `{num}`\n\n"
                f"✅ Your number is active!\n"
                f"❗ Go to our OTP Group to see your incoming SMS.\n\n"
                f"🔖 Service: {emoji} {service}",
                parse_mode="Markdown",
                reply_markup=number_action_keyboard(num, service)
            )
        else:
            await update.message.reply_text("❌ আপনার কোনো number নেই।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📲 Number নিন", callback_data="get_number")]]))

    elif text == "👑 Admin Panel":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ আপনি admin না!")
            return
        await show_admin_panel(update, context)

async def show_admin_panel(update, context):
    stats = service_stats()
    total_otp = sum(len(v) for v in otp_history.values())
    text = (
        f"👑 *Admin Panel*\n\n"
        f"👥 Total Users: {len(all_users)}\n"
        f"🚫 Banned: {len(banned_users)}\n"
        f"📨 Total OTP: {total_otp}\n\n"
        f"*📦 Number Pool:*\n"
    )
    for s in SERVICES:
        emoji = SERVICE_EMOJI[s]
        st = stats[s]
        text += f"{emoji} {s}: {st['total']} total | 🟢 {st['available']} free | 🔴 {st['busy']} busy\n"
    await update.message.reply_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 User List", callback_data="admin_users"),
             InlineKeyboardButton("📊 OTP Stats", callback_data="admin_otp_stats")],
            [InlineKeyboardButton("➕ Number যোগ", callback_data="admin_add_num"),
             InlineKeyboardButton("📋 Number List", callback_data="admin_numlist")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
             InlineKeyboardButton("🧪 Test API", callback_data="admin_test")],
            [InlineKeyboardButton("🔴 Live OTP Feed", callback_data="admin_live_otp"),
             InlineKeyboardButton("📤 File Upload", callback_data="admin_upload")],
            [InlineKeyboardButton("🗑 Clear Numbers", callback_data="admin_clear"),
             InlineKeyboardButton("🚫 Ban/Unban", callback_data="admin_ban_menu")],
        ])
    )

# ─── Button Handler ───────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if user_id in banned_users and user_id != ADMIN_ID:
        await safe_edit(query, "❌ আপনি ban হয়েছেন।")
        return

    if data in ("main_menu", "get_number"):
        await safe_edit(query, "📲 *Service বেছে নিন:*", reply_markup=service_keyboard())

    elif data.startswith("service_"):
        service = data.replace("service_", "")
        if service not in SERVICES:
            return
        # Join check
        if not await is_member(context.bot, user_id):
            await safe_edit(query,
                "⚠️ *Number নিতে হলে আগে আমাদের OTP Channel join করুন!*",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Channel Join করুন", url=JOIN_CHANNEL)],
                    [InlineKeyboardButton("✅ Join করেছি", callback_data=data)],
                ])
            )
            return
        if user_id in user_numbers:
            user_numbers.pop(user_id)
        num = get_available_number(service)
        if not num:
            await safe_edit(query,
                f"❌ *{SERVICE_EMOJI.get(service,'')} {service}* এ এখন কোনো number নেই।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="get_number")]]))
            return
        user_numbers[user_id] = {"number": num, "service": service}
        if user_id not in user_history:
            user_history[user_id] = []
        user_history[user_id].insert(0, {"number": num, "service": service, "time": datetime.now().strftime("%Y-%m-%d %H:%M")})
        all_users.add(user_id)
        save_data()
        emoji = SERVICE_EMOJI.get(service, "")
        await safe_edit(query,
            f"📞 *Your Number is Ready!*\n\n"
            f"Tap to copy: `{num}`\n\n"
            f"✅ Your number is active!\n"
            f"❗ Go to our OTP Group to see your incoming SMS.\n\n"
            f"🔖 Service: {emoji} {service}",
            reply_markup=number_action_keyboard(num, service)
        )

    elif data.startswith("change_"):
        service = data.replace("change_", "")
        if user_id in user_numbers:
            user_numbers.pop(user_id)
        num = get_available_number(service)
        if not num:
            await safe_edit(query, f"❌ *{service}* এ আর কোনো number নেই।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="get_number")]]))
            return
        user_numbers[user_id] = {"number": num, "service": service}
        if user_id not in user_history:
            user_history[user_id] = []
        user_history[user_id].insert(0, {"number": num, "service": service, "time": datetime.now().strftime("%Y-%m-%d %H:%M")})
        save_data()
        emoji = SERVICE_EMOJI.get(service, "")
        await safe_edit(query,
            f"🔀 *নতুন Number:*\n\nTap to copy: `{num}`\n\n✅ Your number is active!\n❗ Go to our OTP Group.\n\n🔖 Service: {emoji} {service}",
            reply_markup=number_action_keyboard(num, service)
        )

    elif data.startswith("refresh_"):
        num = data.replace("refresh_", "")
        result = fetch_otp_for_number(num)
        service = user_numbers.get(user_id, {}).get("service", "")
        if result:
            otp_code = extract_otp(result["message"])
            await safe_edit(query,
                f"✅ *Latest OTP:*\n\n📞 `{num}`\n🏢 From: *{result['sender']}*\n🔐 OTP: `{otp_code}`\n💬 _{result['message'][:100]}_\n🕐 {result['datetime']}",
                reply_markup=number_action_keyboard(num, service)
            )
        else:
            await safe_edit(query, f"⏳ `{num}` এ এখনো OTP আসেনি।",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 আবার Check", callback_data=f"refresh_{num}")],
                    [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
                ]))

    elif data.startswith("history_"):
        num = data.replace("history_", "")
        history = otp_history.get(num, [])
        service = user_numbers.get(user_id, {}).get("service", "")
        if not history:
            await safe_edit(query, f"📜 `{num}` এর কোনো OTP history নেই।",
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
        text = f"👥 *সব Users ({len(all_users)})*\n\n"
        for uid in list(all_users)[:30]:
            info = user_numbers.get(uid, {})
            num = info.get("number", "—")
            svc = info.get("service", "—")
            banned = "🚫" if uid in banned_users else "✅"
            text += f"{banned} `{uid}` | {svc} | `{num}`\n"
        if len(all_users) > 30:
            text += f"\n...আরো {len(all_users)-30} জন"
        await safe_edit(query, text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_otp_stats":
        if user_id != ADMIN_ID:
            return
        total_otp = sum(len(v) for v in otp_history.values())
        text = f"📊 *OTP Statistics*\n\nTotal: {total_otp}\n\n*সাম্প্রতিক (last 10):*\n"
        recent = []
        for num, records in otp_history.items():
            for r in records:
                recent.append((r.get("datetime", ""), num, r.get("otp", ""), r.get("sender", "")))
        recent.sort(reverse=True, key=lambda x: x[0])
        for dt, num, otp, sender in recent[:10]:
            text += f"📞 `{mask_number(num)}` | 🔐 `{otp}` | {sender}\n"
        await safe_edit(query, text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_live_otp":
        if user_id != ADMIN_ID:
            return
        await safe_edit(query, "🔴 *Live OTP চেক করছি...*")
        rows = fetch_all_recent_otps()
        if not rows:
            await context.bot.send_message(user_id, "❌ API থেকে কোনো OTP পাওয়া যায়নি।")
            return
        all_pool_numbers = set()
        for s in SERVICES:
            all_pool_numbers.update(numbers_pool[s])
        text = f"🔴 *Live OTP Feed* (last {min(len(rows),10)})\n\n"
        for row in rows[:10]:
            num = str(row.get("num", ""))
            sender = row.get("cli", "?")
            message = row.get("message", "")
            dt = row.get("dt", "")
            otp = extract_otp(message)
            in_pool = "✅" if num in all_pool_numbers else "❌"
            text += f"{in_pool} `{mask_number(num)}` | 🔐 `{otp}` | {sender}\n🕐 {dt}\n\n"
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
        context.user_data["add_number_mode"] = service
        await safe_edit(query,
            f"➕ *{SERVICE_EMOJI.get(service,'')} {service}* এ number যোগ করুন:\n\nSpace বা comma দিয়ে পাঠান:\n`959655653869 959654946028`")

    elif data == "admin_numlist":
        if user_id != ADMIN_ID:
            return
        stats = service_stats()
        assigned_nums = {v["number"] for v in user_numbers.values()}
        text = "📋 *Number List*\n\n"
        for s in SERVICES:
            emoji = SERVICE_EMOJI[s]
            st = stats[s]
            text += f"{emoji} *{s}* — {st['total']} total | 🟢 {st['available']} | 🔴 {st['busy']}\n"
            for n in numbers_pool[s][:5]:
                status = "🔴" if n in assigned_nums else "🟢"
                text += f"  {status} `{n}`\n"
            if len(numbers_pool[s]) > 5:
                text += f"  ...আরো {len(numbers_pool[s])-5}টি\n"
            text += "\n"
        await safe_edit(query, text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

    elif data == "admin_broadcast":
        if user_id != ADMIN_ID:
            return
        context.user_data["broadcast_mode"] = True
        await safe_edit(query, f"📢 *Broadcast*\n\n{len(all_users)} জন user কে message যাবে।\nএখন message পাঠান:")

    elif data == "admin_test":
        if user_id != ADMIN_ID:
            return
        await safe_edit(query, "🧪 API test করছি...")
        rows = fetch_all_recent_otps()
        if rows:
            await context.bot.send_message(user_id, f"✅ API কাজ করছে!\n📊 {len(rows)}টি SMS পাওয়া গেছে।")
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
        await safe_edit(query, f"📤 *{SERVICE_EMOJI.get(service,'')} {service}* এর জন্য TXT/CSV file পাঠান।")

    elif data == "admin_clear":
        if user_id != ADMIN_ID:
            return
        buttons = [[InlineKeyboardButton(f"{SERVICE_EMOJI[s]} {s} clear", callback_data=f"clear_{s}")] for s in SERVICES]
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
                [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"),
                 InlineKeyboardButton("✅ Unban User", callback_data="admin_unban")],
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
        text = (
            f"👑 *Admin Panel*\n\n"
            f"👥 Total Users: {len(all_users)}\n"
            f"🚫 Banned: {len(banned_users)}\n"
            f"📨 Total OTP: {total_otp}\n\n*📦 Number Pool:*\n"
        )
        for s in SERVICES:
            emoji = SERVICE_EMOJI[s]
            st = stats[s]
            text += f"{emoji} {s}: {st['total']} | 🟢 {st['available']} | 🔴 {st['busy']}\n"
        await safe_edit(query, text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 User List", callback_data="admin_users"),
                 InlineKeyboardButton("📊 OTP Stats", callback_data="admin_otp_stats")],
                [InlineKeyboardButton("➕ Number যোগ", callback_data="admin_add_num"),
                 InlineKeyboardButton("📋 Number List", callback_data="admin_numlist")],
                [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                 InlineKeyboardButton("🧪 Test API", callback_data="admin_test")],
                [InlineKeyboardButton("🔴 Live OTP Feed", callback_data="admin_live_otp"),
                 InlineKeyboardButton("📤 File Upload", callback_data="admin_upload")],
                [InlineKeyboardButton("🗑 Clear Numbers", callback_data="admin_clear"),
                 InlineKeyboardButton("🚫 Ban/Unban", callback_data="admin_ban_menu")],
            ])
        )

# ─── File Upload ──────────────────────────────────────────────────

async def upload_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.document:
        return

    service = context.user_data.pop("upload_service", None)
    if not service:
        buttons = [[InlineKeyboardButton(f"{SERVICE_EMOJI[s]} {s}", callback_data=f"upload_{s}")] for s in SERVICES]
        await update.message.reply_text("❓ কোন service এর জন্য এই file?", reply_markup=InlineKeyboardMarkup(buttons))
        context.user_data["pending_file"] = update.message.document.file_id
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
            if token not in numbers_pool[service]:
                numbers_pool[service].append(token)
                added.append(token)
    save_numbers()
    emoji = SERVICE_EMOJI.get(service, "")
    await update.message.reply_text(
        f"✅ *{emoji} {service}* এ *{len(added)}টি* number যোগ!\n📦 Total: {len(numbers_pool[service])}",
        parse_mode="Markdown"
    )

# ─── Main ─────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Starting Bot...")
    load_numbers()
    load_data()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, upload_numbers))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.job_queue.run_repeating(poll_otps, interval=10, first=5)
    logger.info("✅ Bot running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
