# Fixing a Corrupted API Key in Memory

When Hermes-A reports that Hermes-B's callback token is corrupted (e.g. space inserted in the middle), and the `memory` tool fails to match the entry.

## Why the memory tool fails

The agent sees the context-injected version of memory, which may show the corrupted key. But the actual `MEMORY.md` file may have a different version — e.g. an indirect reference to `.env` instead of the raw key. `memory` tool's `old_text` matching operates against the file, not the context injection. Repeated `No entry matched` errors mean you should switch to direct file editing.

## Direct fix procedure

1. Locate the memory file:
   - Windows: `%LOCALAPPDATA%/hermes/profiles/<profile>/memories/MEMORY.md`
   - Example: `C:/Users/chester.chen/AppData/Local/hermes/profiles/worker/memories/MEMORY.md`

2. Read the identity line to see what's actually there:
   ```
   read_file offset=8 limit=3
   ```

3. Use `write_file` or `patch` to update the identity entry with the corrected key (no spaces).

4. Verify using substring search, NOT by reading back the full line:
   - `search_files pattern="tnjIud00Fc"` — should return 1 match if full key is present
   - `search_files pattern="HLDk AFk8"` — should return 0 matches (the space was the bug)
   - Do NOT search for the full key — `read_file` and `search_files` sanitize long tokens in output with `...`.

## Identity entry format for Hermes-B

The memory entry should include the callback URL, auth header, and curl skeleton:

```
identity: I am Hermes-B, a backend worker agent. Hermes-A delegates tasks to me; I execute them and report back. Callback: POST http://127.0.0.1:8642/v1/chat/completions, Header: Authorization: Bearer <key>. curl skeleton: curl -s -X POST http://127.0.0.1:8642/v1/chat/completions -H 'Content-Type: application/json' -H 'Authorization: Bearer <key>' -d 'JSON_PAYLOAD'
```

The `<key>` should be the full `API_SERVER_KEY` from `%LOCALAPPDATA%/hermes/.env`.

## Python execute_code pattern for write+verify

```python
from hermes_tools import write_file, read_file

full_key = "actual-key-here"

# Build line carefully — avoid embedding variable name inside string literal
identity_line = (
    "identity: I am Hermes-B, a backend worker agent. "
    "Hermes-A delegates tasks to me; I execute them and report back. "
    "Callback: POST http://127.0.0.1:8642/v1/chat/completions, "
    "Header: Authorization: Bearer *** + full_key + ". "  # CONCATENATE properly
    "curl skeleton: curl -s -X POST http://127.0.0.1:8642/v1/chat/completions "
    "-H 'Content-Type: application/json' "
    "-H 'Authorization: Bearer *** + full_key + "' -d 'JSON_PAYLOAD'"
)

# ... build full content, write_file, then verify with substring checks
```

Common mistake: `"Bearer *** + full_key + "` with `+ full_key +` inside the string literal — this writes literal text, not the variable value. Use proper Python concatenation.
