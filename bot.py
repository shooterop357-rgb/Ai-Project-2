# ============================================================
# Miss Bloosm — Core Foundation
# Part 1: Config, Prompt Lock, Identity, Global State
# ============================================================

import os
import time
import threading
from itertools import cycle
from typing import Dict, List, Optional

from groq import Groq
from pymongo import MongoClient
from dotenv import load_dotenv

# ------------------------------------------------------------
# ENV LOAD
# ------------------------------------------------------------
load_dotenv()

# ------------------------------------------------------------
# IDENTITY
# ------------------------------------------------------------
BOT_NAME = "Miss Bloosm"
MODEL_NAME = "llama-3.1-70b-versatile"

# ------------------------------------------------------------
# OWNER CONFIG (CRITICAL)
# ------------------------------------------------------------
OWNER_USER_ID = os.getenv("OWNER_USER_ID")
if not OWNER_USER_ID:
    raise RuntimeError("OWNER_USER_ID missing")

# 🔧 FIX: normalize OWNER ID once
OWNER_USER_ID = str(OWNER_USER_ID)

# ------------------------------------------------------------
# GROQ ROUND ROBIN (4 KEYS)
# ------------------------------------------------------------
GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
    os.getenv("GROQ_API_KEY_4"),
]
GROQ_KEYS = [k for k in GROQ_KEYS if k]

if not GROQ_KEYS:
    raise RuntimeError("No Groq API keys found")

groq_cycle = cycle(GROQ_KEYS)

MAX_TOKENS = 900
REQUEST_TIMEOUT = 30

# ------------------------------------------------------------
# MONGODB (CHAT ONLY)
# ------------------------------------------------------------
MONGO_URI = os.getenv("MONGODB_URI")
mongo_client = MongoClient(MONGO_URI) if MONGO_URI else None

db = mongo_client["miss_bloosm"] if mongo_client else None
chat_col = db["chat_history"] if db else None
state_col = db["user_state"] if db else None

# ------------------------------------------------------------
# PUBLIC LOCKED MESSAGES (FROM YOUR PROMPT)
# ------------------------------------------------------------
SERVER_OFFLINE_TEXT = (
    "Server offline. This service has been permanently discontinued. "
    "No further responses will be generated."
)

CALM_PERSONAL_TEXT = (
    "I am personal, at peace in my own world, away from noise and questions, "
    "existing peacefully in my own inner garden. I am not missing, not hiding, "
    "not lost—just choosing stillness and living somewhere only I can reach."
)

# ------------------------------------------------------------
# USER STATE ENUM
# ------------------------------------------------------------
STATE_NEW = "new"
STATE_OFFLINE_SENT = "offline_sent"
STATE_CALM_SENT = "calm_sent"
STATE_SILENT = "silent"

# ------------------------------------------------------------
# SYSTEM PROMPT (LOCKED)
# ------------------------------------------------------------
SYSTEM_PROMPT = """
You are Miss Bloosm.

You are a chat-only AI.
You engage naturally, honestly, and calmly.

Rules:
- You chat freely with the OWNER.
- If a task is not possible, skip it and inform the OWNER only.
- Never promise background or future work.
- Never fake capability.
- Do not praise questions.
- Oververbosity level is low (2).
- Writing is clear, calm, readable.

You do NOT interact normally with non-owners.
"""

# ------------------------------------------------------------
# UTIL: GROQ CLIENT
# ------------------------------------------------------------
def get_groq_client(api_key: str) -> Groq:
    return Groq(api_key=api_key, timeout=REQUEST_TIMEOUT)

# ------------------------------------------------------------
# UTIL: USER STATE
# ------------------------------------------------------------
def get_user_state(user_id: str) -> str:
    if not state_col:
        return STATE_NEW
    # 🔧 FIX: always use string user_id
    doc = state_col.find_one({"user_id": str(user_id)})
    return doc["state"] if doc else STATE_NEW

def set_user_state(user_id: str, state: str):
    if not state_col:
        return
    # 🔧 FIX: always store string user_id
    state_col.update_one(
        {"user_id": str(user_id)},
        {"$set": {"state": state}},
        upsert=True
    )

# ------------------------------------------------------------
# UTIL: CHAT MEMORY
# ------------------------------------------------------------
def load_memory(user_id: str, limit: int = 20) -> List[Dict]:
    if not chat_col:
        return []
    docs = (
        chat_col.find({"user_id": str(user_id)})
        .sort("ts", -1)
        .limit(limit)
    )
    return [{"role": d["role"], "content": d["content"]} for d in reversed(list(docs))]

def save_message(user_id: str, role: str, content: str):
    if not chat_col:
        return
    chat_col.insert_one({
        "user_id": str(user_id),  # 🔧 FIX
        "role": role,
        "content": content,
        "ts": time.time()
    })

# ============================================================
# END OF PART 1
# ============================================================

# ============================================================
# Miss Bloosm — Core Brain
# Part 2: Message Routing & Behaviour Enforcement (FIXED)
# ============================================================

import threading
import time

# ------------------------------------------------------------
# INTERNAL: SEND MESSAGE HOOK
# ------------------------------------------------------------
def send_message(user_id: str, text: str):
    print(f"[SEND -> {user_id}] {text}")

