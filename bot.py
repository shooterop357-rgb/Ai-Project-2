import os
import json
from datetime import datetime
import pytz
import requests

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

# =========================
# ENV VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HOLIDAY_API_KEY = os.getenv("HOLIDAY_API_KEY")

# =========================
# CORE IDENTITY
# =========================
BOT_NAME = "Miss Bloosm"
DEVELOPER = "@Frx_Shooter"
TIMEZONE = pytz.timezone("Asia/Kolkata")

# =========================
# GROQ CLIENT
# =========================
client = Groq(api_key=GROQ_API_KEY)

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
# INDIAN HOLIDAYS (API)
# =========================
def get_indian_holidays():
    year = datetime.now(TIMEZONE).year
    url = f"https://api.api-ninjas.com/v1/holidays?country=IN&year={year}"
    headers = {"X-Api-Key": HOLIDAY_API_KEY}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()

        upcoming = []
        today = datetime.now(TIMEZONE).date()

        for item in data:
            d = datetime.strptime(item["date"], "%Y-%m-%d").date()
            if d >= today:
                upcoming.append(f"{item['name']} ({d.strftime('%d %b')})")

        return ", ".join(upcoming[:5]) if upcoming else None

    except Exception:
        return None

# =========================
# /START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    intro = (
        f"Hello, I’m {BOT_NAME} 🌸\n\n"
        "I’m a calm, friendly AI designed for natural conversations.\n"
        "Human Like Replay Feels Emotionas.\n"
        "You can talk to me in Any language.\n\n"
        "⚠️ This bot is currently in beta.\n"
        "Some replies may not always be perfect."
    )
    await update.message.reply_text(intro)

# =========================
# MAIN CHAT (PURE AI)
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_text = update.message.text.strip()

    memory = load_memory()
    uid = str(user.id)

    if uid not in memory:
        memory[uid] = []

    # Save user message
    memory[uid].append({"role": "user", "content": user_text})
    memory[uid] = memory[uid][-MAX_MEMORY:]
    save_memory(memory)

    # 🔹 CHANGE 1: Typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    holidays_context = get_indian_holidays()

    system_prompt = (
        f"You are {BOT_NAME}, a female AI assistant.\n"
        f"Developer: {DEVELOPER}.\n\n"
        "Purpose:\n"
        "- Calm, friendly, professional conversation\n"
        "- Human-like tone\n"
        "- Light, natural emojis allowed 🙂🌸🤍\n\n"
        "Rules:\n"
        "- No automatic or scripted replies\n"
        "- Never mention errors or technical issues\n\n"
        f"Current time (IST): {ist_context()}\n"
    )

    if holidays_context:
        system_prompt += f"Upcoming Indian holidays: {holidays_context}\n"

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(memory[uid])

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.65,
            max_tokens=200,
        )

        reply = response.choices[0].message.content.strip()

        memory[uid].append({"role": "assistant", "content": reply})
        memory[uid] = memory[uid][-MAX_MEMORY:]
        save_memory(memory)

        await update.message.reply_text(reply)

    except Exception:
        # 🔹 CHANGE 2: Silent failure (no message)
        return

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
