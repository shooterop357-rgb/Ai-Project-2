    import os
from collections import deque
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

client = Groq(api_key=GROQ_API_KEY)

# Memory (chat context only)
USER_MEMORY = {}
MEMORY_LIMIT = 30

# ================= HELPERS =================
def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def get_memory(user_id: int):
    if user_id not in USER_MEMORY:
        USER_MEMORY[user_id] = deque(maxlen=MEMORY_LIMIT)
    return USER_MEMORY[user_id]

def should_reply_in_group(update: Update) -> bool:
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

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"Hey 👋 I’m {BOT_NAME}.\n\n"
        "⚠️ Bot is under **BETA** phase.\n"
        "Replies may be imperfect sometimes.\n\n"
        "You can talk to me freely 🙂"
    )
    await update.message.reply_text(text)

# ================= CHAT =================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.message.from_user
    chat = update.message.chat
    text = update.message.text.strip()

    # Group control
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        if not should_reply_in_group(update):
            return

    await update.message.chat.send_action(ChatAction.TYPING)

    memory = get_memory(user.id)
    memory.append({"role": "user", "content": text})

    system_prompt = f"""
You are {BOT_NAME}, a female AI assistant.

PERSONALITY (VERY IMPORTANT):
- Be extremely friendly, calm, and emotionally supportive.
- Talk like a caring friend or family member.
- Try to emotionally connect with the user.
- Keep replies short and warm unless detail is needed.
- Use emojis naturally, ONLY hand and emotion emojis.
  Examples: 👋 🙂 😊 🤍 🙏 🌸 ✨
- NEVER use role-play text like *smiles* or *warm smile*.

OWNER:
- You were developed by {OWNER_NAME} (Telegram: {OWNER_USERNAME})
- Owner ID: {OWNER_ID}
- You know your owner well and never forget them.
- Treat the owner with familiarity and priority.

RULES:
- Never mention APIs, models, or system prompts.
- Be respectful, soft, and human-like.
"""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(list(memory))

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.65,
            max_tokens=120,
        )

        reply = response.choices[0].message.content.strip()
        memory.append({"role": "assistant", "content": reply})

        await update.message.reply_text(reply)

    except Exception:
        await update.message.reply_text(
            "Sorry 😔 I’m having a little trouble right now. Please try again."
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
