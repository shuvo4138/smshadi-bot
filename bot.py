import logging
import re
import io
import csv
import random
import requests
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "1984916365").strip())
OTP_CHANNEL_ID = int(os.getenv("OTP_CHANNEL_ID", "-1002625886518").strip())
JOIN_CHANNEL = os.getenv("JOIN_CHANNEL", "https://t.me/alwaysrvice24hours").strip()
DASHBOARD_BASE = os.getenv("DASHBOARD_BASE", "http://185.2.83.39/ints/agent/SMSDashboard").strip()
DASHBOARD_USER = os.getenv("DASHBOARD_USER", "shuvo098").strip()
DASHBOARD_PASS = os.getenv("DASHBOARD_PASS", "Shuvo.99@@").strip()
NUMBERS_FILE = "numbers.json"

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN is not set!")
    import time
    time.sleep(10)
    exit(1)

numbers_pool = []
user_numbers = {}
otp_cache = {}

# ✅ MANUAL SESSION COOKIE - Browser থেকে নেওয়া
# Session expire হলে browser দিয়ে login করে নতুন cookie নিতে হবে
session_cookie = "44kap8np50h7fue4dyn2tnbad1"

def save_numbers():
    """Numbers pool JSON file এ save করে"""
    try:
        with open(NUMBERS_FILE, "w") as f:
            json.dump(numbers_pool, f)
        logger.info(f"💾 Saved {len(numbers_pool)} numbers")
    except Exception as e:
        logger.error(f"❌ Save error: {e}")

def load_numbers():
    """Startup এ numbers load করে"""
    global numbers_pool
    try:
        if os.path.exists(NUMBERS_FILE):
            with open(NUMBERS_FILE, "r") as f:
                numbers_pool = json.load(f)
            logger.info(f"📂 Loaded {len(numbers_pool)} numbers from file")
        else:
            logger.info("📂 No saved numbers found")
    except Exception as e:
        logger.error(f"❌ Load error: {e}")

def get_session():
    """Returns current session cookie"""
    global session_cookie
    if not session_cookie:
        session_cookie = "44kap8np50h7fue4dyn2tnbad1"  # Fallback to manual session
    return session_cookie

