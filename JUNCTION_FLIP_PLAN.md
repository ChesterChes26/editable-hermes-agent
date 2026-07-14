# Junction Flip Status

This document records the completed Hermes runtime junction layout for this
private fork.

## Paths

```text
RUNTIME = C:\Users\chester.chen\AppData\Local\hermes
REPO    = C:\Users\chester.chen\AppData\Local\hermes\hermes-agent
TARGET  = C:\Users\chester.chen\AppData\Local\hermes\hermes-agent\customized-junction
```

## Current Junction Graph

All five mutable runtime directories are junctions to sibling directories under
`customized-junction`.

```text
RUNTIME\skills   -> REPO\customized-junction\skills
RUNTIME\plugins  -> REPO\customized-junction\plugins
RUNTIME\hooks    -> REPO\customized-junction\hooks
RUNTIME\memories -> REPO\customized-junction\memories
RUNTIME\scripts  -> REPO\customized-junction\scripts
```

`RUNTIME\config.yaml` is intentionally not part of this junction set. It remains
a normal runtime root file. The tracked template/copy in `REPO\user-config` is
legacy configuration material and is not the live runtime file unless copied
manually.

## Repository Layout

```text
hermes-agent\
  customized-junction\
    skills\
    plugins\
    hooks\
    memories\
    scripts\
  user-config\
    config.yaml
    cron\
    profiles\
    path-vars.template.yaml
```

`user-config\hooks`, `user-config\memories`, and `user-config\scripts` were
moved into `customized-junction`. `user-config` now only carries non-junction
configuration/profile material.

## Verification Commands

Run these from PowerShell:

```powershell
$Runtime = 'C:\Users\chester.chen\AppData\Local\hermes'
$Repo = Join-Path $Runtime 'hermes-agent'

foreach ($name in @('skills','plugins','hooks','memories','scripts')) {
  $item = Get-Item -LiteralPath (Join-Path $Runtime $name) -Force
  $target = if ($item.Target) { $item.Target -join ',' } else { '' }
  Write-Host "$name`t$($item.LinkType)`t$target"
}
```

Expected targets:

```text
skills   Junction  ...\hermes-agent\customized-junction\skills
plugins  Junction  ...\hermes-agent\customized-junction\plugins
hooks    Junction  ...\hermes-agent\customized-junction\hooks
memories Junction  ...\hermes-agent\customized-junction\memories
scripts  Junction  ...\hermes-agent\customized-junction\scripts
```

Runtime content checks:

```powershell
Test-Path "$Runtime\memories\MEMORY.md"
(Get-Item "$Runtime\memories\MEMORY.md").Length
Test-Path "$Runtime\scripts\agentmemory-watchdog.py"
```

Known current counts after the flip:

```text
skills   748 files
plugins  6 files
hooks    3 files
memories 2 files
scripts  2 files
```

## Git Tracking Rules

`.gitignore` is written for `customized-junction`:

- track skill/plugin/hook/script source files that belong in the fork
- ignore runtime state such as `.hub`, `.usage.json`, `.curator_*`
- ignore generated files such as `__pycache__`, `*.pyc`, `*.lock`
- ignore runtime memory data such as `MEMORY.md`
- ignore snapshot/example-snapshot output

Check the split with:

```powershell
$paths = @(
  'customized-junction/skills',
  'customized-junction/plugins',
  'customized-junction/hooks',
  'customized-junction/memories',
  'customized-junction/scripts'
)
git -C $Repo ls-files --others --exclude-standard -- $paths
git -C $Repo ls-files --others --ignored --exclude-standard -- $paths
```

## Rebuild Procedure

Stop Hermes and agentmemory processes first. Then recreate the junctions:

```powershell
$Runtime = 'C:\Users\chester.chen\AppData\Local\hermes'
$Repo = Join-Path $Runtime 'hermes-agent'
$Target = Join-Path $Repo 'customized-junction'

$map = @{
  skills = Join-Path $Target 'skills'
  plugins = Join-Path $Target 'plugins'
  hooks = Join-Path $Target 'hooks'
  memories = Join-Path $Target 'memories'
  scripts = Join-Path $Target 'scripts'
}

foreach ($name in $map.Keys) {
  $runtimePath = Join-Path $Runtime $name
  if (Test-Path -LiteralPath $runtimePath) {
    [System.IO.Directory]::Delete($runtimePath, $false)
  }
  New-Item -ItemType Junction -Path $runtimePath -Target $map[$name] | Out-Null
}
```

## Backups

Original full runtime backups from the first flip are still under:

```text
C:\Users\chester.chen\AppData\Local\hermes\*.bak.20260714_112345
```

The second migration also created a safety copy under:

```text
D:\tmp\hermes-customized-junction-migration-20260714_133335
```

Keep these until the pushed branch has been verified on another machine.
