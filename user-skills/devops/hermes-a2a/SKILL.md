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

### Critical: callback must carry user identity

When B's curl triggers A's agent loop ③ through the API Server, the new agent loop has no inherent connection to the original user's chat. The loop MUST know which user to reply to. Solution: **pass the user ID through the entire chain.**

**Message format (A → B):**
```
[CALLER: hermes-a] USER: <platform>:<user_id> TASK: <description>
```
Example: `[CALLER: hermes-a] USER: weixin:o9cq809tH14...@im.wechat TASK: 分析这份财报`

**Callback format (B → A):**
```
[CALLER: hermes-b] USER: <platform>:<user_id> RESULT: <result>
```

**A's callback handler in SOUL.md:**
```markdown
## Handling B's callback
When API Server receives [CALLER: hermes-b] USER: <id> RESULT: <result>:
→ send_message(target="<id>", message="<result>")
```

Without the USER field, the callback agent loop has no way to know which WeChat/QQ user to push the result to. The response evaporates.

### Sync vs Async: when one API Server suffices

For simple request-response where A waits for B's answer:

```
A agent loop → curl B:8643 → B reasons → HTTP response body = B's answer → A resumes
```

**One API Server (B only).** The curl is synchronous — A's terminal tool output captures B's response, and A's agent loop continues reasoning in the same turn. Only one agent loop needed. Use this when A needs B's answer before replying to the user.

## Reference Files

- `references/code-locations.md` — precise file paths, line numbers, and config keys for each A2A mechanism

## Profile-Isolated API Keys

Each Hermes profile has its own `.env` file with its own `API_SERVER_KEY`. When running two Hermes instances on the same machine via profiles, each profile's API Server authenticates with its own key. The default profile's key lives in `~/.hermes/.env`; a profile named `worker` uses `~/.hermes/profiles/worker/.env`.

## Verification Recipes

- `references/windows-dual-profile-verification.md` — step-by-step recipe for verifying two Hermes profiles communicating via API Server on the same Windows machine. Includes the Python test pattern that works around secret redaction.

## SOUL.md Writing Conventions for A2A

When writing SOUL.md rules that involve A2A communication, follow these rules to avoid silent breakage from secret redaction:

1. **No bash code blocks with auth headers.** `Authorization: Bearer *** and similar patterns get eaten by `write_file`'s redaction. Use plain language: "Auth: Bearer token from env `VAR_NAME`."
2. **No API keys in SOUL.md at all.** Store them in `.env` (preferred) or the agent's memory (fallback). Reference by env var name.
3. **Keep instructions short and imperative.** "Do X, then Y" not "You should consider doing X because..."
4. **Reference env vars with backtick-quoted names:** `HERMES_B_AUTH`, not `$HERMES_B_AUTH` in bash blocks.
5. **Include exact message format:** `[CALLER: hermes-a] USER: <id> TASK: <task>`. The agent needs a template, not just a description of what the format should be.

## Caller Whitelist (Soft — SOUL.md/Memory Based)

Hermes API Server identifies callers by a single `API_SERVER_KEY` — no caller identity, no per-key permissions. For multi-caller setups, implement a soft whitelist via the `[CALLER: <name>]` message prefix convention:

**Receiving side (e.g., B):** SOUL.md enforces a whitelist:

```markdown
## Caller Whitelist (MANDATORY — check every request)

Known callers:
- [CALLER: hermes-a] — Hermes-A, trusted.
- [CALLER: hermes-c] — Hermes-C, trusted (future).

If a message lacks a caller tag or has an unknown one, reply:
  "Unknown caller. Rejected." and do NOT process further.
```

**Sending side (e.g., A):** SOUL.md mandates the prefix:

```markdown
## Delegating to Hermes-B

Every message to B MUST start with [CALLER: hermes-a]. Example:
  "[CALLER: hermes-a] Analyze this report. Callback when done."

