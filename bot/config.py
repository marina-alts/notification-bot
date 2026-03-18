import logging
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DEFAULT_POLL_INTERVAL_SECONDS = 60

# Conversation states
ASK_URL, ASK_CONDITION, ASK_INTERVAL, ASK_SEARCH_QUERY, ASK_SEARCH_DAYS, \
    ASK_SEARCH_MONITOR_QUERY, ASK_SEARCH_MONITOR_DAYS, ASK_SEARCH_MONITOR_INTERVAL = range(8)

# TicketPro
TICKETPRO_SEARCH_URL = "https://www.ticketpro.by/rasshirennyj-poisk/"
SEARCH_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TICKETPRO_SEARCH_HEADERS = {
    "User-Agent": SEARCH_UA,
    "Accept": "text/html, */*; q=0.01",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "X-PJAX": "true",
    "X-PJAX-Container": "#advanced-search-pjax",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": TICKETPRO_SEARCH_URL,
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
