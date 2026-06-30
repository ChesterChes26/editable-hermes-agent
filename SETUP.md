# Hermes 私人配置还原指南

本仓库是基于 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的私有 fork，
包含自定义源码改动、agentmemory 插件、全套 skills 和运行时配置。

> **Windows 路径说明**：Windows 下 `~/.hermes/` 实际映射为 `~/AppData/Local/hermes/`。
> 下文脚本用 `~/.hermes/` 书写，Windows 终端中需替换为 `~/AppData/Local/hermes/`（Git Bash 下 `~/.hermes/` 也能用）。

## 仓库结构

```
hermes-agent/              # Hermes Agent 源码（含自定义改动）
├── agent/agent_init.py    # agentmemory provider 集成
├── gateway/platforms/
│   ├── weixin.py          # WeChat ITEM_NOTE + obsidian-sync 自动加载
│   └── qqbot/adapter.py   # QQ Bot 定制
├── user-plugins/          # 自定义插件
│   ├── agentmemory/       # 持久化跨 session 记忆
│   └── horizon/           # AI 资讯聚合 (Horizon MCP)
├── user-skills/           # 默认 profile 已安装 skills
├── user-config/           # 运行时配置（同步到 runtime 目录）
│   ├── config.yaml        # 主配置（已脱敏）
│   ├── hooks/             # Gateway 事件钩子
│   ├── cron/              # 定时任务
│   ├── scripts/           # 自定义脚本
│   ├── profiles/worker/   # worker profile 完整配置
│   └── memories/          # 持久 memory 源文件
└── SETUP.md               # 本文件
```

## 还原步骤

### 1. 安装 Hermes Agent

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

Windows 下参考官方文档安装。

### 2. 替换为自定义版本

```bash
# 备份原始安装
mv ~/.hermes/hermes-agent ~/.hermes/hermes-agent.bak

# Clone 本仓库
git clone https://github.com/ChesterChes26/editable-hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
git checkout chester
```

### 3. 同步运行时文件

> **关键概念**：Hermes 有两层目录——git 仓库里的 `user-*` 目录（版本控制用）
> 和 runtime 目录（Hermes 实际读写）。两者是独立副本，没有自动同步。
> 换机还原时需把 git 仓库内容复制到 runtime 目录，日常修改 skill/plugin 后需反向同步。

```bash
cd ~/.hermes

# === plugins ===
mkdir -p plugins
cp -r hermes-agent/user-plugins/* plugins/

# === skills ===
rm -rf skills
cp -r hermes-agent/user-skills skills
# 注：computer-use 是上游 bundled skill，runtime skills/ 中有但 user-skills/ 中无，不需同步

# === hooks ===
mkdir -p hooks
cp -r hermes-agent/user-config/hooks/* hooks/

# === scripts ===
mkdir -p scripts
cp hermes-agent/user-config/scripts/* scripts/

# === memories ===
mkdir -p memories
cp hermes-agent/user-config/memories/* memories/

# === config.yaml ===
cp hermes-agent/user-config/config.yaml config.yaml

# === cron ===
cp hermes-agent/user-config/cron/jobs.json cron/

# === worker profile ===
rm -rf profiles/worker
mkdir -p profiles/worker
cp hermes-agent/user-config/profiles/worker/config.yaml profiles/worker/
cp -r hermes-agent/user-config/profiles/worker/skills profiles/worker/skills
```

### 4. 配置 API Keys（手动）

`~/.hermes/.env` 需要包含（不进入仓库，需手动填写）：

```
DEEPSEEK_API_KEY=*** 以及其他 provider 的 key
```

### 5. 配置 agentmemory 服务

agentmemory 是独立服务，**无需 fork**——直接从 Docker Hub 拉镜像，npm 装 worker 即可。
它的架构是三层：

```
plugin（本仓库提供）  →  HTTP :3111  →  worker（npx）  →  iii-engine（Docker）
  user-plugins/agentmemory/              @agentmemory/agentmemory    rohitg00/agentmemory
  2个文件，Hermes 适配层                  Node.js 进程，注册路由        Rust 引擎，存储/索引/衰减
```

```bash
# 1. 启动 Docker 引擎
docker run -d --name agentmemory -p 3111:3111 rohitg00/agentmemory:latest

# 2. 创建配置文件
mkdir -p ~/.agentmemory
cat > ~/.agentmemory/.env << 'EOF'
OPENAI_API_KEY=<deepse...n
# 3. 启动 worker
AGENTMEMORY_USE_DOCKER=1 npx @agentmemory/agentmemory &

# 4. 验证
sleep 5
curl -s -o /dev/null -w "%{http_code}" http://localhost:3111/agentmemory/smart-search \
  -X POST -H "Content-Type: application/json" -d '{"query":"test","limit":1}'
# 应返回 200
```

