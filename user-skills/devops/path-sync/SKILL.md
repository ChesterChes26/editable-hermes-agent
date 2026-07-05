---
name: path-sync
description: "Sync hardcoded paths in runtime skills/plugins/scripts from git repo to local machine paths. Run after pulling updates from user-skills/user-config into runtime."
version: 1.0.0
author: Hermes Agent
---

# Path Sync — 运行时路径同步

从 git 仓库 `user-skills/`、`user-plugins/`、`user-config/` 同步内容到 runtime 后，
skill 中可能包含旧机器的硬编码路径，需要替换为当前机器路径。

## 路径映射表

| 旧路径 | 新路径 | 说明 |
|--------|--------|------|
| `D:\obsidian\2026` | `E:\new_workspace\obsidian-2026` | Obsidian vault |
| `D:/obsidian/2026` | `E:/new_workspace/obsidian-2026` | Obsidian vault (正斜杠) |
| `C:\Users\chester.chen` | `C:\Users\admin` | Windows 用户目录 |
| `C:/Users/chester.chen` | `C:/Users/admin` | Windows 用户目录 (正斜杠) |
| `D:\workspace\AI-research\Horizon` | *(待定)* | Horizon 项目 (暂未安装) |

> **添加新映射**: 换机后在此表追加旧路径→新路径的映射即可。

## 使用方式

### 1. 扫描差异（只读，不修改）

```bash
cd <HERMES_HOME>
python skills/devops/path-sync/scripts/sync.py --dry-run
```

### 2. 执行替换

```bash
cd <HERMES_HOME>
python skills/devops/path-sync/scripts/sync.py
```

### 3. 替换后验证

```bash
cd <HERMES_HOME>
python skills/devops/path-sync/scripts/sync.py --verify
```

## 排除规则

以下目录/文件不扫描：
- `skills/devops/horizon/` — horizon 未安装，跳过
- `plugins/horizon/` — 同上
- `*.lock`、`*.hub`、`*.bundled_manifest`、`.usage.json`、`__pycache__`

## 适用范围

- **扫描目录**: `skills/`、`plugins/`、`scripts/`、`hooks/`
- **文件类型**: `.md`、`.py`、`.yaml`、`.json`、`.sh`、`.bat`、`.mjs`

## 工作流

```
git pull → cp user-* → runtime/ → 运行 sync.py → 路径已适配本机 ✓
```

日常：修改 skill 后，先确认没有把本机路径写死进去。
如果写了绝对路径，优先用环境变量（如 `%USERPROFILE%`）或相对路径。