B will reject messages without this tag.
```

**Callback convention:** Callbacks also carry caller tags. B would prepend `[CALLER: hermes-b]` so A can identify the reply source.

This is an LLM-enforced soft boundary — not a cryptographic guarantee. For hard security, add a reverse proxy with per-caller API keys and IP filtering in front of the API Server.

## Profile Identity — Telling A and B Apart\n\nWhen running multiple profiles on the same machine, CLI sessions and gateway processes can be confusing. Three ways to distinguish:\n\n1. **SOUL.md identity markers** — add a role declaration to each profile's `SOUL.md`. Hot-loaded, no restart needed:\n\n   ```markdown\n   # Hermes-A persona (default profile, C:\\Users\\...\\AppData\\Local\\hermes\\SOUL.md)\n   You are Hermes-A, frontend chatbot gateway (WeChat/QQ). Delegate heavy tasks to Hermes-B.\n\n   # Hermes-B persona (worker profile, ...\\profiles\\worker\\SOUL.md)\n   You are Hermes-B, backend worker node. No chat platforms. Receive tasks via API, callback when done.\n   ```\n\n   Next message after editing, the agent self-identifies. Combined with in-session `/profile`, you always know who you're talking to.\n\n2. **Profile alias** — `hermes profile alias <name>` creates a shortcut command (`worker` = `hermes -p worker`). Each profile gets its own launch command.\n\n3. **`/profile` slash command** — prints active profile name, model, and config path during a session.\n\n## Persistent Callback Config via Memory\n\nFor async A2A where B must autonomously callback to A, B needs to know A's address and API key. Rather than embedding credentials in every request, save them to B's memory once:\n\n```python\n# Send B a one-time config message\nmsg = {\n    \"messages\": [{\"role\": \"user\", \"content\": (\n        \"Remember this permanently: you are Hermes-B. When you complete a task, \"\n        \"callback to Hermes-A at http://127.0.0.1:8642/v1/chat/completions \"\n        f\"with Authorization: Bearer ***\n        \"Save this to your memory now.\"\n    )}]\n}\n# POST to B's API Server: 127.0.0.1:8643\n```\n\nB's agent will call the `memory` tool, persisting the callback info across sessions. Subsequent tasks can simply say \"callback to A when done\" — B already knows how.\n\n## Gateway Process vs CLI Session (Don't Confuse Them)

A common point of confusion: `hermes` (CLI chat session) and `hermes gateway run` (background message listener) are **two independent processes** with different PIDs. Killing one does NOT affect the other.

| | `hermes` (CLI) | `hermes gateway run` (daemon) |
|---|---|---|
| Purpose | One-on-one terminal chat | Listen on WeChat/QQ/API, auto-spawn agent loops |
| Process | Standalone | Standalone (different PID) |
| Stopping | `/exit` or Ctrl+C | Kill process manually (see below) |
| Affected by killing the other? | No — CLI keeps running | No — gateway keeps running |

At any moment you can have all four running simultaneously:
- A's CLI session (talking to the user)
- A's gateway (listening on WeChat/QQ/API :8642)
- B's CLI session (separate terminal)
- B's gateway (listening on API :8643)

When you hear "stop A", clarify whether you mean the CLI session or the gateway process.

### Stopping Gateways on Windows

`hermes gateway stop` only works for gateways installed as Windows services (`hermes gateway install`). For gateways started with `hermes gateway run`, use:

```bash
# Find the PID
netstat -ano | findstr 8642    # A's port
netstat -ano | findstr 8643    # B's port

# Kill (from cmd or PowerShell)
powershell -Command "Stop-Process -Id <PID> -Force"

# Or kill all processes on A2A ports at once
powershell -Command "Get-NetTCPConnection -LocalPort 8642,8643 | Stop-Process -Force"
```

Background Hermes processes spawned by the agent (`terminal(background=true)`) may have stale PIDs when the gateway restarts — always verify with `netstat`, don't trust session-tracked PIDs.