# ------------------------------------------------------------
# NON-OWNER FLOW HANDLER (EXACT 2 MESSAGES)
# ------------------------------------------------------------
def handle_non_owner(user_id: str):
    """
    Non-owner:
    1. Instant server-offline
    2. 3 sec baad calm message
    3. Phir silence forever
    """

    state = get_user_state(user_id)

    # FIRST CONTACT
    if state == STATE_NEW:
        send_message(user_id, SERVER_OFFLINE_TEXT)
        set_user_state(user_id, STATE_OFFLINE_SENT)

        def delayed_calm():
            time.sleep(3)
            # 🔒 double-message guard
            if get_user_state(user_id) == STATE_OFFLINE_SENT:
                send_message(user_id, CALM_PERSONAL_TEXT)
                set_user_state(user_id, STATE_SILENT)

        threading.Thread(target=delayed_calm, daemon=True).start()
        return

    # AFTER 2 MESSAGES → SILENCE
    set_user_state(user_id, STATE_SILENT)

# ------------------------------------------------------------
# OWNER CHAT FLOW (DB SAFE)
# ------------------------------------------------------------
def owner_chat(user_id: str, user_text: str) -> str:
    """
    Owner ke liye full AI chat.
    Old DB state ignored.
    """
    # 🔧 FIX: owner never stuck
    set_user_state(user_id, STATE_NEW)

    memory = load_memory(user_id)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *memory,
        {"role": "user", "content": user_text},
    ]

    reply = None

    for _ in range(len(GROQ_KEYS)):
        api_key = next(groq_cycle)
        try:
            client = get_groq_client(api_key)
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                max_tokens=MAX_TOKENS,
                temperature=0.6,
            )
            reply = response.choices[0].message.content
            break
        except Exception:
            continue

    if reply is None:
        reply = "I cannot process this right now."

    save_message(user_id, "user", user_text)
    save_message(user_id, "assistant", reply)
    return reply

# ------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------
def on_message(user_id: str, text: str):
    # OWNER
    if str(user_id) == str(OWNER_USER_ID):
        reply = owner_chat(user_id, text)
        send_message(user_id, reply)
        return

    # NON-OWNER
    handle_non_owner(user_id)

# ============================================================
# END OF PART 2
# ============================================================

# ============================================================
# # ============================================================
# Miss Bloosm — Integration Layer
# Part 3: Telegram Bot Adapter (SINGLE FILE FIX)
# ============================================================

import os
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

# ------------------------------------------------------------
# ENV
# ------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN missing")

# ------------------------------------------------------------
# TELEGRAM MESSAGE HANDLER
# ------------------------------------------------------------
async def telegram_on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    text = update.message.text

    # Patch send_message locally (GLOBAL function)
    def telegram_send_message(uid: str, msg: str):
        asyncio.create_task(
            context.bot.send_message(chat_id=uid, text=msg)
        )

    global send_message
    send_message = telegram_send_message

    # 🔑 SINGLE ENTRY
    on_message(user_id, text)

# ------------------------------------------------------------
# APP START
# ------------------------------------------------------------
async def main():
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_on_message)
    )

    print("Miss Bloosm Telegram bot is running.")
    await application.run_polling()

# ------------------------------------------------------------
# BOOT (Railway-safe)
# ------------------------------------------------------------
if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())

# ============================================================
# Miss Bloosm — Hardening Layer
# Part 4: Safety, Restart Protection, Memory Control (FIXED)
# ============================================================

import hashlib

# ------------------------------------------------------------
# DUPLICATE MESSAGE PROTECTION (OWNER ONLY)
# ------------------------------------------------------------
RECENT_MSG_WINDOW_SEC = 10
_recent_messages = {}

def is_duplicate(user_id: str, text: str) -> bool:
    key = f"{user_id}:{hashlib.sha256(text.encode()).hexdigest()}"
    now = time.time()

    # cleanup
    for k, ts in list(_recent_messages.items()):
        if now - ts > RECENT_MSG_WINDOW_SEC:
            del _recent_messages[k]

    if key in _recent_messages:
        return True

    _recent_messages[key] = now
    return False

# ------------------------------------------------------------
# SAFE OWNER WRAPPER (NO LOGIC CHANGE)
# ------------------------------------------------------------
def safe_owner_chat(user_id: str, text: str):
    if is_duplicate(user_id, text):
        return

    reply = owner_chat(user_id, text)
    send_message(user_id, reply)
    
    # ============================================================
# Miss Bloosm — Web Adapter
# Part 5: FastAPI HTTP Interface (FIXED)
# ============================================================

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Miss Bloosm")

class ChatIn(BaseModel):
    user_id: str
    message: str

class ChatOut(BaseModel):
    response: str | None

@app.post("/chat", response_model=ChatOut)
def chat_api(data: ChatIn):
    responses = []

    def web_send_message(uid: str, msg: str):
        responses.append(msg)

    # Patch send_message only
    global send_message
    send_message = web_send_message

    # 🔑 SINGLE ENTRY (same as Telegram)
    on_message(data.user_id, data.message)

    if responses:
        return ChatOut(response=responses[-1])
    return ChatOut(response=None)
    
    # ============================================================
# Miss Bloosm — Owner Notification
# Part 6: Fail Awareness (Owner Only) (FIXED)
# ============================================================

def notify_owner(text: str):
    """
    ONLY owner is informed.
    Public never sees failures.
    """
    send_message(OWNER_USER_ID, f"[Notice] {text}")
    
    # ============================================================
# Miss Bloosm — Boot Integrity
# Part 8: Startup Validation
# ============================================================

def integrity_check():
    if not OWNER_USER_ID:
        raise RuntimeError("Owner missing")
    if not GROQ_KEYS:
        raise RuntimeError("Groq keys missing")
    if not mongo_client:
        print("Warning: MongoDB disabled (memory off)")

integrity_check()

# ============================================================
# Miss Bloosm — Final Export
# Part 9: Unified Entry (USE THIS EVERYWHERE)
# ============================================================

def handle_input(user_id: str, text: str):
    """
    Universal entry for ALL platforms (Telegram / Web / CLI)
    """
    on_message(user_id, text)