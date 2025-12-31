import os
import json
import asyncio
from datetime import datetime
import pytz

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

from groq import Groq

# =========================
# 🔐 ENV VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")          # Telegram Bot Token
GROQ_API_KEY = os.getenv("GROQ_API_KEY")    # Groq API Key

OWNER_ID = 5436530930  # Frx_Shooter (locked)

# =========================
# 🤖 GROQ CLIENT
# =========================
groq_client = Groq(api_key=GROQ_API_KEY)

# =========================
# 🧠 MEMORY (FILE BASED)
# =========================
MEMORY_FILE = "memory.json"

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
# ⏰ IST TIME
# =========================
def get_ist_time():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    return (
        now.strftime("%I:%M %p"),
        now.strftime("%A, %d %B %Y"),
        now.hour
    )

# =========================
# 🌸 START COMMAND
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Hello, I’m **Miss Blossom** 🌸\n\n"
        "I’m a calm, friendly AI companion 🤍\n"
        "Main yahan hoon aapki baat sunne aur support karne ke liye.\n\n"
        "⚠️ Bot abhi **BETA phase** mein hai,\n"
        "kabhi-kabhi replies imperfect ho sakte hain.\n\n"
        "Aap freely baat kar sakte ho 🙂"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# =========================
# 💬 MAIN CHAT HANDLER
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.lower().strip()

    memory = load_memory()
    user_id = str(user.id)

    if user_id not in memory:
        memory[user_id] = {
            "name": user.first_name,
            "messages": []
        }

    # save last messages (limit 30)
    memory[user_id]["messages"].append(text)
    memory[user_id]["messages"] = memory[user_id]["messages"][-30:]
    save_memory(memory)

    # typing action
    await update.message.chat.send_action(ChatAction.TYPING)

    # =========================
    # ⏰ TIME / DATE HANDLER
    # =========================
    if any(k in text for k in [
        "time kya", "real time", "kya time",
        "samay kya", "current time", "abhi time"
    ]):
        time_now, date_now, _ = get_ist_time()
        await update.message.reply_text(
            f"⏰ Abhi time hai: {time_now}\n"
            f"📅 Date: {date_now} 😊"
        )
        return

    # =========================
    # 🌞 GREETINGS (TIME BASED)
    # =========================
    if "good morning" in text:
        await update.message.reply_text("Good morning ☀️ umeed hai aaj ka din achha jaaye 🙂")
        return

    if "good night" in text:
        await update.message.reply_text("Good night 🌙 aaram se sona, main yahin hoon 🤍")
        return

    # =========================
    # 👑 OWNER DETECTION
    # =========================
    if user.id == OWNER_ID and "don't reply" in text:
        await update.message.reply_text(
            "Theek hai 🙏 main is group / chat me reply nahi karungi."
        )
        return

    # =========================
    # 🤍 EMOTIONAL SHORT REPLIES
    # =========================
    if "sad" in text or "dukhi" in text:
        await update.message.reply_text(
            "🤍 Sun ke bura laga… main yahin hoon, aap akela nahi ho."
        )
        return

    # =========================
    # 🧠 AI RESPONSE (GROQ)
    # =========================
    try:
        system_prompt = (
            "You are Miss Blossom 🌸.\n"
            "You are calm, friendly, emotional, and supportive.\n"
            "Reply in Hinglish.\n"
            "Use only hand and emotion emojis (🙂🤍🙏☀️🌙).\n"
            "Keep replies short and human-like.\n"
            "You know your owner is Frx_Shooter.\n"
            "Never sound robotic or philosophical."
        )

        completion = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.6,
            max_tokens=120
        )

        reply = completion.choices[0].message.content
        await update.message.reply_text(reply)

    except Exception:
        await update.message.reply_text(
            "🤍 Thoda slow ho gayi hoon… ek baar phir try karo na 🙂"
        )

# =========================
# 🚀 MAIN
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("Miss Blossom is running 🌸")
    app.run_polling()

if __name__ == "__main__":
    main()
