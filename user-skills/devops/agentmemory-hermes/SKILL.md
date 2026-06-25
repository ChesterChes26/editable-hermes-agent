---
name: agentmemory-hermes
description: "Install, configure, and operate agentmemory with Hermes Agent — Docker on Windows, MCP tools, MemoryProvider hooks, model switching, decay mechanics."
version: 1.8.0
tags: [agentmemory, hermes, memory, docker, windows, deepseek, mcp]
category: devops
---

# agentmemory + Hermes 集成

agentmemory 是 Rohit Ghumare 的本地 session 记忆系统（23K stars），作为 Hermes 的 MemoryProvider plugin 接入。存的是"agent 做了什么"，不是 curated 知识。

## 安装（Windows Docker 路径）

Windows 上 iii-engine（Rust 二进制）没有原生 x86_64 构建，必须用 Docker。

```bash
# 1. 创建配置
mkdir -p ~/.agentmemory
# ~/.agentmemory/.env
OPENAI_API_KEY=<deepseek-key>
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-flash  # 或 deepseek-chat，便宜够用
EMBEDDING_PROVIDER=local
AGENTMEMORY_AUTO_COMPRESS=true
CONSOLIDATION_ENABLED=true
GRAPH_EXTRACTION_ENABLED=true

# 2. 启动（另一个终端，或后台）
AGENTMEMORY_USE_DOCKER=1 npx @agentmemory/agentmemory

# 3. 验证
curl http://localhost:3111/health        # 应返回 OK
curl -X POST http://localhost:3111/agentmemory/smart-search \
  -H "Content-Type: application/json" -d '{"query":"test"}'
```

## Hermes 配置

用 `hermes config set`（不要手动改 config.yaml——会被保护拦截）：

```bash
# 1. MemoryProvider
hermes config set memory.provider agentmemory

# 2. MCP 工具（注意：此命令在当前 Hermes 版本可能不产生正确 YAML list）
hermes config set mcp_servers.agentmemory.command npx
# 以下命令可能将 args 存为 YAML string 而非 list，导致 Pydantic 拒绝
# 已知局限，不影响 memory provider plugin（plugin 走 REST，不经过 MCP）
hermes config set "mcp_servers.agentmemory.args" '["-y","@agentmemory/mcp"]'

# 3. 启用插件（Hermes home 在 AppData！）
hermes config set plugins.enabled '["agentmemory"]'
```

**关键陷井：** plugin 文件必须放在 Hermes 的 home 目录（通常是 `AppData/Local/hermes/plugins/agentmemory/`），不是 `~/.hermes/plugins/`。如果 `hermes memory status` 显示 "NOT installed"，检查路径：

```bash
hermes config path                    # 确认 home 目录
ls <home>/plugins/agentmemory/        # __init__.py + plugin.yaml 必须在这
```

## 六个 Hook（自动，Agent 不感知）

| hook | 触发 | 做什么 |
|------|------|--------|
| system_prompt_block | session 启动 | 注入项目上下文到 system prompt |
| prefetch | 每次 LLM 调用前 | 搜 agentmemory，注入 Top-5 相关记忆 |
| sync_turn | Agent 回复后 | 追踪式 daemon 线程记录对话（线程注册到 _pending_observes，完成后自动移除） |
| on_memory_write | 调用 memory 工具后 | 镜像 MEMORY.md 写入到 agentmemory |
| on_pre_compress | 上下文压缩前 | 重新注入关键记忆防丢失 |
| on_session_switch | session_id 变更 (/new, /resume, /branch) | reset=True 时：flush→session/end→clear→session/start；否则仅 session/start |
| on_session_end | session 结束（正常退出）或 /new 触发的 commit_memory_session | _flush_observes() 等所有 pending observe 完成 → session/end |

**Token 成本（两条路径，差别巨大）：**

| 路径 | 方法 | 触发 | 大小 | 每次 LLM 调用都带？ |
|------|------|------|------|---------------------|
| system_prompt_block | `POST /agentmemory/context` | session 启动时构建 system prompt | **无上限**，实测 5854 字符 ≈ 1463 tokens（SQLite 快照验证） | ✅ 每次 API 调用 |
| prefetch | `POST /agentmemory/smart-search` (limit=5) | 每轮对话开始前 | 最多 ~1000 字符（5×200） | ❌ 只在用户消息末尾注入一次 |

**system_prompt_block 是真正的 token 杀手。** 它随每次 LLM API 调用发送——不是每轮对话一次，是每次 tool call 循环都带。一个 4 次 tool call 的回合，光这一项就吃掉 5 × 1463 = 7315 tokens。对比 AGENTS.md 有 20K 硬上限，agentmemory 的 context 块**没有上限**——observations 越多，块越大，token 消耗线性增长。

**实测数据（来自 `state.db` 真实 system prompt 快照）：**

| 指标 | 值 | 来源 |
|------|-----|------|
| 总 system prompt | 25904 chars (~6476 tokens) | session `20260622_170830` |
| agentmemory block | 5854 chars (~1463 tokens) | 同上 |
| block 在 system prompt 中的位置 | offset 19963 ~ 25819 | 同上 |
| 缓存稳定前缀 | offset 0 ~ 19962 (stable tier + MEMORY + USER PROFILE) | 同上 |

**缓存失效机制（DeepSeek 专用）：** agentmemory block 位于 system prompt 的第 19963 个字符。前面 19962 个字符跨 session 不变（稳定前缀），但从第 19963 字符起——agentmemory 块的第 1 个字节——每多一个 observation 就变化。DeepSeek 的隐式前缀缓存要求前缀 token 序列完全一致才命中 → 每次新 session 都 **MISS** → 全量重算 ~6500 tokens 的 KV cache。

详见 `references/system-prompt-anatomy.md` — 完整源码调用链（8 步）、system prompt 三段解剖、精确 byte offset 图、常见陷阱（字符串误判）和 intra-session 稳定性数值验证。

### Session 成本精算工作流

当需要评估 agentmemory 的实际 token 开销（而非猜测）时，从 `state.db` 逐 session 计算：

