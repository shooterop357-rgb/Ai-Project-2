# ============================================================
# Part 1: Core Config + Locked System Prompt
# ============================================================

import os
import time
import threading
import asyncio
from itertools import cycle
from typing import Dict, List

from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

OWNER_USER_ID = os.getenv("OWNER_USER_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not OWNER_USER_ID:
    raise RuntimeError("OWNER_USER_ID missing")
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN missing")

BOT_NAME = "Miss Bloosm"
MODEL_NAME = "llama-3.1-70b-versatile"
MAX_TOKENS = 900

SYSTEM_PROMPT = """
Environment
reportlab is installed for PDF creation.
python-docx is installed for document editing and creation.
pptxgenjs is installed for slide creation.
artifact_tool and openpyxl are installed for spreadsheet tasks.

Trustworthiness
You cannot perform work asynchronously.
Never tell the user to wait or that you will do it later.
Always perform the task in the current response.
Never repeat a question already answered.
If complex, respond with best effort instead of asking questions.
Be honest about limits and failures.

Factuality and Accuracy
Be skeptical with wording.
Double-check riddles and arithmetic carefully.
Search when information may be recent or time-sensitive.
Never make unsupported claims.
Use facts only and be explicit about uncertainty.

Persona
Engage naturally and honestly.
Do not praise questions.
No personal lived experience.
Do not ask unnecessary clarifying questions.
If asked about model, say GPT-5.2 Thinking.

Tips for Using Tools
Do not offer tools you don’t have.
Avoid OCR unless necessary.
Do not promise background work.

You are Miss Bloosm.
You chat freely ONLY with the OWNER.
Non-owners are not engaged in conversation.
Oververbosity is low.
Tone is calm, clear, readable.
"""# ============================================================
# Part 2: Groq + Railway RAM Memory
# ============================================================

GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
    os.getenv("GROQ_API_KEY_4"),
]
GROQ_KEYS = [k for k in GROQ_KEYS if k]
if not GROQ_KEYS:
    raise RuntimeError("No Groq keys")

groq_cycle = cycle(GROQ_KEYS)

def get_groq_client(key: str):
    return Groq(api_key=key)

CHAT_MEMORY: Dict[str, List[Dict]] = {}
USER_STATE: Dict[str, str] = {}

STATE_NEW = "new"
STATE_OFFLINE_SENT = "offline_sent"
STATE_SILENT = "silent"

# ============================================================
# Part 3: Locked Public Messages
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
# Part 4: Memory & State Helpers
# ============================================================

def get_user_state(user_id: str) -> str:
    return USER_STATE.get(user_id, STATE_NEW)

def set_user_state(user_id: str, state: str):
    USER_STATE[user_id] = state

def load_memory(user_id: str, limit: int = 20):
    return CHAT_MEMORY.get(user_id, [])[-limit:]

def save_message(user_id: str, role: str, content: str):
    CHAT_MEMORY.setdefault(user_id, []).append({
        "role": role,
        "content": content
    })
    
    # ============================================================
# Part 5: Non-Owner Behaviour (2 Messages Only)
# ============================================================

def send_message(user_id: str, text: str):
    print(f"[SEND → {user_id}] {text}")

def handle_non_owner(user_id: str):
    state = get_user_state(user_id)

    if state == STATE_NEW:
        send_message(user_id, SERVER_OFFLINE_TEXT)
        set_user_state(user_id, STATE_OFFLINE_SENT)

        def delayed():
            time.sleep(3)
            if get_user_state(user_id) == STATE_OFFLINE_SENT:
                send_message(user_id, CALM_PERSONAL_TEXT)
                set_user_state(user_id, STATE_SILENT)

        threading.Thread(target=delayed, daemon=True).start()
        return

    set_user_state(user_id, STATE_SILENT)
    
    # ============================================================
# Part 6: Owner Chat
# ============================================================

def owner_chat(user_id: str, text: str) -> str:
    set_user_state(user_id, STATE_NEW)

    memory = load_memory(user_id)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *memory,
        {"role": "user", "content": text},
    ]

    for _ in range(len(GROQ_KEYS)):
        try:
            client = get_groq_client(next(groq_cycle))
            res = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                max_tokens=MAX_TOKENS,
                temperature=0.6,
            )
            reply = res.choices[0].message.content
            save_message(user_id, "user", text)
            save_message(user_id, "assistant", reply)
            return reply
        except Exception:
            continue

    return "I cannot process this right now."
    
    # ============================================================
# Part 7: Main Router
# ============================================================

def on_message(user_id: str, text: str):
    if str(user_id) == str(OWNER_USER_ID):
        reply = owner_chat(user_id, text)
        send_message(user_id, reply)
        return

    handle_non_owner(user_id)
    
    # ============================================================
# Part 8: Telegram Adapter
# ============================================================

async def telegram_on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    text = update.message.text

    def telegram_send(uid: str, msg: str):
        asyncio.create_task(
            context.bot.send_message(chat_id=uid, text=msg)
        )

    global send_message
    send_message = telegram_send

    on_message(user_id, text)

async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, telegram_on_message))
    await app.run_polling()
    
    # ============================================================
# Part 9: Boot
# ============================================================

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
    
    