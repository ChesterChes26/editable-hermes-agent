# Wiki Import: 导入外部 Markdown 文档

将外部分析文档/笔记/文章导入 Obsidian Wiki 的完整流程。

## 适用场景

- 与 Claude Code / Hermes Agent / AI Agent 架构相关的分析文档
- 深度技术文章或笔记
- 外部对话记录或研究报告

## 前提

- 目标文件是纯 Markdown，非 HTML/CSS 类布局文档（HTML 文档参见 `html-to-markdown.md`）
- 文件内容与 wiki Domain（AI Agent 架构与工具设计）相关

## 步骤

### 1. 阅读目标文件

```tool
read_file("D:/path/to/source-file.md")
```

评估内容适合哪个分类：`concepts(概念)/`、`comparisons(对比)/`、`entities(实体)/`、`raw(源材料)/`

### 2. 阅读 SCHEMA 确认最新约定

```tool
read_file("D:/obsidian/2026/wiki/SCHEMA.md")
```

特别检查：frontmatter 格式、tag taxonomy、目录结构、关联页面的路由

### 3. 检查 wiki 已有相关页面

```tool
search_files(target="files", pattern="*关键词*", path="D:/obsidian/2026/wiki")
```

避免重复创建。如果存在相关页面，考虑更新已有页面而非新建。

### 4. 创建概念/对比/实体页

文件路径：`D:/obsidian/2026/wiki/<category>(<中文名>)/<filename>.md`

- 文件名全小写，连字符分隔
- YAML frontmatter（title/created/updated/type/tags/sources/confidence）
- title 用口语化中文问句（用户偏好）
- 添加至少 2 个 wikilink 交叉引用已有 wiki 页面
- 保留原文核心结构（小标题、条款、代码块、表格）
- 可酌情简化/重组非结构化内容为 wiki 风格
- 末尾添加与 Hermes 或相关内容的对比/关联段落以增加 wiki 价值

### 5. 更新 index.md

```tool
pad = patch(path="D:/obsidian/2026/wiki/index.md",
            old_string="### 总页数: <N>",
            new_string="### 总页数: <N+1>")
```
也要更新日期：`2026-06-XX`

在对应分类下插入新条目：
```
- [[concepts(概念)/filename|显示标题]] — <一句话摘要>
```

按字母顺序插入（尽量保持排序）。

### 6. 追加 log.md

```tool
patch(path="D:/obsidian/2026/wiki/log.md",
      old_string="<前一次log的最后一行的文本>",
      new_string="<前一次log的最后一行的文本>\n\n..."
```

格式：
```
## [YYYY-MM-DD] create | <显示标题>
- 类型: concept | comparison | entity
- 文件: [[concepts(概念)/filename]]
- 内容: <一句话内容摘要>
- 来源: <源文件路径>
```

### 7. Git commit & push

```bash
cd /d/obsidian/2026
git add wiki/index.md wiki/log.md "wiki/<category>(<中文名>)/<filename>.md"
git commit -m "wiki: <描述>"
git -c http.proxy=http://127.0.0.1:7897 push
```

## Pitfalls

1. **漏掉 log.md**: index.md 和概念页都创建了但忘了记 log，后续追踪会断。
2. **漏掉 index.md 日期/页数更新**: index 头部元数据必须同步更新。
3. **wikilink 太少**: SCHEMA 要求最少 2 个出链。检查 wiki 已有页面中是否有关联概念。
4. **filename 不规范**: 全小写+连字符，不要用空格或中文文件名。
5. **frontmatter 缺失或错误**: 每页必须 YAML frontmatter，tags 必须来自 SCHEMA taxonomy。
6. **Git push 需要代理**: GitHub 在 corp 防火墙后被拦，必须加 `-c http.proxy=http://127.0.0.1:7897`。
7. **不要 commit 大文件**: wiki 只含 markdown 文本。二进制/图片走 `raw(源材料)/assets/`。
