# Hermes 可复现配置完整清单

从把 Hermes 配置同步到 GitHub private repo 的实践中梳理出的完整清单。
比 `hermes-agent` 的 `migration.md` 多覆盖了 hooks/cron/scripts/profiles/memories。

## 需要进入仓库的

| 层 | 路径 | 说明 |
|---|------|------|
| 源码 diff | `hermes-agent/gateway/platforms/weixin.py` 等 | git diff 导出或 fork |
| 插件 | `~/.hermes/plugins/<name>/` | agentmemory 等自定义插件 |
| Skills | `~/.hermes/skills/` | 排除 `.hub/` 缓存（~24MB 无用） |
| Hooks | `~/.hermes/hooks/` | gateway 事件钩子（如 agentmemory-worker） |
| Cron | `~/.hermes/cron/jobs.json` | 定时任务定义 |
| Scripts | `~/.hermes/scripts/` | 自定义脚本（如 watchdog） |
| Profiles | `~/.hermes/profiles/<name>/` | 含 skills（排除 `.hub`）、config、memories |
| Config | `~/.hermes/config.yaml` | API key 全为空字符串可安全提交 |
| Memories | `~/.hermes/memories/` | MEMORY.md + USER.md |

## 绝不进入仓库的

- `.env` — 真正的 API key
- `auth.json` — OAuth token
- `state.db` — 会话历史 + 用户 openid
- `channel_directory.json` — WeChat/QQ 用户身份
- `gateway_state.json` — 运行时 PID

## agentmemory 不需要 fork

agentmemory 是三层架构：
- **Docker 镜像** (`rohitg00/agentmemory`) — iii-engine 框架
- **npm 包** (`@agentmemory/agentmemory`) — worker 进程
- **Hermes plugin** (2 文件) — HTTP client 桥接层

新机直接 `docker run` + `npx` 即可。plugin 的 2 文件在 Hermes 配置仓库里。
唯一丢的是 Docker volume 里的历史记忆。可备份迁移：

```bash
# 旧机导出
docker cp agentmemory-iii-engine-1:/app/data ./agentmemory-data-backup

# 新机导入（先启动 Docker + worker）
docker cp ./agentmemory-data-backup/. agentmemory-iii-engine-1:/app/data/
docker restart agentmemory-iii-engine-1
# worker 不需要重启，自动重连
```

备份目录通常几十 MB，可随配置仓库一起打包。

## 仓库结构建议

```
hermes-dotfiles/
├── plugins/agentmemory/     # plugin 文件
├── skills/                  # 排除 .hub 缓存
├── config/                  # hooks, cron, scripts, config.yaml, memories
├── profiles/worker/         # 排除 .hub 缓存
├── patches/                 # 源码 diff（可选）
├── setup.sh
└── README.md
```

setup.sh 只需 `cp -r` 到 `~/.hermes/` 对应位置。
