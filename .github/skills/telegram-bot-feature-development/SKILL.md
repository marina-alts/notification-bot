---
name: telegram-bot-feature-development
description: "Use when: adding a new feature to a Telegram bot project. Follows a systematic workflow for requirements gathering, architecture design, implementation, testing, UI/UX improvement, and documentation."
---

# Telegram Bot Feature Development

A 7-step workflow for building new Telegram bot features with proper architecture, testing, and UI.

**See `CODE_GUIDELINES.md` for project structure, patterns, and code standards.**

---

## 1. Clarify Requirements

Ask clarifying questions:
- Data persistence? (in-memory, database, file)
- Multiple concurrent instances per user?
- Where in UI? (new button, existing flow)
- Notification style? (batched, individual, real-time)
- Can reuse existing code? (helpers, keyboards, jobs)

---

## 2. Create Implementation Plan

Break into 5-8 tracked tasks using manage_todo_list:

```
1. Create/modify feature module
2. Add conversation states to config.py
3. Integrate into bot/app.py
4. Add status/stop functions
5. Enhance UI & messages
6. Syntax check (get_errors)
7. Document changes
```

Mark items `in-progress` when starting, `completed` immediately when done.

---

## 3. Design Architecture

**For conversation flows:**
- New module: `bot/feature.py`
- States in `config.py`
- Build function at bottom of module

**For background jobs:**
- Async job in feature module
- Register with `job_queue.run_repeating()`
- Unique name: `feature_{chat_id}`

**For menu integration:**
- Import in `app.py`
- Add button to `_MAIN_KB`
- Register handlers in `main()`
- Hook stop/status into `menu_callback()`

---

## 4. Implement Core

Follow patterns in CODE_GUIDELINES.md and existing modules (`monitor.py`, `search_monitor.py`). Reuse:
- Helpers: `parse_interval()`, `interval_label()`
- Functions: `search_events()`, `_send_event()`
- Keyboards: `DAYS_KB`, `INTERVAL_KB`, `_STOP_KB`

---

## 5. Test for Errors

```bash
python -m py_compile bot/feature.py
```

Check:
- [ ] All imports present
- [ ] Job names unique
- [ ] Conversation flow sensible (3-4 steps max)
- [ ] Stop/status handle "no job" case
- [ ] HTML escaping for user input

---

## 6. Enhance UI

Template:
```html
<b>📌 FEATURE NAME</b>
────────────────────────────────────

<b>Parameter:</b>
Value

<b>Status:</b> ✅ Active
────────────────────────────────────
```

- [ ] Consistent formatting (bold, separators)
- [ ] Clear parameter labels
- [ ] Status indicator
- [ ] Helpful errors with suggestions
- [ ] Good button organization

---

## 7. Document

Save session notes with:
- Files created/modified
- Key design decisions
- Reused components
- Non-obvious patterns

---

## Checklist

- [ ] All config states added
- [ ] Job naming: `feature_{chat_id}`
- [ ] App wiring complete
- [ ] Syntax errors checked
- [ ] HTML formatting consistent
- [ ] 3-4 steps max in conversation
- [ ] Status/stop work with no active job

---

## Common Mistakes

| Issue | Fix |
|-------|-----|
| Job names conflict | Use `feature_{chat_id}` |
| Button not appearing | Check: import, MAIN_KB, handler pattern |
| Old data in status | Update `job.data` during operation |
| Too many steps | Limit to 3-4 steps |
| No feedback on start | Send confirmation with parameters |
| State not reset | Clear user_data between runs |