```python
import sqlite3
db = sqlite3.connect('~/AppData/Local/hermes/state.db')

# 1. 列出所有含 agentmemory context 的 session（注意搜 <memory-context> 而非 <agentmemory-context>——后者是笔记文字的误报）
rows = db.execute("""
  SELECT id, api_call_count, system_prompt
  FROM sessions
  WHERE system_prompt LIKE '%<memory-context>%'
  ORDER BY started_at
""").fetchall()

total_waste = 0
for sid, calls, sp in rows:
    idx_am = sp.find('<memory-context>')
    idx_conv = sp.find('Conversation started:')
    am_size = idx_conv - idx_am if idx_am >= 0 and idx_conv > idx_am else 0
    waste = calls * am_size // 4  # chars → tokens (approx)
    total_waste += waste
    print(f'{sid[:30]}  calls={calls:4d}  am={am_size:5d} chars  waste={waste:8,d} tokens')

print(f'总浪费: {total_waste:,} tokens')
```

**典型发现：** agentmemory 的 token 开销占比通常很小（实测 6月22日仅 0.07%），因为 session 内 system prompt 稳定（sp-am 恒定 20048 chars 验证了这一点），缓存正常工作。真正的 token 大户是长链工具调用 session 本身的历史消息累积。

**诊断方法有两种：**

1. 调 API（需 worker 在线）：
```bash
curl -s -X POST http://localhost:3111/agentmemory/context \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"default","project":"C:\\\\Users\\\\<user>"}' | jq '.context | length'
```

2. 从 Hermes session DB 提取（不依赖 worker）：
```python
import sqlite3
db = sqlite3.connect('~/AppData/Local/hermes/state.db')
rows = db.execute("""
  SELECT id, length(system_prompt) as len
  FROM sessions WHERE system_prompt LIKE '%<memory-context>%'
  ORDER BY len DESC LIMIT 1
""").fetchone()
sp = db.execute("SELECT system_prompt FROM sessions WHERE id=?", (rows[0],)).fetchone()[0]
idx = sp.find('<memory-context>')
print(f'Block: {len(sp)-idx} chars, starts at offset {idx}')
```
返回的字符数 ÷ 4 ≈ token 估算。如果超过 10000 字符，考虑清理旧 observations。

**控制策略：**

### 临时关（只停 provider）
`hermes config set memory.provider ""` —— 停的是 memory 工具 + MemoryProvider hook。`/reset` 生效。**plugin 本身仍在**，六个 hook 注册未移除（session 重建时 system_prompt_block 不再调 /context，但 prefetch/sync_turn 等代码路径还在）。

### 永久关（禁用整个 plugin）
需要三步——缺一步 watchdog 会继续弹窗（见下文）：
```bash
# 1. 禁用 plugin
hermes config set plugins.enabled '[]'

# 2. 重启 gateway 生效
hermes gateway restart      # kill 旧 gateway
hermes gateway run &        # 后台启动（bash 里 &）
# 或在 Hermes 会话里: terminal(background=true, command="hermes gateway run")
```

这会把 agentmemory plugin 全部六个 hook（system_prompt_block、prefetch、sync_turn、on_memory_write、on_pre_compress、on_session_end）一起移除，token 开销完全清零。

**3. 暂停 watchdog cronjob（重要！否则每分钟弹 cmd 窗口）。** Watchdog 是独立于 Hermes plugin 的 cronjob，不会因为 plugin 禁用而自动停止。如果容器之后变 TCP-stuck，watchdog 会每 1 分钟触发 `npx.cmd` 重启尝试 → Windows 桌面每分钟一个 cmd 闪窗。

先用 `cronjob action=list` 找到 watchdog 的 job_id，然后 `cronjob action=pause job_id=<id>`。恢复时用 `cronjob action=resume`。

### 重新接入（从关闭状态恢复）

如果之前永久关了，现在要恢复完整功能：

```bash
# 1. 确保容器健康（优先重启，免得 TCP-stuck）
docker restart agentmemory-iii-engine-1

# 2. 验证端点
curl -s -X POST http://localhost:3111/agentmemory/smart-search \
  -H "Content-Type: application/json" -d '{"query":"h","limit":1}'

# 3. 恢复 Hermes 配置
hermes config set memory.provider agentmemory
hermes config set plugins.enabled '["agentmemory"]'

# 4. 重启 gateway（Windows: restart 只 kill 不 start，需手动 run）
hermes gateway restart 2>&1 || true   # kill 旧的
hermes gateway run &                   # 后台启动新的

# 5. 恢复 watchdog
# cronjob action=resume job_id=<watchdog_id>

# 6. 验证
hermes memory status   # 应显示 Provider: agentmemory, Plugin: installed ✓, Status: available ✓
```

**常见陷阱：** 恢复时只改 Hermes 配置但忘记重启容器 → watchdog 继续检测到死容器 → 继续弹窗。容器和配置要一起恢复。

**Windows gateway 重启陷阱：** `hermes gateway start` 走的是 systemd/launchd（Linux/macOS 后台服务），Windows 不支持——会卡在 "Install it now so the gateway starts on login?" 的 service 安装提示然后退出，gateway 实际没起来。正确命令是 `hermes gateway run`（foreground 模式，手动后台化）。验证：`tail -5 ~/AppData/Local/hermes/logs/gateway.log` 应看到各平台 "connected"。

- 不要同时挂多个巨型 skill——它们也在 system prompt 里，一起被乘法效应放大
- 上下文压缩救不了——它只压 messages，不碰 system prompt。agentmemory context 在 system prompt 里，压缩完重建时又被拉回来
- 如果 context 块已上万字符，该给 agentmemory 的 system_prompt_block 加截断（目前 Hermes memory_manager 没有对 provider 返回做大小限制）

**prefetch 路径仍然可控**——永远 5 条，永远每条最多 200 字符。如果每轮对话主题完全不同，prefetch 是纯浪费。Agent 按需手动调 MCP 工具更省。

## 模型配置

agentmemory 用 DeepSeek 做压缩（通过 OpenAI-compatible 端点，PR #307 已合入）：

