---
name: outlook-tencent-meeting-hybrid
description: |
  Chinese variant of the Outlook Tencent Meeting hybrid skill.
  ONLY load this skill when the user explicitly requests Chinese mode
  (e.g., "CN", "中文", "用中文运行", "Chinese mode OFF").
  For the default English-mode skill, use outlook-tencent-meeting-hybrid-en.
version: "2.0.0-hermes"
---

# Outlook 腾讯会议会邀 — 混合自动化 (cua-driver + COM)

> ⚠️ **仅限经典 Outlook (OUTLOOK.EXE)**，New Outlook (WebView2) / OWA / Mac 均不支持。
> `list_apps` 中 `launch_path` 含 `Office16\OUTLOOK.EXE` 的是经典版；`bundle_id` 含 `Microsoft.OutlookForWindows` 的是 New Outlook。
> 详见 `references/com-background.md`。

> **优先级：** 🔴=流程阻断 🟠=严重降级 🟡=边缘健壮 ⚪=参考。优先确保所有 🔴🟠 要求满足。

## 🔴 核心工作原则 — 必须先理解再执行

本 skill 的核心是 **GUI + COM 混合**，两者有严格分工，不能互换：

| 模式 | 负责什么 | 不负责什么 |
|---|---|---|
| **GUI**（cua-driver） | 点击 Ribbon 按钮、截图验证、关闭弹窗 | 填写表单字段、点击 Send |
| **COM**（win32com.client） | 填写表单字段、发送邀请、读取会议属性 | 打开会议窗口、处理插件对话框 |

> **🔴 铁律：会议表单字段（收件人、时间、主题等）和 Send 操作 100% 通过 COM 完成。**
> `type_text`、`set_value`、像素点击等 GUI 方式在会议窗口上**永远不工作**（rctrl_renwnd32 不支持 UIA）。
> 不要尝试、不要试探、不要降级——直接使用 `compose.py compose` 和 `compose.py send`。

> **🔴 COM 连接：** Hermes pipeline 采用 `launch_outlook_gui()` → `compose_meeting(outlook_app=handle)` 路径，COM 句柄直接传递，完全不需要 GetObject/ROT。Claude Code / CLI 路径使用 `dispatch_outlook_app(use_getobject=True)`（GetObject + 重试）。

## 🔴 关闭协议 (Closing Protocol) — 先读这个

本 skill 的**唯一交付物**是 `report.py finalize` 输出的执行报告。
用户没有屏幕——他们只能通过这份报告确认：所有 Step 是否通过、
会议链接是否正确、Token 消耗是否合理。

**铁律：**

1. 所有 Step 完成后，**必须**执行 `report.py finalize`
2. `report.py finalize` 的输出 **= 本 task 的最终回复**
3. 报告输出后 **禁止** 追加任何文字——总结、注释、确认、"任务已完成"均属违规
4. 报告内容 **禁止** 截断或省略——必须完整原样呈现
5. 报告必须作为 chat 可见文本输出——**禁止**将报告留在 Bash tool-result 折叠块中（用户不可见）。`report.py finalize` 返回后，必须将输出原样 echo 到 chat 中，确保用户无需 Ctrl+O 展开即可直接阅读
6. `report.py finalize` 输出后，**必须**立即执行 `report_html.py --open`，生成 HTML 报告并打开浏览器。HTML 报告中每步须包含 `duration` 耗时字段
7. 🔴 **Token 预算：** `capture_snapshot.py` 保存的 PNG 仅用于报告——**禁止**后续 `Read` 或分析。用 `get_window_state`（UIA 树文本）或 `list_windows`（窗口标题）做验证。验证用 `get_window_state` 调用如不需要视觉确认，传 `capture_mode="ax"`，每步省 ~100K+ tokens

**违反任一条 = 任务未完成。** 不是"质量不好"，是没做完。

> 🟡 **report.py 链接错误时的例外：** 如果 `report.py finalize` 输出的会议链接与 `compose.py compose` 输出的不一致（Pitfall #33），允许在报告下方追加一行 `⚠️` 标注实际链接。这是铁律 #3（禁止追加文字）的唯一例外——因为输出错误数据比输出正确数据多一行注释更严重。

报告格式见文末「🔴 执行报告模板」——`report.py finalize` 按模板输出，
你只需将输出完整呈现在 chat 中，不加不减。

## 🔴 执行前不可跳过清单

开始 Step 1 前通读，每完成一个 Step 对照确认，全部 Step 后对照上方铁律逐条自查——**任一条未通过 = 任务未完成**：

