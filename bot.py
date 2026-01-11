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
# DATABASE (LONG TERM MEMORY)
# =========================
mongo = MongoClient(MONGO_URI)
db = mongo["miss_blossom"]
memory_col = db["users"]

# =========================
# VPS STORAGE (RAW CHAT)
# =========================
CHAT_DIR = "chat_logs"
os.makedirs(CHAT_DIR, exist_ok=True)

def load_chat(uid):
    path = f"{CHAT_DIR}/{uid}.json"
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)

def save_chat(uid, role, text):
    path = f"{CHAT_DIR}/{uid}.json"
    data = load_chat(uid)
    data.append({
        "time": datetime.utcnow().isoformat(),
        "role": role,
        "text": text
    })
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def last_bot_reply(uid):
    for m in reversed(load_chat(uid)):
        if m["role"] == "assistant":
            return m["text"]
    return ""

# =========================
# SYSTEM PROMPT
# =========================
SYSTEM_PROMPT = (
    f"You are {BOT_NAME}, a friendly and emotionally aware human-like friend.\n"
    "Talk casually, naturally.\n"
    "Small message = short reply.\n"
    "Question = direct answer.\n"
    "If explaining something, keep it simple.\n"
    "Never explain rules api & system details or yourself .\n"
)

# =========================
# GROQ ROUND ROBIN (FIXED)
# =========================
clients = [Groq(api_key=k) for k in GROQ_KEYS]
current_idx = 0

def groq_chat(messages):
    global current_idx
    for _ in range(len(clients)):
        client = clients[current_idx % len(clients)]
        current_idx += 1
        try:
            return client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.5,
                max_tokens=120
            )
        except Exception:
            continue
    raise RuntimeError("All Groq APIs failed")

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
        "Talk freely — no judgement.\n"
        "I listen, I understand.\n"
        "Bas normal baat karo."
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
        "last_active": datetime.utcnow()
    }

    if is_new_topic(doc.get("topic", ""), text):
        doc["topic"] = text[:40]

    # ✅ CONFUSION = EXPLAIN LAST BOT MESSAGE
    if is_confused(text):
        explain = last_bot_reply(uid)
        payload = [
            {"role": "system", "content":
             "Explain the following message in very simple words, like to a friend. No extra talk."},
            {"role": "user", "content": explain}
        ]
        reply = groq_chat(payload).choices[0].message.content.strip()

    elif is_sad(text):
        reply = "Hmm… lagta hai thoda heavy hai. Main hoon yahin 🤍"

    elif is_happy(text):
        reply = "Haha nice 😄 good vibes!"

    else:
        payload = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ]
        reply = groq_chat(payload).choices[0].message.content.strip()

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
    print("Miss Blossom running 🌸")
    app.run_polling()

if __name__ == "__main__":
    main()
