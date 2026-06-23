---
name: hermes-hooks
description: Create and manage Hermes gateway event hooks — message processing, external sync, and automation.
platforms: [linux, macos, windows]
---

# Hermes Gateway Hooks

Gateway event hooks let you run custom Python handlers at key lifecycle points —
message arrival, session start/end, agent processing, and slash commands. Use
them to sync messages to external systems (Obsidian, Notion, databases), trigger
notifications, or inject custom logic into the agent pipeline.

## Hook Directory Layout

```
~/.hermes/hooks/<hook-name>/
├── HOOK.yaml       # metadata: name, description, events
└── handler.py      # async def handle(event_type, context)
```

Hooks are auto-discovered on gateway startup. No restart needed for edits if the
hook directory already existed — the gateway picks up file changes on the next
event fire.

## Available Events

| Event | Fires when | Use case |
|-------|-----------|----------|
| `gateway:startup` | Gateway process starts | Init connections, validate state |
| `session:start` | New session created | Logging, analytics |
| `session:end` | Session ends (/new, /reset) | Cleanup, archival |
| `session:reset` | Session reset completed | State reset handlers |
| `agent:start` | Agent begins processing a message | **Sync inbound messages** |
| `agent:step` | Each turn in tool-calling loop | Progress tracking |
| `agent:end` | Agent finishes processing | Sync full conversation |
| `command:*` | Any slash command | Custom slash command handling |

## agent:start Context

Fires when the agent starts processing an inbound message from any platform.

```python
{
    "platform": "weixin",        # platform name
    "user_id": "...",            # sender's platform ID
    "chat_id": "...",            # chat/DM identifier
    "thread_id": "",             # forum topic ID (if applicable)
    "chat_type": "dm",           # "dm" | "group" | "forum"
    "session_id": "...",         # Hermes session ID
    "message": "...",            # inbound text, truncated to 500 chars
}
```

## agent:end Context

Same as `agent:start` plus:

```python
{
    "response": "...",           # agent's reply, truncated to 500 chars
}
```

## Creating a Hook

**HOOK.yaml:**
```yaml
name: my-hook
description: Sync WeChat messages to Obsidian
events:
  - agent:start
```

**handler.py:**
```python
import os
from datetime import datetime

async def handle(event_type, context):
    if event_type == "agent:start":
        platform = context.get("platform", "")
        if platform not in ("weixin", "qqbot"):
            return

        vault = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        if not vault:
            return

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_id = context.get("user_id", "unknown")
        message = context.get("message", "")

        note = f"# Inbound {platform} — {ts}\n\n"
        note += f"- **From:** {user_id}\n"
        note += f"- **Session:** {context.get('session_id', '')}\n\n"
        note += f"{message}\n"

        filename = f"Inbox/{ts.replace(':', '-')} - {platform}.md"
        filepath = os.path.join(vault, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(note)
```

## Known Limitation: No media_urls in Hook Context

The `agent:start` hook context does **not** include `media_urls` (local paths to
downloaded images, videos, files). The gateway downloads media from WeChat CDN
before the hook fires, but the paths are not passed to the hook context.

**Workaround for images:** the hook can record a note that media was received,
but cannot copy the image file itself without modifying `gateway/run.py` to
include `media_urls` in the hook context dictionary (around line 8863).

**To add media_urls to the hook context**, patch `gateway/run.py`:

```python
hook_ctx = {
    ...
    "message": message_text[:500],
    "media_urls": getattr(event, "media_urls", None) or [],  # add this line
}
```

## Pitfalls

- **Handler exceptions are swallowed.** Errors are logged but never block the
  agent pipeline. Always add try/except in handlers for critical operations.
- **Message is truncated to 500 chars.** For long messages, use `session_id` to
  look up the full session log if needed.
- **Hooks run in the gateway process.** Don't block the event loop with
  synchronous I/O — use async libraries (aiofiles) or keep handlers fast.
- **Handler module is loaded once** at discovery time. Changes to handler.py
  require a gateway restart to take effect if the hook directory is new;
  existing directories auto-reload on each event.
- **Gateway PATH may not include user-installed tools.** The gateway process inherits its parent's environment, which on some platforms (especially Windows) may lack `npx`, `python`, or other CLI tools that are available in interactive shells. When spawning subprocesses from hooks, use absolute paths (e.g. `C:\Program Files\nodejs\npx.cmd`) or explicitly extend `PATH` in the subprocess environment.

## Verification

After creating a hook, restart the gateway and watch logs:

```bash
hermes gateway restart
tail -f ~/.hermes/logs/gateway.log | grep "\[hooks\]"
```

You should see:
```
[hooks] Loaded hook 'my-hook' for events: ['agent:start']
```

## Reference Files

- `references/wechat-qq-migration.md` — WeChat & QQ Bot migration checklist
  (env vars, credential files, verification steps).
- `templates/obsidian-inbox-hook.md` — Ready-to-use hook template for syncing
  WeChat/QQ messages to an Obsidian vault as timestamped notes.
