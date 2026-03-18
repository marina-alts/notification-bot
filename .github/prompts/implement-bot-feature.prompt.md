---
name: implement-bot-feature
description: "Use when: you have a feature idea for the Telegram bot and need to implement it following best practices"
---

# Implement Telegram Bot Feature

Quickly implement a new feature using proven patterns from the project.

## Quick Start

1. **Understand what's needed** by asking clarifying questions
2. **Plan the implementation** with file structure and todo list
3. **Code it** following the project's patterns
4. **Test** for errors immediately
5. **Polish** the UI and messaging
6. **Ship it** with documentation

---

### Step 1: Clarify Requirements

Answer these key questions:

- **Data Storage:** How long should data persist? (in-memory, database, file)
- **Concurrency:** Can multiple users run this simultaneously?
- **Integration:** Where does this fit in the UI? (new button, existing menu)
- **Notifications:** How should users be notified? (on-demand, batched, real-time)

---

### Step 2: Design & Plan

Identify files to create/modify:

**Create:**
- [ ] New feature module (e.g., `bot/feature_name.py`)

**Modify:**
- [ ] `bot/config.py` - Add conversation states
- [ ] `bot/app.py` - Import, integrate, add menu button

**Plan:**
- Reuse existing: `search_events()`, `_send_event()`, interval helpers
- Job naming: `feature_{chat_id}` (avoid conflicts)
- Conversation states: Keep to 3-4 steps max

---

### Step 3: Implement

Create module following this structure:

```python
# Imports
# Keyboards (reuse existing where possible)
# Background job function (if polling)
# Conversation handlers (step 1, 2, 3...)
# Confirmation + startup function
# Stop/status functions
# Build conversation function
```

---

### Step 4: Quick Test

```python
# Check for errors
python -m py_compile bot/new_feature.py

# Run the app
python monitor_bot.py
```

---

### Step 5: Enhance UI

- [ ] Organize buttons logically in main menu
- [ ] Add visual separators to status messages: `{'─' * 40}`
- [ ] Use bold headers: `<b>FEATURE NAME</b>`
- [ ] Show status indicator: `✅ Active`
- [ ] Provide helpful error messages with commands

---

### Step 6: Document

Save session notes with:
- Files created and why
- Files modified and what changed
- Key design decisions
- Reused components

---

## Remember

✅ Unique job names prevent conflicts  
✅ Reuse existing helpers and keyboards  
✅ Keep conversation flows short (3-4 steps)  
✅ Consistent message formatting  
✅ Test early, polish late  

