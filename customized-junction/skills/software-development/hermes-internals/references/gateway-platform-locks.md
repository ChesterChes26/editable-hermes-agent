# Gateway Platform Lock Architecture

## Connection Models

| Platform | Adapter | Inbound Model | Source |
|----------|---------|---------------|--------|
| WeChat (weixin) | `gateway/platforms/weixin.py` | Long-poll `getupdates` | line 7 |
| QQ Bot | `gateway/platforms/qqbot/adapter.py` | WebSocket Gateway | line 4 |

## Platform Lock: Machine-Local Only

Both adapters call `_acquire_platform_lock()` during `connect()`:

- **QQ Bot** — `adapter.py:309`: `_acquire_platform_lock("qqbot-appid", self._app_id, ...)`
- **WeChat** — `weixin.py:1340`: `_acquire_platform_lock('weixin-bot-token', self._token, ...)`

### Implementation

`gateway/status.py:63-69` — lock directory is local filesystem:
```python
def _get_lock_dir() -> Path:
    """Return the machine-local directory for token-scoped gateway locks."""
    override = os.getenv("HERMES_GATEWAY_LOCK_DIR")
    if override:
        return Path(override)
    state_home = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state_home / "hermes" / _LOCKS_DIRNAME
```

`gateway/status.py:582-587` — explicitly scoped as machine-local:
```python
def acquire_scoped_lock(scope, identity, metadata=None):
    """Acquire a machine-local lock keyed by scope + identity.

    Used to prevent multiple local gateways from using the same external identity
    at once (e.g. the same Telegram bot token across different HERMES_HOME dirs).
    """
```

Lock filename: `{scope}-{identity_hash}.lock` under the lock directory.

### Staleness Detection

`gateway/status.py:608-660` — the lock has sophisticated staleness detection:
1. Same PID + start_time → re-acquire (same process)
2. PID doesn't exist → stale
3. PID exists but different start_time → stale
4. On Windows/macOS (no `/proc`): falls back to process cmdline inspection

## Cross-Machine Behavior

The Hermes lock is NOT distributed. Two machines with the same credentials can both pass `_acquire_platform_lock`. The actual single-connection enforcement happens at the **platform server level**:

- **QQ Bot**: QQ's WebSocket gateway likely enforces one active connection per app_id. Second machine connecting will either be rejected or will displace the first.
- **WeChat iLink**: Long-poll sessions are tied to the bot token. The server delivers messages to the most recently authenticated polling session.

## Implication

When asked "will messages go to Machine B if Machine A's gateway is down?" — the answer is YES, but because Machine A has no active connection to the platform server, not because Hermes routes anything. The platform server naturally delivers to the only connected client.
