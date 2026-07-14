# COM 混合方案 — 背景与原理

## 为什么需要 COM

经典 Outlook 的会议窗口使用 `rctrl_renwnd32` 自定义表单控件，不支持 UIA 缓存树遍历（`BuildUpdatedCache failed: 0x80040201`）。cua-driver 可以点击 Ribbon 按钮打开/关闭窗口，但**字段级交互不可靠**——Tab 导航、`type_text` 填充字段、点击 Send 均无法稳定工作。

COM (`win32com.client`) 绕过 UIA 树，直接操作 `AppointmentItem` 对象。

## 能力矩阵

| 能力 | cua-driver (UIA) | COM | 说明 |
|------|-----------------|-----|------|
| 打开会议窗口 | ✅ | ❌ | Ribbon 按钮 UIA 树完整 |
| 腾讯会议插件弹窗 | ✅ | ❌ | 弹窗 UIA 树完整（15 elements） |
| 填充表单字段 | ❌ | ✅ | `rctrl_renwnd32` UIA 树不可用 |
| Send 按钮 | ❌ | ✅ | 像素盲点 0% 命中率 |
| 读取会议属性 | ❌ | ✅ | Subject, Location, Body |

## 前置条件

- **经典 Outlook (Microsoft Office Outlook)** — 必须已安装且运行。`launch_path` 含 `OUTLOOK.EXE`（通常在 `C:\Program Files\Microsoft Office\root\Office16\`）
- **pywin32** — COM 接口依赖：`pip install pywin32`
- **cua-driver MCP 工具已连接** — 不可降级到 Bash CLI

### 平台识别

通过 `list_apps` 区分：
- **经典版**：`launch_path` 含 `Office16\OUTLOOK.EXE`（或其他版本如 `Office19`） → ✅ 可用
- **New Outlook**：`bundle_id` 含 `Microsoft.OutlookForWindows` → ❌ 不可用（WebView2，无 COM）
- **OWA**：浏览器应用 → ❌ 不可用

## COM 封装脚本

所有 COM 操作通过 skill 内建脚本 `scripts/compose.py` 完成（永久存在，不跨 session 创建临时脚本）。

```bash
python "$SKILL_DIR/scripts/compose.py" compose --to <email> --start "YYYY-MM-DD HH:MM" --end "YYYY-MM-DD HH:MM"
```

支持子命令：`compose`（填充表单）、`send`（发送）、`location`（读取 Location）。

## 关键事实

- 主窗口 UIA 树正常（~100 elements）
- 腾讯会议对话框 UIA 树正常（15 elements，含 Waiting Room checkbox + OK button）
- 会议窗口 UIA 树始终失败：`BuildUpdatedCache failed: 0x80040201`
- COM `Dispatch()` 连接现有 Outlook GUI 实例成功，`GetActiveObject()` 失败（Outlook 不注册 ROT）

### 🔴 ROT（Running Object Table）注册 — 为什么必须先 Dispatch

当用户通过双击 `.lnk` / 任务栏图标交互式启动 Outlook 时，Outlook 可能**不注册到 ROT**，
导致 `GetActiveObject()` 挂死。更严重的是：如果 Outlook 从未被 COM `Dispatch()` 过，
ROT 中根本没有 `Outlook.Application` 条目 —— 后续所有 COM 调用都可能失败。

**修复方法：在任何 GUI 操作（`launch_app`）之前，先运行一次 `Dispatch('Outlook.Application')`。**
- 如果 Outlook 未运行 → COM 自动冷启动，并正确注册到 ROT ✅
- 如果 Outlook 已交互式运行 → `Dispatch()` 强制触发 ROT 注册 ✅
- 之后再调用 `launch_app` 是幂等的（不会重复启动），仅用于确认窗口可见
- 此后所有 `Dispatch()` 调用都可靠

```bash
# Step 0c 必须先做这个（在 launch_app 之前）
python -c "import win32com.client; o=win32com.client.Dispatch('Outlook.Application'); print('COM registered')"
```

此方案仅 Windows（COM 是 Windows 独占）
为什么必须先点插件再 compose：腾讯会议插件创建 AppointmentItem 并设好 Location + Body。compose.py 只追加用户字段，不创建会议。跳过插件则无 AppointmentItem 可操作

## COM 管道验证

在 Step 1 前运行，确保 pywin32 + Outlook COM 注册正常：

```bash
python -c "import win32com.client; o=win32com.client.Dispatch('Outlook.Application'); a=o.CreateItem(1); a.Subject='VERIFY-TEST-DELETE-ME'; a.Start='2026-07-01 08:30'; a.End='2026-07-01 08:35'; a.Save(); a.Delete(); print('COM pipeline OK')"
```
