# Language Pack Stuck Diagnosis

Evidence from a session where Chinese display language was set in Outlook's UI but
never actually downloaded/provisioned. The registry told one story; the filesystem told another.

## Symptoms

- Outlook UI stays English after setting Chinese in File → Options → Language
- Restarting Outlook doesn't help
- `OutlookChangeInstallLanguage: YES` persists across reboots

## Diagnostic registry snapshot (the smoking gun)

```
UISnapshotLanguages:          en-us;zh-cn        ← both listed, looks correct
UILanguageTag:                zh-CN              ← correctly set
OutlookChangeInstallLanguage: YES                ← STUCK — waiting for download
LangTuneUp:                   OfficeCompleted    ← looks fine but misleading
InstalledLanguages subkey:    EMPTY              ← THE PROBLEM
```

Key insight: `UILanguageTag = zh-CN` AND `OutlookChangeInstallLanguage = YES` mean
Office KNOWS it should switch to Chinese but the language pack resources were NEVER
downloaded. `InstalledLanguages` subkey being empty confirms zero provisioning.

## What did NOT work

- Setting `UILanguage = 2052` in registry — no effect without provisioned resources
- ODT /configure (any Product ID) — exit 127 repeatedly
- OfficeC2RClient /update — exit 0 but no change
- OfficeC2RClient /repair — exit 2
- Restarting ClickToRun service + re-opening Outlook — still stuck

## Root cause

Office was installed via OfficeSetup.exe (consumer installer), which creates:
- `O365HomePremRetail` (ExcludedApps: onedrive,teams,**outlook**)
- `ProPlusRetail` (ExcludedApps: groove only)

Outlook's language resources come from ProPlusRetail. ODT targeting `O365ProPlusRetail`
(a different product ID) fails because the product doesn't exist. ODT targeting
`ProPlusRetail` still fails because the consumer installer's streaming config
is locked differently from enterprise ODT deployments.

## What SHOULD have worked (but couldn't be confirmed)

1. Close all Office apps
2. Turn off VPN (TUN mode)
3. Open Outlook → File → Options → Language → Add Chinese → Install
4. Office downloads language pack through its own C2R update mechanism
5. Restart Outlook

Requirement: Office CDN (`officecdn.microsoft.com`) must be reachable from the machine.
Test: `curl http://officecdn.microsoft.com/pr/<AudienceId>/Office/Data/v64.cab` → 200.
