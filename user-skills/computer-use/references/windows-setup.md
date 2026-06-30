# Windows Setup Detail — cua-driver on Hermes

Complete end-to-end setup captured from a real session (2025-06-30, Windows 10,
Hermes default profile, DeepSeek provider).

## 1. Install binary

```bash
hermes computer-use install
```

Downloads cua-driver-rs v0.6.8 to:
`C:\Users\<user>\AppData\Local\Programs\Cua\cua-driver\bin\`

Binary files:
- `cua-driver.exe` (main)
- `cua-driver-uia.exe` (UI Automation worker, requires admin for UIAccess)

Installer adds the bin dir to User PATH, but the change only takes effect
in **new** shells — the current shell won't see it.

## 2. Verify binary works

```bash
# In a shell where PATH includes the install dir:
cua-driver --version
# → "cua-driver 0.6.8"

# Or with absolute path:
"C:\Users\<user>\AppData\Local\Programs\Cua\cua-driver\bin\cua-driver.exe" --version
```

## 3. Get Hermes MCP config snippet

```bash
cua-driver mcp-config --client hermes
```

Output:
```yaml
mcp_servers:
  cua-driver:
    command: "C:\\Users\\<user>\\AppData\\Local\\Programs\\Cua\\cua-driver\\bin\\cua-driver.exe"
    args: ["mcp"]
```

## 4. Add to Hermes config

**CRITICAL: ~/.hermes/config.yaml is protected.** Cannot use `patch`,
`write_file`, or shell editors. Must use `hermes config set`:

```bash
hermes config set mcp_servers.cua-driver.command "C:\\Users\\<user>\\AppData\\Local\\Programs\\Cua\\cua-driver\\bin\\cua-driver.exe"
hermes config set 'mcp_servers.cua-driver.args[0]' mcp
```

Note: `hermes config set mcp_servers.cua-driver.args '["mcp"]'` may time out
on array syntax.  Use the `args[0]` form instead.

## 5. Verify MCP config took effect

```bash
# Read the section to confirm:
hermes config show mcp_servers
```

Expected result contains `cua-driver:` with `command:` and `args[0]: mcp`.

## 6. Restart / reload

The `computer_use` tool will NOT appear in the current Hermes session.
Options:
- `/reload-mcp` inside an active Hermes TUI session
- Restart Hermes entirely

## 7. Verify health

```bash
hermes computer-use doctor
```

## Pitfall: CLI wrapper vs MCP tool

`hermes computer-use status` searches `PATH` for `cua-driver`.  If the
binary was installed but the current shell doesn't have it on PATH,
status reports "not installed" — even though the MCP-based tool works.
This is harmless for the `computer_use` tool itself, which uses MCP
not the CLI wrapper.

## Pitfall: config.yaml location

Active config: `C:\Users\<user>\AppData\Local\hermes\config.yaml`
User-config (git-tracked): `C:\Users\<user>\AppData\Local\hermes\hermes-agent\user-config\config.yaml`

`hermes config set` writes to the active config.
