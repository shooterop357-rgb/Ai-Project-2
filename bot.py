import os
import json
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI
from groq import Groq

# =========================
# ENV
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not BOT_TOKEN or not OPENAI_API_KEY or not GROQ_API_KEY:
    raise RuntimeError("Missing ENV variables")

# =========================
# CLIENTS
# =========================
openai_client = OpenAI(api_key=OPENAI_API_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# =========================
# SYSTEM PROMPT
# =========================
SYSTEM_PROMPT = (
    "You are Miss Bloosm, a female AI assistant.\n"
    "Your developer is @Frx_Shooter.\n"
    "You speak calmly, softly, and with emotional understanding.\n"
    "You respond like a caring human, not like a robot.\n"
    "You understand emotions and reply gently.\n"
    "You never mention technical details or errors.\n"
    "If asked who created you, you say @Frx_Shooter.\n"
)

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
# /START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello, I’m Miss Bloosm.\nYou can talk to me freely."
    )

# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    uid = str(user.id)
    user_text = update.message.text.strip()

    memory = load_memory()
    if uid not in memory:
        memory[uid] = []
        name = user.first_name or "User"
        username = f"@{user.username}" if user.username else "unknown"
        memory[uid].append({
            "role": "system",
            "content": f"The user's name is {name}, username is {username}."
        })

    memory[uid].append({"role": "user", "content": user_text})
    memory[uid] = memory[uid][-MAX_MEMORY:]
    save_memory(memory)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(memory[uid])

    reply = None

    # ---- OPENAI FIRST ----
    try:
        r = openai_client.responses.create(
            model="gpt-4.1-mini",
            input=messages
        )
        reply = r.output_text.strip()
    except Exception:
        reply = None

    # ---- GROQ FALLBACK ----
    if not reply:
        try:
            r = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.6,
                max_tokens=200,
            )
            reply = r.choices[0].message.content.strip()
        except Exception:
            reply = None

    # ---- FINAL ----
    if reply:
        memory[uid].append({"role": "assistant", "content": reply})
        memory[uid] = memory[uid][-MAX_MEMORY:]
        save_memory(memory)
        await update.message.reply_text(reply)
    else:
        return  # SILENT (old method)

# =========================
# RUN
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Miss Bloosm running (Hybrid AI)")
    app.run_polling()

if __name__ == "__main__":
    main()
