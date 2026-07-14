# Windows Event Log IDs for Diagnostics

Reference for diagnosing Windows performance issues via event logs.

## System log

| ID | Provider | Meaning | Diagnostic value |
|----|----------|---------|-----------------|
| 1 | Kernel-Power | System resumed from low-power state | Shows wake source (device) |
| 37 | Time-Service | NTP time sync result | Failure = domain auth delay risk |
| 41 | Kernel-Power | Unexpected shutdown | Crash/BSOD history |
| 42 | Kernel-Power | System entering sleep | Sleep reason (System Idle, User Request) |
| 107 | Kernel-Power | System resumed from sleep | Timestamp of resume |
| 130 | Kernel-Power | S3 suspend timing | SuspendStart, SuspendEnd (µs ticks) |
| 131 | Kernel-Power | S3 resume timing | ResumeCount, FullResume (ms), AverageResume |
| 566 | Kernel-Power | Session transition | Tracks session ID changes across sleep |
| 1001 | BugCheck | BSOD dump | Blue screen history |
| 6005 | EventLog | Event log started | Boot events |
| 6006 | EventLog | Event log stopped | Shutdown events |
| 7001 | Service Control | Service start timeout | Hung service during boot/login |
| 7002 | Service Control | Service start failure | Failed service during boot/login |
| 7040 | Service Control | Service start type change | BITS flipping auto/manual = suspicious |
| 10005 | DistributedCOM | DCOM activation timeout | Permission/service timeout |
| 10010 | DistributedCOM | DCOM server timeout | Permission/service timeout |

## Winlogon operational

| ID | Meaning |
|----|---------|
| 811 | Winlogon notification started (e.g., Sens, TermSrv) |
| 812 | Winlogon notification completed |

Event 4 = lock, Event 5 = unlock (shown in Message as 通知事件).

## User Profile Service operational

| ID | Meaning |
|----|---------|
| 1 | Received logon notification |
| 2 | Created logon notification |
| 3 | Received logoff notification |
| 4 | Created logoff notification |
| 5 | Loaded/unloaded registry hive (ntuser.dat, UsrClass.dat) |
| 1530-1533 | Profile load/unload timing details |

## Group Policy operational

| ID | Meaning |
|----|---------|
| 5016 | GP processing started |
| 5017 | GP processing completed |
| 8000-8007 | GP component processing times |

Requires admin rights to read.

## Power management commands

```
powercfg /list                    # Active power plans
powercfg /lastwake                # What woke the machine last
powercfg /waketimers              # Active wake timers
powercfg /devicequery wake_armed  # Devices allowed to wake
powercfg /sleepstudy              # Modern Standby analysis (needs admin)
powercfg /query SCHEME_CURRENT SUB_SLEEP     # Sleep timeout settings
powercfg /query SCHEME_CURRENT SUB_PCIEXPRESS # PCIe ASPM settings
```
