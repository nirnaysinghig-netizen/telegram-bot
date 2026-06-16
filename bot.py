#!/usr/bin/env python3
"""
ByteOTP Bot v3 — Bot API 9.4 Colored Buttons + Telegram Premium Custom Emoji
"""

import asyncio
import sqlite3
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    FloodWaitError,
    PhoneNumberInvalidError,
)

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "8670806248:AAE5BVkhvy4knQVLpmqal61JhM6b-K_BrVo")
ADMIN_ID     = 6121829939
API_ID       = 30478307
API_HASH     = "cd94f64d413b610650c1933f37228d8b"
SUPPORT_USER = "@byteotp_support"

SESSIONS_DIR = "sessions"
DB_PATH      = "byteotp.db"

COUNTRIES = {
    "IN": ("India",          "🇮🇳", 55,  "+91"),
    "US": ("United States",  "🇺🇸", 80,  "+1"),
    "CA": ("Canada",         "🇨🇦", 80,  "+1"),
    "UK": ("United Kingdom", "🇬🇧", 90,  "+44"),
    "RU": ("Russia",         "🇷🇺", 60,  "+7"),
    "BD": ("Bangladesh",     "🇧🇩", 45,  "+880"),
    "PK": ("Pakistan",       "🇵🇰", 45,  "+92"),
    "ID": ("Indonesia",      "🇮🇩", 50,  "+62"),
    "NG": ("Nigeria",        "🇳🇬", 50,  "+234"),
}

CANADA_AREA_CODES = {
    '204','226','236','249','250','289','306','343','365','387',
    '403','416','418','431','437','438','450','506','514','519',
    '548','579','581','587','604','613','639','647','672','705',
    '709','742','778','780','782','807','819','825','867','873',
    '902','905'
}

LOW_STOCK_THRESHOLD = 3

MIN_DEPOSIT = 20      # minimum deposit amount (₹)
MAX_DEPOSIT = 10000   # maximum deposit amount (₹)

os.makedirs(SESSIONS_DIR, exist_ok=True)
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
#  PREMIUM TELEGRAM CUSTOM EMOJI
#
#  Two sets:
#   1. MSG_*  — for HTML message text  → use <tg-emoji> tag
#   2. BTN_*  — for button text labels → same <tg-emoji> tag
#              (NiceGram / premium clients render these in buttons)
#
#  Emoji IDs sourced from user's premium emoji pack screenshots.
#  Fallback shown to non-premium / older clients.
#
#  PLACEMENT RULES (don't use randomly):
#   MSG_SPARKLE   → welcome / greeting messages only
#   MSG_STAR_*    → headings / bot title decoration
#   MSG_COIN      → wallet, balance, payment context
#   MSG_MONEY     → deposit, transaction context
#   MSG_CHECK     → success confirmations
#   MSG_CHECK_ANIM→ strong success (purchase done, deposit approved)
#   MSG_SHIELD    → security, ban, suspension warnings
#   MSG_TG        → Telegram-specific content (buy number, account)
#   MSG_CROWN     → admin panel messages
#   MSG_CONFETTI  → promo code / redeem success
#   MSG_BULB      → help / how-it-works messages
#   MSG_OTP_FLASH → OTP reveal (exciting moment)
#   MSG_TICK      → list bullet points / feature items
# ═══════════════════════════════════════════════════════════════════

def e(emoji_id: int, fallback: str) -> str:
    """Wrap in Telegram custom emoji HTML tag."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

# ── Message-context premium emoji ────────────────────────────────
MSG_SPARKLE    = e(4956560549287560231, "✨")   # welcome / greeting
MSG_OTP_FLASH  = e(5354973921961611463, "✨")   # OTP reveal flash
MSG_STAR       = e(5388675409346847202, "⭐")   # main heading decoration
MSG_STAR_PINK  = e(5388627846879013988, "⭐")   # secondary heading
MSG_STAR_BLUE  = e(4956706659780003072, "⭐")   # info headings
MSG_STAR_FIRE  = e(4956232383721374836, "⭐")   # feature highlights
MSG_CHECK      = e(4956721670690702265, "✅")   # success confirmation
MSG_CHECK_BLUE = e(4990307318513009602, "✅")   # secondary success
MSG_TICK       = e(5298979535675483473, "✔️")  # list bullet / feature item
MSG_SHIELD     = e(4956611513369494230, "🛡")   # security / ban / suspension
MSG_TG         = e(5798436339019947373, "📱")   # Telegram platform context
MSG_BUY_NUMBER = e(4956583802240500602, "🛍")   # "Buy a Number" section heading
MSG_COIN       = e(4956719506027185156, "🪙")   # wallet / balance / coin
MSG_MONEY      = e(4956719506027185156, "💰")   # deposit / money bag
MSG_DOLLAR     = e(4958506272551863292, "💵")   # transaction / dollar
MSG_CROWN      = e(4956420859771225351, "👑")   # admin panel
MSG_CONFETTI   = e(5206171807874322401, "🎊")   # promo code / redeem
MSG_BULB       = e(5206442399403903626, "💡")   # help / info / tips
MSG_GEAR       = e(5206341626586240935, "⚙️")  # settings / admin actions
MSG_BOX        = e(5206369213161184480, "📦")   # stock / accounts
MSG_DIAMOND    = e(5206563130934597848, "💎")   # premium / highlight
MSG_BADGE      = e(5206257320673186878, "✅")   # verified / OTP fetch

MSG_CROSS      = e(4958526153955476488, "❌")   # error / invalid / cancelled
MSG_LOADING    = e(5472094171135248679, "⏳")   # loading / processing
MSG_CARE       = e(5206369213161184480, "💬")   # customer care chat

# ── New premium emoji (2560 pack) ────────────────────────────────────
MSG_CHECK_ANIM = e(6298670698948724690, "✅")   # OVERRIDE: animated green checkmark (global)
MSG_BUY_BTN    = e(5316746823241600820, "🛒")   # BUY button decoration
MSG_QR_CODE    = e(5316868877622217508, "📲")   # QR / deposit context
MSG_SOLD_OUT   = e(5314646378075430423, "🚫")   # sold out / out of stock

# ── Country adjective map ─────────────────────────────────────────────
COUNTRY_ADJECTIVE = {
    "IN": "Indian",
    "US": "USA",
    "CA": "Canadian",
    "UK": "British",
    "RU": "Russian",
    "BD": "Bangladeshi",
    "PK": "Pakistani",
    "ID": "Indonesian",
    "NG": "Nigerian",
}

def country_label(code: str) -> str:
    """Return '<Adjective> Telegram Account' for a country code."""
    adj = COUNTRY_ADJECTIVE.get(code, COUNTRIES.get(code, ("Unknown","","",""))[0])
    return f"{adj} Telegram Account"
# ── Button premium emoji IDs — used via icon_custom_emoji_id param ──
# Bot API 9.4: pass these as icon_custom_emoji_id= in kb()/ib()
# Do NOT embed in button text strings.
BEID_PHONE    = "5244763347454300958"   # Buy Number (Telegram emoji)
BEID_GET_NUMBER = "5384503132086625813" # Get Number (Menu) / Buy Your First Number
BEID_NUMBERS  = "5316608310546308121"   # My Numbers
BEID_COIN     = "5206619055703760254"   # Wallet
BEID_GIFT     = "5314578938498948321"   # Redeem Code
BEID_SHIELD   = "5206442399403903626"   # Support
BEID_BULB     = "5206472919441509767"   # Help
BEID_CROWN    = "4956420859771225351"   # Admin Panel
BEID_CHECK    = "5206170789967071490"   # Confirm / Done
BEID_BADGE    = "5206665368336111207"   # Get OTP / Verified
BEID_MONEY    = "5190735192901325809"   # Deposit / Money Bag
BEID_DOLLAR   = "5206621860583797800"   # Deposits (admin)
BEID_STAR     = "5470007710382592656"   # Stats
BEID_GEAR     = "5206341626586240935"   # Admin / Settings
BEID_BOX      = "5206369213161184480"   # Release Stock
BEID_SPARKLE  = "5251329798399104282"   # Broadcast
BEID_DIAMOND  = "5952003057897183329"   # Confirm Buy / Premium
BEID_NOTEBOOK = "4956475826762679249"   # Lists / History
BEID_CONFETTI = "5206171807874322401"   # Promo Create
BEID_CARE     = "5206369213161184480"   # Customer Care Chat

# ─────────────────────────────────────────
#  BOT API 9.4 COLORED BUTTON HELPERS
#  style: "primary" blue | "success" green | "danger" red
# ─────────────────────────────────────────
def kb(text: str, style: str = "primary", icon: str = None, **kwargs) -> KeyboardButton:
    if icon:
        kwargs["icon_custom_emoji_id"] = icon
    try:
        return KeyboardButton(text=text, style=style, **kwargs)
    except TypeError:
        # Older aiogram versions don't support style/icon_custom_emoji_id
        kwargs.pop("icon_custom_emoji_id", None)
        return KeyboardButton(text=text, **kwargs)

def ib(text: str, style: str = "primary", icon: str = None, **kwargs) -> InlineKeyboardButton:
    if icon:
        kwargs["icon_custom_emoji_id"] = icon
    try:
        return InlineKeyboardButton(text=text, style=style, **kwargs)
    except TypeError:
        # Older aiogram versions don't support style/icon_custom_emoji_id
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(text=text, **kwargs)

# ─────────────────────────────────────────
#  FSM STATES
# ─────────────────────────────────────────
class AddAccount(StatesGroup):
    phone        = State()
    country_pick = State()
    otp          = State()
    passwd       = State()

class BanState(StatesGroup):
    ban_uid   = State()
    unban_uid = State()

class SupportState(StatesGroup):
    issue   = State()
    message = State()

class RedeemState(StatesGroup):
    code = State()

class AdminStates(StatesGroup):
    broadcast       = State()
    create_promo    = State()
    set_price       = State()
    adjust_balance  = State()
    reply_ticket    = State()
    approve_deposit = State()

class DepositState(StatesGroup):
    awaiting_amount = State()
    awaiting_utr    = State()

# ─────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────
def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            phone        TEXT UNIQUE NOT NULL,
            session_file TEXT NOT NULL,
            country_code TEXT DEFAULT 'IN',
            twofa_pass   TEXT DEFAULT '',
            is_available INTEGER DEFAULT 0,
            is_released  INTEGER DEFAULT 0,
            added_at     TEXT
        );
        CREATE TABLE IF NOT EXISTS assignments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER,
            account_id   INTEGER,
            phone        TEXT,
            session_file TEXT,
            country_code TEXT DEFAULT 'IN',
            price        REAL DEFAULT 55,
            status       TEXT DEFAULT 'active',
            assigned_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS users (
            user_id   INTEGER PRIMARY KEY,
            name      TEXT,
            username  TEXT,
            balance   REAL DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            joined_at TEXT
        );
        CREATE TABLE IF NOT EXISTS promo_codes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            code       TEXT UNIQUE NOT NULL,
            amount     REAL NOT NULL,
            max_uses   INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            created_at TEXT,
            is_active  INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS promo_uses (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            code    TEXT,
            used_at TEXT
        );
        CREATE TABLE IF NOT EXISTS support_tickets (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            issue_type TEXT,
            message    TEXT,
            status     TEXT DEFAULT 'open',
            reply      TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS country_prices (
            country_code TEXT PRIMARY KEY,
            price        REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS deposits (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER,
            txn_id         TEXT,
            amount         REAL DEFAULT 0,
            proof_type     TEXT,
            proof_data     TEXT,
            status         TEXT DEFAULT 'pending',
            qr_message_id  INTEGER,
            created_at     TEXT
        );
        """)
        for code, (_, _, price, _) in COUNTRIES.items():
            c.execute(
                "INSERT OR IGNORE INTO country_prices (country_code, price) VALUES (?,?)",
                (code, price)
            )

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_user(uid: int, name: str, username: str):
    with get_db() as c:
        c.execute(
            "INSERT OR IGNORE INTO users (user_id,name,username,balance,joined_at) VALUES (?,?,?,0,?)",
            (uid, name, username or "", datetime.now().isoformat())
        )

def is_banned(uid: int) -> bool:
    with get_db() as c:
        r = c.execute("SELECT is_banned FROM users WHERE user_id=?", (uid,)).fetchone()
    return bool(r and r["is_banned"])

def get_balance(uid: int) -> float:
    with get_db() as c:
        r = c.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
    return float(r["balance"]) if r else 0.0

def update_balance(uid: int, delta: float):
    with get_db() as c:
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (delta, uid))

def get_country_price(code: str) -> float:
    with get_db() as c:
        r = c.execute("SELECT price FROM country_prices WHERE country_code=?", (code,)).fetchone()
    if r:
        return float(r["price"])
    return COUNTRIES.get(code, ("", "", 55, ""))[2]

