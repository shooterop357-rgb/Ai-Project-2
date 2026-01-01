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
def ist_now():
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

    hour = ist_now().hour
    if mood == "sad":
        mode = "support"
    elif hour >= 22 or hour <= 5:
        mode = "night"
    else:
        mode = "calm"

    return mood, mode

# =========================
# CONSTANT LISTS
# =========================
DISRESPECT_WORDS = [
    "randi", "pagal", "chutiya", "mc", "bc",
    "beta", "bacha", "idiot"
]

APOLOGY_WORDS = [
    "sorry", "maaf", "galti ho gayi",
    "my mistake", "apologies", "sry"
]

FAKE_APOLOGY_HINTS = [
    "but", "lekin", "par", "still"
]

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

    memory = load_memory()
    if uid not in memory:
        memory[uid] = {"chat": [], "strikes": 0}

    # =========================
    # OWNER VERIFY
    # =========================
    if "developer" in text:
        if user_id == OWNER_ID:
            await update.message.reply_text(
                f"😌 Haan, mujhe pata hai.\nAap hi mere creator ho {DEVELOPER_USERNAME} 🌸"
            )
        else:
            await update.message.reply_text(
                f"😄 Mujhe to sirf itna pata hai ki mujhe {DEVELOPER_USERNAME} ne build kiya hai 🌸"
            )
        return

    if "age" in text or "umar" in text:
        await update.message.reply_text("Main 21 saal ki hoon 🌸")
        return

    # =========================
    # APOLOGY HANDLING
    # =========================
    if any(w in text for w in APOLOGY_WORDS):
        # fake apology check
        if any(h in text for h in FAKE_APOLOGY_HINTS):
            await update.message.reply_text(
                "🙂 Theek hai, par apology ke saath clarity bhi zaroori hoti hai.\nChalo araam se baat karte hain."
            )
            return

        # genuine apology → reset strikes + soft tone
        if memory[uid]["strikes"] > 0:
            memory[uid]["strikes"] = 0
            save_memory(memory)
            await update.message.reply_text(
                "Theek hai 😌\nChalo fresh start karte hain."
            )
            return

    # =========================
    # 3-STRIKE DISRESPECT SYSTEM
    # =========================
    if any(w in text for w in DISRESPECT_WORDS):
        memory[uid]["strikes"] += 1
        strikes = memory[uid]["strikes"]
        save_memory(memory)

        if strikes == 1:
            await update.message.reply_text(
                "Main respect se baat karti hoon.\nAaraam se baat karte hain 🙂"
            )
            return

        if strikes == 2:
            await update.message.reply_text(
                "Is tarah ki language theek nahi.\nPlease tone theek rakho."
            )
            return

        if strikes >= 3:
            return  # silent ignore

    # =========================
    # MOOD / MODE
    # =========================
    mood, mode = detect_mode_and_mood(text)

    if mood == "sexual":
        await update.message.reply_text(
            "😳 Arre… itna aage nahi.\nMain thodi classy hoon 😌"
        )
        return

    # =========================
    # MEMORY CHAT
    # =========================
    memory[uid]["chat"].append({"role": "user", "content": raw})
    memory[uid]["chat"] = memory[uid]["chat"][-MAX_MEMORY:]
    save_memory(memory)

    # =========================
    # SYSTEM PROMPT (FINAL)
    # =========================
    system_prompt = f"""
You are {BOT_NAME} 🌸, a 21-year-old girl.

You are kind, intelligent, emotionally mature, and self-respecting.
You understand people and adapt without losing dignity.

MODE: {mode.upper()}

Mode behavior:
- night → soft, warm, comforting
- calm → balanced, gentle, logical
- support → caring, listening, guiding

Core rules:
- Never mirror disrespect
- Never over-apologize
- Set boundaries once, calmly
- Forgive genuine apologies and soften tone
- Detect fake apologies and stay neutral

Style:
- Hinglish
- Short, meaningful replies
- Soft emojis 😊😌🌸
- Never dramatic, never robotic

Strict:
- Never mention AI, API, system, backend
"""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(memory[uid]["chat"])

    try:
        await update.message.chat.send_action(ChatAction.TYPING)
        res = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.6,
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

    memory[uid]["chat"].append({"role": "assistant", "content": reply})
    memory[uid]["chat"] = memory[uid]["chat"][-MAX_MEMORY:]
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
