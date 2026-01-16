import os
import json
from datetime import datetime
import pytz
import requests
import time

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

# =========================
# ENV VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
HOLIDAY_API_KEY = os.getenv("HOLIDAY_API_KEY")

GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
    os.getenv("GROQ_API_KEY_4"),
]

if not BOT_TOKEN or not all(GROQ_KEYS):
    raise RuntimeError("Missing ENV variables")

# =========================
# CORE IDENTITY
# =========================
BOT_NAME = "Miss Bloosm"
DEVELOPER = "@Frx_Shooter"
OWNER_ID = 5436530930
TIMEZONE = pytz.timezone("Asia/Kolkata")

# =========================
# OWNER MEMORY FILES
# =========================
PERSONALITY_FILE = "personality.json"
LEARNING_FILE = "learning_versions.json"

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

# =========================
# GROQ ROUND ROBIN
# =========================
groq_clients = [Groq(api_key=k) for k in GROQ_KEYS]
current_idx = 0

def groq_chat(messages):
    global current_idx
    for _ in range(len(groq_clients)):
        client = groq_clients[current_idx % len(groq_clients)]
        current_idx += 1
        try:
            return client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.6,
                max_tokens=180,
            )
        except Exception:
            continue
    return None

# =========================
# MEMORY FILE
# =========================
MEMORY_FILE = "memory.json"

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_memory(data):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

# =========================
# SMART MEMORY CONFIG (NEW)
# =========================
MAX_MEMORY = 30

CLOSURE_PHRASES = [
    "kuch nahi", "nothing", "no", "bas", "filhaal to nahi"
]

CASUAL_PHRASES = [
    "hi", "hello", "hey", "ok", "okay", "hmm", "hm", "👍"
]

SLEEP_KEYWORDS = [
    "sleep", "so jao", "good night", "gn", "neend"
]

def detect_topic(text: str) -> str:
    t = text.lower()
    if any(k in t for k in SLEEP_KEYWORDS):
        return "sleep"
    if any(k in t for k in ["why", "what", "how", "explain"]):
        return "question"
    return "general"

def is_important_line(text: str) -> bool:
    t = text.lower()
    if t in CASUAL_PHRASES:
        return False
    if any(p in t for p in CLOSURE_PHRASES):
        return False
    return True

# =========================
# TIME CONTEXT
# =========================
def ist_context():
    return datetime.now(TIMEZONE).strftime("%A, %d %B %Y | %I:%M %p IST")

# =========================
# HOLIDAYS (CACHED)
# =========================
_holiday_cache = {"date": None, "data": None}

def get_indian_holidays():
    if not HOLIDAY_API_KEY:
        return None

    today = datetime.now(TIMEZONE).date()
    if _holiday_cache["date"] == today:
        return _holiday_cache["data"]

    try:
        year = today.year
        url = f"https://api.api-ninjas.com/v1/holidays?country=IN&year={year}"
        headers = {"X-Api-Key": HOLIDAY_API_KEY}
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()

        upcoming = []
        for item in data:
            d = datetime.strptime(item["date"], "%Y-%m-%d").date()
            if d >= today:
                upcoming.append(f"{item['name']} ({d.strftime('%d %b')})")

        result = ", ".join(upcoming[:5]) if upcoming else None
        _holiday_cache["date"] = today
        _holiday_cache["data"] = result
        return result
    except Exception:
        return None

# =========================
# SHORT REPLY MAP
# =========================
LOW_EFFORT = {
    "ok": "Okay.",
    "okay": "Alright.",
    "hmm": "Hmm.",
    "hm": "Hmm.",
    "nothing": "Got it.",
    "sure": "Great.",
    "fine": "Alright.",
    "👍": "👍"
}

# =========================
# /START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Hello, I’m {BOT_NAME}.\n\n"
        "I’m designed for calm, friendly, professional conversations.\n"
        "Talk anytime freely 🙂"
    )