def get_stock_count(country_code: str) -> int:
    with get_db() as c:
        r = c.execute(
            "SELECT COUNT(*) FROM accounts WHERE country_code=? AND is_available=1 AND is_released=1",
            (country_code,)
        ).fetchone()
    return r[0] if r else 0

def get_unreleased_count(country_code: str) -> int:
    with get_db() as c:
        r = c.execute(
            "SELECT COUNT(*) FROM accounts WHERE country_code=? AND is_released=0",
            (country_code,)
        ).fetchone()
    return r[0] if r else 0

def save_account(phone: str, session_file: str, country_code: str = "IN", twofa_pass: str = ""):
    with get_db() as c:
        c.execute(
            "INSERT OR REPLACE INTO accounts (phone,session_file,country_code,twofa_pass,is_available,is_released,added_at) VALUES (?,?,?,?,1,0,?)",
            (phone, session_file, country_code, twofa_pass, datetime.now().isoformat())
        )

def release_stock(country_code: str) -> int:
    with get_db() as c:
        r = c.execute(
            "SELECT COUNT(*) FROM accounts WHERE country_code=? AND is_released=0",
            (country_code,)
        ).fetchone()
        count = r[0] if r else 0
        if count:
            c.execute(
                "UPDATE accounts SET is_released=1 WHERE country_code=? AND is_released=0",
                (country_code,)
            )
    return count

def get_available_account(country_code: str) -> Optional[dict]:
    with get_db() as c:
        r = c.execute(
            "SELECT * FROM accounts WHERE country_code=? AND is_available=1 AND is_released=1 ORDER BY id LIMIT 1",
            (country_code,)
        ).fetchone()
    return dict(r) if r else None

def assign_account(uid: int, acc: dict, price: float) -> int:
    with get_db() as c:
        c.execute(
            "INSERT INTO assignments (user_id,account_id,phone,session_file,country_code,price,status,assigned_at) VALUES (?,?,?,?,?,?,'active',?)",
            (uid, acc["id"], acc["phone"], acc["session_file"], acc["country_code"], price, datetime.now().isoformat())
        )
        aid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.execute("UPDATE accounts SET is_available=0, is_released=0 WHERE id=?", (acc["id"],))
    return aid

def get_active_assignment(uid: int) -> Optional[dict]:
    with get_db() as c:
        r = c.execute(
            "SELECT * FROM assignments WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 1",
            (uid,)
        ).fetchone()
    return dict(r) if r else None

def get_user_history(uid: int) -> list:
    with get_db() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM assignments WHERE user_id=? ORDER BY id DESC LIMIT 20",
            (uid,)
        )]

def complete_assignment(assign_id: int, status: str = "completed"):
    with get_db() as c:
        c.execute("UPDATE assignments SET status=? WHERE id=?", (status, assign_id))

def release_user_assignment(uid: int):
    with get_db() as c:
        a = c.execute("SELECT * FROM assignments WHERE user_id=? AND status='active'", (uid,)).fetchone()
        if a:
            c.execute("UPDATE assignments SET status='released' WHERE id=?", (a["id"],))

def get_all_accounts() -> list:
    with get_db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM accounts ORDER BY id DESC")]

def get_all_users() -> list:
    with get_db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM users ORDER BY user_id DESC LIMIT 50")]

def get_all_assignments() -> list:
    with get_db() as c:
        return [dict(r) for r in c.execute(
            "SELECT a.*, u.name FROM assignments a JOIN users u ON u.user_id=a.user_id WHERE a.status='active'"
        )]

def delete_account_db(acc_id: int) -> Optional[str]:
    with get_db() as c:
        r = c.execute("SELECT session_file FROM accounts WHERE id=?", (acc_id,)).fetchone()
        if not r:
            return None
        sf = r["session_file"]
        c.execute("DELETE FROM accounts WHERE id=?", (acc_id,))
    return sf

def get_stats() -> dict:
    with get_db() as c:
        return {
            "total":       c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
            "avail":       c.execute("SELECT COUNT(*) FROM accounts WHERE is_available=1 AND is_released=1").fetchone()[0],
            "unreleased":  c.execute("SELECT COUNT(*) FROM accounts WHERE is_released=0").fetchone()[0],
            "users":       c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "assigned":    c.execute("SELECT COUNT(*) FROM assignments WHERE status='active'").fetchone()[0],
            "total_sales": c.execute("SELECT COALESCE(SUM(price),0) FROM assignments WHERE status='completed'").fetchone()[0],
            "open_tickets":c.execute("SELECT COUNT(*) FROM support_tickets WHERE status='open'").fetchone()[0],
        }

def get_countries_in_db() -> list:
    with get_db() as c:
        rows = c.execute("SELECT DISTINCT country_code FROM accounts").fetchall()
    return [r[0] for r in rows]

def get_countries_with_stock() -> list:
    with get_db() as c:
        rows = c.execute(
            "SELECT DISTINCT country_code FROM accounts WHERE is_available=1 AND is_released=1"
        ).fetchall()
    return [r[0] for r in rows]

def create_promo(code: str, amount: float, max_uses: int = 1) -> bool:
    try:
        with get_db() as c:
            c.execute(
                "INSERT INTO promo_codes (code,amount,max_uses,used_count,created_at,is_active) VALUES (?,?,?,0,?,1)",
                (code.upper(), amount, max_uses, datetime.now().isoformat())
            )
        return True
    except:
        return False

def redeem_promo(uid: int, code: str) -> tuple:
    code = code.upper().strip()
    with get_db() as c:
        p = c.execute("SELECT * FROM promo_codes WHERE code=? AND is_active=1", (code,)).fetchone()
        if not p:
            return False, "Invalid or expired code.", 0
        p = dict(p)
        already = c.execute("SELECT id FROM promo_uses WHERE user_id=? AND code=?", (uid, code)).fetchone()
        if already:
            return False, "You already used this code.", 0
        if p["used_count"] >= p["max_uses"]:
            return False, "Code limit reached.", 0
        c.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE code=?", (code,))
        if p["used_count"] + 1 >= p["max_uses"]:
            c.execute("UPDATE promo_codes SET is_active=0 WHERE code=?", (code,))
        c.execute("INSERT INTO promo_uses (user_id,code,used_at) VALUES (?,?,?)",
                  (uid, code, datetime.now().isoformat()))
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (p["amount"], uid))
    return True, f"Redeemed! ₹{p['amount']:.0f} added to wallet.", p["amount"]

def create_ticket(uid: int, issue_type: str, message: str) -> int:
    with get_db() as c:
        c.execute(
            "INSERT INTO support_tickets (user_id,issue_type,message,status,created_at) VALUES (?,?,?,'open',?)",
            (uid, issue_type, message, datetime.now().isoformat())
        )
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]

def get_open_tickets() -> list:
    with get_db() as c:
        return [dict(r) for r in c.execute(
            "SELECT t.*, u.name, u.username FROM support_tickets t JOIN users u ON u.user_id=t.user_id WHERE t.status='open' ORDER BY t.id DESC"
        )]

def close_ticket(ticket_id: int, reply: str):
    with get_db() as c:
        c.execute("UPDATE support_tickets SET status='closed', reply=? WHERE id=?", (reply, ticket_id))

def detect_country(phone: str) -> str:
    if phone.startswith("+1") and len(phone) >= 5:
        area_code = phone[2:5]
        if area_code in CANADA_AREA_CODES:
            return "CA"
        return "US"
    sorted_entries = sorted(
        [(code, prefix) for code, (_, _, _, prefix) in COUNTRIES.items() if code not in ("US", "CA")],
        key=lambda x: len(x[1]), reverse=True
    )
    for code, prefix in sorted_entries:
        if phone.startswith(prefix):
            return code
    return "IN"

# ─────────────────────────────────────────
#  TELETHON HELPERS
# ─────────────────────────────────────────
_login_clients: dict = {}

def _session_path(phone: str) -> str:
    safe = phone.replace("+", "").replace(" ", "")
    return os.path.join(SESSIONS_DIR, safe)

async def tg_send_otp(phone: str) -> tuple:
    path   = _session_path(phone)
    client = TelegramClient(path, API_ID, API_HASH)
    try:
        await client.connect()
        result = await client.send_code_request(phone)
        _login_clients[phone] = {"client": client, "phone_hash": result.phone_code_hash}
        return True, "OTP sent"
    except PhoneNumberInvalidError:
        await client.disconnect()
        return False, "Invalid phone number format."
    except FloodWaitError as ex:
        await client.disconnect()
        return False, f"Flood wait {ex.seconds}s. Try later."
    except Exception as ex:
        try: await client.disconnect()
        except: pass
        return False, f"Error: {str(ex)}"

async def tg_complete_login(phone: str, code: str, country_override: str = "", password: str = "") -> tuple:
    data = _login_clients.get(phone)
    if not data:
        return False, "Session expired. Start again."
    client     = data["client"]
    phone_hash = data["phone_hash"]
    try:
        await client.sign_in(phone, code=code, phone_code_hash=phone_hash)
        await client.disconnect()
        _login_clients.pop(phone, None)
        country = country_override if country_override else detect_country(phone)
        save_account(phone, _session_path(phone), country, "")
        cname = COUNTRIES.get(country, ("Unknown", "", 0, ""))[0]
        flag  = COUNTRIES.get(country, ("", "🌍", 0, ""))[1]
        return True, f"Account added ({flag} {cname})"
    except SessionPasswordNeededError:
        if not password:
            return None, "2FA_NEEDED"
        try:
            await client.sign_in(password=password)
            await client.disconnect()
            _login_clients.pop(phone, None)
            country = country_override if country_override else detect_country(phone)
            save_account(phone, _session_path(phone), country, password)
            return True, "Account added (2FA)"
        except Exception as ex:
            return False, f"Wrong 2FA: {ex}"
    except PhoneCodeInvalidError:
        return False, "Wrong OTP. Try again."
    except PhoneCodeExpiredError:
        await client.disconnect()
        _login_clients.pop(phone, None)
        return False, "OTP expired. Start again."
    except Exception as ex:
        return False, f"Login failed: {ex}"

async def tg_complete_2fa(phone: str, password: str, country_override: str = "") -> tuple:
    data = _login_clients.get(phone)
    if not data:
        return False, "Session expired."
    client = data["client"]
    try:
        await client.sign_in(password=password)
        await client.disconnect()
        _login_clients.pop(phone, None)
        country = country_override if country_override else detect_country(phone)
        save_account(phone, _session_path(phone), country, password)
        return True, "Account added (2FA)"
    except Exception as ex:
        return False, f"Wrong 2FA: {ex}"

async def tg_get_otp(session_file: str) -> Optional[str]:
    client = TelegramClient(session_file, API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None
        msgs = await client.get_messages(777000, limit=5)
        otp  = None
        for msg in msgs:
            if msg.text:
                match = re.search(r'\b(\d{5,6})\b', msg.text)
                if match:
                    otp = match.group(1)
                    break
        await client.disconnect()
        return otp
    except Exception as ex:
        logger.error(f"OTP fetch error [{session_file}]: {ex}")
        try: await client.disconnect()
        except: pass
        return None

async def tg_logout_session(session_file: str):
    client = TelegramClient(session_file, API_ID, API_HASH)
    try:
        await client.connect()
        if await client.is_user_authorized():
            await client.log_out()
        await client.disconnect()
    except Exception as ex:
        logger.error(f"Auto-logout error [{session_file}]: {ex}")
        try: await client.disconnect()
        except: pass

# ─── DEPOSIT HELPERS ─────────────────────
UPI_ID  = "bytecraft@freecharge"
QR_LINK = "https://ibb.co/bMrL0WwP"

def create_deposit(uid: int, txn_id: str, qr_msg_id: int) -> int:
    with get_db() as c:
        c.execute(
            "INSERT INTO deposits (user_id,txn_id,status,qr_message_id,created_at) VALUES (?,?,'pending',?,?)",
            (uid, txn_id, qr_msg_id, datetime.now().isoformat())
        )
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]

def update_deposit_proof(deposit_id: int, proof_type: str, proof_data: str):
    with get_db() as c:
        c.execute(
            "UPDATE deposits SET proof_type=?, proof_data=?, status='submitted' WHERE id=?",
            (proof_type, proof_data, deposit_id)
        )

def get_pending_deposits() -> list:
    with get_db() as c:
        return [dict(r) for r in c.execute(
            "SELECT d.*, u.name, u.username FROM deposits d JOIN users u ON u.user_id=d.user_id WHERE d.status='submitted' ORDER BY d.id DESC"
        )]

def get_user_deposits(uid: int) -> list:
    with get_db() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM deposits WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,)
        )]

def approve_deposit_db(deposit_id: int) -> Optional[dict]:
    with get_db() as c:
        d = c.execute("SELECT * FROM deposits WHERE id=?", (deposit_id,)).fetchone()
        if not d:
            return None
        d = dict(d)
        c.execute("UPDATE deposits SET status='approved' WHERE id=?", (deposit_id,))
    return d

