# Installing Codex Plugins from openai/plugins into a Project

## Context

Codex plugins are hosted in the `openai/plugins` GitHub repository (175+ plugins). To use them in a local project, clone specific plugins into `.codex/` directory.

## Prerequisites

- Codex CLI installed: `npm install -g @openai/codex`
- Project initialized as git repo (Codex requires it)
- Network: if GitHub is firewalled, need proxy (e.g., `127.0.0.1:7897` via Clash)

## Plugin structure

Each plugin is a directory with:

```
plugin-name/
├── .codex-plugin/plugin.json    ← required: manifest
├── skills/                      ← optional: SKILL.md instructions
├── agents/                      ← optional: sub-agent definitions
├── commands/                    ← optional: slash commands
├── hooks.json                   ← optional: PostToolUse hooks
├── .app.json                    ← optional: OAuth connector
├── .mcp.json                    ← optional: MCP server
├── scripts/                     ← optional: executable scripts
└── assets/                      ← icons, logos
```

## Installation via sparse checkout

```bash
git -c http.proxy=http://127.0.0.1:7897 clone --depth 1 --no-checkout \
  https://github.com/openai/plugins.git plugins
cd plugins
git sparse-checkout init --cone
git sparse-checkout set plugins/github plugins/slack plugins/notion ...
git checkout
cd .. && mkdir -p .codex && mv plugins/plugins/* .codex/ && rm -rf plugins
```

## Pitfalls

- **Double nesting**: clone creates `plugins/` (repo root) containing `plugins/` (actual dirs). Must move `plugins/plugins/*` not `plugins/*`.
- **Large repo**: `--filter=blob:none` caused proxy disconnect. Fix: drop filter, keep `--no-checkout`.
- **OAuth plugins** (`.app.json`) need Codex connector setup; skill-only plugins work immediately.
