import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI

"""
OPENAI GROQ-STYLE BOT

Behavior:
- AI reply aaye → bot bole
- AI fail ho → bot silent
- No fallback
- No retry
- Pure AI output only
"""

# =========================
# ENV VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Missing BOT_TOKEN or OPENAI_API_KEY")

# =========================
# OPENAI CLIENT
# =========================
client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# /START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello, I’m an AI.\nTalk to me naturally."
    )

# =========================
# CHAT (GROQ-STYLE)
# =========================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=user_text,
        )

        reply = response.output_text.strip()

        if reply:
            await update.message.reply_text(reply)

    except Exception:
        # OpenAI fail → bot silent (same as Groq old method)
        return

# =========================
# RUN BOT
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("OpenAI Groq-style bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