```bash
# agentmemory 自己用的模型（默认 gpt-4o-mini，但 base URL 是 DeepSeek 会被映射）
OPENAI_MODEL=deepseek-v4-flash   # 便宜（$0.14/M input, $0.28/M output）
OPENAI_MODEL=deepseek-chat       # 同上（2026/07/24 废弃，映射到 flash）
OPENAI_MODEL=deepseek-v4-pro     # 贵 3 倍，压缩不需要推理能力
```

别用 pro 或 reasoner——压缩会话不需要推理。

## 检索管线与衰减

三重混合搜索：BM25（关键词，不衰减）+ 向量（语义，衰减生效）+ 图遍历（结构，不衰减）。

**衰减是排名降权，不是删除。** BM25 和图遍历不受衰减影响——只要记得一个关键词（"jose"、"auth"），就能搜到久远记忆。向量搜索靠语义匹配，衰减后模糊查询可能搜不到。

四层管道：工作记忆（天级衰减）→ 情景记忆（周级）→ 语义记忆（月级）→ 程序性记忆（几乎不衰减）。consolidation 把高频确认的信息往上推。

**局限：** consolidation 假设"最近被访问 = 重要"。长期低频知识应存入 MEMORY.md（memory 工具）或 llm-wiki。

## 记忆架构：KV Scope 与 LLM 分工

agentmemory 有 47 个 KV scope，但 agent 能搜索/使用的只有少数几个。关键区分：

| KV Scope | 写入者 | 是否进 BM25/Vector/Graph 索引 | 是否进 context/prefetch |
|----------|--------|-------------------------------|------------------------|
| `KV.observations` | sync_turn→observe→compress | ✅ smart-search 主数据源 | ❌ |
| `KV.summaries` | summarize（session 结束自动） | ❌ | ✅ `mem::context` 读取 |
| `KV.memories` | remember / memory_save | ✅（转伪 observation） | ❌ |
| `KV.lessons` | lesson-save | ❌ | ✅ `mem::context` 读取 |
| `KV.slots` | slot-create | ❌ | ✅ `mem::context` 读取 |
| `KV.profiles` | profile（纯统计） | ❌ | ✅ `mem::context` 读取 |
| `KV.semantic` | consolidate-pipeline | ❌ | ❌（仅供 consolidate 内部去重） |
| `KV.procedural` | consolidate-pipeline | ❌ | ❌ |

**关键结论：** observations 和 summaries 是两条独立的"数据河"——observations → 搜索索引（agent 能搜历史对话），summaries → 上下文注入（agent 知道之前 session 做了什么）。Consolidate 的产出（semantic/procedural）对 agent 不可见，只用于 consolidate 管道的跨 session 去重。

**LLM 做什么 vs 代码做什么：** 分区路由（哪个数据进哪个 KV scope）100% 由代码决定，LLM 零参与。LLM 只负责每个格子里的内容质量——compress 提取 facts/concepts，summarize 生成摘要，consolidate 提取语义事实。整个系统 47 个 scope 中只有 9 个函数涉及 LLM 调用。

**consolidate-pipeline 需手动触发：** agentmemory 默认 0 个 routines。summarize 在 session 结束时自动触发（`event::session::stopped`），但 consolidate 管道不会自动运行。需积累 ≥5 个 session summaries 后手动 `curl -X POST localhost:3111/agentmemory/consolidate-pipeline -d '{}'`。

**端到端管道验证** 和 **47 个 KV Scope 全量映射** 详见：
- `references/kv-scope-source-evidence.md` — 源码级 KV scope 追踪
- `references/memory-pipeline-gap.md` — 记忆管道不自动运行的原因与修复
- `references/session-end-auto-pipeline.md` — session 结束时的自动 summarize 源码证据
- `references/worker-bound-diagnostic.md` — worker 连接问题诊断实录

## 排查

```bash
hermes memory status           # 看 provider + plugin 状态
curl http://localhost:3111/health
docker ps | grep iii           # 确认 Docker 容器在跑
```

### 容器在跑但 API 不响应（TCP OK, HTTP stuck）

**症状：** `docker ps` 显示 running，进程 `/app/iii` 活着，但 curl 超时——`curl -v` 能看到 TCP 握手成功（`* Established connection`），请求发出后永远收不到 HTTP 响应（`Operation timed out after 5000 milliseconds with 0 bytes received`）。

**诊断：** TCP 连接建立说明端口监听正常，HTTP 层无响应说明容器内的应用层卡死了（Rust 的 tokio runtime 可能被某个阻塞任务卡住）。这不是 worker 断开（断开是 404），是 iii-engine 自身的 HTTP server 堵塞。

```bash
# 确认 TCP 层面的状态
curl -v http://127.0.0.1:3111/ --connect-timeout 3 --max-time 5 2>&1

# 如果输出包含 "* Established connection" 但最终 timeout → 本问题
# 如果输出包含 "Connection refused" → 端口没监听
# 如果返回 404 → worker 断开（Worker-Bound 问题）
```

**修复：** 重启容器。`docker restart agentmemory-iii-engine-1`。新启动的 process 会重新绑定端口，HTTP server 恢复正常。

**注意：** 这种情况下 watchdog 无法修复——它调用 `npx @agentmemory/agentmemory` 试图启动新 worker，但 iii-engine 容器已经在运行且端口被占用，新 worker 也无法注册路由。必须重启容器。

**诊断配方与 curl 返回值对照：** 详见 `references/iii-engine-http-hung-diagnostic.md` — TCP 握手成功但 HTTP recv 超时的确诊方法、容器日志特征（"Checking trigger scope"）、与 worker 断开的区分表、watchdog 改进建议。

## Config 损坏诊断：列表被存为字符串

**这是一类问题，不是孤例。** config.yaml 中某些本应是 YAML 列表的值被存成了 Python repr/JSON 字符串，导致 `isinstance(val, list)` 检查静默失败 → 功能不加载且无报错。

**已知受影响字段：**

