# agentmemory Worker Lifecycle Debugging Transcript

Session: 2026-06-22, new session verification → automation
Goal: Verify prefetch injection, MCP tool restoration, sync_turn capture → automate worker recovery

## Phase 1: Diagnosis

### Symptom

memory_search/memory_save/memory_recall 在工具列表中，但调用返回 `{"results": []}` 或 `{"success": false}`。agent.log 显示工具 "completed" (2-7s, 15-18 chars 返回体)，无报错。

### Root Cause Chain

```
旧 gateway 被杀
  → @agentmemory/agentmemory worker 断开
  → Docker 里所有 REST API 路由注销
  → 新 session memory provider plugin 初始化
  → session/start → 404（无 worker）
  → 工具在列表里但调用全返回空/false
  → sync_turn 调 observe → 404，静默失败
```

### Docker 日志证据

两个 worker 先后注册：

- Worker #1 (pid 89328): 注册所有路由 → 0.4s 后注销
- Worker #2 (pid 75356): 注册所有核心+高级路由 → 存活 37 分钟 → 在新 session 启动时注销

Worker #2 注销后无新 "Worker registered" — 确认 root cause 是 worker 没被自动拉起。

### MCP args 是 Red Herring

errors.log 同时有 MCP 连接失败（Pydantic list_type），但上一个 session 也有同样错误，当时工具正常。Memory provider plugin 走 REST API（直连 Docker），不经过 MCP transport。

## Phase 2: Automation Attempts

### Attempt 1: gateway:startup Hook → 失败

创建 hook `agentmemory-worker/handler.py`，监听 `gateway:startup` 事件，检测 worker 不在线时自动 spawn。

**失败原因：**
- Hook 加载成功（"1 hook(s) loaded"），但 handler 的 `print(..., file=sys.stderr)` 输出完全失踪
- Gateway 进程的 PATH 里没有 npx（`subprocess.Popen(["npx", ...])` → `[WinError 2] 系统找不到指定的文件`）
- 未进一步排查——hook 黑盒调试成本高于 cronjob 方案

### Attempt 2: Cronjob Watchdog → 成功

脚本 `scripts/agentmemory-watchdog.py`：
- 每分钟 cron tick
- 检查 `curl localhost:3111/agentmemory/smart-search`
- 200 → 静默退出（worker 在线）
- 404 → 用绝对路径 `C:\Program Files\nodejs\npx.cmd` 启动 worker → 等 60s 上线 → 报告结果

**踩过的坑：**
1. Script 路径加倍：cronjob `script` 参数相对 `scripts/` 目录，传 `scripts/agentmemory-watchdog.py` 变成 `<scripts>/scripts/...`
2. npx 不在 PATH：需用绝对路径 `C:\Program Files\nodejs\npx.cmd`
3. Worker 生命周期：`subprocess.Popen` 启动的进程不在 Hermes managed process 列表里，gateway 重启不杀它。正常情况下 watchdog tick 发现 worker 活着就跳过。

### Worker 生命周期对比

| 启动方式 | 进程管理 | gateway 重启影响 |
|----------|---------|-----------------|
| `terminal(background=true)` | Hermes managed | 被杀 |
| `subprocess.Popen` (hook/cron) | 独立进程 | 不受影响 |

Cronjob watchdog 用的是 `subprocess.Popen`，所以 worker 常驻——只有机器重启、自身崩溃或手动 taskkill 才会挂，watchdog 60s 内救活。

### 验证

```
14:39  手动 kill worker → API 404
14:45  cron tick → 检测到 down → spawn worker → 等待上线 → "Worker online"
       Docker: [06:45:49 AM] Worker registered
       API: 200 ✅
```

## Key Architectural Insight

```
┌──────────────────────┐
│ Docker: iii-engine   │  ← 只跑框架，路由表初始为空
│ 监听 :3111           │
└──────┬───────────────┘
       │ worker 连接后动态注册路由
┌──────▼───────────────┐
│ Worker 进程 (Node)   │  ← npx @agentmemory/agentmemory
│ 注册: smart-search   │
│       remember       │
│       search         │
│       observe        │
│       session/*      │
│ 断开 → 全部注销       │
└──────────────────────┘
```

没有 worker = 全端点 404。这不是 "服务挂了"，是 "服务员下班了但店门开着"。
