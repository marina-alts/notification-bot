import logging

import requests as http_requests
from bot.monitor_helpers import (
    condition_label,
    interval_label,
    parse_condition,
    parse_interval,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from bot.config import (
    ASK_URL,
    ASK_CONDITION,
    ASK_INTERVAL,
    DEFAULT_POLL_INTERVAL_SECONDS,
)

logger = logging.getLogger(__name__)

# Pre-built inline keyboards
CONDITION_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("= 200",  callback_data="cond:is:200"),
        InlineKeyboardButton("≠ 422",  callback_data="cond:not:422"),
        InlineKeyboardButton("≠ 500",  callback_data="cond:not:500"),
        InlineKeyboardButton("≠ 503",  callback_data="cond:not:503"),
    ],
    [InlineKeyboardButton("✏️ Ввести вручную", callback_data="cond:manual")],
])

INTERVAL_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("30с",  callback_data="iv:30"),
        InlineKeyboardButton("1м",   callback_data="iv:60"),
        InlineKeyboardButton("5м",   callback_data="iv:300"),
        InlineKeyboardButton("15м",  callback_data="iv:900"),
        InlineKeyboardButton("1ч",   callback_data="iv:3600"),
    ],
    [InlineKeyboardButton("✏️ Ввести вручную", callback_data="iv:manual")],
])

_STOP_KB = InlineKeyboardMarkup([[
    InlineKeyboardButton("🛑 Остановить мониторинг", callback_data="action_stop"),
]])


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
                    f"✅ <b>Условие выполнено!</b>\n\n"
                    f'🔗 URL: <a href="{url}">{url}</a>\n'
                    f"📋 Статус: <b>{status}</b> (ожидался {condition_label(operator, code)})\n\n"
                    f"Мониторинг остановлен. Используйте /monitor для повторного запуска."
                ),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            job.schedule_removal()

    except Exception as e:
        logger.error(f"[{chat_id}] Ошибка проверки {url}: {e}")


# ---------------------------------------------------------------------------
# Conversation handlers
# ---------------------------------------------------------------------------

async def monitor_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.answer()
    await message.reply_text(
        "👁 <b>Мониторинг URL</b>\n\nОтправьте URL для мониторинга:",
        parse_mode="HTML",
    )
    return ASK_URL


async def got_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith(("http://", "https://")):
        await update.message.reply_text(
            "Это не похоже на корректный URL.\n"
            "Пожалуйста, отправьте URL, начинающийся с "
            "<code>http://</code> или <code>https://</code>",
            parse_mode="HTML",
        )
        return ASK_URL

    context.user_data["url"] = url
    await update.message.reply_text(
        "Принято! Выберите условие для уведомления:",
        parse_mode="HTML",
        reply_markup=CONDITION_KB,
    )
    return ASK_CONDITION


async def got_condition_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # "cond:is:200" / "cond:not:422" / "cond:manual"

    if data == "cond:manual":
        await query.edit_message_text(
            "Введите условие вручную.\n\n"
            "Примеры:\n"
            "• <code>not 422</code> — статус НЕ 422\n"
            "• <code>200</code>     — статус равен 200",
            parse_mode="HTML",
        )
        return ASK_CONDITION

    _, operator, code_str = data.split(":")
    condition = (operator, int(code_str))
    context.user_data["condition"] = condition
    await query.edit_message_text(
        f"Условие: <b>{condition_label(operator, int(code_str))}</b>\n\n"
        "Выберите интервал проверки:",
        parse_mode="HTML",
        reply_markup=INTERVAL_KB,
    )
    return ASK_INTERVAL


