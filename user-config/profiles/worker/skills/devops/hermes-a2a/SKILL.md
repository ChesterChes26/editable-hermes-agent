---
name: hermes-a2a
description: "Hermes-to-Hermes communication: API Server, webhooks, shared platforms, terminal spawn, MCP."
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, a2a, multi-agent, interop, api-server, webhooks, messaging]
---

# Hermes A2A (Agent-to-Agent Communication)

How to make two Hermes instances communicate. Hermes has **no built-in A2A protocol** — there is no dedicated agent-to-agent message format, handshake, or discovery mechanism. But five practical paths exist, each with different trade-offs.

## 1. API Server — Direct HTTP (best for "chatbot → another endpoint's Hermes")

The API Server adapter (`gateway/platforms/api_server.py`) exposes an OpenAI-compatible HTTP API on `127.0.0.1:8642` by default.

**Receiver** enables API Server:
```bash
hermes gateway setup        # enable api_server platform
# or manually in config.yaml:
# platforms:
#   api_server:
#     enabled: true
#     extra:
#       host: "0.0.0.0"
#       port: 8642
#       secret: "your-api-key"
hermes gateway run
```

**Sender** (any Hermes, or any HTTP client) calls it:
```bash
curl -X POST http://<receiver-ip>:8642/v1/chat/completions \
  -H "Authorization: Bearer <secret>" \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","messages":[{"role":"user","content":"Hello from another Hermes!"}]}'
```

Key endpoints:
- `POST /v1/chat/completions` — stateless (opt-in session via `X-Hermes-Session-Id`)
- `POST /v1/responses` — stateful via `previous_response_id`
- `POST /v1/runs` — async (returns 202, poll `/v1/runs/{id}/events`)
- `POST /api/sessions/{id}/chat` — persisted session chat
- `GET /health` — liveness probe

Authentication: `API_SERVER_KEY` env var, sent as `Bearer` token.

Network: needs reachable IP. For LAN this works directly; for WAN use a tunnel (ngrok, cloudflared).

## 2. Webhooks — Event-Driven Push

One Hermes exposes a webhook route; the other POSTs to it. The webhook adapter (`gateway/platforms/webhook.py`) fires an agent run on each POST.

**Receiver** creates subscription:
```bash
hermes webhook subscribe greeting \
  --prompt "Incoming A2A message: {message}" \
  --deliver origin
# Returns URL like http://<host>:8644/webhooks/greeting and an HMAC secret
```

**Sender** POSTs:
```bash
curl -X POST http://<receiver>:8644/webhooks/greeting \
  -H "X-Hub-Signature-256: sha256=<signature>" \
  -d '{"message":"Hello!"}'
```

Use `--deliver-only` to skip the LLM entirely — the payload becomes the literal message forwarded to the target platform. Zero token cost.

Security: each subscription gets an auto-generated HMAC-SHA256 secret. Configurable per-subscription with `--secret`.

## 3. Shared Messaging Platform — Via Existing Gateway

If both Hermes instances are connected to the same platform (Telegram, Discord, WeChat, etc.), one can use `send_message` (`tools/send_message_tool.py`, `messaging` toolset) to send to the other's chat ID.

```python
send_message(
    target="telegram:<chat_id>",
    message="Hello from Hermes A!"
)
```

Use `send_message(action='list')` first to discover available targets.

Zero additional configuration. Downside: messages traverse the platform's servers.

## 4. Terminal Spawn (tmux) — Same-Machine Only

Documented in the `hermes-agent` skill. One Hermes spawns another via `terminal` + tmux, then communicates through `send-keys` / `capture-pane`.

```bash
# Start agent B
tmux new-session -d -s agent-b -x 120 -y 40 'hermes'
sleep 8
# Send message
tmux send-keys -t agent-b 'Hello from agent A!' Enter
# Read response
sleep 20
tmux capture-pane -t agent-b -p | tail -30
```

Fragile: response parsing requires regex, and prompt_toolkit output is messy. Prefer API Server even on same machine.

## 5. MCP — NOT for A2A Conversation (Messaging Channel Bridge Only)

`hermes mcp serve` (source: `mcp_serve.py`, line 3: "expose messaging conversations as MCP tools") runs Hermes as an MCP **tool server**, not a conversational agent. The 10 exposed tools are messaging channel management:

| Tool | What it does |
|------|-------------|
| `conversations_list` | List active sessions across platforms |
| `conversation_get` | Get session metadata |
| `messages_read` | Read message history from a session |
| `messages_send` | Send a message to a platform target |
| `attachments_fetch` | List non-text attachments for a message |
| `events_poll` / `events_wait` | Poll/wait for new gateway events |
| `channels_list` | List available platform channels |
| `permissions_list_open` / `permissions_respond` | Manage pending approval requests |

**None of these tools trigger an agent reasoning loop.** They are data-channel operations — read messages, send messages, list sessions. Another Hermes connecting via `hermes mcp add` can read/send messages *through* the server's platforms, but cannot have a conversation with the server's LLM agent.

```bash
# Receiver (exposes messaging management, NOT agent chat)
hermes mcp serve --port 8742
# Sender (can call messages_send, messages_read, etc. — not chat)
hermes mcp add remote-hermes --url http://localhost:8742
```