## Profile Isolation at a Glance

When two Hermes profiles run on the same machine, here's what's isolated and what's shared:

| Isolated (profile-specific) | Shared (machine-level) |
|---|---|
| `memory` (persistent notes) | Filesystem (both can read/write `D:/obsidian`, `~/Documents`, etc.) |
| `skills/` (installed skills) | Network stack (same `localhost`, same NIC) |
| `sessions/state.db` (chat history) | OS user/permissions |
| `SOUL.md` (persona) | Installed binaries (`python`, `git`, `curl`) |
| `config.yaml` (settings) | |
| `.env` (API keys, `API_SERVER_KEY`) | |

**Within a single profile, all entries share memory and skills.** CLI, WeChat, QQ, and API Server are all entries to the same agent. A `memory add` done in the CLI is immediately available when the next WeChat message fires an agent loop. This means you can configure A2A credentials via CLI (`memory add` or `.env` edits) and they'll work for WeChat-initiated delegations. Only the conversation session (current chat context) is isolated per entry.

Profiles cloned with `hermes profile create --clone` start identical but diverge immediately. Each gets its own `API_SERVER_KEY` — a profile's key file is the authoritative source, not the cloning parent.

When both profiles use the same LLM provider (e.g., both cloned from a DeepSeek-configured parent), they share the **same API key and rate limit**. To truly separate compute capacity, give the worker profile a different provider/model.

## Pitfalls

- **No built-in A2A protocol.** A grep of the codebase for `a2a`, `agent_to_agent`, or `inter.agent` finds only a skill-tag extraction keyword in `website/scripts/extract-skills.py` — no functional code.
- **API Server needs explicit gateway startup.** It's not a standalone server; the gateway process must be running.
- **Cloned profiles inherit messaging platforms.** `hermes profile create --clone` copies the parent's full config and `.env`, including WeChat/QQ/Telegram platform credentials. A cloned worker will try to connect to those platforms — WeChat will fail with "bot token already in use" (parent holds it), but QQ/Discord will connect successfully if the platform allows multiple sessions. The worker should NOT be on messaging platforms. Fix: after cloning, either remove the platform credentials from the worker's `.env`, or add explicit `enabled: false` under each platform section in its config.yaml.
- **SOUL.md can't hold API keys or auth headers due to secret redaction.** The `write_file` tool redacts `Authorization: Bearer *** patterns in SOUL.md — even when they're env var references like `$HERMES_B_AUTH` in a bash code block, not actual keys. Workarounds: (a) **Preferred:** store the remote key as a `.env` variable (e.g., `HERMES_B_AUTH`) and reference it by name in SOUL.md without bash code blocks — use plain language like "Auth: Bearer token from env `HERMES_B_AUTH`"; (b) fallback: store the key in the agent's memory, but this wastes context tokens. **SOUL.md writing rule:** never put `Authorization: Bearer` in a bash code block; use plain language instructions instead and let the agent construct the curl command.
- **`write_file` secret redaction breaks Python scripts that embed API keys.** When writing a Python script that constructs an `Authorization: Bearer {KEY_B}` header (f-string or concatenation with a variable holding the API key), the `write_file` tool's secret redaction scanner replaces the variable reference with `***`, yielding broken code. Use `execute_code` instead of `write_file` + `terminal` for scripts that need to construct auth headers with API keys. See `references/windows-dual-profile-verification.md` for the working pattern.
- **Webhook HMAC is mandatory for security.** Don't skip it, especially on exposed endpoints.
- **Network reachability is the hard part.** For WAN communication, use a tunnel (ngrok, cloudflared) or a VPS with a public IP. Hermes doesn't include a tunnel client.
- **Rate-limiting and auth are up to you.** API Server has basic Bearer auth; webhooks have HMAC. Neither includes rate-limiting. Add a reverse proxy (nginx, Caddy) in production.
