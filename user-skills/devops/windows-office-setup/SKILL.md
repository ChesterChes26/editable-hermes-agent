---
name: windows-office-setup
description: Install classic Outlook / Office on Windows via ODT, configure proxy layers (WinHTTP vs WinINET), and manage language packs. Covers pitfalls with headless ODT, Office auth proxy issues, and language pack quirks.
version: 1.0.0
---

# Windows Office Setup & Proxy Configuration

Installing and configuring classic Outlook (COM-based, not the new WebView2 Outlook) on Windows, dealing with proxy layering that breaks Office sign-in, and managing language packs.

## Trigger conditions

- User needs classic Outlook (for COM add-ins, plugins like Tencent Meeting)
- Office sign-in fails with 0x80190001 or "No Network Connection"
- Office language switch doesn't take effect
- ODT setup.exe fails silently (exit 127)

## Windows has TWO proxy layers — Office straddles both

```
WinINET (IE/Edge proxy)          WinHTTP (system services proxy)
  HKCU\...\Internet Settings       netsh winhttp
  └─ WebView2 / AuthHost           └─ Outlook desktop app
  └─ Office sign-in dialog         └─ Office API calls
```

When you set a system proxy at 127.0.0.1:7897 (e.g., Clash/V2Ray), WinINET picks it up automatically. WinHTTP does NOT — you must set it separately.

### Set WinHTTP proxy (requires admin)

```powershell
Start-Process netsh -ArgumentList 'winhttp set proxy proxy-server="127.0.0.1:7897" bypass-list="localhost;127.*;..."' -Verb RunAs -Wait
```

### Office sign-in 0x80190001 → proxy is interfering with OAuth

Office modern auth uses AuthHost.exe (WebView2 in AppContainer sandbox). This component:
1. Uses WinINET proxy (not WinHTTP)
2. Runs in AppContainer which **blocks localhost connections** on some Windows versions
3. OAuth 2.0 token flows are sensitive to proxy MITM

**Fix**: Add Microsoft auth domains to BOTH bypass lists:
- WinHTTP: `netsh winhttp set proxy ... bypass-list="...;login.live.com;login.microsoftonline.com;*.msauth.net;*.msftauth.net"`
- WinINET: `reg add HKCU\...\Internet Settings /v ProxyOverride /t REG_SZ /d "...;login.live.com;login.microsoftonline.com;*.msauth.net" /f`

### Verify proxy state

```
# System proxy (WinINET)
reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable
reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer

# WinHTTP proxy
netsh winhttp show proxy
```

### If VPN TUN mode is active (e.g., "Meta Tunnel" adapter)

The VPN creates a virtual adapter that routes ALL traffic. In this case, the simplest fix for Office sign-in is to disable the VPN/proxy temporarily, sign in once, then re-enable. Subsequent token refreshes use WinHTTP which handles proxy bypass correctly.

## Installing classic Outlook via ODT

The new Outlook (Microsoft.OutlookForWindows, olk.exe) is a WebView2 shell — no COM add-in support. Classic Outlook comes with Microsoft 365 Apps / Office Click-to-Run.

### Check what Outlook is installed

```powershell
Get-AppxPackage -Name "*OutlookForWindows*"  # new Outlook
Test-Path "C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE"  # classic Outlook
```

### ODT download & extraction

1. Real download URL from Microsoft page (URLs change; get current one):
   ```
   https://download.microsoft.com/download/<guid>/officedeploymenttool_<version>.exe
   ```
   To get the current URL: navigate to https://www.microsoft.com/en-us/download/details.aspx?id=49117, then extract from `document.querySelector('a[href*="officedeploymenttool"]')?.href`.

2. The .exe is a PE with embedded CAB at a variable offset. Extract with Python:
   ```python
   with open(exe_path, 'rb') as f:
       data = f.read()
   cab_offset = data.find(b'MSCF')
   cab_size = struct.unpack_from('<I', data, cab_offset + 8)[0]
   with open('odt.cab', 'wb') as f:
       f.write(data[cab_offset:cab_offset + cab_size])
   ```
3. Extract CAB: `cmd /c expand -F:* odt.cab .`

### ODT config XML (Outlook only, both languages)

```xml
<Configuration>
  <Add OfficeClientEdition="64" Channel="Current">
    <Product ID="O365ProPlusRetail">
      <Language ID="en-us" />
      <Language ID="zh-cn" />
      <ExcludeApp ID="Access" />
      <ExcludeApp ID="Excel" />
      <ExcludeApp ID="Groove" />
      <ExcludeApp ID="Lync" />
      <ExcludeApp ID="OneDrive" />
      <ExcludeApp ID="OneNote" />
      <ExcludeApp ID="PowerPoint" />
      <ExcludeApp ID="Publisher" />
      <ExcludeApp ID="Teams" />
      <ExcludeApp ID="Word" />
    </Product>
  </Add>
  <Display Level="None" AcceptEULA="TRUE" />
</Configuration>
```

### ODT pitfalls

- **Self-extracting EXE hangs in terminal** — the GUI EULA prompt blocks. Extract the CAB manually with Python instead.
- **`setup.exe /configure` exit 127** — in headless/terminal environment, ODT configure often fails silently. Common causes:
  - Product ID mismatch: OfficeSetup.exe consumer installer creates `O365HomePremRetail` + `ProPlusRetail`, NOT `O365ProPlusRetail`. ODT targeting wrong product ID fails.
  - Already-open Office apps blocking the configuration change.
  - Consumer-installed Office has a locked streaming config that ODT can't modify (unlike enterprise deployments).
  - **After OfficeSetup.exe installation, ODT is effectively useless** for reconfiguration — use Outlook's built-in settings instead.
