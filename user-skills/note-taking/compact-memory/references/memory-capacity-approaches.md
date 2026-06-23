# Memory 容量方案对比

2200 字符限制是 Hermes builtin memory 的硬上限。两种解决路径：

## 方案 A：索引代理（改 memory_tool.py）

MEMORY.md 只存文件路径索引 → 实际内容在 Obsidian vault。

```
MEMORY.md:      obsidian-path: 记忆/agentmemory恢复.md
Obsidian:       D:/obsidian/2026/记忆/agentmemory恢复.md (完整内容)
```

### 优势
- 容量无上限（磁盘大小）
- 全部内容在 Obsidian 内可搜索、wikilink、git 版本控制

### 代价
- 必须 patch `memory_tool.py`，每次 Hermes 升级都可能冲突
- System prompt 构建路径增加 I/O（读索引 → 逐个读 Obsidian → 拼接）
- vault 路径变更或文件被移动 → memory 静默断裂
- 持续维护负担

## 方案 B：compact-memory 归档（当前方案）

不改源码，通过 skill 指导 LLM：压缩电报体 → 归档过时条目到 Obsidian → 删除释放空间。

### 优势
- 零源码修改，零升级冲突
- 日常读写无额外延迟
- 归档旧内容自然从上下文窗口退场（环境细节不应永久占 token 预算）

### 劣势
- 硬上限 2200 字符，15-20 条 compact 格式即满
- 依赖 LLM 主动执行归档，遗忘即满
- 归档后内容从 system prompt 消失

## 结论

方案 B 更合理。2200 字符对"当前活跃记忆"足够，强制修剪保持上下文窗口卫生。方案 A 是过度工程，维护成本远大于收益。

若 2200 实在不够，先查 Hermes config 是否有 memory_char_limit 配置项，不改源码。
