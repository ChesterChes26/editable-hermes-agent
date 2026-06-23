# Obsidian Inbox Hook — Sync WeChat/QQ messages to Obsidian

This hook writes every inbound WeChat or QQ Bot message to an Obsidian vault
as a timestamped markdown note.

## Setup

1. Set `OBSIDIAN_VAULT_PATH` in `~/.hermes/.env`:
   ```
   OBSIDIAN_VAULT_PATH=C:/Users/me/Documents/Obsidian Vault
   ```

2. Create the hook directory and files (see below).

3. Restart the gateway:
   ```bash
   hermes gateway restart
   ```

4. Verify in logs:
   ```bash
   tail -f ~/.hermes/logs/gateway.log | grep "\[hooks\]"
   ```

## Files

### HOOK.yaml

```yaml
name: obsidian-inbox
description: Sync inbound WeChat and QQ Bot messages to Obsidian vault
events:
  - agent:start
```

### handler.py

Uses `aiofiles` for async file I/O to avoid blocking the gateway event loop:

```python
import os
from datetime import datetime, timezone, timedelta

try:
    import aiofiles
    import aiofiles.os as aio_os
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False


PLATFORM_LABELS = {
    "weixin": "微信",
    "qqbot": "QQ",
}


async def handle(event_type, context):
    if event_type != "agent:start":
        return

    platform = context.get("platform", "")
    if platform not in PLATFORM_LABELS:
        return

    vault = os.environ.get("OBSIDIAN_VAULT_PATH", "")
    if not vault:
        return

    user_id = context.get("user_id", "unknown")
    message = context.get("message", "") or "(no text)"
    session_id = context.get("session_id", "")
    chat_type = context.get("chat_type", "")

    # Beijing time
    now = datetime.now(timezone.utc) + timedelta(hours=8)
    ts = now.strftime("%Y-%m-%d %H:%M")
    ts_file = now.strftime("%Y%m%d-%H%M%S")

    label = PLATFORM_LABELS[platform]
    note_lines = [
        f"---",
        f"platform: {platform}",
        f"user_id: {user_id}",
        f"chat_type: {chat_type}",
        f"session_id: {session_id}",
        f"date: {now.strftime('%Y-%m-%d')}",
        f"---",
        f"",
        f"# {label} — {ts}",
        f"",
        f"**From:** `{user_id}`",
        f"",
        f"{message}",
        f"",
    ]
    note = "\n".join(note_lines)

    inbox_dir = os.path.join(vault, "Inbox")
    filename = f"{ts_file} - {label}.md"
    filepath = os.path.join(inbox_dir, filename)

    if HAS_AIOFILES:
        await aio_os.makedirs(inbox_dir, exist_ok=True)
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(note)
    else:
        os.makedirs(inbox_dir, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(note)
```

## Notes

- Without `aiofiles`, falls back to synchronous I/O (OK for low-traffic but may
  block the gateway briefly).
- Images are NOT synced — the hook context lacks `media_urls`. See SKILL.md
  "Known Limitation" section.
- Messages created under `Inbox/` in the vault with YAML frontmatter for
  Dataview queries.
