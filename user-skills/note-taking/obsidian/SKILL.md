---
name: obsidian
description: Read, search, create, and edit notes in the Obsidian vault.
platforms: [linux, macos, windows]
---

# Obsidian Vault

Use this skill for filesystem-first Obsidian vault work: reading notes, listing notes, searching note files, creating notes, appending content, and adding wikilinks.

## Vault path

**This user's vault:** `D:\obsidian\2026`

Use this concrete path directly — do not shell-expand `$OBSIDIAN_VAULT_PATH`. If unset or unreachable, fall back to `D:\obsidian\2026`.

## Vault Layout

```
D:\obsidian\2026\
├── inbox/                     # obsidian-sync image archive
├── memory(记忆)/              # agent behavioral memory (independent)
│   ├── index.md
│   ├── driving(行为)/
│   └── technical(技术)/
├── wiki/                      # [DEPRECATED] 旧 wiki，不再新增内容
├── wiki-next/                 # 当前活跃 wiki，所有新内容走 wiki-guide-split skill
│   ├── SCHEMA.md
│   ├── index.md
│   ├── log.md
│   ├── concepts(概念)/
│   ├── comparisons(对比)/
│   ├── entities(实体)/
│   ├── queries(问答)/
│   └── raw(源材料)/
```

## Folder Naming Convention (MANDATORY)

**ALL folders at every depth use `english(中文)` format.** This applies to the vault root, wiki/, memory(记忆)/, and all subdirectories created in the future.

Examples: `entities(实体)/`, `driving(行为)/`, `raw(源材料)/articles(文章)/`

Do NOT create folders with bare English names. If a new folder is needed, determine the Chinese translation and name it `english(中文)`.

## Read a note

Use `read_file` with the resolved absolute path to the note. Prefer this over `cat` because it provides line numbers and pagination.

## List notes

Use `search_files` with `target: "files"` and the resolved vault path. Prefer this over `find` or `ls`.

- To list all markdown notes, use `pattern: "*.md"` under the vault path.
- To list a subfolder, search under that subfolder's absolute path.

## Search

Use `search_files` for both filename and content searches. Prefer this over `grep`, `find`, or `ls`.

- For filenames, use `search_files` with `target: "files"` and a filename `pattern`.
- For note contents, use `search_files` with `target: "content"`, the content regex as `pattern`, and `file_glob: "*.md"` when you want to restrict matches to markdown notes.

## Create a note

Use `write_file` with the resolved absolute path and the full markdown content. Prefer this over shell heredocs or `echo` because it avoids shell quoting issues and returns structured results.

## Append to a note

Prefer a native file-tool workflow when it is not awkward:

- Read the target note with `read_file`.
- Use `patch` for an anchored append when there is stable context, such as adding a section after an existing heading or appending before a known trailing block.
- Use `write_file` when rewriting the whole note is clearer than constructing a fragile patch.

For an anchored append with `patch`, replace the anchor with the anchor plus the new content.

For a simple append with no stable context, `terminal` is acceptable if it is the clearest safe option.

## Targeted edits

Use `patch` for focused note changes when the current content gives you stable context. Prefer this over shell text rewriting.

## Wikilinks

Obsidian links notes with `[[Note Name]]` syntax. When creating notes, use these to link related content.

## Importing external documents

### Plain Markdown documents → wiki (DEPRECATED)

**Wiki 内容导入已迁移至 `wiki-guide-split` skill。** 不要再用此管线写入 `wiki/` 目录。所有新 wiki 文档通过 wiki-guide-split 走完整流程：Phase 0 生成 → Phase 1 约束密度判断 → Phase 2 拆或留 → review → 写入 `wiki-next/`。

`references/wiki-import-markdown.md` 仅保留作为旧管线的技术记录，不再使用。

### HTML documents → wiki (DEPRECATED)

同上述——HTML 文档若要进 wiki，先转为 Markdown 后交给 wiki-guide-split。转换技术细节保留在 `references/html-to-markdown.md`。

### Codebase → wiki coverage audit

To systematically compare a codebase against existing wiki documentation and identify uncovered subsystems, see `references/codebase-wiki-audit.md`. Covers the full audit pipeline: build module inventory → read headers → map wiki coverage → cross-reference → tier classification → report output.

## Reorganizing vault content (bulk moves + wikilinks)

When bulk-moving files between vault directories and updating all cross-references, use `execute_code` with Python, not shell find/sed. See `references/wiki-reorg-wikilinks.md` for the three wikilink patterns to handle (bare links, normal pipes, escaped pipes in markdown tables), the two-pass strategy, and YAML frontmatter bare-path gotchas. Always run a final scan for remaining old links.
