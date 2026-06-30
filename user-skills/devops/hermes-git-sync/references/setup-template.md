# Hermes 私人配置还原指南

本仓库是基于 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的私有 fork，
包含自定义源码改动、插件、skills 和运行时配置。

> **Windows 路径**：`~/.hermes/` 实际为 `~/AppData/Local/hermes/`。

## 仓库结构

```
├── agent/agent_init.py     # 可能的源码改动
├── gateway/platforms/      # WeChat/QQ 等平台适配器
├── user-plugins/           # 自定义插件
├── user-skills/            # 所有已安装 skills
├── user-config/            # 运行时配置
│   ├── config.yaml
│   ├── hooks/
│   ├── cron/
│   ├── scripts/
│   ├── profiles/worker/
│   └── memories/
└── SETUP.md
```

## 还原步骤

### 1. 安装 Hermes → Clone 仓库 → Checkout 分支

```bash
git clone <fork-url> ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent && git checkout <branch>
```

### 2. 同步运行时文件（五组目录）

```bash
cd ~/.hermes
cp -r hermes-agent/user-plugins/* plugins/
cp -r hermes-agent/user-skills skills
cp -r hermes-agent/user-config/hooks/* hooks/
cp hermes-agent/user-config/scripts/* scripts/
cp hermes-agent/user-config/memories/* memories/
cp hermes-agent/user-config/config.yaml config.yaml
cp hermes-agent/user-config/cron/jobs.json cron/
```

### 3. 手动配置 .env → 启动

## 增量同步（日常修改后）

修改 skill/plugin/script/memory 后 runtime 目录有改动但 `git status` 看不到。
跨目录 diff → cp → commit → push。详见 `hermes-git-sync` skill 的 Incremental sync 章节。

## 不需要进入仓库的文件

- `.env` — API keys
- `auth.json` — OAuth tokens
- `state.db` — 会话历史
- `channel_directory.json` — 用户 openid
- `gateway_state.json` — Gateway PID