```
□ 1. Step 0 MCP 可用性检查通过（list_apps 可调用）
□ 2. 已确认使用经典 Outlook（非 New Outlook / OWA）
□ 3. 每步截图已保存（Step 1-5 共 5 张 📷，Step 2 先截后点 OK）
□ 4. 🔴 每个 Step 截图前已完成状态验证（navigate → verify → screenshot）
□ 5. 🔴 铁律第1条：已执行 report.py finalize
□ 6. 🔴 铁律第2-4条：报告完整原样呈现在 chat 中，无截断无追加
□ 7. 🔴 铁律第5条：报告已作为可见文本 echo 到 chat 中（非 tool-result 折叠块），用户无需 Ctrl+O
□ 8. 🔴 HTML hook 已执行：report_html.py 生成 report.html 到截图目录并自动打开浏览器，每步含耗时
```

## 🔴 Step 0: Token 基线 + MCP 可用性检查

MCP 连接只在 session 启动时建立，中途无法热加载。必须先确认 MCP 工具可用。

### Step 0a: 确保 daemon 运行

> 使用 Python 包装脚本调用 cua-driver。

```bash
# 步骤 1: 确保 daemon 运行
python $SKILL_DIR/scripts/cua.py autostart kick
# 步骤 2: 仅当 kick 返回非零时才启动 serve；否则跳过此步
python $SKILL_DIR/scripts/cua.py serve
# 步骤 3: 验证状态（serve 启动后等待 2s）
python $SKILL_DIR/scripts/cua.py status
```

### Step 0b: 验证 MCP 已连接

直接调用 `mcp_cua_driver_get_config`（返回配置仅 ~100 tokens，比 `list_apps` 的 100K+ 节省大量 token）：
- 工具存在且返回配置 → 继续
- 工具不存在 → **立即中止**，输出以下信息：

```
❌ cua-driver MCP 工具未连接。MCP 只在 session 启动时连接，中途无法热加载。
修复：① 确认 Hermes config 中 mcp_servers.cua-driver 已配置 ② cua-driver serve 运行中 ③ 重启 Hermes session
```

> ⚠️ **绝对不要**降级到 Bash CLI (`cua-driver get_window_state ...`)，会导致每步手动审批。

### Step 0c: Token 基线

```bash
# 记录当前 token 消耗基线（用于 Step 6 计算增量）
python -c "
import sqlite3, os, sys
db_path = os.path.join(os.environ['LOCALAPPDATA'], 'hermes', 'state.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('SELECT input_tokens, output_tokens, cache_read_tokens, api_call_count FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1')
row = c.fetchone()
if row:
    baseline_file = os.path.join(os.environ['TEMP'], 'hermes_tokens_baseline.txt')
    with open(baseline_file, 'w') as f:
        f.write(f'{row[0]}|{row[1]}|{row[2]}|{row[3]}')
    print(f'Token baseline: input={row[0]}, output={row[1]}, cache={row[2]}, calls={row[3]}')
else:
    print('No active session found')
conn.close()
"
```

## 🔴 Hermes 工具调用规则

> **`$SKILL_DIR` 说明：** 本 SKILL.md 中的 `$SKILL_DIR` 是 Hermes skill 系统的占位符，解析为 skill 目录的绝对路径。Hermes 在执行时自动替换。在 bash 命令中直接使用 `$SKILL_DIR/scripts/xxx.py` 即可。

> **🔴 pid/window_id 跟踪：** Hermes 所有 `mcp_cua_driver_*` 窗口操作工具都需要显式传递 `pid` 和 `window_id` 参数。Claude Code 自动从上一次 `get_window_state` 获取——Hermes 不会。每次 `launch_app` 或 `list_windows` 后，记录返回的 `pid` 和 `window_id`，后续所有操作使用这些值。
>
> **🔴 launch_outlook_gui 后必须刷新 window_id：** `launch_outlook_gui()` 返回的 hwnd 可能立即失效；即使它打印 `Outlook GUI visible`，下一次 `get_window_state(pid, returned_hwnd)` 仍可能报 `No window with window_id ... exists`。因此 Step 1 启动后先调用 `mcp_cua_driver_list_windows(pid=<outlook_pid>)`，以标题含 `Outlook`/`日历`/`Calendar` 的当前可见窗口 `window_id` 作为后续唯一主窗口句柄。只有 `list_windows` 找不到可见 Outlook 主窗口时，才走 Pitfall #37 的 `launch_app` 回退。

> **🟡 弹窗 pid 可能不同：** 插件弹出的对话框（如腾讯会议对话框）可能属于不同进程。用 `list_windows` 确认对话框的 pid/window_id。

> **收件人分隔符必须是 `;`（分号），不能用 `,`（逗号）。**
> `--to`（RequiredAttendees）和 `--optional-to`（OptionalAttendees）在 ≥2 人时
> 都必须用分号分隔。Outlook COM 对逗号分隔的邮箱会静默解析错误。
> compose.py 内部会兜底将逗号转为分号，但传入时必须用正确格式。

> UI 标签在中英文系统下可能不同。以 `get_window_state` 实际返回为准，优先用 `element_index` 点击（不受语言影响），需要搜索时用子串重试（如 "Meeting" → "会议"）。不确定时查看 `references/bilingual-labels.md`。

