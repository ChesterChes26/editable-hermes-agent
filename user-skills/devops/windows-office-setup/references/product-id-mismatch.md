# ODT Product ID Mismatch: Consumer vs Enterprise Office

## Problem

After installing Office via the consumer online installer (`OfficeSetup.exe`), ODT `/configure` consistently fails with exit code 127 — even with correct product IDs, language settings, and CDN accessibility.

## Root cause

The consumer installer (`OfficeSetup.exe` from `c2rsetup.officeapps.live.com`) creates a **different Click-to-Run product profile** than enterprise ODT deployments.

### What OfficeSetup.exe installs

```
ProductReleaseIds: O365HomePremRetail,OneNoteFreeRetail,ProPlusRetail
ClientCulture:     en-us (single language, no multi-language provisioning)
ScenarioCulture:   (EMPTY)
```

- `O365HomePremRetail` — the "Home" edition
  - `O365HomePremRetail.ExcludedApps: onedrive,teams,outlook` ← **Outlook excluded!**
- `ProPlusRetail` — the "Professional Plus" edition
  - `ProPlusRetail.ExcludedApps: groove` ← Only Groove excluded, Outlook included

Outlook is installed via `ProPlusRetail`, NOT `O365HomePremRetail`.

### What ODT default config targets

```xml
<Product ID="O365ProPlusRetail">  ← WRONG product for consumer install
```

`O365ProPlusRetail` is the **enterprise** SKU. It doesn't exist in consumer-installed Office → ODT fails.

### Even with correct Product ID, ODT fails

```xml
<Product ID="ProPlusRetail">  ← Correct, but still exit 127
  <Language ID="zh-cn" />
</Product>
```

The consumer Click-to-Run configuration is **locked for streaming**. The `ClientCulture: en-us` is baked into the initial install and ODT cannot modify it on consumer installs. Enterprise deployments (volume license, Configuration Manager) have a different provisioning path.

## The only reliable approach

After OfficeSetup.exe installation, all configuration changes (language packs, feature toggles) must go through the Office UI or built-in services — NOT ODT.

## Registry evidence of the mismatch

```powershell
# These keys reveal the actual product structure:
reg query "HKLM\SOFTWARE\Microsoft\Office\ClickToRun\Configuration" /v ProductReleaseIds
# → O365HomePremRetail,OneNoteFreeRetail,ProPlusRetail

reg query "HKLM\SOFTWARE\Microsoft\Office\ClickToRun\Configuration" /s | findstr ExcludedApps
# → O365HomePremRetail.ExcludedApps: onedrive,teams,outlook
# → ProPlusRetail.ExcludedApps: groove
```

## Language pack diagnosis transcript

After setting zh-CN via Outlook UI:

```
UILanguageTag:                zh-CN       ✓ Set
UISnapshotLanguages:          en-us;zh-cn ✓ Both listed
OutlookChangeInstallLanguage: YES         ← STUCK — download never completes
InstalledLanguages subkey:    EMPTY       ← Root cause — nothing actually provisioned

Files in 2052 directory: 153 (incomplete, missing outlook.exe.mui)
```

The `OutlookChangeInstallLanguage: YES` flag means Office *knows* it needs to download the pack but the download is silently failing. Likely causes in order:
1. VPN TUN mode intercepting C2R traffic
2. Office CDN unreachable in current network mode
3. ClickToRun service in a bad state
