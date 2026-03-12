import logging
import re
import requests
import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "1984916365"))
OTP_CHANNEL_ID = int(os.getenv("OTP_CHANNEL_ID", "-1002625886518"))

PANEL_URL = "http://185.2.83.39/ints/agent/"
PANEL_USER = "shuvo098"
PANEL_PASS = "Shuvo.99@@"
PANEL_API_URL = "http://185.2.83.39/ints/agent/res/data_smscdr.php"

PANEL_PHPSESSID = None
PANEL_SESSKEY = None
user_numbers = {}
otp_cache = {}

bot_stats = {
    "total_otps_received": 0,
    "total_otps_delivered": 0,
    "last_otp_time": None,
}

# ─── Panel Login with Selenium ───

def panel_login_selenium():
    """Real browser login to Panel"""
    global PANEL_PHPSESSID, PANEL_SESSKEY
    
    try:
        logger.info("🔐 Starting Panel login (Real Browser)...")
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(PANEL_URL + "login")
        
        # Wait and fill login form
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "username")))
        driver.find_element(By.NAME, "username").send_keys(PANEL_USER)
        driver.find_element(By.NAME, "password").send_keys(PANEL_PASS)
        
        # Get CAPTCHA
        captcha_element = driver.find_element(By.XPATH, "//*[contains(text(), 'What is')]")
        captcha_text = captcha_element.text
        logger.info(f"CAPTCHA: {captcha_text}")
        
        # Solve: "What is 5 + 3 =" → 8
        numbers = re.findall(r'\d+', captcha_text)
        if len(numbers) >= 2:
            answer = int(numbers[0]) + int(numbers[1])
            driver.find_element(By.NAME, "captcha").send_keys(str(answer))
            logger.info(f"✅ CAPTCHA solved: {answer}")
        
        # Submit
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        WebDriverWait(driver, 10).until(EC.url_changes(PANEL_URL + "login"))
        
        # Get cookies
        for cookie in driver.get_cookies():
            if cookie['name'] == 'PHPSESSID':
                PANEL_PHPSESSID = cookie['value']
        
        # Get sesskey
        url = driver.current_url
        match = re.search(r'sesskey=([^&"\']+)', url)
        if match:
            PANEL_SESSKEY = match.group(1)
        
        driver.quit()
        
        if PANEL_PHPSESSID:
            logger.info(f"✅ Login successful! PHPSESSID: {PANEL_PHPSESSID[:15]}...")
            return True
        return False
        
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
        return False

# ─── Fetch OTPs ───

def fetch_all_recent_otps():
    """Fetch OTPs from Panel API"""
    try:
        if not PANEL_PHPSESSID:
            logger.warning("⚠️ No session, attempting login...")
            if not panel_login_selenium():
                return []
        
        now = datetime.now()
        dt1 = now.strftime("%Y-%m-%d 00:00:00")
        dt2 = now.strftime("%Y-%m-%d 23:59:59")
        
        resp = requests.get(
            PANEL_API_URL,
            params={
                "fdate1": dt1, "fdate2": dt2,
                "frange": "", "fclient": "", "fnum": "", "fcli": "",
                "fg": "0", "sesskey": PANEL_SESSKEY or "",
                "sEcho": "1", "iColumns": "9",
                "iDisplayStart": "0", "iDisplayLength": "500",
                "sSearch": "", "bRegex": "false",
                "iSortCol_0": "0", "sSortDir_0": "desc",
            },
            cookies={"PHPSESSID": PANEL_PHPSESSID} if PANEL_PHPSESSID else {},
            timeout=10
        )
        
        if resp.status_code != 200:
            logger.error(f"Panel API error: {resp.status_code}")
            return []
        
        data = resp.json()
        rows = data.get("aaData", [])
        logger.info(f"📡 Panel API: {len(rows)} OTPs")
        
        result = []
        for row in rows:
            if len(row) >= 6 and row[0] and row[2] and row[5]:
                result.append({
                    "dt": str(row[0]).strip(),
                    "num": str(row[2]).strip().lstrip("+"),
                    "cli": str(row[3]).strip().upper() if row[3] else "Unknown",
                    "message": str(row[5]).strip(),
                })
        
        return result
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        return []

# ─── OTP Polling ───

async def poll_otps(context):
    """Poll Panel API and deliver OTPs"""
    rows = fetch_all_recent_otps()
    if not rows:
        return

    for row in rows:
        try:
            num = str(row["num"]).lstrip("+").strip()
            message = str(row["message"]).strip()
            
            otp_code = re.findall(r'\b\d{4,8}\b', message.replace("#", "").replace("is", ""))
            if not otp_code:
                continue
            
            otp_code = otp_code[0]
            cache_key = f"{num}:{otp_code}"
            
            if cache_key in otp_cache:
                continue
            
            otp_cache[cache_key] = True
            if len(otp_cache) > 500:
                for k in list(otp_cache.keys())[:100]:
                    del otp_cache[k]
            
            logger.info(f"🔔 NEW OTP! +{num} | {otp_code}")
            bot_stats["total_otps_received"] += 1
            bot_stats["last_otp_time"] = datetime.now().isoformat()
            
            # Send to channel
            msg = f"🔔 *New OTP*\n\n📱 {row['cli']}\n📞 +{num}\n🔑 `{otp_code}`"
            try:
                await context.bot.send_message(OTP_CHANNEL_ID, msg, parse_mode="Markdown")
                logger.info("✅ Channel notified")
            except Exception as e:
                logger.error(f"Channel error: {e}")

        except Exception as e:
            logger.error(f"Poll error: {e}")

# ─── Bot Handlers ───

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot running with Panel API!")

async def main():
    logger.info("🚀 Starting Bot with Panel Login...")
    
    # Login first
    if panel_login_selenium():
        logger.info("✅ Panel login successful")
    else:
        logger.warning("⚠️ Panel login failed, will retry on first poll")
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    # Poll every 5 seconds
    app.job_queue.run_repeating(poll_otps, interval=5, first=1)
    
    logger.info("✅ Bot running!")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
