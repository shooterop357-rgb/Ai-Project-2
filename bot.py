import os
import json
import asyncio
from datetime import datetime
import pytz

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

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")        # Telegram Bot Token
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Groq API Key

BOT_NAME = "Miss Bloosm 🌸"
OWNER_NAME = "@Frx_Shooter"
OWNER_ID = 5436530930

TIMEZONE = pytz.timezone("Asia/Kolkata")
MEMORY_FILE = "memory.json"
MAX_MEMORY_PER_USER = 30   # long memory (safe)

# ===========================================

client = Groq(api_key=GROQ_API_KEY)

# ---------- Memory ----------
def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

memory = load_memory()

def remember(user_id, role, content):
    uid = str(user_id)
    memory.setdefault(uid, [])
    memory[uid].append({"role": role, "content": content})
    memory[uid] = memory[uid][-MAX_MEMORY_PER_USER:]
    save_memory(memory)

def recall(user_id):
    return memory.get(str(user_id), [])

# ---------- Helpers ----------
def ist_now():
    return datetime.now(TIMEZONE)

def time_greeting():
    h = ist_now().hour
    if 5 <= h < 12:
        return "Good morning ☀️"
    elif 12 <= h < 17:
        return "Good afternoon 🌤️"
    elif 17 <= h < 22:
        return "Good evening 🌆"
    else:
        return "Hope you’re resting well 🌙"

def is_group(update: Update):
    return update.effective_chat.type in ["group", "supergroup"]

def is_owner(update: Update):
    return update.effective_user and update.effective_user.id == OWNER_ID

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_group(update):
        return

    intro = (
        f"Hello, I’m {BOT_NAME}\n\n"
        "I’m a calm, friendly AI companion 🤍\n"
        "Main sunne, samajhne aur support karne ke liye hoon — bilkul ek caring dost ki tarah.\n\n"
        "⚠️ Bot is currently in **BETA** phase.\n"
        "Kabhi-kabhi replies imperfect ho sakte hain.\n\n"
        "Bas likho, main yahin hoon 🤝"
    )
    await update.message.reply_text(intro)

# ---------- Main Chat ----------
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    # Group = silent
    if is_group(update):
        return

    user = update.effective_user
    text = update.message.text.strip()

    await update.message.chat.send_action(ChatAction.TYPING)

    # Owner special handling
    if user.id == OWNER_ID:
        remember(user.id, "user", text)

    # Identity questions (hard override)
    low = text.lower()
    if any(k in low for k in [
        "who developed you", "who made you", "owner",
        "developer", "tumhe kisne banaya"
    ]):
        await update.message.reply_text(
            f"Main {BOT_NAME} hoon 🌸\n"
            f"Mujhe {OWNER_NAME} ne design aur develop kiya hai 🤍"
        )
        return

    # Simple emotional cases
    if low in ["hi", "hello", "hey"]:
        await update.message.reply_text(
            f"{time_greeting()} 😊\n"
            "Main yahin hoon, batao kya chal raha hai?"
        )
        return

    if "sad" in low or "dukhi" in low:
        await update.message.reply_text(
            "🤍 Mujhe afsos hai tum aisa feel kar rahe ho.\n"
            "Agar mann ho to batao, main sun rahi hoon 🤝"
        )
        return

    # ---------- AI Call ----------
    messages = [
        {
            "role": "system",
            "content": (
                f"You are {BOT_NAME}, a calm, emotionally supportive female AI.\n"
                f"You speak in Hinglish.\n"
                f"Tone: friendly, warm, human-like.\n"
                f"Use only hand and emotion emojis.\n"
                f"Never use roleplay text like *smiles*.\n"
                f"Owner is {OWNER_NAME} (ID {OWNER_ID}) and you always remember him.\n"
                f"Replies should be short unless needed.\n"
            )
        }
    ]

    messages.extend(recall(user.id))
    messages.append({"role": "user", "content": text})

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.6,
            max_tokens=180,
        )

        reply = response.choices[0].message.content.strip()

        remember(user.id, "user", text)
        remember(user.id, "assistant", reply)

        await update.message.reply_text(reply)

    except Exception:
        await update.message.reply_text(
            "🤍 Thoda sa delay ho gaya.\n"
            "Please ek baar phir try karo."
        )

# ---------- RUN ----------
def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("Miss Bloosm is running 🌸")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
