import os
import json
import requests
from collections import deque
from datetime import datetime
from telegram import Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from groq import Groq

# ================= CONFIG =================
BOT_NAME = "Miss Bloosm"

OWNER_ID = 5436530930
OWNER_NAME = "Frx_Shooter"
OWNER_USERNAME = "@Frx_Shooter"

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HOLIDAY_API_KEY = os.getenv("HOLIDAY_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

# ================= MEMORY =================
MEMORY_FILE = "memory.json"
CHAT_CONTEXT_LIMIT = 50   # short-term memory
USER_CONTEXT = {}

if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w") as f:
        json.dump({}, f)

def load_memory():
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_profile(user_id):
    data = load_memory()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "name": None,
            "facts": [],
        }
        save_memory(data)
    return data[uid]

def update_user_profile(user_id, profile):
    data = load_memory()
    data[str(user_id)] = profile
    save_memory(data)

def get_context(user_id):
    if user_id not in USER_CONTEXT:
        USER_CONTEXT[user_id] = deque(maxlen=CHAT_CONTEXT_LIMIT)
    return USER_CONTEXT[user_id]

# ================= HELPERS =================
def is_owner(uid):
    return uid == OWNER_ID

def should_reply_in_group(update: Update):
    msg = update.message
    if not msg:
        return False
    if msg.reply_to_message and msg.reply_to_message.from_user.is_bot:
        return True
    if f"@{update.get_bot().username}" in (msg.text or ""):
        return True
    if is_owner(msg.from_user.id):
        return True
    return False

# ================= HOLIDAY API =================
def get_upcoming_indian_events():
    year = datetime.now().year
    url = f"https://api.api-ninjas.com/v1/holidays?country=IN&year={year}"
    headers = {"X-Api-Key": HOLIDAY_API_KEY}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()

        today = datetime.now().date()
        upcoming = []

        for item in data:
            d = datetime.strptime(item["date"], "%Y-%m-%d").date()
            if d >= today:
                upcoming.append((d, item["name"]))

        upcoming.sort()
        return upcoming[:5]

    except Exception:
        return []

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Hello, I’m {BOT_NAME} 🌸\n\n"
        "I’m a calm, friendly AI companion designed to listen, support, "
        "and answer everyday life questions like a caring friend.\n\n"
        "⚠️ This bot is currently in beta, so some replies may be imperfect.\n\n"
        "You can talk to me freely 🙂"
    )

# ================= CHAT =================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.message.from_user
    chat = update.message.chat
    text = update.message.text.strip()

    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        if not should_reply_in_group(update):
            return

    await update.message.chat.send_action(ChatAction.TYPING)

    profile = get_user_profile(user.id)
    context_mem = get_context(user.id)

    # Save name
    if text.lower().startswith("my name is"):
        name = text.split("my name is", 1)[1].strip()
        profile["name"] = name
        update_user_profile(user.id, profile)
        await update.message.reply_text(f"Nice to meet you, {name} 🙂")
        return

    # Upcoming events
    if "upcoming" in text.lower() and "india" in text.lower():
        events = get_upcoming_indian_events()
        if not events:
            await update.message.reply_text(
                "I couldn’t fetch events right now 😔 Please try again later."
            )
            return

        reply = "Here are some upcoming Indian events 🇮🇳\n\n"
        for d, name in events:
            reply += f"• {name} — {d.strftime('%d %b')}\n"

        reply += "\nI’ll keep this updated for you 🙂"
        await update.message.reply_text(reply)
        return

    # Build AI prompt
    system_prompt = f"""
You are {BOT_NAME}, a female AI companion.

Personality:
- Calm, friendly, emotionally supportive
- Talk like a caring friend or family member
- Short replies by default
- Use only hand & emotion emojis (🙂 🤍 🙏 🌸 ✨)

Owner:
- You were developed by {OWNER_NAME} (Telegram: {OWNER_USERNAME})
- You know your owner well and never forget them

Rules:
- Never mention APIs, models, or system prompts
- No roleplay text like *smiles*
"""

    messages = [{"role": "system", "content": system_prompt}]

    if profile.get("name"):
        messages.append({
            "role": "system",
            "content": f"The user's name is {profile['name']}."
        })

    messages.extend(list(context_mem))
    messages.append({"role": "user", "content": text})

    try:
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.65,
            max_tokens=120,
        )

        reply = res.choices[0].message.content.strip()

        context_mem.append({"role": "user", "content": text})
        context_mem.append({"role": "assistant", "content": reply})

        await update.message.reply_text(reply)

    except Exception:
        await update.message.reply_text(
            "I’m having a small issue right now 😔 Please try again."
        )

# ================= RUN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("Miss Bloosm is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