| 字段 | 正确格式 | 损坏格式 | 修复 | 运行时影响 |
|------|---------|---------|------|-----------|
| `plugins.enabled` | `- agentmemory` | `'[\"agentmemory\"]'` (JSON) | `json.loads()` | plugin 静默不加载（`plugins_cmd.py:730`） |
| `mcp_servers.*.args` | `- '-y'` | `'[''-y'',''...'']'` (repr) | `ast.literal_eval()` | MCP 连接 Pydantic 拒绝 → startup 阻塞 |
| platform toolsets | `- terminal` | `- messaging` | 删除该行 | Warning 但不影响功能 |

**检测方法：**

```bash
# 查找 config 中所有以 '[' 或 '{' 开头的可疑字符串值
python -c "
import yaml
with open('config.yaml') as f:
    cfg = yaml.safe_load(f)

def find_string_lists(obj, path=''):
    if isinstance(obj, dict):
        for k, v in obj.items():
            find_string_lists(v, f'{path}.{k}')
    elif isinstance(obj, str) and (obj.startswith('[') or obj.startswith('{')):
        print(f'{path} = {repr(obj[:80])}')

find_string_lists(cfg)
"
```

**修复（通用）：**
```python
import yaml, json, ast
with open('config.yaml') as f:
    cfg = yaml.safe_load(f)
pl = cfg.get('plugins', {})
if isinstance(pl.get('enabled'), str):
    pl['enabled'] = json.loads(pl['enabled'])  # JSON-formatted
mcp = cfg.get('mcp_servers', {})
for name, srv in mcp.items():
    if isinstance(srv.get('args'), str):
        srv['args'] = ast.literal_eval(srv['args'])  # Python repr
with open('config.yaml', 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
```

**注意：** JSON 字符串用 `json.loads()`（双引号），Python repr 用 `ast.literal_eval()`（单引号）。两者不能互换——`json.loads("['-y']")` 会报错。

### MCP 连接失败：args 格式（具体症状）

如果 gateway 日志出现 `Pydantic list_type` 错误，说明 config.yaml 中 `args` 被存成 JSON 字符串而非 YAML 列表：
```
1 validation error for StdioServerParameters
  Input should be a valid list [type=list_type, input_value='["-y","@agentmemory/mcp"]', input_type=str]
```

**根因：** `mcp_tool.py:1461` 直接把 config 的 `args` 值传给 Pydantic 的 `StdioServerParameters(args=args)`，不做 JSON 解析。而 `hermes config set` 会存成 YAML 字符串（被引号包裹），读出来就是 string，Pydantic 拒绝。

**已知局限：** `hermes config set mcp_servers.agentmemory.args` 不管怎么写参数（`'["-y","@agentmemory/mcp"]'` 或 `"['-y','@agentmemory/mcp']"`），都会被存为 YAML string 而非 list。这是 Hermes 自身的边角 bug——`mcp_tool.py` 应该对 string 类型的 args 先 JSON.parse。这**不影响** memory provider plugin 的三个工具（plugin 走 REST API，不经过 MCP transport），仅影响 MCP 工具注册。等 Hermes 修复此 bug 或暂时接受 MCP 工具不可用。

注意：即使此错误存在，也不影响 memory provider plugin 的三个工具——plugin 走 REST API（依赖 `@agentmemory/agentmemory` worker），不经过 MCP transport。

### 工具在列表中但返回空/false

agentmemory 是 **Worker-Bound** 架构：Docker 容器只跑 iii-engine 框架引擎，REST API 路由由连接的 worker 进程动态注册。Worker 断开时所有路由注销，容器返回 404。

**关键区分：两个 Worker，两条路径。**

| | @agentmemory/agentmemory | @agentmemory/mcp |
|---|---|---|
| 启动命令 | `AGENTMEMORY_USE_DOCKER=1 npx @agentmemory/agentmemory` | `npx @agentmemory/mcp` |
| 注册的路由 | 核心 REST API（smart-search, remember, search, observe, session/start 等） | MCP 工具路由 + 高级路由（slots, snapshots 等） |
| MemoryProvider plugin 依赖 | ✅ 必须在线 | ❌ 不需要 |
| 工具列表中可见 | ❌（plugin 注册工具，不是 worker） | ✅（MCP 注册工具） |

**最常踩的坑：** gateway 重启后 agentmemory worker 也会死（它随旧 gateway 进程一起被杀），但新 gateway 的 memory provider plugin 只在 `initialize()` 时调一次 `session/start`，不会自动重启 worker。症状是——三个 memory 工具在列表里，调用返回 `{"results": []}` / `{"success": false}`，agent.log 显示工具 "completed" (2-7s，返回体 15-18 chars)。

**不要被 MCP args 格式错误误导。** 如果 errors.log 里同时有 MCP 连接失败（Pydantic list_type），这是另一个独立问题——mcp_tool.py:1461 在 config 存成 YAML string 时不 JSON.parse。但即使 MCP 挂了，只要 agentmemory worker 在线，plugin 的 REST 调用就正常。反过来，MCP 修好但 worker 没启动，plugin 照样返回空。

**排查流程：**

```bash
# 1. 确认端点可达（404 = 无 worker）
curl -s -o /dev/null -w "%{http_code}" http://localhost:3111/agentmemory/smart-search \
  -X POST -H "Content-Type: application/json" -d '{"query":"test"}'

# 2. 确认 worker 是否注册
docker logs agentmemory-iii-engine-1 2>&1 | grep "Worker registered"

# 3. 确认具体哪些路由在册（应看到 smart-search/remember/search/observe）
docker logs agentmemory-iii-engine-1 2>&1 | grep "REGISTERED.*Endpoint" | grep -E "smart-search|remember|search|observe"

# 4. 如果无 worker 或路由缺失：重启 agentmemory worker
AGENTMEMORY_USE_DOCKER=1 npx @agentmemory/agentmemory &

# 5. 等几秒后验证
sleep 5
docker logs agentmemory-iii-engine-1 --since 1m | grep "Worker registered"
curl -s -o /dev/null -w "%{http_code}" http://localhost:3111/agentmemory/smart-search \
  -X POST -H "Content-Type: application/json" -d '{"query":"test"}'
```

**sync_turn 也受影响：** sync_turn 走的是 REST API（`POST /agentmemory/observe`），worker 不在线时同样 404，但因 `_api()` 静默吞异常（不抛给 memory_manager 的 try/except），agent.log 不会报 warning。症状是 Docker 日志里没有 observe 请求记录。Worker 恢复后下一轮对话起生效。

