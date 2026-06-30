---
name: windows-diagnostics
description: Diagnose Windows system performance issues — slow login, lock-screen delays, sleep/resume problems, network adapter issues — via PowerShell event logs, powercfg, and system configuration checks.
---

# Windows Diagnostics

Diagnose Windows performance issues on the local machine: slow login after lock, sleep/resume problems, network adapter misconfiguration, domain authentication delays.

## Trigger conditions
- User reports slow login, lock-screen delay, or system hangs after unlock
- User asks why Windows is slow after sleep/resume
- User wants to diagnose Windows performance issues

## Critical: PowerShell script encoding

When writing .ps1 files for execution via `powershell -File` on a Chinese-locale Windows machine:
- **MUST use UTF-8 with BOM** (`encoding='utf-8-sig'` in Python). Without BOM, PowerShell's parser fails on multi-byte characters (Chinese UI strings in error messages, log entries) with misleading errors like "missing Catch or Finally block".
- `write_file` tool does NOT add BOM — always use `execute_code` with Python to write .ps1 files.
- bash heredocs also produce corrupt .ps1 files on CJK Windows — avoid.

## Critical: PowerShell from bash

When running PowerShell commands from bash (git-bash/MSYS):
- `$_.Property` gets expanded by bash before reaching PowerShell. The command fails with "ObjectNotFound" for odd paths like `C:\Users\user.Id`.
- **Always write standalone .ps1 files and execute with `powershell -ExecutionPolicy Bypass -File`.** Never inline PowerShell pipelines in bash `powershell -Command`.
- Exception: simple one-liners without `$_` or `| Where-Object` are safe.

## Diagnostic workflow for lock-screen login slowness

### Phase 1: Check if it's actually sleep/resume

```
powercfg /lastwake
powercfg /devicequery wake_armed
powercfg /waketimers
```

Key question: is the machine going into S3 sleep during lock, or staying unlocked? Check System event log:

```
Get-WinEvent -LogName System -MaxEvents 200 | Where-Object { $_.Id -eq 42 }   # entering sleep
Get-WinEvent -LogName System -MaxEvents 200 | Where-Object { $_.Id -eq 131 }  # S3 resume time
```

Event 131 shows `FullResume` in milliseconds. Under ~2s is normal; anything over 5s is suspicious.

### Phase 2: Check Wake-on-LAN configuration

Excessive Wake-on-LAN sensitivity causes sleep/wake cycling that leaves the system unstable:

```
Get-NetAdapterAdvancedProperty -Name "以太网" | Where-Object { $_.RegistryKeyword -match "Wake|WoL|PME|Pattern" }
```

Red flags:
- **Wake on Pattern Match = Enabled** → ANY network traffic wakes the machine. Causes sleep/wake cycling every few minutes.
- Wake on Magic Packet = Enabled → OK for IT-managed machines.
- Enable PME = Enabled → PCI power management events wake the machine.

Check how often the machine wakes: count S3 resume events per hour.

### Phase 3: Check domain/network auth delays

If the machine is domain-joined:

```
# Check for NTP failures (Event 37)
Get-WinEvent -LogName System -MaxEvents 200 | Where-Object { $_.Id -eq 37 }

# Check domain role
Get-ComputerInfo | Select-Object CsDomain, CsDomainRole
```

NTP failures during login cause Kerberos time-skew → authentication retries with timeouts. Each retry can add 5-30 seconds.

### Phase 4: Check registry hive sizes

Large ntuser.dat / UsrClass.dat slow down profile loading:

```
Get-Item "C:\Users\<user>\ntuser.dat" -Force
Get-Item "C:\Users\<user>\AppData\Local\Microsoft\Windows\UsrClass.dat" -Force
```

Under 10 MB is normal. Over 50 MB warrants investigation (shell extension bloat, COM registration leaks).

### Phase 5: Memory pressure

```
Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory
Get-Process -Name "Memory Compression" -ErrorAction SilentlyContinue
```

Memory Compression over 2 GB WorkingSet suggests significant memory pressure. Combined with high uptime, shell extension leaks in explorer.exe can accumulate.

## Key event log IDs

See `references/event-log-ids.md` for the full reference.

## Office/Outlook connectivity & WinHTTP proxy

See `references/winhttp-proxy.md` for the full reference on WinHTTP vs WinINET proxy layers, Outlook "No Network Connection" (WinHTTP missing proxy), `0x80190001` sign-in error (WebView2 AppContainer + localhost proxy), and ODT CAB extraction.

## Scripts

- `scripts/check-wake-config.ps1` — dump Wake-on-LAN config, S3 resume stats, NTP errors, memory pressure. Must be written via Python with UTF-8 BOM before execution. Run with `powershell -ExecutionPolicy Bypass -File`.
