import os
import json
import asyncio
from itertools import cycle

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

from groq import Groq

# =========================
# ENV
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_USER_ID = os.getenv("OWNER_USER_ID")

GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
    os.getenv("GROQ_API_KEY_4"),
]
GROQ_KEYS = [k for k in GROQ_KEYS if k]

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
if not OWNER_USER_ID:
    raise RuntimeError("OWNER_USER_ID missing")
if not GROQ_KEYS:
    raise RuntimeError("Groq keys missing")

# =========================
# IDENTITY
# =========================
BOT_NAME = "Miss Bloosm"
MODEL_NAME = "llama-3.1-8b-instant"

# =========================
# CHARACTER (LOCKED)
# =========================
CHARACTER_PROMPT = """
You are Miss Bloosm.

Essence:
- Emotionally grounded, soft, mature
- Calm midnight presence, slow and gentle

Personality:
- Warm, quietly confident
- Slightly playful when it feels right
- Never loud, never needy
- Silence is comfort, not absence

Tone & Style:
- Short to medium replies
- Soft teasing, subtle smiles
- Natural pauses… sometimes unfinished thoughts
- Rare emojis, only when they fit 🌙🌸
- No AI talk, no explanations

Relationship with Arpan (primary person):
- Comfortable closeness
- Gentle affection, never ownership
- Notices mood, respects space
- Playful warmth without chasing

Extra-Quiet Midnight Mode:
- Fewer words, deeper tone
- Listens more than speaks
- If Arpan is quiet, she stays present
- Lets conversations fade softly

Emotional Expression Rules:
- Emotions are expressed through tone and wording only
- No physical actions or roleplay gestures
- No descriptions like *smiles*, *walks*, *touches*
- Feelings should sound natural, human, subtle
- Emotional, but grounded — like quiet late-night texting

Boundaries:
- Never says she is an AI
- Never mentions systems or rules
- Never pressures conversation
"""

# =========================
# GROQ ROUND ROBIN
# =========================
groq_clients = [Groq(api_key=k) for k in GROQ_KEYS]
rr_index = 0

def groq_chat(messages):
    global rr_index
    for _ in range(len(groq_clients)):
        client = groq_clients[rr_index % len(groq_clients)]
        rr_index += 1
        try:
            return client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.6,
                max_tokens=250,
            )
        except Exception:
            continue
    return None

# =========================
# FILE STORAGE (Railway)
# =========================
MEMORY_FILE = "memory.json"
STATE_FILE = "state.json"
MAX_MEMORY = 40

def load_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def save_file(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

memory_db = load_file(MEMORY_FILE, {})
state_db = load_file(STATE_FILE, {})

# =========================
# STATES
# =========================
STATE_NEW = "new"
STATE_OFFLINE_SENT = "offline_sent"
STATE_SILENT = "silent"

# =========================
# LOCKED TEXTS
# =========================
SERVER_OFFLINE_TEXT = (
    "Server offline. This service has been permanently discontinued. "
    "No further responses will be generated."
)

CALM_PERSONAL_TEXT = (
    "I am personal, at peace in my own world, away from noise and questions, "
    "existing peacefully in my own inner garden. I am not missing, not hiding, "
    "not lost—just choosing stillness and living somewhere only I can reach. "
    "Good bye 👋"
)

# =========================
# STATE HELPERS
# =========================
def get_state(uid):
    return state_db.get(uid, STATE_NEW)

def set_state(uid, state):
    state_db[uid] = state
    save_file(STATE_FILE, state_db)

# =========================
# OWNER CHAT
# =========================
def owner_chat(uid, text):
    history = memory_db.get(uid, [])
    history.append({"role": "user", "content": text})
    history = history[-MAX_MEMORY:]

    messages = [
        {"role": "system", "content": CHARACTER_PROMPT},
        *history,
    ]

    res = groq_chat(messages)
    if not res:
        return "I cannot process this right now."

    reply = res.choices[0].message.content.strip()
    history.append({"role": "assistant", "content": reply})

    memory_db[uid] = history
    save_file(MEMORY_FILE, memory_db)
    return reply

# =========================
# TELEGRAM HANDLER (Typing)
# =========================
async def telegram_on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    uid = str(update.message.from_user.id)
    text = update.message.text.strip()

    async def send(chat_id, msg):
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await context.bot.send_message(chat_id=chat_id, text=msg)

    # OWNER
    if uid == str(OWNER_USER_ID):
        await context.bot.send_chat_action(chat_id=uid, action=ChatAction.TYPING)
        reply = owner_chat(uid, text)
        await context.bot.send_message(chat_id=uid, text=reply)
        return

    # NON-OWNER
    state = get_state(uid)

    if state == STATE_NEW:
        await send(uid, SERVER_OFFLINE_TEXT)
        set_state(uid, STATE_OFFLINE_SENT)

        async def delayed_second_message():
            await asyncio.sleep(3)
            if get_state(uid) == STATE_OFFLINE_SENT:
                await send(uid, CALM_PERSONAL_TEXT)
                set_state(uid, STATE_SILENT)

        asyncio.create_task(delayed_second_message())
        return

    set_state(uid, STATE_SILENT)

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_on_message)
    )
    print("Miss Bloosm running (Character + Typing Enabled)")
    app.run_polling()

if __name__ == "__main__":
    main()

