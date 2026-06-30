---
name: outlook-tencent-meeting-hybrid
description: "Send a Tencent Meeting invitation via Outlook Classic using cua-driver UI + COM form-filling hybrid pipeline. Windows only (COM)."
version: 1.4.0
---

# Outlook 腾讯会议会邀 — 混合自动化 (cua-driver + COM)

## 这东西解决什么问题

自动创建并发送腾讯会议邀请：cua-driver 处理 UI（点击按钮 + 插件对话框），COM 处理表单填充（填参会人 + 时间 + 发送），避开 Outlook 自定义会议表单 `rctrl_renwnd32` 的 UIA 树不可用问题。

## 前置条件

```bash
pip install pywin32
```

**不要去找 `outlook_com.py`**——那个文件是旧 session 创建的单文件，早已丢失。所有 COM 操作都走 skill 内置的 `scripts/compose.py`，它永久存在不会丢。

COM 封装脚本内置于 skill 中：`scripts/compose.py`（支持 compose / send / location 三个子命令）。
调用时使用 skill 目录下的绝对路径。在 Hermes Agent 环境中：

```bash
SKILL_DIR="C:/Users/chester.chen/AppData/Local/hermes/skills/computer-use/outlook-tencent-meeting-hybrid"
python "$SKILL_DIR/scripts/compose.py" compose --to <email> --start "YYYY-MM-DD HH:MM" --end "YYYY-MM-DD HH:MM"
```

## 工作流（7 步：Step 0 基线 → 5 步核心 → Step 6 报告）

> **⚠️ 重点：不要花任何时间去 `C:/Users/chester.chen/` 下找 `outlook_com.py`。它不存在。直接 `$SKILL_DIR/scripts/compose.py`。**

执行每一步前先更新 todo 状态。

### Step 0: 记录 token 基线

```bash
# Step 0 — 记 token 基线
python -c "
import sqlite3, os, sys
try:
    conn = sqlite3.connect('file:$HOME/AppData/Local/hermes/state.db', uri=True, timeout=2)
    cur = conn.execute('SELECT input_tokens, output_tokens, cache_read_tokens, api_call_count FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1')
    row = cur.fetchone()
    if row is None:
        print('No active session — skipping token baseline')
        sys.exit(0)
    f = os.path.join(os.environ['TEMP'], 'hermes_tokens_baseline.txt')
    open(f, 'w').write(f'{row[0]}|{row[1]}|{row[2]}|{row[3]}')
    print(f'Baseline written: {row[0]}|{row[1]}|{row[2]}|{row[3]}')
except sqlite3.OperationalError as e:
    print(f'Token tracking unavailable ({e}) — skipping baseline')
    sys.exit(0)
" 2>&1
```

### Step 1: 启动 + 清理弹窗

```text
list_apps → 如果 Outlook 未运行 → launch_app(path=OUTLOOK.EXE)
# 注意：不要用 start_minimized=true，会导致主窗口不显示
# 冷启动后等 ~5s 主窗口出现

list_windows → 检查是否出现激活弹窗：
  "Keep using Outlook"        → 主窗口 UIA 树中 element #8 (关闭按钮) click
  "1 Reminder(s)" 或类似      → ax 模式 get_window_state → click(关闭按钮)
```

### Step 2: 点击 Schedule Meeting + 处理腾讯会议对话框

```
主窗口 get_window_state(ax, query="Schedule Meeting") → click(element_index=#22或#24)
list_windows → 找到 "Tencent Meeting-Schedule Meeting"
对话框 get_window_state(ax, query="Waiting") → click(#2 Enable Waiting Room) → click(#10 OK)
```

### Step 3: 等待会议窗口出现 → COM 接管

```text
list_windows → 确认 "chuckGen预定的会议 - Meeting" 窗口出现

# 使用 skill 内建脚本（替换 SKILL_DIR 为实际路径）
# 注意: compose 阶段打印的 Location (腾讯会议链接) 只是临时的——Tencent Meeting 插件在 Send 后会重新生成 meeting ID，最终链接以 Step 5 为准
SKILL_DIR="$HOME/AppData/Local/hermes/skills/computer-use/outlook-tencent-meeting-hybrid"
python "$SKILL_DIR/scripts/compose.py" compose \
    --to <email> \
    --start "YYYY-MM-DD HH:MM" \
    --end "YYYY-MM-DD HH:MM"
```

### Step 4: 发送

```text
SKILL_DIR="$HOME/AppData/Local/hermes/skills/computer-use/outlook-tencent-meeting-hybrid"
python "$SKILL_DIR/scripts/compose.py" send
```

### Step 5: Calendar 验证