def reject_deposit_db(deposit_id: int):
    with get_db() as c:
        c.execute("UPDATE deposits SET status='rejected' WHERE id=?", (deposit_id,))

# ─────────────────────────────────────────
#  BOT + DISPATCHER
# ─────────────────────────────────────────
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp  = Dispatcher(storage=MemoryStorage())

# ═══════════════════════════════════════════════════════════════════
#  KEYBOARDS  — Bot API 9.4 Colored Buttons + Premium Emoji
#
#  Button text includes <tg-emoji> tags → premium clients render them.
#  Color rules:
#    primary (blue)  → buy / deposit / info / get OTP
#    success (green) → wallet / done / approve / redeem / numbers
#    danger  (red)   → cancel / close / ban / reject / support
# ═══════════════════════════════════════════════════════════════════

def main_kb(uid: int) -> ReplyKeyboardMarkup:
    rows = [
        [kb("Buy Number",   "primary", icon=BEID_GET_NUMBER),
         kb("My Numbers",  "success", icon=BEID_NUMBERS)],
        [kb("Wallet",      "success", icon=BEID_COIN),
         kb("Redeem Code", "primary", icon=BEID_GIFT)],
        [kb("Support",     "danger",  icon=BEID_SHIELD),
         kb("Help",        "primary", icon=BEID_BULB)],
    ]
    if uid == ADMIN_ID:
        rows.append([kb("Admin Panel", "success", icon=BEID_CROWN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def admin_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("Add Account",    "primary", icon=BEID_PHONE,    callback_data="adm_add"),
         ib("All Accounts",  "success", icon=BEID_NOTEBOOK, callback_data="adm_list")],
        [ib("Stats",         "primary", icon=BEID_STAR,     callback_data="adm_stats"),
         ib("Users",         "success", icon=BEID_GEAR,     callback_data="adm_users")],
        [ib("Release Stock", "success", icon=BEID_BOX,      callback_data="adm_release_stock"),
         ib("Release Number","primary", icon=BEID_CHECK,    callback_data="adm_release")],
        [ib("Delete Account","danger",                       callback_data="adm_delete"),
         ib("Promo Codes",   "success", icon=BEID_CONFETTI, callback_data="adm_promos")],
        [ib("Tickets",       "primary", icon=BEID_SHIELD,   callback_data="adm_tickets"),
         ib("Adjust Balance","success", icon=BEID_COIN,     callback_data="adm_adj_bal")],
        [ib("Set Prices",    "primary", icon=BEID_DOLLAR,   callback_data="adm_prices"),
         ib("Broadcast",     "success", icon=BEID_SPARKLE,  callback_data="adm_broadcast")],
        [ib("Deposits",      "primary", icon=BEID_MONEY,    callback_data="adm_deposits"),
         ib("Ban User",      "danger",                       callback_data="adm_ban")],
        [ib("Unban User",    "success", icon=BEID_BADGE,    callback_data="adm_unban"),
         ib("Close",         "danger",                       callback_data="adm_close")],
    ])

def back_ikb(cb: str = "adm_home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("Back", "primary", callback_data=cb)]
    ])

def country_select_ikb() -> InlineKeyboardMarkup:
    available_codes = get_countries_with_stock()
    btns = []
    for i, code in enumerate(available_codes):
        if code not in COUNTRIES:
            continue
        name, flag, _, _ = COUNTRIES[code]
        stock = get_stock_count(code)
        price = get_country_price(code)
        style = "primary" if i % 2 == 0 else "success"
        label = f"{flag} {country_label(code)}  |  ₹{price:.0f}  |  {stock} left"
        btns.append([ib(
            label,
            style,
            callback_data=f"country_{code}"
        )])
    if not btns:
        btns.append([ib("No stock available", "danger", callback_data="no_stock")])
    btns.append([ib("Cancel", "danger", callback_data="cancel_buy")])
    return InlineKeyboardMarkup(inline_keyboard=btns)

def support_main_ikb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("File a Complaint", "primary", icon=BEID_SHIELD, callback_data="support_complaint")],
        [ib("Customer Care Chat", "success", icon=BEID_CARE, url=f"https://t.me/{SUPPORT_USER.lstrip('@')}")],
        [ib("Cancel",                           "danger",  callback_data="cancel_support")],
    ])

def support_issues_ikb() -> InlineKeyboardMarkup:
    issues = [
        ("Refund Request",    "refund"),
        ("Wrong Credentials", "wrong_creds"),
        ("OTP Not Received",  "no_otp"),
        ("Balance Issue",     "balance"),
        ("Bug / Error",       "bug"),
        ("Other",             "other"),
    ]
    styles = ["primary", "success", "primary", "success", "primary", "success"]
    btns   = [[ib(label, styles[i], callback_data=f"issue_{val}")] for i, (label, val) in enumerate(issues)]
    btns.append([ib("Back", "primary", callback_data="support_back")])
    return InlineKeyboardMarkup(inline_keyboard=btns)

# ─────────────────────────────────────────
#  /start  /help
# ─────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(msg: Message):
    u = msg.from_user
    ensure_user(u.id, u.full_name, u.username or "")
    if is_banned(u.id):
        await msg.answer(
            f"{MSG_SHIELD} <b>Your account has been suspended.</b>\n\n"
            f"<i>Contact support if you believe this is an error.</i>"
        )
        return
    await msg.answer(
        f"{MSG_SPARKLE} <b>Welcome to ByteOTP Bot!</b> {MSG_STAR}\n"
        f"<i>Your automated shop for verified Telegram accounts.</i>\n\n"
        f"<blockquote>"
        f"{MSG_STAR_FIRE} <b>Instant Delivery</b> — right after payment\n"
        f"{MSG_SHIELD} <b>Safe &amp; Secure</b> — encrypted sessions\n"
        f"{MSG_DIAMOND} <b>Premium Numbers</b> — verified &amp; ready to use"
        f"</blockquote>\n\n"
        f"{MSG_TG} <i>Use the menu buttons below to get started!</i>",
        reply_markup=main_kb(u.id)
    )

@dp.message(Command("help"))
@dp.message(F.text.startswith("\U0001f4a1") | (F.text == "Help") | F.text.contains("Help"))
async def cmd_help(msg: Message):
    await msg.answer(
        f"{MSG_BULB} <b>How It Works</b>\n\n"
        f"<blockquote>"
        f"{MSG_TICK} Add balance to your wallet via <b>Deposit</b>\n"
        f"{MSG_TICK} Tap <b>Buy Number</b> → choose country → confirm\n"
        f"{MSG_TICK} Enter the assigned number on Telegram login\n"
        f"{MSG_TICK} Tap <b>Get OTP</b> — bot auto-fetches the code!"
        f"</blockquote>\n\n"
        f"{MSG_COIN} Prices start from <b>₹45</b> per number\n"
        f"{MSG_SHIELD} All sessions are encrypted &amp; secure\n\n"
        f"<i>Support: {SUPPORT_USER}</i>"
        # NOTE: no reply_markup here on purpose — the persistent menu keyboard
        # is already showing, and re-sending it caused a visible refresh/shake.
    )

# ─────────────────────────────────────────
#  WALLET
# ─────────────────────────────────────────
@dp.message(F.text.startswith("\U0001fa99") | (F.text == "Wallet") | F.text.contains("Wallet"))
async def wallet_cmd(msg: Message):
    uid = msg.from_user.id
    ensure_user(uid, msg.from_user.full_name, msg.from_user.username or "")
    if is_banned(uid):
        await msg.answer(f"{MSG_SHIELD} <b>Account suspended.</b>")
        return
    bal = get_balance(uid)
    kb_wallet = InlineKeyboardMarkup(inline_keyboard=[
        [ib("Deposit", "primary", icon=BEID_MONEY, callback_data="deposit_start")],
        [ib("Redeem Code", "success", icon=BEID_GIFT, callback_data="go_redeem")],
        [ib("Transactions", "primary", icon=BEID_NOTEBOOK, callback_data="wallet_txns")],
    ])
    await msg.answer(
        f"{MSG_COIN} <b>Your Wallet</b>\n\n"
        f"<blockquote>{MSG_CHECK} <b>Balance:</b> <code>₹{bal:.2f}</code></blockquote>\n\n"
        f"<i>Tap <b>Deposit</b> to add funds or <b>Transactions</b> to view history.</i>",
        reply_markup=kb_wallet
    )

@dp.callback_query(F.data == "wallet_txns")
async def wallet_txns_cb(cb: CallbackQuery):
    await cb.answer()
    uid      = cb.from_user.id
    deposits = get_user_deposits(uid)
    if not deposits:
        await cb.message.edit_text(
            f"{MSG_COIN} <b>Transaction History</b>\n\n"
            f"<blockquote><i>No transactions yet.\nDeposit funds to get started!</i></blockquote>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [ib("Back to Wallet", "primary", callback_data="back_wallet")]
            ])
        )
        return
    lines = [f"{MSG_COIN} <b>Transaction History</b>\n"]
    for d in deposits:
        status_icon = {"pending": MSG_LOADING, "submitted": MSG_LOADING, "approved": MSG_CHECK_ANIM, "rejected": MSG_CROSS}.get(d["status"], MSG_LOADING)
        amt_txt     = f"₹{d['amount']:.0f}" if d["amount"] else "—"
        date        = d["created_at"][:10] if d.get("created_at") else "—"
        lines.append(f"{status_icon} <b>{amt_txt}</b>  <code>{d['txn_id']}</code>  <i>{date}</i>")
    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [ib("Back to Wallet", "primary", callback_data="back_wallet")]
        ])
    )