> **🟡 Reminder 弹窗随时可能出现：** Step 0 之后的每个 Step，Outlook 都可能弹出 Reminder 对话框。
> **Reminder 不阻断目标操作时直接忽略。** 如果目标窗口可正常点击和截图，跳过 Reminder 处理。
> 仅当 Reminder 是前台最顶层窗口且直接阻挡下一步点击操作时，才尝试关闭。
> ⛔ 如需关闭：禁止点 "Dismiss" / "Dismiss All"（会触发二次确认），只点关闭按钮（Close / 关闭 / X）。

### Step 1: 启动经典 Outlook（Hermes: COM Dispatch）

> **🟡 Outlook 已在运行？** 如果 `list_apps` 显示 `Outlook (classic)` running + visible window：
> 直接用 `list_windows(pid=<pid>)` 获取 hwnd，跳过 launch 步骤，从弹窗检查开始。
> ⚠️ `compose.py` 内部 `dispatch_outlook_app(use_getobject=True)` 在本机**必定失败**（ROT 不可用）。
> 需要 COM 句柄时用 `win32com.client.Dispatch('Outlook.Application')` 直接连接——
> Outlook 已有 GUI 窗口时 Dispatch 成功连接到运行实例（不会触发 "Only one version" 弹窗）。
> 已验证：2026-07-10 session 中 Outlook pid=36824 已在运行，直接使用，流程正常。

> **Hermes 差异：** 使用 `launch_outlook_gui()` 通过 COM 冷启动并确保窗口可见，
> 而非 `launch_app(path=OUTLOOK.EXE)`。Claude Code 的主进程有 COM 消息泵，
> `Explorers.Add` 后窗口自动可见；Hermes 子进程没有消息泵，需要显式
> `ShowWindow(SW_SHOWNOACTIVATE)` + `ShowWindow(SW_MAXIMIZE)`。
> 详见 `.hermes/README.md`。

```python
# Hermes: 用 COM Dispatch 启动 + 确保 GUI 可见
from _shared import launch_outlook_gui
outlook, outlook_pid, outlook_hwnd = launch_outlook_gui()
# 返回: (COM handle, pid, hwnd) — COM handle 直接传给 compose.py
# PITFALL: 不要用 launch_app({path: "OUTLOOK.EXE"})——COM 句柄不可得

# Check for popups
mcp_cua_driver_get_window_state(pid=<outlook_pid>, window_id=<outlook_hwnd>, capture_mode="ax") → 检查弹窗：
  "Product Notice" / "Activate" → mcp_cua_driver_click(pid=<outlook_pid>, window_id=<outlook_hwnd>, element_index=<close_btn>)
  "Reminder(s)" → 如果不阻挡主窗口操作，直接忽略
    如需关闭：⛔ 禁止点 "Dismiss" — 只点关闭按钮（Close / 关闭 / X）

# ── Snapshot ──
python $SKILL_DIR/scripts/capture_snapshot.py --pid <Outlook PID> --title-substring "Outlook" --output $SKILL_DIR/snapshots/<UUID>/step1_main_window.png --update-state-key step1
```

### Step 2: 点击 Schedule Meeting + 处理腾讯会议对话框

```text
主窗口 mcp_cua_driver_get_window_state(pid=<outlook_pid>, window_id=<outlook_window_id>) → 找到 "Schedule Meeting" / "安排会议" 按钮 → mcp_cua_driver_click(pid=<outlook_pid>, window_id=<outlook_window_id>, element_index=<btn_index>)

# ── 🟡 按钮查找策略 ──
# 1. 先尝试 capture_mode="som" + query="Schedule Meeting"
# 2. 如果无匹配 → 立即用 capture_mode="ax" 重试

# ── 🔴 验证：找到 Schedule Meeting 按钮 ──
如果找不到 → 立即中止（可能 Simplified Ribbon）

# ── 🔴 验证：确认 Tencent Meeting 对话框存在 ──
mcp_cua_driver_list_windows(pid=<outlook_pid>) → 确认标题含 "Tencent Meeting" 的窗口
# 🔴 记录对话框的 pid/window_id（可能属于不同进程！）
tencent_pid = <dialog_pid>
tencent_window_id = <dialog_window_id>

对话框 mcp_cua_driver_get_window_state(pid=<tencent_pid>, window_id=<tencent_window_id>, capture_mode="ax") → 确认控件

# ── Snapshot（⚠️ 先截后点——OK 后弹窗立即关闭）──
python $SKILL_DIR/scripts/capture_snapshot.py --pid <Outlook PID> --title-substring "Tencent Meeting" --output $SKILL_DIR/snapshots/<UUID>/step2_tencent_dialog.png --update-state-key step2

# 点 OK / 确定
mcp_cua_driver_click(pid=<tencent_pid>, window_id=<tencent_window_id>, element_index=<ok_btn_index>)
```

