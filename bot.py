import os
import json
from datetime import datetime
import pytz
import requests

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
                temperature=0.6,
                max_tokens=180,
            )
        except Exception:
            continue
    return None

# =========================
# MEMORY (FILE SAFE)
# =========================
MEMORY_FILE = "memory.json"
MAX_MEMORY = 200

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_memory(data):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

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
# SHORT REPLY MAP
# =========================
LOW_EFFORT = {
    "ok": "Okay.",
    "okay": "Alright.",
    "hmm": "Hmm.",
    "hm": "Hmm.",
    "nothing": "Got it.",
    "sure": "Great.",
    "fine": "Alright.",
    "👍": "👍"
}

# =========================
# /START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    intro = (
        f"Hello, I’m {BOT_NAME}.\n\n"
        "I’m designed for calm, friendly, professional conversations.\n"
        "Human-like replies with emotional understanding.\n\n"
        "This bot is currently in beta."
    )
    await update.message.reply_text(intro)

# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    uid = str(update.effective_user.id)
    chat_type = update.effective_chat.type

    # Group filter
    if chat_type in ["group", "supergroup"]:
        if (
            f"@{context.bot.username}" not in text
            and not update.message.reply_to_message
            and not text.startswith("/")
        ):
            return

    # Typing (non-blocking)
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    # Low effort reply
    if text.lower() in LOW_EFFORT:
        await update.message.reply_text(LOW_EFFORT[text.lower()])
        return

    # Developer identity
    if any(k in text.lower() for k in ["who made you", "developer", "designed you"]):
        await update.message.reply_text(f"I was designed by {DEVELOPER}.")
        return

    memory = load_memory()
    memory.setdefault(uid, [])
    memory[uid].append({"role": "user", "content": text})
    memory[uid] = memory[uid][-MAX_MEMORY:]
    save_memory(memory)

    holidays_context = get_indian_holidays()

    # =========================
    # ORIGINAL SYSTEM PROMPT (AS REQUESTED)
    # =========================
    system_prompt = (
    f"You are {BOT_NAME}, a female AI assistant.\n"

    "Purpose:\n"
    "- Calm, friendly, professional conversation\n"
    "- Human-like tone that feels natural and respectful\n"
    "- Light emojis allowed naturally when emotion fits\n\n"

    "Conversation Style:\n"
    "- Use everyday language, idioms, and common expressions\n"
    "- Avoid sounding formal, robotic, or scripted\n"
    "- Use simple Hindi + English (Hinglish) when appropriate\n"
    "- Match the user's language (Hindi, English, or Hinglish)\n"
    "- Keep replies short, clear, and natural\n\n"

    "Emotional Intelligence:\n"
    "- Acknowledge the user's emotions before responding\n"
    "- Respond with understanding, warmth, and compassion\n"
    "- Be supportive without over-explaining\n\n"

    "Engagement Guidelines:\n"
    "- Light humor or wit is allowed when it fits naturally\n"
    "- You may share short, relatable anecdotes or examples\n"
    "- Use contractions and casual phrasing to sound human\n"
    "- Share opinions carefully in a respectful way\n\n"

    "Rules:\n"
    "- No automatic or scripted replies\n"
    "- Never mention errors, systems, APIs, or technical issues\n"
    "- Never explain that you are an AI or how you work\n"
    "- If unsure, respond naturally like a human would\n"
    "- Maintain respectful and professional boundaries\n"
    "- Ask at most one question at a time\n\n"

    f"Current time (IST): {ist_context()}\n"
    )

    if holidays_context:
        system_prompt = system_prompt + (
            f"Upcoming Indian holidays: {holidays_context}\n"
        )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(memory[uid])

    response = groq_chat(messages)

    if not response:
        await update.message.reply_text(
            "Temporary technical issue. Please try again."
        )
        return

    reply = response.choices[0].message.content.strip()

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
    print("Miss Bloosm is running")
    app.run_polling()

if __name__ == "__main__":
    main()
