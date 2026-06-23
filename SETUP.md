# Hermes 私人配置还原指南

本仓库是基于 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的私有 fork，
包含自定义源码改动、agentmemory 插件、全套 skills 和运行时配置。

## 仓库结构

```
hermes-agent/              # Hermes Agent 源码（含自定义改动）
├── agent/agent_init.py    # agentmemory provider 集成
├── gateway/platforms/
│   ├── weixin.py          # WeChat ITEM_NOTE + obsidian-sync 自动加载
│   └── qqbot/adapter.py   # QQ Bot 定制
├── user-plugins/          # 自定义插件
│   └── agentmemory/       # 持久化跨 session 记忆
├── user-skills/           # 默认 profile 已安装 skills（72 个）
├── user-config/           # 运行时配置（同步到 ~/.hermes/）
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

或 Windows 下参考官方文档安装。

### 2. 替换为自定义版本

```bash
# 备份原始安装
mv ~/.hermes/hermes-agent ~/.hermes/hermes-agent.bak

# Clone 本仓库
git clone https://github.com/ChesterChes26/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
git checkout chester
```

### 3. 链接插件和 skills

```bash
# agentmemory plugin
mkdir -p ~/.hermes/plugins
cp -r user-plugins/agentmemory ~/.hermes/plugins/agentmemory

# skills（默认 profile）
rm -rf ~/.hermes/skills
cp -r user-skills ~/.hermes/skills

# 运行时配置
cp user-config/config.yaml ~/.hermes/config.yaml
cp -r user-config/hooks/* ~/.hermes/hooks/
cp user-config/cron/jobs.json ~/.hermes/cron/
cp user-config/scripts/* ~/.hermes/scripts/
cp user-config/memories/* ~/.hermes/memories/

# worker profile
rm -rf ~/.hermes/profiles/worker
mkdir -p ~/.hermes/profiles/worker
cp user-config/profiles/worker/config.yaml ~/.hermes/profiles/worker/
cp -r user-config/profiles/worker/skills ~/.hermes/profiles/worker/skills
```

### 4. 配置 API Keys（手动）

`~/.hermes/.env` 需要包含（不进入仓库，需手动填写）：

```
DEEPSEEK_API_KEY=sk-xxx
# 以及其他 provider 的 key
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
OPENAI_API_KEY=<deepseek-key>
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-flash
EMBEDDING_PROVIDER=local
AGENTMEMORY_AUTO_COMPRESS=true
EOF

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

## 更新上游

```bash
cd ~/.hermes/hermes-agent
git fetch upstream
git checkout main
git merge upstream/main
# 切回 chester 分支，rebase 或 merge
git checkout chester
git rebase main
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