### Step 3: 等待会议窗口 → COM compose

> ⛔ **COM 模式切换闸门：到此为止，GUI 模式正式结束。**
> 从这一步开始，**所有**表单填写和发送操作 **100% 通过 COM 完成**。
> ⛔ **绝对禁止：** `type_text` 填字段、`set_value` 设值、像素点击 Send、Tab 导航、Alt+S 发送。
> 这些 GUI 方式在 rctrl_renwnd32 窗口上**永远不工作**——不是"不太可靠"，是"完全不工作"。

**Hermes pipeline（推荐）：** 使用 COM 句柄，跳过 GetObject：

```python
# outlook 来自 Step 1（launch_outlook_gui() 或 Dispatch）
# ⚠️ compose_meeting() 必须传 subject 参数（非可选！）
from compose import compose_meeting
compose_meeting(
    to="chesterchen@augmentum.com.cn;lizhangjie130@outlook.com",
    subject="chuckGen预定的会议",      # 🔴 REQUIRED — 不传会 TypeError
    start_str="2026-07-11 08:00",
    end_str="2026-07-11 09:00",
    snapshot_dir="$SKILL_DIR/snapshots/<UUID>",
    outlook_app=outlook,    # <-- 传入 COM 句柄
)
```

> **🟡 COM 句柄获取回退：** 如果 Step 1 没有保存 `launch_outlook_gui()` 返回的句柄，
> 或 Outlook 已在运行但无句柄，用 `win32com.client.Dispatch('Outlook.Application')`
> 直接连接——**不要用 `dispatch_outlook_app(use_getobject=True)`**（ROT 不可用，必失败）。
> Dispatch 在 Outlook 已有 GUI 窗口时连接到运行实例，不会触发 "Only one version" 弹窗。

**Claude Code / CLI（兼容）：** 如果 GetObject 可用（机器有 ROT 注册），也可以用 CLI：

```text
mcp_cua_driver_list_windows(pid=<outlook_pid>) → 确认有标题含 "Meeting" / "会议" 的窗口
# PITFALL: rctrl_renwnd32 窗口不支持 UIA 树，不能用 get_window_state 验证控件

python $SKILL_DIR/scripts/compose.py compose --to <email> --start "YYYY-MM-DD HH:MM" --end "YYYY-MM-DD HH:MM" --snapshot-dir $SKILL_DIR/snapshots/<UUID> [--subject "<自定义主题>"] [--optional-to "<可选参会人>"]
```

### Step 4: 发送

**Hermes pipeline（推荐）：** `compose.py send` 内部调用 `dispatch_outlook_app(use_getobject=True)`，在 ROT 不可用的机器上**必定失败**。使用直接 COM 发送：

```python
# outlook 来自 Step 1（launch_outlook_gui() 返回的 COM handle）
# 或 win32com.client.Dispatch('Outlook.Application')
import time
for i in range(1, outlook.Inspectors.Count + 1):
    insp = outlook.Inspectors.Item(i)
    item = insp.CurrentItem
    if item and hasattr(item, 'Subject') and '<会议主题关键字>' in item.Subject:
        item.Send()
        time.sleep(2)
        break
```

**Claude Code / CLI（兼容）：**

```text
python $SKILL_DIR/scripts/compose.py send
```

# ── 验证：确认会议窗口已消失 ──
mcp_cua_driver_list_windows(pid=<outlook_pid>) → 检查是否还有标题含 "Meeting" 的窗口
  如果仍存在 → 等待 2s → 重新 mcp_cua_driver_list_windows(pid=<outlook_pid>)
  如果仍存在 → WARNING（Send 可能未完成），继续截图
  如果已消失 → 确认主 Outlook 窗口（标题含 "Outlook"）可见

# ── 验证：切换到已发送邮件确认邀请已发出 ──
主窗口 mcp_cua_driver_get_window_state(pid=<outlook_pid>, window_id=<outlook_window_id>) → 找到 "Mail" / "邮件" 按钮 → mcp_cua_driver_click(pid=<outlook_pid>, window_id=<outlook_window_id>, element_index=<mail_btn>)
等待 1s
主窗口 mcp_cua_driver_get_window_state(pid=<outlook_pid>, window_id=<outlook_window_id>) → 在文件夹面板找到 "Sent Items" / "已发送邮件" → mcp_cua_driver_click(pid=<outlook_pid>, window_id=<outlook_window_id>, element_index=<sent_btn>)
等待 2s
mcp_cua_driver_get_window_state(pid=<outlook_pid>, window_id=<outlook_window_id>) → 扫描邮件列表，查找主题含会议主题或 "Tencent Meeting" 的邮件
  如果找到 → 邀请已成功发送 ✓
  如果未找到 → WARNING（可能需要更多时间同步），继续截图

