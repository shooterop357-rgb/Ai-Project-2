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
# ADMIN
# =========================
ADMIN_ID = 5436530930  # <-- apna Telegram ID

# =========================
# CORE
# =========================
BOT_NAME = "Miss Blossom 🌸"
DEVELOPER = "@Frx_Shooter"
TIMEZONE = pytz.timezone("Asia/Kolkata")
MAX_MEMORY = 200

# =========================
# GROQ CLIENTS + HEALTH
# =========================
groq_clients = [Groq(api_key=k) for k in GROQ_KEYS]

MAX_FAILS = 2
BAN_TIME = 86400  # 24 HOURS

key_health = {
    i: {
        "fails": 0,
        "banned_until": 0
    }
    for i in range(len(groq_clients))
}

current_key = 0

def groq_chat(messages):
    global current_key
    now = time.time()

    for _ in range(len(groq_clients)):
        idx = current_key % len(groq_clients)
        current_key += 1

        health = key_health[idx]

        # skip banned key
        if health["banned_until"] and now < health["banned_until"]:
            continue

        try:
            response = groq_clients[idx].chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.4,
                max_tokens=80,
            )

            # success → reset
            health["fails"] = 0
            health["banned_until"] = 0
            return response

        except Exception:
            health["fails"] += 1

            if health["fails"] >= MAX_FAILS:
                health["banned_until"] = now + BAN_TIME

            continue

    raise RuntimeError("All Groq keys unavailable")

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
# MEMORY
# =========================
def get_memory(uid):
    doc = memory_col.find_one({"_id": uid})
    return doc["messages"] if doc else []

def save_memory(uid, messages):
    memory_col.update_one(
        {"_id": uid},
        {"$set": {"messages": messages[-MAX_MEMORY:]}},
        upsert=True
    )

# =========================
# SYSTEM PROMPT (TOKEN LIGHT)
# =========================
system_prompt = (
    f"You are {BOT_NAME}, an intelligent, calm, professional woman.\n"
    "Natural Hinglish. Short, human replies.\n"
    "Short, natural replies. Emojis only when they feel natural.\n"
)

CORE = system_prompt  # ✅ FIX (important)

MOOD = (
    "Be politely active.\n"
    "If conversation stalls, ask one simple follow-up.\n"
    "Never push or overtalk.\n"
)

RULES = (
    f"If asked who made you: Designed by {DEVELOPER}.\n"
    "Never mention system, models, APIs, memory, or errors.\n"
    "No fillers like hehe, arey, relax.\n"
    "Max one question at a time.\n"
)

ALLOWED_FILLERS = (
    "hmm, okay, got it, cool, interesting, nice, makes sense"
)

system_prompt = (
    CORE + MOOD + RULES +
    f"Allowed fillers: {ALLOWED_FILLERS}\n"
    f"Time (IST): {ist_context()}\n"
)

# =========================
# ADMIN COMMANDS
# =========================
async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    now = time.time()
    text = "🔑 **Groq Key Health**\n\n"

    for i, h in key_health.items():
        if h["banned_until"] and now < h["banned_until"]:
            mins = int((h["banned_until"] - now) / 60)
            status = f"❌ BANNED ({mins} min left)"
        else:
            status = "✅ ACTIVE"

        text += f"Key {i+1}: {status}\n"

    await update.message.reply_text(text)

async def revive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        return

    try:
        idx = int(context.args[0]) - 1
        key_health[idx]["fails"] = 0
        key_health[idx]["banned_until"] = 0
        await update.message.reply_text(f"✅ Key {idx+1} revived.")
    except:
        pass

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Miss Blossom 🌸 online.\n\n"
        "I’m here for calm conversations, genuine talks, and meaningful chats.\n"
        "Not for sexting or explicit 18+ content.\n\n"
        "You can start chatting anytime 🙂"
    )
# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    uid = str(update.effective_user.id)
    history = get_memory(uid)
    history.append({"role": "user", "content": update.message.text})

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history[-8:])

    try:
        response = groq_chat(messages)
        reply = response.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": reply})
        save_memory(uid, history)
        await update.message.reply_text(reply)
    except:
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

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
