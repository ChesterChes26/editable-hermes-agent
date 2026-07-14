# Office Sign-In 0x80190001: Proxy Debugging

## The error

Office (Outlook) shows "No Network Connection" initially, then `0x80190001` when signing in with a Microsoft account. The system has a local proxy (127.0.0.1:7897) and potentially a VPN TUN interface.

## Root cause chain

```
System proxy (WinINET) = 127.0.0.1:7897  ✓
WinHTTP proxy            = DIRECT          ✗  ← Outlook uses this
```

Outlook desktop app uses WinHTTP for network. WinHTTP does NOT inherit WinINET proxy settings. So Outlook tries direct connections, which fail in environments where all traffic must go through proxy/VPN.

After setting WinHTTP proxy to match WinINET:

```
WinHTTP proxy = 127.0.0.1:7897  ✓
```

Outlook now routes through the proxy, but sign-in fails with `0x80190001`.

## Why proxy breaks Office sign-in

Office modern auth uses **AuthHost.exe** — a WebView2-based dialog for Microsoft account sign-in. Three compounding issues:

1. **AuthHost uses WinINET, not WinHTTP** — so the WinHTTP fix helps API calls but the sign-in dialog itself still uses system proxy
2. **AuthHost runs in AppContainer** — Windows 10/11 AppContainer sandbox blocks localhost connections by default. Proxy at 127.0.0.1 is unreachable from inside the sandbox
3. **OAuth 2.0 token flow is proxy-sensitive** — even if AuthHost reaches the proxy, the OAuth redirect chain (login.live.com → login.microsoftonline.com → token endpoint) can be broken by proxy manipulation

## Diagnostic steps

### 1. Check both proxy layers
```
reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable
reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer
netsh winhttp show proxy
```

### 2. Check VPN TUN interface
```
Get-NetAdapter | Where { $_.InterfaceDescription -match "VPN|TUN|TAP|Virtual|WireGuard|Wintun" }
```

### 3. Test auth endpoint connectivity
```bash
curl -I -m 5 https://login.live.com                     # should be 200
curl -I -m 5 https://login.microsoftonline.com          # should be 302
curl -I -m 5 --proxy http://127.0.0.1:7897 https://login.live.com  # through proxy
```

### 4. Check if auth endpoints work direct
If direct connections to login.live.com work (HTTP 200) but through-proxy fails, the fix is to BYPASS the proxy for auth domains, not route through it.

## The fix: Bypass proxy for Microsoft auth domains

**WinHTTP bypass** (for Outlook API calls after sign-in):
```
netsh winhttp set proxy proxy-server="127.0.0.1:7897" bypass-list="...;login.live.com;login.microsoftonline.com;account.live.com;logincdn.msauth.net;login.windows.net;graph.microsoft.com;*.msauth.net;*.msftauth.net;aadcdn.msauth.net"
```

**WinINET bypass** (for the sign-in dialog AuthHost):
```
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyOverride /t REG_SZ /d "...;login.live.com;login.microsoftonline.com;account.live.com;*.msauth.net;*.msftauth.net" /f
```

## The nuclear option: disable proxy for first sign-in

If the VPN creates a TUN interface (full tunnel), even "direct" connections go through the VPN. The bypass doesn't help because there's no true direct path. In this case:

1. Temporarily disable the VPN/proxy (user action)
2. Sign in to Outlook once (this caches the refresh token)
3. Re-enable VPN/proxy
4. Subsequent token refreshes go through WinHTTP with the bypass list → should work

## Verification: "No Network Connection" gone

After fixing:
- WinHTTP proxy properly configured AND auth domains bypassed
- OR proxy disabled, sign-in complete, proxy re-enabled with bypass
