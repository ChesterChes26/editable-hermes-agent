# System Prompt 解剖：agentmemory block 的精确位置和缓存失效机制

> 基于 2026-06-23 从 `state.db` 提取的真实 system prompt 快照（session `20260622_170830_494a07`）

## 宏观结构

```
总 system prompt: 25904 chars (~6476 tokens)

┌─────────────────────────────────────────────────┐
│ STABLE TIER: 16598 chars (offset 0 ~ 16597)     │
│ 身份声明 + 工具指引 + skills 列表               │
├─────────────────────────────────────────────────┤
│ CONTEXT TIER (AGENTS.md等, 常为空)              │
├─────────────────────────────────────────────────┤
│ VOLATILE TIER: 9306 chars (offset 16598 ~ 25903)│
│ ┌─────────────────────────────────────────────┐ │
│ │ MEMORY block                                │ │
│ │ USER PROFILE block                          │ │
│ │─────────────────────────────────────────────│ │
│ │ <agentmemory-context project="...">         │ │
│ │   ... 5854 chars (~1463 tokens) ...         │ │
│ │ </agentmemory-context>                      │ │
│ │─────────────────────────────────────────────│ │
│ │ Conversation started: ...                   │ │
│ │ Model: deepseek-v4-pro                      │ │
│ │ Provider: deepseek                          │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## 精确数字

| 指标 | 值 |
|------|-----|
| 总 system prompt | 25904 chars (~6476 tokens) |
| Stable tier | 16598 chars |
| Volatile tier | 9306 chars |
| agentmemory block 起点 | offset 19963 |
| agentmemory block 终点 | offset 25819 |
| agentmemory block 大小 | 5854 chars (~1463 tokens) |
| 缓存稳定前缀 | offset 0 ~ 19962（前面部分跨 session 不变） |
| 缓存失效点 | offset 19963（agentmemory block 的第一个字节） |

## 缓存失效机制

```
Session N:
  system_prompt → DeepSeek 推理引擎计算 KV cache
  hash(prefix tokens[0..4990]) → KV states

Session N+1 (新 session, agentmemory 多了 observation):
  system_prompt[0:19962] = 与 Session N 完全相同 ✓
  system_prompt[19963:???] = 不同！(多了新 observation) ✗
  → 前缀匹配在第 19963 个字符处中断
  → DeepSeek 隐式前缀缓存 MISS
  → 从头计算全部 ~6500 tokens 的 KV cache
```

## 源码调用链（完整 8 步）

| 步骤 | 文件:行号 | 操作 |
|------|----------|------|
| 1 | `plugins/agentmemory/__init__.py:222-229` | `system_prompt_block()` HTTP POST `/agentmemory/context` |
| 2 | `plugins/agentmemory/__init__.py:156-169` | `_api()` 用 `urllib.request.urlopen` — 零缓存 |
| 3 | `agent/memory_manager.py:413-430` | `build_system_prompt()` 遍历所有 provider |
| 4 | `agent/system_prompt.py:355-362` | `volatile_parts.append(_ext_mem_block)` |
| 5 | `agent/system_prompt.py:403-404` | `stable + "\n\n" + context + "\n\n" + volatile` |
| 6 | `agent/conversation_loop.py:333` | `agent._cached_system_prompt = agent._build_system_prompt()` |
| 7 | `agent/conversation_loop.py:772-776` | `messages[0] = {"role":"system", "content": effective_system}` |
| 8 | DeepSeek 推理引擎 | 前缀匹配失败 → KV cache miss → 全量重算 |

## agentmemory block 的真实格式

```xml
<agentmemory-context project="C:\Users\chester.chen">
## Session 20260622 (2026-06-22T08:48:01Z)
- [conversation] <title>: <one-line narrative>
- [conversation] <title>: <one-line narrative>
...

## Session 20260622 (2026-06-22T08:39:40Z)
- [conversation] <title>: <one-line narrative>
...

## AgentMemory silent failure diagnosis and pipeline validation
<multi-paragraph narrative>

Decisions: <bullet list>
Files: <file list>
</agentmemory-context>
```

格式特点：
- 按 session 分组，每组 `## Session YYYYMMDD (ISO timestamp)`
- 每条 observation 一行：`- [conversation] title: narrative`
- 末尾有全局的 Decisions/Files 小节
- 没有截断，没有上限 — 随 session 数线性增长

## 无 API 时的诊断方法

当 agentmemory worker 断开无法调 `/context` 时，可从 Hermes session DB 直接提取：

```python
import sqlite3
db = sqlite3.connect('~/AppData/Local/hermes/state.db')
rows = db.execute("""
  SELECT id, length(system_prompt) as len
  FROM sessions
  WHERE system_prompt LIKE '%agentmemory%'
  ORDER BY len DESC LIMIT 5
""").fetchall()
# 取最大那个，查看 agentmemory block
sp = db.execute("SELECT system_prompt FROM sessions WHERE id=?", (rows[0][0],)).fetchone()[0]
idx = sp.find('<agentmemory-context')
print(f'Block size: {len(sp) - idx} chars')
```

这比调 API 更可靠 — 不依赖 agentmemory worker 在线。

## 常见陷阱：字符串误判

`system_prompt LIKE '%agentmemory%'` 会命中 skills 列表中的 `agentmemory-hermes` 技能名——**不代表 agentmemory context 块存在**。判断 session 是否真的有 context 注入，必须搜 `<agentmemory-context`：

```sql
-- 正确：搜真实的 context 块
SELECT id FROM sessions WHERE system_prompt LIKE '%<agentmemory-context%'

-- 错误：会误判 skills 列表中的 agentmemory-hermes
SELECT id FROM sessions WHERE system_prompt LIKE '%agentmemory%'
```

6月22日的数据就踩了这个坑：16 个 session 中 `LIKE '%agentmemory%'` 命中 7 个，但实际含 `<agentmemory-context` 的只有 5 个。14:16 和 15:04 两个 session 的 "agentmemory" 命中点在 skills 列表。

## Intra-session 稳定性验证

跨 session 对比 `sp - am_block` 的值：

| session 时间 | sp 总长 | am_block | sp - am_block |
|-------------|---------|----------|---------------|
| 16:18 | 21290 | 1242 | **20048** |
| 16:38 | 22551 | 2503 | **20048** |
| 16:46 | 23724 | 3676 | **20048** |
| 17:08 | 25904 | 5856 | **20048** |
| 17:20 | 25408 | 5360 | **20048** |

精确恒定值 **20048** 证明了 Hermes 的 `_cached_system_prompt` 机制：system prompt 在 session 内是 byte-stable 的，agentmemory block 只在 session 启动时拉取一次。当前 session 内的 `memory` 工具写入或 `sync_turn` 记录的 observations **不会**影响当前 session 的 system prompt——要到下个 session 才出现。