详见 `references/worker-lifecycle-debug.md`。

## Worker 保活自动化

**问题：** gateway 重启后 agentmemory worker 不会自动恢复。每次需要手动 `npx @agentmemory/agentmemory`。

**推荐方案：Cronjob Watchdog（已验证，三层诊断）**

每分钟运行的 watchdog 脚本，四层诊断避免误判：

| 检测 | 条件 | 动作 |
|------|------|------|
| worker 正常 | smart-search 返回 200 | 立即退出 |
| worker 挂了（容器健康） | HTTP reachable + 容器 running | `npx` 重启 worker（`CREATE_NO_WINDOW` 无弹窗） |
| 容器 HTTP-stuck | 容器 running 但 HTTP 不响应 | `docker restart`（无弹窗） |
| 容器挂了 | docker ps 找不到 | `docker start` + 等 worker 重连 |

**关键改进（2026-06-24）：** 第三层从 `tcp_reachable()`（仅 TCP 握手）升级为 `container_http_healthy()`（真实 HTTP GET）。iii-engine 可以 TCP 握手成功但 HTTP server 内部死锁——只有 HTTP round-trip 能检测。之前因 TCP 检查的盲区，watchdog 误判为「只缺 worker」每次弹窗失败 30 秒；修复后直接 `docker restart` 自动救活。

**验证 watchdog 是否已升级（一行命令）：**
```bash
grep -q "container_http_healthy" ~/AppData/Local/hermes/scripts/agentmemory-watchdog.py && echo "✓ HTTP check active" || echo "✗ OLD TCP-only version — update needed"
```

**⚠ 改完 watchdog 后必须验证（不要只读代码，要实测）：**

2026-06-24 用户追问 "你确定改对了？安全吗？" 暴露了一个教训——只读代码验证不够。`container_http_healthy()` 用的是 `GET /`，但 iii-engine 根路径返回什么？如果返回 500 就会误判为不健康。必须实测：

```bash
# 1. 确认 GET / 的实际返回值
curl -s --max-time 3 -w "\nHTTP %{http_code}" http://localhost:3111/
# 预期: 404 (iii-engine 无根路由，但 HTTP 层在响应)

# 2. 逐路径心智推演（不要在脑里跑，写出来）
# Path A: worker 活着 → exit 0
# Path B: worker 死 + HTTP 正常 → spawn worker
# Path C: worker 死 + HTTP 卡死 → docker restart
# Path D: 容器没了 → docker start
```

**教训：** 改完健康检查必须实际 curl 看返回值。404 < 500 算健康（HTTP 层活着），这不能靠读代码推断。

```bash
# Watchdog 脚本位置：~/AppData/Local/hermes/scripts/agentmemory-watchdog.py
# 脚本内容见该文件（2026-06-24 版含 HTTP 级别健康检查 + 四层诊断）
# 创建 cronjob：
hermes cron create --name agentmemory-watchdog \
  --schedule "every 1m" --no-agent \
  --script agentmemory-watchdog.py
```

**Worker 生命周期关键区别：**

| 启动方式 | 进程管理 | gateway 重启影响 |
|----------|---------|-----------------|
| `terminal(background=true)` | Hermes managed | 被杀 |
| `subprocess.Popen` (watchdog) | 独立进程 | 不受影响 |

Watchdog 用的是 `subprocess.Popen`，所以 worker 常驻——只有机器重启、自身崩溃或手动 taskkill 才会挂，watchdog 60s 内自动救活。

**2026-06-23 修复：** watchdog 脚本改为三层诊断。容器 TCP-stuck 时用 `docker restart` 而非 `npx`——docker.exe 是原生二进制，不会弹 cmd 窗口。所有子进程调用加 `CREATE_NO_WINDOW`。不再有 cmd 闪窗问题。

**替代方案（不推荐）：** `gateway:startup` hook。

尝试过，两个问题导致放弃：(1) gateway 进程 PATH 里没有 npx，`subprocess.Popen(["npx", ...])` 找不到命令；(2) handler 的 `print(..., file=sys.stderr)` 输出完全失踪，无法调试。详见 `references/worker-lifecycle-debug.md`。

相关 wiki：[[concepts(概念)/agentmemory-worker-bound-session-gap]]

## 多 Profile 隔离

本机多 Hermes profile（如 default + worker/B）共享同一个 agentmemory 实例时：

- **不会 crash**——Docker + worker 是单实例，多 profile 各自 REST 调用
- **会记忆串扰**——`smart-search` 不带 project/session 过滤，搜的是全局。default 的 prefetch 可能注入 B 的记忆，反之亦然

**推荐：** 纯推理节点（如 B profile）不开 agentmemory（`memory.provider: ''`）。如果确实需要隔离，起双实例——另一个 Docker + worker 用不同端口，各 profile 配不同的 `AGENTMEMORY_URL`。

## Hermes 整体配置迁移

把 Hermes 完整配置（含 agentmemory plugin、skills、hooks、cron、profiles 等）同步到 GitHub 或迁移到新机器时，完整清单见 `references/hermes-setup-inventory.md`。要点：
- plugin 只是 HTTP 桥接层，agentmemory 本体是 Docker + npx，不需 fork
- `~/.hermes/` 下需进仓库的有 8 类（hooks/cron/scripts/profiles/memories/config/skills/plugins），绝不进仓库的 5 类（.env/auth.json/state.db/channel_directory/gateway_state）
- 缓存目录（`.hub/`、`.curator_backups/`、`__pycache__/`）需排除
- Docker volume 里的历史记忆可用 `docker cp` 备份

## sync_turn 没写入怎么排查

症状：聊了好几轮但 agentmemory 里查不到对话记录。

### 快速诊断：当前对话是否被记录

当用户问"现在的对话记录了吗"，按以下流程诊断（不要跳过步骤）：

