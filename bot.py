import os
from datetime import datetime
import pytz

from telegram import Update
from telegram.constants import ChatAction
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
GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
    os.getenv("GROQ_API_KEY_4"),
]
MONGO_URI = os.getenv("MONGO_URI")

if not BOT_TOKEN or not MONGO_URI or not all(GROQ_KEYS):
    raise RuntimeError("Missing environment variables")

# =========================
# CORE
# =========================
BOT_NAME = "Miss Blossom 🌸"
DEVELOPER = "@Frx_Shooter"
TIMEZONE = pytz.timezone("Asia/Kolkata")
MAX_MEMORY = 200

# =========================
# GROQ CLIENTS (4 KEYS)
# =========================
groq_clients = [Groq(api_key=k) for k in GROQ_KEYS]

def groq_chat(messages):
    for client in groq_clients:
        try:
            # No retry, no sleep → instant switch
            return client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.45,
                max_tokens=120,
            )
        except Exception:
            continue
    raise RuntimeError("All Groq keys exhausted")

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

def is_important_memory(text: str) -> bool:
    keys = ["mera naam", "i am", "i live", "i like", "exam", "job", "college", "relationship"]
    return any(k in text.lower() for k in keys)

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
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome 👋\n\n"
        "I’m Miss Blossom (Beta) 🌸\n"
        "Calm chats, real vibes.\n\n"
        "You can start anytime 🙂"
    )

# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    uid = str(update.effective_user.id)
    user_text = update.message.text.strip()

    history = get_memory(uid)
    history.append({"role": "user", "content": user_text})

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history[-16:])  # strict token control

    try:
        response = groq_chat(messages)
        reply = response.choices[0].message.content.strip()

        if len(reply) > 30:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.TYPING
            )

        history.append({"role": "assistant", "content": reply})

        if is_important_memory(user_text):
            history.append({"role": "system", "content": "Remember user info."})

        save_memory(uid, history)
        await update.message.reply_text(reply)

    except Exception:
        return  # silent fail

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Miss Blossom is running 🌸")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
