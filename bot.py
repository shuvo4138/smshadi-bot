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
session_cookie = None

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

def solve_math_captcha(question: str) -> str:
    """
    Math CAPTCHA solve করে
    Example: "What is 6 + 9 = ?" → "15"
    """
    try:
        # Extract numbers and operator
        # Pattern: "What is X + Y = ?" or "X + Y = ?"
        match = re.search(r'(\d+)\s*\+\s*(\d+)', question)
        if match:
            a = int(match.group(1))
            b = int(match.group(2))
            result = a + b
            logger.info(f"🔢 CAPTCHA: {a} + {b} = {result}")
            return str(result)
        
        # Try subtraction
        match = re.search(r'(\d+)\s*-\s*(\d+)', question)
        if match:
            a = int(match.group(1))
            b = int(match.group(2))
            result = a - b
            logger.info(f"🔢 CAPTCHA: {a} - {b} = {result}")
            return str(result)
        
        # Try multiplication
        match = re.search(r'(\d+)\s*[*×]\s*(\d+)', question)
        if match:
            a = int(match.group(1))
            b = int(match.group(2))
            result = a * b
            logger.info(f"🔢 CAPTCHA: {a} × {b} = {result}")
            return str(result)
            
        logger.warning(f"⚠️ Could not parse CAPTCHA: {question}")
        return ""
        
    except Exception as e:
        logger.error(f"❌ CAPTCHA solve error: {e}")
        return ""

