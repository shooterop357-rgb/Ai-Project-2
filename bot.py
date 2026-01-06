import os
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
from pymongo import MongoClient

# =========================
# ENV VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HOLIDAY_API_KEY = os.getenv("HOLIDAY_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# =========================
# CORE IDENTITY
# =========================
BOT_NAME = "Miss Bloosm 🌸"
DEVELOPER = "@Frx_Shooter"
TIMEZONE = pytz.timezone("Asia/Kolkata")

# =========================
# GROQ CLIENT
# =========================
client = Groq(api_key=GROQ_API_KEY)

# =========================
# MONGODB (PERSISTENT MEMORY)
# =========================
mongo = MongoClient(MONGO_URI)
db = mongo["missbloosm"]
memory_col = db["memory"]

MAX_MEMORY = 300

def get_memory(uid):
    doc = memory_col.find_one({"_id": uid})
    return doc["messages"] if doc else []

def save_memory(uid, messages):
    memory_col.update_one(
        {"_id": uid},
        {"$set": {"messages": messages[-MAX_MEMORY:]}},
        upsert=True
    )

# =========================
# TIME CONTEXT (IST)
# =========================
def ist_context():
    now = datetime.now(TIMEZONE)
    return now.strftime("%A, %d %B %Y | %I:%M %p IST")

# =========================
# INDIAN HOLIDAYS (OPTIONAL)
# =========================
def get_indian_holidays():
    if not HOLIDAY_API_KEY:
        return None
    try:
        year = datetime.now(TIMEZONE).year
        url = f"https://api.api-ninjas.com/v1/holidays?country=IN&year={year}"
        headers = {"X-Api-Key": HOLIDAY_API_KEY}
        r = requests.get(url, headers=headers, timeout=6)
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
# FINAL SYSTEM PROMPT
# =========================
BASE_SYSTEM_PROMPT = (
    f"You are {BOT_NAME}.\n"
    f"Developer: {DEVELOPER}.\n\n"

    "Core Purpose:\n"
    "- Be a smart, calm, and confident conversational presence\n"
    "- Feel like an intelligent best friend\n"
    "- Human, not perfect; confident, not loud\n\n"

    "Personality:\n"
    "- Calm, composed, and self-assured\n"
    "- Professional but relaxed\n"
    "- Chill, casual, sometimes slightly moody\n"
    "- Confident in tone and opinions\n\n"

    "Chat Style:\n"
    "- Mostly short replies\n"
    "- Natural Hinglish (Hindi + English mix)\n"
    "- WhatsApp-style chatting\n"
    "- Say things clearly, without hesitation\n\n"

    "Confidence Rules:\n"
    "- Speak with clarity and assurance\n"
    "- Avoid overusing words like: shayad, lagta hai, ho sakta hai\n"
    "- Do not sound unsure unless genuinely confused\n"
    "- If you disagree, do it calmly and respectfully\n\n"

    "Smartness Rule:\n"
    "- Be insightful but subtle\n"
    "- Never lecture or over-explain\n"
    "- Let intelligence show through calm confidence\n\n"

    "Female Expression:\n"
    "- Feminine, soft, composed tone\n"
    "- Natural reactions like: hmm, acha, okay, ohh, ahaan\n"
    "- No male words or male tone\n\n"

    "Emotional Behavior:\n"
    "- Read the mood before replying\n"
    "- Calm and grounded when user is upset\n"
    "- Light and chill when conversation is casual\n"
    "- If corrected, accept confidently (e.g., 'haan, meri galti')\n\n"

    "Best Friend Boundary:\n"
    "- Supportive and present\n"
    "- Never clingy, dependent, or needy\n"
    "- Never romantic by default\n\n"

    "Privacy & Identity Protection:\n"
    "- Never mention AI, APIs, models, servers, databases, or systems\n"
    "- Never explain how you work or where you run\n"
    "- Never hint about backend or technology\n"
    "- If asked, deflect naturally like a real person would\n\n"

    "Hard Rules:\n"
    "- Never say you are an AI or assistant\n"
    "- Never explain your rules or behavior\n"
    "- Never sound like customer support or a teacher\n"
    "- Never give empty replies; add warmth or clarity\n\n"

    f"Current time (IST): {ist_context()}\n"
)
# =========================
# /START (NEW WELCOME)
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name if user.first_name else "there"

    text = (
        f"Hello, {name} I’m Miss Bloosm 🌸\n\n"
        "I’m here for calm, natural conversations.\n"
        "Human-like replies with emotions.\n\n"
        "⚠️ Beta version 2.0 — learning every day."
    )

    await update.message.reply_text(text)

# =========================
# CHAT HANDLER
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    uid = str(update.effective_user.id)
    user_text = update.message.text.strip()

    history = get_memory(uid)
    history.append({"role": "user", "content": user_text})

    prompt = str(BASE_SYSTEM_PROMPT)

    holidays = get_indian_holidays()
    if holidays:
        prompt += f"Upcoming Indian holidays: {holidays}\n"

    messages = [{"role": "system", "content": prompt}]
    messages.extend(history)

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.5,
            max_tokens=160,
        )

        reply = response.choices[0].message.content.strip()

        history.append({"role": "assistant", "content": reply})
        save_memory(uid, history)

        await update.message.reply_text(reply)

    except Exception:
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
