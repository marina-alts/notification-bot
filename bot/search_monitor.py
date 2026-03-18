import asyncio
import logging
from datetime import datetime

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
    ASK_SEARCH_MONITOR_QUERY,
    ASK_SEARCH_MONITOR_DAYS,
    ASK_SEARCH_MONITOR_INTERVAL,
    DEFAULT_POLL_INTERVAL_SECONDS,
)
from bot.monitor_helpers import interval_label, parse_interval
from bot.ticketpro_client import search_events
from bot.ticketpro import _send_event

logger = logging.getLogger(__name__)

# Pre-built inline keyboards
DAYS_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("7 дней",  callback_data="monitor_days:7"),
        InlineKeyboardButton("14 дней", callback_data="monitor_days:14"),
        InlineKeyboardButton("30 дней", callback_data="monitor_days:30"),
    ],
    [InlineKeyboardButton("🌐 Все события", callback_data="monitor_days:0")],
])

INTERVAL_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("1м",   callback_data="monitor_iv:60"),
        InlineKeyboardButton("5м",   callback_data="monitor_iv:300"),
        InlineKeyboardButton("15м",  callback_data="monitor_iv:900"),
        InlineKeyboardButton("1ч",   callback_data="monitor_iv:3600"),
    ],
    [InlineKeyboardButton("✏️ Ввести вручную", callback_data="monitor_iv:manual")],
])

_STOP_KB = InlineKeyboardMarkup([[
    InlineKeyboardButton("🛑 Остановить мониторинг поиска", callback_data="action_stop"),
]])


# ---------------------------------------------------------------------------
# Background job
# ---------------------------------------------------------------------------

async def search_monitor_job(context: ContextTypes.DEFAULT_TYPE):
    """Background job that periodically searches for new events."""
    job = context.job
    chat_id = job.chat_id
    search_query = job.data["query"]
    days_ahead = job.data["days"]
    seen_event_urls = job.data.get("seen_urls", set())

    try:
        events = await asyncio.get_running_loop().run_in_executor(
            None, search_events, search_query, days_ahead
        )
        logger.info(f"[{chat_id}] Поиск '{search_query}': найдено {len(events)} событий")

        # Filter to new events only
        new_events = [e for e in events if e["url"] not in seen_event_urls]

        if new_events:
            # Update seen URLs
            for event in new_events:
                if event["url"]:
                    seen_event_urls.add(event["url"])
            job.data["seen_urls"] = seen_event_urls

            # Send notification header
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"✨ <b>Новые события найдены!</b>\n\n"
                    f"🔍 Запрос: <b>{search_query}</b>\n"
                    f"📊 Найдено: <b>{len(new_events)}</b> новых\n\n"
                    f"⏰ {datetime.now().strftime('%d.%m.%Y, %H:%M')}"
                ),
                parse_mode="HTML",
            )

            # Send each event
            for event in new_events:
                await _send_event(context.bot, chat_id, event)
                await asyncio.sleep(0.4)

    except Exception as e:
        logger.error(f"[{chat_id}] Ошибка поиска '{search_query}': {e}")


# ---------------------------------------------------------------------------
# Conversation handlers
# ---------------------------------------------------------------------------

async def search_monitor_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.answer()
    await message.reply_text(
        "📌 <b>Мониторинг поиска событий</b>\n\n"
        "Введите название события или исполнителя:",
        parse_mode="HTML",
    )
    return ASK_SEARCH_MONITOR_QUERY


async def got_search_monitor_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text(
            "Запрос не может быть пустым. Введите название события или исполнителя:"
        )
        return ASK_SEARCH_MONITOR_QUERY

    context.user_data["monitor_query"] = query
    await update.message.reply_text(
        "На сколько дней вперёд искать новые события?",
        reply_markup=DAYS_KB,
    )
    return ASK_SEARCH_MONITOR_DAYS


async def got_search_monitor_days_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_cb = update.callback_query
    await query_cb.answer()
    days = int(query_cb.data.split(":")[1])
    context.user_data["monitor_days"] = days

    try:
        await query_cb.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    await query_cb.edit_message_text(
        "Выберите интервал проверки поиска:",
        reply_markup=INTERVAL_KB,
    )
    return ASK_SEARCH_MONITOR_INTERVAL