#### Docker Volume 备份与还原（迁移记忆数据）

agentmemory 的所有记忆（observations、semantic memories 等）持久化在 Docker volume 中，
不在 `~/.hermes/` 下。换机时可通过 volume 备份保留记忆：

```bash
# === 旧机导出 ===
docker cp agentmemory-iii-engine-1:/app/data ./agentmemory-data-backup

# === 新机导入 ===
# 先按上面的步骤启动 Docker + worker，然后：
docker cp ./agentmemory-data-backup/. agentmemory-iii-engine-1:/app/data/
docker restart agentmemory-iii-engine-1
# worker 不需要重启，它自动重连
```

备份目录通常很小（几十 MB），可以随 dotfiles 一起打包带走。

### 6. 启动 Gateway

```bash
hermes gateway start
```

## 增量同步（日常修改后 commit + push）

修改 skill / plugin / hook / script / memory 后，runtime 目录有改动但 git 仓库看不到。
**`git status` 报 clean 不等于没有改动**——必须跨目录 diff 后再 commit。

### 检查哪些目录有差异

```bash
cd ~/AppData/Local/hermes  # Windows（macOS: ~/.hermes）

for pair in \
  "skills:user-skills" \
  "plugins:user-plugins" \
  "hooks:user-config/hooks" \
  "scripts:user-config/scripts" \
  "memories:user-config/memories"
do
  runtime="${pair%%:*}"
  gt="${pair##*:}"
  result=$(diff -rq --exclude=__pycache__ "$runtime/" "hermes-agent/$gt/" 2>&1 \
    | grep -v ".lock\|.hub\|.bundled_manifest\|.curator\|.usage.json" | head -1)
  if [ -n "$result" ]; then
    echo "❌ $runtime — 需要同步"
  else
    echo "✓ $runtime"
  fi
done
```

### 同步并推送

```bash
cd ~/AppData/Local/hermes

# 同步改动的目录（示例）
rm -rf hermes-agent/user-skills/research/wiki-guide-split
cp -r skills/research/wiki-guide-split hermes-agent/user-skills/research/wiki-guide-split

# 新增的目录也一样
cp -r skills/note-taking/new-skill hermes-agent/user-skills/note-taking/new-skill

# commit + push
cd hermes-agent
git add -A
git commit -m "sync: <描述改动>"

# GitHub 被墙则走代理
git config http.proxy http://127.0.0.1:7897
git push origin chester
```

**排除的垃圾文件**：`.lock`、`.hub`、`.bundled_manifest`、`.curator_backups`、`.usage.json`、
`__pycache__` 是 runtime 产物，**永远不要复制到 git 仓库**。

## 更新上游

```bash
cd ~/.hermes/hermes-agent
git fetch upstream
git checkout main
git merge upstream/main

# 切回 chester 分支
git checkout chester
git rebase main

# ⚠️ 合并后必须更新 venv（上游可能改了 pyproject.toml）
uv sync --directory .
# 验证
hermes --version
```

## 不需要进入仓库的文件

以下文件包含敏感信息或运行时状态，未进入仓库：

- `~/.hermes/.env` — API keys（需手动填写）
- `~/.hermes/auth.json` — OAuth token
- `~/.hermes/state.db` — 会话历史
- `~/.hermes/channel_directory.json` — WeChat/QQ 用户 openid
- `~/.hermes/gateway_state.json` — Gateway 运行时 PID
- agentmemory Docker 镜像 / npm 包 — 从 Docker Hub/npm 直接安装，无需 fork
- agentmemory Docker volume（记忆数据） — 通过 `docker cp` 单独备份迁移

## 注意事项

- **GitHub 被墙**：直连 github.com 可能超时，push 前需 `git config http.proxy http://127.0.0.1:7897`
- **Git 身份**：Windows 下 git 可能自动生成 `T04081 <Chester.Chen@augmentum.com.cn>`。
  在新机器上手动设置：`git config user.name "xxx"` / `git config user.email "xxx@xxx"`
- **computer-use skill**：runtime `skills/computer-use/` 是上游 bundled skill，
  不在 `user-skills/` 中。diff 时出现 `Only in skills/: computer-use` 属正常，不需同步。
- **uv sync 别忘了**：上游合并后 `pyproject.toml` / `uv.lock` 更新了但 venv 没更新，
  可能 `ImportError`。务必 `uv sync`。
- **MEMORY.md / USER.md 含个人信息**：这两个文件在 git 中跟踪，push 前确认 fork 是 private。
