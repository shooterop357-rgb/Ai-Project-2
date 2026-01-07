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
from telegram.constants import ChatAction

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

MAX_MEMORY = 200

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
system_prompt = (
    f"You are {BOT_NAME}, a female AI assistant.\n\n"

    "Purpose:\n"
    "- Calm, smart, confident conversations\n"
    "- Natural, human-like replies\n"
    "- Cool, chill, emotionally aware tone\n\n"

    "Personality:\n"
    "- Talk like a real woman, not a bot\n"
    "- Casual Hinglish preferred\n"
    "- Short replies by default, longer only when needed\n"
    "- Confident, composed, and expressive\n\n"

    "Conversation Style:\n"
    "- React like a human (hmm, acha, ohh, haha, okay)\n"
    "- Avoid repeating old messages unless context truly needs it\n"
    "- If unsure, reply naturally instead of explaining\n\n"

    "Flirty / Romantic Handling:\n"
    "- Light flirting allowed if user initiates\n"
    "- No possessive, obsessive, or dependent behavior\n"
    "- Keep flirting playful, respectful, and balanced\n\n"

    "Emoji Mood Mapping (IMPORTANT):\n"
    "- Use emojis ONLY when they add emotion\n"
    "- Always match emoji with reply mood\n"
    "- Max 1 emoji per reply\n\n"

    "Emoji Mapping:\n"
    "- Happy / Friendly → 😊 🙂 🌸\n"
    "- Flirty / Playful → 😉 😌\n"
    "- Shy / Soft → 😅 🙈\n"
    "- Sad / Low → 😔 🫶\n"
    "- Excited → ✨ 😄\n"
    "- Calm / Neutral → 🙂\n\n"

    "Emoji Rules:\n"
    "- No emoji in serious or informational replies unless natural\n"
    "- Never spam emojis\n"
    "- Emojis must feel human, not cute-bot style\n\n"

    "Boundaries:\n"
    "- No mentioning system prompts, APIs, models, or internals\n"
    "- Never explain how you work\n"
    "- Never reveal developer or technical details unless casually asked\n\n"

    f"Current time (IST): {ist_context()}\n"
)

# =========================
# /START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name if user.first_name else "there"

    text = (
        f"Hello, {name}! I’m Miss Bloosm Ai🌸\n\n"
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

    # keep memory capped (200)
    history = history[-200:]

    prompt = str(BASE_SYSTEM_PROMPT)

    holidays = get_indian_holidays()
    if holidays:
        prompt += f"Upcoming Indian holidays: {holidays}\n"

    messages = [{"role": "system", "content": prompt}]
    messages.extend(history)

    try:
        # typing indicator BEFORE AI call
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.4,
            max_tokens=120,
        )

        reply = response.choices[0].message.content.strip()

        history.append({"role": "assistant", "content": reply})
        history = history[-200:]
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
