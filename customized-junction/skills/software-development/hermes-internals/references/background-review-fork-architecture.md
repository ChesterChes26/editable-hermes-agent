# Background Review Fork Architecture

## Quick Summary

Background Review 在每个 turn 结束后 fork 一个独立的 `AIAgent` 子实例，用 daemon 线程运行，评估当前 turn 是否有值得记录的东西并写入 memory/skill store。**Fork 不是无状态的 throwaway agent**——它通过共享 `_memory_store` 对象和父 agent 落在同一存储上。

## Fork 创建：完整继承清单

`agent/background_review.py:641-709` — `_run_review_in_thread()` 中的 `AIAgent(...)` 构造：

### 共享 runtime（同一认证和模型）
```python
review_agent = AIAgent(
    model=_rt.get("model") or agent.model,
    provider=_rt.get("provider") or agent.provider,
    base_url=_rt.get("base_url") or None,
    api_key=_rt.get("api_key") or None,          # line 648-649
    credential_pool=getattr(agent, "_credential_pool", None),  # line 650
    parent_session_id=agent.session_id,           # line 651
    enabled_toolsets=getattr(agent, "enabled_toolsets", None),  # line 652
    disabled_toolsets=getattr(agent, "disabled_toolsets", None),# line 653
    skip_memory=True,                             # line 654
    quiet_mode=True,                              # line 644
    max_iterations=16,                            # line 643
)
```

### 内存存储：传递同一个 Python 对象
```python
review_agent._memory_store = agent._memory_store             # line 665
review_agent._memory_enabled = agent._memory_enabled         # line 666
review_agent._user_profile_enabled = agent._user_profile_enabled  # line 667
review_agent._memory_nudge_interval = 0   # 禁止触发递归 review
review_agent._skill_nudge_interval = 0   # line 668-669
```

**关键**：`review_agent._memory_store = agent._memory_store` 传递的是**同一个 Python 对象引用**，不是拷贝。Fork 通过 `memory` 工具调用时，`tool_executor.py:1047` 传递这个共享对象：

```python
# agent/tool_executor.py:1047
result = _memory_tool(
    ...
    store=agent._memory_store,  # fork 拿到的就是父 agent 的 store
)
```

### System Prompt 和 Cache
```python
# 同模型路径（默认）
review_agent._cached_system_prompt = agent._cached_system_prompt  # line 693
review_agent.session_start = agent.session_start                   # line 701
review_agent.session_id = agent.session_id                        # line 702
```

`_cached_system_prompt` 赋值后，system prompt builder 走 short-circuit 路径，fork 的 system prompt 和父 agent **byte-identical**。加上 `enabled_toolsets` 继承（line 652）保证 `tools[]` 也 byte-identical → Anthropic prefix cache 命中。

### 路由路径（不同模型）
如果配置了 `auxiliary.background_review.{provider,model}`：
- `_cached_system_prompt` 不继承（不同模型 cache key 不同，继承也 miss）
- 全量 replay 改为 `_digest_history()` 压缩（`background_review.py:111-152`），只保留最近 24 条消息 verbatim，早期对话压缩为 synthetic digest
- 目标：尽量减少 cold-written token

## MemoryStore 双状态设计

`tools/memory_tool.py:113-121`：

```
MemoryStore:
  _system_prompt_snapshot: 会话启动时冻结，注入 system prompt，中途不变
                           → 保证 prefix cache 稳定
  memory_entries / user_entries: 实时状态，被工具调用修改，持久化到磁盘
                                 → fork 读写的是这个实时状态
```

### Fork 看到什么 Memory

| 维度 | fork 看到的 | 原因 |
|------|------------|------|
| system prompt 中的 memory context | 会话启动时的**冻结快照**（和父 agent 相同） | `_cached_system_prompt` 继承；snapshot 在 `load_from_disk()` 时构建 |
| `memory` 工具读取的 entries | **实时状态**（包括会话中途新增的） | 共享 `_memory_store` 对象，读 `memory_entries` 实时列表 |
| `memory` 工具写入 | **落同一磁盘** → 父 agent 可见 | 共享 store，`apply_batch()`/`add()` 走同一个 `_save_file()` |
| 外部 memory 插件（agentmemory 等） | **全部跳过** | `skip_memory=True` → 不构建 `_memory_manager` |
| `<agentmemory-context>` 块 | **没有** | `skip_memory` 跳过 prefetch_all |

### 为什么不直接读实时状态就能判断？

Fork 在做出 memory 决策时主要依赖：
1. **对话历史**（`messages_snapshot`）—— 看到完整的 turn 对话
2. **system prompt 中的冻结快照**—— 知道会话开始时已经有哪些记忆
3. **Review prompt 指令**—— 告诉 fork 找"新出现的偏好/模式"

如果 fork 想确认某条记忆是否已存在，它**可以**调 `memory` 工具（会报 `old_text` 缺失 → 返回 `current_entries`，间接暴露实时状态）。但在 system prompt 层面，它只看得到冻结快照。

## 隔离设计

### 零用户可见泄露
```python
# background_review.py:605-607
with open(os.devnull, "w") as _devnull, \
     contextlib.redirect_stdout(_devnull), \
     contextlib.redirect_stderr(_devnull):
```
stdout/stderr 全部重定向到 `/dev/null`。`suppress_status_output=True`（line 677）补充封锁 `_emit_status` → `_print_fn` 这条绕过 `sys.stdout` 的通道。

### Non-interactive Approval
```python
# background_review.py:591-596
def _bg_review_auto_deny(command, description, **kwargs):
    return "deny"
```
Fork 不能用 `input()` 弹窗——会和父进程的 prompt_toolkit TUI 死锁。所有危险命令直接 deny。

### Tool Whitelist
```python
# background_review.py:728-741
review_whitelist = {
    t["function"]["name"]
    for t in get_tool_definitions(enabled_toolsets=["memory", "skills"], ...)
}
set_thread_tool_whitelist(review_whitelist, ...)
```
Fork 只能调用 memory 和 skill_manage 工具。read_file / terminal / search / browser 等全部被 thread-level whitelist 拦截。

### 禁止压缩和关闭
```python
review_agent.compression_enabled = False       # line 720 — 不抢占父 session 的压缩
review_agent._end_session_on_close = False     # line 709 — 不终结父 session 的 DB 行
review_agent._skip_mcp_refresh = True          # line 664 — 不引入新 MCP 工具破坏 tools[] 一致性
```

## 结果报告

`summarize_background_review_actions()`（line 362-541）解析 fork 的 tool call 历史：
- 过滤掉 `messages_snapshot` 中已有的 tool 结果（避免把旧操作重报成 fresh action）
- 匹配 `memory` 和 `skill_manage` 调用
- 支持三种通知模式：`off`（静默）、`on`（通用摘要）、`verbose`（含内容预览）

## 与 Wiki 文档的对应

本文档是对 `wiki/_drafts/hermes-background-review.md` 中"Fork 模型"章节（2.2）的源码级展开。Wiki 文档描述了继承/差异的对比表，本文档提供精确的文件名和行号。
