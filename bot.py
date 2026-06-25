#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   𝐏𝐑𝐎𝐅𝐄𝐒𝐒𝐎𝐑 𝐄𝐗𝐎𝐃𝐔𝐒 𝚯𝐅𝐅𝚰𝐂𝐈𝚫𝐋 - Telegram Bot                ║
║   Developer: @mianmanan270                                       ║
║   DISCLAIMER: For Educational Purposes Only                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import os
import re
import random
import string
import base64
import hashlib
import urllib.parse
import logging
import asyncio
import socket
import threading
import xml.etree.ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, date, timedelta
from typing import Optional

import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

# ─────────────────────────── CONFIG ───────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set. Please set it before running.")
DEVELOPER_USERNAME = "mianmanan270"
DATA_FILE = os.path.join(os.path.dirname(__file__), "user_data.json")

FREE_DAILY_CREDITS = 10
PREMIUM_DAILY_CREDITS = 100
REFERRAL_BONUS_REFERRER = 10
REFERRAL_BONUS_NEW_USER  = 5

# World Monitor
WORLD_MONITOR_CREDIT_COST = 5

# Daily Claim
CLAIM_BASE_CREDITS = 5
CLAIM_STREAK_BONUS_PER_5 = 3
CLAIM_MAX_BONUS = 20

# Games
GAME_MIN_BET = 1
GAME_MAX_BET = 50

# Rate limiting (seconds between tool commands)
RATE_LIMIT_FREE_SECS = 2
RATE_LIMIT_PREMIUM_SECS = 1

BOT_NAME = "𝐏𝐑𝐎𝐅𝐄𝐒𝐒𝐎𝐑 𝐄𝐗𝐎𝐃𝐔𝐒 𝚯𝐅𝐅𝚰𝐂𝐈𝚫𝐋"
VERSION = "v3.0"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ────────────────────────── DECORATIVE CHARS ──────────────────────────
LINE    = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DLINE   = "══════════════════════════════"
STAR    = "✦"
DIAMOND = "◈"
BULLET  = "▸"
CROWN   = "👑"
BOLT    = "⚡"
SHIELD  = "🛡️"
FIRE    = "🔥"
GEM     = "💎"
LOCK    = "🔐"
TOOLS   = "🛠️"
GLOBE   = "🌐"
MAIL    = "📧"
CARD    = "💳"
DEV     = "👨‍💻"
WARN    = "⚠️"
CHECK   = "✅"
CROSS   = "❌"
INFO    = "ℹ️"
ROCKET  = "🚀"
STAR2   = "⭐"
MONEY   = "💰"

# ─────────────────────────── REFERRAL HELPERS ───────────────────────────
def generate_ref_code(user_id: int) -> str:
    raw = f"EXOD{user_id}CSB"
    return hashlib.md5(raw.encode()).hexdigest()[:8].upper()

# ─────────────────────────── DATA LAYER ───────────────────────────
def load_data() -> dict:
    _DEFAULTS = {
        "users": {}, "premium_users": [], "developer_ids": [],
        "ref_codes": {}, "promo_codes": {}, "feedback": [], "tool_stats": {},
    }
    if not os.path.exists(DATA_FILE):
        save_data(_DEFAULTS.copy())
        return _DEFAULTS.copy()
    try:
        with open(DATA_FILE, "r") as f:
            d = json.load(f)
        changed = False
        for k, v in _DEFAULTS.items():
            if k not in d:
                d[k] = v
                changed = True
        if changed:
            save_data(d)
        return d
    except Exception:
        save_data(_DEFAULTS.copy())
        return _DEFAULTS.copy()

def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user(user_id: int, username: str = "") -> dict:
    data = load_data()
    uid = str(user_id)
    today = str(date.today())
    if uid not in data["users"]:
        data["users"][uid] = {
            "user_id": user_id,
            "username": username,
            "credits": FREE_DAILY_CREDITS,
            "last_reset": today,
            "premium": False,
            "total_used": 0,
            "joined": today,
            "ref_code": generate_ref_code(user_id),
            "referrals": 0,
            "ref_credits_earned": 0,
            "referred_by": None,
            "streak": 0,
            "last_claim": None,
        }
        # Register ref_code → user_id mapping
        data["ref_codes"][generate_ref_code(user_id)] = user_id
        save_data(data)
    user = data["users"][uid]
    # Daily credit reset
    if user.get("last_reset") != today:
        is_premium = is_user_premium(user_id)
        user["credits"] = PREMIUM_DAILY_CREDITS if is_premium else FREE_DAILY_CREDITS
        user["last_reset"] = today
        data["users"][uid] = user
        save_data(data)
    if username:
        data["users"][uid]["username"] = username
        save_data(data)
    return data["users"][uid]

def is_developer(user_id: int, username: str = "") -> bool:
    data = load_data()
    if username and username.lower().replace("@", "") == DEVELOPER_USERNAME.lower():
        if user_id not in data["developer_ids"]:
            data["developer_ids"].append(user_id)
            save_data(data)
        return True
    return user_id in data["developer_ids"]

def is_user_premium(user_id: int) -> bool:
    data = load_data()
    return user_id in data.get("premium_users", []) or is_developer(user_id)

def use_credit(user_id: int) -> bool:
    if is_developer(user_id):
        data = load_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["total_used"] = data["users"][uid].get("total_used", 0) + 1
            save_data(data)
        return True
    data = load_data()
    uid = str(user_id)
    if uid not in data["users"]:
        return False
    user = data["users"][uid]
    if user["credits"] <= 0:
        return False
    user["credits"] -= 1
    user["total_used"] = user.get("total_used", 0) + 1
    data["users"][uid] = user
    save_data(data)
    return True

def add_credits(user_id: int, amount: int):
    data = load_data()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "user_id": user_id, "username": "", "credits": amount,
            "last_reset": str(date.today()), "premium": False,
            "total_used": 0, "joined": str(date.today()),
        }
    else:
        data["users"][uid]["credits"] = data["users"][uid].get("credits", 0) + amount
    save_data(data)

def set_premium(user_id: int, status: bool):
    data = load_data()
    if status:
        if user_id not in data["premium_users"]:
            data["premium_users"].append(user_id)
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["credits"] = PREMIUM_DAILY_CREDITS
    else:
        if user_id in data["premium_users"]:
            data["premium_users"].remove(user_id)
    save_data(data)

def get_all_users() -> list:
    data = load_data()
    return list(data["users"].values())

# ─── in-memory rate limit store ───
_rate_limits: dict = {}

def check_rate_limit(user_id: int) -> float:
    """Returns seconds remaining if rate-limited, else 0."""
    if is_developer(user_id):
        return 0
    limit = RATE_LIMIT_PREMIUM_SECS if is_user_premium(user_id) else RATE_LIMIT_FREE_SECS
    elapsed = datetime.now().timestamp() - _rate_limits.get(user_id, 0)
    remaining = limit - elapsed
    return remaining if remaining > 0 else 0

def update_rate_limit(user_id: int):
    _rate_limits[user_id] = datetime.now().timestamp()

def track_tool_usage(tool_name: str):
    """Increment global tool usage counter."""
    data = load_data()
    data["tool_stats"][tool_name] = data["tool_stats"].get(tool_name, 0) + 1
    save_data(data)

def get_crypto_prices() -> dict:
    """Fetch live prices from CoinGecko free API."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "bitcoin,ethereum,tether,binancecoin,solana,dogecoin,ripple",
                "vs_currencies": "usd",
                "include_24hr_change": "true",
            },
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def get_user_by_ref_code(code: str) -> Optional[int]:
    """Return user_id for a referral code, or None if not found."""
    data = load_data()
    # Check the fast lookup map first
    uid = data.get("ref_codes", {}).get(code.upper())
    if uid:
        return int(uid)
    # Fallback: scan users (handles legacy data)
    for udata in data["users"].values():
        if udata.get("ref_code", "").upper() == code.upper():
            return int(udata["user_id"])
    return None

async def process_referral(context, new_user_id: int, referrer_id: int):
    """Credit both sides and notify referrer."""
    if new_user_id == referrer_id:
        return  # can't refer yourself
    data = load_data()
    new_uid = str(new_user_id)
    ref_uid = str(referrer_id)
    # Guard: only allow one referral per new user
    if data["users"].get(new_uid, {}).get("referred_by") is not None:
        return
    # Mark the new user as referred
    if new_uid in data["users"]:
        data["users"][new_uid]["referred_by"] = referrer_id
        data["users"][new_uid]["credits"] = (
            data["users"][new_uid].get("credits", 0) + REFERRAL_BONUS_NEW_USER
        )
    # Credit referrer
    if ref_uid in data["users"]:
        data["users"][ref_uid]["referrals"] = (
            data["users"][ref_uid].get("referrals", 0) + 1
        )
        data["users"][ref_uid]["credits"] = (
            data["users"][ref_uid].get("credits", 0) + REFERRAL_BONUS_REFERRER
        )
        data["users"][ref_uid]["ref_credits_earned"] = (
            data["users"][ref_uid].get("ref_credits_earned", 0) + REFERRAL_BONUS_REFERRER
        )
    save_data(data)
    # Notify referrer
    try:
        referrer_name = data["users"].get(ref_uid, {}).get("username", "User")
        await context.bot.send_message(
            referrer_id,
            f"🎉 *Referral Bonus!*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Someone just joined using your referral link!\n\n"
            f"⚡ *You earned:* `+{REFERRAL_BONUS_REFERRER} credits`\n"
            f"👥 *Total Referrals:* `{data['users'].get(ref_uid, {}).get('referrals', 1)}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Keep sharing your link for more rewards! 🚀",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass

# ─────────────────────────── LUHN ALGORITHM ───────────────────────────
def luhn_check(card_number: str) -> bool:
    digits = [int(d) for d in card_number if d.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    reverse = digits[::-1]
    for i, d in enumerate(reverse):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0

def luhn_complete(partial: str) -> str:
    partial = partial.replace("x", "").replace("X", "").replace("*", "")
    digits = [int(d) for d in partial if d.isdigit()]
    digits.append(0)
    for check in range(10):
        digits[-1] = check
        total = 0
        for i, d in enumerate(digits[::-1]):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        if total % 10 == 0:
            return "".join(str(d) for d in digits)
    return "".join(str(d) for d in digits)

def generate_cards_from_bin(bin_prefix: str, count: int = 10) -> list:
    cards = []
    bin_clean = bin_prefix.replace("x", "").replace("X", "").replace("*", "")
    for _ in range(count):
        partial = bin_clean
        while len(partial) < 15:
            partial += str(random.randint(0, 9))
        card = luhn_complete(partial)
        month = str(random.randint(1, 12)).zfill(2)
        year = str(random.randint(datetime.now().year + 1, datetime.now().year + 5))
        cvv = "".join([str(random.randint(0, 9)) for _ in range(3)])
        cards.append(f"{card}|{month}|{year}|{cvv}")
    return cards

def get_card_brand(number: str) -> str:
    n = number.replace(" ", "").replace("|", "")
    if n.startswith("4"):
        return "Visa"
    elif n[:2] in ["51","52","53","54","55"] or (51 <= int(n[:2]) <= 55):
        return "Mastercard"
    elif n[:2] in ["34","37"]:
        return "Amex"
    elif n.startswith("6011") or n.startswith("65") or n.startswith("644") or n.startswith("645") or n.startswith("646") or n.startswith("647") or n.startswith("648") or n.startswith("649"):
        return "Discover"
    elif n.startswith("35"):
        return "JCB"
    elif n.startswith("30") or n.startswith("36") or n.startswith("38"):
        return "Diners Club"
    else:
        return "Unknown"

# ─────────────────────────── BIN LOOKUP ───────────────────────────
def lookup_bin(bin_number: str) -> Optional[dict]:
    bin_clean = bin_number[:6]
    try:
        headers = {"Accept-Version": "3", "Accept": "application/json"}
        r = requests.get(f"https://lookup.binlist.net/{bin_clean}", headers=headers, timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    try:
        r2 = requests.get(f"https://data.handyapi.com/bin/{bin_clean}", timeout=8)
        if r2.status_code == 200:
            d = r2.json()
            if d.get("Status") == "SUCCESS":
                return {
                    "scheme": d.get("Scheme", ""),
                    "type": d.get("Type", ""),
                    "brand": d.get("CardTier", ""),
                    "country": {"name": d.get("Country", {}).get("Name", ""), "emoji": d.get("Country", {}).get("A2", "")},
                    "bank": {"name": d.get("Issuer", "")},
                }
    except Exception:
        pass
    return None

# ─────────────────────────── EMAILNATOR ───────────────────────────
EMAILNATOR_SESSION = requests.Session()
EMAILNATOR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.emailnator.com/",
}

def emailnator_get_email() -> Optional[str]:
    try:
        EMAILNATOR_SESSION.get("https://www.emailnator.com/", timeout=8, headers={"User-Agent": EMAILNATOR_HEADERS["User-Agent"]})
        csrf = EMAILNATOR_SESSION.cookies.get("XSRF-TOKEN", "")
        if csrf:
            csrf = urllib.parse.unquote(csrf)
        headers = {**EMAILNATOR_HEADERS, "X-XSRF-TOKEN": csrf}
        payload = {"email": ["domain", "plusGmail", "dotGmail"]}
        r = EMAILNATOR_SESSION.post(
            "https://www.emailnator.com/generate-email",
            json=payload, headers=headers, timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            emails = data.get("email", [])
            if emails:
                return emails[0]
    except Exception as e:
        logger.error(f"Emailnator error: {e}")
    return None

def emailnator_get_inbox(email: str) -> list:
    try:
        csrf = EMAILNATOR_SESSION.cookies.get("XSRF-TOKEN", "")
        if csrf:
            csrf = urllib.parse.unquote(csrf)
        headers = {**EMAILNATOR_HEADERS, "X-XSRF-TOKEN": csrf}
        r = EMAILNATOR_SESSION.post(
            "https://www.emailnator.com/message-list",
            json={"email": email}, headers=headers, timeout=10
        )
        if r.status_code == 200:
            return r.json().get("messageData", [])
    except Exception as e:
        logger.error(f"Emailnator inbox error: {e}")
    return []

def emailnator_read_message(email: str, message_id: str) -> str:
    try:
        csrf = EMAILNATOR_SESSION.cookies.get("XSRF-TOKEN", "")
        if csrf:
            csrf = urllib.parse.unquote(csrf)
        headers = {**EMAILNATOR_HEADERS, "X-XSRF-TOKEN": csrf}
        r = EMAILNATOR_SESSION.post(
            "https://www.emailnator.com/message-list",
            json={"email": email, "messageID": message_id}, headers=headers, timeout=10
        )
        if r.status_code == 200:
            return r.text[:1500]
    except Exception:
        pass
    return ""

# ─────────────────────────── UTILITY FUNCTIONS ───────────────────────────
def fake_address() -> dict:
    streets = ["Maple Street", "Oak Avenue", "Pine Road", "Cedar Lane", "Elm Boulevard", "Walnut Drive", "Cherry Court", "Birch Way", "Willow Place", "Ash Circle"]
    cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "Austin"]
    states = {"New York": "NY", "Los Angeles": "CA", "Chicago": "IL", "Houston": "TX", "Phoenix": "AZ", "Philadelphia": "PA", "San Antonio": "TX", "San Diego": "CA", "Dallas": "TX", "Austin": "TX"}
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan", "Jessica", "Sarah", "Karen"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    city = random.choice(cities)
    fn = random.choice(first_names)
    ln = random.choice(last_names)
    return {
        "name": f"{fn} {ln}",
        "address": f"{random.randint(1, 9999)} {random.choice(streets)}",
        "city": city,
        "state": states[city],
        "zip": f"{random.randint(10000, 99999)}",
        "country": "United States",
        "phone": f"+1-{random.randint(200,999)}-{random.randint(200,999)}-{random.randint(1000,9999)}",
        "email": f"{fn.lower()}.{ln.lower()}{random.randint(1,999)}@gmail.com",
        "dob": f"{random.randint(1,28):02d}/{random.randint(1,12):02d}/{random.randint(1970,2000)}",
        "ssn": f"***-**-{random.randint(1000,9999)}",
        "gender": random.choice(["Male", "Female"]),
    }

def generate_password(length: int = 16, use_symbols: bool = True) -> str:
    chars = string.ascii_letters + string.digits
    if use_symbols:
        chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"
    pwd = []
    pwd.append(random.choice(string.ascii_uppercase))
    pwd.append(random.choice(string.ascii_lowercase))
    pwd.append(random.choice(string.digits))
    if use_symbols:
        pwd.append(random.choice("!@#$%^&*()"))
    while len(pwd) < length:
        pwd.append(random.choice(chars))
    random.shuffle(pwd)
    return "".join(pwd)

def check_website_status(url: str) -> dict:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        start = datetime.now()
        r = requests.get(url, timeout=10, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        elapsed = (datetime.now() - start).total_seconds() * 1000
        return {
            "status_code": r.status_code,
            "status": "Online" if r.status_code < 400 else "Issues",
            "response_time": f"{elapsed:.0f}ms",
            "url": url,
            "final_url": r.url,
            "server": r.headers.get("Server", "Unknown"),
            "content_type": r.headers.get("Content-Type", "Unknown"),
        }
    except requests.exceptions.ConnectionError:
        return {"status": "Offline", "url": url, "status_code": 0, "response_time": "N/A", "server": "N/A", "content_type": "N/A", "final_url": url}
    except Exception as e:
        return {"status": "Error", "url": url, "status_code": 0, "response_time": "N/A", "server": "N/A", "content_type": "N/A", "final_url": url, "error": str(e)}

def ip_lookup(host: str) -> dict:
    try:
        ip = socket.gethostbyname(host)
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=8)
        if r.status_code == 200:
            d = r.json()
            return {
                "ip": ip,
                "hostname": host,
                "city": d.get("city", "N/A"),
                "region": d.get("region", "N/A"),
                "country": d.get("country_name", "N/A"),
                "org": d.get("org", "N/A"),
                "timezone": d.get("timezone", "N/A"),
                "latitude": d.get("latitude", "N/A"),
                "longitude": d.get("longitude", "N/A"),
                "isp": d.get("org", "N/A"),
            }
        return {"ip": ip, "hostname": host}
    except Exception as e:
        return {"error": str(e), "hostname": host}

def age_calculator(dob_str: str) -> dict:
    try:
        parts = dob_str.replace("/", "-").replace(".", "-").split("-")
        if len(parts) == 3:
            if len(parts[2]) == 4:
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            dob = date(y, m, d)
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            next_bday = date(today.year if (today.month, today.day) <= (dob.month, dob.day) else today.year + 1, dob.month, dob.day)
            days_to_bday = (next_bday - today).days
            total_days = (today - dob).days
            return {
                "age": age,
                "dob": f"{d:02d}/{m:02d}/{y}",
                "days_lived": total_days,
                "days_to_birthday": days_to_bday,
                "zodiac": get_zodiac(m, d),
                "day_of_week": dob.strftime("%A"),
            }
    except Exception:
        pass
    return {"error": "Invalid date format. Use DD/MM/YYYY"}

def get_zodiac(month: int, day: int) -> str:
    signs = [
        (1, 20, "Capricorn ♑"), (2, 19, "Aquarius ♒"), (3, 21, "Pisces ♓"),
        (4, 20, "Aries ♈"), (5, 21, "Taurus ♉"), (6, 21, "Gemini ♊"),
        (7, 23, "Cancer ♋"), (8, 23, "Leo ♌"), (9, 23, "Virgo ♍"),
        (10, 23, "Libra ♎"), (11, 22, "Scorpio ♏"), (12, 22, "Sagittarius ♐"),
        (12, 31, "Capricorn ♑"),
    ]
    for end_month, end_day, sign in signs:
        if month < end_month or (month == end_month and day <= end_day):
            return sign
    return "Capricorn ♑"

def discount_calculator(price: float, discount: float) -> dict:
    savings = price * discount / 100
    final = price - savings
    return {"original": price, "discount_pct": discount, "savings": savings, "final_price": final}

def gst_calculator(amount: float, gst_rate: float) -> dict:
    gst_amount = amount * gst_rate / 100
    total = amount + gst_amount
    return {"original": amount, "gst_rate": gst_rate, "gst_amount": gst_amount, "total": total}

def currency_convert(amount: float, from_cur: str, to_cur: str) -> dict:
    try:
        r = requests.get(f"https://api.exchangerate-api.com/v4/latest/{from_cur.upper()}", timeout=8)
        if r.status_code == 200:
            data = r.json()
            rates = data.get("rates", {})
            if to_cur.upper() in rates:
                rate = rates[to_cur.upper()]
                converted = amount * rate
                return {"amount": amount, "from": from_cur.upper(), "to": to_cur.upper(), "rate": rate, "converted": converted}
    except Exception:
        pass
    return {"error": "Currency conversion failed"}

def base64_encode(text: str) -> str:
    return base64.b64encode(text.encode()).decode()

def base64_decode(text: str) -> str:
    try:
        return base64.b64decode(text.encode()).decode()
    except Exception:
        return "Invalid Base64 string"

def case_convert(text: str, mode: str) -> str:
    modes = {
        "upper": text.upper(),
        "lower": text.lower(),
        "title": text.title(),
        "swap": text.swapcase(),
        "sentence": text.capitalize(),
    }
    return modes.get(mode, text)

def binary_to_decimal(b: str) -> str:
    try:
        return str(int(b, 2))
    except Exception:
        return "Invalid binary"

def decimal_to_binary(n: str) -> str:
    try:
        return bin(int(n))[2:]
    except Exception:
        return "Invalid number"

def hex_to_decimal(h: str) -> str:
    try:
        return str(int(h, 16))
    except Exception:
        return "Invalid hex"

def decimal_to_hex(n: str) -> str:
    try:
        return hex(int(n))[2:].upper()
    except Exception:
        return "Invalid number"

def octal_to_decimal(o: str) -> str:
    try:
        return str(int(o, 8))
    except Exception:
        return "Invalid octal"

def decimal_to_octal(n: str) -> str:
    try:
        return oct(int(n))[2:]
    except Exception:
        return "Invalid number"

def ascii_to_binary(text: str) -> str:
    return " ".join(format(ord(c), "08b") for c in text)

def binary_to_ascii(b: str) -> str:
    try:
        parts = b.strip().split()
        return "".join(chr(int(p, 2)) for p in parts)
    except Exception:
        return "Invalid binary string"

def text_to_hex(text: str) -> str:
    return text.encode().hex()

def hex_to_text(h: str) -> str:
    try:
        return bytes.fromhex(h).decode()
    except Exception:
        return "Invalid hex"

def url_encode(text: str) -> str:
    return urllib.parse.quote(text)

def url_decode(text: str) -> str:
    return urllib.parse.unquote(text)

def html_encode(text: str) -> str:
    replacements = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

def html_decode(text: str) -> str:
    replacements = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'"}
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

def word_count(text: str) -> dict:
    words = text.split()
    lines = text.split("\n")
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    return {
        "chars": len(text),
        "chars_no_spaces": len(text.replace(" ", "")),
        "words": len(words),
        "lines": len(lines),
        "sentences": len(sentences),
        "paragraphs": len([p for p in text.split("\n\n") if p.strip()]),
    }

def md5_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()

def sha256_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def temperature_convert(value: float, from_unit: str, to_unit: str) -> float:
    fu = from_unit.upper()
    tu = to_unit.upper()
    if fu == "C" and tu == "F":
        return value * 9/5 + 32
    elif fu == "F" and tu == "C":
        return (value - 32) * 5/9
    elif fu == "C" and tu == "K":
        return value + 273.15
    elif fu == "K" and tu == "C":
        return value - 273.15
    elif fu == "F" and tu == "K":
        return (value - 32) * 5/9 + 273.15
    elif fu == "K" and tu == "F":
        return (value - 273.15) * 9/5 + 32
    return value

def get_whois(domain: str) -> dict:
    try:
        clean = domain.replace("https://", "").replace("http://", "").split("/")[0]
        ip = socket.gethostbyname(clean)
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=8)
        if r.status_code == 200:
            d = r.json()
            return {
                "domain": clean,
                "ip": ip,
                "org": d.get("org", "N/A"),
                "country": d.get("country_name", "N/A"),
                "city": d.get("city", "N/A"),
                "asn": d.get("asn", "N/A"),
            }
    except Exception as e:
        return {"error": str(e), "domain": domain}
    return {"domain": domain}

def get_ssl_info(domain: str) -> dict:
    try:
        import ssl
        clean = domain.replace("https://", "").replace("http://", "").split("/")[0]
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=clean) as s:
            s.settimeout(5)
            s.connect((clean, 443))
            cert = s.getpeercert()
            return {
                "domain": clean,
                "issuer": dict(x[0] for x in cert.get("issuer", [])).get("organizationName", "N/A"),
                "subject": dict(x[0] for x in cert.get("subject", [])).get("commonName", "N/A"),
                "valid_from": cert.get("notBefore", "N/A"),
                "valid_to": cert.get("notAfter", "N/A"),
            }
    except Exception as e:
        return {"error": str(e), "domain": domain}

def cpm_calculator(impressions: float, cost: float) -> dict:
    cpm = (cost / impressions) * 1000
    return {"impressions": impressions, "cost": cost, "cpm": cpm}

def average_calculator(nums: list) -> dict:
    if not nums:
        return {"error": "No numbers provided"}
    total = sum(nums)
    avg = total / len(nums)
    return {"count": len(nums), "sum": total, "average": avg, "min": min(nums), "max": max(nums)}

def comma_separator(text: str) -> str:
    numbers = re.findall(r'\d+\.?\d*', text.replace(",", ""))
    if numbers:
        try:
            n = float(numbers[0])
            if n.is_integer():
                return f"{int(n):,}"
            return f"{n:,.2f}"
        except Exception:
            pass
    return text

def reverse_text(text: str) -> str:
    return text[::-1]

def generate_uuid() -> str:
    import uuid
    return str(uuid.uuid4())

def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def color_converter(value: str) -> dict:
    value = value.strip()
    try:
        if value.startswith("#"):
            h = value.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return {"hex": value.upper(), "rgb": f"rgb({r}, {g}, {b})", "r": r, "g": g, "b": b}
        elif value.lower().startswith("rgb"):
            nums = re.findall(r'\d+', value)
            r, g, b = int(nums[0]), int(nums[1]), int(nums[2])
            return {"hex": f"#{r:02X}{g:02X}{b:02X}", "rgb": f"rgb({r}, {g}, {b})", "r": r, "g": g, "b": b}
    except Exception:
        pass
    return {"error": "Invalid color format. Use #RRGGBB or rgb(R,G,B)"}

# ─────────────────────────── KEYBOARDS ───────────────────────────
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Carding Tools", callback_data="menu_carding"),
         InlineKeyboardButton("🔒 Disposable Tools", callback_data="menu_disposable")],
        [InlineKeyboardButton("🌐 Website Tools", callback_data="menu_website"),
         InlineKeyboardButton("🔧 Developer Tools", callback_data="menu_devtools")],
        [InlineKeyboardButton("🔢 Number & Math", callback_data="menu_math"),
         InlineKeyboardButton("📝 Text Tools", callback_data="menu_text")],
        [InlineKeyboardButton("🔄 Converters", callback_data="menu_converters"),
         InlineKeyboardButton("💰 Finance Tools", callback_data="menu_finance")],
        [InlineKeyboardButton("💎 My Credits", callback_data="my_credits"),
         InlineKeyboardButton("👑 Premium Info", callback_data="premium_info")],
        [InlineKeyboardButton("🔗 Referral Program", callback_data="referral_menu"),
         InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard_menu")],
        [InlineKeyboardButton("🎁 Daily Claim", callback_data="claim_daily"),
         InlineKeyboardButton("🎰 Games & Betting", callback_data="menu_games")],
        [InlineKeyboardButton("₿ Crypto Prices", callback_data="crypto_refresh"),
         InlineKeyboardButton("🔌 Port Scanner", callback_data="menu_ports")],
        [InlineKeyboardButton("🃏 CC Extractor", callback_data="tool_ccextrap"),
         InlineKeyboardButton("💬 Feedback", callback_data="feedback_prompt")],
        [InlineKeyboardButton("📜 Disclaimer", callback_data="disclaimer"),
         InlineKeyboardButton("ℹ️ About Bot", callback_data="about")],
    ])

def carding_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 BIN Checker", callback_data="tool_binchk"),
         InlineKeyboardButton("🔎 BIN Finder", callback_data="tool_binfind")],
        [InlineKeyboardButton("⚙️ CC Generator", callback_data="tool_ccgen"),
         InlineKeyboardButton("✅ CC Checker (Luhn)", callback_data="tool_cchk")],
        [InlineKeyboardButton("📦 Bulk CC Gen", callback_data="tool_bulkgen"),
         InlineKeyboardButton("🔗 BIN Share Info", callback_data="tool_binshare")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])

def disposable_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📧 Temp Email", callback_data="tool_tempmail"),
         InlineKeyboardButton("📥 Check Inbox", callback_data="tool_inbox")],
        [InlineKeyboardButton("👤 Fake Address", callback_data="tool_fakeaddr"),
         InlineKeyboardButton("🔑 Password Gen", callback_data="tool_passgen")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])

def website_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Site Status", callback_data="tool_sitestatus"),
         InlineKeyboardButton("🌍 IP Lookup", callback_data="tool_iplookup")],
        [InlineKeyboardButton("🔒 SSL Info", callback_data="tool_ssl"),
         InlineKeyboardButton("📋 WHOIS Info", callback_data="tool_whois")],
        [InlineKeyboardButton("🔗 URL Encode", callback_data="tool_urlencode"),
         InlineKeyboardButton("🔗 URL Decode", callback_data="tool_urldecode")],
        [InlineKeyboardButton("🌐 HTML Encode", callback_data="tool_htmlenc"),
         InlineKeyboardButton("🌐 HTML Decode", callback_data="tool_htmldec")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])

def devtools_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Base64 Encode", callback_data="tool_b64enc"),
         InlineKeyboardButton("📦 Base64 Decode", callback_data="tool_b64dec")],
        [InlineKeyboardButton("#️⃣ MD5 Hash", callback_data="tool_md5"),
         InlineKeyboardButton("🔐 SHA256 Hash", callback_data="tool_sha256")],
        [InlineKeyboardButton("🆔 UUID Gen", callback_data="tool_uuid"),
         InlineKeyboardButton("✉️ Email Validator", callback_data="tool_emailval")],
        [InlineKeyboardButton("🎨 Color Converter", callback_data="tool_color"),
         InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])

def math_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Age Calculator", callback_data="tool_age"),
         InlineKeyboardButton("📊 Average Calc", callback_data="tool_avg")],
        [InlineKeyboardButton("🔢 Bin→Dec", callback_data="tool_bin2dec"),
         InlineKeyboardButton("🔢 Dec→Bin", callback_data="tool_dec2bin")],
        [InlineKeyboardButton("🔡 Hex→Dec", callback_data="tool_hex2dec"),
         InlineKeyboardButton("🔡 Dec→Hex", callback_data="tool_dec2hex")],
        [InlineKeyboardButton("🔣 Oct→Dec", callback_data="tool_oct2dec"),
         InlineKeyboardButton("🔣 Dec→Oct", callback_data="tool_dec2oct")],
        [InlineKeyboardButton("📡 Bin→ASCII", callback_data="tool_bin2ascii"),
         InlineKeyboardButton("📡 ASCII→Bin", callback_data="tool_ascii2bin")],
        [InlineKeyboardButton("🔤 Text→Hex", callback_data="tool_text2hex"),
         InlineKeyboardButton("🔤 Hex→Text", callback_data="tool_hex2text")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])

def text_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔠 Uppercase", callback_data="tool_upper"),
         InlineKeyboardButton("🔡 Lowercase", callback_data="tool_lower")],
        [InlineKeyboardButton("📝 Title Case", callback_data="tool_title"),
         InlineKeyboardButton("🔀 Swap Case", callback_data="tool_swap")],
        [InlineKeyboardButton("↩️ Reverse Text", callback_data="tool_reverse"),
         InlineKeyboardButton("📊 Word Count", callback_data="tool_wordcount")],
        [InlineKeyboardButton("📋 Comma Sep", callback_data="tool_comma"),
         InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])

def converters_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌡️ Temperature", callback_data="tool_temp"),
         InlineKeyboardButton("💱 Currency", callback_data="tool_currency")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])

def finance_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏷️ Discount Calc", callback_data="tool_discount"),
         InlineKeyboardButton("🧾 GST Calculator", callback_data="tool_gst")],
        [InlineKeyboardButton("📢 CPM Calculator", callback_data="tool_cpm"),
         InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])

def back_main_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]])

def back_carding_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Carding Tools", callback_data="menu_carding"), InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]])

# ─────────────────────────── MESSAGE TEMPLATES ───────────────────────────
def header(title: str) -> str:
    return f"╔{'═' * (len(title) + 4)}╗\n║  {title}  ║\n╚{'═' * (len(title) + 4)}╝"

def credits_warning(credits: int) -> str:
    if credits <= 2:
        return f"\n⚠️ *Low Credits:* {credits} remaining!"
    return ""

DISCLAIMER_TEXT = f"""
{DLINE}
⚠️ *DISCLAIMER — READ CAREFULLY* ⚠️
{DLINE}

*{BOT_NAME}*

🔴 This bot is provided for *EDUCATIONAL PURPOSES ONLY*.

📚 All tools, features, and information are intended solely for:
• Learning and research purposes
• Testing and development environments
• Educational demonstrations

🚫 *PROHIBITED USES:*
• Fraud or financial crimes of any kind
• Unauthorized access to systems
• Any illegal activities
• Bypassing security systems

⚖️ *LEGAL NOTICE:*
The developer *@{DEVELOPER_USERNAME}* and this bot take *NO responsibility* for any misuse, damage, or illegal activities performed using this bot.

By using this bot, you agree that:
• You are solely responsible for your actions
• You will use tools only for legal, ethical purposes
• You understand the educational intent

🛡️ *USE RESPONSIBLY. STAY LEGAL.*
{DLINE}
"""

# ─────────────────────────── HANDLERS ───────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # ── Handle referral deep-link: /start <ref_code> ──
    ref_code_arg = context.args[0] if context.args else None
    db_user = get_user(user.id, user.username or "")   # creates user if new
    is_dev = is_developer(user.id, user.username or "")
    is_prem = is_user_premium(user.id)
    bonus_msg = ""

    if ref_code_arg:
        referrer_id = get_user_by_ref_code(ref_code_arg)
        if referrer_id and referrer_id != user.id:
            data = load_data()
            already_referred = data["users"].get(str(user.id), {}).get("referred_by") is not None
            if not already_referred:
                await process_referral(context, user.id, referrer_id)
                db_user = get_user(user.id)  # reload with updated credits
                bonus_msg = (
                    f"\n🎁 *Referral Bonus Applied!*\n"
                    f"   You received `+{REFERRAL_BONUS_NEW_USER}` bonus credits!\n"
                )

    badge = f"{CROWN} DEVELOPER" if is_dev else (f"{GEM} PREMIUM" if is_prem else f"{STAR2} FREE USER")

    welcome = f"""
╔══════════════════════════════╗
║  {BOT_NAME}  
╚══════════════════════════════╝

{BOLT} *Welcome, {user.first_name}!* {BOLT}

{LINE}
{DIAMOND} *Status:* `{badge}`
{DIAMOND} *Credits:* `{db_user['credits']}` {"(∞ Unlimited)" if is_dev else ""}
{DIAMOND} *Member Since:* `{db_user.get('joined', 'Today')}`
{LINE}{bonus_msg}
🚀 *{BOT_NAME}* — Your all-in-one God Mode toolkit:

💳 *Carding Tools* — BIN Check, CC Gen, Luhn
🔒 *Disposable Tools* — Temp Mail, Fake Address
🌐 *Website Tools* — Status, IP, SSL, WHOIS
🔧 *Developer Tools* — Hash, Base64, UUID
🔢 *Math & Number* — Conversions, Calculators
📝 *Text Tools* — Case, Count, Reverse
🔄 *Converters* — Temperature, Currency
💰 *Finance Tools* — Discount, GST, CPM
🌍 *World Monitor* — Live global news (5 credits)
📡 *Subscribe* — Auto news to your DM (1h/6h/12h/24h)
🌤 *Weather* — Live weather, any city worldwide
📈 *Stocks* — Real-time stock + crypto prices
🌐 *Translator* — 30+ languages via AI
📖 *Dictionary* — Definitions + examples
😂 *Jokes & Facts* — Free, unlimited fun
🔲 *QR Generator* — Text, URL, or any FILE → QR
🧠 *Trivia Quiz* — Bet credits, win 2× back
🔐 *Password Gen* — Unbreakable passwords
🕐 *World Clock* — Time in any city/timezone
🧮 *Calculator* — Safe math evaluator (free)
🎭 *Random Identity* — Full fake name + details
🌐 *IP Geolocation* — Deep IP lookup
🔓 *Hash Lookup* — Reverse MD5 decryption
✂️ *URL Shortener* — Shorten any link instantly
🔗 *Referral Program* — Earn credits by inviting friends

{WARN} *For Educational Purposes Only*
Use /disclaimer to read full terms.

{LINE}
🎯 *Select a category below:*
"""
    await update.message.reply_text(
        welcome, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard()
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""
{CROWN} *{BOT_NAME}* — Command Reference
{LINE}

📋 *GENERAL COMMANDS*
`/start` — Main menu & welcome
`/help` — This help message
`/credits` — Check your credits
`/premium` — Premium info & benefits
`/disclaimer` — Read disclaimer

{LINE}
💳 *CARDING TOOLS* _(1 credit each)_
`/bin <number>` — BIN Checker
`/gen <bin> [qty]` — CC Generator
`/chk <card>` — CC Luhn Checker
`/bulkgen <bin> <qty>` — Bulk CC Gen

{LINE}
🔒 *DISPOSABLE TOOLS* _(1 credit each)_
`/tempmail` — Generate temp email
`/inbox <email>` — Check inbox
`/fakeaddr` — Fake address (US)
`/passgen [length]` — Password gen

{LINE}
🌐 *WEBSITE TOOLS* _(1 credit each)_
`/status <url>` — Website status
`/iplookup <host>` — IP lookup
`/ssl <domain>` — SSL info
`/whois <domain>` — WHOIS lookup

{LINE}
🔧 *DEVELOPER TOOLS* _(1 credit each)_
`/b64enc <text>` — Base64 encode
`/b64dec <text>` — Base64 decode
`/md5 <text>` — MD5 hash
`/sha256 <text>` — SHA256 hash
`/uuid` — Generate UUID
`/emailval <email>` — Validate email
`/color <#hex or rgb>` — Color convert

{LINE}
🔢 *MATH TOOLS* _(1 credit each)_
`/age <DD/MM/YYYY>` — Age calculator
`/avg <n1> <n2> ...` — Average calc
`/bin2dec <binary>` — Binary to decimal
`/dec2bin <number>` — Decimal to binary
`/hex2dec <hex>` — Hex to decimal
`/dec2hex <number>` — Decimal to hex
`/oct2dec <octal>` — Octal to decimal
`/dec2oct <number>` — Decimal to octal
`/bin2ascii <binary>` — Binary to ASCII
`/ascii2bin <text>` — ASCII to binary
`/text2hex <text>` — Text to hex
`/hex2text <hex>` — Hex to text

{LINE}
📝 *TEXT TOOLS* _(1 credit each)_
`/upper <text>` — UPPERCASE
`/lower <text>` — lowercase
`/title <text>` — Title Case
`/swapcase <text>` — sWaP cAsE
`/reverse <text>` — Reverse text
`/wordcount <text>` — Word/char count
`/commasep <number>` — Comma format

{LINE}
🔄 *CONVERTER TOOLS* _(1 credit each)_
`/temp <val> <C/F/K> <C/F/K>` — Temperature
`/currency <amt> <FROM> <TO>` — Currency

{LINE}
💰 *FINANCE TOOLS* _(1 credit each)_
`/discount <price> <pct>` — Discount
`/gst <amount> <rate>` — GST calculator
`/cpm <impressions> <cost>` — CPM calc

{LINE}
💎 *CREDITS SYSTEM*
• Free: `10 credits/day` (auto-reset)
• Premium: `100 credits/day`
• Developer: `∞ Unlimited`

{LINE}
{WARN} _For Educational Purposes Only_
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def cmd_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    is_dev = is_developer(user.id, user.username or "")
    ref_code = db_user.get("ref_code") or generate_ref_code(user.id)
    referrals   = db_user.get("referrals", 0)
    ref_earned  = db_user.get("ref_credits_earned", 0)
    referred_by = db_user.get("referred_by")

    # Build the deep-link URL (works once the bot is set up)
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    ref_link = f"https://t.me/{bot_username}?start={ref_code}"

    text = f"""
╔══════════════════════════════╗
║    🔗 REFERRAL PROGRAM       ║
╚══════════════════════════════╝

{ROCKET} *Invite friends & earn free credits!*
{LINE}
🎯 *Your Referral Code:*
`{ref_code}`

🔗 *Your Referral Link:*
`{ref_link}`

{LINE}
📊 *Your Referral Stats:*
{DIAMOND} Total Referrals: `{referrals}`
{BOLT} Credits Earned: `{ref_earned}`
{DIAMOND} Referred By: `{"Someone ✅" if referred_by else "Nobody yet"}`

{LINE}
💎 *Reward System:*
{BULLET} You earn `+{REFERRAL_BONUS_REFERRER} credits` per referral
{BULLET} Your friend gets `+{REFERRAL_BONUS_NEW_USER} bonus credits`
{BULLET} No limit — refer as many as you want!
{BULLET} Credits are added instantly

{LINE}
📋 *How It Works:*
1️⃣ Copy your referral link above
2️⃣ Share it with your friends
3️⃣ When they start the bot → you both get credits!
4️⃣ Check your balance with /credits

{LINE}
💰 *Your Credits:* `{db_user['credits']}` {"(∞)" if is_dev else ""}
"""
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share My Link", switch_inline_query=f"Join {BOT_NAME} with my link: {ref_link}")],
        [InlineKeyboardButton("🔄 Refresh Stats", callback_data="referral_menu"),
         InlineKeyboardButton("💎 My Credits", callback_data="my_credits")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

def build_leaderboard_text(caller_id: int) -> str:
    """Build leaderboard text ranked by referrals then total_used."""
    all_users = get_all_users()
    # Sort: most referrals first, tie-break by total commands used
    ranked = sorted(all_users, key=lambda u: (u.get("referrals", 0), u.get("total_used", 0)), reverse=True)
    top = ranked[:10]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = []
    caller_rank = None
    for i, u in enumerate(ranked):
        if u["user_id"] == caller_id:
            caller_rank = i + 1
            break
    for i, u in enumerate(top):
        uname = f"@{u['username']}" if u.get("username") else f"User#{u['user_id']}"
        refs   = u.get("referrals", 0)
        used   = u.get("total_used", 0)
        badge  = "👑" if is_developer(u["user_id"]) else ("💎" if u.get("premium") else "⭐")
        marker = " ◀ YOU" if u["user_id"] == caller_id else ""
        lines.append(f"{medals[i]} {badge} `{uname[:18]}`\n    ├ Referrals: `{refs}` | Used: `{used}`{marker}")
    board = "\n\n".join(lines) if lines else "_No users yet._"
    your_rank = f"\n{LINE}\n🎯 *Your Rank:* `#{caller_rank}` out of `{len(ranked)}`" if caller_rank else f"\n{LINE}\n🎯 *Your Rank:* Not ranked yet"
    return f"""
╔══════════════════════════════╗
║    🏆 REFERRAL LEADERBOARD   ║
╚══════════════════════════════╝

{ROCKET} *Top 10 — Ranked by Referrals*
{LINE}

{board}
{your_rank}
{LINE}
_Invite friends with /referral to climb the ranks!_
"""

async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    text = build_leaderboard_text(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 My Referral Link", callback_data="referral_menu"),
         InlineKeyboardButton("🔄 Refresh", callback_data="leaderboard_menu")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

# ═══════════════════════════════════════════════
# FEATURE: DAILY CLAIM
# ═══════════════════════════════════════════════
async def cmd_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    uid = str(user.id)
    db_user = get_user(user.id, user.username or "")
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))

    last_claim = db_user.get("last_claim")
    streak = db_user.get("streak", 0)

    if last_claim == today:
        next_claim = (date.today() + timedelta(days=1)).strftime("%d %b %Y")
        streak_bar = "🔥" * min(streak, 10)
        await update.message.reply_text(
            f"⏳ *Already Claimed Today!*\n{LINE}\n"
            f"🔥 Current Streak: {streak_bar} `{streak} days`\n"
            f"⏰ Next Claim: `{next_claim}`\n{LINE}\n"
            f"_Come back tomorrow to keep your streak!_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]),
        )
        return

    if last_claim == yesterday:
        streak += 1
    else:
        streak = 1

    base = CLAIM_BASE_CREDITS
    streak_bonus = min((streak // 5) * CLAIM_STREAK_BONUS_PER_5, CLAIM_MAX_BONUS)
    total = base + streak_bonus

    data["users"][uid]["last_claim"] = today
    data["users"][uid]["streak"] = streak
    data["users"][uid]["credits"] = db_user.get("credits", 0) + total
    save_data(data)

    streak_bar = "🔥" * min(streak, 10)
    milestone = f"\n🏅 *{streak}-Day Milestone! Keep going!*" if streak % 7 == 0 else ""
    track_tool_usage("claim")
    await update.message.reply_text(
        f"🎁 *Daily Reward Claimed!*\n{LINE}\n"
        f"⚡ Base Credits: `+{base}`\n"
        f"🔥 Streak Bonus: `+{streak_bonus}` ({streak}-day streak)\n"
        f"💰 Total Earned: `+{total} credits`\n{LINE}\n"
        f"🔥 Streak: {streak_bar} `{streak} days`\n"
        f"💎 Balance: `{data['users'][uid]['credits']} credits`"
        f"{milestone}\n{LINE}\n_Come back tomorrow!_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 My Credits", callback_data="my_credits"),
             InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard_menu")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ]),
    )

# ═══════════════════════════════════════════════
# FEATURE: GAMES (DICE + COIN FLIP)
# ═══════════════════════════════════════════════
async def cmd_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    is_dev = is_developer(user.id, user.username or "")

    if not context.args:
        await update.message.reply_text(
            f"🎲 *Dice Game*\n{LINE}\n"
            f"Usage: `/dice <bet>`\n\n"
            f"▸ Roll *4-6* → Win `2×` your bet 🎉\n"
            f"▸ Roll *1-3* → Lose your bet 😢\n\n"
            f"Min bet: `{GAME_MIN_BET}` | Max bet: `{GAME_MAX_BET}`\n"
            f"Your credits: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text(f"{CROSS} Bet must be a whole number.", parse_mode=ParseMode.MARKDOWN)
        return

    if not (GAME_MIN_BET <= bet <= GAME_MAX_BET):
        await update.message.reply_text(
            f"{CROSS} Bet must be between `{GAME_MIN_BET}` and `{GAME_MAX_BET}` credits.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if db_user["credits"] < bet and not is_dev:
        await update.message.reply_text(
            f"{CROSS} Not enough credits! You have `{db_user['credits']}` but bet `{bet}`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    roll = random.randint(1, 6)
    faces = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}
    face = faces[roll]
    data = load_data()
    uid = str(user.id)
    cur = db_user["credits"]

    if roll >= 4:
        new_credits = cur + bet if not is_dev else cur
        result_text = f"🎉 *YOU WIN!*\n{face} Rolled `{roll}` — High roll!\n\n💰 Won: `+{bet} credits`"
    else:
        new_credits = max(0, cur - bet) if not is_dev else cur
        result_text = f"😢 *YOU LOSE!*\n{face} Rolled `{roll}` — Low roll!\n\n💸 Lost: `-{bet} credits`"

    data["users"][uid]["credits"] = new_credits
    save_data(data)
    track_tool_usage("dice")
    await update.message.reply_text(
        f"🎲 *DICE GAME*\n{LINE}\n{result_text}\n\n💎 Balance: `{new_credits} credits`\n{LINE}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🎲 Roll Again ({bet} bet)", callback_data=f"dice_again_{bet}")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ]),
    )

async def cmd_flip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    is_dev = is_developer(user.id, user.username or "")

    if len(context.args) < 2:
        await update.message.reply_text(
            f"🪙 *Coin Flip Game*\n{LINE}\n"
            f"Usage: `/flip <bet> <h or t>`\n\n"
            f"Pick *heads* (`h`) or *tails* (`t`)!\n"
            f"▸ Correct → Win `2×` your bet 🎉\n"
            f"▸ Wrong   → Lose your bet 😢\n\n"
            f"Min bet: `{GAME_MIN_BET}` | Max bet: `{GAME_MAX_BET}`\n"
            f"Your credits: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text(f"{CROSS} Bet must be a whole number.", parse_mode=ParseMode.MARKDOWN)
        return

    choice = context.args[1].lower().strip()
    if choice not in ("h", "t", "heads", "tails"):
        await update.message.reply_text(f"{CROSS} Pick `h` (heads) or `t` (tails).", parse_mode=ParseMode.MARKDOWN)
        return

    if not (GAME_MIN_BET <= bet <= GAME_MAX_BET):
        await update.message.reply_text(
            f"{CROSS} Bet between `{GAME_MIN_BET}` and `{GAME_MAX_BET}`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if db_user["credits"] < bet and not is_dev:
        await update.message.reply_text(
            f"{CROSS} Not enough credits! You have `{db_user['credits']}`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    result = random.choice(("h", "t"))
    chose_heads = choice.startswith("h")
    landed_heads = result == "h"
    won = chose_heads == landed_heads

    coin_show   = "🪙 *HEADS*" if landed_heads else "🪙 *TAILS*"
    choice_show = "Heads" if chose_heads else "Tails"
    data = load_data()
    uid = str(user.id)
    cur = db_user["credits"]

    if won:
        new_credits = cur + bet if not is_dev else cur
        result_text = f"🎉 *YOU WIN!*\n{coin_show}\nYou picked `{choice_show}` ✅\n\n💰 Won: `+{bet} credits`"
    else:
        new_credits = max(0, cur - bet) if not is_dev else cur
        result_text = f"😢 *YOU LOSE!*\n{coin_show}\nYou picked `{choice_show}` ❌\n\n💸 Lost: `-{bet} credits`"

    data["users"][uid]["credits"] = new_credits
    save_data(data)
    track_tool_usage("flip")
    await update.message.reply_text(
        f"🪙 *COIN FLIP*\n{LINE}\n{result_text}\n\n💎 Balance: `{new_credits} credits`\n{LINE}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🪙 Flip Again ({bet} bet)", callback_data=f"flip_again_{bet}_{choice[0]}")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ]),
    )

# ═══════════════════════════════════════════════
# FEATURE: PROMO CODES
# ═══════════════════════════════════════════════
async def cmd_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")

    if not context.args:
        await update.message.reply_text(
            f"🎫 *Redeem a Promo Code*\n{LINE}\nUsage: `/redeem <CODE>`\n\n"
            f"_Get codes from @{DEVELOPER_USERNAME}_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    code = context.args[0].upper().strip()
    data = load_data()
    codes = data.get("promo_codes", {})

    if code not in codes:
        await update.message.reply_text(
            f"{CROSS} *Invalid code!* `{code}` does not exist.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    promo = codes[code]
    uid = str(user.id)

    if promo.get("uses", 0) >= promo.get("max_uses", 1):
        await update.message.reply_text(
            f"{CROSS} This code has *expired* — all uses have been claimed.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if uid in promo.get("used_by", []):
        await update.message.reply_text(
            f"{CROSS} You have *already redeemed* this code!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    credits_granted = promo["credits"]
    data["users"][uid]["credits"] = db_user.get("credits", 0) + credits_granted
    promo.setdefault("used_by", []).append(uid)
    promo["uses"] = promo.get("uses", 0) + 1
    data["promo_codes"][code] = promo
    save_data(data)
    track_tool_usage("redeem")

    new_bal = data["users"][uid]["credits"]
    remaining = promo["max_uses"] - promo["uses"]
    await update.message.reply_text(
        f"{CHECK} *Code Redeemed!*\n{LINE}\n"
        f"🎫 Code: `{code}`\n"
        f"⚡ Credits Added: `+{credits_granted}`\n"
        f"💎 New Balance: `{new_bal}`\n"
        f"♾️ Remaining Uses: `{remaining}`\n{LINE}\n"
        f"_Keep an eye out for more codes from @{DEVELOPER_USERNAME}!_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]),
    )

async def cmd_createcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Developer only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 3:
        await update.message.reply_text(
            f"{WARN} Usage: `/createcode <CODE> <credits> <max_uses>`\n"
            f"Example: `/createcode LAUNCH50 50 100`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    code = context.args[0].upper().strip()
    try:
        credits = int(context.args[1])
        max_uses = int(context.args[2])
    except ValueError:
        await update.message.reply_text(f"{CROSS} Credits and max_uses must be numbers.", parse_mode=ParseMode.MARKDOWN)
        return
    data = load_data()
    data["promo_codes"][code] = {
        "credits": credits, "max_uses": max_uses, "uses": 0,
        "used_by": [], "created_by": user.id, "created_at": str(date.today()),
    }
    save_data(data)
    await update.message.reply_text(
        f"{CHECK} *Promo Code Created!*\n{LINE}\n"
        f"🎫 Code: `{code}`\n⚡ Credits: `{credits}`\n♾️ Max Uses: `{max_uses}`\n{LINE}\n"
        f"Share: `/redeem {code}`",
        parse_mode=ParseMode.MARKDOWN,
    )

async def cmd_listcodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Developer only.", parse_mode=ParseMode.MARKDOWN)
        return
    data = load_data()
    codes = data.get("promo_codes", {})
    if not codes:
        await update.message.reply_text(
            f"{INFO} No promo codes yet. Create one with `/createcode`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    lines = []
    for code, info in codes.items():
        uses, max_u, cr = info.get("uses",0), info.get("max_uses",1), info.get("credits",0)
        status = "✅" if uses < max_u else "❌ Expired"
        lines.append(f"`{code}` → `{cr}`cr | `{uses}/{max_u}` uses | {status}")
    await update.message.reply_text(
        f"{CROWN} *Promo Codes ({len(codes)} total)*\n{LINE}\n" + "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )

async def cmd_deletecode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Developer only.", parse_mode=ParseMode.MARKDOWN)
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/deletecode <CODE>`", parse_mode=ParseMode.MARKDOWN)
        return
    code = context.args[0].upper().strip()
    data = load_data()
    if code not in data.get("promo_codes", {}):
        await update.message.reply_text(f"{CROSS} Code `{code}` not found.", parse_mode=ParseMode.MARKDOWN)
        return
    del data["promo_codes"][code]
    save_data(data)
    await update.message.reply_text(f"{CHECK} Code `{code}` deleted.", parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════
# FEATURE: FEEDBACK
# ═══════════════════════════════════════════════
async def cmd_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")

    if not context.args:
        await update.message.reply_text(
            f"💬 *Send Feedback*\n{LINE}\n"
            f"Usage: `/feedback <message>`\n\n"
            f"Report bugs, suggest features, or send anything to @{DEVELOPER_USERNAME}!\n"
            f"_Max 500 characters._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    msg_text = " ".join(context.args).strip()
    if len(msg_text) < 5:
        await update.message.reply_text(f"{CROSS} Message too short. Please be descriptive.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(msg_text) > 500:
        await update.message.reply_text(f"{CROSS} Too long! Max 500 characters.", parse_mode=ParseMode.MARKDOWN)
        return

    data = load_data()
    data["feedback"].append({
        "user_id": user.id,
        "username": user.username or "",
        "name": user.first_name,
        "message": msg_text,
        "date": str(date.today()),
    })
    save_data(data)
    track_tool_usage("feedback")

    uname = f"@{user.username}" if user.username else f"User#{user.id}"
    dev_msg = (
        f"📨 *New Feedback!*\n{LINE}\n"
        f"👤 From: {uname} (`{user.id}`)\n"
        f"📅 Date: `{date.today()}`\n{LINE}\n"
        f"💬 *Message:*\n_{msg_text}_"
    )
    for dev_id in data.get("developer_ids", []):
        try:
            await context.bot.send_message(dev_id, dev_msg, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

    preview = msg_text[:100] + ("…" if len(msg_text) > 100 else "")
    await update.message.reply_text(
        f"{CHECK} *Feedback Sent!*\n{LINE}\n"
        f"Thank you! @{DEVELOPER_USERNAME} will review it.\n{LINE}\n"
        f"💬 Your message:\n_\"{preview}\"_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]),
    )

async def cmd_viewfeedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Developer only.", parse_mode=ParseMode.MARKDOWN)
        return
    data = load_data()
    fb_list = data.get("feedback", [])
    if not fb_list:
        await update.message.reply_text(f"{INFO} No feedback received yet.", parse_mode=ParseMode.MARKDOWN)
        return
    recent = list(reversed(fb_list[-5:]))
    lines = []
    for fb in recent:
        uname = f"@{fb['username']}" if fb.get("username") else f"User#{fb['user_id']}"
        lines.append(f"👤 {uname} | {fb.get('date','')}\n💬 _{fb['message'][:120]}_\n")
    await update.message.reply_text(
        f"{CROWN} *Feedback ({len(fb_list)} total — last 5)*\n{LINE}\n\n" + "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )

# ═══════════════════════════════════════════════
# FEATURE: LIVE CRYPTO PRICES
# ═══════════════════════════════════════════════
CRYPTO_COINS = {
    "bitcoin":     ("₿ Bitcoin",   "BTC"),
    "ethereum":    ("⟠ Ethereum",  "ETH"),
    "tether":      ("💵 Tether",   "USDT"),
    "binancecoin": ("🔶 BNB",      "BNB"),
    "solana":      ("◎ Solana",    "SOL"),
    "dogecoin":    ("🐕 Dogecoin", "DOGE"),
    "ripple":      ("💧 XRP",      "XRP"),
}

def build_crypto_text(prices: dict) -> str:
    def fmt_price(p):
        return f"${p:,.2f}" if p >= 1 else f"${p:.6f}"
    def fmt_change(c):
        arrow = "📈" if c >= 0 else "📉"
        return f"{arrow} `{c:+.2f}%`"
    lines = []
    for cid, (name, ticker) in CRYPTO_COINS.items():
        if cid in prices:
            p = prices[cid]
            price = p.get("usd", 0)
            change = p.get("usd_24h_change") or 0.0
            lines.append(f"{name} *({ticker})*\n  💰 `{fmt_price(price)}`  {fmt_change(change)}")
    ts = datetime.now().strftime("%H:%M:%S")
    return (
        f"╔══════════════════════════════╗\n"
        f"║    ₿ LIVE CRYPTO PRICES      ║\n"
        f"╚══════════════════════════════╝\n"
        f"_Live prices • 24h change_\n{LINE}\n\n"
        + "\n\n".join(lines)
        + f"\n\n{LINE}\n🕐 _Updated: {ts} UTC_"
    )

async def cmd_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    msg = await update.message.reply_text("₿ _Fetching live crypto prices…_", parse_mode=ParseMode.MARKDOWN)
    prices = get_crypto_prices()
    if "error" in prices:
        await msg.edit_text(
            f"{CROSS} *Failed to fetch prices*\nError: `{prices['error']}`\n_Try again in a moment._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    text = build_crypto_text(prices)
    track_tool_usage("crypto")
    await msg.edit_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh Prices", callback_data="crypto_refresh")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ]),
    )

# ═══════════════════════════════════════════════
# FEATURE: CC EXTRACTOR
# ═══════════════════════════════════════════════
async def cmd_ccextrap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(
            f"🃏 *CC Extractor*\n{LINE}\n"
            f"Usage: `/ccextrap <card>`\n\n"
            f"Supported formats:\n"
            f"▸ `4111111111111111|01|2025|123`\n"
            f"▸ `4111111111111111 01 2025 123`\n"
            f"▸ `4111111111111111|01|25|123`\n"
            f"▸ Just the card number alone\n{LINE}\n"
            f"_Costs 1 credit per use_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    raw = " ".join(context.args).strip()
    normalized = re.sub(r"[\s/\\]+", "|", raw)
    parts = normalized.split("|")
    card_num = re.sub(r"\D", "", parts[0])
    if len(card_num) < 13:
        await update.message.reply_text(f"{CROSS} Invalid card number (too short).", parse_mode=ParseMode.MARKDOWN)
        return
    month = parts[1].zfill(2) if len(parts) > 1 else "??"
    year  = parts[2]          if len(parts) > 2 else "????"
    cvv   = parts[3]          if len(parts) > 3 else "???"
    if year != "????" and len(year) == 2:
        year = "20" + year
    bin_num  = card_num[:6]
    bin_info = get_bin_info(bin_num)
    valid    = luhn_check(card_num)
    masked   = card_num[:6] + "×" * (len(card_num) - 10) + card_num[-4:]
    brand    = bin_info.get("brand", "Unknown")
    if not brand or brand == "N/A":
        first2 = card_num[:2]
        if card_num[0] == "4":        brand = "Visa"
        elif first2 in ("51","52","53","54","55"): brand = "Mastercard"
        elif first2 in ("34","37"):   brand = "Amex"
        elif card_num[0] == "6":      brand = "Discover"
        elif card_num[:4] in ("3528","3589"): brand = "JCB"
    db_user = get_user(user.id)
    track_tool_usage("ccextrap")
    await update.message.reply_text(
        f"🃏 *CC EXTRACTOR*\n{LINE}\n"
        f"💳 Card: `{masked}`\n"
        f"📏 Length: `{len(card_num)} digits`\n"
        f"🔢 BIN: `{bin_num}`\n"
        f"📅 Expiry: `{month}/{year}`\n"
        f"🔑 CVV: `{cvv}`\n"
        f"{LINE}\n"
        f"🏦 Bank: `{bin_info.get('bank','N/A')}`\n"
        f"🌍 Country: `{bin_info.get('country','N/A')}`\n"
        f"💳 Brand: `{brand}`\n"
        f"🃏 Type: `{bin_info.get('type','N/A')}`\n"
        f"📊 Level: `{bin_info.get('level','N/A')}`\n"
        f"{LINE}\n"
        f"{'✅ LUHN VALID' if valid else '❌ LUHN INVALID'}\n"
        f"💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(),
    )

# ═══════════════════════════════════════════════
# FEATURE: ANALYTICS (DEV)
# ═══════════════════════════════════════════════
async def cmd_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Developer only.", parse_mode=ParseMode.MARKDOWN)
        return
    data = load_data()
    stats = data.get("tool_stats", {})
    all_u = get_all_users()
    total_cmds = sum(u.get("total_used", 0) for u in all_u)
    if not stats:
        await update.message.reply_text(
            f"{INFO} No analytics data yet.\n_Start using tools to generate stats._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    top20 = sorted_stats[:20]
    lines = [f"  `{tool}`: `{count}` uses" for tool, count in top20]
    total_tracked = sum(stats.values())
    await update.message.reply_text(
        f"{CROWN} *Tool Usage Analytics*\n{LINE}\n"
        f"📊 Total Tool Calls (tracked): `{total_tracked}`\n"
        f"⚡ Total Commands (all users): `{total_cmds}`\n"
        f"👥 Total Users: `{len(all_u)}`\n{LINE}\n"
        f"*Top Tools:*\n" + "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )

# ════════════════════════════════════════════════
# FEATURE: SLOTS 🎰
# ════════════════════════════════════════════════
SLOT_SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣", "⭐"]
SLOT_WEIGHTS  = [30,   25,   20,   15,   5,    3,    2  ]
SLOT_JACKPOTS = {
    ("7️⃣","7️⃣","7️⃣"): ("💥 JACKPOT! TRIPLE 7s!", 50),
    ("💎","💎","💎"):   ("💎 DIAMOND JACKPOT!",     20),
    ("⭐","⭐","⭐"):   ("⭐ STAR JACKPOT!",          10),
}

def spin_slot() -> list:
    return random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=3)

def evaluate_slot(reels: list, bet: int):
    t = tuple(reels)
    if t in SLOT_JACKPOTS:
        label, mult = SLOT_JACKPOTS[t]
        return label, mult, bet * mult
    if reels[0] == reels[1] == reels[2]:
        return f"🎊 TRIPLE {reels[0]}!", 5, bet * 5
    if reels[0]==reels[1] or reels[1]==reels[2] or reels[0]==reels[2]:
        return "✨ Double Match!", 2, bet * 2
    return "💸 No Match", 0, 0

async def _do_slots(send_fn, user_id: int, username: str, bet: int, edit: bool = False):
    db_user = get_user(user_id, username)
    is_dev  = is_developer(user_id, username)
    if db_user["credits"] < bet and not is_dev:
        return False, f"{CROSS} Not enough credits! You have `{db_user['credits']}`.", None
    reels = spin_slot()
    label, mult, _ = evaluate_slot(reels, bet)
    won = mult > 0
    data = load_data()
    uid  = str(user_id)
    cur  = db_user["credits"]
    if won:
        net = bet * mult - bet
        nc  = cur + net if not is_dev else cur
        result = f"🎉 *{label}*\n💰 Won: `+{net} credits` (`{mult}×`)"
    else:
        nc  = max(0, cur - bet) if not is_dev else cur
        result = f"💸 *{label}*\n😢 Lost: `-{bet} credits`"
    data["users"][uid]["credits"] = nc
    save_data(data)
    track_tool_usage("slots")
    text = (
        f"🎰 *SLOT MACHINE*\n{LINE}\n"
        f"┌───┬───┬───┐\n"
        f"│{reels[0]}│{reels[1]}│{reels[2]}│\n"
        f"└───┴───┴───┘\n"
        f"{LINE}\n{result}\n\n💎 Balance: `{nc} credits`\n{LINE}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🎰 Spin Again ({bet} bet)", callback_data=f"slots_again_{bet}")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])
    return True, text, kb

async def cmd_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    if not context.args:
        await update.message.reply_text(
            f"🎰 *Slot Machine*\n{LINE}\n"
            f"Usage: `/slots <bet>`\n\n"
            f"Symbols: {' '.join(SLOT_SYMBOLS)}\n\n"
            f"*Jackpot Payouts:*\n"
            f"7️⃣7️⃣7️⃣ → `50×` JACKPOT!\n💎💎💎 → `20×`\n⭐⭐⭐ → `10×`\n"
            f"Any 3 same → `5×`\nAny 2 same → `2×`\nNo match → lose\n\n"
            f"Min bet: `{GAME_MIN_BET}` | Max: `{GAME_MAX_BET}`\n"
            f"💎 Credits: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text(f"{CROSS} Bet must be a number.", parse_mode=ParseMode.MARKDOWN)
        return
    if not (GAME_MIN_BET <= bet <= GAME_MAX_BET):
        await update.message.reply_text(f"{CROSS} Bet between `{GAME_MIN_BET}` and `{GAME_MAX_BET}`.", parse_mode=ParseMode.MARKDOWN)
        return
    ok, text, kb = await _do_slots(None, user.id, user.username or "", bet)
    if not ok:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

# ════════════════════════════════════════════════
# FEATURE: ROULETTE 🎡
# ════════════════════════════════════════════════
ROULETTE_RED   = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
ROULETTE_BLACK = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

async def cmd_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    db_user = get_user(user.id, user.username or "")
    is_dev  = is_developer(user.id, user.username or "")
    if len(context.args) < 2:
        await update.message.reply_text(
            f"🎡 *Roulette*\n{LINE}\n"
            f"Usage: `/roulette <bet> <choice>`\n\n"
            f"*Choices & Payouts:*\n"
            f"▸ `red`   → 2× (18/37)\n▸ `black` → 2× (18/37)\n"
            f"▸ `green` → 15× (1/37)\n▸ `odd`   → 2×\n▸ `even`  → 2×\n"
            f"▸ `0`–`36` → 36× (exact number)\n\n"
            f"Min: `{GAME_MIN_BET}` | Max: `{GAME_MAX_BET}`\n"
            f"💎 Credits: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text(f"{CROSS} Bet must be a number.", parse_mode=ParseMode.MARKDOWN)
        return
    if not (GAME_MIN_BET <= bet <= GAME_MAX_BET):
        await update.message.reply_text(f"{CROSS} Bet between `{GAME_MIN_BET}` and `{GAME_MAX_BET}`.", parse_mode=ParseMode.MARKDOWN)
        return
    if db_user["credits"] < bet and not is_dev:
        await update.message.reply_text(f"{CROSS} Not enough credits.", parse_mode=ParseMode.MARKDOWN)
        return
    choice = context.args[1].lower().strip()
    spin   = random.randint(0, 36)
    spin_color = "🟢" if spin == 0 else ("🔴" if spin in ROULETTE_RED else "⚫")
    won, mult = False, 0
    choice_disp = choice
    if choice == "red":
        won, mult = spin in ROULETTE_RED, 2
    elif choice == "black":
        won, mult = spin in ROULETTE_BLACK, 2
    elif choice == "green":
        won, mult = spin == 0, 15
    elif choice == "odd":
        won, mult = (spin != 0 and spin % 2 == 1), 2
    elif choice == "even":
        won, mult = (spin != 0 and spin % 2 == 0), 2
    elif choice.isdigit() and 0 <= int(choice) <= 36:
        won, mult = spin == int(choice), 36
        choice_disp = f"#{choice}"
    else:
        await update.message.reply_text(
            f"{CROSS} Invalid choice! Use: `red` `black` `green` `odd` `even` or a number `0-36`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    data = load_data()
    uid  = str(user.id)
    cur  = db_user["credits"]
    if won:
        net = bet * (mult - 1)
        nc  = cur + net if not is_dev else cur
        result = f"🎉 *YOU WIN!*\n💰 Won: `+{net} credits` (`{mult}×`)"
    else:
        nc  = max(0, cur - bet) if not is_dev else cur
        result = f"😢 *YOU LOSE!*\n💸 Lost: `-{bet} credits`"
    data["users"][uid]["credits"] = nc
    save_data(data)
    track_tool_usage("roulette")
    await update.message.reply_text(
        f"🎡 *ROULETTE*\n{LINE}\n"
        f"🎯 Bet: `{bet}` on `{choice_disp}`\n"
        f"🎰 Ball: {spin_color} `{spin}`\n"
        f"{LINE}\n{result}\n\n💎 Balance: `{nc} credits`\n{LINE}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🎡 Spin Again", callback_data=f"roulette_again_{bet}_{context.args[1]}")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ]),
    )

# ════════════════════════════════════════════════
# FEATURE: BLACKJACK 🃏
# ════════════════════════════════════════════════
_BJ_RANKS = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
_BJ_SUITS = ["♠","♥","♦","♣"]

def _bj_card():
    return (random.choice(_BJ_RANKS), random.choice(_BJ_SUITS))

def _bj_val(hand):
    total = 0
    aces  = 0
    for r, _ in hand:
        if r in ("J","Q","K"):  total += 10
        elif r == "A":          total += 11; aces += 1
        else:                   total += int(r)
    while total > 21 and aces:
        total -= 10; aces -= 1
    return total

def _bj_fmt(hand):
    return " ".join(f"`{r}{s}`" for r, s in hand)

def _bj_resolve(player, dealer, bet, cur, is_dev):
    pv = _bj_val(player)
    while _bj_val(dealer) < 17:
        dealer.append(_bj_card())
    dv = _bj_val(dealer)
    if pv > 21:
        nc = max(0, cur - bet) if not is_dev else cur
        return dealer, nc, f"💥 *BUST!* You hit `{pv}`\n💸 Lost: `-{bet} credits`", False
    if dv > 21 or pv > dv:
        nc = cur + bet if not is_dev else cur
        return dealer, nc, f"🎉 *YOU WIN!* `{pv}` beats dealer `{dv}`\n💰 Won: `+{bet} credits`", True
    if pv == dv:
        return dealer, cur, f"🤝 *PUSH!* Both `{pv}` — bet returned", True
    nc = max(0, cur - bet) if not is_dev else cur
    return dealer, nc, f"😢 *DEALER WINS!* `{dv}` beats your `{pv}`\n💸 Lost: `-{bet} credits`", False

async def cmd_blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    db_user = get_user(user.id, user.username or "")
    is_dev  = is_developer(user.id, user.username or "")
    if not context.args:
        await update.message.reply_text(
            f"🃏 *Blackjack*\n{LINE}\n"
            f"Usage: `/blackjack <bet>`\n\n"
            f"▸ Get closer to 21 than dealer\n"
            f"▸ Bust (>21) = instant lose\n"
            f"▸ Beat dealer = win 2× bet\n"
            f"▸ Blackjack (21) = 2.5× bet\n\n"
            f"Min: `{GAME_MIN_BET}` | Max: `{GAME_MAX_BET}`\n"
            f"💎 Credits: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text(f"{CROSS} Bet must be a number.", parse_mode=ParseMode.MARKDOWN)
        return
    if not (GAME_MIN_BET <= bet <= GAME_MAX_BET):
        await update.message.reply_text(f"{CROSS} Bet between `{GAME_MIN_BET}` and `{GAME_MAX_BET}`.", parse_mode=ParseMode.MARKDOWN)
        return
    if db_user["credits"] < bet and not is_dev:
        await update.message.reply_text(f"{CROSS} Not enough credits.", parse_mode=ParseMode.MARKDOWN)
        return
    player = [_bj_card(), _bj_card()]
    dealer = [_bj_card(), _bj_card()]
    pv     = _bj_val(player)
    context.user_data["bj"] = {"bet": bet, "player": player, "dealer": dealer, "is_dev": is_dev}
    if pv == 21:
        payout = int(bet * 1.5)
        data   = load_data()
        uid    = str(user.id)
        data["users"][uid]["credits"] = db_user["credits"] + payout if not is_dev else db_user["credits"]
        save_data(data)
        track_tool_usage("blackjack")
        await update.message.reply_text(
            f"🃏 *BLACKJACK!* 🎉\n{LINE}\n"
            f"Your hand: {_bj_fmt(player)} = `{pv}`\n"
            f"Dealer: {_bj_fmt(dealer)} = `{_bj_val(dealer)}`\n{LINE}\n"
            f"💰 Blackjack bonus: `+{payout} credits` (1.5×)\n"
            f"💎 Balance: `{data['users'][uid]['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]),
        )
        return
    await update.message.reply_text(
        f"🃏 *BLACKJACK*\n{LINE}\n"
        f"Your hand: {_bj_fmt(player)} = `{pv}`\n"
        f"Dealer shows: `{dealer[0][0]}{dealer[0][1]}` 🂠\n{LINE}\n"
        f"💰 Bet: `{bet} credits`  |  _What do you do?_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👊 Hit", callback_data="bj_hit"),
             InlineKeyboardButton("✋ Stand", callback_data="bj_stand")],
            [InlineKeyboardButton("❌ Forfeit (lose half)", callback_data="bj_forfeit")],
        ]),
    )

# ════════════════════════════════════════════════
# FEATURE: CRASH GAME 💥
# ════════════════════════════════════════════════
async def cmd_crash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    db_user = get_user(user.id, user.username or "")
    is_dev  = is_developer(user.id, user.username or "")
    if len(context.args) < 2:
        await update.message.reply_text(
            f"💥 *Crash Game*\n{LINE}\n"
            f"Usage: `/crash <bet> <target_multiplier>`\n\n"
            f"Set your target cashout multiplier.\n"
            f"▸ Crash ≥ target → you WIN at target\n"
            f"▸ Crash < target → you LOSE your bet\n\n"
            f"Example: `/crash 10 2.5`\n"
            f"_Wins `{10*2}` if crash happens at 2.5× or higher_\n\n"
            f"Min: `{GAME_MIN_BET}` | Max: `{GAME_MAX_BET}` | Min target: `1.1×`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    try:
        bet    = int(context.args[0])
        target = round(float(context.args[1]), 2)
    except ValueError:
        await update.message.reply_text(f"{CROSS} Usage: `/crash <bet> <multiplier>` e.g. `/crash 10 2.5`", parse_mode=ParseMode.MARKDOWN)
        return
    if not (GAME_MIN_BET <= bet <= GAME_MAX_BET):
        await update.message.reply_text(f"{CROSS} Bet between `{GAME_MIN_BET}` and `{GAME_MAX_BET}`.", parse_mode=ParseMode.MARKDOWN)
        return
    if target < 1.1:
        await update.message.reply_text(f"{CROSS} Target must be at least `1.1×`.", parse_mode=ParseMode.MARKDOWN)
        return
    if db_user["credits"] < bet and not is_dev:
        await update.message.reply_text(f"{CROSS} Not enough credits.", parse_mode=ParseMode.MARKDOWN)
        return
    # Exponential distribution — lower multipliers much more common
    r           = random.random()
    crash_point = round(min(100.0, max(1.0, 1.0 / (1.0 - r * 0.97))), 2)
    won         = crash_point >= target
    data        = load_data()
    uid         = str(user.id)
    cur         = db_user["credits"]
    if won:
        payout = int(bet * target)
        net    = payout - bet
        nc     = cur + net if not is_dev else cur
        result = f"🚀 *CASHED OUT!*\nCrash at `{crash_point}×` ≥ target `{target}×`\n💰 Won: `+{net} credits`"
    else:
        nc     = max(0, cur - bet) if not is_dev else cur
        result = f"💥 *CRASHED EARLY!*\nCrash at `{crash_point}×` < target `{target}×`\n💸 Lost: `-{bet} credits`"
    data["users"][uid]["credits"] = nc
    save_data(data)
    track_tool_usage("crash")
    chart_steps = [1.0, 1.2, 1.5, 2.0, 3.0, 5.0, 10.0, 20.0, 50.0, 100.0]
    chart = ""
    for s in chart_steps:
        if s < crash_point:
            chart += f"📈`{s}×` "
        elif s == crash_point or crash_point < s:
            chart += f"💥`{crash_point}×`"
            break
    await update.message.reply_text(
        f"💥 *CRASH GAME*\n{LINE}\n{chart}\n{LINE}\n"
        f"🎯 Your target: `{target}×`\n{result}\n\n💎 Balance: `{nc} credits`\n{LINE}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]),
    )

# ════════════════════════════════════════════════
# FEATURE: HORSE RACE 🏇
# ════════════════════════════════════════════════
HORSES = [
    ("🐎 Thunderbolt",   0.40, 2.5),
    ("🏇 SilverMane",    0.30, 3.5),
    ("🦄 NightStar",     0.20, 5.0),
    ("⚡ BlackLightning", 0.10, 10.0),
]

async def cmd_horse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    db_user = get_user(user.id, user.username or "")
    is_dev  = is_developer(user.id, user.username or "")
    if len(context.args) < 2:
        lines = [f"{i+1}. {h[0]} — `{int(h[1]*100)}%` chance | `{h[2]}×` payout" for i, h in enumerate(HORSES)]
        await update.message.reply_text(
            f"🏇 *Horse Race*\n{LINE}\nUsage: `/horse <bet> <1-4>`\n\n"
            + "\n".join(lines) +
            f"\n\nMin: `{GAME_MIN_BET}` | Max: `{GAME_MAX_BET}`\n💎 Credits: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    try:
        bet       = int(context.args[0])
        horse_num = int(context.args[1])
    except ValueError:
        await update.message.reply_text(f"{CROSS} Usage: `/horse <bet> <1-4>`", parse_mode=ParseMode.MARKDOWN)
        return
    if not (GAME_MIN_BET <= bet <= GAME_MAX_BET):
        await update.message.reply_text(f"{CROSS} Bet between `{GAME_MIN_BET}` and `{GAME_MAX_BET}`.", parse_mode=ParseMode.MARKDOWN)
        return
    if not (1 <= horse_num <= 4):
        await update.message.reply_text(f"{CROSS} Pick a horse 1-4.", parse_mode=ParseMode.MARKDOWN)
        return
    if db_user["credits"] < bet and not is_dev:
        await update.message.reply_text(f"{CROSS} Not enough credits.", parse_mode=ParseMode.MARKDOWN)
        return
    winner_idx = random.choices(range(4), weights=[h[1] for h in HORSES], k=1)[0]
    chosen     = HORSES[horse_num - 1]
    winner     = HORSES[winner_idx]
    won        = winner_idx == horse_num - 1
    data       = load_data()
    uid        = str(user.id)
    cur        = db_user["credits"]
    if won:
        net = int(bet * chosen[2]) - bet
        nc  = cur + net if not is_dev else cur
        result = f"🏆 *YOUR HORSE WON!*\n💰 Won: `+{net} credits` (`{chosen[2]}×`)"
    else:
        nc     = max(0, cur - bet) if not is_dev else cur
        result = f"😢 *YOUR HORSE LOST!*\nWinner: {winner[0]}\n💸 Lost: `-{bet} credits`"
    data["users"][uid]["credits"] = nc
    save_data(data)
    track_tool_usage("horse")
    medals = ["🥇","🥈","🥉","4️⃣"]
    scores = [random.randint(1,5) for _ in range(4)]
    scores[winner_idx] = 6
    ranked = sorted(range(4), key=lambda i: scores[i], reverse=True)
    race_lines = []
    for rank, idx in enumerate(ranked):
        marker = " ← YOUR BET" if idx == horse_num - 1 else ""
        race_lines.append(f"{medals[rank]} {HORSES[idx][0]}{marker}")
    await update.message.reply_text(
        f"🏇 *RACE RESULTS*\n{LINE}\n" + "\n".join(race_lines) +
        f"\n{LINE}\n{result}\n\n💎 Balance: `{nc} credits`\n{LINE}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]),
    )

# ════════════════════════════════════════════════
# FEATURE: TOWER CLIMB 🗼
# ════════════════════════════════════════════════
TOWER_MULTS   = {1: 1.5, 2: 2.2, 3: 3.5, 4: 5.0, 5: 8.0}
TOWER_CHANCE  = 0.60

async def cmd_tower(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    db_user = get_user(user.id, user.username or "")
    is_dev  = is_developer(user.id, user.username or "")
    if len(context.args) < 2:
        lines = [f"  {f} floor{'s' if f>1 else ''} → `{m}×`" for f, m in TOWER_MULTS.items()]
        await update.message.reply_text(
            f"🗼 *Tower Climb*\n{LINE}\nUsage: `/tower <bet> <floors 1-5>`\n\n"
            f"Each floor: `60%` survival chance\n\n*Payouts:*\n" + "\n".join(lines) +
            f"\n\nMin: `{GAME_MIN_BET}` | Max: `{GAME_MAX_BET}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    try:
        bet    = int(context.args[0])
        floors = int(context.args[1])
    except ValueError:
        await update.message.reply_text(f"{CROSS} Usage: `/tower <bet> <1-5>`", parse_mode=ParseMode.MARKDOWN)
        return
    if not (GAME_MIN_BET <= bet <= GAME_MAX_BET):
        await update.message.reply_text(f"{CROSS} Bet between `{GAME_MIN_BET}` and `{GAME_MAX_BET}`.", parse_mode=ParseMode.MARKDOWN)
        return
    if not (1 <= floors <= 5):
        await update.message.reply_text(f"{CROSS} Floors must be 1-5.", parse_mode=ParseMode.MARKDOWN)
        return
    if db_user["credits"] < bet and not is_dev:
        await update.message.reply_text(f"{CROSS} Not enough credits.", parse_mode=ParseMode.MARKDOWN)
        return
    survived    = 0
    tower_lines = []
    for f in range(1, floors + 1):
        if random.random() < TOWER_CHANCE:
            survived += 1
            tower_lines.append(f"  Floor {f}: ✅ Safe")
        else:
            tower_lines.append(f"  Floor {f}: 💀 FELL!")
            break
    data = load_data()
    uid  = str(user.id)
    cur  = db_user["credits"]
    if survived == floors:
        mult   = TOWER_MULTS[floors]
        net    = int(bet * mult) - bet
        nc     = cur + net if not is_dev else cur
        result = f"🏆 *CLIMBED ALL {floors} FLOOR(S)!*\n💰 Won: `+{net} credits` (`{mult}×`)"
    else:
        nc     = max(0, cur - bet) if not is_dev else cur
        result = f"💀 *FELL on floor {survived + 1}!*\n💸 Lost: `-{bet} credits`"
    data["users"][uid]["credits"] = nc
    save_data(data)
    track_tool_usage("tower")
    tower_art = "\n".join(reversed(tower_lines))
    await update.message.reply_text(
        f"🗼 *TOWER CLIMB*\n{LINE}\n{tower_art}\n{LINE}\n{result}\n\n💎 Balance: `{nc} credits`\n{LINE}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]),
    )

# ════════════════════════════════════════════════
# FEATURE: GUESS THE NUMBER 🔢
# ════════════════════════════════════════════════
async def cmd_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    db_user = get_user(user.id, user.username or "")
    is_dev  = is_developer(user.id, user.username or "")
    if len(context.args) < 2:
        await update.message.reply_text(
            f"🔢 *Guess the Number*\n{LINE}\n"
            f"Usage: `/guess <bet> <1-10>`\n\n"
            f"▸ Correct guess → Win `8×` your bet!\n"
            f"▸ Wrong → Lose your bet\n\n"
            f"Min: `{GAME_MIN_BET}` | Max: `{GAME_MAX_BET}`\n💎 Credits: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    try:
        bet   = int(context.args[0])
        guess = int(context.args[1])
    except ValueError:
        await update.message.reply_text(f"{CROSS} Usage: `/guess <bet> <1-10>`", parse_mode=ParseMode.MARKDOWN)
        return
    if not (GAME_MIN_BET <= bet <= GAME_MAX_BET):
        await update.message.reply_text(f"{CROSS} Bet between `{GAME_MIN_BET}` and `{GAME_MAX_BET}`.", parse_mode=ParseMode.MARKDOWN)
        return
    if not (1 <= guess <= 10):
        await update.message.reply_text(f"{CROSS} Guess a number 1-10.", parse_mode=ParseMode.MARKDOWN)
        return
    if db_user["credits"] < bet and not is_dev:
        await update.message.reply_text(f"{CROSS} Not enough credits.", parse_mode=ParseMode.MARKDOWN)
        return
    secret = random.randint(1, 10)
    won    = guess == secret
    data   = load_data()
    uid    = str(user.id)
    cur    = db_user["credits"]
    if won:
        net = bet * 7
        nc  = cur + net if not is_dev else cur
        result = f"🎉 *CORRECT!* Number was `{secret}`!\n💰 Won: `+{net} credits` (8×)"
    else:
        nc     = max(0, cur - bet) if not is_dev else cur
        result = f"❌ *WRONG!* Number was `{secret}`\nYou guessed `{guess}`\n💸 Lost: `-{bet} credits`"
    data["users"][uid]["credits"] = nc
    save_data(data)
    track_tool_usage("guess")
    await update.message.reply_text(
        f"🔢 *GUESS THE NUMBER*\n{LINE}\n"
        f"🎲 Secret: `{secret}` | Your guess: `{guess}`\n{LINE}\n"
        f"{result}\n\n💎 Balance: `{nc} credits`\n{LINE}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]),
    )

# ════════════════════════════════════════════════
# FEATURE: PORT SCANNER 🔌 (Real socket checks)
# ════════════════════════════════════════════════
COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
    3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 6379: "Redis",
    8080: "HTTP-Alt", 8443: "HTTPS-Alt", 27017: "MongoDB",
    1433: "MSSQL", 5900: "VNC", 11211: "Memcached",
}

def scan_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """Real TCP port scan via socket — no simulation."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False

async def cmd_portscan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    db_user = get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            f"🔌 *Port Scanner*\n{LINE}\n"
            f"Usage: `/portscan <host> <port>`\n\n"
            f"Real TCP connect test — no simulation!\n"
            f"Example: `/portscan google.com 443`\n"
            f"_Costs 1 credit_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    host = context.args[0].strip()
    try:
        port = int(context.args[1])
        if not (1 <= port <= 65535):
            raise ValueError
    except ValueError:
        await update.message.reply_text(f"{CROSS} Port must be 1-65535.", parse_mode=ParseMode.MARKDOWN)
        return
    msg = await update.message.reply_text(f"🔌 _Scanning `{host}:{port}`…_", parse_mode=ParseMode.MARKDOWN)
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        await msg.edit_text(f"{CROSS} Cannot resolve `{host}`", parse_mode=ParseMode.MARKDOWN)
        return
    is_open = scan_port(ip, port)
    service = COMMON_PORTS.get(port, "Unknown/Custom")
    status  = "🟢 OPEN" if is_open else "🔴 CLOSED/FILTERED"
    db_user = get_user(user.id)
    track_tool_usage("portscan")
    await msg.edit_text(
        f"🔌 *PORT SCAN RESULT*\n{LINE}\n"
        f"🌐 Host: `{host}`\n📡 IP: `{ip}`\n"
        f"🔢 Port: `{port}`\n🛠 Service: `{service}`\n"
        f"{LINE}\nStatus: {status}\n{LINE}\n"
        f"💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(),
    )

async def cmd_scanports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    db_user = get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(
            f"🔍 *Scan Common Ports*\n{LINE}\n"
            f"Usage: `/scanports <host>`\n\n"
            f"Scans `{len(COMMON_PORTS)}` common ports via real TCP.\n"
            f"Example: `/scanports google.com`\n"
            f"⏱ _Takes ~15-20 seconds. Costs 1 credit._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    host = context.args[0].strip()
    msg  = await update.message.reply_text(
        f"🔍 _Scanning {len(COMMON_PORTS)} ports on `{host}`…_\n_Please wait up to 20s._",
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        await msg.edit_text(f"{CROSS} Cannot resolve `{host}`", parse_mode=ParseMode.MARKDOWN)
        return
    open_ports, closed_ports = [], []
    for port, service in COMMON_PORTS.items():
        if scan_port(ip, port, timeout=1.0):
            open_ports.append(f"🟢 `{port}` ({service})")
        else:
            closed_ports.append(f"🔴 `{port}` ({service})")
    db_user = get_user(user.id)
    track_tool_usage("scanports")
    open_text   = "\n".join(open_ports)   if open_ports   else "_None found_"
    closed_text = "\n".join(closed_ports[:10]) if closed_ports else "_None_"
    await msg.edit_text(
        f"🔍 *PORT SCAN: {host}*\n{LINE}\n"
        f"📡 IP: `{ip}` | Scanned: `{len(COMMON_PORTS)} ports`\n"
        f"🟢 Open: `{len(open_ports)}`\n{LINE}\n"
        f"*Open Ports:*\n{open_text}\n{LINE}\n"
        f"*Closed (first 10):*\n{closed_text}\n{LINE}\n"
        f"💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(),
    )

async def cmd_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    is_dev = is_developer(user.id, user.username or "")
    is_prem = is_user_premium(user.id)

    next_reset = (date.today() + timedelta(days=1)).strftime("%d %b %Y")
    daily_limit = "∞ Unlimited" if is_dev else (str(PREMIUM_DAILY_CREDITS) if is_prem else str(FREE_DAILY_CREDITS))
    status = f"{CROWN} Developer" if is_dev else (f"{GEM} Premium" if is_prem else f"{STAR2} Free")

    text = f"""
╔══════════════════════════════╗
║      💎 CREDITS PANEL        ║
╚══════════════════════════════╝

{DIAMOND} *User:* `{user.first_name}`
{DIAMOND} *Status:* `{status}`
{LINE}
{BOLT} *Credits Balance:* `{db_user['credits']}` {"(∞ No Limit)" if is_dev else ""}
{BULLET} *Daily Limit:* `{daily_limit}`
{BULLET} *Total Used:* `{db_user.get('total_used', 0)}`
{BULLET} *Next Reset:* `{next_reset}`
{LINE}

💡 *Upgrade to Premium* for:
   ✦ 100 credits/day
   ✦ Priority support
   ✦ Unlimited tool access

Contact: @{DEVELOPER_USERNAME}
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_premium_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""
╔══════════════════════════════╗
║    👑 PREMIUM MEMBERSHIP     ║
╚══════════════════════════════╝

{GEM} *Premium Benefits:*
{LINE}
  ✦ `100 credits/day` (vs 10 free)
  ✦ Access to all premium tools
  ✦ Priority processing
  ✦ No restrictions on features
  ✦ Early access to new tools
  ✦ Premium support badge
{LINE}

{CROWN} *Developer Perks (Lifetime):*
  ✦ Unlimited credits
  ✦ All features unlocked
  ✦ Developer panel access
  ✦ Can manage all users

{LINE}
📩 *Get Premium:*
Contact developer: @{DEVELOPER_USERNAME}

{WARN} _Premium is activated by the developer_
"""
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Contact Developer", url=f"https://t.me/{DEVELOPER_USERNAME}")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def cmd_disclaimer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(DISCLAIMER_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

# ─── DEVELOPER PANEL ───
async def cmd_dev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Access denied. Developer only.")
        return

    data = load_data()
    total_users = len(data["users"])
    premium_count = len(data["premium_users"])
    total_credits_used = sum(u.get("total_used", 0) for u in data["users"].values())

    text = f"""
╔══════════════════════════════╗
║    👨‍💻 DEVELOPER PANEL        ║
╚══════════════════════════════╝

{CROWN} *Developer:* @{DEVELOPER_USERNAME}
{LINE}
📊 *Bot Statistics:*
{DIAMOND} Total Users: `{total_users}`
{DIAMOND} Premium Users: `{premium_count}`
{DIAMOND} Total Credits Used: `{total_credits_used}`
{LINE}

🔧 *Developer Commands:*

`/addpremium <user_id>` — Grant premium
`/revokepremium <user_id>` — Revoke premium
`/addcredits <user_id> <amount>` — Add credits
`/takecredits <user_id> <amount>` — Remove credits
`/transfer <from_id> <to_id> <amount>` — Transfer credits
`/userinfo <user_id>` — View user info
`/allstats` — Full bot statistics
`/broadcast <message>` — Send to all users
`/resetuser <user_id>` — Reset user data
`/listpremium` — List premium users
`/ban <user_id>` — Ban user
`/unban <user_id>` — Unban user

{LINE}
{WARN} _Handle with care — developer commands affect all users_
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cmd_add_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Access denied.")
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/addpremium <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
        set_premium(target_id, True)
        await update.message.reply_text(f"{CHECK} Premium granted to user `{target_id}`", parse_mode=ParseMode.MARKDOWN)
        try:
            await context.bot.send_message(target_id, f"{CROWN} *Congratulations!* You've been upgraded to *Premium* by the developer!\n\n{GEM} You now have *100 credits/day*!", parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid user ID.")

async def cmd_revoke_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Access denied.")
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/revokepremium <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
        set_premium(target_id, False)
        await update.message.reply_text(f"{CHECK} Premium revoked from user `{target_id}`", parse_mode=ParseMode.MARKDOWN)
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid user ID.")

async def cmd_add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Access denied.")
        return
    if len(context.args) < 2:
        await update.message.reply_text(f"{WARN} Usage: `/addcredits <user_id> <amount>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        add_credits(target_id, amount)
        await update.message.reply_text(f"{CHECK} Added `{amount}` credits to user `{target_id}`", parse_mode=ParseMode.MARKDOWN)
        try:
            await context.bot.send_message(target_id, f"{BOLT} *{amount} credits* have been added to your account by the developer!", parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid arguments.")

async def cmd_take_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Access denied.")
        return
    if len(context.args) < 2:
        await update.message.reply_text(f"{WARN} Usage: `/takecredits <user_id> <amount>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        add_credits(target_id, -amount)
        await update.message.reply_text(f"{CHECK} Removed `{amount}` credits from user `{target_id}`", parse_mode=ParseMode.MARKDOWN)
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid arguments.")

async def cmd_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Access denied.")
        return
    if len(context.args) < 3:
        await update.message.reply_text(f"{WARN} Usage: `/transfer <from_id> <to_id> <amount>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        from_id = int(context.args[0])
        to_id = int(context.args[1])
        amount = int(context.args[2])
        add_credits(from_id, -amount)
        add_credits(to_id, amount)
        await update.message.reply_text(f"{CHECK} Transferred `{amount}` credits from `{from_id}` to `{to_id}`", parse_mode=ParseMode.MARKDOWN)
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid arguments.")

async def cmd_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Access denied.")
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/userinfo <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
        data = load_data()
        uid = str(target_id)
        if uid not in data["users"]:
            await update.message.reply_text(f"{CROSS} User `{target_id}` not found.", parse_mode=ParseMode.MARKDOWN)
            return
        u = data["users"][uid]
        is_prem = target_id in data["premium_users"]
        is_dev = is_developer(target_id)
        is_banned = u.get("banned", False)
        text = f"""
{DEV} *User Info*
{LINE}
🆔 ID: `{target_id}`
👤 Username: @{u.get('username', 'N/A')}
{DIAMOND} Status: `{"Developer" if is_dev else "Premium" if is_prem else "Free"}`
{BOLT} Credits: `{u.get('credits', 0)}`
📊 Total Used: `{u.get('total_used', 0)}`
📅 Joined: `{u.get('joined', 'N/A')}`
🔄 Last Reset: `{u.get('last_reset', 'N/A')}`
🚫 Banned: `{is_banned}`
"""
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid user ID.")

async def cmd_all_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Access denied.")
        return
    data = load_data()
    users = list(data["users"].values())
    total = len(users)
    premium = len(data["premium_users"])
    active_today = sum(1 for u in users if u.get("last_reset") == str(date.today()))
    total_used = sum(u.get("total_used", 0) for u in users)
    text = f"""
📊 *Full Bot Statistics*
{LINE}
👥 Total Users: `{total}`
{GEM} Premium Users: `{premium}`
{STAR2} Free Users: `{total - premium}`
{BOLT} Active Today: `{active_today}`
📈 Total Credits Used: `{total_used}`
{LINE}
📅 Report Date: `{date.today()}`
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Access denied.")
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/broadcast <message>`", parse_mode=ParseMode.MARKDOWN)
        return
    message = " ".join(context.args)
    data = load_data()
    success = 0
    failed = 0
    broadcast_msg = f"""
📢 *Broadcast from Developer*
{LINE}
{message}
{LINE}
— @{DEVELOPER_USERNAME}
"""
    for uid, udata in data["users"].items():
        if udata.get("banned"):
            continue
        try:
            await context.bot.send_message(int(uid), broadcast_msg, parse_mode=ParseMode.MARKDOWN)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await update.message.reply_text(f"{CHECK} Broadcast sent!\n✅ Success: `{success}`\n❌ Failed: `{failed}`", parse_mode=ParseMode.MARKDOWN)

async def cmd_list_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Access denied.")
        return
    data = load_data()
    if not data["premium_users"]:
        await update.message.reply_text(f"{INFO} No premium users yet.")
        return
    lines = [f"{GEM} *Premium Users List*\n{LINE}"]
    for pid in data["premium_users"]:
        uid = str(pid)
        udata = data["users"].get(uid, {})
        uname = udata.get("username", "Unknown")
        lines.append(f"• `{pid}` — @{uname}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Access denied.")
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/ban <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
        data = load_data()
        uid = str(target_id)
        if uid not in data["users"]:
            data["users"][uid] = {"user_id": target_id, "username": "", "credits": 0, "last_reset": str(date.today()), "premium": False, "total_used": 0, "joined": str(date.today())}
        data["users"][uid]["banned"] = True
        save_data(data)
        await update.message.reply_text(f"{CHECK} User `{target_id}` has been banned.", parse_mode=ParseMode.MARKDOWN)
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid user ID.")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Access denied.")
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/unban <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
        data = load_data()
        uid = str(target_id)
        if uid in data["users"]:
            data["users"][uid]["banned"] = False
            save_data(data)
        await update.message.reply_text(f"{CHECK} User `{target_id}` has been unbanned.", parse_mode=ParseMode.MARKDOWN)
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid user ID.")

async def cmd_reset_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text(f"{CROSS} Access denied.")
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/resetuser <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
        data = load_data()
        uid = str(target_id)
        if uid in data["users"]:
            data["users"][uid]["credits"] = FREE_DAILY_CREDITS
            data["users"][uid]["total_used"] = 0
            data["users"][uid]["banned"] = False
            data["users"][uid]["last_reset"] = str(date.today())
            save_data(data)
        await update.message.reply_text(f"{CHECK} User `{target_id}` data reset.", parse_mode=ParseMode.MARKDOWN)
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid user ID.")

# ─── CREDIT CHECK HELPER ───
async def check_credits_and_use_query(query, user_id: int) -> bool:
    """Same as check_credits_and_use but works with callback query (no update.message)."""
    data = load_data()
    uid = str(user_id)
    udata = data["users"].get(uid, {})
    if udata.get("banned"):
        await query.answer("You are banned from using this bot.", show_alert=True)
        return False
    if not use_credit(user_id):
        await query.answer("Not enough credits! Earn more with /claim or /referral.", show_alert=True)
        return False
    return True

async def check_credits_and_use(update: Update, user_id: int) -> bool:
    data = load_data()
    uid = str(user_id)
    udata = data["users"].get(uid, {})
    if udata.get("banned"):
        await update.message.reply_text(f"{CROSS} You are banned from using this bot.")
        return False
    if not use_credit(user_id):
        await update.message.reply_text(
            f"{CROSS} *Insufficient Credits!*\n\n"
            f"You have *0 credits* remaining.\n"
            f"Credits reset daily at midnight.\n\n"
            f"💎 *Upgrade to Premium* for 100 credits/day!\n"
            f"Contact: @{DEVELOPER_USERNAME}",
            parse_mode=ParseMode.MARKDOWN
        )
        return False
    return True

# ─── CARDING TOOLS COMMANDS ───
async def cmd_bin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/bin <6-digit BIN>`\n\nExample: `/bin 457173`", parse_mode=ParseMode.MARKDOWN)
        return
    bin_num = context.args[0].strip()[:16]
    msg = await update.message.reply_text(f"🔍 Looking up BIN `{bin_num}`...", parse_mode=ParseMode.MARKDOWN)
    result = lookup_bin(bin_num)
    db_user = get_user(user.id)
    if result:
        country = result.get("country", {})
        bank = result.get("bank", {})
        scheme = result.get("scheme", "N/A").upper()
        card_type = result.get("type", "N/A").upper()
        brand = result.get("brand", "N/A").upper()
        country_name = country.get("name", "N/A") if isinstance(country, dict) else str(country)
        country_emoji = country.get("emoji", "") if isinstance(country, dict) else ""
        bank_name = bank.get("name", "N/A") if isinstance(bank, dict) else str(bank)
        card_brand = get_card_brand(bin_num)
        text = f"""
╔══════════════════════════════╗
║    🔍 BIN CHECKER RESULT     ║
╚══════════════════════════════╝

{DIAMOND} *BIN:* `{bin_num}`
{LINE}
💳 *Scheme:* `{scheme}`
🏦 *Bank:* `{bank_name}`
🌍 *Country:* `{country_emoji} {country_name}`
📋 *Type:* `{card_type}`
🏷️ *Brand:* `{brand or card_brand}`
{LINE}
💰 *Credits Left:* `{db_user['credits']}` {"(∞)" if is_developer(user.id) else ""}

{WARN} _For educational purposes only_
"""
    else:
        text = f"""
{CROSS} *BIN Lookup Failed*
{LINE}
BIN: `{bin_num}`
The BIN database returned no results, or the BIN is invalid.

Try a 6-digit BIN like: `457173`, `411111`
{LINE}
💰 Credits Left: `{db_user['credits']}`
"""
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_carding_keyboard())

async def cmd_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/gen <bin> [quantity]`\n\nExample: `/gen 457173 5`", parse_mode=ParseMode.MARKDOWN)
        return
    bin_num = context.args[0].strip()
    qty = min(int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 5, 20)
    msg = await update.message.reply_text(f"⚙️ Generating {qty} cards from BIN `{bin_num}`...", parse_mode=ParseMode.MARKDOWN)
    cards = generate_cards_from_bin(bin_num, qty)
    brand = get_card_brand(bin_num)
    db_user = get_user(user.id)
    cards_text = "\n".join([f"`{c}`" for c in cards])
    text = f"""
╔══════════════════════════════╗
║    ⚙️ CC GENERATOR RESULT    ║
╚══════════════════════════════╝

💳 *BIN:* `{bin_num}`
🏷️ *Brand:* `{brand}`
📦 *Generated:* `{qty}` cards
{LINE}
{cards_text}
{LINE}
💰 Credits Left: `{db_user['credits']}` {"(∞)" if is_developer(user.id) else ""}

{WARN} _Generated for testing/education only_
"""
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_carding_keyboard())

async def cmd_chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/chk <card_number|mm|yy|cvv>`\n\nExample: `/chk 4111111111111111|12|2025|123`", parse_mode=ParseMode.MARKDOWN)
        return
    raw = context.args[0].strip()
    parts = raw.replace("|", "|").split("|")
    card_num = re.sub(r'\D', '', parts[0])
    month = parts[1] if len(parts) > 1 else "??"
    year = parts[2] if len(parts) > 2 else "????"
    cvv = parts[3] if len(parts) > 3 else "???"
    is_luhn = luhn_check(card_num)
    brand = get_card_brand(card_num)
    db_user = get_user(user.id)
    status_icon = CHECK if is_luhn else CROSS
    status_text = "VALID (Luhn Pass)" if is_luhn else "INVALID (Luhn Fail)"
    text = f"""
╔══════════════════════════════╗
║    ✅ CC CHECKER (LUHN)      ║
╚══════════════════════════════╝

💳 *Card:* `{card_num}`
📅 *Expiry:* `{month}/{year}`
🔑 *CVV:* `{cvv}`
{LINE}
🏷️ *Brand:* `{brand}`
{status_icon} *Status:* `{status_text}`
{LINE}
💰 Credits Left: `{db_user['credits']}` {"(∞)" if is_developer(user.id) else ""}

{WARN} _Luhn check only — not a live payment check_
_For educational purposes only_
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_carding_keyboard())

async def cmd_bulk_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(f"{WARN} Usage: `/bulkgen <bin> <quantity>`\n\nMax: 50 cards\nExample: `/bulkgen 457173 10`", parse_mode=ParseMode.MARKDOWN)
        return
    bin_num = context.args[0].strip()
    qty = min(int(context.args[1]) if context.args[1].isdigit() else 10, 50)
    msg = await update.message.reply_text(f"📦 Bulk generating {qty} cards from BIN `{bin_num}`...", parse_mode=ParseMode.MARKDOWN)
    cards = generate_cards_from_bin(bin_num, qty)
    brand = get_card_brand(bin_num)
    db_user = get_user(user.id)
    cards_text = "\n".join(cards)
    header_text = f"╔══ 📦 BULK CC GENERATOR ══╗\nBIN: {bin_num} | Brand: {brand} | Qty: {qty}\n╚══════════════════════════╝\n\n"
    footer_text = f"\n\n⚠️ For educational purposes only\n💰 Credits Left: {db_user['credits']}"
    full = header_text + cards_text + footer_text
    if len(full) > 4096:
        chunks = [cards[i:i+20] for i in range(0, len(cards), 20)]
        await msg.edit_text(header_text + "\n".join(chunks[0]) + f"\n\n...{qty} total cards generated (showing first 20)" + footer_text, parse_mode=None)
    else:
        await msg.edit_text(full, parse_mode=None)

# ─── DISPOSABLE TOOLS COMMANDS ───
async def cmd_tempmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    msg = await update.message.reply_text("📧 Generating temporary email via Emailnator...")
    email = emailnator_get_email()
    db_user = get_user(user.id)
    if email:
        context.user_data["temp_email"] = email
        text = f"""
╔══════════════════════════════╗
║    📧 TEMP EMAIL GENERATED   ║
╚══════════════════════════════╝

📬 *Your Temp Email:*
`{email}`

{LINE}
📋 *How to use:*
• Copy the email above
• Register anywhere using it
• Use `/inbox {email}` to check messages
• Email auto-expires after session

{LINE}
💰 Credits Left: `{db_user['credits']}`

"""
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Check Inbox", callback_data=f"inbox_{email}")],
            [InlineKeyboardButton("🔄 New Email", callback_data="tool_tempmail"), InlineKeyboardButton("« Menu", callback_data="main_menu")],
        ])
    else:
        text = f"""
{CROSS} *Failed to generate temp email*

The Emailnator service may be temporarily unavailable.
Please try again in a moment.

{LINE}
💰 Credits Left: `{db_user['credits']}`
"""
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Retry", callback_data="tool_tempmail"), InlineKeyboardButton("« Menu", callback_data="main_menu")]])
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def cmd_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        saved = context.user_data.get("temp_email")
        if saved:
            email = saved
        else:
            await update.message.reply_text(f"{WARN} Usage: `/inbox <email>`\n\nExample: `/inbox test@gmail.com`", parse_mode=ParseMode.MARKDOWN)
            return
    else:
        email = context.args[0].strip()
    msg = await update.message.reply_text(f"📥 Checking inbox for `{email}`...", parse_mode=ParseMode.MARKDOWN)
    messages = emailnator_get_inbox(email)
    db_user = get_user(user.id)
    if messages:
        text = f"""
╔══════════════════════════════╗
║      📥 INBOX RESULTS        ║
╚══════════════════════════════╝

📧 *Email:* `{email}`
📬 *Messages:* `{len(messages)}`
{LINE}
"""
        for i, m in enumerate(messages[:5], 1):
            subject = m.get("subject", "No Subject")[:50]
            sender = m.get("from", "Unknown")[:30]
            text += f"*{i}.* 📩 {subject}\n   👤 From: `{sender}`\n\n"
        text += f"{LINE}\n💰 Credits Left: `{db_user['credits']}`"
    else:
        text = f"""
╔══════════════════════════════╗
║      📥 INBOX EMPTY          ║
╚══════════════════════════════╝

📧 *Email:* `{email}`
📬 *Messages:* No messages yet

_Inbox may take a moment to update._
{LINE}
💰 Credits Left: `{db_user['credits']}`
"""
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_fakeaddr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    addr = fake_address()
    db_user = get_user(user.id)
    text = f"""
╔══════════════════════════════╗
║   👤 FAKE IDENTITY CARD      ║
╚══════════════════════════════╝

{DIAMOND} *Name:* `{addr['name']}`
{DIAMOND} *DOB:* `{addr['dob']}`
{DIAMOND} *Gender:* `{addr['gender']}`
{LINE}
🏠 *Address:* `{addr['address']}`
🌆 *City:* `{addr['city']}, {addr['state']} {addr['zip']}`
🌎 *Country:* `{addr['country']}`
{LINE}
📞 *Phone:* `{addr['phone']}`
📧 *Email:* `{addr['email']}`
{LINE}
💰 Credits Left: `{db_user['credits']}`

{WARN} _Fake data for testing/privacy only_
"""
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate New", callback_data="tool_fakeaddr")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def cmd_passgen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    length = 16
    if context.args and context.args[0].isdigit():
        length = max(8, min(int(context.args[0]), 64))
    passwords = [generate_password(length, True) for _ in range(5)]
    db_user = get_user(user.id)
    pwd_text = "\n".join([f"`{p}`" for p in passwords])
    text = f"""
╔══════════════════════════════╗
║   🔑 PASSWORD GENERATOR      ║
╚══════════════════════════════╝

🔒 *Length:* `{length}` characters
{LINE}
{pwd_text}
{LINE}
💰 Credits Left: `{db_user['credits']}`

{WARN} _Use a password manager to store securely_
"""
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate New", callback_data="tool_passgen")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

# ─── WEBSITE TOOLS COMMANDS ───
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/status <url>`\nExample: `/status google.com`", parse_mode=ParseMode.MARKDOWN)
        return
    url = context.args[0].strip()
    msg = await update.message.reply_text(f"🌐 Checking status of `{url}`...", parse_mode=ParseMode.MARKDOWN)
    result = check_website_status(url)
    db_user = get_user(user.id)
    status_icon = CHECK if result.get("status") == "Online" else CROSS
    text = f"""
╔══════════════════════════════╗
║   🌐 WEBSITE STATUS CHECKER  ║
╚══════════════════════════════╝

🔗 *URL:* `{result.get('url', url)}`
{LINE}
{status_icon} *Status:* `{result.get('status', 'Unknown')}`
📊 *HTTP Code:* `{result.get('status_code', 'N/A')}`
⚡ *Response Time:* `{result.get('response_time', 'N/A')}`
🖥️ *Server:* `{result.get('server', 'N/A')}`
📄 *Content Type:* `{result.get('content_type', 'N/A')}`
{LINE}
💰 Credits Left: `{db_user['credits']}`
"""
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_iplookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/iplookup <host or IP>`\nExample: `/iplookup google.com`", parse_mode=ParseMode.MARKDOWN)
        return
    host = context.args[0].strip()
    msg = await update.message.reply_text(f"🌍 Looking up `{host}`...", parse_mode=ParseMode.MARKDOWN)
    result = ip_lookup(host)
    db_user = get_user(user.id)
    if "error" in result:
        text = f"{CROSS} Lookup failed: `{result['error']}`"
    else:
        text = f"""
╔══════════════════════════════╗
║      🌍 IP LOOKUP RESULT     ║
╚══════════════════════════════╝

🔗 *Host:* `{result.get('hostname', host)}`
🌐 *IP:* `{result.get('ip', 'N/A')}`
{LINE}
🌆 *City:* `{result.get('city', 'N/A')}`
🗺️ *Region:* `{result.get('region', 'N/A')}`
🌍 *Country:* `{result.get('country', 'N/A')}`
🏢 *ISP/Org:* `{result.get('org', 'N/A')}`
🕐 *Timezone:* `{result.get('timezone', 'N/A')}`
📍 *Lat/Lng:* `{result.get('latitude', 'N/A')}, {result.get('longitude', 'N/A')}`
{LINE}
💰 Credits Left: `{db_user['credits']}`
"""
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_ssl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/ssl <domain>`\nExample: `/ssl google.com`", parse_mode=ParseMode.MARKDOWN)
        return
    domain = context.args[0].strip()
    msg = await update.message.reply_text(f"🔒 Checking SSL for `{domain}`...", parse_mode=ParseMode.MARKDOWN)
    result = get_ssl_info(domain)
    db_user = get_user(user.id)
    if "error" in result:
        text = f"{CROSS} SSL check failed: `{result['error']}`\n\nDomain may not support HTTPS or is unreachable."
    else:
        text = f"""
╔══════════════════════════════╗
║      🔒 SSL CERTIFICATE      ║
╚══════════════════════════════╝

🌐 *Domain:* `{result.get('domain', domain)}`
{LINE}
🏢 *Issuer:* `{result.get('issuer', 'N/A')}`
📋 *Subject:* `{result.get('subject', 'N/A')}`
📅 *Valid From:* `{result.get('valid_from', 'N/A')}`
📅 *Valid To:* `{result.get('valid_to', 'N/A')}`
{LINE}
💰 Credits Left: `{db_user['credits']}`
"""
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_whois(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/whois <domain>`\nExample: `/whois google.com`", parse_mode=ParseMode.MARKDOWN)
        return
    domain = context.args[0].strip()
    msg = await update.message.reply_text(f"📋 Looking up WHOIS for `{domain}`...", parse_mode=ParseMode.MARKDOWN)
    result = get_whois(domain)
    db_user = get_user(user.id)
    if "error" in result:
        text = f"{CROSS} WHOIS lookup failed: `{result['error']}`"
    else:
        text = f"""
╔══════════════════════════════╗
║      📋 WHOIS LOOKUP         ║
╚══════════════════════════════╝

🌐 *Domain:* `{result.get('domain', domain)}`
🌐 *IP:* `{result.get('ip', 'N/A')}`
{LINE}
🏢 *Organization:* `{result.get('org', 'N/A')}`
🌍 *Country:* `{result.get('country', 'N/A')}`
🌆 *City:* `{result.get('city', 'N/A')}`
📡 *ASN:* `{result.get('asn', 'N/A')}`
{LINE}
💰 Credits Left: `{db_user['credits']}`
"""
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_url_encode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/urlencode <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = url_encode(text_in)
    db_user = get_user(user.id)
    await update.message.reply_text(
        f"🔗 *URL Encode*\n{LINE}\n*Input:* `{text_in[:100]}`\n*Output:*\n`{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
    )

async def cmd_url_decode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/urldecode <encoded_text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = url_decode(text_in)
    db_user = get_user(user.id)
    await update.message.reply_text(
        f"🔗 *URL Decode*\n{LINE}\n*Input:* `{text_in[:100]}`\n*Output:*\n`{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
    )

async def cmd_html_encode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/htmlenc <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = html_encode(text_in)
    db_user = get_user(user.id)
    await update.message.reply_text(
        f"🌐 *HTML Encode*\n{LINE}\n*Input:* `{text_in[:100]}`\n*Output:*\n`{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
    )

async def cmd_html_decode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/htmldec <encoded_text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = html_decode(text_in)
    db_user = get_user(user.id)
    await update.message.reply_text(
        f"🌐 *HTML Decode*\n{LINE}\n*Input:* `{text_in[:100]}`\n*Output:*\n`{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
    )

# ─── DEVELOPER TOOLS ───
async def cmd_b64enc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/b64enc <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = base64_encode(text_in)
    db_user = get_user(user.id)
    await update.message.reply_text(
        f"📦 *Base64 Encode*\n{LINE}\n*Input:* `{text_in[:100]}`\n*Output:*\n`{result}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
    )

async def cmd_b64dec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/b64dec <base64_text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = base64_decode(text_in)
    db_user = get_user(user.id)
    await update.message.reply_text(
        f"📦 *Base64 Decode*\n{LINE}\n*Input:* `{text_in[:100]}`\n*Output:*\n`{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
    )

async def cmd_md5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/md5 <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = md5_hash(text_in)
    db_user = get_user(user.id)
    await update.message.reply_text(
        f"#️⃣ *MD5 Hash*\n{LINE}\n*Input:* `{text_in[:100]}`\n*Hash:*\n`{result}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
    )

async def cmd_sha256(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/sha256 <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = sha256_hash(text_in)
    db_user = get_user(user.id)
    await update.message.reply_text(
        f"🔐 *SHA256 Hash*\n{LINE}\n*Input:* `{text_in[:100]}`\n*Hash:*\n`{result}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
    )

async def cmd_uuid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    uuids = [generate_uuid() for _ in range(5)]
    db_user = get_user(user.id)
    uuid_text = "\n".join([f"`{u}`" for u in uuids])
    await update.message.reply_text(
        f"🆔 *UUID Generator*\n{LINE}\n{uuid_text}\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
    )

async def cmd_email_val(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/emailval <email>`", parse_mode=ParseMode.MARKDOWN)
        return
    email = context.args[0].strip()
    valid = is_valid_email(email)
    db_user = get_user(user.id)
    icon = CHECK if valid else CROSS
    status = "Valid" if valid else "Invalid"
    await update.message.reply_text(
        f"✉️ *Email Validator*\n{LINE}\n*Email:* `{email}`\n{icon} *Status:* `{status}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
    )

async def cmd_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/color <#hex or rgb(r,g,b)>`\nExample: `/color #FF5733`", parse_mode=ParseMode.MARKDOWN)
        return
    value = " ".join(context.args)
    result = color_converter(value)
    db_user = get_user(user.id)
    if "error" in result:
        await update.message.reply_text(f"{CROSS} {result['error']}", parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text(
        f"🎨 *Color Converter*\n{LINE}\n🔷 *HEX:* `{result.get('hex', 'N/A')}`\n🔴 *RGB:* `{result.get('rgb', 'N/A')}`\n\nR: `{result.get('r')}` | G: `{result.get('g')}` | B: `{result.get('b')}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
    )

# ─── MATH & NUMBER TOOLS ───
async def cmd_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/age <DD/MM/YYYY>`\nExample: `/age 15/08/1995`", parse_mode=ParseMode.MARKDOWN)
        return
    result = age_calculator(context.args[0])
    db_user = get_user(user.id)
    if "error" in result:
        await update.message.reply_text(f"{CROSS} {result['error']}", parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text(
        f"📅 *Age Calculator*\n{LINE}\n🎂 *DOB:* `{result['dob']}`\n🗓️ *Day Born:* `{result['day_of_week']}`\n{LINE}\n🎯 *Age:* `{result['age']} years old`\n📆 *Days Lived:* `{result['days_lived']:,}`\n🎈 *Days to Birthday:* `{result['days_to_birthday']}`\n⭐ *Zodiac:* `{result['zodiac']}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
    )

async def cmd_avg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/avg <n1> <n2> <n3> ...`\nExample: `/avg 10 20 30 40`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        nums = [float(x) for x in context.args]
        result = average_calculator(nums)
        db_user = get_user(user.id)
        await update.message.reply_text(
            f"📊 *Average Calculator*\n{LINE}\n📈 *Count:* `{result['count']}`\n➕ *Sum:* `{result['sum']}`\n📊 *Average:* `{result['average']:.4f}`\n⬇️ *Min:* `{result['min']}`\n⬆️ *Max:* `{result['max']}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
        )
    except ValueError:
        await update.message.reply_text(f"{CROSS} Invalid numbers. Use: `/avg 10 20 30`", parse_mode=ParseMode.MARKDOWN)

async def make_conv_cmd(func, name, emoji, usage):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        get_user(user.id, user.username or "")
        if not await check_credits_and_use(update, user.id):
            return
        if not context.args:
            await update.message.reply_text(f"{WARN} Usage: `/{usage}`", parse_mode=ParseMode.MARKDOWN)
            return
        val = context.args[0].strip()
        result = func(val)
        db_user = get_user(user.id)
        await update.message.reply_text(
            f"{emoji} *{name}*\n{LINE}\n*Input:* `{val}`\n*Output:* `{result}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
        )
    return handler

# ─── TEXT TOOLS ───
async def make_text_cmd(func_name, display_name, emoji):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        get_user(user.id, user.username or "")
        if not await check_credits_and_use(update, user.id):
            return
        if not context.args:
            await update.message.reply_text(f"{WARN} Usage: `/{func_name} <text>`", parse_mode=ParseMode.MARKDOWN)
            return
        text_in = " ".join(context.args)
        result = case_convert(text_in, func_name.replace("swapcase", "swap").replace("title", "title").replace("upper", "upper").replace("lower", "lower"))
        db_user = get_user(user.id)
        await update.message.reply_text(
            f"{emoji} *{display_name}*\n{LINE}\n*Input:* `{text_in[:200]}`\n*Output:*\n`{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
        )
    return handler

async def cmd_upper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/upper <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = case_convert(text_in, "upper")
    db_user = get_user(user.id)
    await update.message.reply_text(f"🔠 *Uppercase*\n{LINE}\n`{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_lower(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/lower <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = case_convert(text_in, "lower")
    db_user = get_user(user.id)
    await update.message.reply_text(f"🔡 *Lowercase*\n{LINE}\n`{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/title <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = case_convert(text_in, "title")
    db_user = get_user(user.id)
    await update.message.reply_text(f"📝 *Title Case*\n{LINE}\n`{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_swapcase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/swapcase <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = case_convert(text_in, "swap")
    db_user = get_user(user.id)
    await update.message.reply_text(f"🔀 *Swap Case*\n{LINE}\n`{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_reverse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/reverse <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = reverse_text(text_in)
    db_user = get_user(user.id)
    await update.message.reply_text(f"↩️ *Reverse Text*\n{LINE}\n*Input:* `{text_in[:200]}`\n*Output:*\n`{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_wordcount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/wordcount <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = word_count(text_in)
    db_user = get_user(user.id)
    await update.message.reply_text(
        f"📊 *Word Count*\n{LINE}\n📝 Words: `{result['words']}`\n🔤 Characters: `{result['chars']}`\n🔡 Chars (no spaces): `{result['chars_no_spaces']}`\n📄 Lines: `{result['lines']}`\n💬 Sentences: `{result['sentences']}`\n📋 Paragraphs: `{result['paragraphs']}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
    )

async def cmd_commasep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/commasep <number>`\nExample: `/commasep 1000000`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = context.args[0]
    result = comma_separator(text_in)
    db_user = get_user(user.id)
    await update.message.reply_text(f"📋 *Comma Separator*\n{LINE}\n*Input:* `{text_in}`\n*Output:* `{result}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

# ─── CONVERTER TOOLS ───
async def cmd_temp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 3:
        await update.message.reply_text(f"{WARN} Usage: `/temp <value> <FROM> <TO>`\nUnits: C, F, K\nExample: `/temp 100 C F`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        val = float(context.args[0])
        from_u = context.args[1].upper()
        to_u = context.args[2].upper()
        result = temperature_convert(val, from_u, to_u)
        db_user = get_user(user.id)
        await update.message.reply_text(
            f"🌡️ *Temperature Converter*\n{LINE}\n*Input:* `{val}°{from_u}`\n*Output:* `{result:.4f}°{to_u}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
        )
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid input. Example: `/temp 100 C F`", parse_mode=ParseMode.MARKDOWN)

async def cmd_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 3:
        await update.message.reply_text(f"{WARN} Usage: `/currency <amount> <FROM> <TO>`\nExample: `/currency 100 USD EUR`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        amount = float(context.args[0])
        from_c = context.args[1].upper()
        to_c = context.args[2].upper()
        msg = await update.message.reply_text(f"💱 Converting {amount} {from_c} to {to_c}...")
        result = currency_convert(amount, from_c, to_c)
        db_user = get_user(user.id)
        if "error" in result:
            await msg.edit_text(f"{CROSS} {result['error']}", parse_mode=ParseMode.MARKDOWN)
        else:
            await msg.edit_text(
                f"💱 *Currency Converter*\n{LINE}\n💵 *Amount:* `{amount} {from_c}`\n💶 *Converted:* `{result['converted']:.4f} {to_c}`\n📊 *Rate:* `1 {from_c} = {result['rate']:.6f} {to_c}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
                parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
            )
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid input. Example: `/currency 100 USD EUR`", parse_mode=ParseMode.MARKDOWN)

# ─── FINANCE TOOLS ───
async def cmd_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(f"{WARN} Usage: `/discount <price> <discount%>`\nExample: `/discount 1000 25`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        price = float(context.args[0])
        disc = float(context.args[1])
        result = discount_calculator(price, disc)
        db_user = get_user(user.id)
        await update.message.reply_text(
            f"🏷️ *Discount Calculator*\n{LINE}\n💰 Original Price: `${result['original']:,.2f}`\n🏷️ Discount: `{result['discount_pct']}%`\n💸 You Save: `${result['savings']:,.2f}`\n✅ Final Price: `${result['final_price']:,.2f}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
        )
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid input. Example: `/discount 1000 25`", parse_mode=ParseMode.MARKDOWN)

async def cmd_gst(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(f"{WARN} Usage: `/gst <amount> <gst_rate%>`\nExample: `/gst 1000 18`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        amount = float(context.args[0])
        rate = float(context.args[1])
        result = gst_calculator(amount, rate)
        db_user = get_user(user.id)
        await update.message.reply_text(
            f"🧾 *GST Calculator*\n{LINE}\n💵 Original Amount: `${result['original']:,.2f}`\n📊 GST Rate: `{result['gst_rate']}%`\n🏛️ GST Amount: `${result['gst_amount']:,.2f}`\n✅ Total (with GST): `${result['total']:,.2f}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
        )
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid input. Example: `/gst 1000 18`", parse_mode=ParseMode.MARKDOWN)

async def cmd_cpm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(f"{WARN} Usage: `/cpm <impressions> <cost>`\nExample: `/cpm 50000 250`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        impressions = float(context.args[0])
        cost = float(context.args[1])
        result = cpm_calculator(impressions, cost)
        db_user = get_user(user.id)
        await update.message.reply_text(
            f"📢 *CPM Calculator*\n{LINE}\n👁️ Impressions: `{result['impressions']:,.0f}`\n💵 Total Cost: `${result['cost']:,.2f}`\n📊 CPM: `${result['cpm']:.4f}` per 1,000 impressions\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
        )
    except (ValueError, IndexError):
        await update.message.reply_text(f"{CROSS} Invalid input. Example: `/cpm 50000 250`", parse_mode=ParseMode.MARKDOWN)

# ─── NUMBER CONVERSION COMMANDS ───
async def cmd_bin2dec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/bin2dec <binary>`\nExample: `/bin2dec 1010`", parse_mode=ParseMode.MARKDOWN)
        return
    val = context.args[0]
    result = binary_to_decimal(val)
    db_user = get_user(user.id)
    await update.message.reply_text(f"🔢 *Binary → Decimal*\n{LINE}\nBinary: `{val}`\nDecimal: `{result}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_dec2bin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/dec2bin <number>`\nExample: `/dec2bin 42`", parse_mode=ParseMode.MARKDOWN)
        return
    val = context.args[0]
    result = decimal_to_binary(val)
    db_user = get_user(user.id)
    await update.message.reply_text(f"🔢 *Decimal → Binary*\n{LINE}\nDecimal: `{val}`\nBinary: `{result}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_hex2dec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/hex2dec <hex>`\nExample: `/hex2dec FF`", parse_mode=ParseMode.MARKDOWN)
        return
    val = context.args[0]
    result = hex_to_decimal(val)
    db_user = get_user(user.id)
    await update.message.reply_text(f"🔡 *Hex → Decimal*\n{LINE}\nHex: `{val}`\nDecimal: `{result}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_dec2hex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/dec2hex <number>`\nExample: `/dec2hex 255`", parse_mode=ParseMode.MARKDOWN)
        return
    val = context.args[0]
    result = decimal_to_hex(val)
    db_user = get_user(user.id)
    await update.message.reply_text(f"🔡 *Decimal → Hex*\n{LINE}\nDecimal: `{val}`\nHex: `{result}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_oct2dec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/oct2dec <octal>`\nExample: `/oct2dec 77`", parse_mode=ParseMode.MARKDOWN)
        return
    val = context.args[0]
    result = octal_to_decimal(val)
    db_user = get_user(user.id)
    await update.message.reply_text(f"🔣 *Octal → Decimal*\n{LINE}\nOctal: `{val}`\nDecimal: `{result}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_dec2oct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/dec2oct <number>`\nExample: `/dec2oct 255`", parse_mode=ParseMode.MARKDOWN)
        return
    val = context.args[0]
    result = decimal_to_octal(val)
    db_user = get_user(user.id)
    await update.message.reply_text(f"🔣 *Decimal → Octal*\n{LINE}\nDecimal: `{val}`\nOctal: `{result}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_bin2ascii(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/bin2ascii <binary>`\nExample: `/bin2ascii 01001000 01101001`", parse_mode=ParseMode.MARKDOWN)
        return
    val = " ".join(context.args)
    result = binary_to_ascii(val)
    db_user = get_user(user.id)
    await update.message.reply_text(f"📡 *Binary → ASCII*\n{LINE}\nBinary: `{val[:100]}`\nASCII: `{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_ascii2bin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/ascii2bin <text>`\nExample: `/ascii2bin Hello`", parse_mode=ParseMode.MARKDOWN)
        return
    val = " ".join(context.args)
    result = ascii_to_binary(val)
    db_user = get_user(user.id)
    await update.message.reply_text(f"📡 *ASCII → Binary*\n{LINE}\nText: `{val[:100]}`\nBinary:\n`{result[:800]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_text2hex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/text2hex <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    val = " ".join(context.args)
    result = text_to_hex(val)
    db_user = get_user(user.id)
    await update.message.reply_text(f"🔤 *Text → Hex*\n{LINE}\nText: `{val[:100]}`\nHex: `{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_hex2text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/hex2text <hex>`", parse_mode=ParseMode.MARKDOWN)
        return
    val = " ".join(context.args)
    result = hex_to_text(val)
    db_user = get_user(user.id)
    await update.message.reply_text(f"🔤 *Hex → Text*\n{LINE}\nHex: `{val[:100]}`\nText: `{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

# ─────────────────────────── CALLBACK HANDLER ───────────────────────────
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if data == "main_menu":
        db_user = get_user(user.id, user.username or "")
        is_dev = is_developer(user.id, user.username or "")
        is_prem = is_user_premium(user.id)
        badge = f"{CROWN} DEVELOPER" if is_dev else (f"{GEM} PREMIUM" if is_prem else f"{STAR2} FREE USER")
        text = f"""
╔══════════════════════════════╗
║  {BOT_NAME}  
╚══════════════════════════════╝

{BOLT} *{user.first_name}'s Dashboard* {BOLT}
{LINE}
{DIAMOND} Status: `{badge}`
{DIAMOND} Credits: `{db_user['credits']}` {"(∞)" if is_dev else ""}
{LINE}
🎯 *Select a category:*
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())

    elif data == "menu_carding":
        text = f"""
╔══════════════════════════════╗
║     💳 CARDING TOOLS         ║
╚══════════════════════════════╝

{WARN} *Educational Use Only*
{LINE}
Select a tool from below:

💳 *BIN Checker* — Lookup BIN info
🔎 *BIN Finder* — Search BINs by criteria  
⚙️ *CC Generator* — Generate test cards
✅ *CC Checker* — Luhn algorithm validation
📦 *Bulk CC Gen* — Generate multiple cards
🔗 *BIN Share* — BIN information sharing

{LINE}
_Each tool costs 1 credit_
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=carding_keyboard())

    elif data == "menu_disposable":
        text = f"""
╔══════════════════════════════╗
║    🔒 DISPOSABLE TOOLS       ║
╚══════════════════════════════╝
{LINE}
📧 *Temp Email* — Generate disposable email
📥 *Check Inbox* — Read temp email messages
👤 *Fake Address* — Random US identity
🔑 *Password Gen* — Secure random passwords

{LINE}
_Each tool costs 1 credit_
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=disposable_keyboard())

    elif data == "menu_website":
        text = f"""
╔══════════════════════════════╗
║     🌐 WEBSITE TOOLS         ║
╚══════════════════════════════╝
{LINE}
🌐 *Site Status* — Check if website is up
🌍 *IP Lookup* — IP geolocation info
🔒 *SSL Info* — SSL certificate details
📋 *WHOIS* — Domain registration info
🔗 *URL Encode/Decode* — URL encoding
🌐 *HTML Encode/Decode* — HTML entities

{LINE}
_Each tool costs 1 credit_
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=website_keyboard())

    elif data == "menu_devtools":
        text = f"""
╔══════════════════════════════╗
║    🔧 DEVELOPER TOOLS        ║
╚══════════════════════════════╝
{LINE}
📦 *Base64 Encode/Decode*
#️⃣ *MD5 Hash*
🔐 *SHA256 Hash*
🆔 *UUID Generator*
✉️ *Email Validator*
🎨 *Color Converter*

{LINE}
_Each tool costs 1 credit_
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=devtools_keyboard())

    elif data == "menu_math":
        text = f"""
╔══════════════════════════════╗
║    🔢 NUMBER & MATH TOOLS    ║
╚══════════════════════════════╝
{LINE}
📅 Age Calculator
📊 Average Calculator
🔢 Binary ↔ Decimal
🔡 Hex ↔ Decimal
🔣 Octal ↔ Decimal
📡 ASCII ↔ Binary
🔤 Text ↔ Hex

{LINE}
_Each tool costs 1 credit_
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=math_keyboard())

    elif data == "menu_text":
        text = f"""
╔══════════════════════════════╗
║       📝 TEXT TOOLS          ║
╚══════════════════════════════╝
{LINE}
🔠 Uppercase / 🔡 Lowercase
📝 Title Case / 🔀 Swap Case
↩️ Reverse Text
📊 Word/Character Count
📋 Comma Separator

{LINE}
_Each tool costs 1 credit_
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=text_keyboard())

    elif data == "menu_converters":
        text = f"""
╔══════════════════════════════╗
║      🔄 CONVERTER TOOLS      ║
╚══════════════════════════════╝
{LINE}
🌡️ *Temperature* — C, F, K conversion
💱 *Currency* — Real-time exchange rates

{LINE}
_Each tool costs 1 credit_
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=converters_keyboard())

    elif data == "menu_finance":
        text = f"""
╔══════════════════════════════╗
║      💰 FINANCE TOOLS        ║
╚══════════════════════════════╝
{LINE}
🏷️ *Discount Calculator* — Price savings
🧾 *GST Calculator* — Tax calculations
📢 *CPM Calculator* — Ad cost per 1000

{LINE}
_Each tool costs 1 credit_
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=finance_keyboard())

    elif data == "my_credits":
        db_user = get_user(user.id, user.username or "")
        is_dev = is_developer(user.id, user.username or "")
        is_prem = is_user_premium(user.id)
        next_reset = (date.today() + timedelta(days=1)).strftime("%d %b %Y")
        daily = "∞ Unlimited" if is_dev else (str(PREMIUM_DAILY_CREDITS) if is_prem else str(FREE_DAILY_CREDITS))
        status = f"{CROWN} Developer" if is_dev else (f"{GEM} Premium" if is_prem else f"{STAR2} Free")
        text = f"""
╔══════════════════════════════╗
║      💎 CREDITS PANEL        ║
╚══════════════════════════════╝

{DIAMOND} Status: `{status}`
{BOLT} Credits: `{db_user['credits']}` {"(∞)" if is_dev else ""}
{BULLET} Daily Limit: `{daily}`
{BULLET} Total Used: `{db_user.get('total_used', 0)}`
{BULLET} Next Reset: `{next_reset}`
{LINE}
💡 Upgrade to Premium for 100 credits/day
Contact: @{DEVELOPER_USERNAME}
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

    elif data == "premium_info":
        text = f"""
╔══════════════════════════════╗
║    👑 PREMIUM MEMBERSHIP     ║
╚══════════════════════════════╝

{GEM} *Premium Benefits:*
{LINE}
  ✦ 100 credits/day (vs 10 free)
  ✦ Access to all premium tools
  ✦ Priority processing
  ✦ Premium badge
  ✦ No restrictions
{LINE}
📩 Contact: @{DEVELOPER_USERNAME}
"""
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📩 Contact Dev", url=f"https://t.me/{DEVELOPER_USERNAME}")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif data == "disclaimer":
        await query.edit_message_text(DISCLAIMER_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

    elif data == "referral_menu":
        db_user = get_user(user.id, user.username or "")
        is_dev = is_developer(user.id, user.username or "")
        ref_code = db_user.get("ref_code") or generate_ref_code(user.id)
        referrals  = db_user.get("referrals", 0)
        ref_earned = db_user.get("ref_credits_earned", 0)
        referred_by = db_user.get("referred_by")
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={ref_code}"
        text = f"""
╔══════════════════════════════╗
║    🔗 REFERRAL PROGRAM       ║
╚══════════════════════════════╝

{ROCKET} *Invite friends & earn free credits!*
{LINE}
🎯 *Your Referral Code:*
`{ref_code}`

🔗 *Your Referral Link:*
`{ref_link}`

{LINE}
📊 *Your Stats:*
{DIAMOND} Total Referrals: `{referrals}`
{BOLT} Credits Earned via Refs: `{ref_earned}`
{DIAMOND} Referred By: `{"Someone ✅" if referred_by else "Nobody yet"}`

{LINE}
💎 *Rewards:*
{BULLET} You earn `+{REFERRAL_BONUS_REFERRER} credits` per referral
{BULLET} Friend gets `+{REFERRAL_BONUS_NEW_USER}` bonus credits
{LINE}
💰 Your Credits: `{db_user['credits']}` {"(∞)" if is_dev else ""}
"""
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Share My Link", switch_inline_query=f"Join {BOT_NAME}! Use my link: {ref_link}")],
            [InlineKeyboardButton("🔄 Refresh Stats", callback_data="referral_menu"),
             InlineKeyboardButton("💎 Credits", callback_data="my_credits")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif data == "leaderboard_menu":
        get_user(user.id, user.username or "")
        text = build_leaderboard_text(user.id)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 My Referral Link", callback_data="referral_menu"),
             InlineKeyboardButton("🔄 Refresh", callback_data="leaderboard_menu")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif data == "claim_daily":
        uid_str = str(user.id)
        raw_data = load_data()
        db_user = get_user(user.id, user.username or "")
        today = str(date.today())
        yesterday = str(date.today() - timedelta(days=1))
        last_claim = db_user.get("last_claim")
        streak = db_user.get("streak", 0)
        if last_claim == today:
            next_claim = (date.today() + timedelta(days=1)).strftime("%d %b %Y")
            streak_bar = "🔥" * min(streak, 10)
            await query.edit_message_text(
                f"⏳ *Already Claimed Today!*\n{LINE}\n"
                f"🔥 Streak: {streak_bar} `{streak} days`\n"
                f"⏰ Next Claim: `{next_claim}`\n{LINE}\n_Come back tomorrow!_",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]),
            )
            return
        streak = (streak + 1) if last_claim == yesterday else 1
        base = CLAIM_BASE_CREDITS
        streak_bonus = min((streak // 5) * CLAIM_STREAK_BONUS_PER_5, CLAIM_MAX_BONUS)
        total = base + streak_bonus
        raw_data["users"][uid_str]["last_claim"] = today
        raw_data["users"][uid_str]["streak"] = streak
        raw_data["users"][uid_str]["credits"] = db_user.get("credits", 0) + total
        save_data(raw_data)
        track_tool_usage("claim")
        streak_bar = "🔥" * min(streak, 10)
        milestone = f"\n🏅 *{streak}-Day Milestone!*" if streak % 7 == 0 else ""
        await query.edit_message_text(
            f"🎁 *Daily Reward Claimed!*\n{LINE}\n"
            f"⚡ Base: `+{base}` | Streak Bonus: `+{streak_bonus}`\n"
            f"💰 Total: `+{total} credits`\n{LINE}\n"
            f"🔥 Streak: {streak_bar} `{streak} days`\n"
            f"💎 Balance: `{raw_data['users'][uid_str]['credits']} credits`{milestone}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 My Credits", callback_data="my_credits")],
                [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
            ]),
        )

    elif data == "menu_games":
        db_user = get_user(user.id, user.username or "")
        text = (
            f"╔══════════════════════════════╗\n"
            f"║       🎰 GAMES CENTER        ║\n"
            f"╚══════════════════════════════╝\n{LINE}\n\n"
            f"🎲 *Dice Game* — `/dice <bet>`\n"
            f"   Roll 4-6 = win 2× | Roll 1-3 = lose\n\n"
            f"🪙 *Coin Flip* — `/flip <bet> <h/t>`\n"
            f"   Pick heads or tails, win 2×!\n\n{LINE}\n"
            f"🎯 Min bet: `{GAME_MIN_BET}` | Max bet: `{GAME_MAX_BET}`\n"
            f"💎 Your Credits: `{db_user['credits']}`\n{LINE}\n"
            f"⚠️ _Gambling can deplete your credits. Bet wisely!_"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 Play Dice", callback_data="game_dice_info"),
             InlineKeyboardButton("🪙 Play Flip", callback_data="game_flip_info")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif data == "game_dice_info":
        db_user = get_user(user.id, user.username or "")
        await query.edit_message_text(
            f"🎲 *Dice Game*\n{LINE}\n"
            f"Use: `/dice <bet>` in chat\n\n"
            f"▸ Roll 4–6 → Win `2×` your bet\n"
            f"▸ Roll 1–3 → Lose your bet\n\n"
            f"Min: `{GAME_MIN_BET}` | Max: `{GAME_MAX_BET}`\n"
            f"💎 Your Credits: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎰 Back to Games", callback_data="menu_games")],
                [InlineKeyboardButton("« Main Menu", callback_data="main_menu")],
            ]),
        )

    elif data == "game_flip_info":
        db_user = get_user(user.id, user.username or "")
        await query.edit_message_text(
            f"🪙 *Coin Flip Game*\n{LINE}\n"
            f"Use: `/flip <bet> <h or t>` in chat\n\n"
            f"▸ Guess correctly → Win `2×` your bet\n"
            f"▸ Wrong guess → Lose your bet\n\n"
            f"Min: `{GAME_MIN_BET}` | Max: `{GAME_MAX_BET}`\n"
            f"💎 Your Credits: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎰 Back to Games", callback_data="menu_games")],
                [InlineKeyboardButton("« Main Menu", callback_data="main_menu")],
            ]),
        )

    elif data == "crypto_refresh":
        await query.edit_message_text(
            "₿ _Fetching live crypto prices…_", parse_mode=ParseMode.MARKDOWN
        )
        prices = get_crypto_prices()
        if "error" in prices:
            await query.edit_message_text(
                f"{CROSS} *Failed to fetch prices*\nError: `{prices['error']}`\n_Try again._",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Retry", callback_data="crypto_refresh")],
                    [InlineKeyboardButton("« Main Menu", callback_data="main_menu")],
                ]),
            )
            return
        text = build_crypto_text(prices)
        track_tool_usage("crypto")
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh Prices", callback_data="crypto_refresh")],
                [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
            ]),
        )

    elif data.startswith("dice_again_"):
        try:
            bet = int(data.split("_")[2])
        except (IndexError, ValueError):
            bet = 1
        db_user  = get_user(user.id, user.username or "")
        is_dev   = is_developer(user.id, user.username or "")
        faces    = {1:"1️⃣",2:"2️⃣",3:"3️⃣",4:"4️⃣",5:"5️⃣",6:"6️⃣"}
        if db_user["credits"] < bet and not is_dev:
            await query.answer(f"Not enough credits! You have {db_user['credits']}.", show_alert=True)
            return
        roll = random.randint(1, 6)
        raw  = load_data()
        uid  = str(user.id)
        cur  = db_user["credits"]
        if roll >= 4:
            nc = cur + bet if not is_dev else cur
            res = f"🎉 *YOU WIN!*\n{faces[roll]} Rolled `{roll}`!\n💰 Won: `+{bet} credits`"
        else:
            nc = max(0, cur - bet) if not is_dev else cur
            res = f"😢 *YOU LOSE!*\n{faces[roll]} Rolled `{roll}`!\n💸 Lost: `-{bet} credits`"
        raw["users"][uid]["credits"] = nc
        save_data(raw)
        track_tool_usage("dice")
        await query.edit_message_text(
            f"🎲 *DICE GAME*\n{LINE}\n{res}\n\n💎 Balance: `{nc} credits`\n{LINE}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🎲 Roll Again ({bet} bet)", callback_data=f"dice_again_{bet}")],
                [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
            ]),
        )

    elif data.startswith("flip_again_"):
        parts = data.split("_")
        try:
            bet    = int(parts[2])
            choice = parts[3] if len(parts) > 3 else "h"
        except (IndexError, ValueError):
            bet, choice = 1, "h"
        db_user = get_user(user.id, user.username or "")
        is_dev  = is_developer(user.id, user.username or "")
        if db_user["credits"] < bet and not is_dev:
            await query.answer(f"Not enough credits! You have {db_user['credits']}.", show_alert=True)
            return
        result      = random.choice(("h","t"))
        chose_heads = choice.startswith("h")
        landed_heads = result == "h"
        won         = chose_heads == landed_heads
        coin_show   = "🪙 *HEADS*" if landed_heads else "🪙 *TAILS*"
        choice_show = "Heads" if chose_heads else "Tails"
        raw  = load_data()
        uid  = str(user.id)
        cur  = db_user["credits"]
        if won:
            nc  = cur + bet if not is_dev else cur
            res = f"🎉 *YOU WIN!*\n{coin_show}\nYou picked `{choice_show}` ✅\n💰 Won: `+{bet} credits`"
        else:
            nc  = max(0, cur - bet) if not is_dev else cur
            res = f"😢 *YOU LOSE!*\n{coin_show}\nYou picked `{choice_show}` ❌\n💸 Lost: `-{bet} credits`"
        raw["users"][uid]["credits"] = nc
        save_data(raw)
        track_tool_usage("flip")
        await query.edit_message_text(
            f"🪙 *COIN FLIP*\n{LINE}\n{res}\n\n💎 Balance: `{nc} credits`\n{LINE}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🪙 Flip Again ({bet} bet)", callback_data=f"flip_again_{bet}_{choice[0]}")],
                [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
            ]),
        )

    elif data.startswith("slots_again_"):
        try:
            bet = int(data.split("_")[2])
        except (IndexError, ValueError):
            bet = 1
        ok, text, kb = await _do_slots(None, user.id, user.username or "", bet)
        if not ok:
            await query.answer(text.replace("`",""), show_alert=True)
            return
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif data.startswith("roulette_again_"):
        parts = data.split("_")
        try:
            bet    = int(parts[2])
            choice = "_".join(parts[3:])
        except (IndexError, ValueError):
            bet, choice = 1, "red"
        db_user = get_user(user.id, user.username or "")
        is_dev  = is_developer(user.id, user.username or "")
        if db_user["credits"] < bet and not is_dev:
            await query.answer(f"Not enough credits!", show_alert=True)
            return
        spin       = random.randint(0, 36)
        spin_color = "🟢" if spin == 0 else ("🔴" if spin in ROULETTE_RED else "⚫")
        won, mult, choice_disp = False, 0, choice
        c = choice.lower().strip()
        if c == "red":   won, mult = spin in ROULETTE_RED, 2
        elif c == "black": won, mult = spin in ROULETTE_BLACK, 2
        elif c == "green": won, mult = spin == 0, 15
        elif c == "odd":   won, mult = (spin != 0 and spin % 2 == 1), 2
        elif c == "even":  won, mult = (spin != 0 and spin % 2 == 0), 2
        elif c.isdigit() and 0 <= int(c) <= 36:
            won, mult, choice_disp = spin == int(c), 36, f"#{c}"
        raw = load_data()
        uid = str(user.id)
        cur = db_user["credits"]
        if won:
            net = bet * (mult - 1)
            nc  = cur + net if not is_dev else cur
            res = f"🎉 *YOU WIN!*\n💰 Won: `+{net} credits` (`{mult}×`)"
        else:
            nc  = max(0, cur - bet) if not is_dev else cur
            res = f"😢 *YOU LOSE!*\n💸 Lost: `-{bet} credits`"
        raw["users"][uid]["credits"] = nc
        save_data(raw)
        track_tool_usage("roulette")
        await query.edit_message_text(
            f"🎡 *ROULETTE*\n{LINE}\n"
            f"🎯 Bet: `{bet}` on `{choice_disp}`\n🎰 Ball: {spin_color} `{spin}`\n"
            f"{LINE}\n{res}\n\n💎 Balance: `{nc} credits`\n{LINE}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎡 Spin Again", callback_data=f"roulette_again_{bet}_{choice}")],
                [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
            ]),
        )

    elif data == "bj_hit":
        bj = context.user_data.get("bj")
        if not bj:
            await query.answer("Game expired. Start a new one with /blackjack.", show_alert=True)
            return
        bj["player"].append(_bj_card())
        pv  = _bj_val(bj["player"])
        bet = bj["bet"]
        if pv > 21:
            raw = load_data()
            uid = str(user.id)
            db_user = get_user(user.id)
            nc  = max(0, db_user["credits"] - bet) if not bj["is_dev"] else db_user["credits"]
            raw["users"][uid]["credits"] = nc
            save_data(raw)
            track_tool_usage("blackjack")
            context.user_data.pop("bj", None)
            await query.edit_message_text(
                f"🃏 *BLACKJACK*\n{LINE}\n"
                f"Your hand: {_bj_fmt(bj['player'])} = `{pv}`\n"
                f"{LINE}\n💥 *BUST!* Over 21!\n💸 Lost: `-{bet} credits`\n💎 Balance: `{nc}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]),
            )
        else:
            await query.edit_message_text(
                f"🃏 *BLACKJACK*\n{LINE}\n"
                f"Your hand: {_bj_fmt(bj['player'])} = `{pv}`\n"
                f"Dealer shows: `{bj['dealer'][0][0]}{bj['dealer'][0][1]}` 🂠\n{LINE}\n"
                f"💰 Bet: `{bet} credits`  |  _What do you do?_",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👊 Hit", callback_data="bj_hit"),
                     InlineKeyboardButton("✋ Stand", callback_data="bj_stand")],
                    [InlineKeyboardButton("❌ Forfeit", callback_data="bj_forfeit")],
                ]),
            )

    elif data == "bj_stand":
        bj = context.user_data.get("bj")
        if not bj:
            await query.answer("Game expired. Start a new one with /blackjack.", show_alert=True)
            return
        bet     = bj["bet"]
        db_user = get_user(user.id)
        is_dev  = bj["is_dev"]
        dealer, nc, result_txt, _ = _bj_resolve(bj["player"], bj["dealer"], bet, db_user["credits"], is_dev)
        raw = load_data()
        uid = str(user.id)
        raw["users"][uid]["credits"] = nc
        save_data(raw)
        track_tool_usage("blackjack")
        context.user_data.pop("bj", None)
        await query.edit_message_text(
            f"🃏 *BLACKJACK — RESULT*\n{LINE}\n"
            f"Your hand: {_bj_fmt(bj['player'])} = `{_bj_val(bj['player'])}`\n"
            f"Dealer hand: {_bj_fmt(dealer)} = `{_bj_val(dealer)}`\n{LINE}\n"
            f"{result_txt}\n\n💎 Balance: `{nc} credits`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]),
        )

    elif data == "bj_forfeit":
        bj = context.user_data.get("bj")
        if not bj:
            await query.answer("Game expired.", show_alert=True)
            return
        bet     = bj["bet"]
        db_user = get_user(user.id)
        penalty = max(1, bet // 2)
        raw     = load_data()
        uid     = str(user.id)
        nc      = max(0, db_user["credits"] - penalty) if not bj["is_dev"] else db_user["credits"]
        raw["users"][uid]["credits"] = nc
        save_data(raw)
        context.user_data.pop("bj", None)
        await query.edit_message_text(
            f"🃏 *BLACKJACK — FORFEITED*\n{LINE}\n"
            f"💸 Penalty: `-{penalty} credits` (half bet)\n"
            f"💎 Balance: `{nc} credits`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]),
        )

    elif data == "menu_ports":
        db_user = get_user(user.id, user.username or "")
        text = (
            f"╔══════════════════════════════╗\n"
            f"║    🔌 PORT SCANNER TOOLS     ║\n"
            f"╚══════════════════════════════╝\n{LINE}\n\n"
            f"🔌 *Single Port* — `/portscan <host> <port>`\n"
            f"   Check if one specific port is open\n\n"
            f"🔍 *Common Port Scan* — `/scanports <host>`\n"
            f"   Scan {len(COMMON_PORTS)} common ports at once\n\n{LINE}\n"
            f"_Real TCP socket connections — no simulation!_\n"
            f"_Costs 1 credit per scan_"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔌 Single Port", callback_data="tool_portscan"),
             InlineKeyboardButton("🔍 Scan All", callback_data="tool_scanports")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif data in ("tool_portscan", "tool_scanports"):
        cmd = "portscan" if data == "tool_portscan" else "scanports"
        example = "`/portscan google.com 443`" if cmd == "portscan" else "`/scanports google.com`"
        await query.edit_message_text(
            f"🔌 *Port Scanner*\n{LINE}\nUse the command in chat:\n{example}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="menu_ports")],
                [InlineKeyboardButton("« Main Menu", callback_data="main_menu")],
            ]),
        )

    elif data == "fileqr_cancel":
        context.user_data.pop("awaiting_fileqr", None)
        await query.edit_message_text(f"✖ *Cancelled* — File→QR request cancelled.", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

    elif data.startswith("passgen_"):
        length = int(data.split("_")[1])
        if not await check_credits_and_use_query(query, user.id):
            return
        from string import ascii_letters, digits
        import random as _r, sys as _s
        pwd = generate_password(length, use_symbols=True)
        strength = password_strength(pwd)
        db_user = get_user(user.id)
        await query.edit_message_text(
            f"╔══════════════════════════════╗\n║    🔐 PASSWORD GENERATOR     ║\n╚══════════════════════════════╝\n\n"
            f"🔑 *Generated Password:*\n`{pwd}`\n\n"
            f"📏 *Length:* `{length} characters`\n"
            f"💪 *Strength:* {strength}\n{LINE}\n"
            f"💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Generate Another", callback_data=f"passgen_{length}")],
                [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
            ]),
        )

    elif data == "randomname_gen":
        if not await check_credits_and_use_query(query, user.id):
            return
        gender = _random.choice(["male","female"])
        first = _random.choice(FIRST_NAMES_M if gender == "male" else FIRST_NAMES_F)
        last = _random.choice(LAST_NAMES)
        full = f"{first} {last}"
        username = f"{_random.choice(USERNAMES_ADJ)}_{_random.choice(USERNAMES_NOUN)}{_random.randint(10,999)}"
        age = _random.randint(18, 55)
        year = 2025 - age
        month = _random.randint(1, 12)
        day = _random.randint(1, 28)
        dob = f"{day:02d}/{month:02d}/{year}"
        db_user = get_user(user.id)
        await query.edit_message_text(
            f"╔══════════════════════════════╗\n║    🎭 RANDOM IDENTITY        ║\n╚══════════════════════════════╝\n\n"
            f"👤 *Full Name:* `{full}`\n"
            f"{'♂️' if gender=='male' else '♀️'} *Gender:* `{gender.capitalize()}`\n"
            f"🎂 *Date of Birth:* `{dob}`\n"
            f"📅 *Age:* `{age}`\n"
            f"💻 *Username:* `@{username}`\n{LINE}\n"
            f"💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Generate Another", callback_data="randomname_gen")],
                [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
            ]),
        )

    elif data.startswith("trivia_bet_"):
        bet = int(data.split("_")[2])
        await trivia_start_question(query, user, bet, context)

    elif data.startswith("trivia_ans_"):
        chosen_idx = int(data.split("_")[2])
        state = context.user_data.get(f"trivia_{user.id}")
        if not state:
            await query.edit_message_text("❌ Session expired. Use /trivia to start a new game.", parse_mode=ParseMode.MARKDOWN)
            return
        bet = state["bet"]
        correct_idx = state["correct_idx"]
        options = state["options"]
        context.user_data.pop(f"trivia_{user.id}", None)
        raw = load_data()
        uid = str(user.id)
        db_user = get_user(user.id)
        correct_answer = options[correct_idx]
        chosen_answer = options[chosen_idx]
        if chosen_idx == correct_idx:
            winnings = bet * 2
            raw["users"][uid]["credits"] = db_user["credits"] + bet
            raw["users"][uid]["total_used"] = db_user.get("total_used", 0) + 1
            save_data(raw)
            db_user = get_user(user.id)
            result_text = (
                f"╔══════════════════════════════╗\n║  🧠 TRIVIA — YOU WIN! 🎉    ║\n╚══════════════════════════════╝\n\n"
                f"✅ *Correct!* The answer was:\n`{correct_answer}`\n\n"
                f"💰 *Won:* `+{bet} credits`\n"
                f"💎 *Balance:* `{db_user['credits']} credits`"
            )
        else:
            raw["users"][uid]["credits"] = max(0, db_user["credits"] - bet)
            raw["users"][uid]["total_used"] = db_user.get("total_used", 0) + 1
            save_data(raw)
            db_user = get_user(user.id)
            result_text = (
                f"╔══════════════════════════════╗\n║  🧠 TRIVIA — WRONG ❌        ║\n╚══════════════════════════════╝\n\n"
                f"❌ *You chose:* `{chosen_answer}`\n"
                f"✅ *Correct answer:* `{correct_answer}`\n\n"
                f"💸 *Lost:* `-{bet} credits`\n"
                f"💎 *Balance:* `{db_user['credits']} credits`"
            )
        track_tool_usage("trivia")
        await query.edit_message_text(
            result_text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Play Again", callback_data="trivia_play")],
                [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
            ]),
        )

    elif data == "trivia_play":
        db_user = get_user(user.id)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💰 Bet {b} credits", callback_data=f"trivia_bet_{b}") for b in TRIVIA_BET_OPTIONS[:2]],
            [InlineKeyboardButton(f"💰 Bet {b} credits", callback_data=f"trivia_bet_{b}") for b in TRIVIA_BET_OPTIONS[2:]],
            [InlineKeyboardButton("« Back", callback_data="main_menu")],
        ])
        await query.edit_message_text(
            f"╔══════════════════════════════╗\n║      🧠 TRIVIA CHALLENGE     ║\n╚══════════════════════════════╝\n\n"
            f"🎯 Answer correctly and *win 2× your bet*!\n"
            f"❌ Wrong answer = lose your bet\n{LINE}\n"
            f"💎 Your credits: `{db_user['credits']}`\n\n"
            f"📋 *Choose your bet:*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb,
        )

    elif data.startswith("rps_"):
        choice = data[4:]
        bot_pick = _random.choice(["rock","paper","scissors"])
        emojis = {"rock":"🪨","paper":"📄","scissors":"✂️"}
        result_map = {("rock","scissors"):"win",("paper","rock"):"win",("scissors","paper"):"win",
                      ("rock","paper"):"lose",("paper","scissors"):"lose",("scissors","rock"):"lose"}
        outcome = result_map.get((choice, bot_pick), "draw")
        result_icon = {"win":"🏆 *You win!*","lose":"😔 *You lose!*","draw":"🤝 *It's a draw!*"}[outcome]
        await query.edit_message_text(
            f"🎮 *Rock Paper Scissors*\n{LINE}\n"
            f"You: {emojis[choice]} *{choice.capitalize()}*\n"
            f"Bot: {emojis[bot_pick]} *{bot_pick.capitalize()}*\n{LINE}\n"
            f"{result_icon}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🪨 Rock", callback_data="rps_rock"),
                InlineKeyboardButton("📄 Paper", callback_data="rps_paper"),
                InlineKeyboardButton("✂️ Scissors", callback_data="rps_scissors"),
            ],[InlineKeyboardButton("« Menu", callback_data="main_menu")]]),
        )

    elif data.startswith("8ball_"):
        question = data[6:]
        answer = _random.choice(EIGHT_BALL_RESPONSES)
        await query.edit_message_text(
            f"🎱 *Magic 8-Ball*\n{LINE}\n❓ *Q:* _{question}_\n\n🎱 *A:* {answer}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎱 Ask Again", callback_data=f"8ball_{question}")]]),
        )

    elif data == "quote_refresh":
        try:
            r = requests.get("https://api.quotable.io/random", timeout=8)
            if r.status_code == 200:
                d = r.json()
                text = f"💬 *Daily Quote*\n{LINE}\n\n_{d.get('content','')}_\n\n— *{d.get('author','Unknown')}*"
            else:
                text = f"{CROSS} Could not fetch quote."
        except Exception:
            text = f"{CROSS} Quote service unavailable."
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 Another Quote", callback_data="quote_refresh")],[InlineKeyboardButton("« Menu", callback_data="main_menu")]]))

    elif data == "meme_refresh":
        try:
            r = requests.get("https://meme-api.com/gimme", timeout=10)
            if r.status_code == 200:
                d = r.json()
                await query.delete_message()
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=d.get("url",""),
                    caption=f"😂 *{d.get('title','')}*\n📌 r/{d.get('subreddit','')} • 👍 {d.get('ups',0)}",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("😂 Another Meme", callback_data="meme_refresh")],[InlineKeyboardButton("« Menu", callback_data="main_menu")]]),
                )
                return
        except Exception:
            pass
        await query.answer("Could not fetch meme. Try again!", show_alert=True)

    elif data == "advice_refresh":
        try:
            r = requests.get("https://api.adviceslip.com/advice", timeout=8)
            if r.status_code == 200:
                slip = r.json().get("slip",{})
                text = f"💡 *Life Advice #{slip.get('id','')}*\n{LINE}\n\n_{slip.get('advice','')}_"
            else:
                text = f"{CROSS} Could not fetch advice."
        except Exception:
            text = f"{CROSS} Advice service unavailable."
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💡 More Advice", callback_data="advice_refresh")],[InlineKeyboardButton("« Menu", callback_data="main_menu")]]))

    elif data.startswith("roll_"):
        expr = data[5:]
        import re as _re
        m = _re.match(r"(\d+)d(\d+)([+-]\d+)?", expr)
        if m:
            num_dice = min(int(m.group(1)),20)
            die_sides = min(int(m.group(2)),1000)
            modifier = int(m.group(3)) if m.group(3) else 0
            rolls = [_random.randint(1, die_sides) for _ in range(num_dice)]
            total = sum(rolls) + modifier
            rolls_str = " + ".join(f"`{r}`" for r in rolls)
            mod_str = f" + {modifier}" if modifier > 0 else (f" - {abs(modifier)}" if modifier < 0 else "")
            await query.edit_message_text(
                f"🎲 *Dice Roller*\n{LINE}\n🎯 *Roll:* `{expr}`\n🎲 *Dice:* {rolls_str}{mod_str}\n🏆 *Total:* `{total}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎲 Roll Again", callback_data=f"roll_{expr}")]]),
            )

    elif data == "scramble_skip":
        context.user_data.pop(f"scramble_{user.id}", None)
        await query.edit_message_text("⏭️ Skipped! Use /scramble to play again.", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

    elif data.startswith("scramble_hint_"):
        word = data[14:]
        if not await check_credits_and_use_query(query, user.id):
            return
        hint = word[0] + "_ " * (len(word)-2) + word[-1]
        await query.answer(f"💡 Hint: {hint}", show_alert=True)

    elif data.startswith("hangman_"):
        letter = data[8:]
        state = context.user_data.get(f"hangman_{user.id}")
        if not state:
            await query.edit_message_text("❌ No active game. Use /hangman to start.", parse_mode=ParseMode.MARKDOWN)
            return
        word = state["word"]
        guessed = state["guessed"]
        wrong = state["wrong"]
        guessed.add(letter)
        if letter not in word:
            wrong += 1
        state["wrong"] = wrong
        context.user_data[f"hangman_{user.id}"] = state
        display = " ".join(c if c in guessed else "_" for c in word)
        winner = all(c in guessed for c in word)
        loser = wrong >= 6
        stage = HANGMAN_STAGES[min(wrong, 6)]
        status_line = (f"🎉 *You won!* The word was `{word}`!" if winner else
                       f"💀 *Game over!* The word was `{word}`." if loser else
                       f"❤️ *Lives:* `{6-wrong}/6`")
        kb = _hangman_keyboard(guessed, word) if not (winner or loser) else InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Play Again", callback_data="hangman_new"),InlineKeyboardButton("« Menu", callback_data="main_menu")]])
        if winner or loser:
            context.user_data.pop(f"hangman_{user.id}", None)
            if winner:
                raw = load_data()
                uid = str(user.id)
                if uid in raw.get("users",{}):
                    raw["users"][uid]["credits"] = raw["users"][uid].get("credits",0) + 5
                    save_data(raw)
        await query.edit_message_text(
            f"╔══════════════════════════════╗\n║       🪓 HANGMAN             ║\n╚══════════════════════════════╝\n\n"
            f"{stage}\n\n📝 *Word:* `{display}`\n"
            f"🔤 *Guessed:* `{' '.join(sorted(guessed)).upper() or 'None'}`\n"
            f"{status_line}",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb,
        )

    elif data == "hangman_new":
        word = _random.choice(HANGMAN_WORDS)
        context.user_data[f"hangman_{user.id}"] = {"word": word, "guessed": set(), "wrong": 0}
        display = " ".join("_" for _ in word)
        await query.edit_message_text(
            f"╔══════════════════════════════╗\n║       🪓 HANGMAN             ║\n╚══════════════════════════════╝\n\n"
            f"{HANGMAN_STAGES[0]}\n\n📝 *Word:* `{display}`\n📏 *Letters:* `{len(word)}`\n❤️ *Lives:* `6/6`\n{LINE}\n_Pick a letter:_",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_hangman_keyboard(set(), word),
        )

    elif data.startswith("ttt_"):
        action = data[4:]
        if action == "new":
            board = [TTT_EMPTY]*9
            context.user_data[f"ttt_{user.id}"] = board
            await query.edit_message_text(
                f"╔══════════════════════════════╗\n║    ❌ TIC TAC TOE ⭕         ║\n╚══════════════════════════════╝\n\nYou are ❌, Bot is ⭕\n_Your turn — pick a square:_",
                parse_mode=ParseMode.MARKDOWN, reply_markup=_ttt_keyboard(board),
            )
            return
        try:
            pos = int(action)
        except ValueError:
            return
        board = context.user_data.get(f"ttt_{user.id}", [TTT_EMPTY]*9)
        if board[pos] != TTT_EMPTY:
            await query.answer("That square is taken!", show_alert=True)
            return
        board[pos] = TTT_X
        winner = _ttt_check_winner(board)
        if not winner:
            bot_pos = _ttt_bot_move(board)
            board[bot_pos] = TTT_O
            winner = _ttt_check_winner(board)
        context.user_data[f"ttt_{user.id}"] = board
        game_over = bool(winner)
        if winner == TTT_X:
            status = "🏆 *You win!* Congratulations!"
            raw = load_data()
            uid = str(user.id)
            if uid in raw.get("users",{}):
                raw["users"][uid]["credits"] = raw["users"][uid].get("credits",0) + 5
                save_data(raw)
        elif winner == TTT_O:
            status = "🤖 *Bot wins!* Better luck next time."
        elif winner == "draw":
            status = "🤝 *It's a draw!*"
        else:
            status = "❌ Your turn!"
        if game_over:
            context.user_data.pop(f"ttt_{user.id}", None)
        await query.edit_message_text(
            f"╔══════════════════════════════╗\n║    ❌ TIC TAC TOE ⭕         ║\n╚══════════════════════════════╝\n\n{status}",
            parse_mode=ParseMode.MARKDOWN, reply_markup=_ttt_keyboard(board, game_over),
        )

    elif data == "noop":
        await query.answer()

    elif data == "joke_refresh":
        try:
            r = requests.get("https://v2.jokeapi.dev/joke/Any?blacklistFlags=nsfw,racist,sexist&type=twopart", timeout=8)
            if r.status_code == 200:
                d = r.json()
                setup = d.get("setup","")
                punchline = d.get("delivery","")
                cat = d.get("category","")
                joke_text = f"😂 *Daily Joke* [{cat}]\n{LINE}\n\n*{setup}*\n\n_{punchline}_\n\n{LINE}\n_Use the button for another!_"
            else:
                joke_text = f"{CROSS} Could not fetch joke. Try again!"
        except Exception:
            joke_text = f"{CROSS} Joke service unavailable. Try again!"
        await query.edit_message_text(joke_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("😂 Another Joke", callback_data="joke_refresh")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ]))

    elif data == "fact_refresh":
        try:
            r = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en", timeout=8)
            if r.status_code == 200:
                fact = r.json().get("text","")
                fact_text = f"🧠 *Random Fact*\n{LINE}\n\n_{fact}_\n\n{LINE}\n_Use the button for more!_"
            else:
                fact_text = f"{CROSS} Could not fetch fact. Try again!"
        except Exception:
            fact_text = f"{CROSS} Fact service unavailable. Try again!"
        await query.edit_message_text(fact_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🧠 Another Fact", callback_data="fact_refresh")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ]))

    elif data.startswith("sub_"):
        interval = data[4:]
        if interval == "cancel":
            remove_subscriber(user.id)
            await query.edit_message_text(
                f"🔕 *Unsubscribed from World News*\n{LINE}\nYou will no longer receive automatic news updates.\nUse /subscribe to re-subscribe anytime.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_main_keyboard(),
            )
        elif interval in SUBSCRIBE_INTERVALS:
            save_subscriber(user.id, interval)
            db_user = get_user(user.id)
            await query.edit_message_text(
                f"✅ *Subscribed to World News!*\n{LINE}\n"
                f"📡 Interval: `{interval}`\n"
                f"💰 Cost per delivery: `{WORLD_MONITOR_CREDIT_COST} credits`\n"
                f"💎 Your balance: `{db_user['credits']} credits`\n{LINE}\n"
                f"Use /unsubscribe to cancel anytime.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_main_keyboard(),
            )

    elif data == "worldmonitor_refresh":
        is_dev = is_developer(user.id, user.username or "")
        db_user = get_user(user.id, user.username or "")
        if not is_dev:
            if db_user["credits"] < WORLD_MONITOR_CREDIT_COST:
                await query.answer(f"Not enough credits! Need {WORLD_MONITOR_CREDIT_COST}.", show_alert=True)
                return
            raw = load_data()
            uid = str(user.id)
            raw["users"][uid]["credits"] = db_user["credits"] - WORLD_MONITOR_CREDIT_COST
            raw["users"][uid]["total_used"] = db_user.get("total_used", 0) + 1
            save_data(raw)
            db_user = get_user(user.id)
        await query.edit_message_text("🌍 _Scanning world events…_", parse_mode=ParseMode.MARKDOWN)
        news_items = get_world_news(8)
        now = datetime.utcnow().strftime("%d %b %Y %H:%M UTC")
        if not news_items:
            await query.edit_message_text(
                f"🌍 *WORLD MONITOR*\n{LINE}\n{CROSS} Unable to fetch live news.\nPlease try again.\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Retry", callback_data="worldmonitor_refresh")],
                    [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
                ]),
            )
            return
        lines = []
        for i, item in enumerate(news_items, 1):
            cat_tag = f"[{item['cat']}]" if item['cat'] and item['cat'].lower() != "general" else ""
            lines.append(f"*{i}.* {cat_tag} {item['title']}")
            if item.get("desc"):
                lines.append(f"   _{item['desc'][:100]}_")
        full_text = (
            f"╔══════════════════════════════╗\n"
            f"║    🌍 WORLD MONITOR LIVE     ║\n"
            f"╚══════════════════════════════╝\n\n"
            f"{GLOBE} *Live World Events*\n"
            f"{LINE}\n"
            f"🕐 *Updated:* `{now}`\n"
            f"{LINE}\n\n"
            + "\n\n".join(lines) +
            f"\n\n{LINE}\n"
            f"💰 Credits Left: `{db_user['credits']}`\n"
            f"💡 _Costs {WORLD_MONITOR_CREDIT_COST} credits per refresh_"
        )
        await query.edit_message_text(
            full_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh News", callback_data="worldmonitor_refresh")],
                [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
            ]),
        )

    elif data == "feedback_prompt":
        await query.edit_message_text(
            f"💬 *Send Feedback*\n{LINE}\n"
            f"Use the command:\n`/feedback <your message>`\n\n"
            f"Report bugs, suggest features, or send anything!\n"
            f"_Your message goes directly to @{DEVELOPER_USERNAME}_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]),
        )

    elif data == "about":
        text = f"""
╔══════════════════════════════╗
║      ℹ️ ABOUT THIS BOT       ║
╚══════════════════════════════╝

🤖 *{BOT_NAME}*
📌 *Version:* `{VERSION}`
{LINE}
👨‍💻 *Developer:* @{DEVELOPER_USERNAME}
🌐 *Website:* teamcsb.com
{LINE}
🛠️ *Features:*
  ✦ BIN & CC Tools
  ✦ Temp Mail (Emailnator)
  ✦ Privacy Tools
  ✦ Developer Utilities
  ✦ Text & Math Tools
  ✦ Finance Calculators
  ✦ Unit Converters
{LINE}
📊 *Credits System:*
  ✦ Free: 10/day
  ✦ Premium: 100/day
  ✦ Developer: ∞ Unlimited
{LINE}
{WARN} _For Educational Purposes Only_
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

    # ── Tool prompts from inline buttons ──
    elif data == "tool_binchk":
        await query.edit_message_text(
            f"🔍 *BIN Checker*\n{LINE}\nSend: `/bin <6-digit BIN>`\n\nExample:\n`/bin 457173`\n`/bin 411111`\n\n{WARN} _1 credit per lookup_",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_carding_keyboard()
        )
    elif data == "tool_binfind":
        await query.edit_message_text(
            f"🔎 *BIN Finder*\n{LINE}\nSend: `/bin <any BIN prefix>`\n\nYou can look up any 4-8 digit BIN prefix.\n\nExamples:\n`/bin 4571`\n`/bin 52345`\n\n{WARN} _1 credit per lookup_",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_carding_keyboard()
        )
    elif data == "tool_ccgen":
        await query.edit_message_text(
            f"⚙️ *CC Generator*\n{LINE}\nSend: `/gen <bin> [quantity]`\n\nExamples:\n`/gen 457173` (5 cards)\n`/gen 411111 10` (10 cards)\nMax: 20 cards\n\n{WARN} _Educational use only — 1 credit_",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_carding_keyboard()
        )
    elif data == "tool_cchk":
        await query.edit_message_text(
            f"✅ *CC Luhn Checker*\n{LINE}\nSend: `/chk <card|mm|yy|cvv>`\n\nExample:\n`/chk 4111111111111111|12|2025|123`\n\nNote: This is Luhn algorithm validation only, not a live payment check.\n\n{WARN} _1 credit — Educational only_",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_carding_keyboard()
        )
    elif data == "tool_bulkgen":
        await query.edit_message_text(
            f"📦 *Bulk CC Generator*\n{LINE}\nSend: `/bulkgen <bin> <quantity>`\n\nExamples:\n`/bulkgen 457173 25`\n`/bulkgen 411111 50`\nMax: 50 cards\n\n{WARN} _1 credit — Educational only_",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_carding_keyboard()
        )
    elif data == "tool_binshare":
        await query.edit_message_text(
            f"🔗 *BIN Share*\n{LINE}\nSend: `/bin <BIN>` to get full BIN info.\n\nYou can share the result with others.\nBIN info includes: bank, country, card type, scheme.\n\n{WARN} _1 credit per lookup_",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_carding_keyboard()
        )
    elif data == "tool_tempmail":
        get_user(user.id, user.username or "")
        if not use_credit(user.id):
            await query.edit_message_text(f"{CROSS} *Insufficient Credits!*\n\nYou have 0 credits. Credits reset daily.\n\n💎 Upgrade to Premium for 100 credits/day!\nContact: @{DEVELOPER_USERNAME}", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())
            return
        await query.edit_message_text("📧 Generating temp email via Emailnator...", parse_mode=ParseMode.MARKDOWN)
        email = emailnator_get_email()
        db_user = get_user(user.id)
        if email:
            context.user_data["temp_email"] = email
            text = f"╔══════════════════════════════╗\n║    📧 TEMP EMAIL GENERATED   ║\n╚══════════════════════════════╝\n\n📬 *Your Temp Email:*\n`{email}`\n\n{LINE}\n📋 Use `/inbox {email}` to check messages\n\n{LINE}\n💰 Credits Left: `{db_user['credits']}`"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Check Inbox", callback_data=f"inbox_{email}")],
                [InlineKeyboardButton("🔄 New Email", callback_data="tool_tempmail"), InlineKeyboardButton("« Menu", callback_data="main_menu")],
            ])
        else:
            text = f"{CROSS} *Failed to generate temp email*\nService may be temporarily unavailable.\n\n💰 Credits Left: `{db_user['credits']}`"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Retry", callback_data="tool_tempmail"), InlineKeyboardButton("« Menu", callback_data="main_menu")]])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif data.startswith("inbox_"):
        email = data[6:]
        get_user(user.id, user.username or "")
        if not use_credit(user.id):
            await query.edit_message_text(f"{CROSS} Insufficient credits!", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())
            return
        await query.edit_message_text(f"📥 Checking inbox for `{email}`...", parse_mode=ParseMode.MARKDOWN)
        messages = emailnator_get_inbox(email)
        db_user = get_user(user.id)
        if messages:
            text = f"╔══════════════════════════════╗\n║      📥 INBOX RESULTS        ║\n╚══════════════════════════════╝\n\n📧 *Email:* `{email}`\n📬 *Messages:* `{len(messages)}`\n{LINE}\n"
            for i, m in enumerate(messages[:5], 1):
                subject = m.get("subject", "No Subject")[:50]
                sender = m.get("from", "Unknown")[:30]
                text += f"*{i}.* 📩 {subject}\n   From: `{sender}`\n\n"
            text += f"{LINE}\n💰 Credits Left: `{db_user['credits']}`"
        else:
            text = f"📥 *Inbox Empty*\n{LINE}\nEmail: `{email}`\nNo messages yet.\n\n💰 Credits Left: `{db_user['credits']}`"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data=f"inbox_{email}")],
            [InlineKeyboardButton("📧 New Email", callback_data="tool_tempmail"), InlineKeyboardButton("« Menu", callback_data="main_menu")],
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif data == "tool_inbox":
        await query.edit_message_text(
            f"📥 *Check Inbox*\n{LINE}\nSend: `/inbox <email>`\n\nExample:\n`/inbox test@gmail.com`\n\nOr generate a temp email first with 📧 Temp Email\n\n{WARN} _1 credit_",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
        )
    elif data == "tool_fakeaddr":
        get_user(user.id, user.username or "")
        if not use_credit(user.id):
            await query.edit_message_text(f"{CROSS} Insufficient credits!", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())
            return
        addr = fake_address()
        db_user = get_user(user.id)
        text = f"╔══════════════════════════════╗\n║   👤 FAKE IDENTITY CARD      ║\n╚══════════════════════════════╝\n\n{DIAMOND} *Name:* `{addr['name']}`\n{DIAMOND} *DOB:* `{addr['dob']}`\n{DIAMOND} *Gender:* `{addr['gender']}`\n{LINE}\n🏠 *Address:* `{addr['address']}`\n🌆 *City:* `{addr['city']}, {addr['state']} {addr['zip']}`\n🌎 *Country:* `{addr['country']}`\n{LINE}\n📞 *Phone:* `{addr['phone']}`\n📧 *Email:* `{addr['email']}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`\n\n{WARN} _Fake data for testing only_"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Generate New", callback_data="tool_fakeaddr"), InlineKeyboardButton("« Menu", callback_data="main_menu")]])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif data == "tool_passgen":
        get_user(user.id, user.username or "")
        if not use_credit(user.id):
            await query.edit_message_text(f"{CROSS} Insufficient credits!", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())
            return
        passwords = [generate_password(16, True) for _ in range(5)]
        db_user = get_user(user.id)
        pwd_text = "\n".join([f"`{p}`" for p in passwords])
        text = f"╔══════════════════════════════╗\n║   🔑 PASSWORD GENERATOR      ║\n╚══════════════════════════════╝\n\n🔒 Length: 16 | With Symbols\n{LINE}\n{pwd_text}\n{LINE}\n💰 Credits Left: `{db_user['credits']}`"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Generate New", callback_data="tool_passgen"), InlineKeyboardButton("« Menu", callback_data="main_menu")]])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif data == "tool_uuid":
        get_user(user.id, user.username or "")
        if not use_credit(user.id):
            await query.edit_message_text(f"{CROSS} Insufficient credits!", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())
            return
        uuids = [generate_uuid() for _ in range(5)]
        db_user = get_user(user.id)
        uuid_text = "\n".join([f"`{u}`" for u in uuids])
        await query.edit_message_text(f"🆔 *UUID Generator*\n{LINE}\n{uuid_text}\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

    # Generic prompt handlers
    elif data.startswith("tool_"):
        tool_map = {
            "tool_sitestatus": ("🌐 Site Status", "/status <url>", "Example: /status google.com"),
            "tool_iplookup": ("🌍 IP Lookup", "/iplookup <host>", "Example: /iplookup google.com"),
            "tool_ssl": ("🔒 SSL Info", "/ssl <domain>", "Example: /ssl google.com"),
            "tool_whois": ("📋 WHOIS", "/whois <domain>", "Example: /whois google.com"),
            "tool_urlencode": ("🔗 URL Encode", "/urlencode <text>", "Example: /urlencode Hello World!"),
            "tool_urldecode": ("🔗 URL Decode", "/urldecode <text>", "Example: /urldecode Hello%20World"),
            "tool_htmlenc": ("🌐 HTML Encode", "/htmlenc <text>", "Example: /htmlenc <div>Hello</div>"),
            "tool_htmldec": ("🌐 HTML Decode", "/htmldec <text>", "Example: /htmldec &lt;div&gt;"),
            "tool_b64enc": ("📦 Base64 Encode", "/b64enc <text>", "Example: /b64enc Hello World"),
            "tool_b64dec": ("📦 Base64 Decode", "/b64dec <base64>", "Example: /b64dec SGVsbG8gV29ybGQ="),
            "tool_md5": ("#️⃣ MD5 Hash", "/md5 <text>", "Example: /md5 password123"),
            "tool_sha256": ("🔐 SHA256 Hash", "/sha256 <text>", "Example: /sha256 password123"),
            "tool_emailval": ("✉️ Email Validator", "/emailval <email>", "Example: /emailval test@gmail.com"),
            "tool_color": ("🎨 Color Converter", "/color <#hex or rgb>", "Example: /color #FF5733"),
            "tool_age": ("📅 Age Calculator", "/age <DD/MM/YYYY>", "Example: /age 15/08/1995"),
            "tool_avg": ("📊 Average Calculator", "/avg <n1> <n2> ...", "Example: /avg 10 20 30 40"),
            "tool_bin2dec": ("🔢 Binary→Decimal", "/bin2dec <binary>", "Example: /bin2dec 1010"),
            "tool_dec2bin": ("🔢 Decimal→Binary", "/dec2bin <number>", "Example: /dec2bin 42"),
            "tool_hex2dec": ("🔡 Hex→Decimal", "/hex2dec <hex>", "Example: /hex2dec FF"),
            "tool_dec2hex": ("🔡 Decimal→Hex", "/dec2hex <number>", "Example: /dec2hex 255"),
            "tool_oct2dec": ("🔣 Octal→Decimal", "/oct2dec <octal>", "Example: /oct2dec 77"),
            "tool_dec2oct": ("🔣 Decimal→Octal", "/dec2oct <number>", "Example: /dec2oct 255"),
            "tool_bin2ascii": ("📡 Binary→ASCII", "/bin2ascii <binary>", "Example: /bin2ascii 01001000 01101001"),
            "tool_ascii2bin": ("📡 ASCII→Binary", "/ascii2bin <text>", "Example: /ascii2bin Hello"),
            "tool_text2hex": ("🔤 Text→Hex", "/text2hex <text>", "Example: /text2hex Hello"),
            "tool_hex2text": ("🔤 Hex→Text", "/hex2text <hex>", "Example: /hex2text 48656c6c6f"),
            "tool_upper": ("🔠 Uppercase", "/upper <text>", "Example: /upper hello world"),
            "tool_lower": ("🔡 Lowercase", "/lower <text>", "Example: /lower HELLO WORLD"),
            "tool_title": ("📝 Title Case", "/title <text>", "Example: /title hello world"),
            "tool_swap": ("🔀 Swap Case", "/swapcase <text>", "Example: /swapcase Hello World"),
            "tool_reverse": ("↩️ Reverse Text", "/reverse <text>", "Example: /reverse Hello World"),
            "tool_wordcount": ("📊 Word Count", "/wordcount <text>", "Example: /wordcount The quick brown fox"),
            "tool_comma": ("📋 Comma Separator", "/commasep <number>", "Example: /commasep 1000000"),
            "tool_temp": ("🌡️ Temperature", "/temp <val> <C/F/K> <C/F/K>", "Example: /temp 100 C F"),
            "tool_currency": ("💱 Currency", "/currency <amt> <FROM> <TO>", "Example: /currency 100 USD EUR"),
            "tool_discount": ("🏷️ Discount Calc", "/discount <price> <pct>", "Example: /discount 1000 25"),
            "tool_gst": ("🧾 GST Calculator", "/gst <amount> <rate>", "Example: /gst 1000 18"),
            "tool_cpm": ("📢 CPM Calculator", "/cpm <impressions> <cost>", "Example: /cpm 50000 250"),
        }
        if data in tool_map:
            title, usage, example = tool_map[data]
            await query.edit_message_text(
                f"{title}\n{LINE}\nUsage: `{usage}`\n{example}\n\n{WARN} _1 credit per use_",
                parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard()
            )

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{INFO} Unknown command. Use /help to see all available commands.",
        parse_mode=ParseMode.MARKDOWN
    )

async def set_commands(app):
    commands = [
        BotCommand("start", "Start the bot & main menu"),
        BotCommand("help", "Show all commands"),
        BotCommand("credits", "Check your credits"),
        BotCommand("premium", "Premium info"),
        BotCommand("gen", "CC Generator"),
        BotCommand("chk", "CC Luhn Checker"),
        BotCommand("bulkgen", "Bulk CC Generator"),
        BotCommand("tempmail", "Generate temp email"),
        BotCommand("inbox", "Check temp email inbox"),
        BotCommand("fakeaddr", "Fake address generator"),
        BotCommand("urlencode", "URL encode"),
        BotCommand("urldecode", "URL decode"),
        BotCommand("htmlenc", "HTML encode"),
        BotCommand("htmldec", "HTML decode"),
        BotCommand("b64enc", "Base64 encode"),
        BotCommand("b64dec", "Base64 decode"),
        BotCommand("uuid", "Generate UUID"),
        BotCommand("age", "Age calculator"),
        BotCommand("avg", "Average calculator"),
        BotCommand("bin2dec", "Binary to decimal"),
        BotCommand("dec2bin", "Decimal to binary"),
        BotCommand("hex2dec", "Hex to decimal"),
        BotCommand("dec2hex", "Decimal to hex"),
        BotCommand("oct2dec", "Octal to decimal"),
        BotCommand("dec2oct", "Decimal to octal"),
        BotCommand("bin2ascii", "Binary to ASCII"),
        BotCommand("ascii2bin", "ASCII to binary"),
        BotCommand("temp", "Temperature converter"),
        BotCommand("currency", "Currency converter"),
        BotCommand("discount", "Discount calculator"),
        
  BotCommand("gst", "GST calculator"),
        BotCommand("cpm", "CPM calculator"),
        BotCommand("referral", "Referral program & your link"),
        BotCommand("leaderboard", "Top 10 users leaderboard"),
        BotCommand("claim", "Claim daily reward & keep your streak"),
        BotCommand("dice", "Dice game — bet credits"),
        BotCommand("flip", "Coin flip game — bet credits"),
        BotCommand("redeem", "Redeem a promo code for credits"),
        BotCommand("feedback", "Send feedback to developer"),
        BotCommand("crypto", "Live crypto prices (BTC/ETH/SOL...)"),
        BotCommand("ccextrap", "Extract info from a card number"),
        BotCommand("slots", "Slot machine — spin to win big"),
        BotCommand("roulette", "Roulette — red/black/number bets"),
        BotCommand("blackjack", "Blackjack — beat the dealer"),
        BotCommand("crash", "Crash game — set your target multiplier"),
        BotCommand("horse", "Horse race — pick your winner"),
        BotCommand("tower", "Tower climb — survive the floors"),
        BotCommand("guess", "Guess the number — 1-10, win 8×"),
        BotCommand("portscan", "Check if a port is open (real TCP)"),

 BotCommand("createcode", "Dev: Create a promo code"),
        BotCommand("listcodes", "Dev: List all promo codes"),
        BotCommand("deletecode", "Dev: Delete a promo code"),
        BotCommand("analytics", "Dev: Tool usage analytics"),
        BotCommand("viewfeedback", "Dev: View user feedback"),
        BotCommand("dev", "Developer panel"),
        BotCommand("worldmonitor", "Live world news monitoring (5 credits)"),
        BotCommand("subscribe", "Auto world news to your DM (pick interval)"),
        BotCommand("unsubscribe", "Cancel world news subscription"),
        BotCommand("stock", "Real-time stock price lookup"),
        BotCommand("joke", "Random joke — free!"),
        BotCommand("fact", "Random fact — free!"),
        BotCommand("qr", "Generate a QR code from text"),
        BotCommand("qrurl", "Convert a URL to QR code (1 credit)"),
        BotCommand("fileqr", "Send any file → get its QR code (3 credits)"),
        BotCommand("trivia", "Trivia quiz — bet credits, win 2x!"),
        BotCommand("timezone", "Current time in any city / timezone"),
        BotCommand("randomname", "Generate a random identity"),
        BotCommand("geoip", "Deep IP geolocation lookup"),
        # Batch 1 — Math / Science / Cipher
        BotCommand("wiki", "Wikipedia article summary"),
        BotCommand("stats", "Statistical analysis of numbers"),
        BotCommand("convert", "Unit converter (km, kg, L, °C, GB...)"),
        BotCommand("baseconv", "Base converter (binary/hex/octal/decimal)"),
        BotCommand("periodic", "Periodic table — all 118 elements"),
        # Batch 2 — Games / World / Social
        BotCommand("rps", "Rock Paper Scissors vs bot"),
        BotCommand("8ball", "Magic 8-Ball — ask any question"),
        BotCommand("roll", "Dice roller — NdN+modifier"),
        BotCommand("quote", "Random inspirational quote"),
        BotCommand("meme", "Random meme from internet"),
        BotCommand("advice", "Random life advice"),
        BotCommand("country", "Country info — capital, pop, currency"),
        BotCommand("earthquake", "Latest earthquake data (USGS)"),
        BotCommand("covid", "COVID-19 stats by country"),
        BotCommand("github", "GitHub profile info"),
        BotCommand("pypi", "PyPI package info"),
        BotCommand("movie", "Movie info & ratings"),
        BotCommand("scramble", "Word scramble game — win credits!"),
        BotCommand("hangman", "Hangman game — guess the word"),
        BotCommand("tictactoe", "Tic Tac Toe vs bot"),
        # Batch 3 — Productivity
        BotCommand("notes", "Personal notes manager"),
        BotCommand("pastebin", "Upload text and get a shareable URL"),
        # Batch 4 — Dev
        BotCommand("devpanel", "Developer control panel"),
        BotCommand("broadcast", "Dev: Send message to all users"),
        BotCommand("botstats", "Dev: Full bot statistics"),
        BotCommand("maintenance", "Dev: Toggle maintenance mode"),
        BotCommand("transfercredits", "Dev: Send credits to any user"),
        BotCommand("givepremium", "Dev: Grant premium to any user"),
        BotCommand("banuser", "Dev: Ban a user"),
        BotCommand("unbanuser", "Dev: Unban a user"),
    ]
    await app.bot.set_my_commands(commands)

# ═══════════════════════════════════════════════════════
# ⚡ GOD MODE FEATURES
# ═══════════════════════════════════════════════════════

# ── WEATHER ──
def get_weather(city: str) -> dict:
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            d = r.json()
            cur = d["current_condition"][0]
            area = d["nearest_area"][0]
            areaName = area["areaName"][0]["value"]
            country = area["country"][0]["value"]
            desc = cur["weatherDesc"][0]["value"]
            temp_c = cur["temp_C"]
            temp_f = cur["temp_F"]
            feels_c = cur["FeelsLikeC"]
            humidity = cur["humidity"]
            wind_kmph = cur["windspeedKmph"]
            wind_dir = cur["winddir16Point"]
            visibility = cur["visibility"]
            uv = cur["uvIndex"]
            return {
                "city": areaName, "country": country, "desc": desc,
                "temp_c": temp_c, "temp_f": temp_f, "feels_c": feels_c,
                "humidity": humidity, "wind_kmph": wind_kmph, "wind_dir": wind_dir,
                "visibility": visibility, "uv": uv,
            }
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

async def cmd_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/weather <city>`\nExample: `/weather London`", parse_mode=ParseMode.MARKDOWN)
        return
    city = " ".join(context.args)
    msg = await update.message.reply_text(f"🌤 _Fetching weather for `{city}`…_", parse_mode=ParseMode.MARKDOWN)
    result = get_weather(city)
    db_user = get_user(user.id)
    if "error" in result:
        await msg.edit_text(f"{CROSS} Weather lookup failed: `{result['error']}`\nCheck the city name and try again.", parse_mode=ParseMode.MARKDOWN)
        return
    emoji_map = {"Sunny":"☀️","Clear":"🌙","Cloudy":"☁️","Overcast":"☁️","Rain":"🌧️","Drizzle":"🌦️","Snow":"❄️","Thunder":"⛈️","Fog":"🌫️","Mist":"🌫️","Haze":"🌫️","Blizzard":"🌨️","Sleet":"🌨️"}
    weather_emoji = next((v for k,v in emoji_map.items() if k.lower() in result["desc"].lower()), "🌤")
    track_tool_usage("weather")
    await msg.edit_text(
        f"╔══════════════════════════════╗\n"
        f"║     {weather_emoji} LIVE WEATHER           ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"📍 *{result['city']}, {result['country']}*\n"
        f"{LINE}\n"
        f"{weather_emoji} *Condition:* `{result['desc']}`\n"
        f"🌡️ *Temperature:* `{result['temp_c']}°C / {result['temp_f']}°F`\n"
        f"🤔 *Feels Like:* `{result['feels_c']}°C`\n"
        f"💧 *Humidity:* `{result['humidity']}%`\n"
        f"💨 *Wind:* `{result['wind_kmph']} km/h {result['wind_dir']}`\n"
        f"👁️ *Visibility:* `{result['visibility']} km`\n"
        f"☀️ *UV Index:* `{result['uv']}`\n"
        f"{LINE}\n"
        f"💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(),
    )

# ── TRANSLATE ──
def translate_text(text: str, target_lang: str) -> dict:
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text, "langpair": f"en|{target_lang}"},
            timeout=10,
        )
        if r.status_code == 200:
            d = r.json()
            translated = d.get("responseData", {}).get("translatedText", "")
            quality = d.get("responseData", {}).get("match", 0)
            if translated:
                return {"translated": translated, "quality": quality}
        return {"error": "Translation failed"}
    except Exception as e:
        return {"error": str(e)}

LANG_NAMES = {
    "af":"Afrikaans","ar":"Arabic","zh":"Chinese","cs":"Czech","da":"Danish",
    "nl":"Dutch","en":"English","fi":"Finnish","fr":"French","de":"German",
    "el":"Greek","he":"Hebrew","hi":"Hindi","hu":"Hungarian","id":"Indonesian",
    "it":"Italian","ja":"Japanese","ko":"Korean","ms":"Malay","no":"Norwegian",
    "fa":"Persian","pl":"Polish","pt":"Portuguese","ro":"Romanian","ru":"Russian",
    "es":"Spanish","sv":"Swedish","th":"Thai","tr":"Turkish","uk":"Ukrainian",
    "ur":"Urdu","vi":"Vietnamese",
}

async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 2:
        langs = ", ".join([f"`{k}` ({v})" for k,v in list(LANG_NAMES.items())[:10]])
        await update.message.reply_text(
            f"🌐 *Translator*\n{LINE}\nUsage: `/translate <lang_code> <text>`\n\n"
            f"Example: `/translate ar Hello world`\n\n"
            f"Common codes:\n{langs}\n_...and more_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    lang = context.args[0].lower()
    text_in = " ".join(context.args[1:])
    msg = await update.message.reply_text(f"🌐 _Translating…_", parse_mode=ParseMode.MARKDOWN)
    result = translate_text(text_in, lang)
    db_user = get_user(user.id)
    lang_name = LANG_NAMES.get(lang, lang.upper())
    track_tool_usage("translate")
    if "error" in result:
        await msg.edit_text(f"{CROSS} Translation failed: `{result['error']}`\nCheck language code and try again.", parse_mode=ParseMode.MARKDOWN)
        return
    await msg.edit_text(
        f"╔══════════════════════════════╗\n"
        f"║      🌐 TRANSLATOR           ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"🔤 *From:* `English`\n"
        f"🗣️ *To:* `{lang_name}`\n"
        f"{LINE}\n"
        f"📥 *Input:*\n`{text_in[:200]}`\n\n"
        f"📤 *Translation:*\n`{result['translated'][:500]}`\n"
        f"{LINE}\n"
        f"💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(),
    )

# ── STOCK PRICE ──
def get_stock_price(ticker: str) -> dict:
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}?interval=1d&range=1d"
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            d = r.json()
            meta = d["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice", 0)
            prev = meta.get("previousClose") or meta.get("chartPreviousClose", price)
            change = price - prev
            change_pct = (change / prev * 100) if prev else 0
            currency = meta.get("currency", "USD")
            name = meta.get("longName") or meta.get("shortName") or ticker.upper()
            exchange = meta.get("exchangeName", "")
            market_state = meta.get("marketState", "")
            return {
                "name": name, "ticker": ticker.upper(), "price": price,
                "change": change, "change_pct": change_pct, "currency": currency,
                "exchange": exchange, "market_state": market_state,
            }
        return {"error": f"Ticker not found or HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

async def cmd_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(
            f"📈 *Stock Lookup*\n{LINE}\nUsage: `/stock <ticker>`\n\n"
            f"Examples:\n`/stock AAPL` — Apple\n`/stock TSLA` — Tesla\n`/stock MSFT` — Microsoft\n`/stock BTC-USD` — Bitcoin",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    ticker = context.args[0].upper()
    msg = await update.message.reply_text(f"📈 _Fetching stock data for `{ticker}`…_", parse_mode=ParseMode.MARKDOWN)
    result = get_stock_price(ticker)
    db_user = get_user(user.id)
    track_tool_usage("stock")
    if "error" in result:
        await msg.edit_text(f"{CROSS} Stock lookup failed: `{result['error']}`\nCheck the ticker symbol.", parse_mode=ParseMode.MARKDOWN)
        return
    arrow = "🟢 ▲" if result["change"] >= 0 else "🔴 ▼"
    change_str = f"{'+' if result['change'] >= 0 else ''}{result['change']:.2f} ({'+' if result['change_pct'] >= 0 else ''}{result['change_pct']:.2f}%)"
    state_icon = "🟢" if result["market_state"] == "REGULAR" else "🔴"
    await msg.edit_text(
        f"╔══════════════════════════════╗\n"
        f"║     📈 STOCK LIVE PRICE      ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"🏢 *{result['name']}*\n"
        f"🔖 *Ticker:* `{result['ticker']}`\n"
        f"🏦 *Exchange:* `{result['exchange']}`\n"
        f"{LINE}\n"
        f"💵 *Price:* `{result['price']:.4f} {result['currency']}`\n"
        f"{arrow} *Change:* `{change_str}`\n"
        f"{state_icon} *Market:* `{result['market_state']}`\n"
        f"{LINE}\n"
        f"💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(),
    )

# ── DICTIONARY ──
def define_word(word: str) -> dict:
    try:
        r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(word.lower())}", timeout=10)
        if r.status_code == 200:
            data = r.json()
            entry = data[0]
            meanings = entry.get("meanings", [])
            phonetic = entry.get("phonetic", "")
            results = []
            for m in meanings[:3]:
                pos = m.get("partOfSpeech", "")
                defs = m.get("definitions", [])
                if defs:
                    d = defs[0]
                    definition = d.get("definition", "")
                    example = d.get("example", "")
                    results.append({"pos": pos, "definition": definition, "example": example})
            return {"word": word, "phonetic": phonetic, "meanings": results}
        return {"error": "Word not found in dictionary"}
    except Exception as e:
        return {"error": str(e)}

async def cmd_define(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/define <word>`\nExample: `/define serendipity`", parse_mode=ParseMode.MARKDOWN)
        return
    word = context.args[0].strip()
    msg = await update.message.reply_text(f"📖 _Looking up `{word}`…_", parse_mode=ParseMode.MARKDOWN)
    result = define_word(word)
    db_user = get_user(user.id)
    track_tool_usage("define")
    if "error" in result:
        await msg.edit_text(f"{CROSS} {result['error']}", parse_mode=ParseMode.MARKDOWN)
        return
    lines = [f"╔══════════════════════════════╗\n║     📖 DICTIONARY            ║\n╚══════════════════════════════╝\n\n"]
    lines.append(f"📝 *Word:* `{result['word']}`\n")
    if result.get("phonetic"):
        lines.append(f"🔊 *Phonetic:* `{result['phonetic']}`\n")
    lines.append(f"{LINE}\n")
    for i, m in enumerate(result.get("meanings", []), 1):
        lines.append(f"*{i}. {m['pos'].capitalize()}*\n")
        lines.append(f"   {m['definition'][:300]}\n")
        if m.get("example"):
            lines.append(f"   _e.g. \"{m['example'][:200]}\"_\n")
        lines.append("\n")
    lines.append(f"{LINE}\n💰 Credits Left: `{db_user['credits']}`")
    await msg.edit_text("".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

# ── JOKES ──
async def cmd_joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    try:
        r = requests.get("https://v2.jokeapi.dev/joke/Any?blacklistFlags=nsfw,racist,sexist&type=twopart", timeout=8)
        if r.status_code == 200:
            d = r.json()
            setup = d.get("setup","")
            punchline = d.get("delivery","")
            cat = d.get("category","")
            joke_text = f"😂 *Daily Joke* [{cat}]\n{LINE}\n\n*{setup}*\n\n_{punchline}_\n\n{LINE}\n_Use /joke again for another!_"
        else:
            joke_text = f"{CROSS} Could not fetch joke. Try again!"
    except Exception:
        joke_text = f"{CROSS} Joke service unavailable. Try again!"
    track_tool_usage("joke")
    await update.message.reply_text(joke_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("😂 Another Joke", callback_data="joke_refresh")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ]))

# ── FACTS ──
async def cmd_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    try:
        r = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en", timeout=8)
        if r.status_code == 200:
            fact = r.json().get("text","")
            fact_text = f"🧠 *Random Fact*\n{LINE}\n\n_{fact}_\n\n{LINE}\n_Use /fact again for more!_"
        else:
            fact_text = f"{CROSS} Could not fetch fact. Try again!"
    except Exception:
        fact_text = f"{CROSS} Fact service unavailable. Try again!"
    track_tool_usage("fact")
    await update.message.reply_text(fact_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Another Fact", callback_data="fact_refresh")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ]))

# ── QR CODE GENERATOR ──
async def cmd_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/qr <text or URL>`\nExample: `/qr https://t.me/yourbot`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(text_in)}"
    db_user = get_user(user.id)
    track_tool_usage("qr")
    await update.message.reply_photo(
        photo=qr_url,
        caption=f"🔲 *QR Code Generated*\n{LINE}\n📝 *Data:* `{text_in[:100]}`\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(),
    )

# ── URL SHORTENER ──
def shorten_url(url: str) -> str:
    try:
        r = requests.get(f"https://tinyurl.com/api-create.php?url={urllib.parse.quote(url)}", timeout=10)
        if r.status_code == 200 and r.text.startswith("http"):
            return r.text.strip()
        return ""
    except Exception:
        return ""

async def cmd_shorturl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/shorturl <url>`\nExample: `/shorturl https://yourwebsite.com/very/long/path`", parse_mode=ParseMode.MARKDOWN)
        return
    url = context.args[0].strip()
    if not url.startswith(("http://","https://")):
        url = "https://" + url
    msg = await update.message.reply_text(f"🔗 _Shortening URL…_", parse_mode=ParseMode.MARKDOWN)
    short = shorten_url(url)
    db_user = get_user(user.id)
    track_tool_usage("shorturl")
    if short:
        await msg.edit_text(
            f"╔══════════════════════════════╗\n║     🔗 URL SHORTENER         ║\n╚══════════════════════════════╝\n\n"
            f"📎 *Original:*\n`{url[:200]}`\n\n"
            f"✂️ *Short URL:*\n`{short}`\n"
            f"{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_main_keyboard(),
        )
    else:
        await msg.edit_text(f"{CROSS} Failed to shorten URL. Please check the URL and try again.", parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════
# ⚡ WORLD NEWS SUBSCRIPTION SYSTEM
# ═══════════════════════════════════════════════════════
SUBSCRIBE_INTERVALS = {"1h": 3600, "6h": 21600, "12h": 43200, "24h": 86400}

def get_subscribers() -> dict:
    data = load_data()
    return data.get("subscribers", {})

def save_subscriber(user_id: int, interval: str):
    data = load_data()
    data.setdefault("subscribers", {})[str(user_id)] = {
        "interval": interval,
        "last_sent": 0,
    }
    save_data(data)

def remove_subscriber(user_id: int):
    data = load_data()
    subs = data.get("subscribers", {})
    subs.pop(str(user_id), None)
    data["subscribers"] = subs
    save_data(data)

def update_subscriber_sent(user_id: int):
    data = load_data()
    subs = data.get("subscribers", {})
    if str(user_id) in subs:
        subs[str(user_id)]["last_sent"] = datetime.now().timestamp()
    data["subscribers"] = subs
    save_data(data)

async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    is_dev = is_developer(user.id, user.username or "")

    if not context.args or context.args[0] not in SUBSCRIBE_INTERVALS:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏰ Every Hour", callback_data="sub_1h"),
             InlineKeyboardButton("⏰ Every 6h", callback_data="sub_6h")],
            [InlineKeyboardButton("⏰ Every 12h", callback_data="sub_12h"),
             InlineKeyboardButton("⏰ Every 24h", callback_data="sub_24h")],
            [InlineKeyboardButton("🔕 Unsubscribe", callback_data="sub_cancel"),
             InlineKeyboardButton("« Menu", callback_data="main_menu")],
        ])
        subs = get_subscribers()
        current = subs.get(str(user.id), {}).get("interval", None)
        status = f"✅ *Currently subscribed:* `{current}` intervals" if current else "❌ *Not subscribed*"
        await update.message.reply_text(
            f"╔══════════════════════════════╗\n║  🌍 NEWS SUBSCRIPTION        ║\n╚══════════════════════════════╝\n\n"
            f"{status}\n{LINE}\n"
            f"Get *automatic world news updates* delivered to your DM!\n\n"
            f"Each delivery costs `{WORLD_MONITOR_CREDIT_COST} credits`.\n"
            f"{'Developer accounts get it free!' if is_dev else ''}\n\n"
            f"📋 *Pick your update interval:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb,
        )
        return

    interval = context.args[0]
    save_subscriber(user.id, interval)
    await update.message.reply_text(
        f"✅ *Subscribed to World News!*\n{LINE}\n"
        f"📡 Interval: `{interval}`\n"
        f"💰 Cost per delivery: `{WORLD_MONITOR_CREDIT_COST} credits`\n"
        f"💎 Your balance: `{db_user['credits']} credits`\n{LINE}\n"
        f"Use `/unsubscribe` to cancel anytime.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(),
    )

async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    remove_subscriber(user.id)
    await update.message.reply_text(
        f"🔕 *Unsubscribed from World News*\n{LINE}\n"
        f"You will no longer receive automatic news updates.\n"
        f"Use `/subscribe` to re-subscribe anytime.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(),
    )

async def news_broadcast_job(context):
    """Called periodically — sends news to subscribers whose interval has elapsed."""
    subs = get_subscribers()
    now = datetime.now().timestamp()
    for uid_str, info in list(subs.items()):
        try:
            uid = int(uid_str)
            interval_secs = SUBSCRIBE_INTERVALS.get(info.get("interval","24h"), 86400)
            last_sent = info.get("last_sent", 0)
            if now - last_sent < interval_secs:
                continue
            is_dev = is_developer(uid)
            db_user = get_user(uid)
            if not is_dev and db_user["credits"] < WORLD_MONITOR_CREDIT_COST:
                await context.bot.send_message(
                    uid,
                    f"⚠️ *World News Subscription*\n{LINE}\n"
                    f"You don't have enough credits for your news update.\n"
                    f"Need `{WORLD_MONITOR_CREDIT_COST}` credits, you have `{db_user['credits']}`.\n"
                    f"Earn more with `/claim` or `/referral`.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                continue
            news = get_world_news(6)
            if not news:
                continue
            if not is_dev:
                data = load_data()
                data["users"][uid_str]["credits"] = db_user["credits"] - WORLD_MONITOR_CREDIT_COST
                save_data(data)
                db_user = get_user(uid)
            update_subscriber_sent(uid)
            now_str = datetime.utcnow().strftime("%d %b %Y %H:%M UTC")
            lines = []
            for i, item in enumerate(news, 1):
                cat_tag = f"[{item['cat']}]" if item['cat'] and item['cat'].lower() != "general" else ""
                lines.append(f"*{i}.* {cat_tag} {item['title']}")
            text = (
                f"╔══════════════════════════════╗\n"
                f"║  📡 AUTO WORLD NEWS UPDATE   ║\n"
                f"╚══════════════════════════════╝\n\n"
                f"🕐 `{now_str}`\n{LINE}\n\n"
                + "\n\n".join(lines) +
                f"\n\n{LINE}\n"
                f"💰 Credits Left: `{db_user['credits']}`\n"
                f"_Use /unsubscribe to cancel_"
            )
            await context.bot.send_message(uid, text, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

# ═══════════════════════════════════════════════════════
# ⚡ GOD MODE EXTENDED FEATURES
# ═══════════════════════════════════════════════════════

import html as _html
import random as _random
import string as _string
import math as _math
import ast as _ast
import operator as _operator
import urllib.parse as _urlparse

FILE_QR_CREDIT_COST = 3

# ── FILE-TO-QR ──
async def upload_file_to_fileio(file_bytes: bytes, filename: str) -> str:
    """Upload bytes to file.io and return the public URL, or ''."""
    try:
        r = requests.post(
            "https://file.io/?expires=1d",
            files={"file": (filename, file_bytes, "application/octet-stream")},
            timeout=30,
        )
        if r.status_code in (200, 201):
            d = r.json()
            if d.get("success"):
                return d.get("link", "")
        return ""
    except Exception:
        return ""

async def cmd_fileqr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    is_dev = is_developer(user.id, user.username or "")
    if not is_dev and db_user["credits"] < FILE_QR_CREDIT_COST:
        await update.message.reply_text(
            f"❌ *Not enough credits*\n{LINE}\nFile→QR costs `{FILE_QR_CREDIT_COST} credits`.\nYou have `{db_user['credits']}`.\n\nEarn more with `/claim` or `/referral`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    context.user_data["awaiting_fileqr"] = True
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║    🔲 FILE → QR CODE         ║\n╚══════════════════════════════╝\n\n"
        f"📤 *Send me any file and I'll give you a QR code for it!*\n{LINE}\n"
        f"✅ Supports: Images, Videos, PDFs, Documents, Audio, Zip…\n"
        f"🔗 Or paste a URL directly with: `/qrurl <url>`\n"
        f"💰 Cost: `{FILE_QR_CREDIT_COST} credits` per conversion\n{LINE}\n"
        f"_Now send your file ↓_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖ Cancel", callback_data="fileqr_cancel")]]),
    )

async def handle_fileqr_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called when user sends a file after /fileqr."""
    user = update.effective_user
    msg = update.message
    if not context.user_data.get("awaiting_fileqr"):
        return
    context.user_data.pop("awaiting_fileqr", None)

    is_dev = is_developer(user.id, user.username or "")
    db_user = get_user(user.id, user.username or "")
    if not is_dev and db_user["credits"] < FILE_QR_CREDIT_COST:
        await msg.reply_text(f"❌ Not enough credits to convert. Need `{FILE_QR_CREDIT_COST}`, have `{db_user['credits']}`.", parse_mode=ParseMode.MARKDOWN)
        return

    # Determine file object
    tg_file = None
    filename = "file"
    if msg.document:
        tg_file = msg.document
        filename = msg.document.file_name or "document"
    elif msg.photo:
        tg_file = msg.photo[-1]
        filename = "photo.jpg"
    elif msg.video:
        tg_file = msg.video
        filename = msg.video.file_name or "video.mp4"
    elif msg.audio:
        tg_file = msg.audio
        filename = msg.audio.file_name or "audio.mp3"
    elif msg.voice:
        tg_file = msg.voice
        filename = "voice.ogg"
    elif msg.video_note:
        tg_file = msg.video_note
        filename = "videonote.mp4"
    elif msg.sticker:
        tg_file = msg.sticker
        filename = "sticker.webp"
    else:
        await msg.reply_text("❌ Unsupported file type. Send a document, image, video, audio, or PDF.", parse_mode=ParseMode.MARKDOWN)
        return

    wait = await msg.reply_text("⏳ _Uploading file and generating QR…_", parse_mode=ParseMode.MARKDOWN)
    try:
        file_size = getattr(tg_file, "file_size", 0) or 0
        if file_size > 20 * 1024 * 1024:
            await wait.edit_text("❌ File too large. Maximum 20 MB supported.", parse_mode=ParseMode.MARKDOWN)
            return
        dl = await context.bot.get_file(tg_file.file_id)
        file_bytes = await dl.download_as_bytearray()
        public_url = await upload_file_to_fileio(bytes(file_bytes), filename)
        if not public_url:
            await wait.edit_text("❌ Upload failed. Please try again later.", parse_mode=ParseMode.MARKDOWN)
            return
        # Deduct credits
        if not is_dev:
            raw = load_data()
            uid = str(user.id)
            raw["users"][uid]["credits"] = db_user["credits"] - FILE_QR_CREDIT_COST
            raw["users"][uid]["total_used"] = db_user.get("total_used", 0) + 1
            save_data(raw)
            db_user = get_user(user.id)
        track_tool_usage("fileqr")
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={_urlparse.quote(public_url)}"
        await wait.delete()
        await msg.reply_photo(
            photo=qr_url,
            caption=(
                f"╔══════════════════════════════╗\n║    🔲 FILE → QR CODE         ║\n╚══════════════════════════════╝\n\n"
                f"📄 *File:* `{filename}`\n"
                f"🔗 *Hosted URL:*\n`{public_url}`\n"
                f"⚠️ _Link expires in 24 hours_\n{LINE}\n"
                f"💰 Credits Left: `{db_user['credits']}`"
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_main_keyboard(),
        )
    except Exception as e:
        await wait.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

async def cmd_qrurl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Convert a URL directly to QR — 1 credit."""
    user = update.effective_user
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/qrurl <url>`\nExample: `/qrurl https://example.com`", parse_mode=ParseMode.MARKDOWN)
        return
    url = context.args[0].strip()
    if not url.startswith(("http://","https://")):
        url = "https://" + url
    db_user = get_user(user.id)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={_urlparse.quote(url)}"
    track_tool_usage("qrurl")
    await update.message.reply_photo(
        photo=qr_url,
        caption=f"🔲 *URL → QR Code*\n{LINE}\n🔗 `{url[:200]}`\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(),
    )

# ── TRIVIA GAME ──
TRIVIA_BET_OPTIONS = [5, 10, 20, 50]

async def fetch_trivia_question() -> dict:
    try:
        r = requests.get(
            "https://opentdb.com/api.php?amount=1&type=multiple",
            timeout=10,
        )
        if r.status_code == 200:
            d = r.json()
            if d.get("results"):
                q = d["results"][0]
                question = _html.unescape(q["question"])
                correct = _html.unescape(q["correct_answer"])
                wrongs = [_html.unescape(a) for a in q["incorrect_answers"]]
                options = wrongs + [correct]
                _random.shuffle(options)
                correct_idx = options.index(correct)
                return {
                    "question": question,
                    "options": options,
                    "correct_idx": correct_idx,
                    "category": _html.unescape(q.get("category","")),
                    "difficulty": q.get("difficulty","medium"),
                }
    except Exception:
        pass
    return {}

async def cmd_trivia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    # Show bet options
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💰 Bet {b} credits", callback_data=f"trivia_bet_{b}") for b in TRIVIA_BET_OPTIONS[:2]],
        [InlineKeyboardButton(f"💰 Bet {b} credits", callback_data=f"trivia_bet_{b}") for b in TRIVIA_BET_OPTIONS[2:]],
        [InlineKeyboardButton("« Back", callback_data="main_menu")],
    ])
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║      🧠 TRIVIA CHALLENGE     ║\n╚══════════════════════════════╝\n\n"
        f"🎯 Answer correctly and *win 2× your bet*!\n"
        f"❌ Wrong answer = lose your bet\n{LINE}\n"
        f"💎 Your credits: `{db_user['credits']}`\n\n"
        f"📋 *Choose your bet:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )

async def trivia_start_question(query, user, bet: int, context):
    """Fetch question and show it."""
    db_user = get_user(user.id)
    if db_user["credits"] < bet:
        await query.edit_message_text(
            f"❌ Not enough credits! You need `{bet}`, you have `{db_user['credits']}`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    await query.edit_message_text("🧠 _Fetching your question…_", parse_mode=ParseMode.MARKDOWN)
    q = await fetch_trivia_question()
    if not q:
        await query.edit_message_text("❌ Could not fetch a question. Please try again.", parse_mode=ParseMode.MARKDOWN)
        return
    context.user_data[f"trivia_{user.id}"] = {"bet": bet, "correct_idx": q["correct_idx"], "options": q["options"]}
    letters = ["🅐","🅑","🅒","🅓"]
    opts_text = "\n".join([f"{letters[i]} `{opt}`" for i, opt in enumerate(q["options"])])
    diff_emoji = {"easy":"🟢","medium":"🟡","hard":"🔴"}.get(q["difficulty"],"🟡")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🅐 {q['options'][0][:30]}", callback_data=f"trivia_ans_0"),
         InlineKeyboardButton(f"🅑 {q['options'][1][:30]}", callback_data=f"trivia_ans_1")],
        [InlineKeyboardButton(f"🅒 {q['options'][2][:30]}", callback_data=f"trivia_ans_2"),
         InlineKeyboardButton(f"🅓 {q['options'][3][:30]}", callback_data=f"trivia_ans_3")],
    ])
    await query.edit_message_text(
        f"╔══════════════════════════════╗\n║      🧠 TRIVIA CHALLENGE     ║\n╚══════════════════════════════╝\n\n"
        f"📚 *Category:* `{q['category']}`\n"
        f"{diff_emoji} *Difficulty:* `{q['difficulty'].capitalize()}`\n"
        f"💰 *Bet:* `{bet} credits`\n{LINE}\n\n"
        f"❓ *{q['question']}*\n\n"
        f"{opts_text}\n{LINE}\n_Pick your answer:_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )

# ── PASSWORD GENERATOR ──
def generate_password(length: int = 16, use_symbols: bool = True) -> str:
    chars = _string.ascii_letters + _string.digits
    if use_symbols:
        chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"
    while True:
        pwd = "".join(_random.SystemRandom().choice(chars) for _ in range(length))
        has_upper = any(c.isupper() for c in pwd)
        has_lower = any(c.islower() for c in pwd)
        has_digit = any(c.isdigit() for c in pwd)
        has_sym = any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?" for c in pwd) if use_symbols else True
        if has_upper and has_lower and has_digit and has_sym:
            return pwd

def password_strength(pwd: str) -> str:
    score = 0
    if len(pwd) >= 12: score += 1
    if len(pwd) >= 16: score += 1
    if any(c.isupper() for c in pwd): score += 1
    if any(c.islower() for c in pwd): score += 1
    if any(c.isdigit() for c in pwd): score += 1
    if any(c in "!@#$%^&*()-_=+" for c in pwd): score += 1
    if score <= 2: return "🔴 Weak"
    if score <= 4: return "🟡 Moderate"
    return "🟢 Strong"

async def cmd_passwordgen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    length = 16
    if context.args:
        try:
            length = max(8, min(64, int(context.args[0])))
        except ValueError:
            pass
    pwd = generate_password(length, use_symbols=True)
    strength = password_strength(pwd)
    track_tool_usage("passwordgen")
    db_user = get_user(user.id)
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║    🔐 PASSWORD GENERATOR     ║\n╚══════════════════════════════╝\n\n"
        f"🔑 *Generated Password:*\n`{pwd}`\n\n"
        f"📏 *Length:* `{length} characters`\n"
        f"💪 *Strength:* {strength}\n"
        f"🎲 *Charset:* Letters + Digits + Symbols\n{LINE}\n"
        f"💡 _Use `/passwordgen 20` for length 20_\n"
        f"💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Generate Another", callback_data=f"passgen_{length}")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ]),
    )

# ── TIMEZONE / WORLD CLOCK ──
async def cmd_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(
            f"🕐 *World Clock*\n{LINE}\nUsage: `/timezone <city or timezone>`\n\n"
            f"Examples:\n`/timezone London`\n`/timezone New_York`\n`/timezone Tokyo`\n`/timezone Dubai`\n`/timezone UTC`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    tz_query = "_".join(context.args)
    try:
        r = requests.get(f"https://worldtimeapi.org/api/timezone", timeout=8)
        all_zones = r.json() if r.status_code == 200 else []
        matched = [z for z in all_zones if tz_query.lower() in z.lower()]
        if not matched:
            matched = [z for z in all_zones if any(w.lower() in z.lower() for w in context.args)]
        if not matched:
            db_user = get_user(user.id)
            await update.message.reply_text(
                f"❌ Timezone not found for `{tz_query}`.\n\nTry using full names like `America/New_York`, `Europe/London`, `Asia/Tokyo`.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        zone = matched[0]
        r2 = requests.get(f"https://worldtimeapi.org/api/timezone/{zone}", timeout=8)
        if r2.status_code != 200:
            await update.message.reply_text("❌ Could not fetch timezone data.", parse_mode=ParseMode.MARKDOWN)
            return
        data = r2.json()
        dt_str = data.get("datetime","")
        day_of_week = data.get("day_of_week", "")
        utc_offset = data.get("utc_offset","")
        week_number = data.get("week_number","")
        days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
        dow = days[int(day_of_week)] if str(day_of_week).isdigit() else day_of_week
        formatted = dt_str[:19].replace("T"," ") if dt_str else "N/A"
        track_tool_usage("timezone")
        db_user = get_user(user.id)
        await update.message.reply_text(
            f"╔══════════════════════════════╗\n║     🕐 WORLD CLOCK           ║\n╚══════════════════════════════╝\n\n"
            f"🌍 *Timezone:* `{zone}`\n"
            f"🕐 *Current Time:* `{formatted}`\n"
            f"📅 *Day:* `{dow}`\n"
            f"🔢 *Week:* `#{week_number}`\n"
            f"🌐 *UTC Offset:* `{utc_offset}`\n{LINE}\n"
            f"💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_main_keyboard(),
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ── CALCULATOR ──
_SAFE_OPS = {
    _ast.Add: _operator.add, _ast.Sub: _operator.sub,
    _ast.Mult: _operator.mul, _ast.Div: _operator.truediv,
    _ast.Pow: _operator.pow, _ast.Mod: _operator.mod,
    _ast.FloorDiv: _operator.floordiv,
    _ast.USub: _operator.neg, _ast.UAdd: _operator.pos,
}
def _safe_eval(node):
    if isinstance(node, _ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Not a number")
    elif isinstance(node, _ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if type(node.op) is _ast.Pow and abs(right) > 100:
            raise ValueError("Exponent too large")
        return op(left, right)
    elif isinstance(node, _ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError("Unsupported unary operator")
        return op(_safe_eval(node.operand))
    elif isinstance(node, _ast.Call):
        if isinstance(node.func, _ast.Attribute):
            raise ValueError("No method calls allowed")
        raise ValueError("No function calls allowed")
    else:
        raise ValueError(f"Unsupported expression type: {type(node).__name__}")

def safe_calculate(expr: str) -> str:
    expr = expr.replace("^","**").replace("×","*").replace("÷","/").replace(",","")
    try:
        tree = _ast.parse(expr, mode="eval")
        result = _safe_eval(tree.body)
        if isinstance(result, float):
            if result == int(result) and abs(result) < 1e15:
                return str(int(result))
            return f"{result:.10g}"
        return str(result)
    except ZeroDivisionError:
        return "Error: Division by zero"
    except Exception as e:
        return f"Error: {e}"

async def cmd_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not context.args:
        await update.message.reply_text(
            f"🧮 *Calculator* _(Free)_\n{LINE}\nUsage: `/calc <expression>`\n\n"
            f"Examples:\n`/calc 15 * 7 + 3`\n`/calc (100 - 20) / 4`\n`/calc 2 ^ 10`\n`/calc 355 / 113`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    expr = " ".join(context.args)
    result = safe_calculate(expr)
    track_tool_usage("calc")
    await update.message.reply_text(
        f"🧮 *Calculator*\n{LINE}\n📥 `{expr}`\n📤 *=* `{result}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_main_keyboard(),
    )

# ── RANDOM NAME GENERATOR ──
FIRST_NAMES_M = ["James","Liam","Noah","William","Benjamin","Elijah","Lucas","Mason","Ethan","Daniel","Oliver","Alexander","Henry","Jackson","Michael","Sebastian","Aiden","Matthew","Samuel","David","Joseph","Carter","Owen","Wyatt","John","Jack","Luke","Jayden","Dylan","Grayson"]
FIRST_NAMES_F = ["Emma","Olivia","Ava","Isabella","Sophia","Mia","Charlotte","Amelia","Harper","Evelyn","Abigail","Emily","Elizabeth","Mila","Ella","Avery","Sofia","Camila","Aria","Scarlett","Victoria","Madison","Luna","Grace","Chloe","Penelope","Layla","Riley","Zoey","Nora"]
LAST_NAMES = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson","White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson"]
USERNAMES_ADJ = ["cool","dark","swift","cyber","silent","alpha","mega","ultra","pro","elite","turbo","hyper","stealth","ghost","neon","frost","iron","crimson","golden","silver"]
USERNAMES_NOUN = ["wolf","eagle","hawk","fox","lion","dragon","viper","blade","storm","nova","phantom","titan","nexus","byte","pixel","cipher","vector","pulse","surge","apex"]

async def cmd_randomname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_credits_and_use(update, user.id):
        return
    gender = _random.choice(["male","female"])
    first = _random.choice(FIRST_NAMES_M if gender == "male" else FIRST_NAMES_F)
    last = _random.choice(LAST_NAMES)
    full = f"{first} {last}"
    username = f"{_random.choice(USERNAMES_ADJ)}_{_random.choice(USERNAMES_NOUN)}{_random.randint(10,999)}"
    age = _random.randint(18, 55)
    year = 2025 - age
    month = _random.randint(1, 12)
    day = _random.randint(1, 28)
    dob = f"{day:02d}/{month:02d}/{year}"
    track_tool_usage("randomname")
    db_user = get_user(user.id)
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║    🎭 RANDOM IDENTITY        ║\n╚══════════════════════════════╝\n\n"
        f"👤 *Full Name:* `{full}`\n"
        f"{'♂️' if gender=='male' else '♀️'} *Gender:* `{gender.capitalize()}`\n"
        f"🎂 *Date of Birth:* `{dob}`\n"
        f"📅 *Age:* `{age}`\n"
        f"💻 *Username:* `@{username}`\n{LINE}\n"
        f"💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Generate Another", callback_data="randomname_gen")],
            [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
        ]),
    )

# ── IP GEOLOCATION (enhanced) ──
async def cmd_geoip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/geoip <ip address>`\nExample: `/geoip 8.8.8.8`", parse_mode=ParseMode.MARKDOWN)
        return
    ip = context.args[0].strip()
    msg = await update.message.reply_text(f"🌐 _Looking up `{ip}`…_", parse_mode=ParseMode.MARKDOWN)
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=10)
        if r.status_code == 200:
            d = r.json()
            if d.get("error"):
                await msg.edit_text(f"❌ {d.get('reason','Invalid IP address')}", parse_mode=ParseMode.MARKDOWN)
                return
            track_tool_usage("geoip")
            db_user = get_user(user.id)
            await msg.edit_text(
                f"╔══════════════════════════════╗\n║    🌐 IP GEOLOCATION         ║\n╚══════════════════════════════╝\n\n"
                f"🔍 *IP:* `{d.get('ip','N/A')}`\n"
                f"🏙️ *City:* `{d.get('city','N/A')}`\n"
                f"🗺️ *Region:* `{d.get('region','N/A')}`\n"
                f"🏳️ *Country:* `{d.get('country_name','N/A')} {d.get('country_code','')}`\n"
                f"🌍 *Continent:* `{d.get('continent_code','N/A')}`\n"
                f"📮 *Postal:* `{d.get('postal','N/A')}`\n"
                f"📡 *ISP/Org:* `{d.get('org','N/A')}`\n"
                f"🌐 *Timezone:* `{d.get('timezone','N/A')}`\n"
                f"📍 *Lat/Lon:* `{d.get('latitude','')}, {d.get('longitude','')}`\n"
                f"💻 *ASN:* `{d.get('asn','N/A')}`\n{LINE}\n"
                f"💰 Credits Left: `{db_user['credits']}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_main_keyboard(),
            )
        else:
            await msg.edit_text(f"❌ Lookup failed (HTTP {r.status_code})", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ── MD5 / HASH LOOKUP (reverse) ──
async def cmd_hashlookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/hashlookup <md5_hash>`\nExample: `/hashlookup 5d41402abc4b2a76b9719d911017c592`", parse_mode=ParseMode.MARKDOWN)
        return
    hash_val = context.args[0].strip().lower()
    msg = await update.message.reply_text(f"🔍 _Looking up hash…_", parse_mode=ParseMode.MARKDOWN)
    try:
        r = requests.get(f"https://md5.gromweb.com/?md5={hash_val}", timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        db_user = get_user(user.id)
        if r.status_code == 200 and "reverse-string" in r.text:
            import re as _re
            match = _re.search(r'class="reverse-string"[^>]*>([^<]+)<', r.text)
            if match:
                plaintext = match.group(1).strip()
                track_tool_usage("hashlookup")
                await msg.edit_text(
                    f"╔══════════════════════════════╗\n║    🔓 HASH LOOKUP            ║\n╚══════════════════════════════╝\n\n"
                    f"🔐 *Hash:* `{hash_val}`\n"
                    f"🔓 *Decrypted:* `{plaintext}`\n{LINE}\n"
                    f"💰 Credits Left: `{db_user['credits']}`",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=back_main_keyboard(),
                )
                return
        await msg.edit_text(
            f"🔐 *Hash:* `{hash_val}`\n❌ *Not found* in public database.\n\n_This hash may be salted or not in the rainbow table._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_main_keyboard(),
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════
# ⚡ BATCH 1 — MATH / SCIENCE / CIPHER / REFERENCE
# ═══════════════════════════════════════════════════════

# ── WIKIPEDIA ──
def wiki_summary(query: str) -> dict:
    try:
        search_r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action":"query","list":"search","srsearch":query,"format":"json","srlimit":1},
            timeout=10,
        )
        results = search_r.json().get("query",{}).get("search",[])
        if not results:
            return {"error":"No results found."}
        title = results[0]["title"]
        extract_r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action":"query","prop":"extracts","exintro":True,"explaintext":True,"titles":title,"format":"json"},
            timeout=10,
        )
        pages = extract_r.json().get("query",{}).get("pages",{})
        page = next(iter(pages.values()))
        extract = page.get("extract","")
        sentences = extract.split(". ")
        summary = ". ".join(sentences[:4]).strip()
        if summary and not summary.endswith("."):
            summary += "."
        return {"title":title, "summary":summary[:1200]}
    except Exception as e:
        return {"error":str(e)}

async def cmd_wiki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/wiki <topic>`\nExample: `/wiki Black Holes`", parse_mode=ParseMode.MARKDOWN)
        return
    query = " ".join(context.args)
    msg = await update.message.reply_text(f"📚 _Searching Wikipedia for `{query}`…_", parse_mode=ParseMode.MARKDOWN)
    result = wiki_summary(query)
    db_user = get_user(user.id)
    if "error" in result:
        await msg.edit_text(f"{CROSS} {result['error']}", parse_mode=ParseMode.MARKDOWN)
        return
    track_tool_usage("wiki")
    await msg.edit_text(
        f"╔══════════════════════════════╗\n║      📚 WIKIPEDIA            ║\n╚══════════════════════════════╝\n\n"
        f"📖 *{result['title']}*\n{LINE}\n\n"
        f"{result['summary']}\n\n{LINE}\n"
        f"🔗 _en.wikipedia.org/wiki/{result['title'].replace(' ','_')}_\n"
        f"💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
    )

# ── STATISTICS ──
def compute_stats(numbers: list) -> dict:
    import statistics as _s
    n = len(numbers)
    total = sum(numbers)
    mean = total / n
    median = _s.median(numbers)
    mode_val = None
    try:
        mode_val = _s.mode(numbers)
    except Exception:
        pass
    std = _s.stdev(numbers) if n > 1 else 0
    variance = _s.variance(numbers) if n > 1 else 0
    minimum = min(numbers)
    maximum = max(numbers)
    rang = maximum - minimum
    sorted_nums = sorted(numbers)
    q1 = _s.median(sorted_nums[:n//2])
    q3 = _s.median(sorted_nums[(n+1)//2:])
    iqr = q3 - q1
    return {"n":n,"sum":total,"mean":mean,"median":median,"mode":mode_val,
            "std":std,"variance":variance,"min":minimum,"max":maximum,
            "range":rang,"q1":q1,"q3":q3,"iqr":iqr}

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/stats <numbers>`\nExample: `/stats 10 20 30 40 50`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        nums = [float(x) for x in context.args]
        if len(nums) < 2:
            await update.message.reply_text("❌ Provide at least 2 numbers.", parse_mode=ParseMode.MARKDOWN)
            return
    except ValueError:
        await update.message.reply_text("❌ All values must be numbers.", parse_mode=ParseMode.MARKDOWN)
        return
    s = compute_stats(nums)
    db_user = get_user(user.id)
    track_tool_usage("stats")
    fmt = lambda v: f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v,float) else str(v)
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║   📊 STATISTICS ANALYSIS    ║\n╚══════════════════════════════╝\n\n"
        f"🔢 *Count (n):* `{s['n']}`\n"
        f"➕ *Sum:* `{fmt(s['sum'])}`\n"
        f"📈 *Mean:* `{fmt(s['mean'])}`\n"
        f"📍 *Median:* `{fmt(s['median'])}`\n"
        f"🔁 *Mode:* `{fmt(s['mode']) if s['mode'] is not None else 'No unique mode'}`\n"
        f"{LINE}\n"
        f"📉 *Min:* `{fmt(s['min'])}`\n"
        f"📈 *Max:* `{fmt(s['max'])}`\n"
        f"📐 *Range:* `{fmt(s['range'])}`\n"
        f"{LINE}\n"
        f"🎲 *Std Dev:* `{fmt(s['std'])}`\n"
        f"📊 *Variance:* `{fmt(s['variance'])}`\n"
        f"🔢 *Q1:* `{fmt(s['q1'])}` | *Q3:* `{fmt(s['q3'])}`\n"
        f"📏 *IQR:* `{fmt(s['iqr'])}`\n"
        f"{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
    )

# ── UNIT CONVERTER ──
UNIT_CONVERSIONS = {
    "length": {
        "mm":0.001,"cm":0.01,"m":1.0,"km":1000.0,
        "in":0.0254,"ft":0.3048,"yd":0.9144,"mi":1609.344,"nm":1852.0,
    },
    "weight": {
        "mg":0.000001,"g":0.001,"kg":1.0,"t":1000.0,
        "oz":0.0283495,"lb":0.453592,"st":6.35029,
    },
    "volume": {
        "ml":0.001,"l":1.0,"m3":1000.0,"tsp":0.00492892,"tbsp":0.0147868,
        "cup":0.236588,"pt":0.473176,"qt":0.946353,"gal":3.78541,"fl_oz":0.0295735,
    },
    "area": {
        "mm2":0.000001,"cm2":0.0001,"m2":1.0,"km2":1e6,
        "in2":0.00064516,"ft2":0.092903,"yd2":0.836127,"acre":4046.86,"ha":10000.0,"mi2":2589988.0,
    },
    "speed": {
        "m/s":1.0,"km/h":0.277778,"mph":0.44704,"kn":0.514444,"ft/s":0.3048,
    },
    "time": {
        "ms":0.001,"s":1.0,"min":60.0,"h":3600.0,"d":86400.0,"wk":604800.0,"mo":2629800.0,"yr":31557600.0,
    },
    "data": {
        "bit":0.125,"b":1.0,"kb":1024.0,"mb":1048576.0,"gb":1073741824.0,"tb":1099511627776.0,
    },
    "pressure": {
        "pa":1.0,"kpa":1000.0,"mpa":1e6,"bar":100000.0,"psi":6894.76,"atm":101325.0,"mmhg":133.322,
    },
    "energy": {
        "j":1.0,"kj":1000.0,"mj":1e6,"cal":4.18400,"kcal":4184.0,"kwh":3600000.0,"btu":1055.06,"ev":1.602e-19,
    },
}
UNIT_ALIASES = {
    "mm":"mm","cm":"cm","m":"m","km":"km","kilometer":"km","kilometers":"km","metre":"m","meter":"m",
    "inch":"in","inches":"in","foot":"ft","feet":"ft","yard":"yd","yards":"yd","mile":"mi","miles":"mi",
    "gram":"g","grams":"g","kilogram":"kg","kilograms":"kg","pound":"lb","pounds":"lb","ounce":"oz","ounces":"oz",
    "liter":"l","litre":"l","liters":"l","gallon":"gal","gallons":"gal","cup":"cup","teaspoon":"tsp","tablespoon":"tbsp",
    "second":"s","seconds":"s","minute":"min","minutes":"min","hour":"h","hours":"h","day":"d","days":"d",
    "week":"wk","weeks":"wk","month":"mo","months":"mo","year":"yr","years":"yr",
    "bit":"bit","byte":"b","kilobyte":"kb","megabyte":"mb","gigabyte":"gb","terabyte":"tb",
    "pascal":"pa","bar":"bar","psi":"psi","atm":"atm",
    "joule":"j","calorie":"cal","kilocalorie":"kcal","watt":"kwh","btu":"btu",
}
def find_unit_category(unit: str):
    u = UNIT_ALIASES.get(unit.lower(), unit.lower())
    for cat, units in UNIT_CONVERSIONS.items():
        if u in units:
            return cat, u, units
    return None, None, None

async def cmd_convert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 3:
        await update.message.reply_text(
            f"🔄 *Unit Converter*\n{LINE}\nUsage: `/convert <value> <from> <to>`\n\n"
            f"Examples:\n`/convert 100 km mi`\n`/convert 70 kg lb`\n`/convert 1 gal l`\n`/convert 5 h min`\n`/convert 1 gb mb`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    try:
        val = float(context.args[0])
        from_unit = context.args[1].lower()
        to_unit = context.args[2].lower()
    except ValueError:
        await update.message.reply_text("❌ Invalid value. Use a number.", parse_mode=ParseMode.MARKDOWN)
        return
    cat1, fu, units = find_unit_category(from_unit)
    cat2, tu, _ = find_unit_category(to_unit)
    db_user = get_user(user.id)
    if not cat1 or not cat2:
        await update.message.reply_text(f"❌ Unknown unit(s). Check spelling.", parse_mode=ParseMode.MARKDOWN)
        return
    if cat1 != cat2:
        await update.message.reply_text(f"❌ Cannot convert between `{cat1}` and `{cat2}`.", parse_mode=ParseMode.MARKDOWN)
        return
    base = val * units[fu]
    result = base / units[tu]
    fmt_result = f"{result:.10g}"
    track_tool_usage("convert")
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║     🔄 UNIT CONVERTER        ║\n╚══════════════════════════════╝\n\n"
        f"📐 *Category:* `{cat1.capitalize()}`\n{LINE}\n"
        f"📥 `{val:g} {fu}` = `{fmt_result} {tu}`\n{LINE}\n"
        f"💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
    )

# ── PRIME NUMBERS ──
def is_prime(n: int) -> bool:
    if n < 2: return False
    if n == 2: return True
    if n % 2 == 0: return False
    for i in range(3, int(n**0.5)+1, 2):
        if n % i == 0: return False
    return True

def prime_factors(n: int) -> list:
    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1: factors.append(n)
    return factors

def nth_prime(n: int) -> int:
    count, num = 0, 1
    while count < n:
        num += 1
        if is_prime(num):
            count += 1
    return num

async def cmd_prime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/prime <number>`\nExample: `/prime 97`  or  `/prime nth 10`", parse_mode=ParseMode.MARKDOWN)
        return
    db_user = get_user(user.id)
    track_tool_usage("prime")
    if context.args[0].lower() == "nth" and len(context.args) > 1:
        n = int(context.args[1])
        if n < 1 or n > 10000:
            await update.message.reply_text("❌ N must be between 1 and 10000.", parse_mode=ParseMode.MARKDOWN)
            return
        p = nth_prime(n)
        await update.message.reply_text(
            f"🔢 *The {n}th prime number is:* `{p}`\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
        )
        return
    try:
        n = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Enter a whole number.", parse_mode=ParseMode.MARKDOWN)
        return
    prime = is_prime(n)
    factors = prime_factors(n) if not prime and n > 1 else []
    icon = "✅" if prime else "❌"
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║     🔢 PRIME CHECKER         ║\n╚══════════════════════════════╝\n\n"
        f"🔢 *Number:* `{n}`\n"
        f"{icon} *Prime:* `{'Yes' if prime else 'No'}`\n"
        + (f"🧮 *Factors:* `{' × '.join(map(str,factors))}`\n" if factors else "") +
        f"{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
    )

# ── BASE CONVERTER (Binary / Hex / Octal) ──
async def cmd_baseconv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            f"🔢 *Base Converter* — Usage:\n`/baseconv <number> <from_base>`\n\n"
            f"Examples:\n`/baseconv 255 10` — decimal → all\n`/baseconv FF 16` — hex → all\n`/baseconv 11111111 2` — binary → all",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    try:
        base = int(context.args[1])
        n_val = int(context.args[0], base)
    except Exception:
        await update.message.reply_text("❌ Invalid number or base.", parse_mode=ParseMode.MARKDOWN)
        return
    db_user = get_user(user.id)
    track_tool_usage("baseconv")
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║     🔢 BASE CONVERTER        ║\n╚══════════════════════════════╝\n\n"
        f"📥 *Input:* `{context.args[0]}` (Base {base})\n{LINE}\n"
        f"🔟 *Decimal (10):* `{n_val}`\n"
        f"🔵 *Binary  (2):* `{bin(n_val)[2:]}`\n"
        f"🟠 *Octal   (8):* `{oct(n_val)[2:]}`\n"
        f"🟢 *Hex    (16):* `{hex(n_val)[2:].upper()}`\n"
        f"{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
    )

# ── ROMAN NUMERALS ──
ROMAN_TABLE = [(1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),(100,"C"),(90,"XC"),
               (50,"L"),(40,"XL"),(10,"X"),(9,"IX"),(5,"V"),(4,"IV"),(1,"I")]
def to_roman(n: int) -> str:
    if n < 1 or n > 3999: return "Out of range (1-3999)"
    result = ""
    for val,sym in ROMAN_TABLE:
        while n >= val:
            result += sym; n -= val
    return result
def from_roman(s: str) -> int:
    vals = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
    total = 0
    prev = 0
    for ch in reversed(s.upper()):
        v = vals.get(ch, 0)
        if v < prev: total -= v
        else: total += v
        prev = v
    return total

async def cmd_roman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/roman <number or roman>`\nExamples: `/roman 2024` or `/roman MMXXIV`", parse_mode=ParseMode.MARKDOWN)
        return
    inp = context.args[0].strip()
    db_user = get_user(user.id)
    track_tool_usage("roman")
    if inp.isdigit():
        r = to_roman(int(inp))
        await update.message.reply_text(f"🏛️ *Roman Numerals*\n{LINE}\n`{inp}` → `{r}`\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())
    else:
        n = from_roman(inp)
        await update.message.reply_text(f"🏛️ *Roman Numerals*\n{LINE}\n`{inp.upper()}` → `{n}`\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

# ── PERIODIC TABLE ──
ELEMENTS = {
    "H":{"name":"Hydrogen","num":1,"mass":1.008,"cat":"Nonmetal"},
    "He":{"name":"Helium","num":2,"mass":4.003,"cat":"Noble Gas"},
    "Li":{"name":"Lithium","num":3,"mass":6.941,"cat":"Alkali Metal"},
    "Be":{"name":"Beryllium","num":4,"mass":9.012,"cat":"Alkaline Earth"},
    "B":{"name":"Boron","num":5,"mass":10.811,"cat":"Metalloid"},
    "C":{"name":"Carbon","num":6,"mass":12.011,"cat":"Nonmetal"},
    "N":{"name":"Nitrogen","num":7,"mass":14.007,"cat":"Nonmetal"},
    "O":{"name":"Oxygen","num":8,"mass":15.999,"cat":"Nonmetal"},
    "F":{"name":"Fluorine","num":9,"mass":18.998,"cat":"Halogen"},
    "Ne":{"name":"Neon","num":10,"mass":20.180,"cat":"Noble Gas"},
    "Na":{"name":"Sodium","num":11,"mass":22.990,"cat":"Alkali Metal"},
    "Mg":{"name":"Magnesium","num":12,"mass":24.305,"cat":"Alkaline Earth"},
    "Al":{"name":"Aluminium","num":13,"mass":26.982,"cat":"Post-transition"},
    "Si":{"name":"Silicon","num":14,"mass":28.086,"cat":"Metalloid"},
    "P":{"name":"Phosphorus","num":15,"mass":30.974,"cat":"Nonmetal"},
    "S":{"name":"Sulfur","num":16,"mass":32.065,"cat":"Nonmetal"},
    "Cl":{"name":"Chlorine","num":17,"mass":35.453,"cat":"Halogen"},
    "Ar":{"name":"Argon","num":18,"mass":39.948,"cat":"Noble Gas"},
    "K":{"name":"Potassium","num":19,"mass":39.098,"cat":"Alkali Metal"},
    "Ca":{"name":"Calcium","num":20,"mass":40.078,"cat":"Alkaline Earth"},
    "Sc":{"name":"Scandium","num":21,"mass":44.956,"cat":"Transition Metal"},
    "Ti":{"name":"Titanium","num":22,"mass":47.867,"cat":"Transition Metal"},
    "V":{"name":"Vanadium","num":23,"mass":50.942,"cat":"Transition Metal"},
    "Cr":{"name":"Chromium","num":24,"mass":51.996,"cat":"Transition Metal"},
    "Mn":{"name":"Manganese","num":25,"mass":54.938,"cat":"Transition Metal"},
    "Fe":{"name":"Iron","num":26,"mass":55.845,"cat":"Transition Metal"},
    "Co":{"name":"Cobalt","num":27,"mass":58.933,"cat":"Transition Metal"},
    "Ni":{"name":"Nickel","num":28,"mass":58.693,"cat":"Transition Metal"},
    "Cu":{"name":"Copper","num":29,"mass":63.546,"cat":"Transition Metal"},
    "Zn":{"name":"Zinc","num":30,"mass":65.38,"cat":"Transition Metal"},
    "Ga":{"name":"Gallium","num":31,"mass":69.723,"cat":"Post-transition"},
    "Ge":{"name":"Germanium","num":32,"mass":72.630,"cat":"Metalloid"},
    "As":{"name":"Arsenic","num":33,"mass":74.922,"cat":"Metalloid"},
    "Se":{"name":"Selenium","num":34,"mass":78.971,"cat":"Nonmetal"},
    "Br":{"name":"Bromine","num":35,"mass":79.904,"cat":"Halogen"},
    "Kr":{"name":"Krypton","num":36,"mass":83.798,"cat":"Noble Gas"},
    "Rb":{"name":"Rubidium","num":37,"mass":85.468,"cat":"Alkali Metal"},
    "Sr":{"name":"Strontium","num":38,"mass":87.62,"cat":"Alkaline Earth"},
    "Y":{"name":"Yttrium","num":39,"mass":88.906,"cat":"Transition Metal"},
    "Zr":{"name":"Zirconium","num":40,"mass":91.224,"cat":"Transition Metal"},
    "Nb":{"name":"Niobium","num":41,"mass":92.906,"cat":"Transition Metal"},
    "Mo":{"name":"Molybdenum","num":42,"mass":95.95,"cat":"Transition Metal"},
    "Tc":{"name":"Technetium","num":43,"mass":98.0,"cat":"Transition Metal"},
    "Ru":{"name":"Ruthenium","num":44,"mass":101.07,"cat":"Transition Metal"},
    "Rh":{"name":"Rhodium","num":45,"mass":102.91,"cat":"Transition Metal"},
    "Pd":{"name":"Palladium","num":46,"mass":106.42,"cat":"Transition Metal"},
    "Ag":{"name":"Silver","num":47,"mass":107.87,"cat":"Transition Metal"},
    "Cd":{"name":"Cadmium","num":48,"mass":112.41,"cat":"Transition Metal"},
    "In":{"name":"Indium","num":49,"mass":114.82,"cat":"Post-transition"},
    "Sn":{"name":"Tin","num":50,"mass":118.71,"cat":"Post-transition"},
    "Sb":{"name":"Antimony","num":51,"mass":121.76,"cat":"Metalloid"},
    "Te":{"name":"Tellurium","num":52,"mass":127.60,"cat":"Metalloid"},
    "I":{"name":"Iodine","num":53,"mass":126.90,"cat":"Halogen"},
    "Xe":{"name":"Xenon","num":54,"mass":131.29,"cat":"Noble Gas"},
    "Cs":{"name":"Caesium","num":55,"mass":132.91,"cat":"Alkali Metal"},
    "Ba":{"name":"Barium","num":56,"mass":137.33,"cat":"Alkaline Earth"},
    "La":{"name":"Lanthanum","num":57,"mass":138.91,"cat":"Lanthanide"},
    "Ce":{"name":"Cerium","num":58,"mass":140.12,"cat":"Lanthanide"},
    "Pr":{"name":"Praseodymium","num":59,"mass":140.91,"cat":"Lanthanide"},
    "Nd":{"name":"Neodymium","num":60,"mass":144.24,"cat":"Lanthanide"},
    "Pm":{"name":"Promethium","num":61,"mass":145.0,"cat":"Lanthanide"},
    "Sm":{"name":"Samarium","num":62,"mass":150.36,"cat":"Lanthanide"},
    "Eu":{"name":"Europium","num":63,"mass":151.96,"cat":"Lanthanide"},
    "Gd":{"name":"Gadolinium","num":64,"mass":157.25,"cat":"Lanthanide"},
    "Tb":{"name":"Terbium","num":65,"mass":158.93,"cat":"Lanthanide"},
    "Dy":{"name":"Dysprosium","num":66,"mass":162.50,"cat":"Lanthanide"},
    "Ho":{"name":"Holmium","num":67,"mass":164.93,"cat":"Lanthanide"},
    "Er":{"name":"Erbium","num":68,"mass":167.26,"cat":"Lanthanide"},
    "Tm":{"name":"Thulium","num":69,"mass":168.93,"cat":"Lanthanide"},
    "Yb":{"name":"Ytterbium","num":70,"mass":173.05,"cat":"Lanthanide"},
    "Lu":{"name":"Lutetium","num":71,"mass":174.97,"cat":"Lanthanide"},
    "Hf":{"name":"Hafnium","num":72,"mass":178.49,"cat":"Transition Metal"},
    "Ta":{"name":"Tantalum","num":73,"mass":180.95,"cat":"Transition Metal"},
    "W":{"name":"Tungsten","num":74,"mass":183.84,"cat":"Transition Metal"},
    "Re":{"name":"Rhenium","num":75,"mass":186.21,"cat":"Transition Metal"},
    "Os":{"name":"Osmium","num":76,"mass":190.23,"cat":"Transition Metal"},
    "Ir":{"name":"Iridium","num":77,"mass":192.22,"cat":"Transition Metal"},
    "Pt":{"name":"Platinum","num":78,"mass":195.08,"cat":"Transition Metal"},
    "Au":{"name":"Gold","num":79,"mass":196.97,"cat":"Transition Metal"},
    "Hg":{"name":"Mercury","num":80,"mass":200.59,"cat":"Transition Metal"},
    "Tl":{"name":"Thallium","num":81,"mass":204.38,"cat":"Post-transition"},
    "Pb":{"name":"Lead","num":82,"mass":207.2,"cat":"Post-transition"},
    "Bi":{"name":"Bismuth","num":83,"mass":208.98,"cat":"Post-transition"},
    "Po":{"name":"Polonium","num":84,"mass":209.0,"cat":"Post-transition"},
    "At":{"name":"Astatine","num":85,"mass":210.0,"cat":"Halogen"},
    "Rn":{"name":"Radon","num":86,"mass":222.0,"cat":"Noble Gas"},
    "Fr":{"name":"Francium","num":87,"mass":223.0,"cat":"Alkali Metal"},
    "Ra":{"name":"Radium","num":88,"mass":226.0,"cat":"Alkaline Earth"},
    "Ac":{"name":"Actinium","num":89,"mass":227.0,"cat":"Actinide"},
    "Th":{"name":"Thorium","num":90,"mass":232.04,"cat":"Actinide"},
    "Pa":{"name":"Protactinium","num":91,"mass":231.04,"cat":"Actinide"},
    "U":{"name":"Uranium","num":92,"mass":238.03,"cat":"Actinide"},
    "Np":{"name":"Neptunium","num":93,"mass":237.0,"cat":"Actinide"},
    "Pu":{"name":"Plutonium","num":94,"mass":244.0,"cat":"Actinide"},
    "Am":{"name":"Americium","num":95,"mass":243.0,"cat":"Actinide"},
    "Cm":{"name":"Curium","num":96,"mass":247.0,"cat":"Actinide"},
    "Bk":{"name":"Berkelium","num":97,"mass":247.0,"cat":"Actinide"},
    "Cf":{"name":"Californium","num":98,"mass":251.0,"cat":"Actinide"},
    "Es":{"name":"Einsteinium","num":99,"mass":252.0,"cat":"Actinide"},
    "Fm":{"name":"Fermium","num":100,"mass":257.0,"cat":"Actinide"},
    "Md":{"name":"Mendelevium","num":101,"mass":258.0,"cat":"Actinide"},
    "No":{"name":"Nobelium","num":102,"mass":259.0,"cat":"Actinide"},
    "Lr":{"name":"Lawrencium","num":103,"mass":262.0,"cat":"Actinide"},
    "Rf":{"name":"Rutherfordium","num":104,"mass":267.0,"cat":"Transition Metal"},
    "Db":{"name":"Dubnium","num":105,"mass":268.0,"cat":"Transition Metal"},
    "Sg":{"name":"Seaborgium","num":106,"mass":271.0,"cat":"Transition Metal"},
    "Bh":{"name":"Bohrium","num":107,"mass":272.0,"cat":"Transition Metal"},
    "Hs":{"name":"Hassium","num":108,"mass":270.0,"cat":"Transition Metal"},
    "Mt":{"name":"Meitnerium","num":109,"mass":278.0,"cat":"Unknown"},
    "Ds":{"name":"Darmstadtium","num":110,"mass":281.0,"cat":"Unknown"},
    "Rg":{"name":"Roentgenium","num":111,"mass":282.0,"cat":"Unknown"},
    "Cn":{"name":"Copernicium","num":112,"mass":285.0,"cat":"Transition Metal"},
    "Nh":{"name":"Nihonium","num":113,"mass":286.0,"cat":"Unknown"},
    "Fl":{"name":"Flerovium","num":114,"mass":289.0,"cat":"Unknown"},
    "Mc":{"name":"Moscovium","num":115,"mass":290.0,"cat":"Unknown"},
    "Lv":{"name":"Livermorium","num":116,"mass":293.0,"cat":"Unknown"},
    "Ts":{"name":"Tennessine","num":117,"mass":294.0,"cat":"Unknown"},
    "Og":{"name":"Oganesson","num":118,"mass":294.0,"cat":"Unknown"},
}

async def cmd_periodic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/periodic <symbol or name or atomic_number>`\nExamples: `/periodic Au` `/periodic Gold` `/periodic 79`", parse_mode=ParseMode.MARKDOWN)
        return
    query_el = " ".join(context.args).strip()
    elem = None
    sym = None
    if query_el.isdigit():
        n = int(query_el)
        for s,e in ELEMENTS.items():
            if e["num"] == n:
                elem = e; sym = s; break
    else:
        for s,e in ELEMENTS.items():
            if s.lower() == query_el.lower() or e["name"].lower() == query_el.lower():
                elem = e; sym = s; break
    db_user = get_user(user.id)
    track_tool_usage("periodic")
    if not elem:
        await update.message.reply_text(f"❌ Element `{query_el}` not found.\nTry symbol (Au), name (Gold), or atomic number (79).", parse_mode=ParseMode.MARKDOWN)
        return
    cat_icons = {"Nonmetal":"🟢","Noble Gas":"🔵","Alkali Metal":"🟡","Alkaline Earth":"🟠","Transition Metal":"⚪","Metalloid":"🟣","Post-transition":"🔘","Halogen":"🔴","Lanthanide":"💛","Actinide":"♦️","Unknown":"⬜"}
    cat_icon = cat_icons.get(elem["cat"],"⬜")
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║   ⚗️  PERIODIC TABLE          ║\n╚══════════════════════════════╝\n\n"
        f"🔬 *Symbol:* `{sym}`\n"
        f"📛 *Name:* `{elem['name']}`\n"
        f"🔢 *Atomic Number:* `{elem['num']}`\n"
        f"⚖️ *Atomic Mass:* `{elem['mass']} u`\n"
        f"{cat_icon} *Category:* `{elem['cat']}`\n"
        f"{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
    )

# ── FIBONACCI ──
async def cmd_fibonacci(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(f"{WARN} Usage: `/fibonacci <n>`\nExample: `/fibonacci 20` (first 20 Fibonacci numbers)", parse_mode=ParseMode.MARKDOWN)
        return
    n = min(int(context.args[0]), 50)
    fibs = []
    a, b = 0, 1
    for _ in range(n):
        fibs.append(a); a, b = b, a+b
    db_user = get_user(user.id)
    track_tool_usage("fibonacci")
    seq = ", ".join(map(str, fibs))
    await update.message.reply_text(
        f"🌀 *Fibonacci Sequence (first {n})*\n{LINE}\n`{seq}`\n\n"
        f"🔢 *F({n}):* `{fibs[-1]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
    )

# ── CIPHER TOOLS ──
MORSE_CODE = {
    "A":".-","B":"-...","C":"-.-.","D":"-..","E":".","F":"..-.","G":"--.","H":"....","I":"..","J":".---",
    "K":"-.-","L":".-..","M":"--","N":"-.","O":"---","P":".--.","Q":"--.-","R":".-.","S":"...","T":"-",
    "U":"..-","V":"...-","W":".--","X":"-..-","Y":"-.--","Z":"--..",
    "0":"-----","1":".----","2":"..---","3":"...--","4":"....-","5":".....","6":"-....","7":"--...","8":"---..","9":"----.",
    ".":".-.-.-",",":"--..--","?":"..--..","!":"-.-.--","/":"-..-.","(":"-.--.",")":"-.--.-",
    "&":".-...","@":".--.-.","=":"-...-","+":".-.-.","-":"-....-",
}
MORSE_REVERSE = {v:k for k,v in MORSE_CODE.items()}

def text_to_morse(text: str) -> str:
    result = []
    for ch in text.upper():
        if ch == " ":
            result.append("/")
        elif ch in MORSE_CODE:
            result.append(MORSE_CODE[ch])
        else:
            result.append("?")
    return " ".join(result)

def morse_to_text(morse: str) -> str:
    words = morse.strip().split(" / ")
    result = []
    for word in words:
        letters = []
        for code in word.split():
            letters.append(MORSE_REVERSE.get(code,"?"))
        result.append("".join(letters))
    return " ".join(result)

async def cmd_morse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"📡 *Morse Code*\n{LINE}\n`/morse encode Hello World`\n`/morse decode .... . .-.. .-.. --- / .-- --- .-. .-.. -.`", parse_mode=ParseMode.MARKDOWN)
        return
    mode = context.args[0].lower()
    text_in = " ".join(context.args[1:])
    db_user = get_user(user.id)
    track_tool_usage("morse")
    if mode == "encode":
        result = text_to_morse(text_in)
        label = "Morse Code"
    elif mode == "decode":
        result = morse_to_text(text_in)
        label = "Decoded Text"
    else:
        result = text_to_morse(" ".join(context.args))
        label = "Morse Code"
    await update.message.reply_text(
        f"📡 *Morse Code Converter*\n{LINE}\n📥 Input: `{text_in[:200] or ' '.join(context.args)[:200]}`\n\n📤 {label}:\n`{result[:1000]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
    )

async def cmd_caesar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 2 or not context.args[0].lstrip("-").isdigit():
        await update.message.reply_text(f"🔐 *Caesar Cipher*\n{LINE}\nUsage: `/caesar <shift> <text>`\nExample: `/caesar 3 Hello World`", parse_mode=ParseMode.MARKDOWN)
        return
    shift = int(context.args[0]) % 26
    text_in = " ".join(context.args[1:])
    result = ""
    for ch in text_in:
        if ch.isupper():
            result += chr((ord(ch)-65+shift)%26+65)
        elif ch.islower():
            result += chr((ord(ch)-97+shift)%26+97)
        else:
            result += ch
    db_user = get_user(user.id)
    track_tool_usage("caesar")
    await update.message.reply_text(
        f"🔐 *Caesar Cipher*\n{LINE}\n🔑 Shift: `{shift}`\n📥 Input: `{text_in[:300]}`\n📤 Output: `{result[:300]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
    )

async def cmd_rot13(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/rot13 <text>`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    result = ""
    for ch in text_in:
        if "a" <= ch <= "z":
            result += chr((ord(ch)-97+13)%26+97)
        elif "A" <= ch <= "Z":
            result += chr((ord(ch)-65+13)%26+65)
        else:
            result += ch
    db_user = get_user(user.id)
    track_tool_usage("rot13")
    await update.message.reply_text(
        f"🔄 *ROT13 Cipher*\n{LINE}\n📥 `{text_in[:300]}`\n📤 `{result[:300]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
    )

async def cmd_binary2text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            f"🔢 *Binary ↔ Text*\n{LINE}\n`/binary2text encode Hello`\n`/binary2text decode 01001000 01100101 01101100 01101100 01101111`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    mode = context.args[0].lower()
    rest = " ".join(context.args[1:])
    db_user = get_user(user.id)
    track_tool_usage("binary2text")
    try:
        if mode == "encode":
            result = " ".join(f"{ord(c):08b}" for c in rest)
            await update.message.reply_text(f"🔢 *Text → Binary*\n{LINE}\n📥 `{rest[:100]}`\n📤 `{result[:800]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())
        else:
            parts = rest.split()
            chars = [chr(int(b,2)) for b in parts if len(b)==8]
            result = "".join(chars)
            await update.message.reply_text(f"🔢 *Binary → Text*\n{LINE}\n📥 (binary data)\n📤 `{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: `{e}`", parse_mode=ParseMode.MARKDOWN)

async def cmd_hex2text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(f"🟢 *Hex ↔ Text*\n{LINE}\n`/hex2text encode Hello`\n`/hex2text decode 48656c6c6f`", parse_mode=ParseMode.MARKDOWN)
        return
    mode = context.args[0].lower()
    rest = " ".join(context.args[1:]).replace(" ","")
    db_user = get_user(user.id)
    track_tool_usage("hex2text")
    try:
        if mode == "encode":
            result = rest.encode().hex()
            await update.message.reply_text(f"🟢 *Text → Hex*\n{LINE}\n📥 `{rest[:100]}`\n📤 `{result[:800]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())
        else:
            result = bytes.fromhex(rest).decode("utf-8","replace")
            await update.message.reply_text(f"🟢 *Hex → Text*\n{LINE}\n📥 `{rest[:100]}`\n📤 `{result[:500]}`\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: `{e}`", parse_mode=ParseMode.MARKDOWN)

async def cmd_jwtdecode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/jwtdecode <token>`", parse_mode=ParseMode.MARKDOWN)
        return
    token = context.args[0].strip()
    db_user = get_user(user.id)
    track_tool_usage("jwtdecode")
    try:
        import base64 as _b64, json as _json
        parts = token.split(".")
        if len(parts) != 3:
            await update.message.reply_text("❌ Invalid JWT format (should have 3 parts).", parse_mode=ParseMode.MARKDOWN)
            return
        def pad(s): return s + "=" * (-len(s)%4)
        header = _json.loads(_b64.urlsafe_b64decode(pad(parts[0])))
        payload = _json.loads(_b64.urlsafe_b64decode(pad(parts[1])))
        header_str = _json.dumps(header, indent=2)[:400]
        payload_str = _json.dumps(payload, indent=2)[:600]
        await update.message.reply_text(
            f"╔══════════════════════════════╗\n║     🔓 JWT DECODER           ║\n╚══════════════════════════════╝\n\n"
            f"📋 *Header:*\n```\n{header_str}\n```\n"
            f"📦 *Payload:*\n```\n{payload_str}\n```\n"
            f"🔏 *Signature:* `[present — not verified]`\n"
            f"{LINE}\n⚠️ _Decoded locally — signature not validated_\n"
            f"💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Decode failed: `{e}`", parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════
# ⚡ BATCH 2 — GAMES / WORLD / SOCIAL
# ═══════════════════════════════════════════════════════

# ── ROCK PAPER SCISSORS ──
RPS_CHOICES = {"🪨":"rock","📄":"paper","✂️":"scissors"}
RPS_WIN = {"rock":"scissors","paper":"rock","scissors":"paper"}
RPS_EMOJI = {"rock":"🪨","paper":"📄","scissors":"✂️"}

async def cmd_rps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🪨 Rock", callback_data="rps_rock"),
        InlineKeyboardButton("📄 Paper", callback_data="rps_paper"),
        InlineKeyboardButton("✂️ Scissors", callback_data="rps_scissors"),
    ],[InlineKeyboardButton("« Menu", callback_data="main_menu")]])
    await update.message.reply_text(
        f"🎮 *Rock Paper Scissors*\n{LINE}\nPick your move — the bot will respond instantly!\n_No credits required — just for fun!_",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb,
    )

# ── MAGIC 8-BALL ──
EIGHT_BALL_RESPONSES = [
    "🟢 It is certain.","🟢 It is decidedly so.","🟢 Without a doubt.","🟢 Yes, definitely.",
    "🟢 You may rely on it.","🟢 As I see it, yes.","🟢 Most likely.","🟢 Outlook good.",
    "🟢 Yes.","🟢 Signs point to yes.","🟡 Reply hazy, try again.","🟡 Ask again later.",
    "🟡 Better not tell you now.","🟡 Cannot predict now.","🟡 Concentrate and ask again.",
    "🔴 Don't count on it.","🔴 My reply is no.","🔴 My sources say no.",
    "🔴 Outlook not so good.","🔴 Very doubtful.",
]

async def cmd_8ball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/8ball <your question>`\nExample: `/8ball Will I get rich?`", parse_mode=ParseMode.MARKDOWN)
        return
    question = " ".join(context.args)
    answer = _random.choice(EIGHT_BALL_RESPONSES)
    await update.message.reply_text(
        f"🎱 *Magic 8-Ball*\n{LINE}\n❓ *Q:* _{question}_\n\n🎱 *A:* {answer}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎱 Ask Again", callback_data=f"8ball_{question[:50]}")]]),
    )

# ── DICE ROLLER ──
async def cmd_roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not context.args:
        await update.message.reply_text(f"🎲 *Dice Roller*\nUsage: `/roll <NdN+mod>`\nExamples:\n`/roll 2d6` — Roll 2 six-sided dice\n`/roll 1d20+5` — D20 + modifier\n`/roll 4d6` — 4 dice", parse_mode=ParseMode.MARKDOWN)
        return
    import re as _re
    expr = context.args[0].strip().lower()
    m = _re.match(r"(\d+)d(\d+)([+-]\d+)?", expr)
    if not m:
        await update.message.reply_text("❌ Format: `NdN` or `NdN+mod` (e.g. `2d6`, `1d20+3`)", parse_mode=ParseMode.MARKDOWN)
        return
    num_dice = min(int(m.group(1)), 20)
    die_sides = min(int(m.group(2)), 1000)
    modifier = int(m.group(3)) if m.group(3) else 0
    rolls = [_random.randint(1, die_sides) for _ in range(num_dice)]
    total = sum(rolls) + modifier
    rolls_str = " + ".join(f"`{r}`" for r in rolls)
    mod_str = f" + {modifier}" if modifier > 0 else (f" - {abs(modifier)}" if modifier < 0 else "")
    await update.message.reply_text(
        f"🎲 *Dice Roller*\n{LINE}\n🎯 *Roll:* `{num_dice}d{die_sides}{'+' if modifier>0 else ''}{modifier if modifier else ''}`\n"
        f"🎲 *Dice:* {rolls_str}\n{mod_str}\n"
        f"🏆 *Total:* `{total}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎲 Roll Again", callback_data=f"roll_{expr}")]]),
    )

# ── RANDOM QUOTE ──
async def cmd_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    try:
        r = requests.get("https://api.quotable.io/random", timeout=8)
        if r.status_code == 200:
            d = r.json()
            quote = d.get("content","")
            author = d.get("author","Unknown")
            tags = ", ".join(d.get("tags",[]))
            text = f"💬 *Daily Quote*\n{LINE}\n\n_{quote}_\n\n— *{author}*\n\n🏷️ `{tags}`"
        else:
            text = f"{CROSS} Could not fetch quote. Try again!"
    except Exception:
        text = f"{CROSS} Quote service unavailable."
    track_tool_usage("quote")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 Another Quote", callback_data="quote_refresh")],[InlineKeyboardButton("« Menu", callback_data="main_menu")]]))

# ── RANDOM MEME ──
async def cmd_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=10)
        if r.status_code == 200:
            d = r.json()
            url = d.get("url","")
            title = d.get("title","")
            sub = d.get("subreddit","")
            ups = d.get("ups",0)
            track_tool_usage("meme")
            await update.message.reply_photo(
                photo=url,
                caption=f"😂 *{title}*\n📌 r/{sub} • 👍 {ups}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("😂 Another Meme", callback_data="meme_refresh")],[InlineKeyboardButton("« Menu", callback_data="main_menu")]]),
            )
            return
    except Exception:
        pass
    await update.message.reply_text(f"{CROSS} Could not fetch meme. Try again!", parse_mode=ParseMode.MARKDOWN)

# ── RANDOM ADVICE ──
async def cmd_advice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    try:
        r = requests.get("https://api.adviceslip.com/advice", timeout=8)
        if r.status_code == 200:
            slip = r.json().get("slip",{})
            advice = slip.get("advice","")
            slip_id = slip.get("id","")
            text = f"💡 *Life Advice #{slip_id}*\n{LINE}\n\n_{advice}_\n\n{LINE}\n_Use /advice again for more!_"
        else:
            text = f"{CROSS} Could not fetch advice."
    except Exception:
        text = f"{CROSS} Advice service unavailable."
    track_tool_usage("advice")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💡 More Advice", callback_data="advice_refresh")],[InlineKeyboardButton("« Menu", callback_data="main_menu")]]))

# ── COUNTRY INFO ──
async def cmd_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/country <name>`\nExample: `/country Japan`", parse_mode=ParseMode.MARKDOWN)
        return
    query = " ".join(context.args)
    msg = await update.message.reply_text(f"🌍 _Looking up `{query}`…_", parse_mode=ParseMode.MARKDOWN)
    try:
        r = requests.get(f"https://restcountries.com/v3.1/name/{urllib.parse.quote(query)}", timeout=10)
        if r.status_code != 200:
            await msg.edit_text(f"❌ Country `{query}` not found.", parse_mode=ParseMode.MARKDOWN)
            return
        c = r.json()[0]
        name = c.get("name",{}).get("common","N/A")
        official = c.get("name",{}).get("official","")
        capital = ", ".join(c.get("capital",["N/A"]))
        pop = c.get("population",0)
        area = c.get("area",0)
        region = c.get("region","")
        subregion = c.get("subregion","")
        flag = c.get("flag","")
        currencies = ", ".join([f"{v.get('name','')} ({k})" for k,v in c.get("currencies",{}).items()])
        languages = ", ".join(c.get("languages",{}).values())
        timezones = ", ".join(c.get("timezones",[])[:3])
        calling = "+"+",+".join(c.get("idd",{}).get("suffixes",[]) or []) if c.get("idd",{}).get("root") else "N/A"
        root = c.get("idd",{}).get("root","")
        drive_side = c.get("car",{}).get("side","")
        db_user = get_user(user.id)
        track_tool_usage("country")
        await msg.edit_text(
            f"╔══════════════════════════════╗\n║    🌍 COUNTRY INFORMATION    ║\n╚══════════════════════════════╝\n\n"
            f"{flag} *{name}*\n📋 _{official}_\n{LINE}\n"
            f"🏙️ *Capital:* `{capital}`\n"
            f"🌐 *Region:* `{region} — {subregion}`\n"
            f"👥 *Population:* `{pop:,}`\n"
            f"📐 *Area:* `{area:,.0f} km²`\n"
            f"💰 *Currency:* `{currencies[:100]}`\n"
            f"🗣️ *Languages:* `{languages[:100]}`\n"
            f"📞 *Calling Code:* `{root}{calling[:20]}`\n"
            f"🚗 *Drives on:* `{drive_side}`\n"
            f"🕐 *Timezones:* `{timezones}`\n"
            f"{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ── EARTHQUAKE ──
async def cmd_earthquake(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    msg = await update.message.reply_text("🌋 _Fetching latest earthquakes from USGS…_", parse_mode=ParseMode.MARKDOWN)
    try:
        r = requests.get(
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson",
            timeout=12,
        )
        if r.status_code != 200:
            await msg.edit_text("❌ USGS API unavailable.", parse_mode=ParseMode.MARKDOWN)
            return
        features = r.json().get("features",[])[:8]
        db_user = get_user(user.id)
        if not features:
            r2 = requests.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson", timeout=12)
            features = r2.json().get("features",[])[:8]
        lines = []
        for f in features:
            props = f.get("properties",{})
            mag = props.get("mag",0)
            place = props.get("place","Unknown")
            time_ms = props.get("time",0)
            from datetime import datetime as _dt
            time_str = _dt.utcfromtimestamp(time_ms/1000).strftime("%d %b %H:%M UTC") if time_ms else "N/A"
            mag_icon = "🔴" if mag >= 6 else ("🟠" if mag >= 5 else "🟡")
            lines.append(f"{mag_icon} *M{mag:.1f}* — {place}\n   🕐 `{time_str}`")
        track_tool_usage("earthquake")
        await msg.edit_text(
            f"╔══════════════════════════════╗\n║    🌋 EARTHQUAKE MONITOR     ║\n╚══════════════════════════════╝\n\n"
            f"📡 *Recent Significant Earthquakes (USGS)*\n{LINE}\n\n"
            + "\n\n".join(lines) +
            f"\n\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ── REDDIT ──
async def cmd_reddit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/reddit <subreddit>`\nExample: `/reddit worldnews`", parse_mode=ParseMode.MARKDOWN)
        return
    sub = context.args[0].strip().lstrip("r/")
    msg = await update.message.reply_text(f"📱 _Fetching r/{sub}…_", parse_mode=ParseMode.MARKDOWN)
    try:
        r = requests.get(
            f"https://www.reddit.com/r/{sub}/hot.json?limit=8",
            headers={"User-Agent":"TelegramBot/1.0"},
            timeout=12,
        )
        if r.status_code != 200:
            await msg.edit_text(f"❌ r/{sub} not found or private.", parse_mode=ParseMode.MARKDOWN)
            return
        posts = r.json().get("data",{}).get("children",[])
        if not posts:
            await msg.edit_text(f"❌ No posts found in r/{sub}.", parse_mode=ParseMode.MARKDOWN)
            return
        lines = []
        for i, p in enumerate(posts[:7], 1):
            d = p.get("data",{})
            title = d.get("title","")[:80]
            score = d.get("score",0)
            comments = d.get("num_comments",0)
            flair = d.get("link_flair_text","") or ""
            flair_tag = f" [{flair}]" if flair else ""
            lines.append(f"*{i}.* {flair_tag} {title}\n   👍 `{score:,}` • 💬 `{comments:,}`")
        db_user = get_user(user.id)
        track_tool_usage("reddit")
        await msg.edit_text(
            f"╔══════════════════════════════╗\n║    📱 REDDIT HOT POSTS       ║\n╚══════════════════════════════╝\n\n"
            f"🔥 *r/{sub} — Top Right Now*\n{LINE}\n\n"
            + "\n\n".join(lines) +
            f"\n\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ── COVID STATS ──
async def cmd_covid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    country = " ".join(context.args) if context.args else "world"
    msg = await update.message.reply_text(f"🦠 _Fetching COVID stats for `{country}`…_", parse_mode=ParseMode.MARKDOWN)
    try:
        if country.lower() in ("world","global","worldwide"):
            r = requests.get("https://disease.sh/v3/covid-19/all", timeout=10)
            label = "🌍 Global"
        else:
            r = requests.get(f"https://disease.sh/v3/covid-19/countries/{urllib.parse.quote(country)}", timeout=10)
            label = f"🏳️ {country.title()}"
        if r.status_code != 200:
            await msg.edit_text(f"❌ Country `{country}` not found.", parse_mode=ParseMode.MARKDOWN)
            return
        d = r.json()
        db_user = get_user(user.id)
        track_tool_usage("covid")
        await msg.edit_text(
            f"╔══════════════════════════════╗\n║     🦠 COVID-19 STATS        ║\n╚══════════════════════════════╝\n\n"
            f"{label}\n{LINE}\n"
            f"😷 *Total Cases:* `{d.get('cases',0):,}`\n"
            f"🟢 *Recovered:* `{d.get('recovered',0):,}`\n"
            f"💀 *Deaths:* `{d.get('deaths',0):,}`\n"
            f"🔴 *Active:* `{d.get('active',0):,}`\n"
            f"🏥 *Critical:* `{d.get('critical',0):,}`\n"
            f"🧪 *Tests:* `{d.get('tests',0):,}`\n"
            f"{LINE}\n"
            f"📅 *Today Cases:* `{d.get('todayCases',0):,}`\n"
            f"📅 *Today Deaths:* `{d.get('todayDeaths',0):,}`\n"
            f"{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ── DNS CHECK ──
async def cmd_dnscheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/dnscheck <domain>`\nExample: `/dnscheck google.com`", parse_mode=ParseMode.MARKDOWN)
        return
    domain = context.args[0].strip().lower().replace("https://","").replace("http://","").split("/")[0]
    msg = await update.message.reply_text(f"🔍 _Checking DNS for `{domain}`…_", parse_mode=ParseMode.MARKDOWN)
    record_types = ["A","AAAA","MX","NS","TXT","CNAME","SOA"]
    results = {}
    for rtype in record_types:
        try:
            r = requests.get(
                f"https://dns.google/resolve?name={domain}&type={rtype}",
                timeout=8,
            )
            if r.status_code == 200:
                ans = r.json().get("Answer",[])
                if ans:
                    results[rtype] = [a.get("data","") for a in ans[:3]]
        except Exception:
            pass
    db_user = get_user(user.id)
    track_tool_usage("dnscheck")
    if not results:
        await msg.edit_text(f"❌ No DNS records found for `{domain}`.", parse_mode=ParseMode.MARKDOWN)
        return
    lines = [f"╔══════════════════════════════╗\n║     🔍 DNS LOOKUP            ║\n╚══════════════════════════════╝\n\n🌐 *Domain:* `{domain}`\n{LINE}\n"]
    for rtype, vals in results.items():
        for v in vals:
            lines.append(f"*{rtype}:* `{v[:80]}`\n")
    lines.append(f"\n{LINE}\n💰 Credits Left: `{db_user['credits']}`")
    await msg.edit_text("".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

# ── SONG LYRICS ──
async def cmd_lyrics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(f"🎵 *Lyrics Lookup*\nUsage: `/lyrics <artist> - <song>`\nExample: `/lyrics Eminem - Lose Yourself`", parse_mode=ParseMode.MARKDOWN)
        return
    full_query = " ".join(context.args)
    if " - " in full_query:
        parts = full_query.split(" - ", 1)
        artist, title = parts[0].strip(), parts[1].strip()
    else:
        artist, title = context.args[0], " ".join(context.args[1:])
    msg = await update.message.reply_text(f"🎵 _Searching lyrics…_", parse_mode=ParseMode.MARKDOWN)
    try:
        r = requests.get(
            f"https://api.lyrics.ovh/v1/{urllib.parse.quote(artist)}/{urllib.parse.quote(title)}",
            timeout=12,
        )
        db_user = get_user(user.id)
        if r.status_code == 200:
            lyrics = r.json().get("lyrics","")
            if lyrics:
                track_tool_usage("lyrics")
                preview = lyrics[:1200].strip()
                truncated = len(lyrics) > 1200
                await msg.edit_text(
                    f"🎵 *{title}* — *{artist}*\n{LINE}\n\n"
                    f"{preview}"
                    + ("\n\n_...lyrics truncated (too long)_" if truncated else "") +
                    f"\n\n{LINE}\n💰 Credits Left: `{db_user['credits']}`",
                    parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
                )
                return
        await msg.edit_text(f"❌ Lyrics not found for *{title}* by *{artist}*.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ── GITHUB PROFILE ──
async def cmd_github(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/github <username>`\nExample: `/github torvalds`", parse_mode=ParseMode.MARKDOWN)
        return
    username = context.args[0].strip()
    msg = await update.message.reply_text(f"🐙 _Fetching GitHub profile for `{username}`…_", parse_mode=ParseMode.MARKDOWN)
    try:
        r = requests.get(f"https://api.github.com/users/{username}", headers={"Accept":"application/vnd.github.v3+json"}, timeout=10)
        db_user = get_user(user.id)
        if r.status_code == 404:
            await msg.edit_text(f"❌ GitHub user `{username}` not found.", parse_mode=ParseMode.MARKDOWN)
            return
        if r.status_code != 200:
            await msg.edit_text(f"❌ GitHub API error (HTTP {r.status_code}).", parse_mode=ParseMode.MARKDOWN)
            return
        d = r.json()
        name = d.get("name") or username
        bio = d.get("bio","") or "No bio"
        company = d.get("company","") or "N/A"
        location = d.get("location","") or "N/A"
        blog = d.get("blog","") or "N/A"
        repos = d.get("public_repos",0)
        followers = d.get("followers",0)
        following = d.get("following",0)
        gists = d.get("public_gists",0)
        joined = d.get("created_at","")[:10]
        account_type = d.get("type","User")
        track_tool_usage("github")
        await msg.edit_text(
            f"╔══════════════════════════════╗\n║    🐙 GITHUB PROFILE         ║\n╚══════════════════════════════╝\n\n"
            f"👤 *{name}* (@{username})\n"
            f"🏷️ _{bio[:200]}_\n{LINE}\n"
            f"🏢 *Company:* `{company}`\n"
            f"📍 *Location:* `{location}`\n"
            f"🔗 *Blog:* `{blog[:80]}`\n"
            f"📦 *Repos:* `{repos}`\n"
            f"👥 *Followers:* `{followers:,}` | *Following:* `{following:,}`\n"
            f"📝 *Public Gists:* `{gists}`\n"
            f"📅 *Joined:* `{joined}`\n"
            f"🔑 *Account Type:* `{account_type}`\n"
            f"{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ── NPM PACKAGE ──
async def cmd_npm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/npm <package>`\nExample: `/npm express`", parse_mode=ParseMode.MARKDOWN)
        return
    pkg = context.args[0].strip().lower()
    msg = await update.message.reply_text(f"📦 _Looking up npm package `{pkg}`…_", parse_mode=ParseMode.MARKDOWN)
    try:
        r = requests.get(f"https://registry.npmjs.org/{urllib.parse.quote(pkg)}", timeout=10)
        db_user = get_user(user.id)
        if r.status_code == 404:
            await msg.edit_text(f"❌ Package `{pkg}` not found on npm.", parse_mode=ParseMode.MARKDOWN)
            return
        d = r.json()
        name = d.get("name","")
        desc = d.get("description","") or "No description"
        latest_ver = d.get("dist-tags",{}).get("latest","")
        homepage = d.get("homepage","") or "N/A"
        license_ = d.get("license","") or "N/A"
        keywords = ", ".join((d.get("keywords") or [])[:8])
        maintainers = ", ".join([m.get("name","") for m in (d.get("maintainers") or [])[:5]])
        versions_count = len(d.get("versions",{}))
        track_tool_usage("npm")
        await msg.edit_text(
            f"╔══════════════════════════════╗\n║    📦 NPM PACKAGE INFO       ║\n╚══════════════════════════════╝\n\n"
            f"📦 *{name}*\n_{desc[:200]}_\n{LINE}\n"
            f"🔖 *Latest:* `{latest_ver}`\n"
            f"📚 *Versions:* `{versions_count}`\n"
            f"📜 *License:* `{license_}`\n"
            f"🏠 *Homepage:* `{homepage[:80]}`\n"
            f"🏷️ *Keywords:* `{keywords[:150]}`\n"
            f"👥 *Maintainers:* `{maintainers[:150]}`\n"
            f"🔗 `npmjs.com/package/{name}`\n"
            f"{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ── PYPI PACKAGE ──
async def cmd_pypi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/pypi <package>`\nExample: `/pypi requests`", parse_mode=ParseMode.MARKDOWN)
        return
    pkg = context.args[0].strip().lower()
    msg = await update.message.reply_text(f"🐍 _Looking up PyPI package `{pkg}`…_", parse_mode=ParseMode.MARKDOWN)
    try:
        r = requests.get(f"https://pypi.org/pypi/{urllib.parse.quote(pkg)}/json", timeout=10)
        db_user = get_user(user.id)
        if r.status_code == 404:
            await msg.edit_text(f"❌ Package `{pkg}` not found on PyPI.", parse_mode=ParseMode.MARKDOWN)
            return
        info = r.json().get("info",{})
        name = info.get("name","")
        version = info.get("version","")
        summary = info.get("summary","") or "No summary"
        author = info.get("author","") or "N/A"
        license_ = info.get("license","") or "N/A"
        home = info.get("home_page","") or "N/A"
        requires_python = info.get("requires_python","") or "N/A"
        classifiers = [c for c in (info.get("classifiers") or []) if "Programming Language" not in c][:3]
        keywords = info.get("keywords","") or "N/A"
        track_tool_usage("pypi")
        await msg.edit_text(
            f"╔══════════════════════════════╗\n║    🐍 PYPI PACKAGE INFO      ║\n╚══════════════════════════════╝\n\n"
            f"📦 *{name}* v{version}\n_{summary[:200]}_\n{LINE}\n"
            f"👤 *Author:* `{author[:60]}`\n"
            f"📜 *License:* `{license_[:60]}`\n"
            f"🐍 *Python:* `{requires_python}`\n"
            f"🏠 *Homepage:* `{home[:80]}`\n"
            f"🏷️ *Keywords:* `{keywords[:150]}`\n"
            f"🔗 `pypi.org/project/{name}`\n"
            f"{LINE}\n💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ── MOVIE INFO ──
async def cmd_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"🎬 *Movie Lookup*\nUsage: `/movie <title>`\nExample: `/movie Inception`", parse_mode=ParseMode.MARKDOWN)
        return
    title = " ".join(context.args)
    msg = await update.message.reply_text(f"🎬 _Searching for `{title}`…_", parse_mode=ParseMode.MARKDOWN)
    try:
        r = requests.get(
            "https://www.omdbapi.com/",
            params={"t": title, "apikey": "trilogy", "plot": "short"},
            timeout=10,
        )
        db_user = get_user(user.id)
        d = r.json() if r.status_code == 200 else {}
        if d.get("Response") == "True":
            track_tool_usage("movie")
            ratings_lines = "\n".join([f"   ⭐ *{rv.get('Source','?')}:* `{rv.get('Value','N/A')}`" for rv in d.get("Ratings",[])])
            await msg.edit_text(
                f"╔══════════════════════════════╗\n║     🎬 MOVIE INFO            ║\n╚══════════════════════════════╝\n\n"
                f"🎬 *{d.get('Title','')}* ({d.get('Year','')})\n"
                f"🎭 _{d.get('Genre','')}_\n{LINE}\n"
                f"🎯 *Director:* `{d.get('Director','N/A')}`\n"
                f"🌟 *Actors:* `{d.get('Actors','N/A')[:100]}`\n"
                f"🌐 *Language:* `{d.get('Language','N/A')}`\n"
                f"🏆 *Awards:* `{d.get('Awards','N/A')[:80]}`\n"
                f"⏱️ *Runtime:* `{d.get('Runtime','N/A')}`\n"
                f"🔞 *Rated:* `{d.get('Rated','N/A')}`\n"
                f"📝 *Plot:* _{d.get('Plot','N/A')[:300]}_\n"
                f"{LINE}\n{ratings_lines}\n"
                f"🎰 *Metascore:* `{d.get('Metascore','N/A')}`\n"
                f"{LINE}\n💰 Credits Left: `{db_user['credits']}`",
                parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
            )
        else:
            r2 = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}_film", timeout=10)
            if r2.status_code == 200:
                w = r2.json()
                extract = w.get("extract","")[:500]
                await msg.edit_text(f"🎬 *{title}*\n{LINE}\n_{extract}_\n{LINE}\n💰 Credits Left: `{db_user['credits']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())
            else:
                await msg.edit_text(f"❌ Movie `{title}` not found.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ── HTTP HEADERS CHECK ──
async def cmd_headers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/headers <url>`\nExample: `/headers https://google.com`", parse_mode=ParseMode.MARKDOWN)
        return
    url = context.args[0].strip()
    if not url.startswith(("http://","https://")):
        url = "https://" + url
    msg = await update.message.reply_text(f"🌐 _Fetching headers…_", parse_mode=ParseMode.MARKDOWN)
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        db_user = get_user(user.id)
        important_headers = ["content-type","server","x-powered-by","x-frame-options","strict-transport-security","content-security-policy","cache-control","x-content-type-options","access-control-allow-origin","cf-ray","set-cookie"]
        lines = [f"╔══════════════════════════════╗\n║    🌐 HTTP HEADERS           ║\n╚══════════════════════════════╝\n\n🔗 `{url[:80]}`\n📡 *Status:* `{r.status_code} {r.reason}`\n{LINE}\n"]
        for h in important_headers:
            v = r.headers.get(h,"")
            if v:
                lines.append(f"*{h}:*\n`{v[:100]}`\n")
        if len(lines) < 3:
            for k,v in list(r.headers.items())[:12]:
                lines.append(f"*{k}:* `{v[:80]}`\n")
        lines.append(f"\n{LINE}\n💰 Credits Left: `{db_user['credits']}`")
        track_tool_usage("headers")
        await msg.edit_text("".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════
# ⚡ BATCH 3 — PRODUCTIVITY / NOTES / REMINDERS / TODO
# ═══════════════════════════════════════════════════════

def get_user_notes(user_id: int) -> dict:
    data = load_data()
    return data.get("notes",{}).get(str(user_id),{})

def save_user_note(user_id: int, key: str, text: str):
    data = load_data()
    data.setdefault("notes",{}). setdefault(str(user_id),{})[key] = text
    save_data(data)

def delete_user_note(user_id: int, key: str):
    data = load_data()
    data.setdefault("notes",{}).setdefault(str(user_id),{}).pop(key, None)
    save_data(data)

async def cmd_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    sub = context.args[0].lower() if context.args else "list"
    notes = get_user_notes(user.id)

    if sub == "add" and len(context.args) >= 3:
        note_key = context.args[1]
        note_text = " ".join(context.args[2:])
        save_user_note(user.id, note_key, note_text)
        await update.message.reply_text(f"✅ Note `{note_key}` saved!\n\n📝 _{note_text[:300]}_", parse_mode=ParseMode.MARKDOWN)
        return
    elif sub == "delete" and len(context.args) >= 2:
        note_key = context.args[1]
        delete_user_note(user.id, note_key)
        await update.message.reply_text(f"🗑️ Note `{note_key}` deleted.", parse_mode=ParseMode.MARKDOWN)
        return
    elif sub == "view" and len(context.args) >= 2:
        note_key = context.args[1]
        text = notes.get(note_key)
        if text:
            await update.message.reply_text(f"📝 *Note: `{note_key}`*\n{LINE}\n{text}", parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())
        else:
            await update.message.reply_text(f"❌ Note `{note_key}` not found.", parse_mode=ParseMode.MARKDOWN)
        return

    if not notes:
        text = f"📓 *Your Notes*\n{LINE}\nNo notes yet!\n\nCreate one:\n`/notes add <key> <text>`\nExample: `/notes add shopping Buy groceries today`"
    else:
        lines = [f"📓 *Your Notes* ({len(notes)})\n{LINE}\n"]
        for i,(k,v) in enumerate(notes.items(),1):
            lines.append(f"*{i}. `{k}`* — _{v[:60]}_\n")
        lines.append(f"\n{LINE}\n`/notes view <key>` • `/notes delete <key>`")
        text = "".join(lines)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

def get_user_todos(user_id: int) -> list:
    data = load_data()
    return data.get("todos",{}).get(str(user_id),[])

def save_user_todos(user_id: int, todos: list):
    data = load_data()
    data.setdefault("todos",{})[str(user_id)] = todos
    save_data(data)

async def cmd_todo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    sub = context.args[0].lower() if context.args else "list"
    todos = get_user_todos(user.id)

    if sub == "add" and len(context.args) >= 2:
        text_in = " ".join(context.args[1:])
        todos.append({"text":text_in,"done":False})
        save_user_todos(user.id, todos)
        await update.message.reply_text(f"✅ Added: _{text_in[:200]}_", parse_mode=ParseMode.MARKDOWN)
        return
    elif sub == "done" and len(context.args) >= 2:
        try:
            idx = int(context.args[1]) - 1
            if 0 <= idx < len(todos):
                todos[idx]["done"] = True
                save_user_todos(user.id, todos)
                await update.message.reply_text(f"✅ Marked done: _{todos[idx]['text'][:100]}_", parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text("❌ Invalid task number.", parse_mode=ParseMode.MARKDOWN)
        except ValueError:
            await update.message.reply_text("❌ Use a number: `/todo done 1`", parse_mode=ParseMode.MARKDOWN)
        return
    elif sub == "delete" and len(context.args) >= 2:
        try:
            idx = int(context.args[1]) - 1
            if 0 <= idx < len(todos):
                removed = todos.pop(idx)
                save_user_todos(user.id, todos)
                await update.message.reply_text(f"🗑️ Deleted: _{removed['text'][:100]}_", parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text("❌ Invalid task number.", parse_mode=ParseMode.MARKDOWN)
        except ValueError:
            await update.message.reply_text("❌ Use a number: `/todo delete 1`", parse_mode=ParseMode.MARKDOWN)
        return
    elif sub == "clear":
        save_user_todos(user.id, [])
        await update.message.reply_text("🗑️ All tasks cleared!", parse_mode=ParseMode.MARKDOWN)
        return

    if not todos:
        text = f"📋 *To-Do List*\n{LINE}\nNo tasks yet!\n\nAdd one: `/todo add Buy groceries`"
    else:
        lines = [f"📋 *To-Do List* ({len(todos)} tasks)\n{LINE}\n"]
        for i, t in enumerate(todos, 1):
            icon = "✅" if t["done"] else "⬜"
            strikethrough = "~" if t["done"] else ""
            lines.append(f"{i}. {icon} {strikethrough}{t['text'][:80]}{strikethrough}\n")
        pending = sum(1 for t in todos if not t["done"])
        lines.append(f"\n{LINE}\n⬜ Pending: `{pending}` | ✅ Done: `{len(todos)-pending}`\n")
        lines.append("`/todo done <#>` • `/todo delete <#>` • `/todo clear`")
        text = "".join(lines)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

async def cmd_remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if len(context.args) < 2:
        await update.message.reply_text(
            f"⏰ *Reminder*\n{LINE}\nUsage: `/remind <time> <message>`\n\n"
            f"Time formats:\n`/remind 5m Buy milk`\n`/remind 1h Call doctor`\n`/remind 30s Test reminder`\n`/remind 2h30m Meeting`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    import re as _re
    time_str = context.args[0].lower()
    reminder_text = " ".join(context.args[1:])
    total_seconds = 0
    matches = _re.findall(r"(\d+)(h|m|s)", time_str)
    for val, unit in matches:
        if unit == "h": total_seconds += int(val)*3600
        elif unit == "m": total_seconds += int(val)*60
        elif unit == "s": total_seconds += int(val)
    if total_seconds == 0:
        await update.message.reply_text("❌ Invalid time format. Use `5m`, `1h`, `2h30m` etc.", parse_mode=ParseMode.MARKDOWN)
        return
    if total_seconds > 86400:
        await update.message.reply_text("❌ Maximum reminder time is 24 hours.", parse_mode=ParseMode.MARKDOWN)
        return
    chat_id = update.effective_chat.id
    uid = user.id

    async def send_reminder(ctx):
        try:
            await ctx.bot.send_message(
                chat_id,
                f"⏰ *Reminder!*\n{LINE}\n_{reminder_text}_\n\n_Set {time_str} ago_",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    context.application.job_queue.run_once(send_reminder, when=total_seconds)
    mins = total_seconds // 60
    secs = total_seconds % 60
    human_time = (f"{mins//60}h " if mins >= 60 else "") + (f"{mins%60}m " if mins else "") + (f"{secs}s" if secs else "")
    await update.message.reply_text(
        f"✅ *Reminder Set!*\n{LINE}\n⏰ In: `{human_time.strip()}`\n📝 _{reminder_text[:200]}_\n\n_I'll ping you when the time comes!_",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
    )

async def cmd_pastebin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if not context.args:
        await update.message.reply_text(f"{WARN} Usage: `/pastebin <text>`\nExample: `/pastebin Hello World this is my text`", parse_mode=ParseMode.MARKDOWN)
        return
    text_in = " ".join(context.args)
    msg = await update.message.reply_text("📋 _Uploading to paste service…_", parse_mode=ParseMode.MARKDOWN)
    try:
        r = requests.post(
            "https://paste.rs/",
            data=text_in.encode("utf-8"),
            headers={"Content-Type":"text/plain"},
            timeout=15,
        )
        db_user = get_user(user.id)
        if r.status_code in (200, 201):
            url = r.text.strip()
            track_tool_usage("pastebin")
            await msg.edit_text(
                f"╔══════════════════════════════╗\n║     📋 PASTE UPLOADED        ║\n╚══════════════════════════════╝\n\n"
                f"🔗 *Your Paste URL:*\n`{url}`\n\n"
                f"📝 *Content preview:*\n_{text_in[:200]}_\n"
                f"{LINE}\n💰 Credits Left: `{db_user['credits']}`",
                parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
            )
        else:
            await msg.edit_text(f"❌ Paste failed (HTTP {r.status_code}). Try again.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

async def cmd_loan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 3:
        await update.message.reply_text(f"🏦 *Loan Calculator*\nUsage: `/loan <amount> <annual_rate%> <years>`\nExample: `/loan 100000 5.5 30`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        P = float(context.args[0])
        annual_rate = float(context.args[1])
        years = float(context.args[2])
    except ValueError:
        await update.message.reply_text("❌ All values must be numbers.", parse_mode=ParseMode.MARKDOWN)
        return
    r = annual_rate / 100 / 12
    n = int(years * 12)
    if r == 0:
        monthly = P / n
    else:
        monthly = P * (r * (1+r)**n) / ((1+r)**n - 1)
    total_paid = monthly * n
    total_interest = total_paid - P
    db_user = get_user(user.id)
    track_tool_usage("loan")
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║    🏦 LOAN CALCULATOR        ║\n╚══════════════════════════════╝\n\n"
        f"💵 *Principal:* `{P:,.2f}`\n"
        f"📈 *Annual Rate:* `{annual_rate}%`\n"
        f"📅 *Term:* `{years} years ({n} payments)`\n"
        f"{LINE}\n"
        f"💳 *Monthly Payment:* `{monthly:,.2f}`\n"
        f"💰 *Total Paid:* `{total_paid:,.2f}`\n"
        f"🏦 *Total Interest:* `{total_interest:,.2f}`\n"
        f"💸 *Interest %:* `{(total_interest/P*100):.1f}%`\n"
        f"{LINE}\n💰 Credits Left: `{db_user['credits']}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard(),
    )

async def cmd_compound(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    if not await check_credits_and_use(update, user.id):
        return
    if len(context.args) < 3:
        await update.message.reply_text(f"📈 *Compound Interest*\nUsage: `/compound <principal> <rate%> <years>`\nExample: `/compound 10000 8 10`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        P = float(context.args[0])
        rate = float(context.args[1]) / 100
        years = int(context.args[2])
    except ValueError:
        await update.message.reply_text("❌ All values must be numbers.", parse_mode=ParseMode.MARKDOWN)
        return
    lines = [f"╔══════════════════════════════╗\n║   📈 COMPOUND INTEREST       ║\n╚══════════════════════════════╝\n\n"
             f"💵 *Principal:* `{P:,.2f}`\n"
             f"📈 *Rate:* `{rate*100:.2f}%` per year\n"
             f"📅 *Period:* `{years} years`\n{LINE}\n"]
    prev = P
    for y in range(1, min(years+1, 11)):
        val = P * (1+rate)**y
        gained = val - prev
        lines.append(f"Year {y:>2}: `{val:>12,.2f}` (+`{gained:,.2f}`)\n")
        prev = val
    if years > 10:
        final = P * (1+rate)**years
        lines.append(f"...\nYear {years}: `{final:>12,.2f}`\n")
    final = P * (1+rate)**years
    lines.append(f"\n{LINE}\n💎 *Final Value:* `{final:,.2f}`\n📊 *Total Gain:* `{final-P:,.2f}` (`{((final-P)/P*100):.1f}%`)\n")
    db_user = get_user(user.id)
    track_tool_usage("compound")
    lines.append(f"{LINE}\n💰 Credits Left: `{db_user['credits']}`")
    await update.message.reply_text("".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=back_main_keyboard())

# ═══════════════════════════════════════════════════════
# ⚡ BATCH 4 — DEVELOPER POWER TOOLS + PANEL
# ═══════════════════════════════════════════════════════

# ── BROADCAST ──
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text("❌ Developer only.", parse_mode=ParseMode.MARKDOWN)
        return
    if not context.args:
        await update.message.reply_text(f"📢 Usage: `/broadcast <message>`", parse_mode=ParseMode.MARKDOWN)
        return
    msg_text = " ".join(context.args)
    data = load_data()
    users = data.get("users",{})
    sent = 0
    failed = 0
    status_msg = await update.message.reply_text(f"📢 _Broadcasting to {len(users)} users…_", parse_mode=ParseMode.MARKDOWN)
    for uid_str in users:
        try:
            await context.bot.send_message(
                int(uid_str),
                f"📢 *Announcement from {BOT_NAME}*\n{LINE}\n\n{msg_text}",
                parse_mode=ParseMode.MARKDOWN,
            )
            sent += 1
        except Exception:
            failed += 1
    await status_msg.edit_text(
        f"📢 *Broadcast Complete*\n{LINE}\n✅ Sent: `{sent}`\n❌ Failed: `{failed}`\n👥 Total: `{len(users)}`",
        parse_mode=ParseMode.MARKDOWN,
    )

# ── BOT STATS ──
async def cmd_botstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text("❌ Developer only.", parse_mode=ParseMode.MARKDOWN)
        return
    data = load_data()
    users = data.get("users",{})
    tool_usage = data.get("tool_usage",{})
    total_users = len(users)
    premium_users = sum(1 for u in users.values() if u.get("premium"))
    banned_users = sum(1 for u in users.values() if u.get("banned"))
    total_tool_uses = sum(tool_usage.values()) if tool_usage else 0
    top_tools = sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)[:5]
    total_credits_in_system = sum(u.get("credits",0) for u in users.values())
    subscribers = len(data.get("subscribers",{}))
    notes_count = sum(len(v) for v in data.get("notes",{}).values())
    todos_count = sum(len(v) for v in data.get("todos",{}).values())
    top_tools_str = "\n".join([f"   `{k}`: {v:,}" for k,v in top_tools]) or "   _None yet_"
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║     📊 BOT STATISTICS        ║\n╚══════════════════════════════╝\n\n"
        f"👥 *Total Users:* `{total_users:,}`\n"
        f"💎 *Premium Users:* `{premium_users:,}`\n"
        f"🚫 *Banned Users:* `{banned_users:,}`\n"
        f"📡 *News Subscribers:* `{subscribers:,}`\n"
        f"📓 *Notes Stored:* `{notes_count:,}`\n"
        f"📋 *Todo Items:* `{todos_count:,}`\n"
        f"{LINE}\n"
        f"🔧 *Total Tool Uses:* `{total_tool_uses:,}`\n"
        f"💰 *Credits in System:* `{total_credits_in_system:,}`\n"
        f"{LINE}\n🏆 *Top 5 Tools:*\n{top_tools_str}",
        parse_mode=ParseMode.MARKDOWN,
    )

# ── MAINTENANCE MODE ──
def set_maintenance(enabled: bool):
    data = load_data()
    data["maintenance"] = enabled
    save_data(data)

def is_maintenance() -> bool:
    return load_data().get("maintenance", False)

async def cmd_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text("❌ Developer only.", parse_mode=ParseMode.MARKDOWN)
        return
    sub = context.args[0].lower() if context.args else "status"
    if sub == "on":
        set_maintenance(True)
        await update.message.reply_text("🔧 *Maintenance mode ENABLED.*\nAll users will see a maintenance message.", parse_mode=ParseMode.MARKDOWN)
    elif sub == "off":
        set_maintenance(False)
        await update.message.reply_text("✅ *Maintenance mode DISABLED.*\nBot is back online for all users.", parse_mode=ParseMode.MARKDOWN)
    else:
        status = "🔴 ON" if is_maintenance() else "🟢 OFF"
        await update.message.reply_text(f"🔧 *Maintenance Mode:* {status}\n\nUsage: `/maintenance on` or `/maintenance off`", parse_mode=ParseMode.MARKDOWN)

# ── TRANSFER CREDITS (DEV) ──
async def cmd_transfercredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text("❌ Developer only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            f"💸 *Transfer Credits*\nUsage: `/transfercredits <user_id> <amount>`\nExample: `/transfercredits 123456789 100`\n\n_Developer credits are unlimited — transfers cost nothing._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except ValueError as e:
        await update.message.reply_text(f"❌ Invalid input: `{e}`", parse_mode=ParseMode.MARKDOWN)
        return
    data = load_data()
    uid = str(target_id)
    if uid not in data.get("users",{}):
        await update.message.reply_text(f"❌ User `{target_id}` not found in database.", parse_mode=ParseMode.MARKDOWN)
        return
    old_credits = data["users"][uid].get("credits", 0)
    data["users"][uid]["credits"] = old_credits + amount
    save_data(data)
    target_user = data["users"][uid]
    username = target_user.get("username","unknown")
    new_credits = data["users"][uid]["credits"]
    try:
        await context.bot.send_message(
            target_id,
            f"🎁 *Credits Received!*\n{LINE}\n💰 You received `{amount} credits` from the Developer!\n💎 New Balance: `{new_credits} credits`\n\nEnjoy! 🚀",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass
    await update.message.reply_text(
        f"✅ *Credits Transferred!*\n{LINE}\n👤 *To:* `@{username}` (`{target_id}`)\n💸 *Amount:* `+{amount} credits`\n📊 *Before:* `{old_credits}` → *After:* `{new_credits}`",
        parse_mode=ParseMode.MARKDOWN,
    )

# ── GIVE PREMIUM (DEV - enhanced) ──
async def cmd_givepremium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text("❌ Developer only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text(
            f"💎 *Give Premium*\nUsage: `/givepremium <user_id> [days]`\nExample: `/givepremium 123456789 30`\n\nDefault: 30 days if not specified.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    try:
        target_id = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else 30
    except ValueError as e:
        await update.message.reply_text(f"❌ Invalid input: `{e}`", parse_mode=ParseMode.MARKDOWN)
        return
    data = load_data()
    uid = str(target_id)
    if uid not in data.get("users",{}):
        await update.message.reply_text(f"❌ User `{target_id}` not found.", parse_mode=ParseMode.MARKDOWN)
        return
    from datetime import timedelta
    expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    data["users"][uid]["premium"] = True
    data["users"][uid]["premium_expiry"] = expiry
    data["users"][uid]["credits"] = data["users"][uid].get("credits",0) + 100
    save_data(data)
    username = data["users"][uid].get("username","unknown")
    try:
        await context.bot.send_message(
            target_id,
            f"💎 *Congratulations! You've been upgraded to PREMIUM!*\n{LINE}\n"
            f"✨ Premium active for `{days} days`\n"
            f"📅 Expires: `{expiry}`\n"
            f"🎁 Bonus: `+100 credits` added!\n"
            f"🚀 Enjoy unlimited access to all features!\n\n"
            f"_Thank you for using {BOT_NAME}!_",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass
    await update.message.reply_text(
        f"✅ *Premium Granted!*\n{LINE}\n👤 *To:* `@{username}` (`{target_id}`)\n💎 *Duration:* `{days} days`\n📅 *Expires:* `{expiry}`\n🎁 *+100 credits* bonus sent!",
        parse_mode=ParseMode.MARKDOWN,
    )

# ── REVOKE USER (DEV ban/unban) ──
async def cmd_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text("❌ Developer only.", parse_mode=ParseMode.MARKDOWN)
        return
    if not context.args:
        await update.message.reply_text(f"🚫 Usage: `/banuser <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.", parse_mode=ParseMode.MARKDOWN)
        return
    data = load_data()
    uid = str(target_id)
    if uid not in data.get("users",{}):
        await update.message.reply_text(f"❌ User `{target_id}` not found.", parse_mode=ParseMode.MARKDOWN)
        return
    data["users"][uid]["banned"] = True
    save_data(data)
    await update.message.reply_text(f"🚫 User `{target_id}` has been *banned*.", parse_mode=ParseMode.MARKDOWN)

async def cmd_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text("❌ Developer only.", parse_mode=ParseMode.MARKDOWN)
        return
    if not context.args:
        await update.message.reply_text(f"✅ Usage: `/unbanuser <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.", parse_mode=ParseMode.MARKDOWN)
        return
    data = load_data()
    uid = str(target_id)
    if uid not in data.get("users",{}):
        await update.message.reply_text(f"❌ User `{target_id}` not found.", parse_mode=ParseMode.MARKDOWN)
        return
    data["users"][uid]["banned"] = False
    save_data(data)
    await update.message.reply_text(f"✅ User `{target_id}` has been *unbanned*.", parse_mode=ParseMode.MARKDOWN)

# ── ENHANCED DEV PANEL ──
async def cmd_devpanel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_developer(user.id, user.username or ""):
        await update.message.reply_text("❌ Developer only.", parse_mode=ParseMode.MARKDOWN)
        return
    data = load_data()
    users = data.get("users",{})
    premium_count = sum(1 for u in users.values() if u.get("premium"))
    banned_count = sum(1 for u in users.values() if u.get("banned"))
    sub_count = len(data.get("subscribers",{}))
    maintenance_status = "🔴 ON" if data.get("maintenance") else "🟢 OFF"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Bot Stats", callback_data="devpanel_stats"),
         InlineKeyboardButton("📢 Broadcast", callback_data="devpanel_broadcast")],
        [InlineKeyboardButton("🔧 Maintenance", callback_data="devpanel_maintenance"),
         InlineKeyboardButton("📋 List Codes", callback_data="devpanel_listcodes")],
        [InlineKeyboardButton("📝 View Feedback", callback_data="devpanel_feedback"),
         InlineKeyboardButton("📈 Analytics", callback_data="devpanel_analytics")],
        [InlineKeyboardButton("« Back", callback_data="main_menu")],
    ])
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║    👑 DEVELOPER PANEL        ║\n╚══════════════════════════════╝\n\n"
        f"*Welcome, Developer @{user.username or user.first_name}!*\n{LINE}\n"
        f"👥 *Total Users:* `{len(users):,}`\n"
        f"💎 *Premium:* `{premium_count}`\n"
        f"🚫 *Banned:* `{banned_count}`\n"
        f"📡 *Subscribers:* `{sub_count}`\n"
        f"🔧 *Maintenance:* {maintenance_status}\n"
        f"♾️ *Your Credits:* `Unlimited`\n"
        f"{LINE}\n"
        f"💸 `/transfercredits <id> <amount>` — Send credits\n"
        f"💎 `/givepremium <id> [days]` — Grant premium\n"
        f"🚫 `/banuser <id>` — Ban a user\n"
        f"✅ `/unbanuser <id>` — Unban a user\n"
        f"📢 `/broadcast <msg>` — Message all users\n"
        f"🔧 `/maintenance on/off` — Toggle maintenance",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb,
    )

# ── WORDSCRAMBLE GAME ──
SCRAMBLE_WORDS = [
    "python","telegram","bitcoin","elephant","journey","mystery","galaxy","thunder","volcano","phantom",
    "crystal","diamond","justice","warrior","kingdom","silence","sunrise","rainbow","freedom","victory",
    "quantum","phantom","eclipse","courage","balance","dolphin","ancient","library","miracle","passion",
    "explore","dynasty","climate","forever","harvest","monster","network","olympus","pioneer","quality",
    "resolve","science","triumph","uniform","vibrant","wisdom","xenon","yellow","zealous","ability",
]

async def cmd_scramble(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    word = _random.choice(SCRAMBLE_WORDS)
    scrambled = list(word)
    _random.shuffle(scrambled)
    scrambled_str = "".join(scrambled)
    context.user_data[f"scramble_{user.id}"] = word
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║     🔀 WORD SCRAMBLE         ║\n╚══════════════════════════════╝\n\n"
        f"🔀 *Unscramble this word:*\n\n`{scrambled_str.upper()}`\n\n"
        f"📏 *Letters:* `{len(word)}`\n{LINE}\n"
        f"💬 Reply with your answer!\n"
        f"💡 Use `/scramblehint` for a hint (costs 1 credit)\n"
        f"💰 *Win 3 credits* for a correct answer!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💡 Hint (-1 credit)", callback_data=f"scramble_hint_{word}")],
            [InlineKeyboardButton("⏭️ Skip", callback_data="scramble_skip")],
            [InlineKeyboardButton("« Menu", callback_data="main_menu")],
        ]),
    )

async def handle_scramble_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    correct_word = context.user_data.get(f"scramble_{user.id}")
    if not correct_word:
        return
    answer = (update.message.text or "").strip().lower()
    if answer == correct_word:
        context.user_data.pop(f"scramble_{user.id}", None)
        data = load_data()
        uid = str(user.id)
        if uid in data.get("users",{}):
            data["users"][uid]["credits"] = data["users"][uid].get("credits",0) + 3
            save_data(data)
        db_user = get_user(user.id)
        track_tool_usage("scramble")
        await update.message.reply_text(
            f"🎉 *Correct!* The word was `{correct_word}`!\n\n"
            f"🏆 *+3 credits* awarded!\n"
            f"💰 Balance: `{db_user['credits']}`\n\n"
            f"_Play again? /scramble_",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            f"❌ *Wrong!* Try again…\n\n💡 The word has *{len(correct_word)} letters*.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💡 Hint", callback_data=f"scramble_hint_{correct_word}")],
                [InlineKeyboardButton("⏭️ Skip", callback_data="scramble_skip")],
            ]),
        )

# ── HANGMAN GAME ──
HANGMAN_WORDS = [
    "algorithm","database","interface","protocol","software","hardware","bandwidth","firewall","encryption","debugging",
    "framework","repository","function","variable","constant","iteration","recursion","parameter","exception","compiler",
]
HANGMAN_STAGES = [
    "```\n  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```",
]

async def cmd_hangman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    word = _random.choice(HANGMAN_WORDS)
    context.user_data[f"hangman_{user.id}"] = {"word": word, "guessed": set(), "wrong": 0}
    display = " ".join("_" for _ in word)
    kb = _hangman_keyboard(set(), word)
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║       🪓 HANGMAN             ║\n╚══════════════════════════════╝\n\n"
        f"{HANGMAN_STAGES[0]}\n\n"
        f"📝 *Word:* `{display}`\n"
        f"📏 *Letters:* `{len(word)}`\n"
        f"❤️ *Lives:* `6/6`\n{LINE}\n_Pick a letter:_",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb,
    )

def _hangman_keyboard(guessed: set, word: str) -> InlineKeyboardMarkup:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    rows = []
    row = []
    for i, letter in enumerate(letters):
        used = letter.lower() in guessed
        btn_text = "✓" if (letter.lower() in guessed and letter.lower() in word) else ("✗" if letter.lower() in guessed else letter)
        row.append(InlineKeyboardButton(btn_text, callback_data="noop" if used else f"hangman_{letter.lower()}"))
        if (i+1) % 7 == 0:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("« Quit", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

# ── TIC TAC TOE ──
TTT_EMPTY = "⬜"
TTT_X = "❌"
TTT_O = "⭕"

def _ttt_check_winner(board: list) -> str:
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in wins:
        if board[a] == board[b] == board[c] and board[a] != TTT_EMPTY:
            return board[a]
    if TTT_EMPTY not in board:
        return "draw"
    return ""

def _ttt_bot_move(board: list) -> int:
    empty = [i for i,v in enumerate(board) if v == TTT_EMPTY]
    # Check if bot can win
    for i in empty:
        b = board.copy(); b[i] = TTT_O
        if _ttt_check_winner(b) == TTT_O: return i
    # Block player
    for i in empty:
        b = board.copy(); b[i] = TTT_X
        if _ttt_check_winner(b) == TTT_X: return i
    # Prefer center, corners, edges
    for pref in [4, 0, 2, 6, 8, 1, 3, 5, 7]:
        if pref in empty: return pref
    return empty[0]

def _ttt_keyboard(board: list, game_over: bool = False) -> InlineKeyboardMarkup:
    rows = []
    for row in range(3):
        r = []
        for col in range(3):
            i = row*3+col
            cell = board[i]
            r.append(InlineKeyboardButton(cell, callback_data="noop" if (cell != TTT_EMPTY or game_over) else f"ttt_{i}"))
        rows.append(r)
    if game_over:
        rows.append([InlineKeyboardButton("🔄 Play Again", callback_data="ttt_new"), InlineKeyboardButton("« Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

async def cmd_tictactoe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "")
    board = [TTT_EMPTY]*9
    context.user_data[f"ttt_{user.id}"] = board
    await update.message.reply_text(
        f"╔══════════════════════════════╗\n║    ❌ TIC TAC TOE ⭕         ║\n╚══════════════════════════════╝\n\n"
        f"You are ❌, Bot is ⭕\n_Your turn — pick a square:_",
        parse_mode=ParseMode.MARKDOWN, reply_markup=_ttt_keyboard(board),
    )

# ─────────────────────────── HTTP HEALTH SERVER ───────────────────────────
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.environ.get("PORT", 5000))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"Health server running on port {port}")

# ─────────────────────────── WORLD MONITOR ───────────────────────────
WORLD_NEWS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.cnn.com/rss/edition_world.rss",
    "https://feeds.reuters.com/reuters/worldNews",
    "https://www.aljazeera.com/xml/rss/all.xml",
]

def get_world_news(max_items: int = 8) -> list:
    """Fetch live world news from RSS feeds."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}
    for feed_url in WORLD_NEWS_FEEDS:
        try:
            r = requests.get(feed_url, timeout=10, headers=headers)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            items = []
            ns = {"media": "http://search.yahoo.com/mrss/"}
            for item in root.findall(".//item"):
                title_el = item.find("title")
                desc_el = item.find("description")
                pub_el = item.find("pubDate")
                cat_el = item.find("category")
                if title_el is None:
                    continue
                title = (title_el.text or "").strip()
                desc = (desc_el.text or "").strip() if desc_el is not None else ""
                pub = (pub_el.text or "").strip() if pub_el is not None else ""
                cat = (cat_el.text or "General").strip() if cat_el is not None else "General"
                if title and title.lower() not in ("", "rss"):
                    items.append({
                        "title": title[:120],
                        "desc": re.sub(r"<[^>]+>", "", desc)[:160],
                        "pub": pub[:30],
                        "cat": cat[:30],
                    })
                if len(items) >= max_items:
                    break
            if items:
                return items
        except Exception:
            continue
    return []

async def cmd_worldmonitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.username or "")
    is_dev = is_developer(user.id, user.username or "")

    wait = check_rate_limit(user.id)
    if wait > 0:
        await update.message.reply_text(
            f"⏳ _Rate limited. Wait `{wait:.1f}s` before next command._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if not is_dev:
        if db_user["credits"] < WORLD_MONITOR_CREDIT_COST:
            await update.message.reply_text(
                f"{CROSS} *Not enough credits!*\n{LINE}\n"
                f"World Monitor costs `{WORLD_MONITOR_CREDIT_COST} credits`.\n"
                f"You have `{db_user['credits']}` credits.\n\n"
                f"Earn more with `/claim` or `/referral`.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        data = load_data()
        uid = str(user.id)
        data["users"][uid]["credits"] = db_user["credits"] - WORLD_MONITOR_CREDIT_COST
        data["users"][uid]["total_used"] = db_user.get("total_used", 0) + 1
        save_data(data)
        db_user = get_user(user.id)
    else:
        data = load_data()
        uid = str(user.id)
        data["users"][uid]["total_used"] = db_user.get("total_used", 0) + 1
        save_data(data)

    update_rate_limit(user.id)
    track_tool_usage("worldmonitor")

    msg = await update.message.reply_text(
        f"🌍 _Scanning world events…_", parse_mode=ParseMode.MARKDOWN
    )

    news_items = get_world_news(8)

    if not news_items:
        await msg.edit_text(
            f"🌍 *WORLD MONITOR*\n{LINE}\n"
            f"{CROSS} Unable to fetch live news at this time.\n"
            f"Please try again in a moment.\n{LINE}\n"
            f"💰 Credits Left: `{db_user['credits']}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Retry", callback_data="worldmonitor_refresh")],
                [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
            ]),
        )
        return

    now = datetime.utcnow().strftime("%d %b %Y %H:%M UTC")
    lines = []
    for i, item in enumerate(news_items, 1):
        cat_tag = f"[{item['cat']}]" if item['cat'] and item['cat'].lower() != "general" else ""
        lines.append(f"*{i}.* {cat_tag} {item['title']}")
        if item.get("desc"):
            lines.append(f"   _{item['desc'][:100]}_")

    full_text = (
        f"╔══════════════════════════════╗\n"
        f"║    🌍 WORLD MONITOR LIVE     ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"{GLOBE} *Live World Events*\n"
        f"{LINE}\n"
        f"🕐 *Updated:* `{now}`\n"
        f"{LINE}\n\n"
        + "\n\n".join(lines) +
        f"\n\n{LINE}\n"
        f"💰 Credits Left: `{db_user['credits']}`\n"
        f"💡 _Costs {WORLD_MONITOR_CREDIT_COST} credits • Free for Developer_"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh News", callback_data="worldmonitor_refresh")],
        [InlineKeyboardButton("« Back to Menu", callback_data="main_menu")],
    ])
    await msg.edit_text(full_text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

# ─────────────────────────── MAIN ───────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # General commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("credits", cmd_credits))
    app.add_handler(CommandHandler("premium", cmd_premium_info))
    app.add_handler(CommandHandler("disclaimer", cmd_disclaimer))
    app.add_handler(CommandHandler("referral", cmd_referral))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("claim", cmd_claim))
    app.add_handler(CommandHandler("dice", cmd_dice))
    app.add_handler(CommandHandler("flip", cmd_flip))
    app.add_handler(CommandHandler("redeem", cmd_redeem))
    app.add_handler(CommandHandler("feedback", cmd_feedback))
    app.add_handler(CommandHandler("crypto", cmd_crypto))
    app.add_handler(CommandHandler("ccextrap", cmd_ccextrap))

    # Extended games & betting
    app.add_handler(CommandHandler("slots", cmd_slots))
    app.add_handler(CommandHandler("roulette", cmd_roulette))
    app.add_handler(CommandHandler("blackjack", cmd_blackjack))
    app.add_handler(CommandHandler("bj", cmd_blackjack))
    app.add_handler(CommandHandler("crash", cmd_crash))
    app.add_handler(CommandHandler("horse", cmd_horse))
    app.add_handler(CommandHandler("tower", cmd_tower))
    app.add_handler(CommandHandler("guess", cmd_guess))

    # Port scanner tools
    app.add_handler(CommandHandler("portscan", cmd_portscan))
    app.add_handler(CommandHandler("scanports", cmd_scanports))

    # Developer-only commands
    app.add_handler(CommandHandler("createcode", cmd_createcode))
    app.add_handler(CommandHandler("listcodes", cmd_listcodes))
    app.add_handler(CommandHandler("deletecode", cmd_deletecode))
    app.add_handler(CommandHandler("analytics", cmd_analytics))
    app.add_handler(CommandHandler("viewfeedback", cmd_viewfeedback))

    # Developer commands
    app.add_handler(CommandHandler("dev", cmd_dev))
    app.add_handler(CommandHandler("addpremium", cmd_add_premium))
    app.add_handler(CommandHandler("revokepremium", cmd_revoke_premium))
    app.add_handler(CommandHandler("addcredits", cmd_add_credits))
    app.add_handler(CommandHandler("takecredits", cmd_take_credits))
    app.add_handler(CommandHandler("transfer", cmd_transfer))
    app.add_handler(CommandHandler("userinfo", cmd_user_info))
    app.add_handler(CommandHandler("allstats", cmd_all_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("listpremium", cmd_list_premium))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("resetuser", cmd_reset_user))

    # Carding tools
    app.add_handler(CommandHandler("bin", cmd_bin))
    app.add_handler(CommandHandler("gen", cmd_gen))
    app.add_handler(CommandHandler("chk", cmd_chk))
    app.add_handler(CommandHandler("bulkgen", cmd_bulk_gen))

    # Disposable tools
    app.add_handler(CommandHandler("tempmail", cmd_tempmail))
    app.add_handler(CommandHandler("inbox", cmd_inbox))
    app.add_handler(CommandHandler("fakeaddr", cmd_fakeaddr))
    app.add_handler(CommandHandler("passgen", cmd_passgen))

    # Website tools
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("iplookup", cmd_iplookup))
    app.add_handler(CommandHandler("ssl", cmd_ssl))
    app.add_handler(CommandHandler("whois", cmd_whois))
    app.add_handler(CommandHandler("urlencode", cmd_url_encode))
    app.add_handler(CommandHandler("urldecode", cmd_url_decode))
    app.add_handler(CommandHandler("htmlenc", cmd_html_encode))
    app.add_handler(CommandHandler("htmldec", cmd_html_decode))

    # Developer tools
    app.add_handler(CommandHandler("b64enc", cmd_b64enc))
    app.add_handler(CommandHandler("b64dec", cmd_b64dec))
    app.add_handler(CommandHandler("md5", cmd_md5))
    app.add_handler(CommandHandler("sha256", cmd_sha256))
    app.add_handler(CommandHandler("uuid", cmd_uuid))
    app.add_handler(CommandHandler("emailval", cmd_email_val))
    app.add_handler(CommandHandler("color", cmd_color))

    # Math/Number tools
    app.add_handler(CommandHandler("age", cmd_age))
    app.add_handler(CommandHandler("avg", cmd_avg))
    app.add_handler(CommandHandler("bin2dec", cmd_bin2dec))
    app.add_handler(CommandHandler("dec2bin", cmd_dec2bin))
    app.add_handler(CommandHandler("hex2dec", cmd_hex2dec))
    app.add_handler(CommandHandler("dec2hex", cmd_dec2hex))
    app.add_handler(CommandHandler("oct2dec", cmd_oct2dec))
    app.add_handler(CommandHandler("dec2oct", cmd_dec2oct))
    app.add_handler(CommandHandler("bin2ascii", cmd_bin2ascii))
    app.add_handler(CommandHandler("ascii2bin", cmd_ascii2bin))
    app.add_handler(CommandHandler("text2hex", cmd_text2hex))
    app.add_handler(CommandHandler("hex2text", cmd_hex2text))

    # Text tools
    app.add_handler(CommandHandler("upper", cmd_upper))
    app.add_handler(CommandHandler("lower", cmd_lower))
    app.add_handler(CommandHandler("title", cmd_title))
    app.add_handler(CommandHandler("swapcase", cmd_swapcase))
    app.add_handler(CommandHandler("reverse", cmd_reverse))
    app.add_handler(CommandHandler("wordcount", cmd_wordcount))
    app.add_handler(CommandHandler("commasep", cmd_commasep))

    # Converter tools
    app.add_handler(CommandHandler("temp", cmd_temp))
    app.add_handler(CommandHandler("currency", cmd_currency))

    # Finance tools
    app.add_handler(CommandHandler("discount", cmd_discount))
    app.add_handler(CommandHandler("gst", cmd_gst))
    app.add_handler(CommandHandler("cpm", cmd_cpm))

    # World Monitor
    app.add_handler(CommandHandler("worldmonitor", cmd_worldmonitor))

    # God Mode features
    app.add_handler(CommandHandler("weather", cmd_weather))
    app.add_handler(CommandHandler("translate", cmd_translate))
    app.add_handler(CommandHandler("stock", cmd_stock))
    app.add_handler(CommandHandler("define", cmd_define))
    app.add_handler(CommandHandler("joke", cmd_joke))
    app.add_handler(CommandHandler("fact", cmd_fact))
    app.add_handler(CommandHandler("qr", cmd_qr))
    app.add_handler(CommandHandler("qrurl", cmd_qrurl))
    app.add_handler(CommandHandler("fileqr", cmd_fileqr))
    app.add_handler(CommandHandler("shorturl", cmd_shorturl))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))
    app.add_handler(CommandHandler("trivia", cmd_trivia))
    app.add_handler(CommandHandler("passwordgen", cmd_passwordgen))
    app.add_handler(CommandHandler("timezone", cmd_timezone))
    app.add_handler(CommandHandler("calc", cmd_calc))
    app.add_handler(CommandHandler("randomname", cmd_randomname))
    app.add_handler(CommandHandler("geoip", cmd_geoip))
    app.add_handler(CommandHandler("hashlookup", cmd_hashlookup))

    # Batch 1 — Math / Science / Cipher
    app.add_handler(CommandHandler("wiki", cmd_wiki))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("convert", cmd_convert))
    app.add_handler(CommandHandler("prime", cmd_prime))
    app.add_handler(CommandHandler("baseconv", cmd_baseconv))
    app.add_handler(CommandHandler("roman", cmd_roman))
    app.add_handler(CommandHandler("periodic", cmd_periodic))
    app.add_handler(CommandHandler("fibonacci", cmd_fibonacci))
    app.add_handler(CommandHandler("morse", cmd_morse))
    app.add_handler(CommandHandler("caesar", cmd_caesar))
    app.add_handler(CommandHandler("rot13", cmd_rot13))
    app.add_handler(CommandHandler("binary2text", cmd_binary2text))
    app.add_handler(CommandHandler("hex2text", cmd_hex2text))
    app.add_handler(CommandHandler("jwtdecode", cmd_jwtdecode))

    # Batch 2 — Games / World / Social
    app.add_handler(CommandHandler("rps", cmd_rps))
    app.add_handler(CommandHandler("8ball", cmd_8ball))
    app.add_handler(CommandHandler("roll", cmd_roll))
    app.add_handler(CommandHandler("quote", cmd_quote))
    app.add_handler(CommandHandler("meme", cmd_meme))
    app.add_handler(CommandHandler("advice", cmd_advice))
    app.add_handler(CommandHandler("country", cmd_country))
    app.add_handler(CommandHandler("earthquake", cmd_earthquake))
    app.add_handler(CommandHandler("reddit", cmd_reddit))
    app.add_handler(CommandHandler("covid", cmd_covid))
    app.add_handler(CommandHandler("dnscheck", cmd_dnscheck))
    app.add_handler(CommandHandler("lyrics", cmd_lyrics))
    app.add_handler(CommandHandler("github", cmd_github))
    app.add_handler(CommandHandler("npm", cmd_npm))
    app.add_handler(CommandHandler("pypi", cmd_pypi))
    app.add_handler(CommandHandler("movie", cmd_movie))
    app.add_handler(CommandHandler("headers", cmd_headers))
    app.add_handler(CommandHandler("scramble", cmd_scramble))
    app.add_handler(CommandHandler("hangman", cmd_hangman))
    app.add_handler(CommandHandler("tictactoe", cmd_tictactoe))

    # Batch 3 — Productivity
    app.add_handler(CommandHandler("notes", cmd_notes))
    app.add_handler(CommandHandler("todo", cmd_todo))
    app.add_handler(CommandHandler("remind", cmd_remind))
    app.add_handler(CommandHandler("pastebin", cmd_pastebin))
    app.add_handler(CommandHandler("loan", cmd_loan))
    app.add_handler(CommandHandler("compound", cmd_compound))

    # Batch 4 — Developer Power Tools
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("botstats", cmd_botstats))
    app.add_handler(CommandHandler("maintenance", cmd_maintenance))
    app.add_handler(CommandHandler("transfercredits", cmd_transfercredits))
    app.add_handler(CommandHandler("givepremium", cmd_givepremium))
    app.add_handler(CommandHandler("banuser", cmd_ban_user))
    app.add_handler(CommandHandler("unbanuser", cmd_unban_user))
    app.add_handler(CommandHandler("devpanel", cmd_devpanel))

    # File-to-QR + Scramble answer message handler (must come BEFORE unknown_command)
    app.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE | filters.VIDEO_NOTE | filters.Sticker.ALL,
        handle_fileqr_message,
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_scramble_answer))

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Unknown
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # Job queue — news subscription broadcast every 60 minutes
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(news_broadcast_job, interval=3600, first=60)

    async def post_init(app):
        await set_commands(app)
        logger.info(f"✅ {BOT_NAME} is running!")

    app.post_init = post_init
    start_health_server()
    logger.info(f"Starting {BOT_NAME}...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
