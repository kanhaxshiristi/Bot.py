import requests
import uuid
import time
import hashlib
import json
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ==============================
# CONFIG
# ==============================
BOT_TOKEN = "7255036978:AAG2Qjv-ZrbNRCBHPAv1MHukyo8W8qqsknI"
BOT_USERNAME = "NGTCPBOT"  # without @

VPLINK_API_KEY = "YOUR_VPLINK_API_KEY"

BASE_URL = f"https://t.me/{BOT_USERNAME}?start=verified-"

CHANNELS = [
    "@KanhaCodex",
    "@KanhaApis",
    "@Kanha_Codex"
]

SUPPORT_LINK = "https://t.me/AuraXseller"

PENDING_FILE = "pending.json"


# ==============================
# LOAD/SAVE PENDING
# ==============================
def load_pending():
    return json.load(open(PENDING_FILE, "r")) if os.path.exists(PENDING_FILE) else {}


def save_pending(data):
    json.dump(data, open(PENDING_FILE, "w"), indent=4)


pending = load_pending()


# ==============================
# VPLink Shortener
# ==============================
def generate_short_url(long_url):
    try:
        api = f"https://vplink.in/api?api={VPLINK_API_KEY}&url={long_url}"
        r = requests.get(api, timeout=10)
        data = r.json()
        if data.get("status") == "success":
            return data["shortenedUrl"]
        return long_url
    except:
        return long_url


# ==============================
# Verification Link Generator
# ==============================
def generate_verification_link(user_id):
    ts = int(time.time())
    rand = uuid.uuid4().hex[:6]
    return f"{BASE_URL}{user_id}-{ts}-{rand}"


# ==============================
# Firebase Setup
# ==============================
from google.cloud import firestore

db = firestore.Client.from_service_account_json("serviceAccount.json")


def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()


# ==============================
# START COMMAND HANDLER
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # If start parameter contains verification proof
    if text.startswith("/start verified-"):
        await handle_verified(update, context)
        return

    # Normal start = Show join channels
    msg = "🔐 *Join These Channels First:*\n\n"
    for ch in CHANNELS:
        msg += f"• {ch}\n"

    kb = [
        [InlineKeyboardButton("✔ Verify Join", callback_data="verify_join")]
    ]

    await update.message.reply_text(
        msg,
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )


# ==============================
# CHANNEL JOIN VERIFY
# ==============================
async def verify_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    uid = user.id

    # Check all channels
    for ch in CHANNELS:
        try:
            m = await context.bot.get_chat_member(ch, uid)
            if m.status not in ["member", "administrator", "creator"]:
                await q.answer("❌ Join all channels first!", show_alert=True)
                return
        except:
            await q.answer("❌ Join all channels first!", show_alert=True)
            return

    # Verified → Show Menu
    kb = [
        [InlineKeyboardButton("🎟 Generate Key", callback_data="gen_key")],
        [InlineKeyboardButton("🔑 My Keys", callback_data="my_keys")],
        [InlineKeyboardButton("📞 Contact", url=SUPPORT_LINK)],
        [InlineKeyboardButton("🌐 Website Login", url="https://yourwebsite.com/login")]
    ]

    await q.edit_message_text(
        "✅ Verified!\nChoose an option:",
        reply_markup=InlineKeyboardMarkup(kb)
    )


# ==============================
# Generate Key Button → VPLink Link
# ==============================
async def gen_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id

    pend = load_pending()
    pend[str(uid)] = True
    save_pending(pend)

    # Generate long verification link
    long_url = generate_verification_link(uid)
    short_url = generate_short_url(long_url)

    kb = [
        [InlineKeyboardButton("🔐 VERIFY HERE", url=short_url)],
        [InlineKeyboardButton("HELP", url=SUPPORT_LINK)]
    ]

    await q.edit_message_text(
        "🔐 *Click verify to get your 12-hour login key*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )


# ==============================
# Handle Verified Link
# ==============================
async def handle_verified(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    user = update.message.from_user
    uid = user.id

    # Check pending
    pend = load_pending()
    if str(uid) not in pend:
        await update.message.reply_text("❌ No verification request found.")
        return

    # Clear pending
    del pend[str(uid)]
    save_pending(pend)

    # Generate key
    plain = uuid.uuid4().hex[:8]
    hashed = hash_password(plain)
    expiresAt = int(time.time()) * 1000 + (12 * 60 * 60 * 1000)

    # Save to Firebase
    ref = db.collection("settings").document("loginPasswords")
    doc = ref.get()

    arr = doc.to_dict().get("list", []) if doc.exists else []
    arr.append({
        "hash": hashed,
        "expiresAt": expiresAt
    })

    ref.set({"list": arr})

    await update.message.reply_text(
        f"🎉 *Your 12-Hour Key:*\n\n`{plain}`\n\nUse it to login on the website.",
        parse_mode="Markdown"
    )


# ==============================
# My Keys
# ==============================
async def my_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id

    # Firebase does not store user-id wise keys
    # You want only latest key → fetch from Firestore
    ref = db.collection("settings").document("loginPasswords")
    doc = ref.get()

    if not doc.exists:
        await q.edit_message_text("❌ No keys found.")
        return

    data = doc.to_dict().get("list", [])
    data = sorted(data, key=lambda x: x["expiresAt"], reverse=True)

    latest = data[0]
    expires = latest["expiresAt"]

    left = expires - int(time.time() * 1000)

    if left <= 0:
        await q.edit_message_text("❌ Your key expired.")
        return

    hours = round(left / 3600000, 1)

    await q.edit_message_text(
        f"🔑 *Last Generated Key*\n\n"
        f"⏳ Valid for: {hours} hours more\n"
        f"(Raw key is NOT stored for security)",
        parse_mode="Markdown"
    )


# ==============================
# MAIN
# ==============================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(verify_join, pattern="verify_join"))
app.add_handler(CallbackQueryHandler(gen_key, pattern="gen_key"))
app.add_handler(CallbackQueryHandler(my_keys, pattern="my_keys"))

print("🚀 BOT STARTED!")
app.run_polling()