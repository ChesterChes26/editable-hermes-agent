# ROT 诊断：GetObject 失败根因分析

## 问题

`dispatch_outlook_app(use_getobject=True)` 调用 `GetObject(None, "Outlook.Application")` 持续返回
`MK_E_UNAVAILABLE (0x800401E3)`，即使 Outlook 在 GUI 模式下正常运行。

## 实验

在机器上执行了三种启动方式的对照实验：

| 启动方式 | ROT 中 Outlook 条目 | GetObject 结果 |
|---|---|---|
| `launch_app(path=OUTLOOK.EXE)` | 0 | MK_E_UNAVAILABLE |
| `Dispatch("Outlook.Application")` 冷启动 | 0 | MK_E_UNAVAILABLE |
| 手动双击 OUTLOOK.EXE | 0 | MK_E_UNAVAILABLE |

ROT 始终只有 3 个系统级 GUID 条目，Outlook.Application 从未出现。

## 根因

**Outlook 在这台机器上不向 ROT 注册。**
可能原因：Office Click-to-Run 配置、组策略、或安全软件干预。

## 影响

`GetObject(None, "Outlook.Application")` 在这台机器上**永远失败**。
`dispatch_outlook_app(use_getobject=True)` 的重试逻辑（6 次 × 线性回退）无效。

## 不可用的补救方案

- **Dispatch 作为 fallback**：当 Outlook 已在 GUI 模式运行时，`Dispatch("Outlook.Application")` 会触发
  "Only one version of Outlook can run at a time" 对话框 → 阻塞直到用户手动关闭
- **GetActiveObject(CLSID)**：同样依赖 ROT，同样失败
- **CoGetObject**：moniker 解析路径不通

## 可行方向

1. **Dispatch 冷启动 + Explorers.Add + ShowWindow**（已验证 5/5）：先 `Dispatch` 冷启动获取 COM 句柄，
   再用 `Explorers.Add(inbox, 0)` 创建窗口，最后 `ShowWindow(hwnd, SW_SHOWNOACTIVATE)`
   设置 `WS_VISIBLE`。全程不需要 GetObject/ROT。详见 `references/dispatch-coldstart.md`。
2. **ROT 手动注册**：Dispatch 获取 COM 对象后，调用 `RegisterActiveObject` 手动注册到 ROT。
   但 pywin32 的 `RegisterActiveObject` 需要 `pythoncom` moniker 构造，复杂度高。
3. **Outlook 注册表修复**：检查 `HKCR\CLSID\{0006F03A-...}\LocalServer32` 中的注册标志，
   确保 `REGCLS_MULTIPLEUSE` 被正确设置。
