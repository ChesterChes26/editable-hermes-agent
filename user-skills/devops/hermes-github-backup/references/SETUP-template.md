# Hermes 私人配置还原指南

本仓库是基于 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的私有 fork，
包含自定义源码改动、自定义插件、全套 skills 和运行时配置。

## 仓库结构

```
hermes-agent/              # Hermes Agent 源码（含自定义改动）
├── agent/                 # agent_init.py 等核心改动
├── gateway/platforms/     # weixin.py, qqbot 等平台适配器改动
├── user-plugins/          # 自定义插件
├── user-skills/           # 默认 profile 已安装 skills
├── user-config/           # 运行时配置（同步到 ~/.hermes/）
│   ├── config.yaml        # 主配置（已脱敏）
│   ├── hooks/             # Gateway 事件钩子
│   ├── cron/              # 定时任务
│   ├── scripts/           # 自定义脚本
│   ├── profiles/          # 其他 profile 配置
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
git clone <repo-url> ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
git checkout chester
```

### 3. 链接插件和 skills

```bash
# 自定义插件
mkdir -p ~/.hermes/plugins
cp -r user-plugins/* ~/.hermes/plugins/

# Skills（默认 profile）
rm -rf ~/.hermes/skills
cp -r user-skills ~/.hermes/skills

# 运行时配置
cp user-config/config.yaml ~/.hermes/config.yaml
cp -r user-config/hooks/* ~/.hermes/hooks/
cp user-config/cron/jobs.json ~/.hermes/cron/
cp user-config/scripts/* ~/.hermes/scripts/
cp user-config/memories/* ~/.hermes/memories/

# Worker profile（如有）
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

### 5. 配置外部服务

如有 agentmemory 等外部依赖，参照对应文档启动。

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
git checkout chester
git rebase main
# 解决冲突后
git push origin chester --force-with-lease
```

## 未进入仓库的文件

以下文件包含敏感信息或运行时状态：

- `~/.hermes/.env` — API keys（需手动填写）
- `~/.hermes/auth.json` — OAuth token
- `~/.hermes/state.db` — 会话历史
- `~/.hermes/channel_directory.json` — 平台用户 openid
- `~/.hermes/gateway_state.json` — Gateway 运行时 PID