```bash
# 0. 【最优先】不依赖 agentmemory 在线的验证：直接查 system prompt 有无 <memory-context> 块
# ⚠ 注意：Hermes 注入的 fence tag 是 <memory-context>（源码 memory_manager.py:157），
# 不是 <agentmemory-context>。用户 MEMORY 笔记中出现的 "<agentmemory-context>"
# 字符串是误报——那只是笔记内容，不是 agentmemory provider 的真实注入。
python -c "
import sqlite3
db = sqlite3.connect('~/AppData/Local/hermes/state.db')
row = db.execute(
    'SELECT id, system_prompt FROM sessions ORDER BY started_at DESC LIMIT 1'
).fetchone()
has_am = row and row[1] and '<memory-context>' in row[1]
print(f'session={row[0][:30]}...  agentmemory={\"ACTIVE\" if has_am else \"NOT INITIALIZED\"}')
"
# 如果输出 "NOT INITIALIZED" → Provider initialize() 从未执行，跳到「手动修复」
# 如果输出 "ACTIVE" → 继续步骤 1-5
# 
# 【辅助验证】如果 session 在 state.db 里但没有 <memory-context> block，
# 说明 _memory_manager 是 None。此时 sync_turn 自愈完全无效，因为
# memory_manager.sync_all 的第一行就是 if not providers: return。

# 1. 确认 plugin + container 在线
hermes memory status          # 应显示 Plugin: installed ✓, Status: available ✓
docker ps | grep iii          # 确认容器在跑
curl -s -o /dev/null -w "%{http_code}" http://localhost:3111/agentmemory/smart-search \
  -X POST -H "Content-Type: application/json" -d '{"query":"test","limit":1}'  # 应 200

# 2. 全链路验证（可选，确认 pipeline 本身通的）
python verify-ingestion.py

# 3. 查 Hermes session DB 获取当前 session ID + 启动时间
python -c "
import sqlite3, time
db = sqlite3.connect('~/AppData/Local/hermes/state.db')
row = db.execute('SELECT id, started_at FROM sessions ORDER BY started_at DESC LIMIT 1').fetchone()
print(f'session={row[0]}  started_local={time.strftime(\"%H:%M:%S\", time.localtime(row[1]))}')
"

# 4. 对比容器重启时间（找最后一次 "Worker registered"）
docker logs agentmemory-iii-engine-1 2>&1 | grep "Worker registered" | tail -1

# 5. 查当前 session 是否在 agentmemory 里存在
#    注意：sessions 端点的 observationCount 有异步延迟
#    要精确看每条 observation，用 /observations 端点
curl -s http://localhost:3111/agentmemory/sessions | python -c "
import sys,json
data=json.load(sys.stdin)
sessions = data if isinstance(data, list) else data.get('sessions',[])
target='<替换为步骤3的session_id>'
for s in sessions:
    if target in s.get('id',''):  # 注意：sessions 端点字段名是 id，不是 sessionId
        print(f'存在: obs={s.get(\"observationCount\",0)}')
        break
else:
    print('不存在 — session/start 静默失败')
"

# 5b. 【权威】直接查 observations 列表（绕过计数延迟）
curl -s "http://localhost:3111/agentmemory/observations?sessionId=<session_id>" | python -c "
import sys,json
data=json.load(sys.stdin)
obs=data.get('observations',[])
for o in obs:
    print(f'  [{o[\"timestamp\"][:19]}] {o[\"title\"][:60]}')
print(f'Total: {len(obs)} observations')
"
```

**典型诊断结论：**
- 如果 session 在 agentmemory 里不存在 → session/start 在容器死的时候静默失败
- 如果 session 存在但 Docker 日志无 "Observation captured" → sync_turn 链路断裂
- 如果 session 存在且有 observe 请求但 smart-search 搜不到 → 索引延迟（BM25 索引需 5-15s）

**`/new` session 切换已完整修复（2026-06-23）。** 原先两个 gap 已解决：

1. **observe daemon 线程竞态**（已修复）：`sync_turn` 改为追踪式 daemon，`on_session_end` 和 `on_session_switch(reset=True)` 调用 `_flush_observes()` 等待所有 pending observe 完成后再 `session/end`。详见 `references/new-session-no-reinit.md`。

2. **`reset=True` 被忽略**（已修复）：`on_session_switch` 现在完整处理 `reset=True`——flush observes → session/end 旧 session → 清空 _pending_observes → session/start 新 session。

**但 `on_session_switch` 里的 `_api("session/start", ...)` 走的是同一条静默吞错链路**（`__init__.py:168` 的 `except: return None`），如果 HTTP 调用暂时失败，session/start 静默返回 None，不会报任何 warning。症状：反复 `/new` 后 agentmemory 里仍然一条 observation 都没有。

**Gateway `/new` vs CLI `/new` 的区别：** CLI 的 `/new`（`cli.py:6037`）直接调 `_mm.on_session_switch()`。Gateway 的 `/new`（`slash_commands.py:64 _handle_reset_command`）只做 `_evict_cached_agent` + `reset_session`，不调 `on_session_switch`。下次消息到来时重建 AIAgent → `initialize()` → `session/start`。两种路径最终都依赖同一个 `_api("session/start", ...)` 调用，都受静默吞错影响。

**当前状态（2026-06-23）：已修复。** 两个问题同时存在：

1. **`logger` 未定义导致 NameError** — 诊断日志里的 `logger.warning(...)` 因为文件中没有 `import logging` 而崩溃。`session/start` 虽然在此之前执行了，但异常被 `memory_manager.on_session_switch()` 的 `logger.debug` 静默吞掉（debug 不落盘）。症状：agent.log 没有任何 "Memory provider" 相关日志，Docker 也无 POST 请求——`initialize()` 可能根本没被调到（gateway 初始化路径待确认）。

2. **`sync_turn` 无自愈** — 如果 init/switch 失败，后续 observe 永远落不了盘。

### Provider 根本没初始化（initialize 从未调）

**症状：** config 有 `memory.provider: agentmemory`，plugin 加载正常（`load_memory_provider` 返回实例、`is_available()` 返回 True），但 agentmemory 端查不到当前 session，system prompt 里没有 `<memory-context>` block。

