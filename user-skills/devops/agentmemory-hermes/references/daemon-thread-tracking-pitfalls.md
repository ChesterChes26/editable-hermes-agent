# Daemon 线程追踪 — 10 个踩坑与调试哲学

2026-06-23 `/new` session 切换竞态修复途中踩过的全部坑及方法论教训。

## 调试方法论（核心）

### 原则 1：追踪完整调用链后再注入日志

DIAG 日志只在被注入的层及以下生效。框架层 `except Exception: pass` 会吞掉所有下层异常，让 DIAG 从不触发。

```
run_agent.py:3085     except Exception: pass           ← Layer 3: 全吞, 零日志
memory_manager.py:591  except Exception: logger.debug    ← Layer 2: debug 不落盘
__init__.py:168        return None                      ← Layer 1: 静默返回
__init__.py:sync_turn  logger.warning("DIAG: ...")      ← Layer 0: 你的 DIAG（如果上层吞了，永远不跑）
```

**做法：** 注入日志前先画出完整调用链，标注每一层 `except` 的处理方式（pass/debug/warning/raise）。

### 原则 2：端到端状态验证替代日志验证

Plugin logger 不传播到 root handler — `grep gateway.log` 不可靠。`session/end` 不出现在 Docker 日志中。`grep "DIAG:"` 会漏掉 INFO 级别的日志。

**可靠验证手段（按优先级）：**
1. `state.db` 查 system_prompt 有无 `<memory-context>` — 确认 provider 是否初始化
2. `/agentmemory/sessions` 查 session 是否存在 — 确认 session/start 是否成功
3. `/agentmemory/observations?sessionId=X` 查 observation 列表 — 确认 observe 是否落盘（权威，绕过计数延迟）
4. agent.log 里的 `Memory provider 'agentmemory' activated` — 仅确认 init_agent 路径

### 原则 3：线程追踪 ≠ 结果追踪

`thread.join()` 只保证线程退出，不保证工作成功。如果 `_api()` 返回 None（HTTP 失败），线程"完成"了但数据丢了。

**做法：** 关键异步操作需要检查返回值或带回调的结果确认。`try/finally` + `discard` 只解决线程泄漏，不解决结果验证。

## 10 个具体坑

| # | 坑 | 教训 |
|---|-----|------|
| 1 | `grep "DIAG: init_agent"` 漏掉第 4 条（INFO 级，无 DIAG 前缀） | 先读代码看实际 log level 和格式 |
| 2 | API key 用 terminal 截断值测试 → 401 | credentials 从源文件读，不复制工具输出截断 |
| 3 | Shell 嵌套 curl+Python 转义地狱 | 写独立 .py 文件执行 |
| 4 | Plugin logger 不传播到 gateway.log → 误判未加载 | 用 state.db 验证 plugin 生效 |
| 5 | 声称 "reset=True 不需要处理" → 被用户纠正 | 查代码前不做结论；防御纵深设计 |
| 6 | observationCount 错误解释为"压缩合并" | 先排除时序延迟再下结论 |
| 7 | session/end 日志不显式出现 → 误以为没调 | 不是所有关键操作都有日志 |
| 8 | gateway 测试 ≠ CLI 测试（init_agent vs on_session_switch） | 测试覆盖实际使用路径 |
| 9 | Logger 注入在 Layer 0，被 Layer 1-3 吞掉时不触发 | 注入前画调用链，标注异常处理 |
| 10 | `_flush_observes()` join 了线程但不检查 HTTP 结果 | 结果追踪比线程追踪重要 |

## 修复后的行为速查

```
每轮对话: sync_turn → _do_observe(daemon) → _api("observe") → 1 observation (type=conversation)

/new:
  commit_memory_session → on_session_end → _flush_observes() → session/end(old)
  on_session_switch(reset=True) → _flush_observes() → session/end(old) → clear → session/start(new)

observationCount = 对话轮数（1:1），延迟来自 worker 异步处理，不是压缩
```

## 残留问题

- `_api()` HTTP 失败静默吞错（return None，无日志）— 最实际的风险
- `run_agent.py:3085` `except Exception: pass` — 极罕见（session 内 _memory_manager 不变）
- `_submit_background` inline fallback `logger.debug` — 极罕见（资源耗尽）
