import os
from collections import deque
from datetime import datetime
import pytz

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)
from groq import Groq

# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

BOT_NAME = "Miss Bloosm"
OWNER_NAME = "@Frx_Shooter"

client = Groq(api_key=GROQ_API_KEY)

# ===== MEMORY =====
user_memory = {}
owner_about_step = {}

def get_memory(user_id):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=30)
    return user_memory[user_id]

def get_owner_step(user_id):
    return owner_about_step.get(user_id, 0)

def set_owner_step(user_id, step):
    owner_about_step[user_id] = step

# ===== TIME HELPERS =====
def get_time_info():
    tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(tz)
    return {
        "hour": now.hour,
        "date": now.strftime("%d %B %Y"),
        "day": now.strftime("%A"),
        "time": now.strftime("%I:%M %p")
    }

# ===== DETECTORS =====
def is_greeting(text: str) -> bool:
    keys = ["hi", "hello", "hey", "gm", "good morning", "gn", "good night"]
    return any(k in text.lower() for k in keys)

def is_time_question(text: str) -> bool:
    keys = ["time", "date", "day", "aaj kya din", "kitna time"]
    return any(k in text.lower() for k in keys)

def is_identity_question(text: str) -> bool:
    keys = [
        "who developed you", "who made you", "developer", "owner",
        "tumhe kisne banaya", "developer kon", "owner kon",
        "your name", "tumhara naam"
    ]
    return any(k in text.lower() for k in keys)

def is_owner_about_question(text: str) -> bool:
    keys = [
        "who is frx", "who is frx shooter", "about frx",
        "tell me about your owner", "frx shooter kon"
    ]
    return any(k in text.lower() for k in keys)

def is_user_identity_question(text: str) -> bool:
    keys = ["who am i", "main kaun ho", "me kaun hu", "mera naam kya hai"]
    return any(k in text.lower() for k in keys)

def needs_long_reply(text: str) -> bool:
    keys = ["explain", "detail", "why", "how", "kaise", "kyu", "samjhao"]
    return any(k in text.lower() for k in keys)

def detect_emotion(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["sad", "alone", "broken", "depressed", "dukhi"]):
        return "sad"
    if any(k in t for k in ["happy", "excited", "good", "great", "acha"]):
        return "happy"
    if any(k in t for k in ["angry", "gussa", "irritated"]):
        return "angry"
    if any(k in t for k in ["lonely", "miss you", "akela"]):
        return "lonely"
    return "neutral"

def analyze_memory(memory) -> str:
    joined = " ".join(memory).lower()
    if any(k in joined for k in ["code", "bot", "api"]):
        return "tech"
    if any(k in joined for k in ["study", "exam"]):
        return "student"
    if any(k in joined for k in ["photo", "design"]):
        return "creative"
    return "general"

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Hey 👋 I'm {BOT_NAME}.\nTalk to me freely 🙂"
    )

# ===== MAIN CHAT =====
async def reply_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_text = update.message.text.strip()
    memory = get_memory(user.id)

    # GREETINGS
    if is_greeting(user_text):
        t = get_time_info()
        h = t["hour"]
        if 5 <= h < 12:
            msg = "Good morning ☀️\nHope aaj ka din bright ho ✨"
        elif 12 <= h < 17:
            msg = "Good afternoon 🌤️\nDay kaisa ja raha hai?"
        elif 17 <= h < 22:
            msg = "Good evening 🌆\nThoda relax ka time 🙂"
        else:
            msg = "Good night 🌙\nAaram se rest karo, kal naya din hai ✨"
        await update.message.reply_text(msg)
        return

    # TIME / DATE
    if is_time_question(user_text):
        t = get_time_info()
        await update.message.reply_text(
            f"Today is {t['day']} 📅\n"
            f"Date: {t['date']}\n"
            f"Time: {t['time']} ⏰"
        )
        return

    # BOT IDENTITY
    if is_identity_question(user_text):
        await update.message.reply_text(
            f"My name is {BOT_NAME}.\n"
            f"I was developed and designed by {OWNER_NAME}."
        )
        return

    # OWNER ABOUT (MULTI-STEP)
    if is_owner_about_question(user_text):
        step = get_owner_step(user.id)
        if step == 0:
            msg = (
                "He’s a Python-based developer — always learning 🐍✨\n"
                "Also a photographer by passion 📸"
            )
            set_owner_step(user.id, 1)
        elif step == 1:
            msg = "He’s been on Telegram since 2018, putting real effort 🌱"
            set_owner_step(user.id, 2)
        else:
            msg = (
                "One of his known projects is **@MultiSaverProBot** 🚀\n"
                "Popular on Telegram & Instagram."
            )
            set_owner_step(user.id, 0)
        await update.message.reply_text(msg)
        return

    # USER IDENTITY (HYBRID)
    if is_user_identity_question(user_text):
        name = user.first_name or "friend"
        style = analyze_memory(memory)
        hint = "You feel thoughtful and real 🙂"
        if style == "tech":
            hint = "You give a tech-curious vibe 💻"
        elif style == "student":
            hint = "You feel like a learner 📚"
        elif style == "creative":
            hint = "You feel creative 🎨"

        await update.message.reply_text(
            f"You're **{name}** ✨\n{hint}"
        )
        return

    # REPEAT CHECK
    if user_text.lower() in (m.lower() for m in memory):
        await update.message.reply_text(
            "Hmm… ye baat tum pehle bhi bol chuke ho 🙂"
        )
        return

    memory.append(user_text)

    emotion = detect_emotion(user_text)
    max_tokens = 150 if needs_long_reply(user_text) else 50

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are {BOT_NAME}, a warm, human-like AI.\n"
                        f"Be emotional, short, and natural.\n"
                        f"Do not mention owner unless asked."
                    )
                },
                {
                    "role": "user",
                    "content": f"[emotion: {emotion}] {user_text}"
                }
            ],
            temperature=0.7,
            max_tokens=max_tokens
        )
        await update.message.reply_text(
            response.choices[0].message.content
        )

    except Exception:
        await update.message.reply_text(
            "Thoda issue aaya… phir se bolo 🙂"
        )

# ===== RUN =====
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_ai))
    print("Miss Bloosm is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
