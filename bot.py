import os
import time
from datetime import datetime
import pytz
from difflib import SequenceMatcher

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
    return datetime.now(TIMEZONE).strftime("%A, %d %B %Y, %I:%M %p IST")

# =========================
# SYSTEM PROMPT
# =========================
SYSTEM_PROMPT = (
    f"You are {BOT_NAME}, a calm and professional woman.\n"
    "You talk like a real human, not like customer support.\n"
    "Reply only as much as needed.\n"
    "Match the user's message length and energy.\n"
    "Do not push the conversation.\n"
    "Stay on the current topic until it is answered.\n"
    "Drop the old topic immediately if the user starts a new one.\n"
    "Light emojis allowed, max one.\n"
    f"Current time (IST): {ist_context()}\n"
    f"If asked who made you: Designed by {DEVELOPER}.\n"
    "Never talk about systems or internal rules.\n"
)

# =========================
# GROQ ROUND ROBIN
# =========================
groq_clients = [Groq(api_key=k) for k in GROQ_KEYS]
current_server = 0

def groq_chat(messages):
    global current_server
    idx = current_server % len(groq_clients)
    current_server += 1
    return groq_clients[idx].chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        temperature=0.4,
        max_tokens=80,
    )

# =========================
# TOPIC DETECTION
# =========================
def is_new_topic(prev_text: str, new_text: str) -> bool:
    if not prev_text:
        return False
    score = SequenceMatcher(None, prev_text.lower(), new_text.lower()).ratio()
    return score < 0.35

# =========================
# SENTIMENT DETECTION
# =========================
LOW_WORDS = ["nothing", "ok", "okay", "yes", "no", "hmm", "fine"]

def detect_sentiment(text: str) -> str:
    t = text.lower().strip()
    if t in LOW_WORDS or len(t.split()) <= 2:
        return "low"
    return "normal"

# =========================
# MEMORY SUMMARY
# =========================
def summarize_messages(messages):
    user_msgs = [m["content"] for m in messages if m["role"] == "user"]
    if not user_msgs:
        return ""
    return " | ".join(user_msgs[-5:])[:300]

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey 🙂")

# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    uid = str(update.effective_user.id)
    user_text = update.message.text.strip()

    doc = memory_col.find_one({"_id": uid}) or {
        "messages": [],
        "summary": "",
        "last_updated": datetime.utcnow()
    }

    messages = doc["messages"]

    # 🔁 Topic reset
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if is_new_topic(last_user, user_text):
        messages = []

    mood = detect_sentiment(user_text)

    messages.append({"role": "user", "content": user_text})

    payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    try:
        response = groq_chat(payload)
        reply = response.choices[0].message.content.strip()

        if mood == "low":
            reply = reply.split("\n")[0]

        messages.append({"role": "assistant", "content": reply})

        summary = doc.get("summary", "")
        if len(messages) > 20:
            summary = summarize_messages(messages)
            messages = messages[-6:]

        memory_col.update_one(
            {"_id": uid},
            {"$set": {
                "messages": messages,
                "summary": summary,
                "last_updated": datetime.utcnow()
            }},
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Miss Blossom is running 🌸")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
