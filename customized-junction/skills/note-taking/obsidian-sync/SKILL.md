---
name: obsidian-sync
description: Images auto-saved to Obsidian inbox. Text messages saved on-demand to LLM Wiki via numbered selection.
platforms: [windows, linux, macos]
---

# Obsidian Sync — Gateway Message Archival

This skill is auto-loaded for WeChat/QQ sessions. When you receive a message
from these platforms, archive it to the Obsidian vault.

## Vault Path

The Obsidian vault path is set via `OBSIDIAN_VAULT_PATH` env var.
**Current vault:** `D:\obsidian\2026`

Always resolve the actual path from the environment before writing:
- Windows: `$env:OBSIDIAN_VAULT_PATH` or `OBSIDIAN_VAULT_PATH`
- If unset, fall back to `D:\obsidian\2026`

## Workflow — Two-Tier Archival

This skill uses a split strategy:

- **Images/media:** Auto-save immediately. Images are information-rich and can't be
  re-created from text.
- **Text messages:** Do NOT auto-save. When the LLM detects the user's intent to
  end the conversation, summarize into a numbered list and ask the user which
  items to save to the LLM Wiki.

### Tier 0: File Intent Check (on every incoming file/document)

When the user sends a file — any non-image document (CSV, Excel, PDF, Word, text, etc.):

1. **Do NOT auto-parse or auto-save.** First ask:

   ```
   收到文件 [filename]。你想让我：
   1. 解析内容
   2. 仅保存到 Obsidian
   ```

2. Based on the user's response:
   - **解析** → Use the appropriate tool (pymupdf for PDF, pandas for CSV/Excel, etc.), then
     deliver the result. After parsing, optionally offer to save the result.
   - **仅保存** → Copy the file to `{VAULT}/inbox/files/` and append a note to the daily log
     (`{VAULT}/inbox/{YYYY-MM-DD}.md`):
     ```markdown
     ## {HH:MM} — {platform}
     
     [文件] filename.ext
     → 已保存至 inbox/files/filename.ext
     ```

3. Images continue to use Tier 1 (auto-save) — images are always saved automatically.

### Tier 1: Auto-Save Images/Media (on every incoming image)

When the message includes an image, save it IMMEDIATELY:

1. Copy each image to `{VAULT}/inbox/assets/`
   - Windows: `terminal(command="copy '<source>' '<vault>\\inbox\\assets\\<filename>'")`
   - Or use `execute_code` with `shutil.copy2()`

2. Append to the daily note (`{VAULT}/inbox/{YYYY-MM-DD}.md`):
   ```markdown
   ## {HH:MM} — {platform}
   
   [图片]
   
   ![[assets/filename.jpg]]
   > 这是一张包含表格的截图...
   ```
   - `{platform}`: `weixin` or `qqbot`
   - `{HH:MM}`: actual current time in 24-hour format. NEVER use `--:--`.
   - Include vision analysis text below the image (blockquote format) if vision
     was used for the user's request.

3. Do NOT log text messages to inbox — only images.

### Tier 2: On-Demand Knowledge Save (intent-based trigger)

Only trigger when you detect the user's intent to end the current conversation.
This includes but is NOT limited to: "好了", "先这样", "今天就到这里", "差不多了",
"OK 先这样", etc. Use your judgment to recognize the intent, not keyword matching.

Do NOT trigger on turn count or conversation length alone.

When end-of-conversation intent is detected, summarize the conversation into
numbered knowledge points, then ask the user to pick:

```
这次对话中值得保存的内容：

   1. [一句话概括知识点 1]
   2. [一句话概括知识点 2]
   3. [一句话概括知识点 3]
   ...

回复数字选择（如 "1" 或 "1,2,3"），或回复 "全部"
```

**Rules for the numbered list:**
- List EVERY text message the user sent in this conversation, verbatim
- One number per user message, in chronological order
- Do not skip, filter, summarize, or judge — include all text messages
- Do not include your own replies
- EXCLUDE the last message if it is the end-of-conversation signal itself
- EXCLUDE file attachments and images — only text messages appear in the list
- Your job is purely mechanical: segment by message, number them, present them

**When the user replies with numbers (e.g. "1,3,5" or "全部"):**
1. Parse the selection — `"1,3,5"` means items 1, 3, and 5. `"全部"` means all.
2. For multi-item selections (2+ items), use LLM judgment to synthesize related
   items into coherent wiki pages rather than creating one page per number.
   For example, if items 1, 3, and 5 all relate to "Agent Tool Architecture",
   create ONE concept page that covers all three angles.
3. Save to the LLM Wiki:
   - Entities → `entities/`
   - Concepts → `concepts/`
   - Comparisons → `comparisons/`
   - Queries → `queries/`
4. Update wiki `index.md` and `log.md`.
5. Confirm what was saved and where.

## Verification

After saving, confirm the file was written by checking its existence with
`search_files` or stat. If the vault path doesn't exist, log a warning but
continue — don't block the user's response.

## Pitfalls

### Skill changes need /new in gateway sessions

When this skill's content is updated on disk, existing WeChat/QQ sessions do NOT
automatically pick up the changes. The skill text is injected into the system
prompt at session start. A gateway restart does NOT fix this — the resumed
session still has the old system prompt.

**Fix:** After updating this skill, have the user send `/new` in WeChat/QQ to
start a fresh session with the updated skill.

### WeChat DM pairing

When `WEIXIN_DM_POLICY=pairing` (the default for this setup), new WeChat
users are NOT automatically allowed. They must be approved first:

```
hermes pairing approve weixin <pairing-code>
```

The pairing code is shown to the user in WeChat when they first message the
bot. Messages from unapproved users are silently rejected with a
"Unauthorized user" warning in the gateway log.

### Gateway restart can break WeChat long-poll

Restarting the gateway (e.g. after code changes) can trigger iLink rate
limiting (`sendmessage rate limited; cooldown active`). This can cause the
WeChat adapter to disconnect and, on reconnect, the long-poll may silently
stop delivering inbound messages even though `gateway_state.json` shows
"connected".

**Symptom:** gateway log shows no new `inbound from=...` entries after
restart, despite user sending messages.

**Fix:** Do a clean stop → wait → start cycle. After restart, send a test
message and verify it appears in the gateway log (`grep "inbound"
~/.hermes/logs/gateway.log`).

## Setup Reference

For the auto-load mechanism that injects this skill on WeChat/QQ sessions,
see `references/auto-load-setup.md`.

For the WeChat iLink item type constants and data structures that enable
forwarded link/record/note support, see `references/weixin-item-types.md`.

For the LLM Wiki integration — directory layout, frontmatter template,
tag taxonomy, and the numbered-selection-to-wiki-page workflow —
see `references/wiki-integration.md`.
