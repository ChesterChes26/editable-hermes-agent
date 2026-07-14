# Hermes COM 调试：Outlook ROT 诊断

> 2026-07-10：GetObject 持续返回 MK_E_UNAVAILABLE 的根因排查过程。

## 诊断步骤

### Step 1: ROT 枚举

```python
import pythoncom
rot = pythoncom.GetRunningObjectTable()
enum = rot.EnumRunning()
for moniker in enum:
    ctx = pythoncom.CreateBindCtx(0)
    name = moniker.GetDisplayName(ctx, None)
    if 'outlook' in name.lower():
        print(f"FOUND: {name}")
```

这台机器 ROT 始终只有 3 个系统级 GUID，Outlook 从不出现。

### Step 2: 对比启动方式

| 方式 | ROT 中 Outlook | GetObject |
|------|:---:|:---:|
| `launch_app(path=OUTLOOK.EXE)` | 0 | MK_E_UNAVAILABLE |
| `Dispatch("Outlook.Application")` 冷启动 | 0 | MK_E_UNAVAILABLE |
| 手动双击 OUTLOOK.EXE | 0 | MK_E_UNAVAILABLE |

结论：与启动方式无关——这台机器 Outlook 不在 ROT 注册。

### Step 3: Dispatch 风险验证

`Dispatch("Outlook.Application")` 在 Outlook 已运行时触发
"Only one version of Outlook can run at a time" 对话框（阻塞直到手动关闭）。
→ Dispatch 不可作为 GetObject 的 fallback。

### Step 4: Dispatch + Explorers.Add 窗口可见性

```python
outlook = Dispatch("Outlook.Application")
explorer = outlook.Explorers.Add(inbox, 0)
# rctrl_renwnd32 创建了但 WS_VISIBLE = False
```
```python
ws = win32gui.GetWindowLong(hwnd, GWL_STYLE)
# WS=0x6cf0000 → WS_VISIBLE(0x10000000) = False
```

Claude Code 主进程有 COM 消息泵，窗口自动可见。
Hermes 子进程没有消息泵，需显式 ShowWindow。

### Step 5: 修复

`_shared.py::launch_outlook_gui()`:
1. Dispatch → COM 句柄
2. Explorers.Add → 创建窗口
3. ShowWindow(SW_SHOWNOACTIVATE) → 设置 WS_VISIBLE
4. ShowWindow(SW_MAXIMIZE) → 最大化
5. 返回 (outlook, pid, hwnd)

`compose.py`: compose_meeting/send_meeting/get_location 增加 outlook_app=None 参数。

### 验证

5 轮冷启动循环全部通过（2026-07-10）。
