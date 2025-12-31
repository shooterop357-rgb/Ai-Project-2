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

# ================== ENV ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

BOT_NAME = "Miss Bloosm"
OWNER_NAME = "@Frx_Shooter"
OWNER_ID = 5436530930  # <-- YOUR TELEGRAM ID

client = Groq(api_key=GROQ_API_KEY)

# ================== SETTINGS ==================
bot_settings = {
    "group_reply": False,   # silent in groups
    "welcome": True
}

# ================== MEMORY ==================
user_memory = {}

def get_memory(uid):
    if uid not in user_memory:
        user_memory[uid] = deque(maxlen=30)
    return user_memory[uid]

# ================== OWNER ==================
def is_owner(uid):
    return uid == OWNER_ID

def owner_intent(text):
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

# ================== HELPERS ==================
def clean_reply(text):
    text = re.sub(r"\*[^*]+\*", "", text).strip()
    return text if text else "🙂"

def now_time():
    tz = pytz.timezone("Asia/Kolkata")
    return datetime.now(tz)

def is_greeting(text):
    return text.lower().strip() in [
        "hi","hello","hey","gm","good morning","gn","good night"
    ]

def is_time_q(text):
    return any(k in text.lower() for k in ["time","date","day","aaj","kitna time"])

def is_tomorrow_q(text):
    return "tomorrow" in text.lower() or "kal" in text.lower()

def needs_long(text):
    return any(k in text.lower() for k in ["explain","detail","why","how","kaise","kyu"])

def detect_emotion(text):
    t = text.lower()
    if any(k in t for k in ["sad","alone","broken","dukhi"]):
        return "sad"
    if any(k in t for k in ["happy","excited","acha"]):
        return "happy"
    if any(k in t for k in ["angry","gussa"]):
        return "angry"
    return "neutral"

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Hey 👋 I'm {BOT_NAME}.\n"
        f"⚠️ Bot is under BETA phase.\n"
        f"Replies may be incorrect sometimes.\n\n"
        f"Just type anything 🙂"
    )

# ================== WELCOME ==================
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_settings["welcome"]:
        return
    await update.message.reply_text(
        "Welcome 🙂\n"
        "⚠️ This bot is under BETA phase.\n"
        "Please mention me if needed."
    )

# ================== BACKGROUND AI ==================
async def send_ai_reply(update, context, text):
    try:
        await update.message.chat.send_action("typing")

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are {BOT_NAME}, a female AI assistant.\n"
                        f"Chat like a real woman on Telegram.\n"
                        f"Use simple emojis 🙂✨\n"
                        f"NEVER use roleplay actions like *smile*.\n"
                        f"Replies must be short, clean, and human."
                    )
                },
                {"role": "user", "content": text}
            ],
            temperature=0.7,
            max_tokens=60
        )

        reply = clean_reply(response.choices[0].message.content)
        await update.message.reply_text(reply)

    except Exception:
        pass

# ================== MAIN ==================
async def reply_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    text = update.message.text.strip()

    # OWNER AUTO CONTROL
    if is_owner(user.id):
        intent = owner_intent(text)
        if intent:
            k, v = intent
            bot_settings[k] = v
            await update.message.reply_text(f"Done 👍 `{k}` set to `{v}`")
            return

    # GROUP FLOOD CONTROL
    if update.message.chat.type in ["group", "supergroup"]:
        if not bot_settings["group_reply"]:
            if not (
                update.message.reply_to_message
                and update.message.reply_to_message.from_user.is_bot
            ) and f"@{context.bot.username}" not in text:
                return

    # GREETING (NO RETURN – AI STILL RUNS)
    if is_greeting(text):
        h = now_time().hour
        if h < 12:
            await update.message.reply_text("Good morning ☀️")
        elif h < 17:
            await update.message.reply_text("Good afternoon 🌤️")
        elif h < 22:
            await update.message.reply_text("Good evening 🌆")
        else:
            await update.message.reply_text("Good night 🌙")

    # TIME / DATE
    if is_time_q(text):
        n = now_time()
        await update.message.reply_text(
            f"{n.strftime('%A')} 📅\n"
            f"{n.strftime('%d %B %Y')}\n"
            f"{n.strftime('%I:%M %p')} ⏰"
        )
        return

    # TOMORROW
    if is_tomorrow_q(text):
        tm = now_time() + timedelta(days=1)
        await update.message.reply_text(
            f"Tomorrow is {tm.strftime('%A')} 📅\n"
            f"{tm.strftime('%d %B %Y')}"
        )
        return

    # MEMORY
    memory = get_memory(user.id)
    memory.append(text)

    # 🔥 INSTANT ACK (PREVENTS TIMEOUT)
    await update.message.reply_text("…")

    # 🔥 BACKGROUND AI (NO TIMEOUT)
    context.application.create_task(
        send_ai_reply(update, context, f"[emotion:{detect_emotion(text)}] {text}")
    )

# ================== RUN ==================
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
