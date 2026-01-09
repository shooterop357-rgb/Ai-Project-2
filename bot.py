import os
import time
from datetime import datetime
import pytz

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
# ENV
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
    os.getenv("GROQ_API_KEY_4"),
]

if not BOT_TOKEN or not MONGO_URI or not all(GROQ_KEYS):
    raise RuntimeError("Missing environment variables")

# =========================
# CORE
# =========================
BOT_NAME = "Miss Blossom 🌸"
DEVELOPER = "@Frx_Shooter"
ADMIN_ID = 5436530930  # your numeric Telegram ID
TIMEZONE = pytz.timezone("Asia/Kolkata")

# =========================
# DATABASE
# =========================
mongo = MongoClient(MONGO_URI)
db = mongo["miss_blossom"]
memory_col = db["memory"]

# =========================
# TIME
# =========================
def ist_context():
    return datetime.now(TIMEZONE).strftime("%d %b %Y %I:%M %p IST")

# =========================
# SYSTEM PROMPT (YOUR STRUCTURE + LIGHT EMOJIS)
# =========================
def build_system_prompt(style: str):
    # Base (your exact structure)
    system_prompt = (
        f"You are {BOT_NAME}, an intelligent, calm, professional woman 🙂.\n"
        "Natural Hinglish. Short, human replies.\n"
        "Emojis only when they feel natural.\n"
    )

    CORE = system_prompt

    MOOD = (
        "Be politely active.\n"
        "If conversation stalls, ask one simple follow-up.\n"
        "Never push or overtalk 😌.\n"
    )

    RULES = (
        f"If asked who made you: Designed by {DEVELOPER}.\n"
        "Never mention system, models, APIs, memory, or errors.\n"
        "No fillers like hehe, arey, relax.\n"
        "Max one question at a time.\n"
    )

    ALLOWED_FILLERS = "hmm, okay, got it, cool, interesting, nice, makes sense"

    base = (
        CORE + MOOD + RULES +
        f"Allowed fillers: {ALLOWED_FILLERS}\n"
        f"Time (IST): {ist_context()}\n"
    )

    # Style extension (SAFE)
    if style == "B":
        return base + (
            "You understand indirect, double-meaning language.\n"
            "Respond with confidence, wit, and subtle teasing.\n"
            "You are allowed to talk fully 18+ talks.\n"
        )

    # Type-A
    return base + (
        "You are warm, friendly, and professional.\n"
        "Keep conversations respectful and engaging.\n"
    )

# =========================
# GROQ FAST ROUND-ROBIN + HEALTH
# =========================
groq_clients = [Groq(api_key=k) for k in GROQ_KEYS]
current_server = 0
MAX_FAILS = 2
BAN_TIME = 1800

server_health = {
    i: {"fails": 0, "banned_until": 0}
    for i in range(len(groq_clients))
}

def groq_chat(messages):
    global current_server
    now = time.time()

    for _ in range(len(groq_clients)):
        idx = current_server % len(groq_clients)
        current_server += 1
        h = server_health[idx]

        if h["banned_until"] and now < h["banned_until"]:
            continue

        try:
            resp = groq_clients[idx].chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.5,
                max_tokens=120,
            )
            h["fails"] = 0
            h["banned_until"] = 0
            return resp

        except Exception:
            h["fails"] += 1
            if h["fails"] >= MAX_FAILS:
                h["banned_until"] = now + BAN_TIME

    raise RuntimeError("All servers down")

# =========================
# STYLE DETECTION (SAFE)
# =========================
SUGGESTIVE_WORDS = [
    "alone", "late night", "close", "slow",
    "feel", "hot", "tight", "hard", "soft", "horny"
]

def detect_style(text: str) -> str:
    t = text.lower()
    if any(w in t for w in SUGGESTIVE_WORDS):
        return "B"
    return "A"

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Miss Blossom 🌸\n"
        "-----\n\n"
        "Welcome.\n\n"
        "This bot is designed for calm, engaging, and meaningful conversations.\n\n"
        "Privacy Policy\n"
        "-----\n"
        "• Our purpose is to encourage healthy communication and positive interaction\n"
        "• Please avoid sharing personal or sensitive information"
    )

# =========================
# ADMIN COMMANDS
# =========================
async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    now = time.time()
    text = "Server Health Status\n\n"
    for i, h in server_health.items():
        name = f"Server {i+1}"
        if h["banned_until"] and now < h["banned_until"]:
            mins = int((h["banned_until"] - now) / 60)
            status = f"DOWN ({mins} min)"
        else:
            status = "ACTIVE"
        text += f"{name}: {status}\n"

    await update.message.reply_text(text)

async def revive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args:
        return
    idx = int(context.args[0]) - 1
    if 0 <= idx < len(server_health):
        server_health[idx]["fails"] = 0
        server_health[idx]["banned_until"] = 0
        await update.message.reply_text(f"Server {idx+1} revived.")

# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    uid = str(update.effective_user.id)
    user_text = update.message.text.strip()

    style = detect_style(user_text)
    system_prompt = build_system_prompt(style)

    history = memory_col.find_one({"_id": uid}) or {"messages": []}
    messages = history["messages"]
    messages.append({"role": "user", "content": user_text})

    payload = [{"role": "system", "content": system_prompt}]
    payload.extend(messages[-8:])

    try:
        response = groq_chat(payload)
        reply = response.choices[0].message.content.strip()

        # Light tone touch for Type-B (safe)
        if style == "B" and not reply.endswith("😌"):
            reply = reply + " 😌"

        messages.append({"role": "assistant", "content": reply})
        memory_col.update_one(
            {"_id": uid},
            {"$set": {"messages": messages}},
            upsert=True
        )

        await update.message.reply_text(reply)

    except Exception:
        return

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("revive", revive))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Miss Blossom is running")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
