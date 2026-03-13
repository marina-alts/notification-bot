import asyncio
import logging
from io import BytesIO

import requests as http_requests
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
    ASK_SEARCH_QUERY,
    ASK_SEARCH_DAYS,
    TICKETPRO_SEARCH_URL,
    SEARCH_UA,
)
from bot.ticketpro_client import (
    _build_event_caption,
    search_events,
)

logger = logging.getLogger(__name__)

DAYS_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("7 дней",  callback_data="days:7"),
        InlineKeyboardButton("14 дней", callback_data="days:14"),
        InlineKeyboardButton("30 дней", callback_data="days:30"),
    ],
    [InlineKeyboardButton("🌐 Все события", callback_data="days:0")],
])


# ---------------------------------------------------------------------------
# HTTP / parsing
# ---------------------------------------------------------------------------

def _get_csrf_token(session) -> str | None:
    try:
        resp = session.get(
            TICKETPRO_SEARCH_URL,
            headers={"User-Agent": SEARCH_UA},
            timeout=15,
        )
        m = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', resp.text)
        return m.group(1) if m else None
    except Exception as e:
        logger.warning(f"Не удалось получить CSRF-токен: {e}")
        return None


def _parse_events_from_html(html: str) -> list:
    events = []
    for match in re.finditer(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(match.group(1).strip())
            if data.get("@type") != "Event":
                continue
            offers = data.get("offers", {})
            location = data.get("location", {})
            address = location.get("address", {})
            images = data.get("image", [])
            events.append({
                "name": data.get("name", ""),
                "url": data.get("url", ""),
                "startDate": data.get("startDate", ""),
                "endDate": data.get("endDate", ""),
                "location": location.get("name", ""),
                "city": address.get("addressLocality", ""),
                "price_min": offers.get("lowPrice", ""),
                "price_max": offers.get("highPrice", ""),
                "currency": offers.get("priceCurrency", "BYN"),
                "image": images[0] if images else "",
            })
        except Exception:
            pass
    return events


def _has_next_page(html: str) -> bool:
    has_next = bool(re.search(r'class="page-next"', html))
    is_disabled = bool(re.search(r'class="page-next\s+disabled"', html))
    return has_next and not is_disabled


def search_events(query: str, days_ahead: int) -> list:
    """Ищет события на ticketpro.by. days_ahead=0 — без ограничения по дате."""
    session = http_requests.Session()
    csrf_token = _get_csrf_token(session)

    date_since = date.today()
    date_before = date_since + timedelta(days=days_ahead) if days_ahead > 0 else None

    headers = dict(TICKETPRO_SEARCH_HEADERS)
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token

    all_events = []
    for page in range(5):  # максимум 5 страниц
        params = {
            "event_or_artist": query,
            "selected_categories": "",
            "date_since": date_since.strftime("%d.%m.%Y"),
            "date_before": date_before.strftime("%d.%m.%Y") if date_before else "",
            "city_id": "",
            "venue_id": "",
            "_pjax": "#advanced-search-pjax",
        }
        if page > 0:
            params["page"] = page + 1
        try:
            resp = session.get(
                TICKETPRO_SEARCH_URL, params=params, headers=headers, timeout=15
            )
            resp.raise_for_status()
            events = _parse_events_from_html(resp.text)
            all_events.extend(events)
            if not _has_next_page(resp.text):
                break
        except Exception as e:
            logger.error(f"Ошибка поиска (страница {page}): {e}")
            break

    return all_events


# ---------------------------------------------------------------------------
# Formatting / sending
# ---------------------------------------------------------------------------

def _format_start_date(iso_date: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%d.%m.%Y, %H:%M")
    except Exception:
        return iso_date


def _build_event_caption(event: dict) -> str:
    name = html_lib.escape(event["name"])
    start = _format_start_date(event["startDate"]) if event["startDate"] else "—"
    parts = [f"<b>{name}</b>", f"📅 {start}"]

    if event["city"] or event["location"]:
        raw_loc = (
            f"{event['city']}, {event['location']}"
            if event["city"] and event["location"]
            else event["city"] or event["location"]
        )
        parts.append(f"📍 {html_lib.escape(raw_loc)}")

    if event["price_min"]:
        if event["price_max"] and event["price_min"] != event["price_max"]:
            parts.append(f"💰 {event['price_min']}–{event['price_max']} {event['currency']}")
        else:
            parts.append(f"💰 от {event['price_min']} {event['currency']}")

    if event["url"]:
        parts.append(f'🎟 <a href="{event["url"]}">Купить билет</a>')

    caption = "\n".join(parts)
    if len(caption) > 1024:
        caption = caption[:1020] + "…"
    return caption


async def _send_event(bot, chat_id: int, event: dict):
    caption = _build_event_caption(event)
    if event["image"]:
        try:
            img_resp = http_requests.get(
                event["image"],
                headers={"Referer": TICKETPRO_SEARCH_URL, "User-Agent": SEARCH_UA},
                timeout=10,
            )
            if img_resp.status_code == 200 and "image" in img_resp.headers.get("content-type", ""):
                photo = BytesIO(img_resp.content)
                photo.name = "event.jpg"
                await bot.send_photo(
                    chat_id=chat_id, photo=photo, caption=caption, parse_mode="HTML"
                )
                return
        except Exception as e:
            logger.warning(f"Не удалось загрузить изображение {event['image']}: {e}")

    await bot.send_message(chat_id=chat_id, text=caption, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Conversation handlers
# ---------------------------------------------------------------------------

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.answer()
    await message.reply_text(
        "🔍 <b>Поиск событий</b> на ticketpro.by\n\n"
        "Введите название события или исполнителя:",
        parse_mode="HTML",
    )
    return ASK_SEARCH_QUERY


async def got_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text(
            "Запрос не может быть пустым. Введите название события или исполнителя:"
        )
        return ASK_SEARCH_QUERY

    context.user_data["search_query"] = query
    await update.message.reply_text(
        "На сколько дней вперёд искать?",
        reply_markup=DAYS_KB,
    )
    return ASK_SEARCH_DAYS


async def got_search_days_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_cb = update.callback_query
    await query_cb.answer()
    days = int(query_cb.data.split(":")[1])
    try:
        await query_cb.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _run_search(query_cb.message, context, days)
    return ConversationHandler.END


async def _run_search(message, context: ContextTypes.DEFAULT_TYPE, days: int):
    search_query = context.user_data["search_query"]
    days_label = f"за {days} дней" if days > 0 else "без ограничения по дате"
    await message.reply_text(
        f"🔍 Ищу <b>{html_lib.escape(search_query)}</b> ({days_label})… Пожалуйста, подождите.",
        parse_mode="HTML",
    )
    try:
        loop = asyncio.get_running_loop()
        events = await loop.run_in_executor(None, search_events, search_query, days)
    except Exception as e:
        logger.error(f"Поиск завершился ошибкой: {e}")
        await message.reply_text("❌ Ошибка при выполнении поиска. Попробуйте позже.")
        return

    if not events:
        await message.reply_text("❌ По вашему запросу ничего не найдено.")
        return

    MAX_EVENTS = 10
    total = len(events)
    suffix = f" (показываю первые {MAX_EVENTS})" if total > MAX_EVENTS else ""
    await message.reply_text(
        f"✅ Найдено событий: <b>{total}</b>{suffix}",
        parse_mode="HTML",
    )
    for event in events[:MAX_EVENTS]:
        await _send_event(context.bot, message.chat_id, event)
        await asyncio.sleep(0.4)


async def got_search_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        return ASK_SEARCH_DAYS

    await _run_search(update.message, context, days)
    return ConversationHandler.END


def build_search_conversation(cancel_handler) -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("search", search_cmd),
            CallbackQueryHandler(search_cmd, pattern="^action_search$"),
        ],
        states={
            ASK_SEARCH_QUERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_search_query)
            ],
            ASK_SEARCH_DAYS: [
                CallbackQueryHandler(got_search_days_callback, pattern="^days:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_search_days),
            ],
        },
        fallbacks=[cancel_handler],
    )
