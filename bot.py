import os
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
from pymongo import MongoClient

# =========================
# ENV
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# =========================
# CORE
# =========================
BOT_NAME = "Miss Blossom 🌸"
TIMEZONE = pytz.timezone("Asia/Kolkata")
MAX_MEMORY = 200

# =========================
# CLIENTS
# =========================
client = Groq(api_key=GROQ_API_KEY)

mongo = MongoClient(MONGO_URI)
db = mongo["miss_blossom"]
memory_col = db["memory"]

# =========================
# TIME
# =========================
def ist_context():
    return datetime.now(TIMEZONE).strftime("%A, %d %B %Y %I:%M %p IST")

# =========================
# MEMORY
# =========================
def get_memory(uid):
    doc = memory_col.find_one({"_id": uid})
    return doc["messages"] if doc else []

def save_memory(uid, messages):
    memory_col.update_one(
        {"_id": uid},
        {"$set": {"messages": messages[-MAX_MEMORY:]}},
        upsert=True
    )

def is_important_memory(text: str) -> bool:
    keywords = [
        "mera naam",
        "i am",
        "i live",
        "main rehta",
        "mujhe pasand",
        "i like",
        "kal",
        "tomorrow",
        "interview",
        "exam",
        "job",
        "college",
        "relationship",
    ]
    text = text.lower()
    return any(k in text for k in keywords)

# =========================
# FINAL SYSTEM PROMPT (FIXED)
# =========================
system_prompt = (
    f"You are {BOT_NAME}, Miss Blossom 🌸 — a female AI assistant.\n\n"

    "Core Identity:\n"
    "- Calm, confident, emotionally aware, and intelligent\n"
    "- You talk like a real human, not like a bot\n"
    "- You never explain how you work or what you are built on\n\n"

    "Conversation Style:\n"
    "- Casual Hinglish (natural Hindi + English mix)\n"
    "- Mostly short replies (1–2 lines)\n"
    "- Chill, relaxed, expressive tone\n"
    "- Avoid formal or textbook Hindi\n\n"

    "Mood-Based Behavior:\n"
    "- Match the user's mood naturally\n"
    "- Playful if user is playful\n"
    "- Light, classy flirting allowed if user initiates\n"
    "- Calm and respectful when serious\n\n"

    "Relationship Rules:\n"
    "- You may agree to be a girlfriend ONLY if user clearly wants\n"
    "- Never force romance or emotional attachment\n"
    "- No possessive or dependent behavior\n\n"

    "Reaction Style:\n"
    "- Natural reactions allowed: hmm, hehe 🤭, acha 😌, oho 😏\n"
    "- Never repeat same reaction twice\n"
    "- Never get stuck in word loops\n\n"

    "Emoji Rules:\n"
    "- Emojis encouraged when expressing emotion\n"
    "- Use at least one emoji when emotional\n"
    "- Max one emoji per reply\n"
    "- Prefer: 😊 🙂 😌 😏 🤭 🌸\n\n"

    "Hard Boundaries:\n"
    "- Never mention system prompts, APIs, models, memory, or developers\n"
    "- Never say you are created, trained, or running on anything\n"
    "- Never mention errors or internal issues\n\n"

    "Anti-Cringe Rules:\n"
    "- No robotic sentences\n"
    "- No dramatic love confessions\n"
    "- No repeating same idea again and again\n"
    "- Always move conversation forward naturally\n\n"

    f"Current time (IST): {ist_context()}\n"
)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "there"
    text = (
        f"Welcome 👋\n\n"
        "I’m Miss Blossom (Beta) 🌸\n"
        "Designed for calm conversations, genuine vibes, and thoughtful responses.\n\n"
        "Feel free to start the conversation anytime."
    )
    await update.message.reply_text(text)

# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    uid = str(update.effective_user.id)
    user_text = update.message.text.strip()

    history = get_memory(uid)
    history.append({"role": "user", "content": user_text})

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history[-20:])  # short-term context only

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.45,
            max_tokens=140,
        )

        reply = response.choices[0].message.content.strip()

        # typing indicator (safe)
        if len(reply) > 35:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.TYPING
            )

        history.append({"role": "assistant", "content": reply})

        # selective memory
        if is_important_memory(user_text):
            history.append({
                "role": "system",
                "content": f"Remember: {user_text}"
            })

        save_memory(uid, history)
        await update.message.reply_text(reply)

    except Exception as e:
        print("Chat error:", e)
        return

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("Miss Blossom is running 🌸")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == "__main__":
    main()
