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
from telegram.constants import ChatAction

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
# GROQ ROUND ROBIN
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
    return None

# =========================
# MEMORY (FILE)
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
# TIME CONTEXT
# =========================
def ist_context():
    return datetime.now(TIMEZONE).strftime("%A, %d %B %Y | %I:%M %p IST")

# =========================
# HOLIDAYS (CACHED)
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
# HELPERS (SAFE ADD-ONS)
# =========================
FILLER_QUESTIONS = [
    "how's your day going",
    "how is your day going",
    "what's on your mind"
]

def is_filler_repeat(last_bot, new_bot):
    if not last_bot:
        return False
    last_bot = last_bot.lower()
    new_bot = new_bot.lower()
    return any(q in last_bot and q in new_bot for q in FILLER_QUESTIONS)

def last_meaningful_bot(memory):
    for m in reversed(memory):
        if m["role"] == "assistant" and len(m["content"].split()) > 6:
            return m["content"]
    return ""

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
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()
    uid = str(update.effective_user.id)

    memory = load_memory()
    memory.setdefault(uid, [])

    # Typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    # HARD developer rule
    if any(k in user_text.lower() for k in ["who made you", "developer", "designed you"]):
        reply = f"I was designed by {DEVELOPER} 🙂"
        memory[uid].append({"role": "assistant", "content": reply})
        save_memory(memory)
        await update.message.reply_text(reply)
        return

    # Explain / previous handling
    if user_text.lower() in ["explain", "explain it", "previous joke"]:
        context_text = last_meaningful_bot(memory[uid])
        if context_text:
            user_text = f"Explain this simply:\n{context_text}"

    memory[uid].append({"role": "user", "content": user_text})
    memory[uid] = memory[uid][-MAX_MEMORY:]
    save_memory(memory)

    holidays_context = get_indian_holidays()

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

    # Anti loop guard
    last_bot = last_meaningful_bot(memory[uid])
    if is_filler_repeat(last_bot, reply):
        return

    memory[uid].append({"role": "assistant", "content": reply})
    memory[uid] = memory[uid][-MAX_MEMORY:]
    save_memory(memory)

    await update.message.reply_text(reply)

# =========================
# RUN
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Miss Bloosm is running 🌸")
    app.run_polling()

if __name__ == "__main__":
    main()
