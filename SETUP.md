# Hermes 私人配置恢复指南

本仓库是 `NousResearch/hermes-agent` 的私人 fork，包含自定义源码改动、
agentmemory 插件、skills、hooks、scripts 和运行时配置材料。

Windows 路径说明：`~/.hermes` 对应
`C:\Users\chester.chen\AppData\Local\hermes`。

## 当前目录结构

```text
hermes-agent/
├── customized-junction/        # 5 个 runtime junction 的同级目标
│   ├── skills/                 # runtime\skills
│   ├── plugins/                # runtime\plugins
│   ├── hooks/                  # runtime\hooks
│   ├── memories/               # runtime\memories
│   └── scripts/                # runtime\scripts
├── user-config/                # 非 junction 配置/Profile 材料
│   ├── config.yaml             # 参考配置；不是 live runtime config
│   ├── cron/
│   ├── profiles/
│   └── path-vars.template.yaml
├── JUNCTION_FLIP_PLAN.md       # junction 布局、验证和重建说明
└── SETUP.md
```

Live runtime 关系：

```text
C:\Users\chester.chen\AppData\Local\hermes\skills
  -> hermes-agent\customized-junction\skills
C:\Users\chester.chen\AppData\Local\hermes\plugins
  -> hermes-agent\customized-junction\plugins
C:\Users\chester.chen\AppData\Local\hermes\hooks
  -> hermes-agent\customized-junction\hooks
C:\Users\chester.chen\AppData\Local\hermes\memories
  -> hermes-agent\customized-junction\memories
C:\Users\chester.chen\AppData\Local\hermes\scripts
  -> hermes-agent\customized-junction\scripts
```

`C:\Users\chester.chen\AppData\Local\hermes\config.yaml` 是 runtime 根目录下的普通文件，
不属于这 5 个 junction。`user-config/config.yaml` 只是仓库中的参考/恢复材料，
不会自动成为 live config。

## 新机器恢复

### 1. 安装 Hermes

按官方方式安装 Hermes。Windows native 安装后默认位于：

```text
C:\Users\<you>\AppData\Local\hermes
```

### 2. 替换为本 fork

```powershell
$Runtime = "$env:LOCALAPPDATA\hermes"

Rename-Item -LiteralPath "$Runtime\hermes-agent" -NewName "hermes-agent.bak"
git clone https://github.com/ChesterChes26/editable-hermes-agent.git "$Runtime\hermes-agent"
git -C "$Runtime\hermes-agent" checkout chester
```

### 3. 建立 junction

先停止 Hermes/gateway/agentmemory 相关进程，然后执行：

```powershell
$Runtime = "$env:LOCALAPPDATA\hermes"
$Repo = Join-Path $Runtime "hermes-agent"
$Target = Join-Path $Repo "customized-junction"

$map = @{
  skills = Join-Path $Target "skills"
  plugins = Join-Path $Target "plugins"
  hooks = Join-Path $Target "hooks"
  memories = Join-Path $Target "memories"
  scripts = Join-Path $Target "scripts"
}

foreach ($name in $map.Keys) {
  $runtimePath = Join-Path $Runtime $name
  if (Test-Path -LiteralPath $runtimePath) {
    [System.IO.Directory]::Delete($runtimePath, $false)
  }
  New-Item -ItemType Junction -Path $runtimePath -Target $map[$name] | Out-Null
}
```

### 4. 恢复非 junction 配置

`config.yaml` 不在 junction 中，需要单独处理：

```powershell
$Runtime = "$env:LOCALAPPDATA\hermes"
$Repo = Join-Path $Runtime "hermes-agent"

Copy-Item -LiteralPath "$Repo\user-config\config.yaml" -Destination "$Runtime\config.yaml" -Force
Copy-Item -LiteralPath "$Repo\user-config\cron\jobs.json" -Destination "$Runtime\cron\jobs.json" -Force
```

Worker profile 仍在 `user-config/profiles/worker`：

```powershell
Remove-Item -LiteralPath "$Runtime\profiles\worker" -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path "$Runtime\profiles\worker" -Force | Out-Null
Copy-Item -LiteralPath "$Repo\user-config\profiles\worker\config.yaml" -Destination "$Runtime\profiles\worker\config.yaml" -Force
Copy-Item -LiteralPath "$Repo\user-config\profiles\worker\skills" -Destination "$Runtime\profiles\worker\skills" -Recurse -Force
```

Secrets still need to be supplied manually, normally in `~/.hermes/.env`.

## 日常同步

Because the five runtime directories are junctions, edits made through Hermes are
already made inside the git checkout. There is no more copy step for:

```text
skills
plugins
hooks
memories
scripts
```

Daily workflow:

```powershell
cd "$env:LOCALAPPDATA\hermes\hermes-agent"
git status --short
git add -A
git commit -m "sync: <change description>"
git push origin chester
```

If GitHub direct access times out, use the repo's proxy setting:

```powershell
git config http.proxy http://127.0.0.1:7897
git push origin chester
```

## 忽略规则

`.gitignore` tracks source/config files under `customized-junction` but ignores
runtime-only artifacts:

- `.hub/`
- `.usage.json`
- `.bundled_manifest`
- `.curator_state`
- `.curator_backups/`
- `MEMORY.md`
- `snapshots/`
- `_example_snapshots/`
- `__pycache__/`
- `*.pyc`
- `*.lock`

Use this check when unsure:

```powershell
$Repo = "$env:LOCALAPPDATA\hermes\hermes-agent"
$paths = @(
  "customized-junction/skills",
  "customized-junction/plugins",
  "customized-junction/hooks",
  "customized-junction/memories",
  "customized-junction/scripts"
)

git -C $Repo ls-files --others --exclude-standard -- $paths
git -C $Repo ls-files --others --ignored --exclude-standard -- $paths
```

The first command shows untracked files that would be committed. The second
shows ignored runtime files.

## agentmemory

The Hermes plugin lives in:

```text
customized-junction/plugins/agentmemory/
```

The agentmemory service itself is external and should be installed from npm /
Docker as usual. Its Docker volume is not stored in `~/.hermes` and must be
backed up separately if memory data needs to move between machines.

## 注意事项

- Stop Hermes/gateway/agentmemory before deleting or recreating junctions.
- `runtime\config.yaml` is a separate live file; compare it with
  `user-config\config.yaml` before overwriting.
- Keep backups under `runtime\*.bak.20260714_112345` and
  `D:\tmp\hermes-customized-junction-migration-20260714_133335` until this branch
  has been pushed and verified elsewhere.
- `MEMORY.md` / `USER.md` may contain personal data. Confirm the fork visibility
  before pushing.
