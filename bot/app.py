from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
)

from bot.config import BOT_TOKEN
from bot.monitor import build_monitor_conversation, stop_cmd, status_cmd
from bot.search_monitor import (
    build_search_monitor_conversation,
    stop_search_monitor_cmd,
    status_search_monitor_cmd,
)
from bot.ticketpro import build_search_conversation

_MAIN_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔍 Поиск событий",  callback_data="action_search"),
        InlineKeyboardButton("� Мониторинг поиска", callback_data="action_monitor_search"),
    ],
    [
        InlineKeyboardButton("👁 Мониторинг URL", callback_data="action_monitor"),
        InlineKeyboardButton("📊 Статус",  callback_data="action_status"),
    ],
    [
        InlineKeyboardButton("🛑 Стоп",    callback_data="action_stop"),
    ],
])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>🤖 Бот событий ticketpro.by</b>\n\n"
        "Что я умею:\n"
        "  🔍 Искать события по запросу\n"
        "  � Следить за новыми событиями по запросу\n"
        "  �👁 Следить за HTTP-статусом URL\n\n"
        "Нажмите кнопку или введите команду:",
        parse_mode="HTML",
        reply_markup=_MAIN_KB,
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline-кнопки главного меню (статус / стоп)."""
    query = update.callback_query
    await query.answer()
    if query.data == "action_stop":
        await stop_cmd(update, context)
        await stop_search_monitor_cmd(update, context)
    elif query.data == "action_status":
        await status_cmd(update, context)
        await status_search_monitor_cmd(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END


async def post_init(app: Application) -> None:
    await app.bot.set_my_commands([
        BotCommand("start",           "Главное меню"),
        BotCommand("search",          "Поиск событий на ticketpro.by"),
        BotCommand("monitor_search",  "Мониторинг поиска событий"),
        BotCommand("monitor",         "Мониторинг URL"),
        BotCommand("status",          "Статус мониторинга"),
        BotCommand("stop",            "Остановить мониторинг"),
        BotCommand("cancel",          "Отменить текущую операцию"),
    ])


def main():
    if not BOT_TOKEN:
        raise ValueError("Установите BOT_TOKEN в переменной окружения перед запуском.")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    cancel_handler = CommandHandler("cancel", cancel)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(build_monitor_conversation(cancel_handler))
    app.add_handler(build_search_monitor_conversation(cancel_handler))
    app.add_handler(build_search_conversation(cancel_handler))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    # action_search / action_monitor / action_monitor_search are handled inside ConversationHandlers above.
    # action_stop / action_status are handled here at lower priority.
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^action_(stop|status)$"))

    print("Бот запущен... Нажмите Ctrl+C для остановки.")
    app.run_polling()