@dp.callback_query(F.data == "back_wallet")
async def back_wallet_cb(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    bal = get_balance(uid)
    kb_wallet = InlineKeyboardMarkup(inline_keyboard=[
        [ib("Deposit", "primary", icon=BEID_MONEY, callback_data="deposit_start")],
        [ib("Redeem Code", "success", icon=BEID_GIFT, callback_data="go_redeem")],
        [ib("Transactions", "primary", icon=BEID_NOTEBOOK, callback_data="wallet_txns")],
    ])
    await cb.message.edit_text(
        f"{MSG_COIN} <b>Your Wallet</b>\n\n"
        f"<blockquote>{MSG_CHECK} <b>Balance:</b> <code>₹{bal:.2f}</code></blockquote>\n\n"
        f"<i>Tap <b>Deposit</b> to add funds or <b>Transactions</b> to view history.</i>",
        reply_markup=kb_wallet
    )

@dp.callback_query(F.data == "go_redeem")
async def go_redeem_cb(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await cb.message.edit_text(
        f"{e(5204042260009754118, '🎁')} <b>Redeem Promo Code</b>\n\n"
        f"<blockquote>{MSG_CHECK} Enter your exclusive promo code to unlock bonus wallet credits.\n{MSG_DIAMOND} Valid codes are case-sensitive — type carefully!\n{MSG_STAR} Each code can only be used once per account.\n\n<i>Send your promo code below:</i></blockquote>"
    )
    await state.set_state(RedeemState.code)

# ─────────────────────────────────────────
#  DEPOSIT FLOW
# ─────────────────────────────────────────
@dp.callback_query(F.data == "deposit_start")
async def deposit_start_cb(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(DepositState.awaiting_amount)
    await cb.message.answer(
        f"{MSG_MONEY} <b>Add Funds to Wallet</b>\n\n"
        f"<blockquote>Enter the amount you want to deposit (₹)\n"
        f"<i>Min: ₹{MIN_DEPOSIT:.0f} • Max: ₹{MAX_DEPOSIT:.0f}</i></blockquote>"
    )

@dp.message(DepositState.awaiting_amount)
async def dep_amount_input(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    try:
        amount = float(msg.text.strip())
        if amount <= 0:
            raise ValueError
    except:
        await msg.answer(f"{MSG_CROSS} <b>Invalid amount.</b> Enter a valid number, e.g. <code>100</code>")
        return

    if amount < MIN_DEPOSIT:
        await msg.answer(
            f"{MSG_CROSS} <b>Amount too low.</b>\n\n"
            f"<blockquote>The minimum deposit is <b>₹{MIN_DEPOSIT:.0f}</b>.\n"
            f"<i>Please enter a higher amount.</i></blockquote>"
        )
        return
    if amount > MAX_DEPOSIT:
        await msg.answer(
            f"{MSG_CROSS} <b>Amount too high.</b>\n\n"
            f"<blockquote>The maximum deposit is <b>₹{MAX_DEPOSIT:.0f}</b>.\n"
            f"<i>Please enter a lower amount.</i></blockquote>"
        )
        return

    txn_id = str(uuid.uuid4())[:8].upper()
    kb_dep = InlineKeyboardMarkup(inline_keyboard=[
        [ib("Enter UTR Number", "primary", icon=BEID_CHECK, callback_data=f"dep_utr_{txn_id}")],
    ])
    qr_msg = await msg.answer_photo(
        photo=QR_LINK,
        caption=(
            f"{MSG_QR_CODE} <b>Pay ₹{amount:.0f} via UPI</b>\n\n"
            f"<blockquote>"
            f"{MSG_TICK} <b>UPI ID:</b> <code>{UPI_ID}</code>\n"
            f"{MSG_TICK} <b>Amount:</b> <code>₹{amount:.0f}</code>\n"
            f"{MSG_TICK} <b>Reference:</b> <code>{txn_id}</code>"
            f"</blockquote>\n\n"
            f"<i>Pay the exact amount, then tap <b>Enter UTR Number</b> below.</i>"
        ),
        reply_markup=kb_dep
    )
    create_deposit(uid, txn_id, qr_msg.message_id)
    with get_db() as c:
        c.execute("UPDATE deposits SET amount=? WHERE txn_id=? AND user_id=?", (amount, txn_id, uid))
    await state.update_data(txn_id=txn_id, qr_msg_id=qr_msg.message_id, amount=amount)
    await state.set_state(DepositState.awaiting_utr)

@dp.callback_query(F.data.startswith("dep_utr_"))
async def dep_utr_cb(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    txn_id = cb.data.split("dep_utr_", 1)[1]
    await state.update_data(proof_type="utr", txn_id=txn_id)
    await state.set_state(DepositState.awaiting_utr)
    await cb.message.answer(
        f"{MSG_DOLLAR} <b>Enter UTR / Reference Number</b>\n\n"
        f"<blockquote>"
        f"Send the 12-digit UTR from your payment app.\n"
        f"<i>Numbers only — no letters or spaces.</i>"
        f"</blockquote>"
    )

@dp.message(DepositState.awaiting_utr)
async def dep_utr_input(msg: Message, state: FSMContext):
    uid    = msg.from_user.id
    data   = await state.get_data()
    txn_id = data.get("txn_id", "")
    utr    = msg.text.strip() if msg.text else ""

    if not utr:
        await msg.answer(f"{MSG_CROSS} <b>Please send your UTR as text.</b>")
        return
    if not utr.isdigit():
        await state.clear()
        await msg.answer(
            f"{MSG_CROSS} <b>Invalid UTR Number!</b>\n\n"
            f"<blockquote>UTR must contain <b>numbers only</b>.\n"
            f"<i>Session closed. Start again from Wallet → Deposit.</i></blockquote>",
            reply_markup=main_kb(uid)
        )
        return
    if len(utr) < 12:
        await state.clear()
        await msg.answer(
            f"{MSG_CROSS} <b>Invalid UTR Number!</b>\n\n"
            f"<blockquote>UTR must be <b>at least 12 digits</b> long.\n"
            f"You entered only <code>{len(utr)}</code> digits.\n"
            f"<i>Session closed. Start again from Wallet → Deposit.</i></blockquote>",
            reply_markup=main_kb(uid)
        )
        return

    with get_db() as c:
        dep = c.execute("SELECT * FROM deposits WHERE txn_id=? AND user_id=?", (txn_id, uid)).fetchone()
    if not dep:
        await msg.answer(f"{MSG_CROSS} <b>Deposit session not found.</b> Start again from Wallet → Deposit.")
        await state.clear()
        return

    dep = dict(dep)
    update_deposit_proof(dep["id"], "utr", utr)
    await state.clear()
    await msg.answer(
        f"{MSG_CHECK} <b>UTR Submitted!</b>\n\n"
        f"<blockquote>"
        f"{MSG_TICK} <b>UTR:</b> <code>{utr}</code>\n"
        f"{MSG_TICK} <b>Amount:</b> ₹{dep['amount']:.0f}"
        f"</blockquote>\n\n"
        f"<i>Our team will verify and credit your wallet shortly.</i>",
        reply_markup=main_kb(uid)
    )
    try:
        kb_admin = InlineKeyboardMarkup(inline_keyboard=[
            [ib(f"Approve #{dep['id']}", "success", icon=BEID_CHECK, callback_data=f"dep_approve_{dep['id']}_{uid}"),
             ib(f"Reject #{dep['id']}",              "danger",  callback_data=f"dep_reject_{dep['id']}_{uid}")],
        ])
        u  = msg.from_user
        un = f"@{u.username}" if u.username else f"ID: {uid}"
        await bot.send_message(
            ADMIN_ID,
            f"{MSG_DOLLAR} <b>New Deposit Request</b>\n\n"
            f"<blockquote>"
            f"User: <b>{u.full_name}</b> ({un})\n"
            f"Amount: <b>₹{dep['amount']:.0f}</b>\n"
            f"Ref: <code>{txn_id}</code>\n"
            f"UTR: <code>{utr}</code>"
            f"</blockquote>",
            reply_markup=kb_admin
        )
    except:
        pass

@dp.callback_query(F.data.startswith("dep_approve_"))
async def dep_approve_cb(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    _, _, dep_id_str, uid_str = cb.data.split("_", 3)
    dep_id = int(dep_id_str)
    uid    = int(uid_str)
    await state.update_data(dep_id=dep_id, dep_uid=uid)
    await state.set_state(AdminStates.approve_deposit)
    await cb.message.edit_text(
        f"{MSG_MONEY} <b>Approve Deposit #{dep_id}</b>\n\n<i>Enter the amount to credit (₹):</i>"
    )

@dp.message(AdminStates.approve_deposit)
async def do_approve_deposit(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    try:
        amount = float(msg.text.strip())
    except:
        await msg.answer(f"{MSG_CROSS} Enter a valid number.")
        return
    data   = await state.get_data()
    dep_id = data["dep_id"]
    uid    = data["dep_uid"]
    await state.clear()
    with get_db() as c:
        c.execute("UPDATE deposits SET status='approved', amount=? WHERE id=?", (amount, dep_id))
    update_balance(uid, amount)
    new_bal = get_balance(uid)
    await msg.answer(
        f"{MSG_CHECK_ANIM} Deposit #{dep_id} approved. ₹{amount:.0f} credited to user <code>{uid}</code>.",
        reply_markup=main_kb(ADMIN_ID)
    )
    try:
        await bot.send_message(
            uid,
            f"{MSG_CHECK_ANIM} <b>Deposit Approved!</b>\n\n"
            f"<blockquote>"
            f"{MSG_COIN} <b>₹{amount:.0f}</b> added to your wallet\n"
            f"{MSG_TICK} <b>New Balance:</b> <code>₹{new_bal:.2f}</code>"
            f"</blockquote>"
        )
    except: pass

@dp.callback_query(F.data.startswith("dep_reject_"))
async def dep_reject_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    _, _, dep_id_str, uid_str = cb.data.split("_", 3)
    dep_id = int(dep_id_str)
    uid    = int(uid_str)
    reject_deposit_db(dep_id)
    await cb.message.edit_text(f"{MSG_CROSS} Deposit #{dep_id} rejected.")
    try:
        await bot.send_message(
            uid,
            f"{MSG_CROSS} <b>Deposit Rejected</b>\n\n"
            f"<blockquote><i>Your deposit request #{dep_id} was not approved.\n"
            f"Contact support if you believe this is an error.</i></blockquote>"
        )
    except: pass

@dp.callback_query(F.data == "adm_deposits")
async def adm_deposits_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    pending = get_pending_deposits()
    if not pending:
        await cb.message.edit_text(f"{MSG_CHECK} No pending deposits.", reply_markup=back_ikb())
        return
    btns = []
    for i, d in enumerate(pending):
        un    = f"@{d['username']}" if d.get("username") else str(d["user_id"])
        style = "primary" if i % 2 == 0 else "success"
        btns.append([ib(
            f"#{d['id']} {d['name'] or un} — {d['txn_id']}",
            style,
            callback_data=f"dep_approve_{d['id']}_{d['user_id']}"
        )])
    btns.append([ib("Back", "primary", callback_data="adm_home")])
    await cb.message.edit_text(
        f"{MSG_DOLLAR} <b>Pending Deposits ({len(pending)})</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
    )

# ─────────────────────────────────────────
#  REDEEM CODE
# ─────────────────────────────────────────
@dp.message(F.text.startswith("\U0001f38a") | (F.text == "Redeem Code") | F.text.contains("Redeem"))
async def redeem_cmd(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    ensure_user(uid, msg.from_user.full_name, msg.from_user.username or "")
    if is_banned(uid):
        await msg.answer(f"{MSG_SHIELD} <b>Account suspended.</b>")
        return
    await msg.answer(
        f"{e(5204042260009754118, '🎁')} <b>Redeem Promo Code</b>\n\n"
        f"<blockquote>{MSG_CHECK} Enter your exclusive promo code to unlock bonus wallet credits.\n{MSG_DIAMOND} Valid codes are case-sensitive — type carefully!\n{MSG_STAR} Each code can only be used once per account.\n\n<i>Send your promo code below:</i></blockquote>"
    )
    await state.set_state(RedeemState.code)

@dp.message(RedeemState.code)
async def do_redeem(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    ok, text, amount = redeem_promo(uid, msg.text.strip())
    await state.clear()
    if ok:
        bal = get_balance(uid)
        await msg.answer(
            f"{e(5204042260009754118, '🎁')} <b>Code Redeemed Successfully!</b>\n\n"
            f"<blockquote>{MSG_CHECK} {text}\n{MSG_COIN} <b>New Balance:</b> <code>₹{bal:.2f}</code>\n{MSG_DIAMOND} Enjoy your premium credits — buy a number now!</blockquote>",
            reply_markup=main_kb(uid)
        )
    else:
        await msg.answer(
            f"{MSG_CROSS} <b>Code Invalid or Expired</b>\n\n"
            f"<blockquote>{MSG_CROSS} {text}\n{MSG_BULB} Double-check the code and try again.\n<i>If you believe this is an error, contact support.</i></blockquote>",
            reply_markup=main_kb(uid)
        )

# ─────────────────────────────────────────
#  BUY NUMBER FLOW
# ─────────────────────────────────────────
@dp.message(F.text.startswith("\U0001f4f1") | (F.text == "Buy Number") | F.text.contains("Buy Number"))
async def buy_number(msg: Message):
    uid = msg.from_user.id
    ensure_user(uid, msg.from_user.full_name, msg.from_user.username or "")
    if is_banned(uid):
        await msg.answer(f"{MSG_SHIELD} <b>Account suspended.</b>")
        return

    existing = get_active_assignment(uid)
    if existing:
        flag = COUNTRIES.get(existing["country_code"], ("", "🌍", 0, ""))[1]
        kb_active = InlineKeyboardMarkup(inline_keyboard=[
            [ib("Get OTP", "success", icon=BEID_BADGE, callback_data="fetch_otp")],
            [ib("Support", "danger", icon=BEID_SHIELD, callback_data="open_support")],
        ])
        await msg.answer(
            f"{MSG_TG} <b>Active Number Found!</b>\n\n"
            f"<blockquote>"
            f"{flag} <b>{country_label(existing['country_code'])}</b>\n"
            f"{MSG_QR_CODE} <code>{existing['phone']}</code>\n"
            f"{MSG_COIN} Paid: <b>₹{existing['price']:.0f}</b>"
            f"</blockquote>\n\n"
            f"{MSG_TICK} Enter this number on Telegram login\n"
            f"{MSG_TICK} Then tap <b>Get OTP</b> below",
            reply_markup=kb_active
        )
        return

    kb_buy = InlineKeyboardMarkup(inline_keyboard=[
        [ib("Telegram Number", "primary", icon=BEID_PHONE, callback_data="platform_telegram")],
        [ib("Cancel",                        "danger",  callback_data="cancel_buy")],
    ])
    await msg.answer(
        f"{MSG_BUY_NUMBER} <b>Buy a Number</b>\n\n"
        f"<blockquote><i>Select the platform you need it for:</i></blockquote>",
        reply_markup=kb_buy
    )

@dp.callback_query(F.data == "platform_telegram")
async def platform_telegram_cb(cb: CallbackQuery):
    await cb.answer()
    available = get_countries_with_stock()
    if not available:
        await cb.message.edit_text(
            f"{MSG_CROSS} <b>Out of Stock</b>\n\n"
            f"<blockquote><i>No numbers available right now.\nCheck back later or contact support.</i></blockquote>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [ib("Back",              "primary", callback_data="back_platform")],
                [ib("Support", "danger", icon=BEID_SHIELD,  callback_data="open_support")],
            ])
        )
        return
    btns = []
    for i, code in enumerate(available):
        if code not in COUNTRIES:
            continue
        name, flag, _, _ = COUNTRIES[code]
        stock     = get_stock_count(code)
        price     = get_country_price(code)
        stock_txt = f"{stock} in stock" if stock > 0 else f"{MSG_SOLD_OUT} Sold Out"
        style     = "primary" if i % 2 == 0 else "success"
        label     = f"{flag} {country_label(code)}  |  ₹{price:.0f}  |  {stock_txt}"
        btns.append([ib(
            label,
            style,
            callback_data=f"country_{code}"
        )])
    btns.append([ib("Back", "primary", callback_data="back_platform")])
    await cb.message.edit_text(
        f"{MSG_TG} <b>Select Your Country</b> {MSG_STAR}\n"
        f"<i>Pick the country you'd like your verified number from — premium quality, every time.</i>\n\n"
        f"<blockquote>"
        f"{MSG_TICK} <b>Instant Delivery</b> — active the second your payment clears\n"
        f"{MSG_SHIELD} <b>Fully Secure</b> — encrypted &amp; verified sessions\n"
        f"{MSG_DIAMOND} <b>Live Pricing</b> — real-time stock &amp; rates shown below\n\n"
        f"{MSG_TG} <i>Tap a country below to continue</i>"
        f"</blockquote>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
    )

@dp.callback_query(F.data == "back_platform")
async def back_platform_cb(cb: CallbackQuery):
    await cb.answer()
    kb_buy = InlineKeyboardMarkup(inline_keyboard=[
        [ib("Telegram Number", "primary", icon=BEID_PHONE, callback_data="platform_telegram")],
        [ib("Cancel",                        "danger",  callback_data="cancel_buy")],
    ])
    await cb.message.edit_text(
        f"{MSG_BUY_NUMBER} <b>Buy a Number</b>\n\n"
        f"<blockquote><i>Select the platform you need it for:</i></blockquote>",
        reply_markup=kb_buy
    )

@dp.callback_query(F.data == "back_country")
async def back_country_cb(cb: CallbackQuery):
    await cb.answer()
    available = get_countries_with_stock()
    if not available:
        await cb.message.edit_text(
            f"{MSG_CROSS} <b>Out of Stock</b>\n\n<blockquote><i>No numbers available.</i></blockquote>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [ib("Back", "primary", callback_data="back_platform")]
            ])
        )
        return
    btns = []
    for i, code in enumerate(available):
        if code not in COUNTRIES:
            continue
        name, flag, _, _ = COUNTRIES[code]
        stock     = get_stock_count(code)
        price     = get_country_price(code)
        stock_txt = f"{stock} in stock" if stock > 0 else f"{MSG_SOLD_OUT} Sold Out"
        style     = "primary" if i % 2 == 0 else "success"
        label     = f"{flag} {country_label(code)}  |  ₹{price:.0f}  |  {stock_txt}"
        btns.append([ib(
            label,
            style,
            callback_data=f"country_{code}"
        )])
    btns.append([ib("Back", "primary", callback_data="back_platform")])
    await cb.message.edit_text(
        f"{MSG_TG} <b>Select Your Country</b>\n\n"
        f"<blockquote>"
        f"Choose the country whose Telegram account you want to receive OTP for.\n\n"
        f"{MSG_TICK} <b>Instant Delivery</b> — assigned the moment payment clears\n"
        f"{MSG_TICK} <b>Fully Verified</b> — encrypted &amp; secure sessions only\n"
        f"{MSG_TICK} <b>Live Rates &amp; Stock</b> — real-time pricing shown below"
        f"</blockquote>\n\n"
        f"<i>Tap your country from the list below to proceed:</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
    )

@dp.callback_query(F.data == "cancel_buy")
async def cancel_buy_cb(cb: CallbackQuery):
    await cb.answer()
    await cb.message.edit_text(f"{MSG_CROSS} <b>Cancelled.</b>")

@dp.callback_query(F.data == "no_stock")
async def no_stock_cb(cb: CallbackQuery):
    await cb.answer("No stock available right now. Please try later!", show_alert=True)

@dp.callback_query(F.data.startswith("country_"))
async def country_selected(cb: CallbackQuery):
    await cb.answer()
    uid  = cb.from_user.id
    code = cb.data.split("_", 1)[1]

    if code not in COUNTRIES:
        await cb.message.edit_text(f"{MSG_CROSS} <b>Invalid country.</b>")
        return

    name, flag, _, _ = COUNTRIES[code]
    price = get_country_price(code)
    stock = get_stock_count(code)
    bal   = get_balance(uid)

    if stock == 0:
        await cb.answer(f"{flag} {name} is out of stock. Try another country!", show_alert=True)
        return

    kb_confirm = InlineKeyboardMarkup(inline_keyboard=[
        [ib(f"Confirm — Pay ₹{price:.0f}", "success", icon=BEID_DIAMOND, callback_data=f"confirm_buy_{code}")],
        [ib("Back",                                        "primary", callback_data="back_country")],
    ])
    status = "Sufficient" if bal >= price else f"Need ₹{price - bal:.0f} more"
    await cb.message.edit_text(
        f"{flag} <b>{country_label(code)}</b>\n\n"
        f"<blockquote>"
        f"{MSG_COIN} Price: <b>₹{price:.0f}</b>\n"
        f"{MSG_BOX} Stock: <b>{stock} available</b>\n"
        f"{MSG_TICK} Your Balance: <b>₹{bal:.2f}</b> — <i>{status}</i>"
        f"</blockquote>\n\n"
        f"<i>Confirm to proceed with payment?</i>",
        reply_markup=kb_confirm
    )

@dp.callback_query(F.data.startswith("confirm_buy_"))
async def confirm_buy(cb: CallbackQuery):
    await cb.answer()
    uid  = cb.from_user.id
    code = cb.data.split("confirm_buy_", 1)[1]

    if code not in COUNTRIES:
        await cb.message.edit_text(f"{MSG_CROSS} <b>Invalid selection.</b>")
        return

    price = get_country_price(code)
    bal   = get_balance(uid)

    if bal < price:
        kb_bal = InlineKeyboardMarkup(inline_keyboard=[
            [ib("Deposit Funds", "primary", icon=BEID_MONEY, callback_data="deposit_start")],
            [ib("Redeem Code", "success", icon=BEID_GIFT, callback_data="go_redeem")],
        ])
        await cb.message.edit_text(
            f"{MSG_CROSS} <b>Insufficient Balance</b>\n\n"
            f"<blockquote>"
            f"{MSG_COIN} Required: <b>₹{price:.0f}</b>\n"
            f"{MSG_COIN} Your balance: <b>₹{bal:.2f}</b>\n"
            f"{MSG_TICK} Short by: <b>₹{price - bal:.0f}</b>"
            f"</blockquote>\n\n"
            f"<i>Add funds or use a promo code to continue.</i>",
            reply_markup=kb_bal
        )
        return

    acc = get_available_account(code)
    if not acc:
        await cb.message.edit_text(
            f"{MSG_CROSS} <b>Just ran out of stock!</b>\n\n"
            f"<blockquote><i>Try again or pick another country.</i></blockquote>",
            reply_markup=country_select_ikb()
        )
        return

    update_balance(uid, -price)
    assign_id = assign_account(uid, acc, price)
    name, flag, _, _ = COUNTRIES[code]
    new_bal   = get_balance(uid)

    remaining = get_stock_count(code)
    if remaining <= LOW_STOCK_THRESHOLD:
        try:
            await bot.send_message(
                ADMIN_ID,
                f"{MSG_SHIELD} <b>Low Stock Alert</b>\n\n{flag} {name}: only <b>{remaining}</b> left!"
            )
        except: pass

    # Start 20-minute auto-refund timer
    if uid in _assign_timers:
        _assign_timers[uid].cancel()
    _assign_timers[uid] = asyncio.create_task(
        auto_refund_timer(uid, assign_id, price, acc["phone"])
    )
    _otp_retries[uid] = 0

    kb_otp = InlineKeyboardMarkup(inline_keyboard=[
        [ib("Get OTP", "success", icon=BEID_BADGE, callback_data="fetch_otp")],
        [ib("Support", "danger", icon=BEID_SHIELD,  callback_data="open_support")],
    ])
    await cb.message.edit_text(
        f"{MSG_CHECK_ANIM} <b>CONGRATULATIONS — NUMBER SUCCESSFULLY ASSIGNED!</b>\n"
        f"<i>Your details are mentioned below.</i>\n\n"
        f"<blockquote>"
        f"{MSG_TG} Country : <b>{name}</b>\n"
        f"{MSG_QR_CODE} Number : <code>{acc['phone']}</code>\n"
        f"{MSG_COIN} Cost : <b>₹{price:.0f}</b>"
        f"</blockquote>\n\n"
        f"{MSG_BUY_BTN} Open Telegram, enter this number &amp; tap <b>Send Code</b> — then press <b>Get OTP</b> below.",
        reply_markup=kb_otp
    )

# ─────────────────────────────────────────
#  GET OTP
# ─────────────────────────────────────────
_otp_msg_ids:   dict = {}
_otp_retries:   dict = {}   # uid -> retry count
_assign_timers: dict = {}   # uid -> asyncio.Task

OTP_MAX_RETRIES = 7
OTP_REFUND_MINS = 20

def do_refund_and_cancel(assign: dict) -> float:
    """Cancel assignment and refund price to user. Returns amount refunded."""
    price = float(assign.get("price", 0))
    uid   = assign["user_id"]
    complete_assignment(assign["id"], "refunded")
    update_balance(uid, price)
    return price

async def auto_refund_timer(uid: int, assign_id: int, price: float, phone: str):
    """Wait OTP_REFUND_MINS, then auto-refund if assignment is still active."""
    await asyncio.sleep(OTP_REFUND_MINS * 60)
    assign = get_active_assignment(uid)
    if assign and assign["id"] == assign_id:
        do_refund_and_cancel(assign)
        _otp_retries.pop(uid, None)
        _assign_timers.pop(uid, None)
        try:
            await bot.send_message(
                uid,
                f"{MSG_MONEY} <b>Auto-Refund Processed</b>\n\n"
                f"<blockquote>"
                f"No OTP was received within <b>{OTP_REFUND_MINS} minutes</b> for <code>{phone}</code>.\n"
                f"Your payment of <b>₹{price:.0f}</b> has been fully refunded to your wallet.\n"
                f"The number has been cancelled automatically."
                f"</blockquote>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [ib("Buy Again", "primary", icon=BEID_PHONE,  callback_data="go_buy")],
                    [ib("Support",   "danger",  icon=BEID_SHIELD, callback_data="open_support")],
                ])
            )
        except Exception as ex:
            logger.warning(f"auto_refund_timer alert failed: {ex}")

@dp.callback_query(F.data == "fetch_otp")
async def fetch_otp(event):
    is_cb  = isinstance(event, CallbackQuery)
    uid    = event.from_user.id
    msg    = event.message if is_cb else event
    assign = get_active_assignment(uid)

    if not assign:
        txt = "No active number. Buy a number first."
        if is_cb: await event.answer(txt, show_alert=True)
        else:     await msg.answer(txt)
        return

    if is_cb: await event.answer("Fetching OTP…")

    # ── Retry gate ──────────────────────────────────────────────
    retries = _otp_retries.get(uid, 0) + 1
    _otp_retries[uid] = retries
    if retries > OTP_MAX_RETRIES:
        price_refunded = do_refund_and_cancel(assign)
        _otp_retries.pop(uid, None)
        t = _assign_timers.pop(uid, None)
        if t: t.cancel()
        await bot.send_message(
            uid,
            f"{MSG_MONEY} <b>Max Retries Reached — Auto-Refund Processed</b>\n\n"
            f"<blockquote>"
            f"You have attempted to fetch the OTP <b>{OTP_MAX_RETRIES} times</b> without success.\n"
            f"Your payment of <b>₹{price_refunded:.0f}</b> has been fully refunded to your wallet.\n"
            f"The number has been cancelled automatically."
            f"</blockquote>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [ib("Buy Again", "primary", icon=BEID_PHONE,  callback_data="go_buy")],
                [ib("Support",   "danger",  icon=BEID_SHIELD, callback_data="open_support")],
            ])
        )
        return
    # ────────────────────────────────────────────────────────────

    wait = await msg.answer(f"<i>Checking messages for <code>{assign['phone']}</code>…</i>")
    otp  = await tg_get_otp(assign["session_file"])
    flag = COUNTRIES.get(assign.get("country_code", "IN"), ("", "🌍", 0, ""))[1]

    twofa_pass = ""
    with get_db() as c:
        acc_row = c.execute("SELECT twofa_pass FROM accounts WHERE phone=?", (assign["phone"],)).fetchone()
        if acc_row and acc_row["twofa_pass"]:
            twofa_pass = acc_row["twofa_pass"]

    MAX_ATTEMPTS = 15
    attempt = 0
    while not otp and attempt < MAX_ATTEMPTS:
        attempt += 1
        dots = "." * (attempt % 4 + 1)
        try:
            await wait.edit_text(
                f"<i>Waiting for OTP on <code>{assign['phone']}</code>{dots} ({attempt}/{MAX_ATTEMPTS})</i>"
            )
        except: pass
        await asyncio.sleep(4)
        otp = await tg_get_otp(assign["session_file"])

    twofa_line = f"\n{MSG_SHIELD} <b>2FA Password:</b> <code>{twofa_pass}</code>" if twofa_pass else ""

    if otp:
        complete_assignment(assign["id"], "completed")
        asyncio.create_task(tg_logout_session(assign["session_file"]))
        _otp_msg_ids.pop(uid, None)
        _otp_retries.pop(uid, None)
        t = _assign_timers.pop(uid, None)
        if t: t.cancel()
        try: await wait.delete()
        except: pass

        kb_after = InlineKeyboardMarkup(inline_keyboard=[
            [ib("Buy Again", "primary", icon=BEID_PHONE, callback_data="go_buy")],
            [ib("Support",   "danger",  icon=BEID_SHIELD, callback_data="open_support")],
        ])
        await bot.send_message(
            uid,
            f"{MSG_OTP_FLASH} <b>Your OTP is ready:</b> <code>{otp}</code>"
            f"{twofa_line}\n\n"
            f"<blockquote>{MSG_CHECK_ANIM} Session logged out automatically.\n"
            f"<i>Thank you for using ByteOTP!</i></blockquote>\n\n"
            f"<i>You can buy another number anytime.</i>",
            reply_markup=kb_after
        )
    else:
        tries_left = max(0, OTP_MAX_RETRIES - retries)
        try: await wait.delete()
        except: pass
        await bot.send_message(
            uid,
            f"{MSG_CROSS} <b>OTP Not Received</b>\n\n"
            f"<blockquote>{flag} <code>{assign['phone']}</code>\n\n"
            f"<i>Checked for ~60s but no OTP arrived.\n"
            f"Make sure you entered this number on Telegram and tapped <b>Send Code</b>.</i>\n\n"
            f"{MSG_LOADING} Retries remaining: <b>{tries_left}</b></blockquote>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [ib("Try Again", "primary", icon=BEID_BADGE,  callback_data="fetch_otp")],
                [ib("Support",   "danger",  icon=BEID_SHIELD, callback_data="open_support")],
            ])
        )

