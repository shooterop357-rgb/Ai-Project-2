import os
import json
import random
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
# 🔐 ENV
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

OWNER_ID = 5436530930
OWNER_NAME = "Frx_Shooter"

# =========================
# 🤖 GROQ CLIENT
# =========================
groq_client = Groq(api_key=GROQ_API_KEY)

# =========================
# 🧠 MEMORY
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
# ⏰ IST CONTEXT
# =========================
def ist_context():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    return f"Current IST time: {now.strftime('%I:%M %p')}, Date: {now.strftime('%d %B %Y')}"

# =========================
# 🌸 START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello, I’m **Miss Blossom** 🌸\n\n"
        "Main ek calm, friendly AI companion hoon 🤍\n"
        "Aapki baat sunne aur support karne ke liye yahan hoon.\n\n"
        "⚠️ Bot abhi **BETA phase** mein hai,\n"
        "kabhi-kabhi replies imperfect ho sakte hain.\n\n"
        "Aap freely baat kar sakte ho 🙂",
        parse_mode="Markdown"
    )

# =========================
# 💬 CHAT (PURE AI)
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text.strip()

    # 🚫 GROUP FLOOD CONTROL
    if chat.type in ["group", "supergroup"]:
        if context.bot.username.lower() not in text.lower():
            return

    memory = load_memory()
    uid = str(user.id)

    if uid not in memory:
        memory[uid] = {
            "name": user.first_name,
            "messages": []
        }

    memory[uid]["messages"].append(text)
    memory[uid]["messages"] = memory[uid]["messages"][-30:]
    save_memory(memory)

    await update.message.chat.send_action(ChatAction.TYPING)

    # =========================
    # 🤖 GROQ AI ONLY
    # =========================
    try:
        completion = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Miss Blossom 🌸, a female AI.\n"
                        "Personality: calm, friendly, emotionally supportive.\n"
                        "Language: Hinglish only.\n"
                        "Tone: like a caring friend, not robotic.\n"
                        "Use only emotion or hand emojis 🤍🙂🙏😊.\n"
                        "Keep replies short and human.\n\n"
                        f"Your owner is {OWNER_NAME}.\n"
                        f"{ist_context()}\n\n"
                        "Never say you are slow, broken, or technical.\n"
                        "If you don't know something, reply gently like a human."
                    )
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.7,
            max_tokens=150
        )

        reply = completion.choices[0].message.content.strip()
        await update.message.reply_text(reply)

    except Exception:
        # 🧠 AI-LIKE FALLBACK (NOT PYTHON STYLE)
        fallback = random.choice([
            "🙂 Lagta hai thoda sa ruk gayi thi… ab bolo na.",
            "🤍 Ek second ke liye connection loose ho gaya tha, phir se bolo.",
            "🙏 Main yahin hoon, bas thoda sa delay hua."
        ])
        await update.message.reply_text(fallback)

# =========================
# 🚀 MAIN
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Miss Blossom 🌸 running (Pure Groq AI)")
    app.run_polling()

if __name__ == "__main__":
    main()
