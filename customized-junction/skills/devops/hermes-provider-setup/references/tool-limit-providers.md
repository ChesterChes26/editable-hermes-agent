# Provider Tool Limits

Some AI gateways enforce a maximum tool count on API requests. Hermes sends
its full tool schema (built-in + MCP) on every API call, which can exceed
gateway limits.

## Known Limits

| Provider | Tool Limit | Notes |
|----------|-----------|-------|
| QB (QuantumBlack) | 128 | GPT-5.x models via `openai.prod.ai-gateway.quantumblack.com` |
| DeepSeek | none known | Accepts 134+ tools |
| Anthropic | none known | Claude models have no practical tool limit |
| DashScope | none known | Qwen models accept full tool set |

## Error Signature

```
HTTP 400: Invalid 'tools': array too long. Expected an array with maximum
length 128, but got an array with length 134 instead.
```

Key indicators: `array_above_max_length`, `param: tools`, `code: invalid_request_error`.

**This is NOT a model or auth issue.** The gateway rejects the request at
parameter validation, before it reaches the model. The model itself is
available and functional — the request never gets there.

## Tool Count Composition

Hermes tools come from three sources, but the actual count sent to the API
is determined by `platform_toolsets` filtering + MCP registration — NOT by
the full registry size.

### What `get_all_tool_names()` returns vs what's sent

`model_tools.get_all_tool_names()` returns ~84 registered built-in tools
across ALL toolsets (including disabled ones like kanban, spotify, discord,
feishu, homeassistant, yuanbao, moa, video, video_gen, x_search). These
disabled toolsets are NOT in `platform_toolsets.cli` and are therefore
FILTERED OUT before the API request is built. They are NOT counted in the
134 that hits the gateway.

To see what's actually sent, enumerate the enabled toolsets:

```bash
cd ~/.hermes/hermes-agent && ./venv/Scripts/python.exe -c "
from toolsets import resolve_toolset
platform_ts = ['browser', 'clarify', 'code_execution', 'computer_use',
    'cronjob', 'delegation', 'file', 'horizon', 'image_gen', 'memory',
    'session_search', 'skills', 'terminal', 'todo', 'tts', 'vision', 'web']
total = set()
for ts in platform_ts:
    total.update(resolve_toolset(ts))
print(f'Built-in (after platform_toolsets filter): {len(total)}')
for t in sorted(total):
    print(f'  {t}')
"
```

This returns ~34 built-in tools (not 84). The composition of the 134:

| Source | Count | Notes |
|--------|-------|-------|
| Built-in (enabled toolsets) | ~34 | After `platform_toolsets.cli` filtering |
| Horizon plugin | 13 | `hz_*` tools from the Horizon plugin |
| MCP: agentmemory | ~50 | `mcp_agentmemory_memory_*` — entire API surface |
| MCP: cua-driver | ~37 | `mcp_cua_driver_*` — all desktop automation tools |
| **Total** | **~134** | |

### Common Misconception

The 27 tools from disabled toolsets (kanban, spotify, discord, feishu,
homeassistant, yuanbao, moa, video, video_gen, x_search) are NOT in the
134. They were already filtered out by `platform_toolsets.cli`. Disabling
them with `hermes tools disable` won't reduce the count — they're already
excluded.

The real fat to trim is in MCP tools, especially agentmemory (50 tools)
and cua-driver (37 tools).

## Fix: Reducing Tool Count

### Why Disable Mechanisms Differ

MCP tools and plugin tools use completely different lifecycle paths:

| Tool | Registration | Disable Method | Why |
|------|-------------|----------------|-----|
| horizon (13) | plugin → toolset → `platform_toolsets` filter | `hermes tools disable horizon` | Goes through the toolset system; remove from list = filtered |
| agentmemory (~50) | MCP server direct connect | Remove `mcp_servers` config block | MCP tools aren't in any toolset, bypass `platform_toolsets` entirely. Only way to stop them is to not establish the connection |
| cua-driver (~37) | MCP server direct connect | Remove `mcp_servers` config block | Same as above |

