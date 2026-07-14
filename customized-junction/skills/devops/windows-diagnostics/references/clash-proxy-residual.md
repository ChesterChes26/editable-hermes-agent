# Clash ProxyServer Registry Residual — Diagnosis & Fix

> Windows network diagnostic: when Clash (Verge) is running in Direct mode with system proxy and TUN both disabled, some applications still can't connect.

## Root cause

Clash sets `ProxyServer=127.0.0.1:7897` in the registry when it starts. On exit, it resets `ProxyEnable` to 0 **but does not delete `ProxyServer`**. The residual value persists across restarts.

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings
  ProxyEnable = 0          ← reset correctly on exit
  ProxyServer = 127.0.0.1:7897  ← LEAKED — never cleared
```

Some applications (WeChat, Electron apps) read `ProxyServer` directly, bypassing the `ProxyEnable` flag entirely. They see `127.0.0.1:7897`, try to connect, and time out because Clash in Direct mode doesn't forward traffic on that port.

## Diagnostic workflow

Run all checks in order. Each step narrows the diagnosis:

### Step 1: Check registry proxy state

```python
import winreg
k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
    r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
try:
    enable, _ = winreg.QueryValueEx(k, "ProxyEnable")
    print(f"ProxyEnable = {enable}")
except: pass
try:
    server, _ = winreg.QueryValueEx(k, "ProxyServer")
    print(f"ProxyServer = {server}")
except: pass
winreg.CloseKey(k)
```

**Key finding:** `ProxyEnable=0` but `ProxyServer=127.0.0.1:7897` → Clash residual. Go to Fix.

### Step 2: If registry looks clean, check DNS

```bash
nslookup api.deepseek.com
```

If DNS fails → Clash DNS hijacking, not registry residual.

### Step 3: If DNS works, check routing

```bash
route print | grep "0.0.0.0"
```

If routing looks normal → test application-level connectivity.

### Step 4: Test bypassing proxy explicitly

```bash
curl -sI --noproxy '*' https://www.baidu.com
curl -sI --noproxy '*' https://api.deepseek.com
```

If these work but browser/WeChat doesn't → registry residual (applications read ProxyServer while curl uses its own proxy logic).

### Step 5: Check environment variables

```bash
env | grep -i proxy
```

If `HTTP_PROXY` or `HTTPS_PROXY` is set → another layer of proxy interference.

## Fix

### Temporary (immediate)

```python
import winreg
k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
    r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
    0, winreg.KEY_SET_VALUE)
winreg.DeleteValue(k, "ProxyServer")
winreg.CloseKey(k)
```

### Permanent

In Clash Verge settings, disable "Modify system proxy" (修改系统代理). This prevents Clash from writing `ProxyServer` at all — no residual on exit.

## Why curl is unaffected

curl uses libcurl which does NOT read the IE proxy registry settings by default. `curl --noproxy '*'` completely bypasses system proxy. Electron/WeChat use Chromium's network stack which reads `ProxyServer` from the registry directly.

## Where this fits in the skill

This is a **network proxy misconfiguration** pattern, not a sleep/resume or login performance issue. It belongs alongside the `references/winhttp-proxy.md` reference as another class of proxy-layer problem — this one caused by third-party app registry leakage rather than WinHTTP/WinINET misconfiguration.
