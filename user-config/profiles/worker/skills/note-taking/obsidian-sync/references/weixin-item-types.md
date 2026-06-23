# WeChat iLink Message Item Types

The WeChat adapter (`gateway/platforms/weixin.py`) handles iLink protocol
message items. Each message has an `item_list` of typed items.

## Currently Supported Types

| Constant | Value | WeChat Feature | Handler |
|----------|-------|---------------|---------|
| `ITEM_TEXT` | 1 | 文字消息 | `_extract_text()` → text content |
| `ITEM_IMAGE` | 2 | 图片 | `_collect_media()` → download + cache |
| `ITEM_VOICE` | 3 | 语音 | `_collect_media()` + `_extract_text()` fallback |
| `ITEM_FILE` | 4 | 文件 | `_collect_media()` → download |
| `ITEM_VIDEO` | 5 | 视频 | `_collect_media()` → download |
| `ITEM_RECORD` | 6 | 合并转发聊天记录 | `_extract_text()` → recursive text extraction |
| `ITEM_APPMSG` | 7 | 分享链接/文章/小程序 | `_extract_text()` + `_collect_media()` (thumbnail) |
| `ITEM_NOTE` | 8 | 收藏/笔记 | `_extract_text()` → title + content |

## Item Data Structures

### ITEM_APPMSG (forwarded link)

```json
{
  "type": 7,
  "appmsg_item": {
    "title": "Article Title",
    "desc": "Description text",
    "url": "https://...",
    "thumburl": "https://... (remote thumbnail URL)"
  }
}
```

Extracted as: `[分享链接: Title]\nDescription\n🔗 URL`

Thumbnail is downloaded via `_download_bytes()` and cached with
`cache_image_from_bytes()`.

### ITEM_RECORD (merged forward / chat history)

```json
{
  "type": 6,
  "record_item": {
    "title": "Chat History Title",
    "data": {
      "item_list": [
        {"type": 1, "text_item": {"text": "..."}},
        ...
      ]
    }
  }
}
```

Extracted recursively: `[聊天记录: Title]\n<recursively extracted text from nested items>`

### ITEM_NOTE (favorite / note)

```json
{
  "type": 8,
  "note_item": {
    "title": "Note Title",
    "content": "Note body text"
  }
}
```

Extracted as: `[笔记: Title]\nContent`

## Code Locations

- Constants: `weixin.py` line ~137-144
- `_extract_text()`: line ~944 (handles TEXT, APPMSG, RECORD, NOTE; VOICE fallback)
- `_collect_media()`: line ~1609 (handles IMAGE, VIDEO, FILE, VOICE, APPMSG thumbnail)
- `_download_appmsg_thumbnail()`: line ~1636 (new, for APPMSG thumbnails)
- Reply/ref handling: line ~952 (ref_type set includes APPMSG for media-like replies)

## Pitfalls

- **Type numbers are guesswork.** These (6, 7, 8) are based on common WeChat
  protocol conventions. If a specific forwarded content type is NOT captured,
  add a debug log in `_process_message()` to dump `item.get("type")` for
  unknown types, then add the constant and handler.

- **RECORD nested media is NOT downloaded.** Only text is recursively
  extracted. Downloading all images from nested forwarded conversations
  would be slow and potentially expensive. If needed, add recursive
  `_collect_media()` for record items.

- **Note item structure may vary.** The `note_item.content` and
  `note_item.text` fields are tried in order. If notes come through
  empty, log the raw item structure to discover the actual field names.