# =========================
# CHAT
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    text_l = text.lower()
    uid = str(update.effective_user.id)
    chat_type = update.effective_chat.type

    # Group filter
    if chat_type in ["group", "supergroup"]:
        if (
            f"@{context.bot.username}" not in text
            and not update.message.reply_to_message
            and not text.startswith("/")
        ):
            return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    # =========================
    # OWNER CONTROLS (UNCHANGED)
    # =========================
    if update.effective_user.id == OWNER_ID:
        if text_l.startswith("personality:"):
            save_json(PERSONALITY_FILE, {"current": text.split(":", 1)[1].strip()})
            await update.message.reply_text("Personality updated.")
            return

        if text_l.startswith("learn:"):
            data = load_json(LEARNING_FILE, {"versions": []})
            data["versions"].append({
                "time": ist_context(),
                "content": text.split(":", 1)[1].strip()
            })
            save_json(LEARNING_FILE, data)
            await update.message.reply_text("Learned.")
            return

        if text_l == "rollback":
            data = load_json(LEARNING_FILE, {"versions": []})
            if data["versions"]:
                data["versions"].pop()
                save_json(LEARNING_FILE, data)
            await update.message.reply_text("Rolled back.")
            return

        if text_l == "list learnings":
            data = load_json(LEARNING_FILE, {"versions": []})
            if not data["versions"]:
                await update.message.reply_text("No learnings yet.")
                return
            await update.message.reply_text(
                "Learnings:\n" + "\n".join(
                    f"{i}. {v['content']}"
                    for i, v in enumerate(data["versions"], 1)
                )
            )
            return

        if text_l.startswith("remove learning:"):
            target = text.split(":", 1)[1].strip().lower()
            data = load_json(LEARNING_FILE, {"versions": []})
            data["versions"] = [
                v for v in data["versions"]
                if v["content"].lower() != target
            ]
            save_json(LEARNING_FILE, data)
            await update.message.reply_text("Learning removed.")
            return

    # Low effort
    if text_l in LOW_EFFORT:
        await update.message.reply_text(LOW_EFFORT[text_l])
        return

    # =========================
    # SMART MEMORY LOGIC
    # =========================
    memory = load_memory()
    memory.setdefault(uid, [])

    # HARD CLOSURE (DM)
    if chat_type == "private" and any(p in text_l for p in CLOSURE_PHRASES):
        memory[uid] = []
        save_memory(memory)
        await update.message.reply_text("Theek hai.")
        return

    current_topic = detect_topic(text)
    last_topic = context.user_data.get("topic")

    if last_topic and last_topic != current_topic:
        memory[uid] = memory[uid][-5:]

    context.user_data["topic"] = current_topic

    if is_important_line(text):
        memory[uid].append({"role": "user", "content": text})

    if current_topic == "sleep":
        memory[uid] = memory[uid][-3:]

    memory[uid] = memory[uid][-MAX_MEMORY:]
    save_memory(memory)

    # =========================
    # SYSTEM PROMPT (UNCHANGED)
    # =========================
    system_prompt = (
        f"You are {BOT_NAME}, a female AI assistant.\n"
        f"Developer: {DEVELOPER}.\n\n"
        "Calm, professional, short replies.\n"
        f"Current time (IST): {ist_context()}\n"
    )

    personality = load_json(PERSONALITY_FILE, {}).get("current")
    if personality:
        system_prompt += f"\nPersonality:\n- {personality}\n"

    learned = load_json(LEARNING_FILE, {}).get("versions", [])
    if learned:
        system_prompt += "\nLearned behavior:\n"
        for v in learned[-5:]:
            system_prompt += f"- {v['content']}\n"

    holidays_context = get_indian_holidays()
    if holidays_context:
        system_prompt += f"Upcoming Indian holidays: {holidays_context}\n"

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(memory[uid])

    response = groq_chat(messages)
    if not response:
        await update.message.reply_text("Message thoda lamba ho gaya. Short me bhejo.")
        return

    reply = response.choices[0].message.content.strip()

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
    print("Miss Bloosm is running")
    app.run_polling()

if __name__ == "__main__":
    main()