async def got_search_monitor_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Text fallback when user types a number instead of pressing a button."""
    text = update.message.text.strip()
    try:
        days = int(text)
        if days < 0:
            raise ValueError("negative")
    except ValueError:
        await update.message.reply_text(
            "Введите целое число (например: "
            "<code>7</code>, <code>14</code>, <code>30</code> или "
            "<code>0</code> без ограничений):",
            parse_mode="HTML",
        )
        return ASK_SEARCH_MONITOR_DAYS

    context.user_data["monitor_days"] = days
    await update.message.reply_text(
        "Выберите интервал проверки поиска:",
        reply_markup=INTERVAL_KB,
    )
    return ASK_SEARCH_MONITOR_INTERVAL


async def got_search_monitor_interval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # "monitor_iv:60" / "monitor_iv:manual"

    if data == "monitor_iv:manual":
        await query.edit_message_text(
            "Введите интервал вручную.\n\n"
            "Примеры: <code>30с</code>, <code>5м</code>, <code>2ч</code>",
            parse_mode="HTML",
        )
        return ASK_SEARCH_MONITOR_INTERVAL

    interval = int(data.split(":")[1])
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _confirm_and_start_search_monitor(query.message, context, interval)
    return ConversationHandler.END


async def got_search_monitor_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            return ASK_SEARCH_MONITOR_INTERVAL

    await _confirm_and_start_search_monitor(update.message, context, interval)
    return ConversationHandler.END


async def _confirm_and_start_search_monitor(
    message, context: ContextTypes.DEFAULT_TYPE, interval: int
):
    search_query = context.user_data["monitor_query"]
    days = context.user_data["monitor_days"]

    # Stop any existing search monitor job
    chat_id_str = str(message.chat_id)
    for job in context.job_queue.get_jobs_by_name(f"search_monitor_{chat_id_str}"):
        job.schedule_removal()

    # Start new search monitor job
    context.job_queue.run_repeating(
        search_monitor_job,
        interval=interval,
        first=0,
        chat_id=message.chat_id,
        name=f"search_monitor_{chat_id_str}",
        data={
            "query": search_query,
            "days": days,
            "interval": interval,
            "seen_urls": set(),
        },
    )

    days_label = f"за {days} дней" if days > 0 else "без ограничения по дате"
    await message.reply_text(
        f"✅ <b>Мониторинг поиска запущен!</b>\n\n"
        f"🔍 Запрос: <b>{search_query}</b>\n"
        f"📅 Период: <b>{days_label}</b>\n"
        f"⏱ Проверка каждые <b>{interval_label(interval)}</b>\n\n"
        "Я сообщу, когда появятся новые события.",
        parse_mode="HTML",
        reply_markup=_STOP_KB,
    )


async def stop_search_monitor_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop search monitor (called from conversation or separately)."""
    chat_id = str(update.effective_chat.id)
    jobs = context.job_queue.get_jobs_by_name(f"search_monitor_{chat_id}")
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
        await reply("🛑 Мониторинг поиска остановлен.")
    else:
        await reply("Нет активного мониторинга поиска для остановки.")


async def status_search_monitor_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show status of search monitor."""
    chat_id = str(update.effective_chat.id)
    jobs = context.job_queue.get_jobs_by_name(f"search_monitor_{chat_id}")
    if update.callback_query:
        await update.callback_query.answer()
        reply = update.callback_query.message.reply_text
    else:
        reply = update.message.reply_text

    if jobs:
        data = jobs[0].data
        query = data["query"]
        days = data["days"]
        interval = data.get("interval", DEFAULT_POLL_INTERVAL_SECONDS)
        seen_count = len(data.get("seen_urls", set()))
        days_label = f"за {days} дней" if days > 0 else "без ограничения по дате"
        await reply(
            f"📌 <b>Текущий мониторинг поиска:</b>\n\n"
            f"🔍 Запрос: <b>{query}</b>\n"
            f"📅 Период: <b>{days_label}</b>\n"
            f"⏱ Каждые <b>{interval_label(interval)}</b>\n"
            f"📊 Обнаружено событий: <b>{seen_count}</b>",
            parse_mode="HTML",
            reply_markup=_STOP_KB,
        )
    else:
        await reply(
            "Нет активного мониторинга поиска. Используйте /monitor_search для запуска.",
        )


def build_search_monitor_conversation(cancel_handler) -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("monitor_search", search_monitor_cmd),
            CallbackQueryHandler(search_monitor_cmd, pattern="^action_monitor_search$"),
        ],
        states={
            ASK_SEARCH_MONITOR_QUERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_search_monitor_query)
            ],
            ASK_SEARCH_MONITOR_DAYS: [
                CallbackQueryHandler(got_search_monitor_days_callback, pattern="^monitor_days:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_search_monitor_days),
            ],
            ASK_SEARCH_MONITOR_INTERVAL: [
                CallbackQueryHandler(got_search_monitor_interval_callback, pattern="^monitor_iv:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_search_monitor_interval),
            ],
        },
        fallbacks=[cancel_handler],
    )