@dp.callback_query(F.data.startswith("done_otp_"))
async def mark_done_otp(cb: CallbackQuery):
    await cb.answer("Logging out & cleaning up…")
    uid       = cb.from_user.id
    assign_id = int(cb.data.split("done_otp_", 1)[1])
    assign    = None
    with get_db() as c:
        row = c.execute("SELECT * FROM assignments WHERE id=?", (assign_id,)).fetchone()
        if row: assign = dict(row)
    complete_assignment(assign_id, "completed")
    if assign:
        asyncio.create_task(tg_logout_session(assign["session_file"]))
    _otp_msg_ids.pop(uid, None)
    await bot.send_message(
        uid,
        f"{MSG_CHECK_ANIM} <b>All Done!</b>\n\n"
        f"<blockquote><i>Session logged out &amp; cleaned automatically.</i></blockquote>\n\n"
        f"<i>Thank you for using ByteOTP. Buy another number anytime.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [ib("Buy Again", "primary", icon=BEID_PHONE, callback_data="go_buy")],
            [ib("Support", "danger", icon=BEID_SHIELD,  callback_data="open_support")],
        ])
    )

@dp.callback_query(F.data.startswith("done_"))
async def mark_done(cb: CallbackQuery):
    if cb.data.startswith("done_otp_"):
        return
    await cb.answer()
    assign_id = int(cb.data.split("_", 1)[1])
    complete_assignment(assign_id, "completed")
    await cb.message.edit_text(
        f"{MSG_CHECK_ANIM} <b>Marked as Completed!</b>\n\n"
        f"<blockquote><i>Thank you for using ByteOTP. Buy another number anytime.</i></blockquote>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [ib("Buy Again", "primary", icon=BEID_PHONE, callback_data="go_buy")],
            [ib("Support", "danger", icon=BEID_SHIELD,  callback_data="open_support")],
        ])
    )