```text
terminal: python -c "
import win32com.client
o = win32com.client.Dispatch('Outlook.Application')
cal = o.GetNamespace('MAPI').GetDefaultFolder(9)
items = cal.Items.Restrict(\"[Start] >= 'YYYY-MM-DD'\")
for i in items:
    # 打印完整字段 — compose 阶段的 Location (Tencent Meeting link) 在 Send 后可能变
    print(i.Subject, i.Start, i.RequiredAttendees, i.Location)
"
```

### Step 6: 报告 token 消耗

读当前 token 数，与 Step 0 基线做差，报告本次 workflow 的消耗。

```bash
python -c "
import sqlite3, os, sys
baseline_path = os.path.join(os.environ['TEMP'], 'hermes_tokens_baseline.txt')
if not os.path.exists(baseline_path):
    print('No token baseline file — token stats skipped')
    sys.exit(0)
try:
    conn = sqlite3.connect('file:$HOME/AppData/Local/hermes/state.db', uri=True, timeout=2)
    cur = conn.execute('SELECT input_tokens, output_tokens, cache_read_tokens, api_call_count FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1')
    now = cur.fetchone()
    baseline = open(baseline_path).read().strip().split('|')
    delta_in = now[0] - int(baseline[0])
    delta_out = now[1] - int(baseline[1])
    delta_cache = now[2] - int(baseline[2])
    delta_api = now[3] - int(baseline[3])
    total = delta_in + delta_out
    print('--- Token 消耗 ---')
    print(f'  API calls:  {delta_api}')
    print(f'  Input:      {delta_in:,}')
    print(f'  Output:     {delta_out:,}')
    print(f'  Total:      {total:,}')
    print(f'  Cache read: {delta_cache:,}')
    print(f'  DeepSeek Flash 估价: 约 ¥{total*0.0000005 + delta_out*0.000002:.4f}')
    print(f'  (估价公式: 输入 ¥0.5/百万 + 输出 ¥2/百万)')
except sqlite3.OperationalError as e:
    print(f'Token tracking unavailable ({e}) — token stats skipped')
    sys.exit(0)
" 2>&1
```

## 绝对不要做的事（Pitfalls）

| # | 不要 | 原因 | 替代 |
|---|------|------|------|
| 1 | **用 cua 填会议表单字段** | 会议窗口 UIA 树不可用 (`0x80040201`) | 用 COM |
| 2 | **像素盲点 Send 按钮** | LLM 无视觉反馈，已尝试 12 次 0 命中 | 用 COM `item.Send()` |
| 3 | **PostMessage Tab 切换字段** | Outlook 自定义表单不响应 | 用 COM 直接设值 |
| 4 | **PostMessage Alt+S 发送** | Win32 加速键需要系统级键盘状态 | 用 COM |
| 5 | **GetActiveObject** | 挂死（Outlook 不注册 ROT） | 用 `Dispatch()` |
| 6 | **type_text 不传 window_id** | 输入路由到错误窗口 → 可能崩溃 | 必须传 `window_id` |
| 7 | **bring_to_front** | 需要 UIAccess 权限 | 不需要——PostMessage 后台上工作 |
| 8 | **`launch_app` 加 `start_minimized=true`** | Outlook 冷启动后主窗口永久不出现 | 不加 start_minimized，静默模式足以避免抢焦点 |
| 9 | **依赖 session 内创建的单文件脚本** | 脚本不跨 session 持久化（如 `outlook_com.py` 第二天就丢了） | 用 skill 内置 `scripts/compose.py`，它永久存在 |
| 10 | **SQLite URI 用 `?mode=ro`** | WAL 模式下 `mode=ro` 看不到未 checkpoint 的数据，导致 `no such table` 或 `None` | 不加 `?mode=ro`；默认连接读 WAL 正常 |
| 11 | **依赖 compose 阶段输出的 Location** | Tencent Meeting 插件在 Send 时会重新生成 meeting ID——compose 时打印的链接可能不是最终链接 | 最终 Location 以 Step 5 Calendar 验证为准 |

## 关键事实

- 主窗口 UIA 树正常（115-131 elements）
- 腾讯会议对话框 UIA 树正常（15 elements，含 Waiting Room checkbox + OK button）
- 会议窗口 UIA 树始终失败：`BuildUpdatedCache failed: 0x80040201`（类 `rctrl_renwnd32` 不支持 `IUIAutomationCacheRequest`）
- COM `Dispatch()` 连接现有 Outlook GUI 实例成功，`GetActiveObject()` 失败
- 此方案仅 Windows（COM 是 Windows 独占）
- COM 脚本：`scripts/compose.py`（skill 内建，永久存在）
