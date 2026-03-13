"""Unit tests for pure helper functions in bot/monitor.py.

These tests require NO Telegram credentials — helpers are plain Python.
Run: pytest tests/unit/test_monitor_helpers.py -v
"""
import pytest

from bot.monitor_helpers import (
    condition_label,
    interval_label,
    parse_condition,
    parse_interval,
)


class TestParseCondition:
    def test_not_condition(self):
        assert parse_condition("not 422") == ("not", 422)

    def test_not_condition_uppercase(self):
        assert parse_condition("NOT 503") == ("not", 503)

    def test_is_condition(self):
        assert parse_condition("200") == ("is", 200)

    def test_strips_whitespace(self):
        assert parse_condition("  not 500  ") == ("not", 500)

    def test_invalid_text(self):
        assert parse_condition("ok") is None

    def test_invalid_mixed(self):
        assert parse_condition("not ok") is None

    def test_empty_string(self):
        assert parse_condition("") is None


class TestConditionLabel:
    def test_not_label(self):
        assert condition_label("not", 422) == "НЕ 422"

    def test_is_label(self):
        assert condition_label("is", 200) == "= 200"


class TestParseInterval:
    @pytest.mark.parametrize("text,expected", [
        ("30",    30),
        ("30с",   30),
        ("30s",   30),
        ("5m",    300),
        ("5м",    300),
        ("5мин",  300),
        ("2h",    7200),
        ("2ч",    7200),
        ("2час",  7200),
        ("1.5h",  5400),
    ])
    def test_valid(self, text, expected):
        assert parse_interval(text) == expected

    def test_invalid_text(self):
        assert parse_interval("abc") is None

    def test_empty(self):
        assert parse_interval("") is None


class TestIntervalLabel:
    @pytest.mark.parametrize("seconds,expected", [
        (30,    "30с"),
        (60,    "1м"),
        (300,   "5м"),
        (3600,  "1ч"),
        (7200,  "2ч"),
        (90,    "90с"),   # not an exact minute
        (3660,  "61м"),   # exact minute (61m), not exact hour
    ])
    def test_label(self, seconds, expected):
        assert interval_label(seconds) == expected
