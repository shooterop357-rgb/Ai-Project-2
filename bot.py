import os
import json
import time
import threading
from itertools import cycle
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

from groq import Groq

# ============================================================
# ENV
# ============================================================

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

# ============================================================
# IDENTITY
# ============================================================

BOT_NAME = "Miss Bloosm"
MODEL_NAME = "llama-3.1-8b-instant"
MAX_TOKENS = 220

# ============================================================
# GROQ ROUND ROBIN
# ============================================================

groq_cycle = cycle(GROQ_KEYS)

def groq_chat(messages):
    for _ in range(len(GROQ_KEYS)):
        try:
            client = Groq(api_key=next(groq_cycle))
            return client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.6,
                max_tokens=MAX_TOKENS,
            )
        except Exception:
            continue
    return None

# ============================================================
# FILE MEMORY (Railway safe)
# ============================================================

MEMORY_FILE = "memory.json"
STATE_FILE = "state.json"
MAX_MEMORY = 40

def _load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def _save(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

memory_db = _load(MEMORY_FILE, {})
state_db = _load(STATE_FILE, {})

# ============================================================
# STATES
# ============================================================

STATE_NEW = "new"
STATE_OFFLINE_SENT = "offline_sent"
STATE_SILENT = "silent"

# ============================================================
# LOCKED MESSAGES
# ============================================================

SERVER_OFFLINE_TEXT = (
    "Server offline. This service has been permanently discontinued. "
    "No further responses will be generated."
)

CALM_PERSONAL_TEXT = (
    "I am personal, at peace in my own world, away from noise and questions, "
    "existing peacefully in my own inner garden. I am not missing, not hiding, "
    "not lost—just choosing stillness and living somewhere only I can reach."
)

# ============================================================
# UTIL
# ============================================================

def get_state(uid):
    return state_db.get(uid, STATE_NEW)

def set_state(uid, state):
    state_db[uid] = state
    _save(STATE_FILE, state_db)

def now_utc():
    return datetime.now(timezone.utc).isoformat()

# ============================================================
# OWNER CHAT
# ============================================================

def owner_chat(uid, text):
    history = memory_db.get(uid, [])
    history.append({"role": "user", "content": text})
    history = history[-MAX_MEMORY:]

    messages = [
        {"role": "system", "content": "You are Miss Bloosm. Calm. Honest. Clear."},
        *history,
    ]

    response = groq_chat(messages)
    if not response:
        return "I cannot process this right now."

    reply = response.choices[0].message.content.strip()
    history.append({"role": "assistant", "content": reply})

    memory_db[uid] = history
    _save(MEMORY_FILE, memory_db)
    return reply

# ============================================================
# NON-OWNER FLOW (LOCKED)
# ============================================================

def handle_non_owner(uid, send):
    state = get_state(uid)

    if state == STATE_NEW:
        send(uid, SERVER_OFFLINE_TEXT)
        set_state(uid, STATE_OFFLINE_SENT)

        def delayed():
            time.sleep(3)
            if get_state(uid) == STATE_OFFLINE_SENT:
                send(uid, CALM_PERSONAL_TEXT)
                set_state(uid, STATE_SILENT)

        threading.Thread(target=delayed, daemon=True).start()
        return

    # absolute silence
    set_state(uid, STATE_SILENT)

# ============================================================
# TELEGRAM HANDLER
# ============================================================

async def telegram_on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    uid = str(update.message.from_user.id)
    text = update.message.text.strip()

    async def tg_send(u, m):
        await context.bot.send_message(chat_id=u, text=m)

    # OWNER
    if uid == str(OWNER_USER_ID):
        reply = owner_chat(uid, text)
        await tg_send(uid, reply)
        return

    # NON-OWNER
    handle_non_owner(uid, lambda u, m: context.application.create_task(
        tg_send(u, m)
    ))

# ============================================================
# MAIN
# ============================================================

async def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_on_message)
    )

    print("Miss Bloosm running")
    await app.run_polling()

# ============================================================
# BOOT (Railway SAFE)
# ============================================================

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())