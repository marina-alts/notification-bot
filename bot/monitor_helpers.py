"""Pure helper functions for URL monitoring — no Telegram dependency."""
import re


def parse_condition(text: str):
    text = text.strip().lower()
    m = re.match(r"^not\s+(\d{3})$", text)
    if m:
        return ("not", int(m.group(1)))
    m = re.match(r"^(\d{3})$", text)
    if m:
        return ("is", int(m.group(1)))
    return None


def condition_label(operator: str, code: int) -> str:
    return f"НЕ {code}" if operator == "not" else f"= {code}"


def parse_interval(text: str):
    text = text.strip().lower()
    m = re.match(r'^(\d+(?:\.\d+)?)\s*(h|hour|hours|ч|час|часа|часов)$', text)
    if m:
        return int(float(m.group(1)) * 3600)
    m = re.match(r'^(\d+(?:\.\d+)?)\s*(m|min|mins|minute|minutes|м|мин|минута|минут)$', text)
    if m:
        return int(float(m.group(1)) * 60)
    m = re.match(r'^(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|с|сек|секунд)?$', text)
    if m:
        return int(float(m.group(1)))
    return None


def interval_label(seconds: int) -> str:
    if seconds >= 3600 and seconds % 3600 == 0:
        return f"{seconds // 3600}ч"
    if seconds >= 60 and seconds % 60 == 0:
        return f"{seconds // 60}м"
    return f"{seconds}с"
