---
name: path-sync
description: "Sync hardcoded paths in runtime skills/plugins between portable $VAR references (git) and local paths (runtime). Canonicalize before commit, localize after pull."
version: 2.0.0
author: Hermes Agent
---

# Path Sync — 两端路径同步（v2）

Git 中的文件使用 `$VAR` 便携占位符（如 `$HOME`, `$HERMES_HOME`），每台机器在自己的 `path-vars.yaml` 中维护本机路径映射。

## 配置

每台机器的 `$HERMES_HOME/path-vars.yaml`：

```yaml
variables:
  HOME: "$HOME"
  HERMES_HOME: "$HERMES_HOME"
  OBSIDIAN_VAULT: "$OBSIDIAN_VAULT"
  HORIZON_HOME: "$HORIZON_HOME"
  AGENTMEMORY_HOME: "$AGENTMEMORY_HOME"
  EDITABLE_HERMES: "$EDITABLE_HERMES"
```

模板文件: `user-config/path-vars.template.yaml`（git 中有，供参考）。

## 工作流

### Push 前（runtime → git）

```bash
# 1. 同步 runtime → git source
cd $HERMES_HOME
for pair in skills:user-skills plugins:user-plugins hooks:user-config/hooks scripts:user-config/scripts memories:user-config/memories; do
  src="${pair%%:*}"
  dst="${pair##*:}"
  rm -rf ../editable-hermes-agent/$dst
  cp -r $src ../editable-hermes-agent/$dst
done

# 2. 格式化路径为便携变量
cd ../editable-hermes-agent
HERMES_HOME=$HERMES_HOME python $HERMES_HOME/skills/devops/path-sync/scripts/canonicalize.py

# 3. 清理垃圾
find user-skills user-plugins \( -name ".hub" -o -name ".bundled_manifest" -o -name ".curator_backups" -o -name ".usage.json" -o -name "*.lock" -o -name "__pycache__" \) -exec rm -rf {} + 2>/dev/null

# 4. Commit
git add user-skills/ user-plugins/ user-config/
git commit -m "sync: user skills + plugins + config"
git push
```

### Pull 后（git → runtime）

```bash
# 1. Pull
cd editable-hermes-agent
git pull

# 2. 同步 git source → runtime
cd $HERMES_HOME
for pair in skills:user-skills plugins:user-plugins hooks:user-config/hooks scripts:user-config/scripts memories:user-config/memories; do
  src="${pair##*:}"
  dst="${pair%%:*}"
  rm -rf $dst
  cp -r ../editable-hermes-agent/$src $dst
done

# 3. 替换路径为本机路径
python skills/devops/path-sync/scripts/localize.py
```

## 脚本说明

| 脚本 | 方向 | 目标目录 | 功能 |
|------|------|----------|------|
| `canonicalize.py` | 本机路径 → `$VAR` | `user-skills/`, `user-plugins/`, `user-config/` | Push 前执行 |
| `localize.py` | `$VAR` → 本机路径 | `skills/`, `plugins/`, `scripts/`, `hooks/`, `memories/`, `profiles/` | Pull 后执行 |
| `sync.py` | (deprecated) | — | 旧版单向映射表，保留向后兼容 |

## 排除规则

`*.lock`, `*.hub`, `*.bundled_manifest`, `.usage.json`, `__pycache__` — 运行时垃圾，永远不同步。

## Pitfalls

- **`cp -r skills/` 会带进上游技能**：apple 系列、`.curator_state` 是上游 bundled skill，不在用户定制范围。sync 后检查 `git status`，如出现则 `git rm --cached` + `rm -rf` 排除。
- **目录结构变更导致 git rename**：如 horizon `horizon/` → `horizon/horizon/` 嵌套。`rm -rf + cp -r` 后 git 显示旧路径删除 + 新路径新增——正常，git 自行追踪即可。
- **canonicalize.py 需要 `HERMES_HOME` 环境变量**：它通过 `HERMES_HOME` 定位 `path-vars.yaml`。在 git source 目录下执行时务必 `HERMES_HOME=...`。
- **localize.py 只扫 runtime 目录**（`skills/`, `plugins/`, `scripts/`, `hooks/`, `memories/`, `profiles/`）。不要对 `user-skills/` 等 git 目录跑 localize——扫到空的 0 files。
- **斜杠归一化**：localize.py 输出统一正斜杠 `/`。round-trip 比较时需 normalize slash，语义一致。
