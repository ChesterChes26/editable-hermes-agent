# Auto-Load Skill Setup for WeChat / QQ Bot

How to make Hermes auto-load a skill on every WeChat or QQ Bot session.

## Mechanism

When a message arrives from WeChat/QQ, the platform adapter creates a
`MessageEvent`. If `auto_skill` is set on that event, the gateway injects
the skill's content into the agent's prompt before processing the message.

Both adapters read `auto_skill` from:
1. `config.yaml` → `gateway.platforms.<weixin|qqbot>.extra.auto_skill`
2. Env var `WEIXIN_AUTO_SKILL` / `QQBOT_AUTO_SKILL`
3. Default: `"obsidian-sync"`

## Adapter Patch Recipe

### WeChat (`gateway/platforms/weixin.py`)

**1. Add to `__init__`** (after the existing `extra` reads):

```python
_auto_skill_raw = extra.get("auto_skill") or os.getenv("WEIXIN_AUTO_SKILL")
if _auto_skill_raw is None:
    _auto_skill_raw = "obsidian-sync"
_auto_skill_raw = str(_auto_skill_raw).strip()
self._auto_skill = _auto_skill_raw if _auto_skill_raw else None
```

**2. Add to `MessageEvent(...)` call** (line ~1465):

```python
event = MessageEvent(
    ...,
    auto_skill=self._auto_skill,
)
```

### QQ Bot (`gateway/platforms/qqbot/adapter.py`)

**1. Add to `__init__`** (after group_allow_from):

```python
_auto_skill_raw = extra.get("auto_skill") or os.getenv("QQBOT_AUTO_SKILL")
if _auto_skill_raw is None:
    _auto_skill_raw = "obsidian-sync"
_auto_skill_raw = str(_auto_skill_raw).strip()
self._auto_skill = _auto_skill_raw if _auto_skill_raw else None
```

**2. Add to all 4 `MessageEvent(...)` calls** (DM, group, guild, guild-DM handlers):

```python
event = MessageEvent(
    ...,
    auto_skill=self._auto_skill,
    timestamp=...,
)
```

## Verification

1. Restart gateway: `hermes gateway stop && hermes gateway run`
2. Send a message from WeChat/QQ
3. Check logs: `grep "Auto-loaded skill" ~/.hermes/logs/gateway.log`

## Env Var

```
OBSIDIAN_VAULT_PATH=D:/obsidian/2026
```

The vault must exist with `inbox/` and `inbox/assets/` subdirectories.
