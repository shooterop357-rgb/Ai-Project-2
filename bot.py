import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from groq import Groq

# ===== ENV VARIABLES =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

BOT_NAME = "Miss Bloosm"
OWNER_NAME = "@Frx_Shooter"

client = Groq(api_key=GROQ_API_KEY)

# ===== START COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Hey 👋\n"
        f"My name is {BOT_NAME}.\n"
        f"I’m an AI-based chat bot designed to talk like a human.\n\n"
        f"You can chat with me freely — ask questions, share thoughts, or just talk.\n"
        f"Type anything to start 🙂"
    )

# ===== IDENTITY QUESTIONS =====
def is_identity_question(text: str) -> bool:
    keywords = [
        "who developed you", "who designed you", "who made you",
        "who is your owner", "developer", "owner",
        "tumhe kisne banaya", "developer kon", "owner kon",
        "your name", "what is your name", "tumhara naam",
        "tumhara name", "your number", "tumhara number"
    ]
    text = text.lower()
    return any(k in text for k in keywords)

# ===== MAIN CHAT HANDLER =====
async def reply_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()

    # HARD OVERRIDE (NO AI)
    if is_identity_question(user_text):
        await update.message.reply_text(
            f"My name is {BOT_NAME}.\n"
            f"I was developed and designed by {OWNER_NAME}."
        )
        return

    # AI RESPONSE
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are an AI chat bot.\n"
                        f"Your name is {BOT_NAME}.\n"
                        f"You were developed and designed by {OWNER_NAME}.\n"
                        f"If asked about your name or creator, always answer correctly."
                    )
                },
                {"role": "user", "content": user_text}
            ],
            temperature=0.7,
            max_tokens=150
        )

        await update.message.reply_text(response.choices[0].message.content)

    except Exception:
        await update.message.reply_text("Sorry, something went wrong. Please try again.")

# ===== RUN =====
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_ai))

    print("Miss Bloosm is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
