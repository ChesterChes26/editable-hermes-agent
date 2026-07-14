# Session Evidence: Loading Profile Hang + TUN Race Condition

Date: 2026-07-06

## Environment

- Windows 10, Clash Verge (PID 32100), Meta TUN adapter
- Outlook Classic: `C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE`
- Account: Leon88726@hotmail.com (Microsoft Exchange)

## Diagnostic Output

### Proxy state at time of hang
```
> netsh winhttp show proxy
当前的 WinHTTP 代理服务器设置:
    直接访问(没有代理服务器)。

> netstat -ano | findstr 7897
TCP    127.0.0.1:7897         0.0.0.0:0              LISTENING       34032
```

Key: port 7897 listening but WinHTTP has NO proxy configured.

### WinINET proxy state
```
> reg query "HKCU\...\Internet Settings" /v ProxyEnable
(no value found)
> reg query "HKCU\...\Internet Settings" /v ProxyServer
(no value found)
```

Key: WinINET proxy keys absent — Clash Verge using TUN mode (virtual adapter routing),
not traditional system proxy.

### TUN adapter
```
> netsh interface show interface | findstr -i "meta"
已启用   已连接   专用    Meta
```

Meta virtual adapter present and "connected", but Outlook hung.

### Resolution
Same Outlook instance launched cleanly ~90 seconds later with no config changes.
Status bar showed "Connected to: Microsoft Exchange", inbox loaded with 2,627 items.

## Root Cause

TUN adapter reports "connected" at the NDIS layer before the userspace proxy
(Clash Verge) has fully initialized its routing table. Outlook's startup sequence
(Autodiscover → Exchange connection) fires during this window. The DNS/connect()
calls hit the TUN adapter, which accepts them but can't forward yet → TCP SYN
times out → Outlook hangs at "Loading Profile" splash screen with no error dialog.

This is a race condition: the same Outlook.exe launched 60s later succeeds because
the TUN routing is fully ready by then.

## Pattern

- Intermittent — same binary, same config, same session: works sometimes, hangs others.
- TUN mode is the variable — system proxy mode (WinINET) doesn't have this race.
- No error code or dialog — just indefinite hang at splash screen.