# ── Snapshot ──
python $SKILL_DIR/scripts/capture_snapshot.py --pid <Outlook PID> --title-substring "Outlook" --prefer-substring "已发送" --output $SKILL_DIR/snapshots/<UUID>/step4_sent_items.png --update-state-key step4 --warn-only
```

### Step 5: Calendar 验证 + 最终报告

```text
# 5a: 切换到 Calendar 视图
主窗口 mcp_cua_driver_get_window_state(pid=<outlook_pid>, window_id=<outlook_window_id>) → 找到 "Calendar" / "日历" → mcp_cua_driver_click(pid=<outlook_pid>, window_id=<outlook_window_id>, element_index=<cal_btn>)

# 5b: 🔴 验证 Calendar 视图已加载
重新 mcp_cua_driver_get_window_state(pid=<outlook_pid>, window_id=<outlook_window_id>) → 检查窗口标题是否包含 "日历" 或 "Calendar"
  或检查 UIA 树中是否出现日历专属元素（日期网格、月/周视图控件等）
  如果未确认 Calendar 视图：
    → 重新 mcp_cua_driver_get_window_state(pid=<outlook_pid>, window_id=<outlook_window_id>)（刷新 element_index，因视图可能已变）
    → 重新 mcp_cua_driver_click(pid=<outlook_pid>, window_id=<outlook_window_id>, element_index=<cal_btn>)
    → 等待 2s → 再次 mcp_cua_driver_get_window_state 验证 → 仍失败则 WARNING 继续
# PITFALL: 不要跳过 Calendar 验证直接截图——窗口标题可能仍是 Mail 视图的 "收件箱/Inbox"

# 5c: 验证会议
# 优先用 Calendar 视图 UIA 树验证：如果 get_window_state(capture_mode="ax") 已明确出现目标日期、时间段、主题、Location，
# 该验证已足够，可跳过下面 COM 日历枚举，避免在大日历/重复事件集合上 Items.Restrict 长时间阻塞。
# 仅当 UIA 树看不到目标会议或需要额外确认 RequiredAttendees 时，再运行 COM 验证，并给 terminal 设置超时。
python -c "import win32com.client; o=win32com.client.Dispatch('Outlook.Application'); cal=o.GetNamespace('MAPI').GetDefaultFolder(9); items=cal.Items; items.Sort('[Start]'); [print(i.Subject, i.Start, i.RequiredAttendees, i.Location) for i in items.Restrict(\"[Start] >= '<MEETING_DATE> 00:00' AND [Start] < '<NEXT_DAY> 00:00'\")]"

# 5d: 截图 — 用 --prefer-substring 精确匹配 Calendar 窗口
# 中文系统窗口标题为 "日历 - ... - Outlook"，英文为 "Calendar - ... - Outlook"
# 根据 5b get_window_state 返回的标题选择 prefer-substring 值：
#   标题含 "日历" → --prefer-substring "日历"
#   标题含 "Calendar" → --prefer-substring "Calendar"
python $SKILL_DIR/scripts/capture_snapshot.py --pid <Outlook PID> --title-substring "Outlook" --prefer-substring "<日历 或 Calendar>" --delay 3000 --output $SKILL_DIR/snapshots/<UUID>/step5_calendar.png --update-state-key step5 --warn-only

# ── 🔴 铁律第1条 + 第5条 ──
python $SKILL_DIR/scripts/report.py finalize --model "<CURRENT_MODEL>"
# 保存 finalize 的完整 stdout 作为最终 chat 回复文本；不要重新整理或摘要。
# stdout 最后一行通常形如：
#   [report] HTML data exported to: C:\...\outlook_meeting_compose_state.json.html_report.json
# 将该路径作为下一步 report_html.py 的 --data-file。

# ── 🔴 HTML Report Hook（铁律第6条）──
python $SKILL_DIR/scripts/report_html.py --open --data-file "<finalize stdout 中的 HTML data exported 路径>" --model "<CURRENT_MODEL>"
```

### Step 6: Token 统计

```bash
python -c "
import sqlite3, os
db_path = os.path.join(os.environ['LOCALAPPDATA'], 'hermes', 'state.db')
baseline_file = os.path.join(os.environ['TEMP'], 'hermes_tokens_baseline.txt')
with open(baseline_file, 'r') as f:
    baseline = f.read().strip().split('|')
    base_input, base_output, base_cache, base_calls = int(baseline[0]), int(baseline[1]), int(baseline[2]), int(baseline[3])
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('SELECT input_tokens, output_tokens, cache_read_tokens, api_call_count FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1')
row = c.fetchone()
if row:
    delta_input = row[0] - base_input
    delta_output = row[1] - base_output
    delta_cache = row[2] - base_cache
    delta_calls = row[3] - base_calls
    total = delta_input + delta_output
    print(f'Token delta: input={delta_input:,}, output={delta_output:,}, cache={delta_cache:,}, calls={delta_calls}')
    print(f'Total: {total:,} tokens')
else:
    print('No active session found')
