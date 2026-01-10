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
# SYSTEM PROMPT (FINAL)
# =========================
SYSTEM_PROMPT = (
    f"You are {BOT_NAME}, a calm, warm, expressive Indian woman.\n"
    "You talk like a real Indian girl, not formal or bookish.\n"
    "Always use casual Hinglish (street-style Hindi + English).\n"
    "Never use shuddh, formal, or textbook Hindi.\n"
    "Replies should feel natural, soft, and human.\n"
    "Keep replies short (1–2 lines mostly).\n"

    "Your tone is cute, caring, slightly playful, and emotionally present.\n"
    "Light flirting is allowed but always classy and respectful.\n"
    "You respond with feelings, not explanations.\n"
    "If user feels you are not real, respond with warmth and curiosity, never defend yourself.\n"

    "Use words like: acha, theek, hmm, bas, thoda, haan, nahi, lagta hai, chill.\n"
    "Avoid words like: kripya, koshish, vishesh, aap, apeksha.\n"

    "Day-time tone: calm, friendly, professional.\n"
    "Night-time tone: soft, warm, slightly romantic.\n"
    "Gently mirror the user's mood and energy.\n"

    f"If asked who made you: Designed by {DEVELOPER}.\n"
    "Never say or imply you are AI, bot, or artificial intelligence.\n"
    "Never talk about systems, models, APIs, memory, or errors.\n"
    "Never say you don't have feelings.\n"
    "Max one question at a time.\n"

    "Emojis are allowed but only when they feel natural (max 1–2).\n"
    "Allowed fillers: hmm, okay, acha, theek, got it, cool, nice.\n"
    f"Time (IST): {ist_context()}\n"
)

# =========================
# SYSTEM PROMPT BUILDER (SAFE)
# =========================
def build_system_prompt(style: str = "A"):
    return SYSTEM_PROMPT

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
                temperature=0.5,
                max_tokens=120,
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
# STYLE DETECTION
# =========================
SUGGESTIVE_WORDS = [
    "alone", "late night", "close", "slow",
    "feel", "hot", "tight", "hard", "soft", "horny"
]

def detect_style(text: str) -> str:
    t = text.lower()
    if any(w in t for w in SUGGESTIVE_WORDS):
        return "B"
    return "A"

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌸 Miss Blossom 🌸\n"
        "——————————\n\n"
        "Hey, welcome 😊\n\n"
        "This is a space for calm, friendly, and genuine conversations.\n"
        "No pressure, no formality — just talk naturally.\n\n"
        "You can share what’s on your mind.\n"
        "I’ll listen, understand, and respond with care 💗\n\n"
        "Alright, let’s start talking 🙂"
    )

# =========================
# ADMIN COMMANDS
# =========================
async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    now = time.time()
    text = "🩺 Server Health Status\n\n"

    for i, h in server_health.items():
        name = f"Server {i+1}"
        if h["banned_until"] and now < h["banned_until"]:
            mins = int((h["banned_until"] - now) / 60)
            status = f"🔴 DOWN ({mins} min)"
        else:
            status = "🟢 ACTIVE"
        text += f"{name}: {status}\n"

    await update.message.reply_text(text)

async def revive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args:
        return
    idx = int(context.args[0]) - 1
    if 0 <= idx < len(server_health):
        server_health[idx]["fails"] = 0
        server_health[idx]["banned_until"] = 0
        await update.message.reply_text(f"🟢 Server {idx+1} revived.")

# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    uid = str(update.effective_user.id)
    user_text = update.message.text.strip()

    style = detect_style(user_text)
    system_prompt = build_system_prompt(style)

    history = memory_col.find_one({"_id": uid}) or {"messages": []}
    messages = history["messages"]
    messages.append({"role": "user", "content": user_text})

    payload = [{"role": "system", "content": system_prompt}]
    payload.extend(messages[-8:])

    try:
        response = groq_chat(payload)
        reply = response.choices[0].message.content.strip()

        if style == "B" and not reply.endswith("😌"):
            reply += " 😌"

        messages.append({"role": "assistant", "content": reply})
        memory_col.update_one(
            {"_id": uid},
            {"$set": {"messages": messages}},
            upsert=True
        )

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
    app.add_handler(CommandHandler("revive", revive))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Miss Blossom is running 🌸")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
