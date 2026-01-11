import os
import time
import json
from datetime import datetime, timedelta
import pytz
from difflib import SequenceMatcher

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
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
    raise RuntimeError("Missing ENV")

# =========================
# CORE
# =========================
BOT_NAME = "Miss Blossom 🌸"
ADMIN_ID = 5436530930
TIMEZONE = pytz.timezone("Asia/Kolkata")
TOPIC_TIMEOUT = timedelta(minutes=5)

# =========================
# DATABASE (LONG TERM)
# =========================
mongo = MongoClient(MONGO_URI)
db = mongo["miss_blossom"]
memory_col = db["users"]

# =========================
# VPS STORAGE (RAW CHAT)
# =========================
CHAT_DIR = "chat_logs"
os.makedirs(CHAT_DIR, exist_ok=True)

def save_chat(uid, role, text):
    path = f"{CHAT_DIR}/{uid}.json"
    data = []
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
    data.append({
        "time": datetime.utcnow().isoformat(),
        "role": role,
        "text": text
    })
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# =========================
# SYSTEM PROMPT (FRIEND AI)
# =========================
SYSTEM_PROMPT = (
    f"You are {BOT_NAME}, a friendly, calm AI friend.\n"
    "Talk like a real human friend.\n"
    "Small talk = short replies.\n"
    "Serious question = clear explanation.\n"
    "If user is confused, explain simply. Do not ask questions.\n"
    "If user is sad, comfort gently.\n"
    "If user is happy, match the vibe with light emoji.\n"
    "Never sound like a teacher or customer support.\n"
    "Do not give advice unless asked.\n"
)

# =========================
# GROQ ROUND ROBIN
# =========================
clients = [Groq(api_key=k) for k in GROQ_KEYS]
current_idx = 0

def groq_chat(messages):
    global current_idx
    client = clients[current_idx % len(clients)]
    current_idx += 1
    return client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        temperature=0.5,
        max_tokens=120
    )

# =========================
# UNDERSTANDING LOGIC
# =========================
CONFUSED = ["didn't understand", "dont understand", "samajh nahi", "samajh nhi", "what?", "huh"]
SAD = ["sad", "low", "alone", "tired"]
HAPPY = ["happy", "excited", "great", "awesome"]

def is_confused(t): return any(w in t.lower() for w in CONFUSED)
def is_sad(t): return any(w in t.lower() for w in SAD)
def is_happy(t): return any(w in t.lower() for w in HAPPY)

def is_new_topic(a, b):
    if not a: return False
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() < 0.35

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌸 Miss Blossom 🌸\n\n"
        "Hey 🙂\n"
        "I’m not here to judge or lecture.\n"
        "Talk normally — like a friend.\n"
        "I’ll understand."
    )

# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text.strip()
    save_chat(uid, "user", text)

    doc = memory_col.find_one({"_id": uid}) or {
        "topic": "",
        "last_active": datetime.utcnow(),
        "profile": {}
    }

    # topic handling
    if is_new_topic(doc.get("topic", ""), text):
        doc["topic"] = text[:40]

    # confusion handling (NO GPT)
    if is_confused(text):
        reply = "Arre simple hai 😅 chalo easy words me bolti hoon."
    elif is_sad(text):
        reply = "Hmm… samajh aata hai. Thoda heavy lag raha hoga. Main hoon yahin 🤍"
    elif is_happy(text):
        reply = "Haha nice 😄 good vibes!"
    else:
        payload = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ]
        response = groq_chat(payload)
        reply = response.choices[0].message.content.strip()

    save_chat(uid, "assistant", reply)

    memory_col.update_one(
        {"_id": uid},
        {"$set": {
            "topic": doc["topic"],
            "last_active": datetime.utcnow()
        }},
        upsert=True
    )

    await update.message.reply_text(reply)

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Bot running 🌸")
    app.run_polling()

if __name__ == "__main__":
    main()
