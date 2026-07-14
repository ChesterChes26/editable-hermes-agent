# Hermes Runtime Junction 方案

## 目标

让 `git status` 反映真实 runtime 状态，消灭 user-* 镜像与 runtime 的漂移问题。

只维护 1 份 repo：`hermes-agent`

## 核心设计

**反向 junction**：runtime 目录 → repo 里的 user-* 目录

```
~/.hermes/skills/              →  ~/.hermes/hermes-agent/user-skills/
~/.hermes/plugins/             →  ~/.hermes/hermes-agent/user-plugins/
~/.hermes/hooks/               →  ~/.hermes/hermes-agent/user-config/hooks/
~/.hermes/scripts/             →  ~/.hermes/hermes-agent/user-config/scripts/
~/.hermes/memories/USER.md     →  ~/.hermes/hermes-agent/user-config/memories/USER.md
```

Hermes 读写 runtime 目录，Git track repo 里的 user-* junction。

## Git Track 策略（白名单）

### ✅ Track

| 目录/文件 | 内容 |
|----------|------|
| `user-skills/*/SKILL.md` | Skill 定义 |
| `user-skills/*/DESCRIPTION.md` | Skill 描述 |
| `user-skills/*/references/**` | Skill 参考资料 |
| `user-skills/*/templates/**` | Skill 模板 |
| `user-plugins/*/*.py` | Plugin 代码 |
| `user-plugins/*/plugin.yaml` | Plugin 配置 |
| `user-plugins/*/README.md` | Plugin 文档 |
| `user-plugins/*/requirements.txt` | Plugin 依赖 |
| `user-config/hooks/*/*.py` | Hook 代码 |
| `user-config/hooks/*/HOOK.yaml` | Hook 配置 |
| `user-config/hooks/*/README.md` | Hook 文档 |
| `user-config/scripts/*.py` | 脚本 |
| `user-config/scripts/*.sh` | Shell 脚本 |
| `user-config/memories/USER.md` | 用户偏好（default profile） |

### ❌ 不 Track

| 目录/文件 | 原因 |
|----------|------|
| `user-config/config.yaml` | 包含 API keys |
| `user-config/memories/MEMORY.md` | 技术笔记，不进 Git |
| `user-config/memories/*.lock` | 运行时锁文件 |
| `user-config/profiles/*/memories/*` | 包含 Bearer token（worker） |
| `user-config/profiles/*/config.yaml` | 包含 API keys |
| `user-config/profiles/*/.env` | 环境变量 |
| `user-config/cron/jobs.json` | 运行状态频繁变化 |
| `user-config/cron/output/` | Cron 执行输出 |
| `user-config/cron/*.lock` | 锁文件 |
| `*.pyc`, `__pycache__/` | Python 字节码 |
| `.usage.json`, `.bundled_manifest` | 运行时状态 |

## 实施步骤

### Step 1: 备份当前状态

```bash
cd C:/Users/chester.chen/AppData/Local/hermes
cp -r skills skills.bak.$(date +%Y%m%d)
cp -r plugins plugins.bak.$(date +%Y%m%d)
cp -r hooks hooks.bak.$(date +%Y%m%d)
cp -r scripts scripts.bak.$(date +%Y%m%d)
cp -r memories memories.bak.$(date +%Y%m%d)
```

### Step 2: 清理 repo 里的 user-* 目录

```bash
cd C:/Users/chester.chen/AppData/Local/hermes/hermes-agent

# 删除现有 user-* 镜像（会被 junction 替换）
rm -rf user-skills
rm -rf user-plugins
rm -rf user-config/hooks
rm -rf user-config/scripts
rm -rf user-config/memories
```

### Step 3: 创建目录级 junction

```bash
# 在 repo 里创建 junction 指向 runtime
cd C:/Users/chester.chen/AppData/Local/hermes/hermes-agent

# Windows junction: mklink /J <link> <target>
# 注意：junction 在 repo 里，指向 runtime 目录

cmd /c "mklink /J user-skills ..\skills"
cmd /c "mklink /J user-plugins ..\plugins"
cmd /c "mklink /J user-config\hooks ..\..\hooks"
cmd /c "mklink /J user-config\scripts ..\..\scripts"
cmd /c "mklink /J user-config\memories ..\..\memories"
```

