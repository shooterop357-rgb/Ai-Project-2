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

from groq import Groq
from openai import OpenAI

# =========================
# ENV VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HOLIDAY_API_KEY = os.getenv("HOLIDAY_API_KEY")

# =========================
# CORE IDENTITY
# =========================
BOT_NAME = "Miss Bloosm"
DEVELOPER = "@Frx_Shooter"
TIMEZONE = pytz.timezone("Asia/Kolkata")

# =========================
# AI CLIENTS
# =========================
groq_client = Groq(api_key=GROQ_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# LONG MEMORY
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
    now = datetime.now(TIMEZONE)
    return now.strftime("%A, %d %B %Y | %I:%M %p IST")

# =========================
# INDIAN HOLIDAYS
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

    user = update.effective_user
    uid = str(user.id)
    user_text = update.message.text.strip()

    memory = load_memory()
    memory.setdefault(uid, [])

    memory[uid].append({"role": "user", "content": user_text})
    memory[uid] = memory[uid][-MAX_MEMORY:]
    save_memory(memory)

    holidays_context = get_indian_holidays()

    system_prompt = (
        f"You are {BOT_NAME}, a female AI assistant.\n"
        f"Your developer is {DEVELOPER}.\n"
        "You speak calmly, emotionally, and naturally like a human.\n"
        "You understand feelings and reply warmly.\n"
        "Never mention errors or technical details.\n"
        f"Current time (IST): {ist_context()}\n"
    )

    if holidays_context:
        system_prompt += f"Upcoming Indian holidays: {holidays_context}\n"

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(memory[uid])

    reply = None

    # ===== OPENAI FIRST (better replies) =====
    try:
        r = openai_client.responses.create(
            model="gpt-4.1-mini",
            input=messages,
            temperature=0.9  # <-- OPENAI BORING FIX
        )
        reply = r.output_text.strip()
    except Exception:
        reply = None

    # ===== GROQ FALLBACK (old method) =====
    if not reply:
        try:
            r = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.65,
                max_tokens=200,
            )
            reply = r.choices[0].message.content.strip()
        except Exception:
            return  # SILENT

    if reply:
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
