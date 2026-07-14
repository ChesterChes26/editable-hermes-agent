# _memory_manager = None 根因分析

2026-06-23 发现：当前运行中的 agent 的 `_memory_manager` 为 None，
尽管 config 正确（`memory.provider: agentmemory`），plugin 可加载。

## 关键代码路径

### session 创建时的 initialize 链路

`cli_agent_setup_mixin.py:384-385`:
```python
skip_context_files=self.ignore_rules,
skip_memory=self.ignore_rules,
```

**这是错配。** `ignore_rules` 的语义是"不加载 AGENTS.md 等 project 规则文件"，
不该同时决定是否初始化 MemoryProvider。虽然默认 `ignore_rules=False` 意味着
正常路径不会被影响，但如果 CLI 以 `--ignore-rules` 或 `--safe-mode` 启动，
或 `HERMES_IGNORE_RULES=1` 环境变量被设，MemoryProvider 也会被跳过。

### agent_init.py 的 MemoryProvider 初始化

`agent_init.py:1140-1201`:
```python
agent._memory_manager = None          # line 1140: 初始设为 None
if not skip_memory:                   # line 1141: skip_memory=True 时整段跳过
    try:
        ...
        agent._memory_manager = _MemoryManager()     # line 1148
        _mp = _load_mem(_mem_provider_name)          # line 1149
        if _mp and _mp.is_available():               # line 1150
            agent._memory_manager.add_provider(_mp)  # line 1151
        if agent._memory_manager.providers:          # line 1152
            agent._memory_manager.initialize_all(...) # line 1194
            _ra().logger.info("Memory provider ... activated")  # line 1195 — 会落盘
        else:
            _ra().logger.debug("... not found or not available")  # line 1197 — DEBUG 不落盘
            agent._memory_manager = None              # line 1198
    except Exception as _mpe:
        _ra().logger.warning("... plugin init failed") # line 1200 — 会落盘
        agent._memory_manager = None                  # line 1201
```

三种情况导致 `_memory_manager = None`：
1. `skip_memory=True` → 整段跳过，保持 line 1140 的 None
2. Provider 未找到/不可用 → line 1198
3. 异常 → line 1201
4. **`_mem_provider_name` 为空字符串** → line 1145 的 `if _mem_provider_name and _mem_provider_name.strip():` 为 False → line 1146-1201 全部跳过，`_memory_manager` 保持 line 1140 的 None。**完全不产生任何日志**——这是最隐蔽的静默失败路径。发生在 `mem_config` 中没有 `provider` key 或其值为空时。

### /new 时的 on_session_switch

`cli.py:6034-6044`:
```python
try:
    _mm = getattr(self.agent, "_memory_manager", None)
    if _mm is not None:
        _mm.on_session_switch(...)
except Exception:
    pass    # 静默吞错
```

如果 `_memory_manager` 是 None，`on_session_switch` 静默跳过。

### sync_turn 自愈的前提

`memory_manager.py:540-542`:
```python
def sync_all(self, ...):
    providers = list(self._providers)
    if not providers:
        return    # ← _memory_manager 是 None 时直接返回
```

**sync_turn 自愈码（`__init__.py:351-361`）在 `_memory_manager` 是 None 时永远不会被调用。**

## 诊断方法

### 确认 _memory_manager 是否为 None

尽管 plugin logger 不落盘，可以通过以下方式诊断：

```python
# 方法 1：查 state.db（唯一可靠的证据）
# ⚠ 注意：fence tag 是 <memory-context>（memory_manager.py:157），不是 <agentmemory-context>
import sqlite3
db = sqlite3.connect('~/AppData/Local/hermes/state.db')
row = db.execute(
    "SELECT id, system_prompt FROM sessions ORDER BY started_at DESC LIMIT 1"
).fetchone()
has_am = '<memory-context>' in (row[1] or '')
# has_am=True  → initialize 执行了
# has_am=False → initialize 未执行，_memory_manager 是 None
```
# 方法 2：runtime 检查（需要在 agent 进程内）
from agent.agent_init import _ra
agent = _ra()
mm = getattr(agent, '_memory_manager', None)
print('_memory_manager:', mm)
# None → 所有 memory provider hook 都不会触发
```

### 确认 skip_memory 是否生效

agent.log 中搜索：
```bash
grep "Memory provider.*activated" agent.log
```
如果某 session 中没有这条 → initialize 未执行 → `_memory_manager` 是 None。

Warning 级别日志（"plugin init failed"）如果真的抛了异常会落盘——搜不到说明不是异常路径，更可能是 `skip_memory=True`。

## 影响范围

`_memory_manager = None` 导致所有 MemoryProvider hook 失效：
- system_prompt_block → 不在 system prompt 中注入 agentmemory context
- prefetch → 不注入相关记忆
- sync_turn → 不记录对话
- on_session_switch → /new 时不注册新 session
- on_session_end → 不触发 consolidation
- on_memory_write → 不镜像 memory 写入

## sync_turn 自愈的边界条件

sync_turn 开头调 session/start 的自愈码**只在以下两个条件同时满足时生效**：
1. `_memory_manager` 不是 None（即 MemoryProvider 已被 add_provider）
2. `sync_all` 被调用（即每轮对话结束后）

如果 initialize 从未执行（`_memory_manager` 是 None），自愈码完全无济于事。
sync_turn 自愈解决的是"session/start 曾失败但后续自动恢复"的场景，
不解决"provider 根本没注册"的场景。
