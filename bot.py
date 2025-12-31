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

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

BOT_NAME = "Miss Bloosm"

OWNER_ID = 5436530930
OWNER_NAME = "Frx_Shooter"
OWNER_USERNAME = "@Frx_Shooter"

client = Groq(api_key=GROQ_API_KEY)

# ================= SETTINGS =================
bot_settings = {
    "group_reply": False,
    "welcome": True
}

# ================= MEMORY =================
user_memory = {}
def get_memory(uid):
    if uid not in user_memory:
        user_memory[uid] = deque(maxlen=30)
    return user_memory[uid]

# ================= OWNER =================
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

# ================= HELPERS =================
def clean_reply(text):
    return re.sub(r"\*[^*]+\*", "", text).strip()

def now_time():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

def is_greeting(text):
    return text.lower().strip() in [
        "hi", "hello", "hey", "good morning", "good evening", "good night"
    ]

def is_time_q(text):
    return any(k in text.lower() for k in ["time", "date", "day", "aaj"])

def is_tomorrow_q(text):
    return "tomorrow" in text.lower() or "kal" in text.lower()

def is_owner_question(text):
    t = text.lower()
    keys = [
        "who made you",
        "who is your owner",
        "who developed you",
        "tumhe kisne banaya",
        "owner kon",
        "developer kon"
    ]
    return any(k in t for k in keys)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Hello, I’m {BOT_NAME}.\n\n"
        f"This bot is currently in beta testing.\n"
        f"Some responses may be inaccurate.\n\n"
        f"You can start chatting anytime."
    )

# ================= WELCOME =================
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_settings["welcome"]:
        await update.message.reply_text(
            "Welcome.\n"
            "This bot is under beta testing.\n"
            "Please mention the bot if you need a response."
        )

# ================= AI BACKGROUND =================
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
                        f"Reply professionally, short and clear.\n"
                        f"Use minimal emojis 🙂\n"
                        f"Never use roleplay actions."
                    )
                },
                {"role": "user", "content": text}
            ],
            temperature=0.6,
            max_tokens=60
        )

        reply = clean_reply(response.choices[0].message.content)
        if reply:
            await update.message.reply_text(reply)

    except Exception:
        pass

# ================= MAIN =================
async def reply_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    text = update.message.text.strip()

    # OWNER SETTINGS
    if is_owner(user.id):
        intent = owner_intent(text)
        if intent:
            k, v = intent
            bot_settings[k] = v
            await update.message.reply_text(f"Setting updated: {k} = {v}")
            return

    # OWNER INFO
    if is_owner_question(text):
        await update.message.reply_text(
            f"I was developed by {OWNER_NAME}.\n"
            f"Telegram: {OWNER_USERNAME}"
        )
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
        h = now_time().hour
        if h < 12:
            await update.message.reply_text("Good morning ☀️")
        elif h < 18:
            await update.message.reply_text("Good afternoon 🌤️")
        else:
            await update.message.reply_text("Good evening 🌆")
        return

    # TIME / DATE
    if is_time_q(text):
        n = now_time()
        await update.message.reply_text(
            f"{n.strftime('%A')}\n"
            f"{n.strftime('%d %B %Y')}\n"
            f"{n.strftime('%I:%M %p')}"
        )
        return

    # TOMORROW
    if is_tomorrow_q(text):
        t = now_time() + timedelta(days=1)
        await update.message.reply_text(
            f"Tomorrow is {t.strftime('%A')}, {t.strftime('%d %B %Y')}"
        )
        return

    # MEMORY
    get_memory(user.id).append(text)

    # BACKGROUND AI
    context.application.create_task(
        send_ai_reply(update, context, text)
    )

# ================= RUN =================
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

    print("Miss Bloosm running...")
    app.run_polling()

if __name__ == "__main__":
    main()