@dp.callback_query(F.data == "go_buy")
async def go_buy_cb(cb: CallbackQuery):
    await cb.answer()
    kb_buy = InlineKeyboardMarkup(inline_keyboard=[
        [ib("Telegram Number", "primary", icon=BEID_PHONE, callback_data="platform_telegram")],
        [ib("Cancel",                        "danger",  callback_data="cancel_buy")],
    ])
    await cb.message.edit_text(
        f"{MSG_BUY_NUMBER} <b>Buy a Number</b>\n\n"
        f"<blockquote><i>Select the platform you need it for:</i></blockquote>",
        reply_markup=kb_buy
    )

# ─────────────────────────────────────────
#  MY NUMBERS HISTORY
# ─────────────────────────────────────────
@dp.message(F.text.startswith("\U0001f4d2") | (F.text == "My Numbers") | F.text.contains("My Numbers"))
async def my_numbers(msg: Message):
    uid = msg.from_user.id
    ensure_user(uid, msg.from_user.full_name, msg.from_user.username or "")
    if is_banned(uid):
        await msg.answer(f"{MSG_SHIELD} <b>Account suspended.</b>")
        return

    history = get_user_history(uid)

    if not history:
        kb_first = InlineKeyboardMarkup(inline_keyboard=[
            [ib("Buy Your First Number!", "success", icon=BEID_GET_NUMBER, callback_data="go_buy")],
        ])
        await msg.answer(
            f"{MSG_STAR} <b>My Numbers</b>\n\n"
            f"<blockquote>"
            f"{MSG_SPARKLE} <i>You haven't bought any numbers yet!</i>\n\n"
            f"{MSG_TICK} <b>Instant delivery</b> after payment\n"
            f"{MSG_SHIELD} <b>Secure</b> encrypted sessions\n"
            f"{MSG_DIAMOND} <b>Premium</b> verified accounts"
            f"</blockquote>\n\n"
            f"<i>Tap below to get started:</i>",
            reply_markup=kb_first
        )
        return

    active = get_active_assignment(uid)
    lines  = [f"{MSG_STAR} <b>Your Number History</b>\n"]
    for h in history:
        flag   = COUNTRIES.get(h.get("country_code", "IN"), ("", "🌍", 0, ""))[1]
        cname  = COUNTRIES.get(h.get("country_code", "IN"), ("Unknown", "", 0, ""))[0]
        dt     = h["assigned_at"][:16].replace("T", " ")
        status = h.get("status", "active")
        s_icon = {"active": MSG_LOADING, "completed": MSG_CHECK_ANIM, "released": MSG_CHECK_BLUE, "failed": MSG_CROSS}.get(status, MSG_LOADING)
        lines.append(
            f"{s_icon} <code>{h['phone']}</code>\n"
            f"   {flag} <b>{cname}</b>  |  ₹{h['price']:.0f}  |  <i>{dt}</i>\n"
        )

    if active:
        kb_hist = InlineKeyboardMarkup(inline_keyboard=[
            [ib("Get OTP", "success", icon=BEID_BADGE, callback_data="fetch_otp")],
            [ib("Buy More", "primary", icon=BEID_PHONE, callback_data="go_buy")],
        ])
    else:
        kb_hist = InlineKeyboardMarkup(inline_keyboard=[
            [ib("Buy Another Number", "primary", icon=BEID_PHONE, callback_data="go_buy")],
        ])

    await msg.answer("\n".join(lines), reply_markup=kb_hist)

# ─────────────────────────────────────────
#  SUPPORT SYSTEM
# ─────────────────────────────────────────
@dp.message(Command("support"))
@dp.message(F.text.startswith("\U0001f6e1") | (F.text == "Support") | F.text.contains("Support"))
@dp.callback_query(F.data == "open_support")
async def support_cmd(event):
    is_cb = isinstance(event, CallbackQuery)
    uid   = event.from_user.id
    if is_banned(uid):
        txt = "Account suspended."
        if is_cb: await event.answer(txt, show_alert=True)
        else:     await event.answer(txt)
        return
    text = (
        f"{MSG_SHIELD} <b>Support Center</b>\n\n"
        f"<blockquote><i>How can we help you today?\nChoose an option below:</i></blockquote>"
    )
    if is_cb:
        await event.answer()
        await event.message.edit_text(text, reply_markup=support_main_ikb())
    else:
        await event.answer(text, reply_markup=support_main_ikb())

@dp.callback_query(F.data == "support_complaint")
async def support_complaint_cb(cb: CallbackQuery):
    await cb.answer()
    await cb.message.edit_text(
        f"{MSG_SHIELD} <b>File a Complaint</b>\n\n"
        f"<blockquote><i>Select the subject of your issue:</i></blockquote>",
        reply_markup=support_issues_ikb()
    )

