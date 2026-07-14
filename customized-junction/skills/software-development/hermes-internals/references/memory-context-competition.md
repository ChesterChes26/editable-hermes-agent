# Memory 与 Context Files 的竞争关系

两个独立的注入路径如何争夺同一块上下文窗口。

## 两条注入路径

| 路径 | 触发时机 | 注入位置 | 有上限？ |
|------|---------|---------|---------|
| `system_prompt_block()` | 系统提示词构建时（session 启动 / 压缩重建） | system prompt volatile tier | **无** |
| `prefetch_all()` | **每轮用户消息** | 用户消息末尾 `<memory-context>` 块 | **有**（agentmemory: limit=5, narrative 200 字符） |

## system_prompt_block() — 无上限

`memory_manager.py:413-430` → 调 `provider.system_prompt_block()`，直接拼进 system prompt。
agentmemory 的实现 (`__init__.py:222-229`) 调 `/context` 端点，原样返回 session 上下文，**无截断**。

对比 AGENTS.md：`prompt_builder.py:86` — `CONTEXT_FILE_MAX_CHARS = 20_000`，超出就掐头去尾。
这是核心不对称：上下文文件有硬刹车，memory system_prompt_block 没有。

## prefetch_all() — 每轮都调

```
用户发消息
  → run_conversation()          conversation_loop.py:469
    → build_turn_context()      turn_context.py:64
      → prefetch_all()          turn_context.py:374
        → provider.prefetch(用户消息文本)
        → 包成 <memory-context> 标签(memory_manager.py:296-310)
      → 拼到用户消息末尾         conversation_loop.py:721-732
```

仅在每轮对话开头调一次，不在内部 tool call 循环里重复调。
agentmemory 的 prefetch (limit=5, narrative[:200]) 最多注入 ~1000 字符，这个路径可控。

## 上下文窗口零和博弈

```
总共 128K tokens (DeepSeek V4 Pro)
  - system prompt:
      stable tier:  identity + tools + skills + env hints
      context tier: AGENTS.md / .hermes.md (有 20K 硬上限)
      volatile tier: memory system_prompt_block (无上限)
  - messages (对话历史)
  - tool schemas
  - thinking tokens
```

context files 和 memory **不在同一 tier，不会互相覆盖**。但它们加在一起挤占同一块上下文窗口。

## 压缩救不了

上下文压缩 (`context_compressor.py`) 只压缩 messages，**不压缩 system prompt**。
压缩触发后 system prompt 会整体重建，重新调 `system_prompt_block()`。
如果 memory 很大，重建后的 system prompt 依然很大，压缩等于白做。

## 实际风险排序

1. **system_prompt_block 膨胀**（高风险）：agentmemory observations 积累 200+ 条后，`/context` 返回的块不可控
2. **context window 竞争**（中风险）：AGENTS.md 20K + memory 20K = 40K，还剩 88K 给 messages
3. **prefetch 噪音**（低风险）：5 条 × 200 字符 = 1000 字符，每轮可控

## 缓解方向

- 给 `system_prompt_block()` 返回值加截断（在 provider 层或 memory_manager 层）
- 给 agentmemory `/context` 端点返回加 limit 参数
- 或者直接调 agentmemory API 指定 max 长度
