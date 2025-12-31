import json
import os
import pytz
from datetime import datetime
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters
)
from openai import OpenAI

# ===================== CONFIG =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")          # Telegram Bot Token
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OWNER_ID = 5436530930   # YOUR TELEGRAM ID
BOT_NAME = "Miss Bloosm"
TIMEZONE = pytz.timezone("Asia/Kolkata")

MEMORY_FILE = "memory.json"
MAX_MEMORY = 50   # safe + human-like

client = OpenAI(api_key=OPENAI_API_KEY)

# ===================== MEMORY =====================
if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w") as f:
        json.dump({}, f)

def load_memory():
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_memory(user_id):
    data = load_memory()
    return data.get(str(user_id), {
        "name": None,
        "history": [],
        "blocked": False
    })

def update_user_memory(user_id, memory):
    data = load_memory()
    data[str(user_id)] = memory
    save_memory(data)

# ===================== SYSTEM PROMPT =====================
SYSTEM_PROMPT = """
You are Miss Bloosm.

Personality:
- Calm
- Friendly
- Family-safe
- Supportive
- Female identity
- Short replies by default
- Warm emojis allowed 🙂🌸

Rules:
- Never say you are an AI model
- Never mention OpenAI or APIs
- Never give technical/internal info
- No flirting, only soft warmth
- Respond like a caring friend
- If user is sad, comfort first
- If user says "nothing", reply softly and stop

Owner:
- You were developed by Frx_Shooter (Telegram: @Frx_Shooter)

Memory:
- Remember user's name if told
- Use name naturally
"""

# ===================== HELPERS =====================
def now_india():
    return datetime.now(TIMEZONE)

# ===================== COMMANDS =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Hey 🙂 I’m {BOT_NAME}.\n"
        "⚠️ Bot is under beta phase.\n"
        "Replies may be imperfect sometimes.\n\n"
        "You can talk freely 🌸"
    )

# ===================== MAIN CHAT =====================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

    memory = get_user_memory(user.id)

    # Blocked users
    if memory.get("blocked"):
        return

    # Save name
    if text.lower().startswith("my name is"):
        name = text.split("my name is", 1)[1].strip()
        memory["name"] = name
        update_user_memory(user.id, memory)
        await update.message.reply_text(f"Nice to meet you, {name} 🙂")
        return

    # Typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    # Build messages
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if memory["name"]:
        messages.append({
            "role": "system",
            "content": f"The user's name is {memory['name']}."
        })

    for h in memory["history"][-MAX_MEMORY:]:
        messages.append(h)

    messages.append({"role": "user", "content": text})

    # OpenAI call
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=120,
            temperature=0.7
        )
        reply = response.choices[0].message.content.strip()
    except Exception:
        reply = "Thoda sa issue aa gaya 😔 thodi der baad try karo."

    # Update memory
    memory["history"].append({"role": "user", "content": text})
    memory["history"].append({"role": "assistant", "content": reply})
    memory["history"] = memory["history"][-MAX_MEMORY:]
    update_user_memory(user.id, memory)

    await update.message.reply_text(reply)

# ===================== RUN =====================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    app.run_polling()

if __name__ == "__main__":
    main()