@dp.callback_query(F.data == "support_back")
async def support_back_cb(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await cb.message.edit_text(
        f"{MSG_SHIELD} <b>Support Center</b>\n\n"
        f"<blockquote><i>How can we help you today?</i></blockquote>",
        reply_markup=support_main_ikb()
    )

@dp.callback_query(F.data.startswith("issue_"))
async def issue_selected(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    issue = cb.data.split("issue_", 1)[1]
    labels = {
        "refund":      "Refund Request",
        "wrong_creds": "Wrong Credentials",
        "no_otp":      "OTP Not Received",
        "balance":     "Balance Issue",
        "bug":         "Bug / Error",
        "other":       "Other",
    }
    await state.update_data(issue_type=issue)
    await state.set_state(SupportState.message)
    await cb.message.edit_text(
        f"{MSG_BULB} <b>{labels.get(issue, issue)}</b>\n\n"
        f"<blockquote><i>Describe your problem in as much detail as possible:</i></blockquote>"
    )

@dp.callback_query(F.data == "cancel_support")
async def cancel_support_cb(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await cb.message.edit_text(f"{MSG_CROSS} <b>Cancelled.</b>")

@dp.message(SupportState.message)
async def support_message(msg: Message, state: FSMContext):
    uid        = msg.from_user.id
    data       = await state.get_data()
    issue_type = data.get("issue_type", "other")
    ticket_id  = create_ticket(uid, issue_type, msg.text)
    await state.clear()
    await msg.answer(
        f"{MSG_CHECK_ANIM} <b>Ticket #{ticket_id} Submitted!</b>\n\n"
        f"<blockquote>"
        f"{MSG_TICK} Issue: <b>{issue_type}</b>\n"
        f"{MSG_TICK} Our support team will reply shortly."
        f"</blockquote>",
        reply_markup=main_kb(uid)
    )
    u    = msg.from_user
    un   = f"@{u.username}" if u.username else f"ID: {uid}"
    try:
        kb_ticket = InlineKeyboardMarkup(inline_keyboard=[
            [ib(f"Reply & Close #{ticket_id}", "success", icon=BEID_CHECK, callback_data=f"adm_reply_{ticket_id}_{uid}")]
        ])
        await bot.send_message(
            ADMIN_ID,
            f"{MSG_SHIELD} <b>New Ticket #{ticket_id}</b>\n\n"
            f"<blockquote>User: {u.full_name} ({un})\n"
            f"Issue: <b>{issue_type}</b>\n\n"
            f"<i>{msg.text}</i></blockquote>",
            reply_markup=kb_ticket
        )
    except: pass

# ─────────────────────────────────────────
#  ADMIN PANEL
# ─────────────────────────────────────────
@dp.message(F.text.startswith("\U0001f451") | (F.text == "Admin Panel") | F.text.contains("Admin Panel"))
@dp.message(Command("admin"))
async def admin_panel(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer(f"{MSG_SHIELD} <b>Access denied.</b>")
        return
    s = get_stats()
    await msg.answer(
        f"{MSG_CROWN} <b>Admin Panel</b>\n\n"
        f"<blockquote>"
        f"{MSG_BOX} Accounts: <b>{s['total']}</b>  |  Live: <b>{s['avail']}</b>\n"
        f"{MSG_GEAR} Unreleased: <b>{s['unreleased']}</b>  |  Assigned: <b>{s['assigned']}</b>\n"
        f"{MSG_COIN} Users: <b>{s['users']}</b>  |  Sales: <b>₹{s['total_sales']:.0f}</b>\n"
        f"{MSG_SHIELD} Open Tickets: <b>{s['open_tickets']}</b>"
        f"</blockquote>",
        reply_markup=admin_ikb()
    )

@dp.callback_query(F.data == "adm_home")
async def adm_home_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("Access denied.", show_alert=True)
        return
    s = get_stats()
    await cb.message.edit_text(
        f"{MSG_CROWN} <b>Admin Panel</b>\n\n"
        f"<blockquote>"
        f"{MSG_BOX} Accounts: <b>{s['total']}</b>  |  Live: <b>{s['avail']}</b>\n"
        f"{MSG_GEAR} Unreleased: <b>{s['unreleased']}</b>  |  Assigned: <b>{s['assigned']}</b>\n"
        f"{MSG_COIN} Users: <b>{s['users']}</b>  |  Sales: <b>₹{s['total_sales']:.0f}</b>\n"
        f"{MSG_SHIELD} Open Tickets: <b>{s['open_tickets']}</b>"
        f"</blockquote>",
        reply_markup=admin_ikb()
    )
    await cb.answer()

@dp.callback_query(F.data == "adm_stats")
async def adm_stats_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    s            = get_stats()
    db_countries = get_countries_in_db()
    lines        = [f"{MSG_STAR_BLUE} <b>Inventory &amp; Stats</b>\n"]
    for code in db_countries:
        info = COUNTRIES.get(code)
        if not info:
            name, flag = code, "🌍"
        else:
            name, flag, _, _ = info
        live       = get_stock_count(code)
        unreleased = get_unreleased_count(code)
        price      = get_country_price(code)
        lines.append(f"{MSG_TICK} {flag} <b>{name}</b>: {live} live, {unreleased} pending  |  ₹{price:.0f}")
    if not db_countries:
        lines.append("<i>No accounts added yet.</i>")
    lines.append(
        f"\n{MSG_COIN} Total users: <b>{s['users']}</b>\n"
        f"{MSG_GEAR} Active assignments: <b>{s['assigned']}</b>\n"
        f"{MSG_DOLLAR} Total sales: <b>₹{s['total_sales']:.0f}</b>\n"
        f"{MSG_SHIELD} Open tickets: <b>{s['open_tickets']}</b>"
    )
    await cb.message.edit_text("\n".join(lines), reply_markup=back_ikb())

@dp.callback_query(F.data == "adm_list")
async def adm_list_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    accs = get_all_accounts()
    if not accs:
        await cb.message.edit_text("<b>No accounts yet.</b>", reply_markup=back_ikb())
        return
    lines = []
    for a in accs:
        st   = "✅" if (a["is_available"] and a["is_released"]) else ("📥" if not a["is_released"] else "🔴")
        info = COUNTRIES.get(a.get("country_code", "IN"))
        flag = info[1] if info else "🌍"
        lines.append(f"{st} {flag} <code>{a['phone']}</code>  <i>#{a['id']}</i>")
    await cb.message.edit_text(
        f"{MSG_BOX} <b>Accounts ({len(accs)})</b>\n\n" + "\n".join(lines),
        reply_markup=back_ikb()
    )

@dp.callback_query(F.data == "adm_users")
async def adm_users_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    users = get_all_users()
    if not users:
        await cb.message.edit_text("<b>No users yet.</b>", reply_markup=back_ikb())
        return
    lines = []
    for u in users:
        ban = " 🚫" if u["is_banned"] else ""
        lines.append(f"{MSG_TICK} <code>{u['user_id']}</code> {u['name'] or 'N/A'}  {MSG_COIN}₹{u.get('balance',0):.0f}{ban}")
    await cb.message.edit_text(
        f"{MSG_GEAR} <b>Users ({len(users)})</b>\n\n" + "\n".join(lines),
        reply_markup=back_ikb()
    )

@dp.callback_query(F.data == "adm_close")
async def adm_close_cb(cb: CallbackQuery):
    await cb.message.edit_text("<i>Admin panel closed.</i>")
    await cb.answer()

# ─── RELEASE STOCK ───────────────────────
@dp.callback_query(F.data == "adm_release_stock")
async def adm_release_stock_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    db_countries = get_countries_in_db()
    btns = []
    for i, code in enumerate(db_countries):
        pending = get_unreleased_count(code)
        if pending > 0:
            info  = COUNTRIES.get(code)
            name  = info[0] if info else code
            flag  = info[1] if info else "🌍"
            style = "primary" if i % 2 == 0 else "success"
            btns.append([ib(
                f"{flag} {name}  —  {pending} pending  → Release",
                style,
                callback_data=f"rel_stock_{code}"
            )])
    if not btns:
        await cb.message.edit_text(f"{MSG_CHECK} <b>No pending stock to release.</b>", reply_markup=back_ikb())
        return
    btns.append([ib("Back", "primary", callback_data="adm_home")])
    await cb.message.edit_text(
        f"{MSG_BOX} <b>Release Stock</b>\n\n<blockquote><i>Tap a country to make numbers live:</i></blockquote>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
    )

@dp.callback_query(F.data.startswith("rel_stock_"))
async def do_release_stock(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    code  = cb.data.split("rel_stock_", 1)[1]
    count = release_stock(code)
    info  = COUNTRIES.get(code, ("Unknown", "🌍", 0, ""))
    name, flag = info[0], info[1]
    await cb.message.edit_text(
        f"{MSG_CHECK_ANIM} Released <b>{count}</b> accounts for {flag} <b>{name}</b>!",
        reply_markup=back_ikb("adm_release_stock")
    )

# ─── RELEASE USER NUMBER ──────────────────
@dp.callback_query(F.data == "adm_release")
async def adm_release_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    asgns = get_all_assignments()
    if not asgns:
        await cb.message.edit_text("No active assignments.", reply_markup=back_ikb())
        return
    btns = []
    for i, a in enumerate(asgns):
        info  = COUNTRIES.get(a.get("country_code", "IN"))
        flag  = info[1] if info else "🌍"
        style = "primary" if i % 2 == 0 else "success"
        btns.append([ib(
            f"{a['name'] or a['user_id']} → {flag} {a['phone']}",
            style,
            callback_data=f"release_{a['user_id']}"
        )])
    btns.append([ib("Back", "primary", callback_data="adm_home")])
    await cb.message.edit_text(
        f"{MSG_CHECK} <b>Select user to release:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
    )

@dp.callback_query(F.data.startswith("release_"))
async def do_release_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    uid = int(cb.data.split("_", 1)[1])
    release_user_assignment(uid)
    await cb.message.edit_text(f"{MSG_CHECK} Released for user {uid}.", reply_markup=back_ikb())
    try:
        await bot.send_message(
            uid,
            f"{MSG_SPARKLE} <b>Your number has been released.</b>\n\n<i>You can buy a new one anytime.</i>"
        )
    except: pass

# ─── DELETE ACCOUNT ───────────────────────
@dp.callback_query(F.data == "adm_delete")
async def adm_delete_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    accs = get_all_accounts()
    if not accs:
        await cb.message.edit_text("No accounts.", reply_markup=back_ikb())
        return
    btns = []
    for i, a in enumerate(accs):
        st    = "✅" if a["is_available"] else "🔴"
        info  = COUNTRIES.get(a.get("country_code", "IN"))
        flag  = info[1] if info else "🌍"
        style = "primary" if i % 2 == 0 else "success"
        btns.append([ib(f"{st} {flag} {a['phone']}", style, callback_data=f"delacc_{a['id']}")])
    btns.append([ib("Back", "primary", callback_data="adm_home")])
    await cb.message.edit_text(
        f"<b>Select account to delete:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
    )

@dp.callback_query(F.data.startswith("delacc_"))
async def del_acc_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    acc_id = int(cb.data.split("_")[1])
    with get_db() as c:
        acc = c.execute("SELECT * FROM accounts WHERE id=?", (acc_id,)).fetchone()
    if not acc:
        await cb.message.edit_text("Not found.", reply_markup=back_ikb())
        return
    acc    = dict(acc)
    kb_del = InlineKeyboardMarkup(inline_keyboard=[
        [ib("Delete", "danger",  callback_data=f"confirmdel_{acc_id}"),
         ib("Cancel", "primary", callback_data="adm_delete")],
    ])
    await cb.message.edit_text(
        f"<b>Delete <code>{acc['phone']}</code>?</b>\n\n"
        f"<blockquote><i>This action cannot be undone.</i></blockquote>",
        reply_markup=kb_del
    )

@dp.callback_query(F.data.startswith("confirmdel_"))
async def confirm_del_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    acc_id = int(cb.data.split("_")[1])
    sf = delete_account_db(acc_id)
    if sf:
        for ext in [".session", ".session-journal"]:
            p = sf + ext
            if os.path.exists(p): os.remove(p)
    await cb.message.edit_text(f"{MSG_CHECK} <b>Deleted.</b>", reply_markup=back_ikb())

# ─── PROMO CODES ─────────────────────────
@dp.callback_query(F.data == "adm_promos")
async def adm_promos_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    with get_db() as c:
        promos = [dict(r) for r in c.execute("SELECT * FROM promo_codes ORDER BY id DESC LIMIT 20")]
    kb_promos = InlineKeyboardMarkup(inline_keyboard=[
        [ib("Create Code", "success", icon=BEID_CONFETTI, callback_data="adm_create_promo")],
        [ib("Back",                         "primary", callback_data="adm_home")],
    ])
    if not promos:
        await cb.message.edit_text(
            f"{MSG_CONFETTI} <b>Promo Codes</b>\n\nNo codes created yet.",
            reply_markup=kb_promos
        )
        return
    lines = [f"{MSG_CONFETTI} <b>Promo Codes</b>\n"]
    for p in promos:
        status = "✅" if p["is_active"] else MSG_CROSS
        lines.append(f"{status} <code>{p['code']}</code>  ₹{p['amount']:.0f}  {p['used_count']}/{p['max_uses']}")
    await cb.message.edit_text("\n".join(lines), reply_markup=kb_promos)

@dp.callback_query(F.data == "adm_create_promo")
async def adm_create_promo_cb(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    await cb.message.edit_text(
        f"{MSG_CONFETTI} <b>Create Promo Code</b>\n\n"
        f"<blockquote>Format: <code>CODE AMOUNT MAX_USES</code>\n\n"
        f"Example: <code>SAVE50 50 100</code>\n"
        f"<i>(Omit MAX_USES for single-use)</i></blockquote>"
    )
    await state.set_state(AdminStates.create_promo)

@dp.message(AdminStates.create_promo)
async def do_create_promo(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    parts = msg.text.strip().split()
    if len(parts) < 2:
        await msg.answer(f"{MSG_CROSS} Format: <code>CODE AMOUNT MAX_USES</code>")
        return
    try:
        code     = parts[0].upper()
        amount   = float(parts[1])
        max_uses = int(parts[2]) if len(parts) > 2 else 1
        ok       = create_promo(code, amount, max_uses)
        await state.clear()
        if ok:
            await msg.answer(
                f"{MSG_CONFETTI} Promo <code>{code}</code> created!\n"
                f"<blockquote>{MSG_COIN} Amount: ₹{amount:.0f}  |  Max uses: {max_uses}</blockquote>",
                reply_markup=main_kb(ADMIN_ID)
            )
        else:
            await msg.answer(f"{MSG_CROSS} Code already exists.", reply_markup=main_kb(ADMIN_ID))
    except:
        await msg.answer(f"{MSG_CROSS} Invalid format.", reply_markup=main_kb(ADMIN_ID))

# ─── SUPPORT TICKETS ──────────────────────
@dp.callback_query(F.data == "adm_tickets")
async def adm_tickets_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    tickets = get_open_tickets()
    if not tickets:
        await cb.message.edit_text(f"{MSG_CHECK} <b>No open tickets.</b>", reply_markup=back_ikb())
        return
    btns = []
    for i, t in enumerate(tickets):
        un    = f"@{t['username']}" if t.get("username") else str(t["user_id"])
        style = "primary" if i % 2 == 0 else "success"
        btns.append([ib(
            f"#{t['id']} {t['issue_type']} — {t['name'] or un}",
            style,
            callback_data=f"adm_ticket_{t['id']}_{t['user_id']}"
        )])
    btns.append([ib("Back", "primary", callback_data="adm_home")])
    await cb.message.edit_text(
        f"{MSG_SHIELD} <b>Open Tickets ({len(tickets)})</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
    )

@dp.callback_query(F.data.startswith("adm_ticket_"))
async def view_ticket_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    parts     = cb.data.split("_")
    ticket_id = int(parts[2])
    user_id   = int(parts[3])
    with get_db() as c:
        t = c.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        await cb.message.edit_text("Not found.", reply_markup=back_ikb("adm_tickets"))
        return
    t       = dict(t)
    kb_tick = InlineKeyboardMarkup(inline_keyboard=[
        [ib("Reply & Close", "success", icon=BEID_CHECK, callback_data=f"adm_reply_{ticket_id}_{user_id}")],
        [ib("Back",                        "primary", callback_data="adm_tickets")],
    ])
    await cb.message.edit_text(
        f"{MSG_SHIELD} <b>Ticket #{ticket_id}</b>\n"
        f"<blockquote>"
        f"Issue: <b>{t['issue_type']}</b>\n"
        f"Date: <i>{t['created_at'][:16]}</i>\n\n"
        f"{t['message']}"
        f"</blockquote>",
        reply_markup=kb_tick
    )

@dp.callback_query(F.data.startswith("adm_reply_"))
async def adm_reply_cb(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    parts     = cb.data.split("_")
    ticket_id = int(parts[2])
    user_id   = int(parts[3])
    await state.update_data(ticket_id=ticket_id, ticket_user=user_id)
    await state.set_state(AdminStates.reply_ticket)
    await cb.message.edit_text(
        f"{MSG_BULB} <b>Reply to Ticket #{ticket_id}</b>\n\n"
        f"<blockquote><i>Type your reply message:</i></blockquote>"
    )

@dp.message(AdminStates.reply_ticket)
async def do_reply_ticket(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    data      = await state.get_data()
    ticket_id = data["ticket_id"]
    user_id   = data["ticket_user"]
    close_ticket(ticket_id, msg.text)
    await state.clear()
    await msg.answer(f"{MSG_CHECK} Ticket #{ticket_id} closed.", reply_markup=main_kb(ADMIN_ID))
    try:
        await bot.send_message(
            user_id,
            f"{MSG_SHIELD} <b>Support Reply — Ticket #{ticket_id}</b>\n\n"
            f"<blockquote>{msg.text}\n\n"
            f"<i>Ticket closed. Contact support if the issue persists.</i></blockquote>"
        )
    except: pass

# ─── ADJUST BALANCE ───────────────────────
@dp.callback_query(F.data == "adm_adj_bal")
async def adm_adj_bal_cb(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    await cb.message.edit_text(
        f"{MSG_COIN} <b>Adjust User Balance</b>\n\n"
        f"<blockquote>Format: <code>USER_ID AMOUNT</code>\n"
        f"<i>(Negative value deducts balance)</i>\n"
        f"Example: <code>123456789 100</code></blockquote>"
    )
    await state.set_state(AdminStates.adjust_balance)

@dp.message(AdminStates.adjust_balance)
async def do_adjust_balance(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    parts = msg.text.strip().split()
    if len(parts) != 2 or not parts[0].lstrip("-").isdigit():
        await msg.answer(f"{MSG_CROSS} Format: <code>USER_ID AMOUNT</code>")
        return
    try:
        uid    = int(parts[0])
        amount = float(parts[1])
        with get_db() as c:
            exists = c.execute("SELECT user_id FROM users WHERE user_id=?", (uid,)).fetchone()
        if not exists:
            await msg.answer(f"{MSG_CROSS} User not found.")
            return
        update_balance(uid, amount)
        new_bal = get_balance(uid)
        await state.clear()
        await msg.answer(
            f"{MSG_CHECK_ANIM} <b>Balance Adjusted!</b>\n\n"
            f"<blockquote>"
            f"User: <code>{uid}</code>\n"
            f"{MSG_COIN} Adjustment: <b>₹{amount:+.2f}</b>\n"
            f"{MSG_COIN} New balance: <b>₹{new_bal:.2f}</b>"
            f"</blockquote>",
            reply_markup=main_kb(ADMIN_ID)
        )
        action = "added to" if amount >= 0 else "deducted from"
        try:
            await bot.send_message(
                uid,
                f"{MSG_COIN} <b>Wallet Updated!</b>\n\n"
                f"<blockquote>₹{abs(amount):.0f} has been {action} your wallet.\n"
                f"{MSG_CHECK} <b>New Balance:</b> ₹{new_bal:.2f}</blockquote>"
            )
        except: pass
    except:
        await msg.answer(f"{MSG_CROSS} Invalid input.")

# ─── SET PRICES ───────────────────────────
@dp.callback_query(F.data == "adm_prices")
async def adm_prices_cb(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    lines = [f"{MSG_DOLLAR} <b>Current Prices</b>\n"]
    for code, (name, flag, _, _) in COUNTRIES.items():
        price = get_country_price(code)
        lines.append(f"{MSG_TICK} {flag} {name} (<code>{code}</code>): ₹{price:.0f}")
    lines.append(f"\n<blockquote>Format: <code>COUNTRY_CODE PRICE</code>\nExample: <code>IN 60</code></blockquote>")
    await cb.message.edit_text("\n".join(lines))
    await state.set_state(AdminStates.set_price)

@dp.message(AdminStates.set_price)
async def do_set_price(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    parts = msg.text.strip().split()
    if len(parts) != 2:
        await msg.answer(f"{MSG_CROSS} Format: <code>COUNTRY_CODE PRICE</code>")
        return
    code = parts[0].upper()
    if code not in COUNTRIES:
        await msg.answer(f"{MSG_CROSS} Unknown code. Valid: {', '.join(COUNTRIES.keys())}")
        return
    try:
        price = float(parts[1])
        with get_db() as c:
            c.execute("INSERT OR REPLACE INTO country_prices (country_code, price) VALUES (?,?)", (code, price))
        await state.clear()
        name, flag, _, _ = COUNTRIES[code]
        await msg.answer(
            f"{MSG_CHECK} {flag} <b>{name}</b> price updated to <b>₹{price:.0f}</b>",
            reply_markup=main_kb(ADMIN_ID)
        )
    except:
        await msg.answer(f"{MSG_CROSS} Invalid price.")

# ─── BROADCAST ────────────────────────────
@dp.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_cb(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    await cb.message.edit_text(
        f"{MSG_SPARKLE} <b>Broadcast Message</b>\n\n"
        f"<blockquote><i>Send your message — it will be forwarded to all users:</i></blockquote>"
    )
    await state.set_state(AdminStates.broadcast)

@dp.message(AdminStates.broadcast)
async def do_broadcast(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    with get_db() as c:
        users = [r[0] for r in c.execute("SELECT user_id FROM users WHERE is_banned=0")]
    sent = 0
    for uid in users:
        try:
            await bot.send_message(uid, msg.text, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)
        except: pass
    await state.clear()
    await msg.answer(
        f"{MSG_CHECK_ANIM} Broadcast sent to <b>{sent}/{len(users)}</b> users.",
        reply_markup=main_kb(ADMIN_ID)
    )

# ─── BAN / UNBAN ──────────────────────────
@dp.callback_query(F.data == "adm_ban")
async def adm_ban_cb(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    await cb.message.edit_text(
        f"{MSG_SHIELD} <b>Ban User</b>\n\n<blockquote><i>Send the User ID to ban:</i></blockquote>"
    )
    await state.set_state(BanState.ban_uid)

@dp.message(BanState.ban_uid)
async def do_ban(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    if not msg.text.isdigit():
        await msg.answer(f"{MSG_CROSS} Enter a valid User ID (numbers only).")
        return
    uid = int(msg.text)
    with get_db() as c:
        c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
    await state.clear()
    await msg.answer(f"{MSG_SHIELD} User <code>{uid}</code> banned.", reply_markup=main_kb(ADMIN_ID))
    try: await bot.send_message(uid, f"{MSG_SHIELD} <b>Your account has been suspended.</b>")
    except: pass

@dp.callback_query(F.data == "adm_unban")
async def adm_unban_cb(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    await cb.message.edit_text(
        f"{MSG_SHIELD} <b>Unban User</b>\n\n<blockquote><i>Send the User ID to unban:</i></blockquote>"
    )
    await state.set_state(BanState.unban_uid)

@dp.message(BanState.unban_uid)
async def do_unban(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    if not msg.text.isdigit():
        await msg.answer(f"{MSG_CROSS} Enter a valid User ID.")
        return
    uid = int(msg.text)
    with get_db() as c:
        c.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (uid,))
    await state.clear()
    await msg.answer(f"{MSG_CHECK} User <code>{uid}</code> unbanned.", reply_markup=main_kb(ADMIN_ID))
    try: await bot.send_message(uid, f"{MSG_CHECK_ANIM} <b>Your account has been reinstated.</b>")
    except: pass

# ─── ADD ACCOUNT ──────────────────────────
@dp.callback_query(F.data == "adm_add")
async def adm_add_cb(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("Access denied.", show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_text(
        f"{MSG_TG} <b>Add Telegram Account</b>\n\n"
        f"<blockquote>Send phone number with country code:\n"
        f"Example: <code>+919876543210</code>\n\n"
        f"<i>Country is auto-detected from the prefix.\n"
        f"For +1 numbers, you will be asked USA or Canada.</i></blockquote>"
    )
    await state.set_state(AddAccount.phone)

@dp.message(AddAccount.phone)
async def add_phone(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    phone = msg.text.strip()
    if not phone.startswith("+") or not phone[1:].isdigit() or len(phone) < 10:
        await msg.answer(f"{MSG_CROSS} Format: <code>+919876543210</code>")
        return

    if phone.startswith("+1"):
        await state.update_data(phone=phone)
        await state.set_state(AddAccount.country_pick)
        kb_pick = InlineKeyboardMarkup(inline_keyboard=[
            [ib("🇺🇸 United States", "primary", callback_data="pick_country_US")],
            [ib("🇨🇦 Canada",        "success", callback_data="pick_country_CA")],
        ])
        await msg.answer(
            f"{MSG_TG} <b>+1 Number — Choose Country</b>\n\n"
            f"<blockquote>Phone: <code>{phone}</code>\n\n"
            f"<i>Is this a USA or Canada number?</i></blockquote>",
            reply_markup=kb_pick
        )
        return

    wait = await msg.answer(f"<i>Sending OTP to <code>{phone}</code>…</i>")
    ok, result = await tg_send_otp(phone)
    await wait.delete()
    if not ok:
        await msg.answer(f"{MSG_CROSS} {result}")
        await state.clear()
        return
    await state.update_data(phone=phone, country_override="")
    await state.set_state(AddAccount.otp)
    country = detect_country(phone)
    info    = COUNTRIES.get(country, ("Unknown", "🌍", 0, ""))
    await msg.answer(
        f"{MSG_CHECK} <b>OTP sent to <code>{phone}</code></b>\n"
        f"<blockquote>{MSG_TG} Detected: {info[1]} <b>{info[0]}</b>\n\n"
        f"<i>Enter the code you received:</i></blockquote>"
    )

@dp.callback_query(F.data.startswith("pick_country_"))
async def pick_country_cb(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID: return
    await cb.answer()
    chosen = cb.data.split("pick_country_", 1)[1]
    data   = await state.get_data()
    phone  = data.get("phone", "")
    if not phone:
        await cb.message.edit_text(f"{MSG_CROSS} Session expired. Start again.")
        await state.clear()
        return

    wait = await cb.message.answer(f"<i>Sending OTP to <code>{phone}</code>…</i>")
    ok, result = await tg_send_otp(phone)
    await wait.delete()
    if not ok:
        await cb.message.answer(f"{MSG_CROSS} {result}")
        await state.clear()
        return

    await state.update_data(country_override=chosen)
    await state.set_state(AddAccount.otp)
    info = COUNTRIES.get(chosen, ("Unknown", "🌍", 0, ""))
    await cb.message.answer(
        f"{MSG_CHECK} <b>OTP sent to <code>{phone}</code></b>\n"
        f"<blockquote>{MSG_TG} Country: {info[1]} <b>{info[0]}</b>\n\n"
        f"<i>Enter the code you received:</i></blockquote>"
    )

@dp.message(AddAccount.otp)
async def add_otp(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    code  = msg.text.strip().replace(" ", "")
    data  = await state.get_data()
    phone = data["phone"]
    cov   = data.get("country_override", "")
    ok, result = await tg_complete_login(phone, code, country_override=cov)
    if ok is None and result == "2FA_NEEDED":
        await state.set_state(AddAccount.passwd)
        await msg.answer(
            f"{MSG_SHIELD} <b>2FA Required</b>\n\n"
            f"<blockquote><i>This account has 2-Factor Authentication enabled.\n"
            f"Enter the 2FA password:</i></blockquote>"
        )
        return
    await state.clear()
    if ok:
        await msg.answer(
            f"{MSG_CHECK_ANIM} <b>{result}</b>\n\n"
            f"<blockquote>{MSG_TG} <code>{phone}</code> added to pool <i>(pending release)</i></blockquote>",
            reply_markup=main_kb(ADMIN_ID)
        )
    else:
        await msg.answer(f"{MSG_CROSS} {result}", reply_markup=main_kb(ADMIN_ID))

@dp.message(AddAccount.passwd)
async def add_2fa(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    data  = await state.get_data()
    phone = data["phone"]
    cov   = data.get("country_override", "")
    ok, result = await tg_complete_2fa(phone, msg.text.strip(), country_override=cov)
    await state.clear()
    if ok:
        await msg.answer(
            f"{MSG_CHECK_ANIM} <b>{result}</b>\n\n"
            f"<blockquote>{MSG_TG} <code>{phone}</code> added <i>(pending release)</i></blockquote>",
            reply_markup=main_kb(ADMIN_ID)
        )
    else:
        await msg.answer(f"{MSG_CROSS} {result}", reply_markup=main_kb(ADMIN_ID))

# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
async def main():
    init_db()
    while True:
        try:
            logger.info("ByteOTP Bot v3 starting (Bot API 9.4 + premium emoji in buttons)...")
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except Exception as ex:
            logger.error(f"Bot crashed: {ex}. Restarting in 5s…")
            await asyncio.sleep(5)
        finally:
            try: await bot.session.close()
            except: pass

if __name__ == "__main__":
    asyncio.run(main())
