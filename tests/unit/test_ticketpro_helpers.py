"""Unit tests for pure helper functions in bot/ticketpro.py.

These tests require NO network access and NO Telegram credentials.
Run: pytest tests/unit/test_ticketpro_helpers.py -v
"""
import json

import pytest

from bot.ticketpro_client import (
    _build_event_caption,
    _format_start_date,
    _has_next_page,
    _parse_events_from_html,
)


# ---------------------------------------------------------------------------
# _format_start_date
# ---------------------------------------------------------------------------

class TestFormatStartDate:
    def test_full_iso_datetime(self):
        assert _format_start_date("2026-03-13T19:00:00") == "13.03.2026, 19:00"

    def test_iso_with_offset(self):
        # should not crash on timezone suffix
        result = _format_start_date("2026-04-01T20:00:00+03:00")
        assert "01.04.2026" in result

    def test_invalid_returns_original(self):
        assert _format_start_date("not-a-date") == "not-a-date"

    def test_empty_returns_empty(self):
        assert _format_start_date("") == ""


# ---------------------------------------------------------------------------
# _build_event_caption
# ---------------------------------------------------------------------------

def _make_event(**kwargs):
    base = {
        "name": "Тест",
        "url": "https://ticketpro.by/event/1",
        "startDate": "2026-04-01T20:00:00",
        "endDate": "",
        "location": "Venue",
        "city": "Минск",
        "price_min": "20",
        "price_max": "50",
        "currency": "BYN",
        "image": "",
    }
    base.update(kwargs)
    return base


class TestBuildEventCaption:
    def test_contains_bold_name(self):
        caption = _build_event_caption(_make_event(name="Concert"))
        assert "<b>Concert</b>" in caption

    def test_contains_date(self):
        caption = _build_event_caption(_make_event())
        assert "01.04.2026" in caption

    def test_contains_location(self):
        caption = _build_event_caption(_make_event())
        assert "Минск" in caption

    def test_price_range(self):
        caption = _build_event_caption(_make_event(price_min="20", price_max="50"))
        assert "20–50 BYN" in caption

    def test_same_price(self):
        caption = _build_event_caption(_make_event(price_min="30", price_max="30"))
        assert "от 30 BYN" in caption

    def test_link_present(self):
        caption = _build_event_caption(_make_event(url="https://example.com"))
        assert 'href="https://example.com"' in caption

    def test_html_escapes_name(self):
        caption = _build_event_caption(_make_event(name="<script>xss</script>"))
        assert "<script>" not in caption
        assert "&lt;script&gt;" in caption

    def test_html_escapes_location(self):
        caption = _build_event_caption(_make_event(city="A & B", location=""))
        assert "&amp;" in caption

    def test_caption_within_telegram_limit(self):
        # Telegram photo caption limit is 1024 chars
        long_name = "A" * 2000
        caption = _build_event_caption(_make_event(name=long_name))
        assert len(caption) <= 1024

    def test_no_price_omitted(self):
        caption = _build_event_caption(_make_event(price_min="", price_max=""))
        assert "💰" not in caption

    def test_no_url_omitted(self):
        caption = _build_event_caption(_make_event(url=""))
        assert "🎟" not in caption


# ---------------------------------------------------------------------------
# _parse_events_from_html
# ---------------------------------------------------------------------------

def _json_ld_block(data: dict) -> str:
    return f'<script type="application/ld+json">{json.dumps(data)}</script>'


class TestParseEventsFromHtml:
    def test_parses_single_event(self):
        data = {
            "@type": "Event",
            "name": "Rock Night",
            "url": "https://ticketpro.by/1",
            "startDate": "2026-04-01T20:00:00",
            "endDate": "",
            "location": {"name": "Club", "address": {"addressLocality": "Минск"}},
            "offers": {"lowPrice": "10", "highPrice": "30", "priceCurrency": "BYN"},
            "image": ["https://ticketpro.by/img.jpg"],
        }
        events = _parse_events_from_html(_json_ld_block(data))
        assert len(events) == 1
        assert events[0]["name"] == "Rock Night"
        assert events[0]["city"] == "Минск"
        assert events[0]["image"] == "https://ticketpro.by/img.jpg"

    def test_skips_non_event_type(self):
        data = {"@type": "Organization", "name": "Corp"}
        events = _parse_events_from_html(_json_ld_block(data))
        assert events == []

    def test_parses_multiple_events(self):
        block = _json_ld_block({"@type": "Event", "name": "A", "url": "", "startDate": "",
                                 "location": {}, "offers": {}, "image": []})
        block += _json_ld_block({"@type": "Event", "name": "B", "url": "", "startDate": "",
                                  "location": {}, "offers": {}, "image": []})
        events = _parse_events_from_html(block)
        assert len(events) == 2

    def test_handles_missing_fields_gracefully(self):
        data = {"@type": "Event"}
        events = _parse_events_from_html(_json_ld_block(data))
        assert len(events) == 1
        assert events[0]["name"] == ""
        assert events[0]["image"] == ""

    def test_empty_html(self):
        assert _parse_events_from_html("") == []

    def test_ignores_malformed_json(self):
        html = '<script type="application/ld+json">NOT_JSON</script>'
        assert _parse_events_from_html(html) == []


# ---------------------------------------------------------------------------
# _has_next_page
# ---------------------------------------------------------------------------

class TestHasNextPage:
    def test_active_next(self):
        assert _has_next_page('<li class="page-next"><a>›</a></li>') is True

    def test_disabled_next(self):
        assert _has_next_page('<li class="page-next disabled"><a>›</a></li>') is False

    def test_no_pagination(self):
        assert _has_next_page("<html><body>content</body></html>") is False
