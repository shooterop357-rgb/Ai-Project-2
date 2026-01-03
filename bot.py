import os
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
    CommandHandler,
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")   # set env variable
OWNER_ID = 5436530930                # <-- YOUR TELEGRAM USER ID
TIMEZONE = pytz.timezone("Asia/Kolkata")

# ================= PERSONAL AI GUARD =================
async def personal_guard(update: Update):
    user = update.effective_user
    if user.id != OWNER_ID:
        await update.message.reply_text(
            "This AI is personal.\nAccess denied."
        )
        return False
    return True

# ================= TIME CHECK =================
def is_night():
    hour = datetime.now(TIMEZONE).hour
    return hour >= 22 or hour < 4

# ================= HONEST THINKING ENGINE =================
def honest_reply(text: str, night: bool):
    t = text.lower()

    # ---- Loneliness ----
    if "lonely" in t or "akela" in t:
        return (
            "Lonely feel hona galat nahi.\n"
            "Par yahin ruk jana bhi solution nahi.\n"
            "Tumhe aage chalna hi padega."
        )

    # ---- Love / GF thoughts ----
    if "gf" in t or "pyaar" in t or "love" in t:
        return (
            "Pyaar koi reward nahi hota.\n"
            "Wo tab aata hai jab tum apni life sambhalte ho.\n"
            "Isse chase mat karo."
        )

    # ---- Weak / failure ----
    if "weak" in t or "fail" in t:
        return (
            "Weak hona nahi.\n"
            "Ruk jana weak hona hota hai.\n"
            "Tum rukey nahi ho."
        )

    # ---- Overthinking ----
    if "overthink" in t or "soch" in t:
        return (
            "Dimaag ka kaam sochna hai.\n"
            "Tumhara kaam har soch pe bharosa karna nahi.\n"
            "Select karo."
        )

    # ---- Meaning of life ----
    if "meaning" in t or "zindagi" in t or "life" in t:
        return (
            "Zindagi ka meaning milta nahi.\n"
            "Zindagi ka meaning banaya jata hai.\n"
            "Roz ke actions se."
        )

    # ---- Default (night/day) ----
    if night:
        return (
            "Raat clarity laati hai,\n"
            "par decisions ke liye din hota hai.\n"
            "Abhi bas shaant raho."
        )
    else:
        return (
            "Tum theek direction me ho.\n"
            "Perfect hona zaroori nahi.\n"
            "Consistent rehna zaroori hai."
        )

# ================= MAIN REPLY HANDLER =================
async def blossom_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await personal_guard(update):
        return

    text = update.message.text
    reply = honest_reply(text, is_night())
    await update.message.reply_text(reply)

# ================= FINAL SHUTDOWN =================
async def shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await personal_guard(update):
        return

    await update.message.reply_text(
        "Yahin tak.\n"
        "Ab jo karna hai,\n"
        "tumhe khud karna hoga.\n\n"
        "— system shutting down"
    )

# ================= START =================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("end", shutdown))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, blossom_reply))

print("MISS BLOSSOM RUNNING | HONEST PERSONAL MODE")
app.run_polling()
