import os
import time
from datetime import datetime, timedelta
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

TOPIC_TIMEOUT = timedelta(minutes=5)

# =========================
# DATABASE
# =========================
mongo = MongoClient(MONGO_URI)
db = mongo["miss_blossom"]
memory_col = db["memory"]
debug_col = db["debug_logs"]

# =========================
# TIME
# =========================
def ist_context():
    return datetime.now(TIMEZONE).strftime("%A, %d %B %Y, %I:%M %p IST")

# =========================
# SYSTEM PROMPT (UNCHANGED)
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
# GROQ ROUND ROBIN + HEALTH (UNCHANGED)
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
            return resp, idx

        except Exception:
            h["fails"] += 1
            if h["fails"] >= MAX_FAILS:
                h["banned_until"] = now + BAN_TIME

    raise RuntimeError("All servers down")

# =========================
# HELPERS (UNCHANGED + SAFE ADD-ONS)
# =========================
SHORT_WORDS = {"ok", "okay", "yes", "no", "nothing", "hmm", "fine"}
CONTINUE_WORDS = {"tell me more", "more", "continue", "go on"}
UNLOCK_WORDS = {"by the way", "another thing", "new topic", "i want to ask"}

def is_short(text: str) -> bool:
    return text.lower().strip() in SHORT_WORDS or len(text.split()) <= 2

def wants_to_continue(text: str) -> bool:
    return text.lower().strip() in CONTINUE_WORDS

def wants_new_topic(text: str) -> bool:
    return any(w in text.lower() for w in UNLOCK_WORDS)

def is_new_topic(prev: str, curr: str) -> bool:
    if not prev:
        return False
    return SequenceMatcher(None, prev.lower(), curr.lower()).ratio() < 0.35

def log_debug(uid, data):
    debug_col.insert_one({
        "user": uid,
        "time": datetime.utcnow(),
        **data
    })

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌸 Miss Blossom 🌸\n\n"
        "Hey 🙂\n"
        "You can talk freely here.\n"
        "No pressure, no formality.\n"
        "I’m here to listen."
    )

# =========================
# ADMIN COMMANDS (UNCHANGED)
# =========================
async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    now = time.time()
    text = "🖥️ Server Health\n\n"

    for i, h in server_health.items():
        if h["banned_until"] and now < h["banned_until"]:
            mins = int((h["banned_until"] - now) / 60)
            status = f"🔴 DOWN ({mins}m)"
        else:
            status = "🟢 ACTIVE"
        text += f"Server {i+1}: {status}\n"

    await update.message.reply_text(text)

async def revive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args:
        return
    idx = int(context.args[0]) - 1
    if 0 <= idx < len(server_health):
        server_health[idx]["fails"] = 0
        server_health[idx]["banned_until"] = 0
        await update.message.reply_text(f"🟢 Server {idx+1} revived")

# =========================
# CHAT (SAFE ADD-ONS APPLIED)
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    uid = str(update.effective_user.id)
    user_text = update.message.text.strip()
    now = datetime.utcnow()

    doc = memory_col.find_one({"_id": uid}) or {
        "messages": [],
        "silence": 0,
        "topic_lock": False,
        "last_active": now
    }

    messages = doc["messages"]
    silence = doc.get("silence", 0)
    topic_lock = doc.get("topic_lock", False)
    last_active = doc.get("last_active", now)

    # ⏳ SAFE ADD-ON: Auto topic timeout
    if topic_lock and now - last_active > TOPIC_TIMEOUT:
        topic_lock = False
        messages = []
        silence = 0
        log_debug(uid, {"event": "topic_timeout"})

    last_assistant = next(
        (m["content"] for m in reversed(messages) if m["role"] == "assistant"),
        ""
    )

    # 🔒 SAFE ADD-ON: Soft conversation lock
    if topic_lock:
        if wants_new_topic(user_text):
            topic_lock = False
            messages = []
            silence = 0
            log_debug(uid, {"event": "manual_unlock"})
    else:
        if not wants_to_continue(user_text):
            if is_new_topic(last_assistant, user_text):
                topic_lock = True
                messages = []
                silence = 0
                log_debug(uid, {"event": "topic_lock"})

    # silence logic (UNCHANGED)
    if is_short(user_text):
        silence += 1
    else:
        silence = 0

    messages.append({"role": "user", "content": user_text})

    if silence >= 2:
        reply = "Theek hai 🙂"
    else:
        payload = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]
        response, server_idx = groq_chat(payload)
        reply = response.choices[0].message.content.strip()
        log_debug(uid, {
            "event": "reply",
            "server": server_idx + 1,
            "silence": silence,
            "topic_lock": topic_lock
        })

    messages.append({"role": "assistant", "content": reply})

    memory_col.update_one(
        {"_id": uid},
        {"$set": {
            "messages": messages[-10:],
            "silence": silence,
            "topic_lock": topic_lock,
            "last_active": now
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
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("revive", revive))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Miss Blossom is running 🌸")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
