---
description: "Telegram bot development on the notification-bot project"
---

# Development Quick Reference

See `CODE_GUIDELINES.md` for architecture patterns and file standards.

## Adding a Feature

Use `/telegram-bot-feature-development` skill or `/implement-bot-feature` prompt.

Quick checklist:
- [ ] Create `bot/feature.py` module
- [ ] Add states to `config.py` if needed
- [ ] Import + wire in `bot/app.py`
- [ ] Use unique job name: `feature_{chat_id}`
- [ ] HTML format all messages
- [ ] Keep conversation ≤4 steps
- [ ] Reuse existing keyboards/helpers

---

## Code Reuse - Common Helpers

**In `monitor_helpers.py`:**
- `parse_interval(text)` → "5m" → 300 seconds
- `interval_label(seconds)` → 300 → "5м"
- `parse_condition(text)` → "not 422" → ("not", 422)

**In `ticketpro.py`:**
- `_send_event(bot, chat_id, event)` - Send formatted event
- `_build_event_caption(event)` - Format event details

**In `ticketpro_client.py`:**
- `search_events(query, days_ahead)` - Fetch ticketpro.by events

**Keyboards:**
- `DAYS_KB` - Date selection (7/14/30/all)
- `INTERVAL_KB` - Poll interval (30s/1m/5m/15m/1h/custom)
- `_STOP_KB` - Always provide stop button

---

## Conversation Pattern

```python
# In bot/feature.py:

STATES = {
    ASK_THING: [
        CallbackQueryHandler(got_thing_callback, pattern="^thing:"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, got_thing),
    ],
}

async def got_thing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # ALWAYS first
    # ... process

def build_feature_conversation(cancel_handler) -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("feature", feature_cmd)],
        states=STATES,
        fallbacks=[cancel_handler],
    )
```

---

## Job Pattern

```python
async def feature_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    config = job.data
    # ... check, notify, update job.data

# In startup:
context.job_queue.run_repeating(
    feature_job,
    interval=interval,
    first=0,
    chat_id=message.chat_id,
    name=f"feature_{chat_id}",
    data={"query": "...", "interval": interval, "seen": set()},
)

# Stop:
jobs = context.job_queue.get_jobs_by_name(f"feature_{chat_id}")
for job in jobs:
    job.schedule_removal()
```

---

## Messages

Always `parse_mode="HTML"`:

**Status:**
```html
<b>📌 FEATURE NAME</b>
────────────────────────────────────

<b>Query:</b>
Something

<b>Status:</b> ✅ Active
────────────────────────────────────
```

**Confirmation:**
```html
<b>✅ FEATURE STARTED</b>

<b>Parameters:</b>
🔹 Query: value
🔹 Interval: value
```

**Error:**
```html
❌ <b>Error message</b>

<code>/command</code>
```

Always escape user input: `html.escape(user_string)`

---

## Testing

```bash
python -m py_compile bot/feature.py  # Check syntax
pytest -v                             # Run all tests
pytest tests/unit -v                  # Fast unit tests
```

Check:
- Unique job names (no conflicts)
- HTML escaping on user input
- Conversation ≤4 steps
- Stop/status handle "no active" case
- All imports present

---

## File Sizes

Keep modules **< 200 lines** (excluding comments/blank lines):
- `config.py` - Constants only
- `monitor.py` - URL monitoring
- `search_monitor.py` - Search monitoring
- `ticketpro.py` - Search UI
- `ticketpro_client.py` - HTTP / parsing (no Telegram)
- `monitor_helpers.py` - Shared parsing helpers

If a module gets longer, split it.

---

## Common Issues

| Problem | Check |
|---------|-------|
| Button not appearing | Import, add to `_MAIN_KB`, handler pattern |
| Job not running | Unique name, interval > 0, job_queue active |
| Old status data | Update `job.data` during operation |
| Command not recognized | Added to `post_init()`, handler registered |
| Message format wrong | Using `parse_mode="HTML"`, escaping input |
| Too many conversation steps | Reduce to 3-4 steps max |

