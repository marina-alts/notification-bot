# Code Guidelines

Quick reminders to keep the codebase easy to read and change.

## File size

- **One responsibility per file.** If you find yourself scrolling more than a screenful to understand what a file does, split it.
- Aim for **< 200 lines** of logic per module. Comments and blank lines don't count, but they're a hint.
- The current split is: `config` → constants, `monitor` → URL-monitoring flow, `ticketpro` → search flow, `app` → wiring. Keep additions within their domain.

## Adding a new feature

**See SKILL.md** for full workflow. Quick steps:

1. **Plan with questions:** Data persistence? Concurrency? UI placement? Reusable code?
2. **Create module:** `bot/feature.py` with handlers + conversation builder + job function (if polling)
3. **Add states:** New states in `config.py` if needed
4. **Wire in app.py:** Import, add button to menu, register handlers
5. **Improve UI:** Use HTML formatting, consistent status displays
6. **Test:** Check imports, job naming unique, HTML escaping

**Module pattern:**
```python
# In bot/feature.py:
# 1. Imports
# 2. Constants (keyboards, state constants from config)
# 3. Background job (if needed) → async def feature_job(context)
# 4. Conversation handlers → async def handler_name(update, context)
# 5. Build function → def build_feature_conversation(cancel_handler)
```

**Job naming:** Always use `feature_{chat_id}` to avoid conflicts.

**App wiring:** Keep App as thin glue. All domain logic stays in feature modules.

## Tests

- **Unit tests** (`tests/unit/`) — pure helpers, no network, no Telegram. Run fast, run always.
- **Integration tests** (`tests/integration/`) — mock HTTP, exercise full pipelines. Still no real network needed.
- Name test files after the module they cover: `test_monitor_helpers.py`, `test_ticketpro_helpers.py`.
- Run all tests: `pytest -v`
- Run only unit tests: `pytest tests/unit -v`

## Conversation handlers

- `build_*_conversation()` at the bottom of each module — public API
- Each state: `CallbackQueryHandler` (button) + `MessageHandler` (text fallback)
- Always: `await query.answer()` first in every callback
- Keep to **3-4 steps max**
- Provide `/cancel` always

## Messages

- **Always** `parse_mode="HTML"`
- Escape user input: `html.escape(user_string)`
- Status format: `<b>ICON FEATURE</b>\n────\n<b>Param:</b> Value\n<b>Status:</b> ✅ Active`
- Use visual separators: `{'─' * 40}`

## Basics

- `BOT_TOKEN` environment variable required
- Entry point: `monitor_bot.py` (don't move)
- Tests: `pytest -v` (unit) or `pytest tests/unit -v` (fast)
- Slack space to keep files <200 lines — if scrolling too much, split it

## Resources

- **Adding features?** Use `/telegram-bot-feature-development` skill or `/implement-bot-feature` prompt
- **Development tips?** See `.github/copilot-instructions.md`
