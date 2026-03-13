"""Integration tests for the TicketPro search pipeline.

These tests mock the HTTP layer so no real network calls are made,
but they exercise the full search_events → parse → return chain.

Run: pytest tests/integration/test_search_flow.py -v
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from bot.ticketpro_client import search_events


def _event_block(name: str = "Test Event") -> str:
    data = {
        "@type": "Event",
        "name": name,
        "url": "https://ticketpro.by/event/1",
        "startDate": "2026-04-01T20:00:00",
        "endDate": "",
        "location": {"name": "Arena", "address": {"addressLocality": "Минск"}},
        "offers": {"lowPrice": "30", "highPrice": "100", "priceCurrency": "BYN"},
        "image": ["https://ticketpro.by/img.jpg"],
    }
    return f'<script type="application/ld+json">{json.dumps(data)}</script>'


def _mock_session(csrf_html: str, *search_htmls: str):
    """Return a mocked Session whose .get() yields csrf_html then each search_html."""
    session = MagicMock()
    csrf_resp = MagicMock()
    csrf_resp.text = csrf_html

    pages = []
    for html in search_htmls:
        resp = MagicMock()
        resp.text = html
        resp.raise_for_status = MagicMock()
        pages.append(resp)

    session.get.side_effect = [csrf_resp, *pages]
    return session


CSRF_HTML = '<meta name="csrf-token" content="tok123">'


class TestSearchEvents:
    def test_returns_empty_on_connection_error(self):
        with patch("bot.ticketpro_client.http_requests.Session") as cls:
            cls.return_value.get.side_effect = Exception("timeout")
            assert search_events("concert", 7) == []

    def test_single_page_single_event(self):
        html = _event_block("Jazz Night")
        with patch("bot.ticketpro_client.http_requests.Session") as cls:
            cls.return_value = _mock_session(CSRF_HTML, html)
            results = search_events("jazz", 7)

        assert len(results) == 1
        assert results[0]["name"] == "Jazz Night"

    def test_no_events_returns_empty(self):
        with patch("bot.ticketpro_client.http_requests.Session") as cls:
            cls.return_value = _mock_session(CSRF_HTML, "<html></html>")
            assert search_events("nothing", 7) == []

    def test_days_zero_sends_empty_date_before(self):
        """days=0 means no upper date limit; date_before param should be empty."""
        captured_params = {}

        def fake_get(url, **kwargs):
            captured_params.update(kwargs.get("params", {}))
            resp = MagicMock()
            resp.text = CSRF_HTML if not captured_params else "<html></html>"
            resp.raise_for_status = MagicMock()
            return resp

        with patch("bot.ticketpro_client.http_requests.Session") as cls:
            cls.return_value.get.side_effect = fake_get
            search_events("event", 0)

        assert captured_params.get("date_before", None) == ""

    def test_two_pages_collected(self):
        next_page_html = (
            _event_block("Event A")
            + '<li class="page-next"><a>›</a></li>'
        )
        last_page_html = _event_block("Event B")

        with patch("bot.ticketpro_client.http_requests.Session") as cls:
            cls.return_value = _mock_session(CSRF_HTML, next_page_html, last_page_html)
            results = search_events("event", 30)

        names = [r["name"] for r in results]
        assert "Event A" in names
        assert "Event B" in names

    def test_http_error_on_search_returns_partial(self):
        """If page 2 fails, we still return whatever was collected."""
        html_p1 = _event_block("Good Event") + '<li class="page-next"><a>›</a></li>'

        session = MagicMock()
        csrf_resp = MagicMock()
        csrf_resp.text = CSRF_HTML

        p1_resp = MagicMock()
        p1_resp.text = html_p1
        p1_resp.raise_for_status = MagicMock()

        p2_resp = MagicMock()
        p2_resp.raise_for_status.side_effect = Exception("500")

        session.get.side_effect = [csrf_resp, p1_resp, p2_resp]

        with patch("bot.ticketpro_client.http_requests.Session") as cls:
            cls.return_value = session
            results = search_events("event", 14)

        assert len(results) == 1
        assert results[0]["name"] == "Good Event"