conn.close()
"
```

## 🟠 绝对不要做的事 (Pitfalls)

| # | 不要 | 原因 | 替代 |
|---|------|------|------|
| 1 | **用 cua 填会议表单字段** | 会议窗口 UIA 树不可用 (`0x80040201`) | 用 COM |
| 2 | **像素盲点 Send 按钮** | LLM 无视觉反馈，0% 命中率 | 用 COM `item.Send()` |
| 3 | **键盘 Tab 切换字段** | `type_text` Tab (WM_CHAR) 不响应 | 用 COM 直接设值 |
| 4 | **PostMessage Alt+S 发送** | Win32 加速键需要系统级键盘状态 | 用 COM |
| 5 | **GetActiveObject** | 挂死（Outlook 不注册 ROT）。**这台机器已验证：3 种启动方式均不注册 ROT（`references/rot-diagnosis.md`）** | compose.py 内部 `dispatch_outlook_app(use_getobject=True)` 只用 `GetObject` 连 ROT，失败直接报错（不会 fallback 到 Dispatch，避免触发 "Only one version" 弹窗），6 次重试。Hermes pipeline 中可以使用 `compose_meeting(outlook_app=handle)` 传入 `launch_outlook_gui()` 返回的 COM 句柄，完全跳过 GetObject |
| 6 | **type_text 不传 window_id** | 输入路由到错误窗口 → 可能崩溃 | 必须传 `window_id` |
| 7 | **bring_to_front** | 需要 UIAccess 权限 | 不需要——PostMessage 后台工作 |
| 8 | **launch_app 加 start_minimized** | Outlook 冷启动后主窗口永久不出现 | 不加 start_minimized |
| 9 | **依赖 session 内创建的临时脚本** | 不跨 session 持久化 | 用 skill 内置 `scripts/compose.py` |
| 10 | **依赖 compose 阶段输出的 Location** | 插件 Send 时重新生成 meeting ID | 以 Step 5 Calendar 验证为准 |
| 11 | **用 New Outlook** | WebView2，无 UIA/COM | 用经典 Outlook |
| 12 | **MCP 不可用时降级 Bash CLI** | 每步手动审批 | MCP 不可用 → 立即中止 |
| 13 | **compose 前未确认会议窗口** | COM 找不到 inspector | Step 2 点 OK 后 `list_windows` 确认 |
| 14 | **忽略弹窗直接 compose** | 弹窗阻塞 inspector 创建 | Step 1 逐窗口检查关闭所有弹窗 |
| 15 | **忽略 Outlook 安全弹窗** | COM 被安全策略阻断 | 暂停并提示用户 |
| 15a | **Step 0c 验证脚本使用 CreateItem/Save/Delete** | 数据修改触发 Outlook 程序访问安全对话框，阻塞后续 compose.py | 只读验证：仅用 `Dispatch()` + `Inspectors.Count` |
| 16 | **Dispatch 无超时保护** | 可能挂死 | compose.py 内置 30s 超时 |
| 17 | **截图前不验证 UI 状态** | 截图拍到错误视图 | 每个 Step 截图前 navigate → verify → screenshot |
| 18 | **弹窗 get_window_state 预设小 max_elements** | 按钮可能被截断 | 弹窗不传 max_elements |
| 19 | **查找 Ribbon 按钮时 max_depth 太浅** | 按钮在 depth 10 | 不传 max_depth 或设 ≥ 10 |
| 20 | **som 模式 query 无果后反复重试** | 结果一样 | 一次无匹配 → 立即 `capture_mode="ax"` |
| 21 | **`--to` 用逗号分隔多人** | COM 要求分号 | ≥2 人时用分号 |
| 22 | **在 launch_app 之前调用 Dispatch 做 COM 预检查** | 导致 Outlook 以 COM server 模式启动（无 GUI 窗口），Send 后进程退出 | compose.py 在 Step 3 用 `dispatch_outlook_app(use_getobject=True)` 内部处理 COM 连接，不需预验证 |
| 23 | **反复 Read PNG 截图** | ~130K+ tokens/张 | PNG 仅用于报告，验证用 UIA 树 |
| 24 | **每次验证都用默认截图的 get_window_state** | ~130K+ tokens/次 | 传 `capture_mode="ax"` |
| 25 | **Step 1 启动后不最大化** | Ribbon 被压缩 | `launch_outlook_gui()` 内部自动处理 `ShowWindow(SW_MAXIMIZE)` |
| 26 | **Hermes 工具调用不传 pid/window_id** | Hermes 不自动解析（与 Claude Code 不同） | 每次 launch/list_windows 后跟踪 pid/window_id |
| 27 | **假设对话框 pid 与主窗口相同** | 插件对话框可能属于不同进程 | 用 list_windows 确认对话框的 pid |
| 28 | **Hermes 下 compose.py 直接运行** | `capture_baseline()` 调用 `get_session_jsonl_path()` 要求 `CLAUDE_CODE_SESSION_ID`，Hermes 中不存在 → 脚本退出 code 1 | compose.py v2.0.0-hermes 内置 Hermes 回退（检查 `CLAUDE_CODE_SESSION_ID` env，未设置时读取 `%TEMP%/hermes_tokens_baseline.txt`）。详见 `.hermes/README.md` |
| 29 | **Dispatch 先于 launch_app（Hermes 适配回归）** | `Dispatch()` 先于 `launch_app` 会导致 Outlook 以无窗口 COM server 模式启动。Send 后进程无主窗口保活 → 退出。这是 v2.0.0-hermes 适配时加入 Step 0d Dispatch 预注册引入的回归 | 不在 launch_app 之前调用 Dispatch。compose.py 在 Step 3 内部处理 COM 连接 |
| 30 | **GetObject 失败后 fallback 到 Dispatch** | Dispatch 检测到 OUTLOOK.EXE 已运行 → "Only one version" 弹窗 → 阻塞。**更深层：Outlook 在这台机器上不注册 ROT（见 `references/rot-diagnosis.md`），GetObject 永远返回 MK_E_UNAVAILABLE，重试无效。** | `_shared.py` 不会 fallback。修复方向：Dispatch 冷启动获 COM 句柄 + GUI 最大化，避免依赖 ROT。详见 `references/rot-diagnosis.md` |
| 31 | **Explorers.Add 创建的窗口不可见** | `Explorers.Add(inbox, 0)` 创建 `rctrl_renwnd32` 窗口时 `WS_VISIBLE` 位为 0 ——窗口**从创建起就是隐藏的**。即使 `Explorer.Caption` 正确、窗口位置正确，用户也看不到。`explorer.Display()` 在无 COM 消息泵的环境中会阻塞超时（Hermes 子进程已验证） | 创建 Explorer 后：① `win32gui.EnumWindows` 按 PID + 类名 `rctrl_renwnd32` 找到 HWND；② `ShowWindow(hwnd, SW_SHOWNOACTIVATE)` 设置 WS_VISIBLE；③ `ShowWindow(hwnd, SW_MAXIMIZE)` 最大化。5 轮循环验证 5/5 通过。详见 `references/dispatch-coldstart.md` |
| 32 | **launch_outlook_gui() 返回 hwnd 未经 list_windows 刷新就用于 get_window_state** | 返回的 hwnd 可能立即失效；本次会话中 `launch_outlook_gui()` 打印 `HWND=9503274 PID=102852`，但 `list_windows(pid=102852)` 显示真实主窗口为 `window_id=5245512`，直接 `get_window_state(...9503274...)` 报 `No window with window_id 9503274 exists`。 | Step 1 后总是先 `mcp_cua_driver_list_windows(pid=<pid>)`，选当前可见 Outlook 主窗口的 `window_id`；只有 `list_windows` 也找不到主窗口时才走 `launch_app({path:"OUTLOOK.EXE"})` 回退，再用 `win32com.client.Dispatch('Outlook.Application')` 获取 COM 句柄。 |
| 33 | **report.py 报告链接与实际不符** | 同一天存在多个同名会议（如 "chuckGen预定的会议"）时，`report.py finalize` 可能匹配到错误的那一个（如全天事件而非 10:00-11:00），输出错误的会议链接。已实测：2026-07-10 session 中 report.py 显示 GzjCDOyCJQeG，实际为 b6LbFW5Gb2v5 | **以 `compose.py` 输出为准**——compose 阶段的 Link/Meeting ID 是权威来源。report.py 输出后检查链接是否与 compose 输出一致，不一致时在报告下方以 ⚠️ 标注实际链接。不以 report.py 的链接为准做后续操作。 |
| 34 | **Outlook 在 Calendar 视图已确认时仍走 Sent Items 来回切换** | 浪费时间和 token。如果用户本来就在 Calendar 视图（或发送后 Calendar 已可见新会议），无需切换到 Mail → Sent Items → 再切回 Calendar | Step 4 发送后先 `get_window_state(pid, window_id, capture_mode="ax")` 看 Calendar 视图是否已有新会议。如果 UIA 树中可见目标时间槽的会议（Subject/Location 匹配），直接跳到 Step 5 截图，跳过 Sent Items 导航 |
| 35 | **Raw COM 路径不写 state file → report.py finalize 失败** | 当不使用 `compose.py` 而直接用 `win32com.client.Dispatch` + `item.Send()` 时，`outlook_meeting_compose_state.json`（位于 `%TEMP%`）不会被自动写入。`report.py finalize` 读取该文件，缺少 `baseline`/`to`/`start`/`end` 等必需 key 时报错退出 | 在调用 `report.py finalize` 前，手动写入 state JSON：`python -c "import json,os,tempfile; json.dump({'snapshots':{...}, 'baseline':{'input_tokens':N,...}, 'to':'...', 'start':'YYYY-MM-DD HH:MM', 'end':'YYYY-MM-DD HH:MM', 'subject':'...', 'location':'...', 'meeting_id':'...', 'compose_args':'COM direct'}, open(os.path.join(tempfile.gettempdir(),'outlook_meeting_compose_state.json'),'w'))"` |
| 37 | **只用 `launch_outlook_gui()`，返回 hwnd 失效后不更新 state** | `launch_outlook_gui()` 可能打印出 Outlook PID/HWND，但该 HWND 随即消失；随后 `get_window_state` / `capture_snapshot.py` 报 `No window ... exists` 或 `No visible window found matching title "Outlook"`。本次回退：`mcp_cua_driver_launch_app(path="C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE")` 返回同一 pid 的有效 `window_id`，主窗口恢复可见；同时用 `win32com.client.Dispatch('Outlook.Application')` 取得 COM 句柄。 | 遇到 hwnd 失效时不要重跑 `launch_outlook_gui()`；立即 `launch_app` 获取有效 `pid/window_id`，把 `%TEMP%/outlook_hermes_run_state.json` 中的 `outlook_pid/outlook_hwnd` 更新为新值，再继续 Step 1 截图与后续 COM 流程。 |
| 38 | **report_html.py 的 `--data-file` 用占位符或手猜路径** | `report.py finalize` 会导出 HTML 数据 JSON，并在 stdout 末尾打印 `[report] HTML data exported to: ...json.html_report.json`。如果没有从 finalize stdout 提取该路径，HTML hook 容易失败或打开旧报告。 | 先完整保存/展示 `report.py finalize` stdout；从 `[report] HTML data exported to:` 后面取真实路径，原样传给 `report_html.py --open --data-file "<path>" --model "<CURRENT_MODEL>"`。 |
| 39 | **把 `report.py finalize` 和后续解析脚本串在同一个 Bash pipeline/compound command 里** | 在 Hermes Windows 环境中，terminal 是 MSYS Bash，但 `python` 是 Windows Python；`tee /tmp/foo` 后再用 Python `Path('/tmp/foo')` 会解析成 `\\tmp\\foo` 并失败。更重要的是：后续解析失败会让整个命令 exit 1，污染 finalize 的成功状态。 | `report.py finalize` 单独运行，完整复制其 stdout 到最终回复；HTML data path 直接从 stdout 末行读取。如需保存 stdout，用 Windows 原生临时路径（`os.path.join(os.environ['TEMP'], ...)`）或分两步执行，不要让后处理影响 finalize exit code。 |

## 🔴 执行报告模板

`report.py finalize` 输出格式如下（仅供参考——实际输出由脚本生成，按铁律在 chat 中原样呈现）：

```text
══ Outlook Tencent Invitation — 执行报告 ══

