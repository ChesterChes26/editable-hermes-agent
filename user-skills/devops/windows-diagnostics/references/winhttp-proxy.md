# WinHTTP vs WinINET Proxy — Office Connectivity Troubleshooting

Windows has two independent proxy layers. Office/Outlook use WinHTTP; browsers and the WebView2-based Office sign-in dialog (AuthHost) use WinINET. Mixing them up is the root cause behind errors like "No Network Connection" and `0x80190001`.

## The two proxy layers

| Layer | Configured via | Used by |
|-------|---------------|---------|
| WinINET (System Proxy) | `HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings` — ProxyEnable, ProxyServer, ProxyOverride | IE, Edge, WebView2, Office AuthHost sign-in dialog |
| WinHTTP | `netsh winhttp` — reads from `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings\Connections\WinHttpSettings` | Windows services, Office desktop apps (Outlook, Word, etc.), `curl` without `--proxy` |

They are **independent** — setting one does NOT affect the other.

## Diagnostic commands

```powershell
# System proxy (WinINET)
reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable
reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer
reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyOverride

# WinHTTP proxy (requires admin to read in some cases)
netsh winhttp show proxy
# Or from registry (may time out in MSYS/bash — use PowerShell)
Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings\Connections" -Name WinHttpSettings
```

## Common symptom: "No Network Connection" in Outlook

Outlook uses WinHTTP for server connectivity. If WinHTTP is set to direct access (`netsh winhttp reset proxy`) but the machine requires a proxy (127.0.0.1:7897) to reach the internet, Outlook can't connect.

Fix: set WinHTTP proxy to match the system proxy.

```powershell
# Set WinHTTP proxy (requires admin)
netsh winhttp set proxy proxy-server="127.0.0.1:7897" bypass-list="localhost;127.*;192.168.*;10.*;<local>"

# Or import from WinINET
netsh winhttp import proxy source=ie
```

Note: `netsh winhttp` requires admin rights. Use `Start-Process netsh -Verb RunAs` from PowerShell.

## Common symptom: 0x80190001 during Office sign-in

This error occurs when the Office modern auth flow (WebView2 AuthHost) can't reach Microsoft authentication endpoints. Three compounding factors:

1. **WinHTTP and WinINET must both be correct.** Outlook desktop uses WinHTTP for API calls, but the sign-in window (AuthHost.exe) uses WebView2 which uses WinINET (system proxy). Both need to work.

2. **WebView2 AppContainer restriction.** AuthHost.exe runs in an AppContainer sandbox that blocks connections to `127.0.0.1` by default. If the proxy is on localhost (127.0.0.1:7897), AuthHost can't reach it.

3. **VPN TUN interfaces** (e.g., "Meta Tunnel", Clash TUN mode) add a third routing layer that may interfere.

### Fix: Bypass the proxy for Microsoft auth domains

Add Microsoft authentication domains to **both** proxy bypass lists:

```
login.live.com
login.microsoftonline.com
account.live.com
*.msauth.net
*.msftauth.net
login.windows.net
aadcdn.msauth.net
logincdn.msauth.net
autologon.microsoftazuread-sso.com
```

For WinINET (system proxy):
```powershell
$current = (Get-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings").ProxyOverride
$bypass = "$current;login.live.com;login.microsoftonline.com;*.msauth.net;*.msftauth.net"
Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings" -Name ProxyOverride -Value $bypass
```

For WinHTTP (requires admin):
```powershell
Start-Process netsh -ArgumentList 'winhttp set proxy proxy-server="127.0.0.1:7897" bypass-list="...;login.live.com;login.microsoftonline.com;*.msauth.net;*.msftauth.net"' -Verb RunAs -Wait
```

### If bypass doesn't work: disable proxy entirely

Sometimes the VPN TUN interface + localhost proxy combination is unresolvable for Office sign-in. The fastest fix:

1. Temporarily disable the VPN/proxy software
2. Disable system proxy (WinINET `ProxyEnable` = 0)
3. Reset WinHTTP: `netsh winhttp reset proxy` (admin)
4. Sign in to Outlook once (credentials are cached)
5. Re-enable proxy/VPN

Outlook stores credentials after first sign-in; subsequent token refreshes use WinHTTP (which can be re-configured with proxy after sign-in).

## ODT (Office Deployment Tool) notes

The ODT self-extracting exe contains an embedded CAB at PE offset 0x40C00. The `setup.exe /extract` self-extraction may hang in headless environments (UAC dialog). Extract programmatically:

```python
import struct
with open('odt.exe', 'rb') as f:
    data = f.read()
cab_offset = 0x40C00  # MSCF signature
cab_size = struct.unpack_from('<I', data, cab_offset + 8)[0]
with open('odt.cab', 'wb') as f:
    f.write(data[cab_offset:cab_offset + cab_size])
```

Then extract with `expand.exe` (Windows built-in) or `cabextract`.

For Office installation without user interaction, use the online installer (`OfficeSetup.exe` from `c2rsetup.officeapps.live.com`) — it handles download + install + EULA acceptance in one step, though it installs the full suite, not individual apps.

## Verification checklist

After proxy fixes, verify connectivity:

```bash
# Direct (bypass works)
curl -s -o /dev/null -w "%{http_code}" https://login.live.com

# Through proxy (proxy works)
curl -s -o /dev/null -w "%{http_code}" --proxy http://127.0.0.1:7897 https://login.live.com
```

Both should return 200/302. If only the proxied one works, bypass is not functional — the machine truly requires the proxy for all connections.
