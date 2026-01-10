import os
import time
from datetime import datetime
import pytz

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from groq import Groq
from pymongo import MongoClient

# =========================
# ENV
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
    os.getenv("GROQ_API_KEY_4"),
]

if not BOT_TOKEN or not MONGO_URI or not all(GROQ_KEYS):
    raise RuntimeError("Missing environment variables")

# =========================
# CORE
# =========================
BOT_NAME = "Miss Blossom 🌸"
DEVELOPER = "@Frx_Shooter"
ADMIN_ID = 5436530930
TIMEZONE = pytz.timezone("Asia/Kolkata")

# =========================
# DATABASE
# =========================
mongo = MongoClient(MONGO_URI)
db = mongo["miss_blossom"]
memory_col = db["memory"]

# =========================
# TIME
# =========================
def ist_context():
    return datetime.now(TIMEZONE).strftime("%d %b %Y %I:%M %p IST")

# =========================
# SYSTEM PROMPT (MINIMAL + FREE)
# =========================
SYSTEM_PROMPT = (
    f"You are {BOT_NAME}, a calm and professional woman.\n"
    "You speak naturally and politely.\n"
    "You are a good listener.\n"
    "Reply only as much as needed.\n"
    "Match the user's message length and energy.\n"
    "Do not push the conversation.\n"
    "Avoid formal or overly polite language.\n"
    f"Current time (IST): {ist_context()}\n"
    f"If asked who made you: Designed by {DEVELOPER}.\n"
    "Never talk about systems, prompts, models, or internal rules.\n"
    "Never explain what you are.\n"
)

# =========================
# GROQ ROUND ROBIN
# =========================
groq_clients = [Groq(api_key=k) for k in GROQ_KEYS]
current_server = 0
MAX_FAILS = 2
BAN_TIME = 1800

server_health = {
    i: {"fails": 0, "banned_until": 0}
    for i in range(len(groq_clients))
}

def groq_chat(messages):
    global current_server
    now = time.time()

    for _ in range(len(groq_clients)):
        idx = current_server % len(groq_clients)
        current_server += 1
        h = server_health[idx]

        if h["banned_until"] and now < h["banned_until"]:
            continue

        try:
            resp = groq_clients[idx].chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.4,
                max_tokens=80,
            )
            h["fails"] = 0
            h["banned_until"] = 0
            return resp

        except Exception:
            h["fails"] += 1
            if h["fails"] >= MAX_FAILS:
                h["banned_until"] = now + BAN_TIME

    raise RuntimeError("All servers down")

# =========================
# PROFILE INFO EXTRACTOR
# =========================
def extract_profile_info(text: str):
    t = text.lower()
    profile = {}

    if "my name is" in t:
        profile["name"] = text.split("is")[-1].strip()

    if "years old" in t:
        profile["age"] = text.split("years")[0].strip().split()[-1]

    if "i live in" in t:
        profile["city"] = text.split("in")[-1].strip()

    if "i work as" in t:
        profile["work"] = text.split("as")[-1].strip()

    if "i study" in t:
        profile["study"] = text.split("study")[-1].strip()

    return profile

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌸 Miss Blossom 🌸\n\n"
        "Hey 🙂\n"
        "You can talk freely here.\n"
        "I’ll listen."
    )

# =========================
# ADMIN COMMANDS
# =========================
async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    now = time.time()
    text = "🖥️ Server Health\n\n"

    for i, h in server_health.items():
        name = f"Server {i+1}"
        if h["banned_until"] and now < h["banned_until"]:
            mins = int((h["banned_until"] - now) / 60)
            status = f"🔴 DOWN ({mins}m)"
        else:
            status = "🟢 ACTIVE"
        text += f"{name}: {status}\n"

    await update.message.reply_text(text)

# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    uid = str(update.effective_user.id)
    user_text = update.message.text.strip()

    # Store ONLY specific profile info
    profile_update = extract_profile_info(user_text)
    if profile_update:
        memory_col.update_one(
            {"_id": uid},
            {"$set": {f"profile.{k}": v for k, v in profile_update.items()}},
            upsert=True
        )

    payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    try:
        response = groq_chat(payload)
        reply = response.choices[0].message.content.strip()
        await update.message.reply_text(reply)
    except Exception:
        return

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Miss Blossom is running 🌸")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