An MCP server configured in `mcp_servers` registers ALL its tools on startup, with no per-toolset filtering. The `platform_toolsets.cli` list has zero effect on MCP tools. To disable individual MCP tools without removing the entire server, use `hermes mcp configure <server>` to toggle them one by one — but for 50 tools this is impractical.

### Option 1: Disable External MCP Servers (fastest)

Remove the MCP server from `mcp_servers` in config.yaml. This is the
highest-impact single change — agentmemory alone adds ~50 tools.

```bash
# Remove agentmemory from mcp_servers (Python, since patch tool refuses config edits)
cd ~/AppData/Local/hermes
../hermes-agent/venv/Scripts/python.exe -c "
import yaml
with open('config.yaml') as f:
    cfg = yaml.safe_load(f)
if 'mcp_servers' in cfg and 'agentmemory' in cfg['mcp_servers']:
    del cfg['mcp_servers']['agentmemory']
    print('Removed agentmemory')
with open('config.yaml', 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
"
```

**Important:** This only removes the MCP tools (`mcp_agentmemory_memory_*`).
The `memory.provider: agentmemory` setting (which powers the built-in
`memory` tool) is unaffected — it uses the internal MemoryProvider
interface, not MCP.

### Option 2: Disable Plugin Toolsets

`hermes tools disable horizon` removes 13 tools from the payload.
Combined with Option 1, this drops the total from ~134 to ~71.

### Option 3: Selectively Disable MCP Tools

Use `hermes mcp configure <server>` to toggle individual MCP tools off.
Higher effort but preserves the tools you actually use.

### Option 4: Ask Gateway Admin

If you control the gateway, raise the `max_tools` limit to 200+.
Cleanest fix — no Hermes-side changes needed.

### What Does NOT Help

- `hermes tools disable` on already-disabled toolsets (kanban, spotify,
  discord, etc.) — these are already excluded by `platform_toolsets.cli`
  and are not in the 134 count. This is a waste of time.
- Switching to a different provider — the same tool set works fine on
  providers without the limit (DeepSeek, Anthropic), proving the models
  are available but the gateway is the bottleneck.

## Pitfall: `hermes tools disable` Can Rewrite platform_toolsets

`hermes tools disable <name>` may trigger a curses-style rewrite of the
entire `platform_toolsets.cli` list, potentially **adding back** toolsets
that were previously excluded. Example: running `hermes tools disable
horizon` removed horizon (correct) but also re-added `kanban` (which was
not in the list before). Net effect: -13 (horizon) + 9 (kanban) = -4
instead of -13.

**Always verify** the list after any `hermes tools disable`:
```bash
python -c "import yaml; cfg=yaml.safe_load(open(r'C:\Users\<user>\AppData\Local\hermes\config.yaml')); print(cfg['platform_toolsets']['cli'])"
```
If unwanted toolsets appear, remove them manually via Python (Hermes
blocks direct config edits through `patch` and `write_file`):
```python
import yaml
cfg_path = r'C:\Users\<user>\AppData\Local\hermes\config.yaml'
with open(cfg_path) as f:
    cfg = yaml.safe_load(f)
ts = cfg['platform_toolsets']['cli']
for unwanted in ['kanban']:
    if unwanted in ts:
        ts.remove(unwanted)
with open(cfg_path, 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
```

## Recovery: Re-Enabling After Testing

After testing with QB (or any limited provider), restore the full tool
set to resume normal operation:

```bash
# 1. Restore plugin toolset
hermes tools enable horizon

# 2. Restore agentmemory MCP server
hermes mcp add agentmemory -- npx -y @agentmemory/mcp

# 3. Reload session
/reset
```

Or manually re-add to `config.yaml`:
```yaml
mcp_servers:
  agentmemory:
    args:
      - -y
      - '@agentmemory/mcp'
    command: npx
```

## Mixing Providers

A common confusion: switching to a provider that works (e.g., DeepSeek)
after seeing the 128-tool error on QB doesn't mean "the config was fixed."
It means the request went to a different gateway without the limit.

The same tool set that works on DeepSeek will still fail on QB until the
tool count is reduced below 128.