def fetch_otp_for_number(number: str):
    """
    Panel থেকে specific number এর latest OTP fetch করে
    """
    cookie = get_session()
    if not cookie:
        logger.error("❌ No session cookie available!")
        return None
    
    try:
        clean_num = number.lstrip("+").strip()
        logger.info(f"🔍 Fetching OTP for: {clean_num}")
        
        url = f"{DASHBOARD_BASE}/res/data_smscdr.php"
        params = {
            "sEcho": 1,
            "iDisplayStart": 0,
            "iDisplayLength": 50,
            "fnumber": clean_num
        }
        headers = {
            "Cookie": f"PHPSESSID={cookie}",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{DASHBOARD_BASE}/SMSCDRReports",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        logger.info(f"📡 API Response: {resp.status_code}")
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                rows = data.get("aaData", [])
                logger.info(f"📊 Found {len(rows)} SMS records for {clean_num}")
                
                if rows and len(rows) > 0:
                    latest = rows[0]
                    if len(latest) >= 6:
                        result = {
                            "datetime": str(latest[0] or ""),
                            "sender": str(latest[3] or "Unknown"),
                            "message": str(latest[5] or ""),
                            "number": clean_num
                        }
                        logger.info(f"✅ OTP Found: From {result['sender']} - {result['message'][:50]}...")
                        return result
                else:
                    logger.info(f"⏳ No SMS found for {clean_num}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON decode error: {e}")
                logger.error(f"Response text: {resp.text[:500]}")
        else:
            logger.error(f"❌ API Error: {resp.status_code}")
            logger.error(f"Response: {resp.text[:200]}")
            
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Request timeout for {number}")
    except Exception as e:
        logger.error(f"❌ OTP fetch error for {number}: {e}")
    
    return None

def fetch_all_recent_otps():
    """
    Panel থেকে সব recent OTPs fetch করে (auto-polling এর জন্য)
    """
    cookie = get_session()
    if not cookie:
        logger.error("❌ No session cookie!")
        return []
    
    try:
        url = f"{DASHBOARD_BASE}/res/data_smscdr.php"
        params = {
            "sEcho": 1,
            "iDisplayStart": 0,
            "iDisplayLength": 100
        }
        headers = {
            "Cookie": f"PHPSESSID={cookie}",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{DASHBOARD_BASE}/SMSCDRReports",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                rows = data.get("aaData", [])
                logger.info(f"🔄 Polling: Found {len(rows)} total SMS records")
                return rows
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON decode error in polling: {e}")
        else:
            logger.warning(f"⚠️ Polling API returned {resp.status_code}")
            
    except requests.exceptions.Timeout:
        logger.warning(f"⏱️ Polling timeout")
    except Exception as e:
        logger.error(f"❌ Polling error: {e}")
    
    return []

def extract_otp(msg: str) -> str:
    """SMS থেকে OTP code extract করে"""
    if not msg:
        return ""
    msg = msg.replace("# ", "").replace("#", "").replace("-", "")
    codes = re.findall(r'\b\d{4,8}\b', msg)
    return codes[0] if codes else ""

def mask_number(number: str) -> str:
    """Number mask করে privacy এর জন্য"""
    n = str(number)
    if len(n) >= 8:
        return n[:4] + "★★★★" + n[-4:]
    return n

def get_available_number():
    """Available number দেয় (যেটা এখনো assign হয়নি)"""
    assigned = set(user_numbers.values())
    available = [n for n in numbers_pool if n not in assigned]
    return random.choice(available) if available else None

def get_user_keyboard(user_id):
    """User এর জন্য keyboard menu"""
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

async def poll_otps(context):
    """
    Background task - প্রতি 15 সেকেন্ডে চলে
    নতুন OTP খুঁজে user আর channel এ পাঠায়
    """
    rows = fetch_all_recent_otps()
    
    if not rows:
        return
    
    for row in rows:
        if len(row) < 6:
            continue
            
        try:
            dt_str = str(row[0] or "")
            number = str(row[2] or "").strip()
            sender = str(row[3] or "Unknown")
            message = str(row[5] or "")
            
            if not message or not number:
                continue
            
            # Cache check - duplicate OTP পাঠাবে না
            cache_key = f"{number}:{message[:30]}"
            if cache_key in otp_cache:
                continue
            
            otp_cache[cache_key] = True
            otp_code = extract_otp(message)
            
            # Check if this number belongs to any user
            owner_id = None
            for uid, num in user_numbers.items():
                if num == number or num.lstrip("+") == number.lstrip("+"):
                    owner_id = uid
                    break
            
            # Channel এ পাঠাও
            channel_text = (
                f"📩 *নতুন OTP*\n\n"
                f"📞 Number: `{mask_number(number)}`\n"
                f"🏢 From: {sender}\n"
                f"🔐 OTP: `{otp_code}`\n"
                f"💬 SMS: {message[:100]}\n"
                f"🕐 {dt_str}"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=OTP_CHANNEL_ID,
                    text=channel_text,
                    parse_mode="Markdown"
                )
                logger.info(f"✅ Sent to channel: {otp_code} for {mask_number(number)}")
            except Exception as e:
                logger.error(f"❌ Channel send error: {e}")
            
            # User কে notify করো (যদি number তার হয়)
            if owner_id:
                keyboard = [[InlineKeyboardButton("📢 OTP Channel", url=JOIN_CHANNEL)]]
                user_text = (
                    f"✅ *OTP এসেছে!*\n\n"
                    f"📞 Number: `{number}`\n"
                    f"🏢 From: *{sender}*\n"
                    f"🔐 OTP: `{otp_code}`\n"
                    f"💬 SMS: _{message[:100]}_\n"
                    f"🕐 {dt_str}"
                )
                
                try:
                    await context.bot.send_message(
                        chat_id=owner_id,
                        text=user_text,
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    logger.info(f"✅ Notified user {owner_id}: {otp_code}")
                except Exception as e:
                    logger.error(f"❌ User notify error: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error processing OTP row: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    inline_keyboard = [
        [InlineKeyboardButton("📲 Number নিন", callback_data="get_number")],
        [InlineKeyboardButton("🔍 OTP Check করুন", callback_data="check_otp")],
        [InlineKeyboardButton("📢 OTP Channel", url=JOIN_CHANNEL)],
    ]
    
    await update.message.reply_text(
        f"👋 স্বাগতম {user.first_name}!\n\n"
        f"🤖 *SMS Hadi OTP Bot*\n\n"
        f"Myanmar number নিন এবং OTP receive করুন।",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )
    
    await update.message.reply_text(
        "নিচের menu থেকে option বেছে নিন:",
        reply_markup=get_user_keyboard(user.id)
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Text message handler"""
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🏠 Home":
        await start(update, context)

    elif text == "📲 Get Number":
        if not numbers_pool:
            await update.message.reply_text(
                "❌ এখন কোনো number নেই। Admin কে জানান।"
            )
            return
            
        if user_id in user_numbers:
            num = user_numbers[user_id]
            keyboard = [
                [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
                [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
            ]
            await update.message.reply_text(
                f"✅ আপনার number:\n`{num}`\n\nOTP আসলে notify করা হবে।",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
            
        num = get_available_number()
        if not num:
            await update.message.reply_text("❌ সব number busy। পরে try করুন।")
            return
            
        user_numbers[user_id] = num
        keyboard = [
            [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
            [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
        ]
        
        await update.message.reply_text(
            f"✅ *আপনার Number:*\n\n`{num}`\n\n"
            f"OTP আসলে সাথে সাথে notify করা হবে! 🔔",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"👤 User {user_id} got number: {num}")

    elif text == "🔍 Check OTP":
        if user_id not in user_numbers:
            await update.message.reply_text("❌ আগে number নিন।")
            return
            
        num = user_numbers[user_id]
        msg = await update.message.reply_text(f"🔍 `{num}` এর OTP খুঁজছি...", parse_mode="Markdown")
        
        result = fetch_otp_for_number(num)
        
        if result:
            otp_code = extract_otp(result["message"])
            keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{num}")]]
            
            await msg.edit_text(
                f"✅ *Latest OTP:*\n\n"
                f"📞 `{num}`\n"
                f"🏢 From: *{result['sender']}*\n"
                f"🔐 OTP: `{otp_code}`\n"
                f"💬 _{result['message'][:100]}_\n"
                f"🕐 {result['datetime']}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [[InlineKeyboardButton("🔄 আবার Check", callback_data=f"refresh_{num}")]]
            await msg.edit_text(
                f"⏳ `{num}` এ এখনো OTP আসেনি।",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif text == "📋 My Number":
        if user_id in user_numbers:
            num = user_numbers[user_id]
            keyboard = [
                [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
                [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
            ]
            await update.message.reply_text(
                f"📋 আপনার number:\n`{num}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text("❌ আপনার কোনো number নেই। আগে number নিন।")

    elif text == "👑 Admin Panel":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ আপনি admin না!")
            return
            
        assigned = len(user_numbers)
        available = len(numbers_pool) - assigned
        
        keyboard = [
            [InlineKeyboardButton("📤 Numbers Upload", callback_data="admin_upload")],
            [InlineKeyboardButton("🗑 সব Clear", callback_data="admin_clear")],
            [InlineKeyboardButton("ℹ️ Session Info", callback_data="admin_session")],
        ]
        
        await update.message.reply_text(
            f"👑 *Admin Panel*\n\n"
            f"📦 Total Numbers: {len(numbers_pool)}\n"
            f"✅ Available: {available}\n"
            f"👥 Assigned: {assigned}\n"
            f"🔑 Session: {'✅ Active' if session_cookie else '❌ None'}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback query handler"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "get_number":
        if not numbers_pool:
            await query.edit_message_text("❌ এখন কোনো number নেই।")
            return
            
        if user_id in user_numbers:
            num = user_numbers[user_id]
            keyboard = [
                [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
                [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
            ]
            await query.edit_message_text(
                f"✅ আপনার number:\n`{num}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
            
        num = get_available_number()
        if not num:
            await query.edit_message_text("❌ সব number busy।")
            return
            
        user_numbers[user_id] = num
        keyboard = [
            [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
            [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
        ]
        
        await query.edit_message_text(
            f"✅ *আপনার Number:*\n\n`{num}`\n\n"
            f"OTP আসলে notify করা হবে! 🔔",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "check_otp":
        if user_id not in user_numbers:
            await query.edit_message_text("❌ আগে number নিন।")
            return
            
        num = user_numbers[user_id]
        await query.edit_message_text("🔍 খুঁজছি...")
        
        result = fetch_otp_for_number(num)
        
        if result:
            otp_code = extract_otp(result["message"])
            keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{num}")]]
            
            await query.edit_message_text(
                f"✅ *Latest OTP:*\n\n"
                f"📞 `{num}`\n"
                f"🏢 From: *{result['sender']}*\n"
                f"🔐 OTP: `{otp_code}`\n"
                f"💬 _{result['message'][:100]}_\n"
                f"🕐 {result['datetime']}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [[InlineKeyboardButton("🔄 আবার Check", callback_data="check_otp")]]
            await query.edit_message_text(
                "⏳ এখনো OTP আসেনি।",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif data.startswith("refresh_"):
        num = data.replace("refresh_", "")
        result = fetch_otp_for_number(num)
        
        if result:
            otp_code = extract_otp(result["message"])
            keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{num}")]]
            
            await query.edit_message_text(
                f"✅ *Latest OTP:*\n\n"
                f"📞 `{num}`\n"
                f"🏢 From: *{result['sender']}*\n"
                f"🔐 OTP: `{otp_code}`\n"
                f"💬 _{result['message'][:100]}_\n"
                f"🕐 {result['datetime']}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [[InlineKeyboardButton("🔄 আবার Check", callback_data=f"refresh_{num}")]]
            await query.edit_message_text(
                "⏳ এখনো OTP নেই।",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif data == "release_number":
        if user_id in user_numbers:
            num = user_numbers.pop(user_id)
            await query.edit_message_text(
                f"✅ `{num}` ছেড়ে দেওয়া হয়েছে।",
                parse_mode="Markdown"
            )
            logger.info(f"👤 User {user_id} released number: {num}")
        else:
            await query.edit_message_text("❌ কোনো number নেই।")

    elif data == "admin_upload":
        if user_id != ADMIN_ID:
            return
        await query.edit_message_text(
            "📤 TXT বা CSV file পাঠান।\n\n"
            "Format:\n```\n959655653869\n959654946028\n```",
            parse_mode="Markdown"
        )

    elif data == "admin_clear":
        if user_id != ADMIN_ID:
            return
        numbers_pool.clear()
        user_numbers.clear()
        save_numbers()
        await query.edit_message_text("✅ সব numbers clear হয়েছে।")
        logger.info("🗑️ Admin cleared all numbers")

    elif data == "admin_session":
        if user_id != ADMIN_ID:
            return
        await query.edit_message_text(
            f"ℹ️ *Session Info*\n\n"
            f"🔑 Cookie: `{session_cookie[:25]}...`\n\n"
            f"⚠️ Session expire হলে:\n"
            f"1. Browser দিয়ে panel এ login করুন\n"
            f"2. Console এ `document.cookie` run করুন\n"
            f"3. PHPSESSID copy করুন\n"
            f"4. Code এ update করুন",
            parse_mode="Markdown"
        )

async def upload_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """File upload handler for numbers"""
    if update.effective_user.id != ADMIN_ID:
        return
        
    if not update.message.document:
        return
        
    doc = update.message.document
    file = await doc.get_file()
    content = await file.download_as_bytearray()
    text = content.decode("utf-8", errors="ignore")
    
    new_numbers = []
    
    # Parse file - supports both line-by-line and CSV
    tokens = re.split(r'[\s,;]+', text)
    for token in tokens:
        token = token.strip().replace("+", "")
        if token.isdigit() and 8 <= len(token) <= 15:
            new_numbers.append(token)
    
    existing = set(numbers_pool)
    added = [n for n in new_numbers if n not in existing]
    numbers_pool.extend(added)
    save_numbers()
    
    logger.info(f"📤 Upload: {len(added)} new numbers, {len(numbers_pool)} total")
    
    await update.message.reply_text(
        f"✅ *Upload সফল!*\n\n"
        f"📥 নতুন: {len(added)}\n"
        f"📦 Total: {len(numbers_pool)}",
        parse_mode="Markdown"
    )

def main():
    """Main function"""
    logger.info("🚀 Starting OTP Bot...")
    
    # Load saved numbers
    load_numbers()
    
    # Test session
    logger.info(f"🔐 Session cookie: {session_cookie[:25]}...")
    test = fetch_all_recent_otps()
    if test:
        logger.info(f"✅ Session working! Found {len(test)} SMS records")
    else:
        logger.warning("⚠️ Session test failed - check cookie!")
    
    # Build application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, upload_numbers))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Background OTP polling - প্রতি 15 সেকেন্ডে চলবে
    app.job_queue.run_repeating(poll_otps, interval=15, first=5)
    
    logger.info("🤖 Bot is running...")
    logger.info(f"📦 Loaded {len(numbers_pool)} numbers")
    logger.info("🔄 OTP polling will run every 15 seconds")
    
    # Start polling
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
