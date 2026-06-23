# Memory Pipeline Gap — 诊断实录（2026-06-22）

## 现象

用户在 agentmemory 的 `memories` 列表里看不到任何记忆（只有 4 条测试数据），但之前 session 的 observations 有 15 条。

```bash
$ curl -s http://localhost:3111/agentmemory/memories?limit=20
# 只有 4 条：[fact] test, [architecture] Hermes agent 使用 jose..., [fact] verify worker is back, [fact] 新 session 验证...
```

## 诊断过程

### Step 1: 确认 sync_turn → observe 链路正常

```bash
# session/start + observe 手动测试
$ curl -X POST http://localhost:3111/agentmemory/session/start -d '{...}'  # → 200
$ curl -X POST http://localhost:3111/agentmemory/observe -d '{...}'        # → 201
$ curl -X POST http://localhost:3111/agentmemory/smart-search -d '{...}'   # → 找到
```

API 链路全通。

### Step 2: 查 session observations

```bash
$ curl -s "http://localhost:3111/agentmemory/sessions"
20260622_141615_3525f7  obs=15  status=completed   # ← 15 条 observations!
```

observations 确实被自动摄入了（sync_turn 工作）。

### Step 3: 查 observation 内容 — compress 也正常

```json
{
  "concepts": ["agentmemory worker startup", "REST API vs MCP dependency", ...],
  "facts": ["Root cause of tool recovery failure was...", ...],
  "narrative": "Debugging three verification items...",
  "importance": 9,
  "type": "conversation"
}
```

compress（LLM 压缩）正常 — facts、concepts、narrative 都被提取。

### Step 4: config/flags — 功能全部开启

```bash
$ curl -s http://localhost:3111/agentmemory/config/flags
GRAPH_EXTRACTION_ENABLED: true    (needsLlm)
CONSOLIDATION_ENABLED: true       (needsLlm)
AGENTMEMORY_AUTO_COMPRESS: true   (needsLlm)
```

### Step 5: 手动跑 consolidation-pipeline — 被阈值拦截

```bash
$ curl -X POST http://localhost:3111/agentmemory/consolidate-pipeline \
  -d '{"sessionId":"20260622_141615_3525f7"}'
{
  "semantic": {"reason": "fewer than 5 summaries", "skipped": true},
  "procedural": {"reason": "fewer than 2 recurring patterns", "skipped": true}
}
```

### Step 6: 查 routines — 空的

```bash
$ curl -s http://localhost:3111/agentmemory/routines
Total routines: 0
```

## 根因

agentmemory 的 memory 管道有两层，但只有第一层自动运行：

| 阶段 | 触发方式 | 状态 |
|------|----------|------|
| observe | sync_turn (Hermes) → REST API | ✅ 自动 |
| compress | event::observation → sdk.trigger("mem::compress") | ✅ 自动 |
| summarize | 需手动 POST `/agentmemory/summarize` | ❌ 无 routine |
| consolidate-pipeline | 需手动 POST `/agentmemory/consolidate-pipeline` | ❌ 无 routine |
| → semantic memories | consolidate 产出 | ❌ 因为上面没跑 |

**agentmemory 在安装后不会自动创建 routines。** 必须在 agentmemory 中创建 routine 来定时触发 summarize + consolidate-pipeline。

### 阈值要求

- `summarize` 需要 session 有 observations
- `consolidate-pipeline` 的 semantic 分支需要 **≥5 个 summaries**
- `consolidate-pipeline` 的 procedural 分支需要 **≥2 个 recurring patterns**

## 额外发现：session/start 的幂等性陷阱

`POST /agentmemory/session/start` 用 `kv.set` 全量覆盖 session 记录，**不是幂等的**：

```javascript
// dist/index.mjs:3804
await kv.set(KV.sessions, payload.sessionId, {
    id: payload.sessionId,
    observationCount: 1,        // ← 覆盖为 1
    status: "active",
    // ...
});
```

