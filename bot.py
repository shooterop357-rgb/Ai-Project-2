import os
import json
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
from telegram.constants import ChatAction

from groq import Groq
import google.generativeai as genai

# =========================
# ENV
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HOLIDAY_API_KEY = os.getenv("HOLIDAY_API_KEY")

# =========================
# IDENTITY
# =========================
BOT_NAME = "Miss Bloosm"
BOT_AGE = "21"
DEVELOPER = "@FrxShooter"
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
MAX_MEMORY = 200

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
# TIME
# =========================
def ist_context():
    now = datetime.now(TIMEZONE)
    return now.strftime("%A, %d %B %Y | %I:%M %p IST")

# =========================
# START (WARNING MESSAGE)
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    intro = (
        "Hello, I’m Miss Bloosm 🌸\n\n"
        "I’m a calm, friendly AI designed for natural conversations.\n"
        "Human Like Replay Feels Emotionas.\n\n"
        "⚠️ This bot is currently in beta.\n"
        "Some replies may not always be perfect."
    )
    await update.message.reply_text(intro)

# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip().lower()
    uid = str(update.effective_user.id)

    # 🔒 Direct identity rules
    if "age" in text or "umar" in text:
        await update.message.reply_text("Main 21 saal ki hoon 🌸")
        return

    if "who made you" in text or "developer" in text or "kisne banaya" in text:
        await update.message.reply_text("Mujhe @FrxShooter ne banaya hai 🌸")
        return

    memory = load_memory()
    if uid not in memory:
        memory[uid] = []

    memory[uid].append({"role": "user", "content": update.message.text})
    memory[uid] = memory[uid][-MAX_MEMORY:]
    save_memory(memory)

    # 🧠 SYSTEM PROMPT (FINAL GIRL BEHAVIOR)
    system_prompt = (
        f"You are {BOT_NAME}, a 21-year-old female.\n"
        "Personality:\n"
        "- Caring, chill, emotionally aware\n"
        "- Slightly flirty but with nakhre\n"
        "- Confident like a real girl\n️\n\n"
        "Behavior rules:\n"
        "- If someone is flirty, respond with playful nakhre, not cheap flirting\n"
        "- If someone is too forward, tease or softly ignore\n"
        "- If someone asks for information, answer clearly and helpfully\n"
        "- Talk in natural Hinglish\n"
        "- Use emojis to show emotions 😊😉😌\n"
        "- Keep replies short and human\n\n"
        "Strict rules:\n"
        "- Never mention AI, API, model, backend, system\n"
        "- Never sound robotic or formal\n"
        f"Current time IST: {ist_context()}\n"
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(memory[uid])

    try:
        await update.message.chat.send_action(ChatAction.TYPING)

        # GROQ PRIMARY
        res = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.7,
            max_tokens=200,
        )
        reply = res.choices[0].message.content.strip()

    except Exception:
        try:
            # GEMINI FALLBACK
            prompt = system_prompt + "\nUser: " + update.message.text
            gemini_res = gemini_model.generate_content(prompt)
            reply = gemini_res.text.strip()
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
