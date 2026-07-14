---
name: hermes-desktop-setup
description: "Use when building, launching, or troubleshooting Hermes Dashboard (web UI) or Desktop (Electron) on Windows."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [hermes, desktop, dashboard, electron, web-ui, windows, build]
    related_skills: [hermes-agent]
---

# Hermes Desktop & Dashboard Setup (Windows)

Build and launch Hermes graphical interfaces on Windows: the Web Dashboard (port-based, browser) and the Electron Desktop app (native window).

## Prerequisites

- Node.js + npm (`node --version && npm --version`)
- Hermes source at `~/.hermes/hermes-agent/` (standard install location)

## Dashboard (Web UI)

The Dashboard is a Vite-built React SPA served on a local port. It manages config, API keys, sessions, skills, and cron jobs via browser.

### First-Time Build

```bash
cd ~/.hermes/hermes-agent
npm install --workspace web
npm run build -w web
```

Output lands in `hermes_cli/web_dist/`. Build takes ~2s after npm install.

### Launch

```bash
hermes dashboard --port 9220 --no-open --skip-build
```

| Flag | Purpose |
|------|---------|
| `--port N` | Port (default 9119, use 0 for auto-assign) |
| `--no-open` | Don't auto-open browser |
| `--skip-build` | Skip Vite rebuild, use existing dist |
| `--insecure` | Allow non-localhost bind (DANGEROUS) |
| `--stop` | Stop all running dashboard processes |
| `--status` | List running dashboard processes |

### Troubleshooting

**Port in use (`Errno 10048`):** Kill the stale process or use a different port.
```bash
hermes dashboard --stop          # kill all instances
hermes dashboard --port 9220     # use alternate port
```

**No web dist found:** Build first with `npm run build -w web` from the hermes-agent source root, or omit `--skip-build` to let it build automatically.

## Desktop App (Electron)

The Desktop is a native Electron window. It requires a full workspace build including TypeScript compilation, Vite bundling, and electron-builder packaging.

### Build & Launch

```bash
hermes desktop --force-build
```

This runs the full pipeline: npm install (if needed) → TypeScript → Vite → electron-builder `--dir` → launch. Output lands in `apps/desktop/release/win-unpacked/Hermes.exe`.

| Flag | Purpose |
|------|---------|
| `--force-build` | Full rebuild even if content stamp matches |
| `--skip-build` | Launch existing unpacked app from `apps/desktop/release` |
| `--build-only` | Build but don't launch |
| `--source` | Launch via `electron .` against `apps/desktop/dist` instead of packaged app |
| `--cwd PATH` | Initial project directory for Desktop chat sessions |

### Troubleshooting

**Build hangs at "updating asar integrity":** This is normal — the asar integrity update can take minutes on Windows. Don't kill it prematurely. If it truly stalls (>10 min), kill and retry with `--force-build`.

**`--skip-build` says no release found:** The Desktop hasn't been built yet. Run `hermes desktop --force-build` first.

## Common Pitfalls

1. **Dashboard build needs npm install first.** Running `npm run build -w web` without `npm install --workspace web` will fail with missing dependencies.
2. **Port 9119 may be occupied.** Windows often has lingering processes holding ports. Use `hermes dashboard --stop` or pick a different port.
3. **Desktop build is slow.** The full pipeline (npm install + tsc + vite + electron-builder) can take 3-5 minutes on first run. Subsequent builds with `--skip-build` launch instantly.
4. **Don't use Git Bash `/` prefix with Claude Code slash commands.** Git Bash converts `/skill-name` to a Windows path like `C:/Program Files/Git/skill-name`. Use `printf '/skill-name\n' | claude` or `--print` mode instead.
5. **`--force-build` vs `--skip-build`**: Use `--force-build` when source changed, `--skip-build` to relaunch without rebuilding.

## Verification Checklist

- [ ] `node --version` returns v18+
- [ ] Dashboard: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:<port>` returns 200
- [ ] Desktop: `ls apps/desktop/release/win-unpacked/Hermes.exe` exists
