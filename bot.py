import hashlib
import random
import string
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from google.cloud import firestore

# ==============================
# CONFIGURATION
# ==============================

BOT_TOKEN = "7255036978:AAG2Qjv-ZrbNRCBHPAv1MHukyo8W8qqsknI"  # <-- INSERT YOUR BOT TOKEN HERE

# Channels user must join
CHANNELS = [
    "Kanha_Codex",
    "KanhaApis",
    "KanhaCodex"
]

# Firebase Admin SDK (serviceAccount.json must be in same folder)
db = firestore.Client.from_service_account_json("serviceAccount.json")


# ==============================
# Generate Password
# ==============================
def generate_password(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


# ==============================
# SHA256 Hash
# ==============================
def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


# ==============================
# START COMMAND
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = "📌 *First join all channels to continue:*\n\n"
    for c in CHANNELS:
        text += f"👉 @{c}\n"

    keyboard = [[InlineKeyboardButton("✔ Verify", callback_data="verify")]]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


# ==============================
# VERIFY USER JOINED CHANNELS
# ==============================
async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer()

    missing = []

    # Check membership for each channel
    for ch in CHANNELS:
        try:
            member = await context.bot.get_chat_member(f"@{ch}", user_id)
            if member.status not in ["member", "administrator", "creator"]:
                missing.append(ch)
        except:
            missing.append(ch)

    # If missing channels
    if missing:
        txt = "❌ *You must join all required channels!*\n\nMissing:\n"
        for m in missing:
            txt += f"➡️ @{m}\n"
        await query.edit_message_text(txt, parse_mode="Markdown")
        return

    # All channels joined
    keyboard = [[InlineKeyboardButton("🔑 Generate Login Key", callback_data="gen_key")]]
    await query.edit_message_text(
        "✅ *Verification Successful!*\nClick below to generate your login key:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==============================
# GENERATE & SAVE LOGIN KEY
# ==============================
async def gen_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Generate random password for user
    plain = generate_password(8)
    hashed = sha256(plain)

    # Expire in 12 hours
    expiresAt = int(time.time() * 1000) + (12 * 60 * 60 * 1000)

    # Save to Firestore
    ref = db.collection("settings").document("loginPasswords")
    doc = ref.get()

    if doc.exists:
        arr = doc.to_dict().get("list", [])
    else:
        arr = []

    arr.append({
        "hash": hashed,
        "expiresAt": expiresAt
    })

    ref.set({"list": arr})

    # Send key to user
    msg = (
        "🎉 *Your Login Key is ready!*\n\n"
        f"`{plain}`\n\n"
        "⏳ Valid for *12 hours*.\n"
        "💻 Use it on the website login page."
    )

    await query.edit_message_text(msg, parse_mode="Markdown")


# ==============================
# START BOT
# ==============================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(verify, pattern="verify"))
app.add_handler(CallbackQueryHandler(gen_key, pattern="gen_key"))

print("🔥 BOT STARTED…")
app.run_polling()