重复调用同一 sessionId 会：
1. 重置 `observationCount` 为 1（或 0）
2. 覆盖 `startedAt` 为当前时间
3. observations 的 KV entries 仍存在，但 API 可能因为 `observationCount=0` 而返回空

**结论：`session/start` 只应在 session 首次创建时调用。查询状态用 `GET /agentmemory/sessions`。**

### Step 7: consolidate 产出的 newFacts 不进入 /memories

手动补了 5 个 sessions 的 summaries 后，consolidate-pipeline 成功执行：

```bash
$ curl -X POST localhost:3111/agentmemory/consolidate-pipeline -d '{}'
{
  "semantic": {"newFacts": 7, "totalSummaries": 6},
  "procedural": {"skipped": true, "reason": "fewer than 2 recurring patterns"},
  "decay": {"semantic": 0, "procedural": 0}
}
```

但 `GET /agentmemory/memories` 仍为空——旧的 4 条已被 decay 清除：

```bash
$ curl -s http://localhost:3111/agentmemory/memories?limit=20
Total memories: 0
```

源码确认：consolidate 产出的 facts 存在 `KV.semantic`（dist/index.mjs:8586），不是 `KV.memories`：

```javascript
// dist/index.mjs:8586
for (const s of semantic) await kv.set(KV.semantic, s.id, s);
```

`/agentmemory/memories` 只显示手动 `remember` 或 `memory_save` 写入 `KV.memories` 的数据。smart-search 可以搜到 semantic 数据（走的是统一搜索索引）。

## 完整管道总结

```
sync_turn → observe ──✅自动──→ observation
                        └─✅自动──→ compress (LLM: facts/concepts/narrative)
                              ↓  ← BM25+vector+graph 索引 ← smart-search 可搜 ✅
                              └─❌需手动──→ summarize → KV.summaries ← context/prefetch ✅
                                              └─❌需手动──→ consolidate (≥5 summaries)
                                                              └─ KV.semantic
                                                                   ↓
                                              ❌ 不进 BM25/vector/graph 索引
                                              ❌ 不进 smart-search
                                              ❌ 不进 context/prefetch
                                              ❌ 不进 /memories 端点
                                              只用于 consolidate 跨 session 去重 + decay
```

**2026-06-22 源码验证结论：consolidate 对 agent 不可见。** `KV.semantic` 数据在 smart-search（`HybridSearch.search()`, `line 2032`）的三个索引（BM25 `line 2051`、vector `line 2056`、graph `line 2061`）中均不存在。三个索引完全来自 compressed observations（`getSearchIndex().add(compressed)` `line 5031`、`vectorIndexAddGuarded(...)` `line 5040`）。`mem::context`（`line 5113-5171`）也不读 `KV.semantic`。consolidate-pipeline 的语义事实是 agentmemory 管道内部工作区，用于为后续 consolidate 运行提供跨 session fact 去重和衰减——**不是面向 agent 的记忆存储**。

## Docker 配置确认

```bash
$ docker inspect agentmemory-iii-engine-1  # env vars
III_ENV=development
III_EXECUTION_CONTEXT=docker

# mounts:
/var/lib/docker/volumes/agentmemory_iii-data/_data → /data
.../iii-config.docker.yaml → /app/config.yaml
```

.env 文件在 `~/.agentmemory/.env`，由 `AGENTMEMORY_USE_DOCKER=1 npx @agentmemory/agentmemory` 读取后传给 Docker。

## Hermes sync_turn 静默吞错链

从 sync_turn 到 agentmemory 的路径上，4 处吞错使故障完全静默：

```
run_agent.py:3085          except Exception: pass                 → 最外层吞错
memory_manager.py:591      except Exception: logger.debug(...)    → debug 不落盘
agentmemory/__init__.py:168 except (...) return None              → 返回 None 不抛异常
agentmemory/__init__.py:172 daemon=True 线程                      → daemon 失败无人知
```

Worker 离线时整个 sync_turn 链路既不报错也不写 agent.log，只能靠 Docker 日志确认 observe 是否到达。
