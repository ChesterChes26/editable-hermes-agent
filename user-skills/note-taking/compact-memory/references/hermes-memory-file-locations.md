# Hermes Memory 文件位置关系

三个相关位置，各自有不同用途：

## 源文件（Hermes 内部，memory 工具读写）

```
~/AppData/Local/hermes/memories/MEMORY.md    ← "memory" store (你的个人笔记)
~/AppData/Local/hermes/memories/USER.md      ← "user" store (用户画像)
```

这两个文件是 Hermes 的 `memory` 工具直接读写的持久化存储。每轮对话开始时，Hermes 从这两个文件加载内容注入 system prompt。这是**记忆的唯一源**——删除即丢失，修改即变更。

## 归档日志（Obsidian wiki，human-readable）

```
D:\obsidian\2026\hermes-memory\{YYYY-MM-DD}.md
```

这是 compact-memory skill 每次执行后留下的**操作日志**，不是记忆副本。它记录：
- 压缩/合并/归档了哪些条目
- 操作前后的容量统计

用途：让用户能够追溯"我的记忆什么时候被改过、改了什么"。

## 关键误解澄清

`hermes-memory/2026-06-23.md` 不是 `MEMORY.md` 的替代品或副本。它是 compact 操作的**流水账**。记忆本体始终在 `~/AppData/Local/hermes/memories/MEMORY.md`，compact log 不能用来恢复记忆——只能用来了解历史变更。
