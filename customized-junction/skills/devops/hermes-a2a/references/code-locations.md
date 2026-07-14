# Hermes A2A — Code Locations

Precise source locations for each A2A communication path. These were found by
tracing the gateway platform adapters and tool implementations. Re-verify with
`search_files` if the codebase has drifted.

## API Server

- **Adapter:** `gateway/platforms/api_server.py` (~4322 lines)
- **Default host/port:** `127.0.0.1:8642` (lines 88-89)
- **Auth:** `API_SERVER_KEY` env var, with config override `platforms.api_server.extra.key`. Source at line 750: `self._api_key = extra.get("key", os.getenv("API_SERVER_KEY", ""))`. Config `key` takes priority over env var. Connect refuses to start without a key (line 4223).
- **Key endpoints:**
  - `POST /v1/chat/completions` — stateless chat, OpenAI format
  - `POST /v1/responses` — stateful, `previous_response_id` chaining
  - `POST /v1/runs` — async execution (202, poll `/v1/runs/{id}/events`)
  - `POST /api/sessions/{id}/chat` — persisted session
  - `GET /health` — liveness
  - `GET /health/detailed` — rich status for dashboard probing
- **Enabling:** `hermes gateway setup` → enable `api_server` platform, or config:
  ```yaml
  platforms:
    api_server:
      enabled: true
      extra:
        host: "0.0.0.0"
        port: 8642
        secret: "your-key"
  ```

## Webhooks

- **Adapter:** `gateway/platforms/webhook.py`
- **Subscription storage:** `~/.hermes/webhook_subscriptions.json`
- **Default port:** `8644` (configurable via `WEBHOOK_PORT`)
- **Auth:** HMAC-SHA256 per subscription (auto-generated or `--secret`)
- **CLI:** `hermes webhook subscribe/list/remove/test`
- **Hot-reload:** webhook adapter re-reads subscriptions file on each request (mtime-gated)
- **Prompt templating:** `{dot.notation}` for nested JSON fields
- **`--deliver-only` mode:** skips LLM, forwards rendered prompt as literal message
- **Reference doc:** `skill_view(name="hermes-agent", file_path="references/webhooks.md")`

## Send Message (Cross-Platform)

- **Tool:** `tools/send_message_tool.py` (~1900 lines)
- **Toolset:** `messaging`
- **Gate:** `_check_send_message()` — requires gateway running (always available on messaging platforms)
- **Key function:** `send_message_tool(args, **kw)` at line 174
- **Target discovery:** `send_message(action='list')` returns available targets
- **Supported platforms for media:** telegram, discord, matrix, weixin, signal, yuanbao, feishu (line 890)
- **Registry:** `registry.register(name="send_message", toolset="messaging", ...)` at line 1905

## Gateway Hooks

- **Skill:** `skill_view(name="hermes-hooks")`
- **Hook dir:** `~/.hermes/hooks/<name>/` containing `HOOK.yaml` + `handler.py`
- **Events:** `agent:start`, `agent:end`, `agent:step`, `session:start`, `session:end`, `command:*`, `gateway:startup`
- **Context:** platform, user_id, chat_id, session_id, message (truncated to 500 chars)
- **Limitation:** `media_urls` not included in hook context (needs patch to `gateway/run.py`)

## MCP

- **Server source:** `mcp_serve.py` (897 lines) — "expose messaging conversations as MCP tools" (line 3)
- **Exposed tools (not agent reasoning tools — messaging channel management only):**
  - `conversations_list` (line 472) — list active sessions
  - `conversation_get` (line 529) — session metadata
  - `messages_read` (line 562) — read message history
  - `messages_send` (line 734) — send to a platform target
  - `attachments_fetch` (line 619) — list non-text attachments
  - `events_poll` / `events_wait` (line ~670) — event streaming
  - `channels_list` — available platform channels
  - `permissions_list_open` / `permissions_respond` — approval management
- **No agent reasoning tool exposed.** No `chat`, `prompt`, `run_agent`, or equivalent tool exists. The server provides data-channel operations only.
- **CLI entry:** `hermes mcp serve` → dispatches to `run_mcp_server()` (line 866)
- **Dispatch:** `hermes_cli/mcp_config.py` line 858-860: `from mcp_serve import run_mcp_server`
- **Client:** `hermes mcp add <name> --url <url>` — connects to MCP server
- **Client tool implementation:** `tools/mcp_tool.py` (~2800 lines)

## Terminal Spawn (tmux)

- **Documented in:** `skill_view(name="hermes-agent")` under "Spawning Additional Hermes Instances"
- **Flags:** `-w` (worktree isolation), `--resume`, `--continue`, `-s` (preload skills)
- **One-shot:** `hermes chat -q "prompt"` (non-interactive, no PTY needed)

## What's Missing (No A2A Protocol)

A grep for `a2a`, `agent_to_agent`, `inter.agent`, or `hermes.*hermes.*communicat` across the
entire codebase returns zero functional matches. The only hit is:
- `website/scripts/extract-skills.py` line 526: `"a2a"` appears in a keyword extraction list

There is no dedicated A2A protocol handler, handshake, discovery mechanism,
or message format anywhere in the codebase.
