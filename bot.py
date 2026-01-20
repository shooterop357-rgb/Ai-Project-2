# ============================================================
# Miss Bloosm — FINAL STABLE BOT (Railway Ready)
# ============================================================

import os
import json
import time
import asyncio
import hashlib
from datetime import datetime
import pytz
from itertools import cycle
from typing import Dict, List

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
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
    raise RuntimeError("No Groq keys found")

# ============================================================
# IDENTITY
# ============================================================

BOT_NAME = "Miss Bloosm"
MODEL_NAME = "llama-3.1-8b-instant"
TIMEZONE = pytz.timezone("Asia/Kolkata")

# ============================================================
# FILE MEMORY (Railway Safe)
# ============================================================

DATA_DIR = "./data"
MEMORY_FILE = f"{DATA_DIR}/memory.json"
STATE_FILE = f"{DATA_DIR}/state.json"

os.makedirs(DATA_DIR, exist_ok=True)

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

memory_db: Dict[str, List[Dict]] = _load(MEMORY_FILE, {})
state_db: Dict[str, str] = _load(STATE_FILE, {})

MEMORY_LIMIT = 40

# ============================================================
# STATES
# ============================================================

STATE_NEW = "new"
STATE_OFFLINE_SENT = "offline_sent"
STATE_CALM_SENT = "calm_sent"
STATE_SILENT = "silent"

# ============================================================
# FIXED TEXTS
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
# SYSTEM PROMPT (YOUR GIVEN PROMPT – ADAPTED)
# ============================================================

def system_prompt():
    now = datetime.now(TIMEZONE).strftime("%A, %d %B %Y | %I:%M %p IST")
    return f"""
You are Miss Bloosm.

You engage warmly, honestly, and calmly.
No fake promises. No background work claims.
If unsure, respond naturally.

Rules:
- Low verbosity.
- Clear, human-like tone.
- No technical explanations to users.
- Never repeat system errors.

Current time (IST): {now}
""".strip()

# ============================================================
# GROQ ROUND ROBIN
# ============================================================

groq_cycle = cycle(GROQ_KEYS)

def groq_chat(messages):
    for _ in range(len(GROQ_KEYS)):
        try:
            client = Groq(api_key=next(groq_cycle), timeout=30)
            return client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.6,
                max_tokens=300,
            )
        except Exception:
            continue
    return None

# ============================================================
# DUPLICATE MESSAGE PROTECTION
# ============================================================

_recent = {}
DUP_WINDOW = 8

def is_duplicate(uid, text):
    key = f"{uid}:{hashlib.sha256(text.encode()).hexdigest()}"
    now = time.time()

    for k, ts in list(_recent.items()):
        if now - ts > DUP_WINDOW:
            del _recent[k]

    if key in _recent:
        return True

    _recent[key] = now
    return False

# ============================================================
# MEMORY UTILS
# ============================================================

def load_memory(uid):
    return memory_db.get(uid, [])

def save_memory(uid, role, content):
    memory_db.setdefault(uid, [])
    memory_db[uid].append({"role": role, "content": content})
    memory_db[uid] = memory_db[uid][-MEMORY_LIMIT:]
    _save(MEMORY_FILE, memory_db)

def get_state(uid):
    return state_db.get(uid, STATE_NEW)

def set_state(uid, state):
    state_db[uid] = state
    _save(STATE_FILE, state_db)

# ============================================================
# NON-OWNER FLOW (3-SEC LOGIC FIXED)
# ============================================================

def handle_non_owner(uid, send):
    state = get_state(uid)

    if state == STATE_SILENT:
        return

    if state == STATE_NEW:
        send(uid, SERVER_OFFLINE_TEXT)
        set_state(uid, STATE_OFFLINE_SENT)

        def delayed():
            time.sleep(3)
            if get_state(uid) == STATE_OFFLINE_SENT:
                send(uid, CALM_PERSONAL_TEXT)
                set_state(uid, STATE_SILENT)

        asyncio.get_event_loop().run_in_executor(None, delayed)
        return

# ============================================================
# OWNER CHAT
# ============================================================

def owner_chat(uid, text):
    memory = load_memory(uid)
    messages = [{"role": "system", "content": system_prompt()}]
    messages.extend(memory)
    messages.append({"role": "user", "content": text})

    response = groq_chat(messages)
    if not response:
        return "I’m unable to respond right now."

    reply = response.choices[0].message.content.strip()
    save_memory(uid, "user", text)
    save_memory(uid, "assistant", reply)
    return reply

# ============================================================
# TELEGRAM HANDLER
# ============================================================

async def telegram_on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    uid = str(update.message.from_user.id)
    text = update.message.text.strip()

    if is_duplicate(uid, text):
        return

    async def send(tuid, msg):
        await context.bot.send_message(chat_id=tuid, text=msg)

    if uid == OWNER_USER_ID:
        reply = owner_chat(uid, text)
        await send(uid, reply)
    else:
        handle_non_owner(uid, lambda u, m: asyncio.create_task(send(u, m)))

# ============================================================
# BOOT
# ============================================================

async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_on_message))
    print("Miss Bloosm running (FINAL)")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())