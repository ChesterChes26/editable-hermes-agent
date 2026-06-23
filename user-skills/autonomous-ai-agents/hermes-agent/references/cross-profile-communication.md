# Cross-Profile Communication

Patterns for having one Hermes profile interact with another.

## Quick One-Shot: `hermes -p <profile> -z "prompt"`

The `-z` flag is a global shortcut that runs a single-turn query and exits — no
subcommand needed. Combine with `-p` to run it on a different profile:

```bash
hermes -p worker -z "向用户问好，用中文"
```

Returns the agent's text response to stdout. Useful for:
- Having another agent persona respond to the user
- Testing a profile's configuration quickly
- Running a fire-and-forget query with a different SOUL.md/personality

**Pitfall:** The output is raw text returned to the caller. If the user is on a
messaging platform (WeChat, Telegram, etc.), the caller must relay the response.
The target profile does NOT deliver messages itself — it just writes to stdout.

## Profile-Aware `hermes send`

`hermes send` reuses the gateway's platform credentials and delivers without an
LLM loop. But it only works if the target profile has messaging platforms
configured:

```bash
# Check what platforms a profile has
hermes -p worker send --list
```

If it says "No messaging platforms configured", the profile can't deliver
messages. Fix: run `hermes -p worker gateway setup` or copy the platform config
from another profile.

## Cron Delivery Across Profiles

Cron jobs created from one profile can deliver to platforms configured on that
profile. If a profile has no messaging platforms, `deliver: origin` will fail
silently — the job runs but the result can't reach the user.

**Workaround:** If you need a different profile's agent to speak, use
`hermes -p <profile> -z "prompt"` and relay the output yourself.

## Profile Isolation

Each profile has its own:
- `config.yaml`, `.env`, `SOUL.md`
- `skills/`, `plugins/`, `cron/`, `memories/`
- Sessions (separate `state.db`)
- Gateway state (separate `gateway_state.json`)

Profiles share the same machine but are otherwise fully independent. Messaging
platform credentials must be configured per-profile.