- **Fallback**: download `OfficeSetup.exe` from the CDN (7MB stub) and run it. This installs the FULL suite but reliably gets classic Outlook.
  ```
  https://c2rsetup.officeapps.live.com/c2r/download.aspx?productReleaseID=ProPlusRetail&platform=x64&language=en-us&...
  ```
- **Winget `Microsoft.Office`** — theoretically works (`winget install --id Microsoft.Office`) but often times out due to download size.
- **Consumer vs enterprise install**: OfficeSetup.exe creates a different C2R profile. Always check actual product IDs after installation:
  ```powershell
  reg query "HKLM\SOFTWARE\Microsoft\Office\ClickToRun\Configuration" /v ProductReleaseIds
  reg query "HKLM\SOFTWARE\Microsoft\Office\ClickToRun\Configuration" /s | findstr ExcludedApps
  ```

### Verify installation

```powershell
Test-Path "C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE"
(Get-Item "C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE").VersionInfo.FileVersion
reg query "HKLM\SOFTWARE\Microsoft\Office\ClickToRun\Configuration" /v VersionToReport
```

## Office language pack

### The registry-only approach DOES NOT WORK

Setting `HKCU\SOFTWARE\Microsoft\Office\16.0\Common\LanguageResources\UILanguage = 2052` alone won't switch the UI. Office Click-to-Run bundles language resources in `stream.x64.x-none.dat` (multi-GB file). The registry tells Office which language to USE, but the resources must be PROVISIONED first.

**Pitfall**: After setting `UILanguage = 2052` in registry and restarting Outlook, the UI may still be English. Do NOT assume "the registry is set, therefore it worked." Always verify the actual language state with `reg query ...LanguageResources /s` and check for `InstalledLanguages` subkey presence. If `InstalledLanguages` is empty, no display language pack was ever provisioned — the registry value was wishful thinking.

### Why ODT language pack install fails (exit 127 repeatedly)

The OfficeSetup.exe consumer installer creates a different Click-to-Run profile than ODT expects:

| What | Product ID | Includes |
|------|-----------|----------|
| ODT default config | `O365ProPlusRetail` | Full suite |
| OfficeSetup.exe installs | `O365HomePremRetail` + `ProPlusRetail` | Split products |
| OfficeSetup Outlook source | `ProPlusRetail` (O365HomePremRetail excludes Outlook via `ExcludedApps: outlook`) | — |

ODT with `Product ID="O365ProPlusRetail"` targets a product that **doesn't exist** in the consumer-installed Office → `/configure` exits 127. Using the correct ID (`ProPlusRetail`) still fails because the consumer installer's streaming configuration is locked differently than enterprise deployments.

**Diagnose the actual installed product IDs:**
```powershell
reg query "HKLM\SOFTWARE\Microsoft\Office\ClickToRun\Configuration" /v ProductReleaseIds
reg query "HKLM\SOFTWARE\Microsoft\Office\ClickToRun\Configuration" /s | findstr ExcludedApps
```

### The ONLY reliable method: Outlook's built-in UI

```
File → Options → Language → "Add a Language..." → Chinese (Simplified) → Install
```

Office downloads and registers the language pack through its own update mechanism (not ODT, not C2R command line). This requires:
- Office CDN reachable (test: `curl http://officecdn.microsoft.com/pr/<AudienceId>/Office/Data/v64.cab` → 200)
- ClickToRun service running (`sc query ClickToRunSvc`)
- No VPN TUN interference

### Diagnosis when language switch doesn't take effect

```powershell
# Check what Office THINKS is installed
reg query "HKCU\SOFTWARE\Microsoft\Office\16.0\Common\LanguageResources" /s

# Key values to inspect:
#   UILanguageTag = zh-CN         (correctly set)
#   OutlookChangeInstallLanguage = YES  (waiting for download, NOT yet installed)
#   UISnapshotLanguages = en-us;zh-cn   (both listed)
#   InstalledLanguages subkey → EMPTY (this is the problem)

# If InstalledLanguages is empty but OutlookChangeInstallLanguage=YES:
# → Language pack download failed silently (VPN, CDN, C2R service issue)
# → Verify: Office CDN reachable, VPN off, restart ClickToRun service
# → Then re-open Outlook and wait for auto-download
```

### Verify language resources

```powershell
# Check if language directories exist
Get-ChildItem "C:\Program Files\Microsoft Office\root\Office16" -Directory | Where { $_.Name -match '^\d+$' }
# 1033 = English, 2052 = Chinese Simplified

# 2052 directory existing ≠ language is provisioned
# Look for app-specific MUI files (may not exist separately in C2R streaming):
Test-Path "C:\Program Files\Microsoft Office\root\Office16\2052"
```

### Check if language is actually provisioned

```powershell
Get-ChildItem "HKCU:\SOFTWARE\Microsoft\Office\16.0\Common\LanguageResources\InstalledLanguages"
# If empty → no language pack is properly registered → UI switch won't work
```

## Tencent Meeting plugin notes

- Supports classic Outlook only (COM add-in), NOT new Outlook (WebView2)
- Requires Tencent Meeting client 2.10.0+
- Download page: https://meeting.tencent.com/download/ (click "Windows Outlook插件")
- Download URLs are dynamically generated via obfuscated JavaScript; scraping is unreliable. Best to provide the download page URL to the user.

## References

- `references/office-proxy-debug.md` — detailed proxy debugging for Office 0x80190001
- `references/product-id-mismatch.md` — why ODT fails after OfficeSetup.exe consumer install (O365HomePremRetail vs O365ProPlusRetail), language pack provisioning failure diagnosis
- `references/language-pack-stuck-diagnosis.md` — real session evidence: registry says zh-CN, InstalledLanguages empty, OutlookChangeInstallLanguage: YES stuck forever