**根因（2026-06-23，CLI session）：** `agent_init.py:1141-1198` 的 MemoryProvider 初始化代码块被跳过。agent.log 中没有 "Memory provider 'agentmemory' activated" 日志（该日志由 `agent_init.py:1195` 的 `_ra().logger.info(...)` 产生，**会落盘**——如果这条也没有，说明整段初始化代码根本没跑）。上次有效初始化记录是 6月22日。

**已知会导致跳过的路径：**

1. **`skip_memory` 被误连到 `ignore_rules`** — `cli_agent_setup_mixin.py:384-385`:
   ```python
   skip_context_files=self.ignore_rules,
   skip_memory=self.ignore_rules,
   ```
   如果 CLI 以 `--ignore-rules` 或 `--safe-mode` 启动，或 `HERMES_IGNORE_RULES=1` 被设，MemoryProvider 也会被跳过。默认 `ignore_rules=False` 不影响正常路径。

2. **`_mp.is_available()` 返回 False 或 `load_memory_provider` 返回 None** — DEBUG 日志不可见，无痕

3. **异常被外层 `except` 捕获** — 会打 WARNING（落盘），搜 "plugin init failed" 确认

**`_memory_manager = None` 的连带后果：** sync_turn 自愈完全失效。
`memory_manager.py:540-542` 检查 `if not providers: return`——当 `_memory_manager` 是 None 时，
`_providers` 为空列表，`sync_all` 直接返回，sync_turn 自愈码（`__init__.py:351-361`）永远不会被调到。

详见 `references/skip-memory-none-root-cause.md`。

**唯一可靠的验证方法（不依赖 plugin logger）：**

```python
import sqlite3
db = sqlite3.connect('~/AppData/Local/hermes/state.db')
row = db.execute(
    "SELECT id, system_prompt FROM sessions WHERE id LIKE ?",
    ('<当前session_id前缀>%',)
).fetchone()
if row:
    has_am = '<memory-context>' in (row[1] or '')
    print('agentmemory ACTIVE' if has_am else 'NOT initialized')
```
⚠ **诊断陷阱：** Hermes 真实的 fence tag 是 `<memory-context>`（源码 `memory_manager.py:157`），不是 `<agentmemory-context>`。用户 MEMORY 笔记中如果包含了 "agentmemory-context" 文字（如 "用state.db查 system_prompt有无<agentmemory-context>"），会导致 `LIKE '%<agentmemory-context%'` 误匹配。

**对比验证（/new session vs 普通 CLI session）：**

| session 类型 | initialize 调用路径 | agentmemory 注册 |
|-------------|-------------------|-----------------|
| `/new` (CLI) | `cli.py:6037` → `_mm.on_session_switch()` → `_api("session/start")` | ✅ 已验证（session 103952 存在，obs=0） |
| 普通 CLI 输入 | `agent_init.py` → `build_agent` → `initialize_all()` → `_api("session/start")` | ❌ 未初始化（session 104936 不存在） |

**注意区分：** `/new` session 虽然注册了（session/start 成功），但 sync_turn 因 NameError 未落盘（obs=0）。普通 CLI session 连注册都没发生——initialize() 整段跳过。

**如果确认 Provider 未初始化：**
1. 先用 `hermes config show` 确认 `memory.provider: agentmemory` 存在
2. 确认 plugin 文件在 `$HERMES_HOME/plugins/agentmemory/__init__.py`
3. 手动注册当前 session（见上文手动修复）
4. 如果反复出现，回退：`hermes config set memory.provider ""` 然后重新设置

**已实施的修复（`plugins/agentmemory/__init__.py`）：**
- 添加 `import logging` + `logger = logging.getLogger(__name__)`
- `sync_turn()` 开头同步调 `_api("session/start", ...)`（幂等），然后 `logger.info` 输出诊断。无论 init/switch 失败多少次，下一轮对话自动恢复。

**⚠ DIAG 日志不可见（2026-06-23 发现）：** plugin 的 `logger.warning(...)` / `logger.info(...)` 诊断消息**不输出到任何 log 文件**（agent.log、gateway.log、errors.log 均无）。根因：plugin 作为 `_hermes_user_memory.agentmemory` 模块加载，其 logger hierarchy 不传播到 root handler。**不能靠 grep DIAG 来确认修复是否生效。** 用 state.db 验证替代（见下节 "Provider 根本没初始化"）。

**⚠ sync_turn 自愈的边界条件（2026-06-23 发现）：** sync_turn 开头调 session/start 的自愈码**只在 `_memory_manager` 不是 None 时生效**。`memory_manager.py:540-542` 的 `if not providers: return` 在 `_memory_manager` 为 None 时直接返回——sync_turn 从未被调，自愈码不到达。sync_turn 自愈解决的是"session/start 曾失败但后续自动恢复"的场景，**不解决"provider 根本没注册"的场景**。详见 `references/skip-memory-none-root-cause.md`。

诊断命令（gateway 日志，**注意：不可靠，见上**）：
```bash
grep "DIAG: sync_turn session/start" ~/AppData/Local/hermes/logs/gateway.log
```

**诊断是否命中此问题：** `/new` 后立即查 agentmemory 里当前 session 是否存在：

```bash
# 1. 查当前 session ID
python -c "import sqlite3; db=sqlite3.connect('~/AppData/Local/hermes/state.db'); print(db.execute('SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1').fetchone()[0])"

# 2. 查 agentmemory 是否认识它
curl -s http://localhost:3111/agentmemory/sessions | python -c "
import sys,json
data=json.load(sys.stdin)
sessions=data if isinstance(data,list) else data.get('sessions',[])
target='<session_id>'
found=any(target in s.get('id','') for s in sessions)
print('session registered' if found else 'NOT registered — session/start silently failed')
"
```

**永久修复（代码层）：** 在 agentmemory 的 `sync_turn` 开头加一行 `_api("session/start", ...)`——幂等操作，session 已存在时是 no-op，不存在时当场补齐。之后 observe 正常写入。无论 init/switch 失败多少次，下一轮对话自动恢复。详见 `references/sync-turn-silent-failure.md`。

**手动修复（不需要等下次 /new）：**

