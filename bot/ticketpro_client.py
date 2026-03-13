"""HTTP client and pure parsing/formatting helpers for ticketpro.by — no Telegram dependency."""
import html as html_lib
import json
import logging
import re
from datetime import date, datetime, timedelta

import requests as http_requests

from bot.config import TICKETPRO_SEARCH_URL, TICKETPRO_SEARCH_HEADERS, SEARCH_UA

logger = logging.getLogger(__name__)


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
