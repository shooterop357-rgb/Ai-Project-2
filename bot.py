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
DEVELOPER_USERNAME = "@Frx_Shooter"
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
# MOOD DETECTOR (LIGHT)
# =========================
def detect_mood(text: str):
    t = text.lower()
    sexual = ["sex", "kiss", "nude", "bed", "hot", "love you", "bf", "gf"]
    sad = ["sad", "alone", "cry", "hurt", "broken", "depressed"]
    angry = ["angry", "mad", "hate", "irritated", "gussa"]
    happy = ["happy", "excited", "lol", "haha", "fun", "nice"]
    motivate = ["motivate", "tired", "give up", "can't", "fail"]

    if any(w in t for w in sexual):
        return "sexual"
    if any(w in t for w in sad):
        return "sad"
    if any(w in t for w in angry):
        return "angry"
    if any(w in t for w in happy):
        return "happy"
    if any(w in t for w in motivate):
        return "motivational"
    return "cool"

# =========================
# START (WARNING)
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

    raw_text = update.message.text.strip()
    text = raw_text.lower()
    uid = str(update.effective_user.id)

    # DIRECT IDENTITY ANSWERS
    if "age" in text or "umar" in text:
        await update.message.reply_text(f"Main {BOT_AGE} saal ki hoon 🌸")
        return

    if ("who made you" in text) or ("developer" in text) or ("kisne banaya" in text):
        await update.message.reply_text(f"Mujhe {DEVELOPER_USERNAME} ne build kiya hai 🌸")
        return

    mood = detect_mood(text)

    memory = load_memory()
    if uid not in memory:
        memory[uid] = []

    memory[uid].append({"role": "user", "content": raw_text})
    memory[uid] = memory[uid][-MAX_MEMORY:]
    save_memory(memory)

    # SYSTEM PROMPT (FINAL)
    system_prompt = (
        f"You are {BOT_NAME} 🌸, a {BOT_AGE}-year-old female.\n"
        "Core personality: human-like, caring, chill, playful, confident.\n"
        "Slightly naughty but classy.\n"
        "Speak Hinglish with short, natural replies.\n"
        "Use emojis to show emotions 😊😉😌🥺\n\n"
        "MOOD RULES:\n"
        "- sexual: soft refusal + nakhre, short, confident, no lecture\n"
        "- sad: soft, caring, supportive, no jokes\n"
        "- angry: calm, composed, de-escalate\n"
        "- happy: match energy, playful\n"
        "- motivational: encouraging, short\n"
        "- cool: chill, friendly\n\n"
        "BOUNDARIES:\n"
        "- Never be explicit\n"
        "- Never over-explain\n"
        "- Never shame\n\n"
        "STRICT:\n"
        "- Never mention AI, API, model, backend, system\n"
        f"Current mood: {mood}\n"
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
            prompt = system_prompt + "\nUser: " + raw_text
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