Use MCP when an external agent needs to operate Hermes's messaging channels (read chat history, send notifications to users). Not for Hermes-to-Hermes dialogue.

## Decision Table

| Path | Latency | Network | Bidirectional | Configuration | Best For |
|------|---------|---------|---------------|---------------|----------|
| API Server | Low | LAN/WAN | Yes | Medium | Direct chat between instances |
| Webhooks | Low | WAN | One-way* | Low | Notifications, triggers |
| Shared Platform | Medium | Any | Yes | Zero | Casual interop |
| Terminal Spawn | Low | Same host | Yes | Medium | Local multi-agent |
| MCP | Low | LAN/WAN | Client-Server | Medium | Messaging channel operation (not conversation) |

*Webhooks can be made bidirectional by creating subscriptions on both sides.

## Async Chatbot Architecture (Full Duplex — Both Sides via Chatbot)

When the user interacts through a chatbot (WeChat/Telegram/etc.) and both Hermes instances need independent reasoning in sequence:

```
User → chatbot → Hermes-A gateway → agent loop ①
                                        ├─ curl B:8643/v1/chat/completions
                                        └─ reply to user: "我问了B，稍等..."

B agent loop ② completes → curl A:8642/v1/chat/completions
                                        ↓
                                A agent loop ③ starts
                                        ├─ "B回复了..."
                                        └─ send_message(weixin:<id>, "...") → User
```

Three independent agent loops. **Both Hermes instances need API Server enabled:**

| Component | What it needs | Why |
|-----------|--------------|-----|
| Hermes-A | gateway + API Server | chatbot entry + receiving B's callback |
| Hermes-B | API Server | receiving A's initial query |

B does not need a messaging platform if it only talks to A via API.

### Critical: callback must use send_message

When B's curl triggers A's agent loop ③ through the API Server, the loop has no inherent connection to the original user's chat. The agent MUST explicitly call `send_message` to push the result back to the user's chatbot. Without this, the response goes nowhere.

```python
# Inside A's agent loop ③
send_message(
    target="weixin:72fc9745a445@im.bot",
    message="B的回复：..."
)
```

### Sync vs Async: when one API Server suffices

For simple request-response where A waits for B's answer:

```
A agent loop → curl B:8643 → B reasons → HTTP response body = B's answer → A resumes
```

**One API Server (B only).** The curl is synchronous — A's terminal tool output captures B's response, and A's agent loop continues reasoning in the same turn. Only one agent loop needed. Use this when A needs B's answer before replying to the user.

## Reference Files

- `references/code-locations.md` — precise file paths, line numbers, and config keys for each A2A mechanism
- `references/corrupted-token-fix.md` — step-by-step fix when a memory-stored API token gets corrupted and the memory tool fails to match

## Pitfalls

- **No built-in A2A protocol.** A grep of the codebase for `a2a`, `agent_to_agent`, or `inter.agent` finds only a skill-tag extraction keyword in `website/scripts/extract-skills.py` — no functional code.
- **API Server needs explicit gateway startup.** It's not a standalone server; the gateway process must be running.
- **Webhook HMAC is mandatory for security.** Don't skip it, especially on exposed endpoints.
- **Network reachability is the hard part.** For WAN communication, use a tunnel (ngrok, cloudflared) or a VPS with a public IP. Hermes doesn't include a tunnel client.
- **Rate-limiting and auth are up to you.** API Server has basic Bearer auth; webhooks have HMAC. Neither includes rate-limiting. Add a reverse proxy (nginx, Caddy) in production.
- **Memory-stored API tokens can be corrupted.** When an agent stores a callback Bearer token in its persistent memory, the text may get whitespace inserted by formatting/truncation (e.g. `"abcd efgh"` instead of `"abcdefgh"`). If a callback returns 401 `invalid_api_key`, do NOT retry with the same token — read `API_SERVER_KEY` from `~/.hermes/.env` (or `%LOCALAPPDATA%/hermes/.env` on Windows) as the source of truth. The memory entry is a convenience pointer, not authoritative.\n- **Memory tool may fail silently when fixing corrupted tokens.** The `memory` tool's `old_text` matching looks at the stored file, but the agent sees the *context-injected* version which may differ (e.g. context shows the corrupted key, file has an indirect reference to `.env`). If `memory` returns `No entry matched` repeatedly, abandon it and edit the file directly at `%LOCALAPPDATA%/hermes/profiles/<profile>/memories/MEMORY.md`. Use `write_file` or `patch` on that path.\n- **API key display sanitization.** `read_file` and `search_files` replace long tokens with `...` in their output — this is display-only, not what's on disk. To verify a key was written correctly, search for substrings of the token (e.g. `tnjIud00Fc` or the absence of a known-bad space like `HLDk AFk8`) rather than expecting the full key in tool output.\n- **Identity entry format.** The Hermes-B memory entry should store the callback URL, auth header, and a curl skeleton so the agent can callback without guessing the payload shape. The token can be abbreviated (e.g. `tnjIud...VRM`) since the authoritative source is `.env`.
- **Include `model` in the JSON payload.** The API Server expects a `model` field. Without it, requests may fail silently or route incorrectly. Use the model name from the receiver's config (e.g. `"deepseek-v4-pro"`).