def login_dashboard():
    """
    ✅ AUTO-LOGIN with CAPTCHA solving
    SMS Hadi panel এ auto login করে session cookie নেয়
    """
    global session_cookie
    
    try:
        logger.info("🔐 Starting auto-login...")
        session = requests.Session()
        
        # Step 1: Get login page to find CAPTCHA
        login_url = "http://185.2.83.39/ints/login"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }
        
        logger.info("📡 Fetching login page...")
        resp = session.get(login_url, headers=headers, timeout=15)
        
        if resp.status_code != 200:
            logger.error(f"❌ Login page error: {resp.status_code}")
            return None
        
        # Step 2: Find CAPTCHA question
        # Looking for: "What is 6 + 9 = ?"
        captcha_answer = ""
        
        # Try multiple CAPTCHA patterns
        patterns = [
            r'What is (\d+)\s*\+\s*(\d+)\s*=\s*\?',
            r'(\d+)\s*\+\s*(\d+)\s*=\s*\?',
            r'What is (\d+)\s*\+\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, resp.text)
            if match:
                captcha_answer = solve_math_captcha(match.group(0))
                break
        
        if not captcha_answer:
            logger.warning("⚠️ CAPTCHA not found in HTML, using default")
            captcha_answer = "15"  # Fallback
        
        # Step 3: Submit login with credentials + CAPTCHA answer
        logger.info(f"📤 Submitting login (CAPTCHA: {captcha_answer})...")
        
        login_data = {
            "username": DASHBOARD_USER,
            "password": DASHBOARD_PASS,
            "captcha": captcha_answer,
            "submit": "LOGIN"
        }
        
        login_resp = session.post(
            login_url,
            data=login_data,
            headers=headers,
            allow_redirects=True,
            timeout=15
        )
        
        logger.info(f"📡 Login response: {login_resp.status_code}, URL: {login_resp.url}")
        
        # Step 4: Check if login successful
        if "PHPSESSID" in session.cookies:
            session_cookie = session.cookies["PHPSESSID"]
            logger.info(f"✅ AUTO-LOGIN SUCCESS! Session: {session_cookie[:20]}...")
            return session_cookie
        
        # Check if redirected to dashboard
        if "SMSDashboard" in login_resp.url or "dashboard" in login_resp.url.lower():
            # Try to get cookie from response
            for cookie in session.cookies:
                if cookie.name == "PHPSESSID":
                    session_cookie = cookie.value
                    logger.info(f"✅ LOGIN SUCCESS via redirect! Session: {session_cookie[:20]}...")
                    return session_cookie
        
        # Login failed
        logger.error(f"❌ Auto-login failed!")
        logger.error(f"Response URL: {login_resp.url}")
        logger.error(f"Response preview: {login_resp.text[:500]}")
        
        # Check for error messages
        if "invalid" in login_resp.text.lower() or "incorrect" in login_resp.text.lower():
            logger.error("❌ Invalid credentials or CAPTCHA!")
        
        return None
        
    except requests.exceptions.Timeout:
        logger.error("⏱️ Login timeout!")
        return None
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def get_session():
    """
    Returns current session cookie
    Auto re-login if session expired
    """
    global session_cookie
    
    if not session_cookie:
        logger.info("🔄 No session, attempting auto-login...")
        login_dashboard()
    
    return session_cookie

def test_session():
    """Test if current session is valid"""
    cookie = get_session()
    if not cookie:
        return False
    
    try:
        resp = requests.get(
            f"{DASHBOARD_BASE}/res/data_smscdr.php",
            params={"sEcho": 1, "iDisplayStart": 0, "iDisplayLength": 10},
            headers={
                "Cookie": f"PHPSESSID={cookie}",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=10
        )
        
        if resp.status_code == 200:
            logger.info("✅ Session is valid")
            return True
        else:
            logger.warning(f"⚠️ Session test failed: {resp.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Session test error: {e}")
        return False

def fetch_otp_for_number(number: str):
    """
    Panel থেকে specific number এর latest OTP fetch করে
    Auto re-login if session expired
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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        logger.info(f"📡 API Response: {resp.status_code}")
        
        # Check if session expired (redirect to login)
        if resp.status_code in [302, 401, 403]:
            logger.warning("⚠️ Session expired, re-logging in...")
            global session_cookie
            session_cookie = None
            login_dashboard()
            return fetch_otp_for_number(number)  # Retry
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                rows = data.get("aaData", [])
                logger.info(f"📊 Found {len(rows)} SMS for {clean_num}")
                
                if rows and len(rows) > 0:
                    latest = rows[0]
                    if len(latest) >= 6:
                        result = {
                            "datetime": str(latest[0] or ""),
                            "sender": str(latest[3] or "Unknown"),
                            "message": str(latest[5] or ""),
                            "number": clean_num
                        }
                        logger.info(f"✅ OTP: {result['sender']} - {result['message'][:50]}...")
                        return result
                else:
                    logger.info(f"⏳ No SMS for {clean_num}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON error: {e}")
                logger.error(f"Response: {resp.text[:500]}")
        else:
            logger.error(f"❌ API Error: {resp.status_code}")
            
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Timeout for {number}")
    except Exception as e:
        logger.error(f"❌ Fetch error for {number}: {e}")
    
    return None

def fetch_all_recent_otps():
    """
    Panel থেকে সব recent OTPs fetch করে
    Auto re-login if needed
    """
    cookie = get_session()
    if not cookie:
        logger.error("❌ No session!")
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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        
        # Auto re-login on session expire
        if resp.status_code in [302, 401, 403]:
            logger.warning("⚠️ Session expired during polling, re-logging in...")
            global session_cookie
            session_cookie = None
            login_dashboard()
            return []  # Skip this poll cycle
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                rows = data.get("aaData", [])
                logger.info(f"🔄 Polling: {len(rows)} SMS records")
                return rows
            except json.JSONDecodeError:
                logger.error("❌ JSON error in polling")
        else:
            logger.warning(f"⚠️ Polling: {resp.status_code}")
            
    except requests.exceptions.Timeout:
        logger.warning("⏱️ Polling timeout")
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
            
            # Cache check
            cache_key = f"{number}:{message[:30]}"
            if cache_key in otp_cache:
                continue
            
            otp_cache[cache_key] = True
            otp_code = extract_otp(message)
            
            # Find owner
            owner_id = None
            for uid, num in user_numbers.items():
                if num == number or num.lstrip("+") == number.lstrip("+"):
                    owner_id = uid
                    break
            
            # Send to channel
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
                logger.info(f"✅ Channel: {otp_code} for {mask_number(number)}")
            except Exception as e:
                logger.error(f"❌ Channel error: {e}")
            
            # Notify user
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
                    logger.info(f"✅ User {owner_id}: {otp_code}")
                except Exception as e:
                    logger.error(f"❌ User notify: {e}")
                    
        except Exception as e:
            logger.error(f"❌ OTP process error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
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
    """Text handler"""
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🏠 Home":
        await start(update, context)

    elif text == "📲 Get Number":
        if not numbers_pool:
            await update.message.reply_text("❌ এখন কোনো number নেই। Admin কে জানান।")
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
        logger.info(f"👤 User {user_id} → {num}")

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
            await update.message.reply_text("❌ আপনার কোনো number নেই।")

    elif text == "👑 Admin Panel":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ আপনি admin না!")
            return
            
        assigned = len(user_numbers)
        available = len(numbers_pool) - assigned
        
        keyboard = [
            [InlineKeyboardButton("📤 Numbers Upload", callback_data="admin_upload")],
            [InlineKeyboardButton("🗑 Clear All", callback_data="admin_clear")],
            [InlineKeyboardButton("🔄 Re-Login", callback_data="admin_relogin")],
            [InlineKeyboardButton("🧪 Test Session", callback_data="admin_test")],
        ]
        
        await update.message.reply_text(
            f"👑 *Admin Panel*\n\n"
            f"📦 Total: {len(numbers_pool)}\n"
            f"✅ Available: {available}\n"
            f"👥 Assigned: {assigned}\n"
            f"🔑 Session: {'✅ Active' if session_cookie else '❌ None'}\n"
            f"🤖 Auto-Login: ✅ Enabled",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Button callback handler"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "get_number":
        if not numbers_pool:
            await query.edit_message_text("❌ কোনো number নেই।")
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
            await query.edit_message_text("❌ সব busy।")
            return
            
        user_numbers[user_id] = num
        keyboard = [
            [InlineKeyboardButton("🔄 OTP Check", callback_data=f"refresh_{num}")],
            [InlineKeyboardButton("❌ Number ছেড়ে দিন", callback_data="release_number")],
        ]
        
        await query.edit_message_text(
            f"✅ *Number:*\n\n`{num}`\n\nOTP আসলে notify হবে! 🔔",
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
            keyboard = [[InlineKeyboardButton("🔄 আবার", callback_data="check_otp")]]
            await query.edit_message_text("⏳ এখনো OTP নেই।", reply_markup=InlineKeyboardMarkup(keyboard))

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
            keyboard = [[InlineKeyboardButton("🔄 আবার", callback_data=f"refresh_{num}")]]
            await query.edit_message_text("⏳ OTP নেই।", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "release_number":
        if user_id in user_numbers:
            num = user_numbers.pop(user_id)
            await query.edit_message_text(f"✅ `{num}` ছেড়ে দেওয়া হয়েছে।", parse_mode="Markdown")
            logger.info(f"👤 User {user_id} released {num}")
        else:
            await query.edit_message_text("❌ কোনো number নেই।")

    elif data == "admin_upload":
        if user_id != ADMIN_ID:
            return
        await query.edit_message_text(
            "📤 TXT/CSV file পাঠান।\n\n```\n959655653869\n959654946028\n```",
            parse_mode="Markdown"
        )

    elif data == "admin_clear":
        if user_id != ADMIN_ID:
            return
        numbers_pool.clear()
        user_numbers.clear()
        save_numbers()
        await query.edit_message_text("✅ সব clear!")
        logger.info("🗑️ Cleared all")

    elif data == "admin_relogin":
        if user_id != ADMIN_ID:
            return
        await query.edit_message_text("🔄 Re-login করছি...")
        global session_cookie
        session_cookie = None
        result = login_dashboard()
        if result:
            await context.bot.send_message(user_id, f"✅ Re-login সফল!\n🔑 Session: `{result[:20]}...`", parse_mode="Markdown")
        else:
            await context.bot.send_message(user_id, "❌ Re-login failed!")

    elif data == "admin_test":
        if user_id != ADMIN_ID:
            return
        await query.edit_message_text("🧪 Testing...")
        valid = test_session()
        if valid:
            await context.bot.send_message(user_id, "✅ Session valid!")
        else:
            await context.bot.send_message(user_id, "❌ Session invalid! Auto re-login...")
            global session_cookie
            session_cookie = None
            login_dashboard()

async def upload_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """File upload handler"""
    if update.effective_user.id != ADMIN_ID:
        return
        
    if not update.message.document:
        return
        
    doc = update.message.document
    file = await doc.get_file()
    content = await file.download_as_bytearray()
    text = content.decode("utf-8", errors="ignore")
    
    new_numbers = []
    tokens = re.split(r'[\s,;]+', text)
    for token in tokens:
        token = token.strip().replace("+", "")
        if token.isdigit() and 8 <= len(token) <= 15:
            new_numbers.append(token)
    
    existing = set(numbers_pool)
    added = [n for n in new_numbers if n not in existing]
    numbers_pool.extend(added)
    save_numbers()
    
    logger.info(f"📤 Upload: {len(added)} new, {len(numbers_pool)} total")
    
    await update.message.reply_text(
        f"✅ *Upload সফল!*\n\n📥 নতুন: {len(added)}\n📦 Total: {len(numbers_pool)}",
        parse_mode="Markdown"
    )

def main():
    """Main function"""
    logger.info("🚀 Starting OTP Bot with AUTO-LOGIN...")
    
    # Load numbers
    load_numbers()
    
    # Auto-login
    logger.info("🔐 Attempting auto-login...")
    result = login_dashboard()
    
    if result:
        logger.info(f"✅ Initial login successful!")
        
        # Test session
        if test_session():
            logger.info("✅ Session test passed!")
        else:
            logger.warning("⚠️ Session test failed!")
    else:
        logger.error("❌ Initial login failed! Bot will retry during operation.")
    
    # Build app
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, upload_numbers))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Background OTP polling
    app.job_queue.run_repeating(poll_otps, interval=15, first=5)
    
    logger.info("🤖 Bot running with AUTO-LOGIN enabled!")
    logger.info(f"📦 {len(numbers_pool)} numbers loaded")
    logger.info("🔄 OTP polling: every 15 seconds")
    logger.info("🔐 Auto re-login on session expire")
    
    # Start
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