会邀参数:
  主题:       <会议主题>
  收件人:     <email>
  时间:       YYYY-MM-DD HH:MM – HH:MM (UTC+8)
  会议链接:   https://meeting.tencent.com/dm/<id>
  会议号:     <id>
  Waiting Room:  已启用

执行流水线:

  Step 1   确认经典Outlook + 清理弹窗   ✓
    📷 <relative-path>/step1_main_window.png
  Step 2   Schedule Meeting + WR        ✓
    📷 <relative-path>/step2_tencent_dialog.png
  Step 3   COM compose                  ✓  <compose args>
    📷 <relative-path>/step3_meeting_form.png
  Step 4   COM send                     ✓
    📷 <relative-path>/step4_sent_items.png
  Step 5   Calendar 验证                ✓  <date> 找到 N 个会议, Location 匹配
    📷 <relative-path>/step5_calendar.png

Token 消耗:
  输入 tokens:   N
  输出 tokens:   N
  总计 tokens:   N

总耗时:    Xm Ys

状态: 全部 5 步通过 ✓
```

## ⚪ 参考资料（按需查阅，不预加载）

- `references/bilingual-labels.md` — 弹窗 label 识别不确定时查阅
- `references/capture-snapshot.md` — 截图命令参数不清楚时查阅
- `references/com-background.md` — COM 原理或平台识别有疑问时查阅
- `references/dispatch-coldstart.md` — Dispatch + Explorers.Add + ShowWindow 冷启动方案的 5 轮验证证据
- `references/hermes-com-debugging.md` — Hermes 环境下 COM 调试方法论：ROT 枚举 → WS_VISIBLE 诊断 → 修复路径（2026-07-10）
- `references/junction-setup.md` — Hermes junction 部署与重建步骤
- `references/only-one-version-dialog.md` — Dispatch 触发 "Only one version" 弹窗的证据和修复步骤
- `references/outlook-com-hybrid.md` — COM 内部机制（来自父 skill）
- `references/raw-com-workflow.md` — 绕过 compose.py 直接用 raw COM 时的 state file 写入要求和完整流程
- `references/rot-diagnosis.md` — GetObject MK_E_UNAVAILABLE 根因分析 + 修复方向
