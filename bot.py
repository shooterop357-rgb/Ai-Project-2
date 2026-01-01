import os
import json
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
from telegram.constants import ChatAction

from groq import Groq
import google.generativeai as genai

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

BOT_NAME = "Miss Bloosm"
BOT_AGE = "21"
DEVELOPER_USERNAME = "@Frx_Shooter"
OWNER_ID = 5436530930

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
MAX_MEMORY = 120

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
# HELPERS
# =========================
def ist_time():
    return datetime.now(TIMEZONE)

def detect_mode_and_mood(text: str):
    t = text.lower()

    sexual = ["sex", "nude", "kiss", "bed", "hot"]
    sad = ["sad", "alone", "cry", "broken", "depressed"]
    angry = ["angry", "gussa", "hate"]
    happy = ["happy", "lol", "haha", "excited"]

    if any(w in t for w in sexual):
        mood = "sexual"
    elif any(w in t for w in sad):
        mood = "sad"
    elif any(w in t for w in angry):
        mood = "angry"
    elif any(w in t for w in happy):
        mood = "happy"
    else:
        mood = "cool"

    hour = ist_time().hour
    if mood == "sad":
        mode = "support"
    elif hour >= 22 or hour <= 5:
        mode = "night"
    else:
        mode = "calm"

    return mood, mode

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello, I’m Miss Bloosm 🌸\n\n"
        "I’m a calm, friendly AI designed for natural conversations.\n"
        "Human Like Replay Feels Emotionas.\n\n"
        "⚠️ This bot is currently in beta.\n"
        "Some replies may not always be perfect."
    )

# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    raw = update.message.text.strip()
    text = raw.lower()
    uid = str(user_id)

    # OWNER VERIFICATION
    if user_id == OWNER_ID and "developer" in text:
        await update.message.reply_text(
            f"😌 Haan, mujhe pata hai.\nAap hi mere creator ho {DEVELOPER_USERNAME} 🌸"
        )
        return

    if user_id != OWNER_ID and "developer" in text:
        await update.message.reply_text(
            f"😄 Mujhe to sirf itna pata hai ki mujhe {DEVELOPER_USERNAME} ne build kiya hai 🌸"
        )
        return

    if "age" in text or "umar" in text:
        await update.message.reply_text("Main 21 saal ki hoon 🌸")
        return

    mood, mode = detect_mode_and_mood(text)

    # SEXUAL BOUNDARY (INTELLIGENT)
    if mood == "sexual":
        await update.message.reply_text(
            "😳 Arre… itna aage nahi.\nMain thodi classy hoon 😌"
        )
        return

    memory = load_memory()
    if uid not in memory:
        memory[uid] = []

    memory[uid].append({"role": "user", "content": raw})
    memory[uid] = memory[uid][-MAX_MEMORY:]
    save_memory(memory)

    # =========================
    # SYSTEM PROMPT (FINAL)
    # =========================
    system_prompt = f"""
You are {BOT_NAME} 🌸, a 21-year-old girl.

You are kind, emotionally intelligent, and understanding.
You behave like a normal, real girl.

MODE: {mode.upper()}

Mode behavior:
- night: soft, warm, comforting
- calm: balanced, gentle, logical
- support: caring, listening, guiding

Mood handling:
- sad → emotional support
- angry → calm grounding
- happy → share joy
- cool → friendly
- sexual → already handled outside

Personality:
- Intelligent and clever
- Never naive
- Never blindly agree
- Adjust behavior based on feelings

Style:
- Hinglish
- Short, meaningful replies
- Soft emojis 😊😌🌸
- Never dramatic
- Never robotic

Rules:
- Never mention AI, API, system, backend
- Never over-explain
- Always think before replying
"""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(memory[uid])

    try:
        await update.message.chat.send_action(ChatAction.TYPING)
        res = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.65,
            max_tokens=180,
        )
        reply = res.choices[0].message.content.strip()
    except Exception:
        try:
            reply = gemini_model.generate_content(
                system_prompt + "\nUser: " + raw
            ).text.strip()
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
    print("Miss Bloosm running 🌸")
    app.run_polling()

if __name__ == "__main__":
    main()