async def got_condition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Text fallback for manual condition input."""
    condition = parse_condition(update.message.text)
    if condition is None:
        await update.message.reply_text(
            "Не удалось распознать условие.\n"
            "Используйте формат <code>not 422</code> или <code>200</code>.",
            parse_mode="HTML",
        )
        return ASK_CONDITION

    context.user_data["condition"] = condition
    operator, code = condition
    await update.message.reply_text(
        f"Условие: <b>{condition_label(operator, code)}</b>\n\n"
        "Выберите интервал проверки:",
        parse_mode="HTML",
        reply_markup=INTERVAL_KB,
    )
    return ASK_INTERVAL


async def got_interval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # "iv:30" / "iv:manual"

    if data == "iv:manual":
        await query.edit_message_text(
            "Введите интервал вручную.\n\n"
            "Примеры: <code>30с</code>, <code>5м</code>, <code>2ч</code>",
            parse_mode="HTML",
        )
        return ASK_INTERVAL

    interval = int(data.split(":")[1])
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _confirm_and_start(query.message, context, interval)
    return ConversationHandler.END


async def got_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Text fallback for manual interval input."""
    text = update.message.text.strip().lower()
    if text == "skip":
        interval = DEFAULT_POLL_INTERVAL_SECONDS
    else:
        interval = parse_interval(text)
        if interval is None or interval < 5:
            await update.message.reply_text(
                "Не удалось распознать интервал или он слишком мал (минимум 5с).\n"
                "Попробуйте <code>30s</code>, <code>5m</code>, <code>1h</code>.",
                parse_mode="HTML",
            )
            return ASK_INTERVAL

    await _confirm_and_start(update.message, context, interval)
    return ConversationHandler.END


async def _confirm_and_start(message, context: ContextTypes.DEFAULT_TYPE, interval: int):
    url = context.user_data["url"]
    condition = context.user_data["condition"]
    operator, code = condition

    for job in context.job_queue.get_jobs_by_name(str(message.chat_id)):
        job.schedule_removal()

    context.job_queue.run_repeating(
        monitor_job,
        interval=interval,
        first=0,
        chat_id=message.chat_id,
        name=str(message.chat_id),
        data={"url": url, "condition": condition, "interval": interval},
    )

    await message.reply_text(
        f"<b>✅ МОНИТОРИНГ ЗАПУЩЕН</b>\n\n"
        f"<b>Параметры:</b>\n"
        f'🔗 Адрес: <a href="{url}">{url}</a>\n'
        f"📋 Условие: {condition_label(operator, code)}\n"
        f"⏱ Интервал: каждые {interval_label(interval)}\n\n"
        f"<b>📬 Вы получите уведомление</b> когда условие выполнится",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=_STOP_KB,
    )


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    jobs = context.job_queue.get_jobs_by_name(chat_id)
    if update.callback_query:
        await update.callback_query.answer()
        reply = update.callback_query.message.reply_text
        try:
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        reply = update.message.reply_text

    if jobs:
        for job in jobs:
            job.schedule_removal()
        await reply("<b>🛑 МОНИТОРИНГ ОСТАНОВЛЕН</b>\n\nМониторинг URL успешно выключен.", parse_mode="HTML")
    else:
        await reply("❌ <b>Нет активного мониторинга</b>\n\nДля запуска используйте: <code>/monitor</code>", parse_mode="HTML")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    jobs = context.job_queue.get_jobs_by_name(chat_id)
    if update.callback_query:
        await update.callback_query.answer()
        reply = update.callback_query.message.reply_text
    else:
        reply = update.message.reply_text

    if jobs:
        data = jobs[0].data
        operator, code = data["condition"]
        iv = data.get("interval", DEFAULT_POLL_INTERVAL_SECONDS)
        url = data["url"]
        await reply(
            f"<b>👁 МОНИТОРИНГ URL</b>\n"
            f"{'─' * 40}\n\n"
            f"<b>Адрес:</b>\n"
            f'<a href="{url}">{url}</a>\n\n'
            f"<b>Условие срабатывания:</b>\n"
            f"{condition_label(operator, code)}\n\n"
            f"<b>Интервал проверки:</b>\n"
            f"{interval_label(iv)}\n\n"
            f"<b>Статус:</b> ✅ Активен\n"
            f"{'─' * 40}",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=_STOP_KB,
        )
    else:
        await reply(
            "❌ <b>No active URL monitoring</b>\n\n"
            "To start monitoring, use:\n"
            "<code>/monitor</code>",
            parse_mode="HTML",
        )


def build_monitor_conversation(cancel_handler) -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("monitor", monitor_cmd),
            CallbackQueryHandler(monitor_cmd, pattern="^action_monitor$"),
        ],
        states={
            ASK_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_url)],
            ASK_CONDITION: [
                CallbackQueryHandler(got_condition_callback, pattern="^cond:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_condition),
            ],
            ASK_INTERVAL: [
                CallbackQueryHandler(got_interval_callback, pattern="^iv:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_interval),
            ],
        },
        fallbacks=[cancel_handler],
    )
