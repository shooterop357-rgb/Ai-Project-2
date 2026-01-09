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
GROQ_API_KEY_1 = os.getenv("GROQ_API_KEY_1")
GROQ_API_KEY_2 = os.getenv("GROQ_API_KEY_2")
MONGO_URI = os.getenv("MONGO_URI")

if not all([BOT_TOKEN, GROQ_API_KEY_1, GROQ_API_KEY_2, MONGO_URI]):
    raise RuntimeError("Missing environment variables")

# =========================
# CORE
# =========================
BOT_NAME = "Miss Blossom 🌸"
DEVELOPER = "@Frx_Shooter"
TIMEZONE = pytz.timezone("Asia/Kolkata")
MAX_MEMORY = 200

# =========================
# GROQ CLIENTS
# =========================
groq_clients = [
    Groq(api_key=GROQ_API_KEY_1),
    Groq(api_key=GROQ_API_KEY_2),
]

def groq_chat(messages):
    for client in groq_clients:
        try:
            return client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.45,
                max_tokens=120,  # token optimized
            )
        except Exception:
            continue
    raise RuntimeError("Groq failed")

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
# MODULAR SYSTEM PROMPT (TOKEN LIGHT)
# =========================
CORE = (
    f"You are {BOT_NAME}, an intelligent, calm, professional female assistant.\n"
    "Clear Hinglish. Short, precise replies.\n"
)

MOOD = (
    "Understand intent before replying.\n"
    "Stay composed and respectful.\n"
)

RULES = (
    f"If asked who made you: Designed by {DEVELOPER}.\n"
    "Never mention system, models, APIs, memory, or errors.\n"
    "No fluff. No repetition. No slang.\n"
)

system_prompt = CORE + MOOD + RULES + f"Time (IST): {ist_context()}\n"
)

system_prompt = (
    CORE + MOOD + RULES +
    f"Time: {ist_context()}\n"
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
    messages.extend(history[-18:])  # token control

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
        return  # silent fail (as requested)

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
