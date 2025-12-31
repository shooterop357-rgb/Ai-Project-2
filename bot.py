import os
import re
import asyncio
from collections import deque
from datetime import datetime, timedelta
import pytz

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)
from telegram.request import HTTPXRequest
from groq import Groq

# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

BOT_NAME = "Miss Bloosm"
OWNER_NAME = "Frx_Shooter"
OWNER_ID = 5436530930  # YOUR ID

client = Groq(api_key=GROQ_API_KEY)

# ===== SETTINGS =====
bot_settings = {
    "group_reply": False,     # group silent
    "welcome": True,          # welcome ON
    "mode": "mention_only"    # reply only on mention/reply
}

# ===== MEMORY =====
user_memory = {}

def get_memory(user_id):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=30)
    return user_memory[user_id]

# ===== OWNER =====
def is_owner(uid: int) -> bool:
    return uid == OWNER_ID

def owner_setting_intent(text: str):
    t = text.lower()
    if "group reply on" in t:
        return ("group_reply", True)
    if "group reply off" in t:
        return ("group_reply", False)
    if "welcome on" in t:
        return ("welcome", True)
    if "welcome off" in t:
        return ("welcome", False)
    return None

# ===== CLEAN AI =====
def clean_reply(text: str) -> str:
    # remove *roleplay*
    text = re.sub(r"\*[^*]+\*", "", text).strip()
    return text if text else "🙂"

# ===== TIME =====
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
    return any(k in text.lower() for k in ["hi", "hello", "hey", "gm", "good morning", "gn", "good night"])

def is_time_question(text: str) -> bool:
    return any(k in text.lower() for k in ["time", "date", "day", "aaj kya din", "kitna time"])

def is_tomorrow_question(text: str) -> bool:
    return any(k in text.lower() for k in ["tomorrow", "kal kya", "what is tomorrow", "kal ka din"])

def is_identity_question(text: str) -> bool:
    return any(k in text.lower() for k in ["who developed you", "who made you", "developer", "owner", "your name"])

def is_user_identity_question(text: str) -> bool:
    return any(k in text.lower() for k in ["who am i", "who i am", "main kaun ho", "me kaun hu", "what is my name"])

def needs_long_reply(text: str) -> bool:
    return any(k in text.lower() for k in ["explain", "detail", "why", "how", "kaise", "kyu"])

def detect_emotion(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["sad", "alone", "broken", "dukhi"]):
        return "sad"
    if any(k in t for k in ["happy", "excited", "acha"]):
        return "happy"
    if any(k in t for k in ["angry", "gussa"]):
        return "angry"
    return "neutral"

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Hey 👋 I'm {BOT_NAME}.\n"
        f"⚠️ Bot is under **BETA phase**.\n"
        f"Replies may be incorrect sometimes.\n\n"
        f"Feel free to chat 🙂"
    )

# ===== WELCOME =====
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_settings["welcome"]:
        return
    for _ in update.message.new_chat_members:
        await update.message.reply_text(
            "Welcome 🙂\n"
            "⚠️ This bot is under **BETA phase**.\n"
            "Replies may be incorrect.\n"
            "Please mention me if needed."
        )

# ===== MAIN =====
async def reply_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    text = update.message.text.strip()

    # OWNER AUTO CONTROL
    if is_owner(user.id):
        intent = owner_setting_intent(text)
        if intent:
            key, value = intent
            bot_settings[key] = value
            await update.message.reply_text(f"Done 👍 `{key}` set to `{value}`")
            return

    # GROUP FLOOD CONTROL
    if update.message.chat.type in ["group", "supergroup"]:
        if not bot_settings["group_reply"]:
            if not (
                update.message.reply_to_message
                and update.message.reply_to_message.from_user.is_bot
            ) and f"@{context.bot.username}" not in text:
                return

    # GREETING
    if is_greeting(text):
        t = get_time_info()
        h = t["hour"]
        if 5 <= h < 12:
            msg = "Good morning ☀️ Hope aaj ka din acha ho ✨"
        elif 12 <= h < 17:
            msg = "Good afternoon 🌤️ Day kaisa ja raha hai?"
        elif 17 <= h < 22:
            msg = "Good evening 🌆 Thoda relax karo 🙂"
        else:
            msg = "Good night 🌙 Aaram se rest karo ✨"
        await update.message.reply_text(msg)
        return

    # TIME / DATE
    if is_time_question(text):
        t = get_time_info()
        await update.message.reply_text(
            f"{t['day']} 📅\nDate: {t['date']}\nTime: {t['time']} ⏰"
        )
        return

    # TOMORROW
    if is_tomorrow_question(text):
        tz = pytz.timezone("Asia/Kolkata")
        tm = datetime.now(tz) + timedelta(days=1)
        await update.message.reply_text(
            f"Tomorrow is {tm.strftime('%A')} 📅\nDate: {tm.strftime('%d %B %Y')}"
        )
        return

    # BOT IDENTITY
    if is_identity_question(text):
        await update.message.reply_text(
            f"My name is {BOT_NAME}.\nDeveloped by {OWNER_NAME}."
        )
        return

    # USER IDENTITY
    if is_user_identity_question(text):
        await update.message.reply_text(
            f"You're **{user.first_name}** ✨\nAnd you matter here 🙂"
        )
        return

    # AI CHAT
    memory = get_memory(user.id)
    memory.append(text)

    emotion = detect_emotion(text)
    max_tokens = 120 if needs_long_reply(text) else 40

    try:
        # keep connection alive
        await update.message.chat.send_action("typing")

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are {BOT_NAME}, chatting like a real human on Telegram.\n"
                        f"Use simple emojis 🙂✨\n"
                        f"NEVER use roleplay actions or text inside asterisks.\n"
                        f"Replies must be short, clean, and natural.\n"
                        f"Never mention your owner unless asked."
                    )
                },
                {"role": "user", "content": f"[emotion:{emotion}] {text}"}
            ],
            temperature=0.7,
            max_tokens=max_tokens
        )

        reply = clean_reply(response.choices[0].message.content)
        await update.message.reply_text(reply)
        await asyncio.sleep(0.3)

    except Exception:
        await update.message.reply_text("Thoda issue aaya… phir se bolo 🙂")

# ===== RUN =====
def main():
    request = HTTPXRequest(
        connect_timeout=20,
        read_timeout=20,
        write_timeout=20,
        pool_timeout=20
    )

    app = ApplicationBuilder().token(BOT_TOKEN).request(request).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_ai))

    print("Miss Bloosm is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
