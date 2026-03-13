# Code Guidelines

Quick reminders to keep the codebase easy to read and change.

## File size

- **One responsibility per file.** If you find yourself scrolling more than a screenful to understand what a file does, split it.
- Aim for **< 200 lines** of logic per module. Comments and blank lines don't count, but they're a hint.
- The current split is: `config` → constants, `monitor` → URL-monitoring flow, `ticketpro` → search flow, `app` → wiring. Keep additions within their domain.

## Adding a new feature

1. Does it fit an existing module? Add it there.
2. If it's a new domain (e.g. calendar integration), create a new `bot/<domain>.py` and a matching `tests/unit/test_<domain>_helpers.py`.
3. Wire it up in `bot/app.py` — keep `app.py` as thin glue only.

## Tests

- **Unit tests** (`tests/unit/`) — pure helpers, no network, no Telegram. Run fast, run always.
- **Integration tests** (`tests/integration/`) — mock HTTP, exercise full pipelines. Still no real network needed.
- Name test files after the module they cover: `test_monitor_helpers.py`, `test_ticketpro_helpers.py`.
- Run all tests: `pytest -v`
- Run only unit tests: `pytest tests/unit -v`

## Conversation handlers

- Keep `build_*_conversation()` factories at the bottom of each module — they're the public API.
- Each state should have both a `CallbackQueryHandler` (button) and a `MessageHandler` (text fallback) where it makes sense.
- Always call `await query.answer()` first in every `CallbackQueryHandler`.

## HTML vs Markdown

All bot messages use `parse_mode="HTML"`. Never switch back to Markdown — it has stricter escaping rules and breaks on unmatched characters. Escape user-supplied strings with `html.escape()`.

## Environment

- `BOT_TOKEN` must be set as an environment variable before running.
- The Procfile entry point is `monitor_bot.py` — don't rename or move it.