### Step 4: 配置 .gitignore（白名单）

在 `hermes-agent/.gitignore` 添加：

```gitignore
# === 默认忽略所有 user-* 内容 ===
user-skills/*
user-plugins/*
user-config/hooks/*
user-config/scripts/*
user-config/memories/*

# === 白名单：允许 track 的文件 ===

# Skills
!user-skills/*/SKILL.md
!user-skills/*/DESCRIPTION.md
!user-skills/*/references/
!user-skills/*/references/**
!user-skills/*/templates/
!user-skills/*/templates/**

# Plugins
!user-plugins/*/*.py
!user-plugins/*/plugin.yaml
!user-plugins/*/README.md
!user-plugins/*/requirements.txt

# Hooks
!user-config/hooks/*/*.py
!user-config/hooks/*/HOOK.yaml
!user-config/hooks/*/README.md

# Scripts
!user-config/scripts/*.py
!user-config/scripts/*.sh
!user-config/scripts/README.md

# Memories (只 track USER.md)
!user-config/memories/USER.md

# === 显式排除（双保险） ===

# 隐私文件
user-config/memories/MEMORY.md
user-config/memories/*.lock
user-config/profiles/*/memories/
user-config/profiles/*/config.yaml
user-config/profiles/*/.env

# 运行时状态
*.pyc
__pycache__/
*.lock
.usage.json
.bundled_manifest
.curator_state
.curator_backups/
.hub/
```

### Step 5: 验证

```bash
cd C:/Users/chester.chen/AppData/Local/hermes/hermes-agent

# 检查 junction 是否正确
ls -la user-skills user-plugins user-config/hooks user-config/scripts user-config/memories

# 检查 Git 能看到什么
git status

# 确认没有隐私文件被 track
git ls-files | grep -E "(MEMORY\.md|\.lock|config\.yaml|profiles/)"

# 确认没有 API keys
git grep -i "api_key\|sk-\|token" -- 'user-*/'
```

### Step 6: 提交

```bash
cd C:/Users/chester.chen/AppData/Local/hermes/hermes-agent
git add user-skills user-plugins user-config
git status
git commit -m "refactor: junction runtime dirs to user-*, eliminate mirror sync"
git push origin chester
```

## 新机器恢复流程

```bash
# 1. Clone repo
git clone https://github.com/ChesterChes26/editable-hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
git checkout chester

# 2. 创建 runtime 目录
mkdir -p ~/.hermes/{skills,plugins,hooks,scripts,memories}

# 3. 重建 junction
cd ~/.hermes/hermes-agent
cmd /c "mklink /J user-skills ..\skills"
cmd /c "mklink /J user-plugins ..\plugins"
cmd /c "mklink /J user-config\hooks ..\..\hooks"
cmd /c "mklink /J user-config\scripts ..\..\scripts"
cmd /c "mklink /J user-config\memories ..\..\memories"

# 4. 手动配置敏感文件
cp user-config/config.yaml.template ~/.hermes/config.yaml
# 编辑 config.yaml 填入 API keys

# 5. 安装 Hermes
uv sync --directory .

# 6. 启动
hermes gateway start
```

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| Junction 被工具意外替换成真实目录 | 恢复脚本自动重建 junction |
| Git clone 时 user-* 目录已存在 | 恢复脚本先删除再创建 junction |
| 误提交隐私文件 | 白名单 .gitignore + pre-commit hook 检查 |
| Junction 路径硬编码 | 恢复脚本动态生成 |

## 待确认

1. **config.yaml**：是否需要 track 脱敏模板？还是完全不 track？
2. **profiles/worker/skills/**：是否 track？（worker profile 的 skills）
3. **cron/jobs.json**：是否 track job 定义部分？还是完全不 track？

## 日常使用

修改 skill/plugin/hook/script 后：

```bash
cd C:/Users/chester.chen/AppData/Local/hermes/hermes-agent
git status
git add <changed files>
git commit -m "sync: update skill/plugin/hook/script"
git push origin chester
```

`git status` 现在反映真实 runtime 状态。
