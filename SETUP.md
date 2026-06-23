# Hermes 私人配置还原指南

本仓库是基于 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的私有 fork，
包含自定义源码改动、agentmemory 插件和全套 skills。

## 仓库结构

```
hermes-agent/           # Hermes Agent 源码（含自定义改动）
├── agent/agent_init.py # agentmemory provider 集成
├── gateway/platforms/
│   ├── weixin.py       # WeChat ITEM_NOTE + obsidian-sync 自动加载
│   └── qqbot/adapter.py # QQ Bot 定制
├── user-plugins/       # 自定义插件
│   └── agentmemory/    # 持久化跨 session 记忆
├── user-skills/        # 所有已安装 skills（72 个）
└── SETUP.md            # 本文件
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

# skills
rm -rf ~/.hermes/skills
cp -r user-skills ~/.hermes/skills
```

### 4. 配置 API Keys（手动）

`~/.hermes/.env` 需要包含（不进入仓库，需手动填写）：

```
DEEPSEEK_API_KEY=sk-xxx
# 以及其他 provider 的 key
```

### 5. 配置 agentmemory 服务

agentmemory plugin 需要 Docker 运行：

```bash
docker run -d --name agentmemory -p 3111:3111 rohitg00/agentmemory:latest
```

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

以下文件包含敏感信息或运行时状态，已在 .gitignore 中排除：

- `~/.hermes/.env` — API keys
- `~/.hermes/config.yaml` — 含密钥引用
- `~/.hermes/state.db` — 会话历史
- `~/.hermes/channel_directory.json` — WeChat/QQ 用户 openid
- `~/.hermes/auth.json` — OAuth token
