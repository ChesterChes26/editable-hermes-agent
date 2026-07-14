# SkillOpt-Sleep 优化已有 operational skill

当用户想把一个已有 Agent skill（如 Outlook + Tencent Meeting + computer-use 混合 skill）变得更好用时，不要默认直接手改 skill。若用户关注“SkillOpt 能否自己发现并验证问题”，应把已知问题转成可评分失败样本，让 SkillOpt-Sleep 用 train/val gate 做发现与验证。

## 关键判断

- SkillOpt 训练的是 skill/memory，不是模型权重或 agent runtime。
- SkillOpt-Sleep 可以发现旧规则问题，但发现能力来自“可评分失败样本”，验证能力来自 held-out gate。
- 不要把有外部副作用的真实 GUI/COM 操作直接当默认 replay；训练期优先验证 agent 的计划/约束遵守，真实 E2E 作为上线前人工验证。

## 推荐流程

1. 保持目标 skill 原样作为 baseline。
2. 写 reviewed `tasks.json`，用 `--target-skill-path` 指向 live SKILL.md。
3. 任务要暴露具体冲突，而不是泛泛写“让 skill 更好”。
4. 用 train tasks 触发失败，用 val tasks 验证泛化；必要时留 test tasks 做最终需求验证。
5. 使用 `--backend mock` 先 dry-run 检查任务文件；真实优化用 `handoff` / `claude` / `codex`。
6. 不开 `--auto-adopt`；review `.skillopt-sleep/staging/<timestamp>/proposed_SKILL.md` 后再 adopt。

## TaskRecord 设计要点

每条任务至少包含：

- `intent`: 用户任务或压力场景。
- `context_excerpt`: 触发冲突的环境事实。
- `attempted_solution`: baseline/错误 agent 会怎么做。
- `reference_kind`: 优先用 `rule` 或强 rubric，不要只靠关键词 soft score。
- `reference` / `judge`: 正负条件都要写清楚。
- `split`: train / val / test。
- `reviewed: true` 放在 payload 顶层，真实 backend 才应接受。

复杂流程 judge 必须惩罚错误 fallback。例如 Outlook meeting skill：

必须通过：
- 使用 `launch_outlook_gui()` 或等价已验证 COM-handle 路径。
- 保留 COM handle 并在 Step 1 后 `list_windows(pid)` 刷新有效 `window_id`。
- meeting form fields 和 Send 走 COM。
- `report.py finalize` 输出完整可见。

必须失败：
- 依赖 GetObject/ROT 作为 Hermes 默认路径。
- 把 `type_text` / `set_value` / Tab / Alt+S / pixel Send 当 fallback。
- MCP 不可用时降级 Bash CLI。
- 强化已知旧规则而不是覆盖它。

## 命令模板

```bash
python -m skillopt_sleep run \
  --project "D:/workspace/<project>" \
  --tasks-file "D:/workspace/<project>/skillopt-sleep-tasks/<name>.tasks.json" \
  --target-skill-path "D:/workspace/<project>/.claude/skills/<category>/<skill>/SKILL.md" \
  --backend handoff \
  --edit-budget 4 \
  --progress
```

## Review proposal 时拒绝

- 大段重写导致原有关键 protocol/pitfall 丢失。
- 把不同 harness 路径混成一套。
- 新增未经验证的 GUI/工具降级。
- 用机械 “if user says X then Y” 替代意图判断。
- 把最终报告协议改成摘要。
