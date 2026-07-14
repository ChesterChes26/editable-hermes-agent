---
name: superpowers-setup
description: Install and configure the Superpowers skill framework (obra/superpowers) in a project workspace. Covers clone layout, update workflow, and harness plugin integration.
---

## Trigger

When the user asks to "install superpowers", "initialize superpowers", "set up .agent with superpowers", or mentions superpowers version numbers (6.x).

## Core Rule: Workspace-Level Clone

Clone the `obra/superpowers` repo at **workspace level** — parallel to project directories — NOT inside a project's `.agent/` or any hidden config folder.

```
D:\workspace\
  automation_re\        ← project
  superpowers\          ← superpowers repo (git clone here)
```

**Why**: enables `git pull` for updates, and multiple projects can reference the same installation.

## Installation Steps

### 1. Determine target version

Check latest release: `https://github.com/obra/superpowers/releases`

Use the latest stable tag (e.g. `v6.1.1`). User may specify a version line (e.g. "6.0" means latest 6.0.x).

### 2. Clone (with proxy if needed)

```bash
cd /d/workspace
git clone --depth 1 --branch main \
  -c http.proxy=http://127.0.0.1:7897 \
  -c https.proxy=http://127.0.0.1:7897 \
  https://github.com/obra/superpowers.git superpowers
```

Without proxy (direct access):
```bash
git clone --depth 1 --branch main \
  https://github.com/obra/superpowers.git superpowers
```

### 3. Verify

```bash
git -C superpowers describe --tags   # e.g. v6.1.1
ls superpowers/skills/               # 14 skill directories
```

### 4. Updating

```bash
cd /d/workspace/superpowers
git pull
```

### 5. Install into Codex CLI

After cloning at workspace level, register the marketplace and install the plugin:

```bash
codex plugin marketplace add obra/superpowers
codex plugin add superpowers@superpowers-dev
```

Verify:

```bash
codex plugin list | grep superpowers
# Expected: superpowers@superpowers-dev  installed, enabled  6.x.x
```

The `superpowers-dev` marketplace name is auto-derived by Codex from the repo name.

### 6. Create project-level .agent/AGENTS.md

For non-Codex agents to discover the skills, create a minimal `.agent/AGENTS.md` in the project root:

```markdown
# Superpowers

This project uses [Superpowers](https://github.com/obra/superpowers).

Skills path: `D:\workspace\superpowers\skills\`

## Codex

Installed via `superpowers@superpowers-dev` plugin.

## Update

cd D:\workspace\superpowers && git pull
```

This file acts as a breadcrumb — agents that read `AGENTS.md` from the project root know where to find the skills.

## Harness Plugin Awareness

The repo contains harness-specific plugin manifests (`.codex-plugin/`, `.claude-plugin/`, `.cursor-plugin/`, etc.). These are marketplace manifests, NOT auto-discovered plugins:

- **`.codex-plugin/`** — does NOT conflict with project `.codex/` directory. Codex only scans `.codex/` for installed plugins. The `.codex-plugin/` manifest is for marketplace installation (`codex plugin add`).
- **`.claude-plugin/`** — Claude Code plugin manifest for `/plugin install`.
- **`.cursor-plugin/`** — Cursor plugin manifest for `/add-plugin`.

## Pitfalls

- **Do NOT clone into `.agent/`** inside a project. The user wants superpowers as a shared, updatable workspace-level dependency, not buried inside a single project's hidden config.
- **Do NOT assume `.codex-plugin/` auto-loads**. It's a manifest for explicit installation, not an active plugin directory.
- **GitHub rate-limiting**: if curl/API calls return 429, switch to browser-based navigation or git clone directly.
- **Windows file locking on git repos**: `rm -rf` or `mv` on a cloned git repo may fail with "Device or resource busy". Workaround: remove `.git/` first (`rm -rf .git`), then remove the remaining directory. The `.git/objects` handle is often the locked resource.