```bash
curl -s -X POST http://localhost:3111/agentmemory/session/start \
  -H "Content-Type: application/json" \
  -d "{\"sessionId\":\"<session_id>\",\"project\":\"hermes\",\"cwd\":\"C:/Users/<user>\"}"
```

手动注册后 sync_turn 正常写入——下一轮对话起 observation 会被记录。
```bash
curl -s -X POST http://localhost:3111/agentmemory/session/start \
  -H "Content-Type: application/json" \
  -d "{\"sessionId\":\"<从state.db查到的session_id>\",\"project\":\"C:/Users/<user>\",\"cwd\":\"C:/Users/<user>\"}"
```
注意 Windows 路径用正斜杠避免 JSON 转义问题。之后 sync_turn 会传正确的 session_id（`run_agent.py:3073`），observe 写入正常。

### 直接验证端点：

```bash
# 手动调 observe（201 Created = 端点正常，问题在 sync_turn 链路）
curl -s -o /dev/null -w "%{http_code}" http://localhost:3111/agentmemory/observe \
  -X POST -H "Content-Type: application/json" \
  -d '{"hookType":"post_tool_use","sessionId":"test","project":"/tmp","cwd":"/tmp","timestamp":"2026-01-01T00:00:00Z","data":{"tool_name":"conversation","tool_input":"hi","tool_output":"hello"}}'

# 查 Docker 是否收到请求
docker logs agentmemory-iii-engine-1 --since 5m | grep "Observation captured"
```

**端到端验证（推荐第一步）：**

```bash
python scripts/verify-ingestion.py
```

脚本会执行 `session/start → observe → smart-search` 全链路，输出 PASS/FAIL。
这是唯一的确诊手段——比查日志更快更可靠。见 `scripts/verify-ingestion.py`。

**索引延迟注意：** agentmemory 的 BM25+向量索引不是同步的，observe 写入后需 **5-6 秒** 才能在 smart-search 中查到。脚本内置了 3 次重试（间隔 2s），容忍这个延迟。如果手动 curl 测试，observe 返回 201 后等一下再搜。

**⚠ observationCount 不是"压缩计数"：** sessions 端点的 `observationCount` 字段就是原始 observation 条数，与对话轮数 1:1 对应（每次 sync_turn → 1 条 observation，type=conversation）。数字偏低不是因为 worker 压缩合并，而是因为 **worker 异步处理有延迟**——sessions 端点的计数更新滞后于 observe 写入。**权威来源是 `/agentmemory/observations?sessionId=<id>`**，不是 `/agentmemory/sessions` 的计数。别用"压缩"来解释数字对不上——那是我踩过的坑。

**sync_turn 全链路静默吞错：** plugin 代码五层 catch + 一个 NameError + plugin logger 不可见 + `_memory_manager` 是 None = 八层无痕：

```
memory_manager.py:540  if not providers: return                         ← 第0层: _memory_manager=None 时直接返回
run_agent.py:3085     except Exception: pass                                 ← 第1层
memory_manager.py:591  except Exception: logger.debug(...)                   ← debug 不落盘
memory_manager.py:595  executor.submit(fn) ← Future 没人读，lambda 失败永不浮现
memory_manager.py:772  except Exception: logger.debug(...)                   ← on_session_switch 专用，debug 不落盘！
memory_manager.py:945  except Exception: logger.warning(...)                 ← initialize_all 专用，会落盘
__init__.py:168        except (URLError, ...): return None                   ← _api 静默吞 HTTP 异常
__init__.py:172        daemon thread → _api_bg 失败了没人知道
__init__.py:200,360    logger.warning/info(...) → 日志不落盘（plugin logger hierarchy 不传播到 root handler）
__init__.py:388        try/finally discard ← daemon 线程异常时 _pending_observes.discard() 不执行（已修复：2026-06-23 加 try/finally）
```

**关键区分：** `initialize_all` 的异常处理用 `logger.warning`（**会落盘**），而 `on_session_switch` 用 `logger.debug`（**不落盘**）。即使 `initialize()` 崩溃，agent.log 里有 warning 可查；但 `on_session_switch()` 崩溃完全无痕。

**`logger` NameError 陷井：** 在 plugin 的 `__init__.py` 中加诊断日志时，务必先确认文件已 `import logging` 且定义了 `logger = logging.getLogger(__name__)`。否则诊断代码自身崩溃，session/start 虽然执行了但异常掩盖了真因。

**⚠ 即使 logger 正确导入，plugin 的 `logger.warning()` / `logger.info()` 仍不输出到任何 log 文件**（`_hermes_user_memory.agentmemory` 的 logger hierarchy 不传播到 root handler）。诊断不能用 grep，只能用 state.db + agentmemory sessions 端点。

第 5 层（`executor.submit` + 无人读 Future）意味着即使 `_run` lambda 本身抛异常（如 `self._providers` 在迭代中被改），异常也会被 Future 静默捕获，`sync_all` 的 `except Exception: pass`（第 1 层）永远看不到它。

如果端点正常但 Docker 没收到请求，`/new` 已修复此问题（见上文的 `on_session_switch` 说明）。如遇旧版插件，手动调 `session/start`（见上文手动修复步骤）。

**Daemon 线程追踪的额外坑点**（2026-06-23 实施修复时发现）：try/finally 必要性、闭包变量捕获安全规则、快照+join 死锁避免、terminal 工具 key 截断陷阱、**Logger 注入位置陷阱（DIAG 只保护所在层）**、**线程追踪 ≠ 结果追踪（join 不检查 HTTP 成功）**。详见 `references/daemon-thread-tracking-pitfalls.md`。最后两个坑是关键调试哲学教训：端到端 observationCount 校验是唯一不依赖任何日志层的验证手段。

详见 `references/sync-turn-silent-failure.md`。

## 与 memory 工具和 wiki 的分工

| | agentmemory | memory 工具 | llm-wiki |
|------|-----------|----------|---------|
| 存什么 | 自动捕获的 session 记忆 | 手动存的持久事实 | Curated 知识 |
| 衰减 | 有 | 无 | 无 |
| 适合 | "上次怎么做的" | "永不过期的关键信息" | "概念分析和对比" |
