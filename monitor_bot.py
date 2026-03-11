"""
URL Monitor Telegram Bot
========================
Commands:
  /monitor  — start monitoring a URL (bot will ask for URL and condition)
  /stop     — stop active monitoring
  /status   — show what's being monitored

Setup:
  pip install "python-telegram-bot[job-queue]" requests
  Set BOT_TOKEN below, then run: python monitor_bot.py

To get a bot token: open Telegram -> @BotFather -> /newbot
To get your chat_id: start the bot, send any message, then open:
  https://api.telegram.org/bot<TOKEN>/getUpdates  and read "chat" -> "id"
"""

import logging
import re
import requests as http_requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "placeholder"  # e.g. "7123456789:AAFxxx..."

POLL_INTERVAL_SECONDS = 60

# Conversation states
ASK_URL, ASK_CONDITION = range(2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_condition(text: str):
    """
    Accepts:
      "not 422"  -> ("not", 422)  – notify when status is NOT 422
      "422"      -> ("is",  422)  – notify when status IS 422
    Returns (operator, code) or None if unparseable.
    """
    text = text.strip().lower()
    m = re.match(r"^not\s+(\d{3})$", text)
    if m:
        return ("not", int(m.group(1)))
    m = re.match(r"^(\d{3})$", text)
    if m:
        return ("is", int(m.group(1)))
    return None


def condition_label(operator: str, code: int) -> str:
    return f"NOT {code}" if operator == "not" else str(code)


# ---------------------------------------------------------------------------
# Background job
# ---------------------------------------------------------------------------

async def monitor_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    url = job.data["url"]
    operator, code = job.data["condition"]

    try:
        response = http_requests.get(url, timeout=15)
        status = response.status_code
        logger.info(f"[{chat_id}] {url} -> {status}")

        triggered = (operator == "not" and status != code) or (
            operator == "is" and status == code
        )

        if triggered:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"\u2705 Condition met!\n\n"
                    f"\U0001f517 URL: {url}\n"
                    f"\U0001f4cb Status: {status} (expected {condition_label(operator, code)})\n\n"
                    f"Monitoring stopped. Use /monitor to watch again."
                ),
            )
            job.schedule_removal()

    except Exception as e:
        logger.error(f"[{chat_id}] Error checking {url}: {e}")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "\U0001f916 URL Monitor Bot\n\n"
        "/monitor \u2014 start monitoring a URL\n"
        "/stop    \u2014 stop monitoring\n"
        "/status  \u2014 show current monitored URL"
    )


async def monitor_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me the URL to monitor:")
    return ASK_URL


async def got_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith(("http://", "https://")):
        await update.message.reply_text(
            "That doesn't look like a valid URL. Please send one starting with http:// or https://"
        )
        return ASK_URL

    context.user_data["url"] = url
    await update.message.reply_text(
        "Got it! Now tell me the condition that should trigger a notification.\n\n"
        "Examples:\n"
        "\u2022 `not 422` \u2014 notify when status is NOT 422\n"
        "\u2022 `200`     \u2014 notify when status IS 200\n"
        "\u2022 `not 503` \u2014 notify when status is NOT 503",
        parse_mode="Markdown",
    )
    return ASK_CONDITION


async def got_condition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    condition = parse_condition(update.message.text)
    if condition is None:
        await update.message.reply_text(
            "Couldn't parse that. Use a format like `not 422` or `200`.",
            parse_mode="Markdown",
        )
        return ASK_CONDITION

    url = context.user_data["url"]
    operator, code = condition

    # Cancel any existing job for this chat
    for job in context.job_queue.get_jobs_by_name(str(update.effective_chat.id)):
        job.schedule_removal()

    context.job_queue.run_repeating(
        monitor_job,
        interval=POLL_INTERVAL_SECONDS,
        first=0,
        chat_id=update.effective_chat.id,
        name=str(update.effective_chat.id),
        data={"url": url, "condition": condition},
    )

    await update.message.reply_text(
        f"\u2705 Monitoring started!\n\n"
        f"\U0001f517 URL: {url}\n"
        f"\U0001f4cb Notify when status: {condition_label(operator, code)}\n"
        f"\u23f1 Checking every {POLL_INTERVAL_SECONDS}s\n\n"
        f"I'll message you when the condition is met. Use /stop to cancel."
    )
    return ConversationHandler.END


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name(str(update.effective_chat.id))
    if jobs:
        for job in jobs:
            job.schedule_removal()
        await update.message.reply_text("\U0001f6d1 Monitoring stopped.")
    else:
        await update.message.reply_text("No active monitoring to stop.")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name(str(update.effective_chat.id))
    if jobs:
        data = jobs[0].data
        operator, code = data["condition"]
        await update.message.reply_text(
            f"\U0001f441 Currently monitoring:\n\n"
            f"\U0001f517 {data['url']}\n"
            f"\U0001f4cb Notify when status: {condition_label(operator, code)}\n"
            f"\u23f1 Every {POLL_INTERVAL_SECONDS}s"
        )
    else:
        await update.message.reply_text("No active monitoring. Use /monitor to start.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if not BOT_TOKEN:
        raise ValueError("Set BOT_TOKEN at the top of monitor_bot.py before running.")

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("monitor", monitor_cmd)],
        states={
            ASK_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_url)],
            ASK_CONDITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_condition)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("status", status_cmd))

    print("Bot is running... Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
