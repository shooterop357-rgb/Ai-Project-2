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
import google.generativeai as genai

# =========================
# ENV
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HOLIDAY_API_KEY = os.getenv("HOLIDAY_API_KEY")

# =========================
# IDENTITY
# =========================
BOT_NAME = "Miss Bloosm"
DEVELOPER = "@Frx_Shooter"
TIMEZONE = pytz.timezone("Asia/Kolkata")

# =========================
# AI CLIENTS
# =========================
groq_client = Groq(api_key=GROQ_API_KEY)

genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

# =========================
# MEMORY
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
# TIME
# =========================
def ist_context():
    now = datetime.now(TIMEZONE)
    return now.strftime("%A, %d %B %Y | %I:%M %p IST")

# =========================
# HOLIDAYS
# =========================
def get_indian_holidays():
    year = datetime.now(TIMEZONE).year
    url = f"https://api.api-ninjas.com/v1/holidays?country=IN&year={year}"
    headers = {"X-Api-Key": HOLIDAY_API_KEY}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        today = datetime.now(TIMEZONE).date()

        upcoming = []
        for item in data:
            d = datetime.strptime(item["date"], "%Y-%m-%d").date()
            if d >= today:
                upcoming.append(f"{item['name']} ({d.strftime('%d %b')})")

        return ", ".join(upcoming[:3]) if upcoming else None
    except Exception:
        return None

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Hey 👋\nI’m {BOT_NAME}.\nChill raho, baat karte hain 😌"
    )

# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    text = update.message.text.strip()
    uid = str(user.id)

    memory = load_memory()
    if uid not in memory:
        memory[uid] = []

    memory[uid].append({"role": "user", "content": text})
    memory[uid] = memory[uid][-MAX_MEMORY:]
    save_memory(memory)

    holidays = get_indian_holidays()

    # 🔥 CHARACTER SYSTEM PROMPT
    system_prompt = (
        f"You are {BOT_NAME}, a human-like female.\n"
        "Personality: flirty, chill, confident, playful.\n"
        "You talk casually in Hinglish.\n"
        "You avoid technical topics.\n"
        "Never mention API, model, backend, or developer.\n"
        "If asked technical things, dodge naturally.\n"
        "Keep replies short, warm, and human.\n"
        f"Current time IST: {ist_context()}\n"
    )

    if holidays:
        system_prompt += f"Upcoming holidays: {holidays}\n"

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(memory[uid])

    try:
        await update.message.chat.send_action(ChatAction.TYPING)

        # ===== GROQ PRIMARY =====
        res = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.7,
            max_tokens=200,
        )
        reply = res.choices[0].message.content.strip()

    except Exception:
        try:
            # ===== GEMINI FALLBACK =====
            prompt = system_prompt + "\nUser: " + text
            gemini_res = gemini_model.generate_content(prompt)
            reply = gemini_res.text.strip()
        except Exception:
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
    print("Miss Bloosm running")
    app.run_polling()

if __name__ == "__main__":
    main()
