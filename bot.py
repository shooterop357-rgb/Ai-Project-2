import os
import json
import time
from datetime import datetime
import pytz
import requests
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

# =========================
# ENV VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
HOLIDAY_API_KEY = os.getenv("HOLIDAY_API_KEY")

GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
    os.getenv("GROQ_API_KEY_4"),
]

if not BOT_TOKEN or not all(GROQ_KEYS):
    raise RuntimeError("Missing ENV variables")

# =========================
# CORE IDENTITY
# =========================
BOT_NAME = "Miss Bloosm"
DEVELOPER = "@Frx_Shooter"
TIMEZONE = pytz.timezone("Asia/Kolkata")

# =========================
# GROQ ROUND ROBIN (AUTO)
# =========================
groq_clients = [Groq(api_key=k) for k in GROQ_KEYS]
current_idx = 0

def groq_chat(messages):
    global current_idx
    for _ in range(len(groq_clients)):
        client = groq_clients[current_idx % len(groq_clients)]
        current_idx += 1
        try:
            return client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.65,
                max_tokens=200,
            )
        except Exception:
            continue
    return None  # silent fail

# =========================
# LONG MEMORY (FILE)
# =========================
MEMORY_FILE = "memory.json"
MAX_MEMORY = 200

if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w") as f:
        json.dump({}, f)

def load_memory():
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2)

# =========================
# TIME CONTEXT (IST)
# =========================
def ist_context():
    now = datetime.now(TIMEZONE)
    return now.strftime("%A, %d %B %Y | %I:%M %p IST")

# =========================
# INDIAN HOLIDAYS (CACHED)
# =========================
_holiday_cache = {"date": None, "data": None}

def get_indian_holidays():
    if not HOLIDAY_API_KEY:
        return None

    today = datetime.now(TIMEZONE).date()
    if _holiday_cache["date"] == today:
        return _holiday_cache["data"]

    try:
        year = today.year
        url = f"https://api.api-ninjas.com/v1/holidays?country=IN&year={year}"
        headers = {"X-Api-Key": HOLIDAY_API_KEY}
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()

        upcoming = []
        for item in data:
            d = datetime.strptime(item["date"], "%Y-%m-%d").date()
            if d >= today:
                upcoming.append(f"{item['name']} ({d.strftime('%d %b')})")

        result = ", ".join(upcoming[:5]) if upcoming else None
        _holiday_cache["date"] = today
        _holiday_cache["data"] = result
        return result

    except Exception:
        return None

# =========================
# NEW START FILTER
# =========================
RESET_WORDS = ["by the way", "another thing", "new topic", "forget that"]

def is_new_start(last_msg, current_msg):
    if not last_msg:
        return False
    if any(w in current_msg.lower() for w in RESET_WORDS):
        return True
    ratio = SequenceMatcher(None, last_msg.lower(), current_msg.lower()).ratio()
    return ratio < 0.35

# =========================
# /START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    intro = (
        f"Hello, I’m {BOT_NAME} 🌸\n\n"
        "I’m a calm, friendly AI designed for natural conversations.\n"
        "Human Like Replay Feels Emotionas.\n\n"
        "⚠️ This bot is currently in beta.\n"
        "Some replies may not always be perfect."
    )
    await update.message.reply_text(intro)

# =========================
# MAIN CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()
    uid = str(update.effective_user.id)

    memory = load_memory()
    memory.setdefault(uid, [])

    # ---- NEW START FILTER ----
    last_user_msg = ""
    for m in reversed(memory[uid]):
        if m["role"] == "user":
            last_user_msg = m["content"]
            break

    if is_new_start(last_user_msg, user_text):
        memory[uid] = []

    # ---- HARD DEVELOPER RULE (NO MODEL) ----
    if any(k in user_text.lower() for k in ["who made you", "developer", "designed you"]):
        reply = f"I was designed by {DEVELOPER} 🙂"
        memory[uid].append({"role": "assistant", "content": reply})
        save_memory(memory)
        await update.message.reply_text(reply)
        return

    # Save user message
    memory[uid].append({"role": "user", "content": user_text})
    memory[uid] = memory[uid][-MAX_MEMORY:]
    save_memory(memory)

    holidays_context = get_indian_holidays()

    # SYSTEM PROMPT (UNCHANGED)
    system_prompt = (
        f"You are {BOT_NAME}, a female AI assistant.\n"
        "Purpose:\n"
        "- Calm, friendly, professional conversation\n"
        "- Human-like tone\n"
        "- Light emojis allowed naturally\n\n"
        "Rules:\n"
        "- No automatic or scripted replies\n"
        "- Never mention errors or technical issues\n"
        "- If unsure, respond naturally like a human\n\n"
        f"Current time (IST): {ist_context()}\n"
    )

    if holidays_context:
        system_prompt += f"Upcoming Indian holidays: {holidays_context}\n"

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(memory[uid])

    response = groq_chat(messages)
    if not response:
        return

    reply = response.choices[0].message.content.strip()

    memory[uid].append({"role": "assistant", "content": reply})
    memory[uid] = memory[uid][-MAX_MEMORY:]
    save_memory(memory)

    await update.message.reply_text(reply)

# =========================
# RUN BOT
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Miss Bloosm is running 🌸")
    app.run_polling()

if __name__ == "__main__":
    main()
