---
name: codex
description: "Delegate coding to OpenAI Codex CLI (features, PRs). Plugin installation from openai/plugins marketplace."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Codex, OpenAI, Code-Review, Refactoring]
    related_skills: [claude-code, hermes-agent]
---

# Codex CLI

Delegate coding tasks to [Codex](https://github.com/openai/codex) via the Hermes terminal. Codex is OpenAI's autonomous coding agent CLI.

## When to use

- Building features
- Refactoring
- PR reviews
- Batch issue fixing

Requires the codex CLI and a git repository.

## Prerequisites

- Codex installed: `npm install -g @openai/codex`
- OpenAI auth configured: either `OPENAI_API_KEY` or Codex OAuth credentials
- **Must run inside a git repository** — Codex refuses to run outside one
- Use `pty=true` in terminal calls — Codex is an interactive terminal app
- **Plugins:** see `references/plugin-install.md` for installing plugins from openai/plugins into a project's `.codex/` directory

For Hermes itself, `model.provider: openai-codex` uses Hermes-managed Codex
OAuth from `~/.hermes/auth.json` after `hermes auth add openai-codex`. For the
standalone Codex CLI, a valid CLI OAuth session may live under
`~/.codex/auth.json`; do not treat a missing `OPENAI_API_KEY` alone as proof
that Codex auth is missing.

## Configuration & Diagnostics

**`codex doctor` is the single authoritative command for diagnosing Codex state.**
Run it whenever the user asks about Codex configuration, model provider, auth,
or connectivity — it reports everything in one structured output.

### Verifying model provider configuration

```
codex doctor
```

Key fields to check in the output:
- `default model provider` — which provider Codex is using (openai, etc.)
- `model` — the active model (`<default>` means no override in config.toml)
- `auth mode` — `api_key` or `oauth`
- `stored API key` / `stored ChatGPT tokens` — which auth methods are present
- `config.toml` — path and parse status (empty file = all defaults)
- `rollout DB model providers custom=N` — if N>0, past third-party tools (ccswitch, CodexSwitch) may have left history entries; not harmful but worth noting

### Configuration files

| File | Format | Purpose |
|------|--------|---------|
| `~/.codex/config.toml` | TOML | Model selection, sandbox, approvals, feature flags |
| `~/.codex/auth.json` | JSON | API key or OAuth tokens |

An **empty `config.toml`** means Codex uses all defaults — no provider override,
no custom model, no feature flag toggles. This is the desired state when the
user wants OpenAI Official as the provider.

### Model provider scope

As of 0.142.0, Codex natively supports:
- **OpenAI** (default) — via API key or OAuth
- **Local open-source** — via `--oss` / `--local-provider ollama|lmstudio`

There is NO native first-party support for Anthropic, Google, or other cloud
providers as of 0.142.0. Tools like ccswitch / CodexSwitch exist in the
ecosystem to fill this gap by routing requests through a proxy.

### Custom model providers (third-party OpenAI-compatible APIs)

Codex supports custom providers via `config.toml`:

```toml
model_provider = "custom"
model = "<model-slug>"
model_catalog_json = "cc-switch-model-catalog.json"

[model_providers.custom]
name = "<provider-name>"
base_url = "https://api.<provider>.com"
wire_api = "responses"           # or "chat_completions"
requires_openai_auth = true
```

The custom provider name must match a `model_providers.<name>` section in
`cc-switch-model-catalog.json`. This catalog defines model capabilities
(slugs, context windows, tool support, reasoning levels).

**Critical: `wire_api` determines the API protocol Codex uses.**

| `wire_api` value | Protocol | Supported by |
|---|---|---|
| `"responses"` | OpenAI Responses API (newer, richer) | OpenAI only |
| `"chat_completions"` | OpenAI Chat Completions API (standard) | OpenAI + all compatible providers |

**Pitfall — Responses API mismatch with third-party providers:**

DeepSeek, Groq, Together, and most third-party providers only implement the
Chat Completions API — they do NOT support the Responses API. If `wire_api`
is set to `"responses"` against a non-OpenAI base_url, the provider returns
errors because it doesn't understand the wire format.

**Fix for DeepSeek and similar providers:** either:

1. Set `wire_api = "chat_completions"` in config.toml (if Codex supports it
   for custom providers in your version — test it).
2. Route through a translation proxy (litellm, one-api) that converts
   Responses API → Chat Completions API format.

The `requires_openai_auth = true` field sends the `OPENAI_API_KEY` from
`~/.codex/auth.json` as a Bearer token — this works with DeepSeek since
DeepSeek also uses Bearer token auth.

See `references/custom-provider-config.toml` for a complete working config
example (DeepSeek V4 Flash, Codex 0.142.5).

For the ecosystem of third-party bridging solutions (protocol translation proxies,
GUI managers, agent runtimes) that connect Codex to DeepSeek and comparable
providers, see `references/deepseek-providers.md` — covers ccswitch-deepseek,
CodeSeeX, and cc-switch with maintenance status, bug history, and recommendation.

### Updating Codex

```
npm install -g @openai/codex@latest
codex --version   # verify
```

## Plugin Installation

Codex does NOT have `/skill-name` slash commands or `@skill` mention syntax (unlike Claude Code). Skills from plugins are loaded **automatically** by the agent — the system prompt injects the skill name + description, and the agent calls `skill_view()` when a matching task is detected. To force-load a skill, explicitly say "use the <name> skill" in your prompt.

Codex plugins live in the [openai/plugins](https://github.com/openai/plugins) repo (175+ plugins). Installing them into a project means cloning plugins into `.codex/` without pulling the entire repo.

### Installing plugins into a project

Use sparse checkout to clone only the plugins you need:

```bash
# 1. Shallow clone without checkout (avoids pulling the full 175-plugin repo)
git -c http.proxy=<proxy> clone --depth 1 --no-checkout \
    https://github.com/openai/plugins.git plugins

cd plugins

# 2. Enable cone-mode sparse checkout, select only needed plugin dirs
git sparse-checkout init --cone
git sparse-checkout set plugins/github plugins/notion plugins/vercel  # ... add more
git checkout

# 3. Move plugins to project-level .codex/ (clean up the nesting)
cd .. && mkdir -p .codex
mv plugins/plugins/* .codex/
rm -rf plugins
```

Each plugin MUST have `.codex-plugin/plugin.json` at minimum. A well-equipped plugin also carries `skills/`, optional `agents/`, `commands/`, `hooks.json`, `.app.json` (OAuth), `.mcp.json` (MCP server).

### Verifying installation

```bash
# Check every plugin has its manifest
for d in .codex/*/; do
  [ -f "$d.codex-plugin/plugin.json" ] && echo "OK: $d" || echo "MISSING: $d"
done

# Audit full structure (skills, agents, commands, hooks, connectors)
find .codex -type f -not -path '*/.git/*'
```

### Plugin categories (selected)

| Category | Plugins |
|----------|---------|
| Developer Tools | github, vercel, cloudflare, supabase, sentry, neon-postgres |
| Productivity | notion, linear, gmail, google-calendar, google-drive, airtable |
| Communication | slack, gmail, outlook-email, teams, zoom |
| Design | figma, canva, lovable |
| Finance | stripe |

### Pitfalls

- **Full clone times out on slow/corporate connections.** The repo is large; always use `--depth 1 --no-checkout` + sparse checkout.
- **`git sparse-checkout set` on a non-cone-mode repo silently fails.** Run `git sparse-checkout init --cone` first.
- **After moving plugins into `.codex/`, verify no orphaned `.git` directory** — the outer clone's `.git` was deleted with `rm -rf plugins`, but double-check.
- See `references/plugin-install.md` for a worked example with proxy specifics.

## One-Shot Tasks

```
terminal(command="codex exec 'Add dark mode toggle to settings'", workdir="~/project", pty=true)
```

For scratch work (Codex needs a git repo):
```
terminal(command="cd $(mktemp -d) && git init && codex exec 'Build a snake game in Python'", pty=true)
```

## Background Mode (Long Tasks)

```
# Start in background with PTY
terminal(command="codex exec --full-auto 'Refactor the auth module'", workdir="~/project", background=true, pty=true)
# Returns session_id

# Monitor progress
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Send input if Codex asks a question
process(action="submit", session_id="<id>", data="yes")

# Kill if needed
process(action="kill", session_id="<id>")
```

## Key Flags

| Flag | Effect |
|------|--------|
| `exec "prompt"` | One-shot execution, exits when done |
| `--full-auto` | Sandboxed but auto-approves file changes in workspace |
| `--yolo` | No sandbox, no approvals (fastest, most dangerous) |
| `--sandbox danger-full-access` | No Codex sandbox; useful when the host service context breaks bubblewrap |

## Hermes Gateway Caveat

When invoking the Codex CLI from a Hermes gateway/service context (for example,
Telegram-driven agent sessions), Codex `workspace-write` sandboxing may fail even
when the same command works in the user's interactive shell. A typical symptom is
bubblewrap/user-namespace errors such as `setting up uid map: Permission denied`
or `loopback: Failed RTM_NEWADDR: Operation not permitted`.

In that context, prefer:

```
codex exec --sandbox danger-full-access "<task>"
```

Use process boundaries as the safety layer instead: explicit `workdir`, clean git
status before launch, narrow task prompts, `git diff` review, targeted tests, and
human/agent confirmation before committing broad changes.

## PR Reviews

Clone to a temp directory for safe review:

```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main", pty=true)
```

## Parallel Issue Fixing with Worktrees

```
# Create worktrees
terminal(command="git worktree add -b fix/issue-78 /tmp/issue-78 main", workdir="~/project")
terminal(command="git worktree add -b fix/issue-99 /tmp/issue-99 main", workdir="~/project")

# Launch Codex in each
terminal(command="codex --yolo exec 'Fix issue #78: <description>. Commit when done.'", workdir="/tmp/issue-78", background=true, pty=true)
terminal(command="codex --yolo exec 'Fix issue #99: <description>. Commit when done.'", workdir="/tmp/issue-99", background=true, pty=true)

# Monitor
process(action="list")

# After completion, push and create PRs
terminal(command="cd /tmp/issue-78 && git push -u origin fix/issue-78")
terminal(command="gh pr create --repo user/repo --head fix/issue-78 --title 'fix: ...' --body '...'")

# Cleanup
terminal(command="git worktree remove /tmp/issue-78", workdir="~/project")
```

## Batch PR Reviews

```
# Fetch all PR refs
terminal(command="git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'", workdir="~/project")

# Review multiple PRs in parallel
terminal(command="codex exec 'Review PR #86. git diff origin/main...origin/pr/86'", workdir="~/project", background=true, pty=true)
terminal(command="codex exec 'Review PR #87. git diff origin/main...origin/pr/87'", workdir="~/project", background=true, pty=true)

# Post results
terminal(command="gh pr comment 86 --body '<review>'", workdir="~/project")
```

## Rules

1. **Always use `pty=true`** — Codex is an interactive terminal app and hangs without a PTY
2. **Git repo required** — Codex won't run outside a git directory. Use `mktemp -d && git init` for scratch
3. **Use `exec` for one-shots** — `codex exec "prompt"` runs and exits cleanly
4. **`--full-auto` for building** — auto-approves changes within the sandbox
5. **Background for long tasks** — use `background=true` and monitor with `process` tool
6. **Don't interfere** — monitor with `poll`/`log`, be patient with long-running tasks
7. **Parallel is fine** — run multiple Codex processes at once for batch work
