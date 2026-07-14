# 中英文双语标签对照

本流水线涉及的 UI 元素在不同系统语言下可能是中文或英文，且同一功能在不同 Office/插件版本下措辞可能不同（如 "安排会议"/"新建会议"/"预定会议"）。下表仅供**语义参考**——帮助理解控件功能，**不是精确匹配字典**。

## 常见对照表

| 功能（语义） | English 常见 | 中文 常见 |
|------|---------|------|
| 安排会议按钮 | Schedule Meeting | 安排会议 / 新建会议 |
| 日历导航按钮 | Calendar | 日历 |
| 腾讯会议弹窗 — OK | OK | 确定 |
| 腾讯会议弹窗 — Cancel | Cancel | 取消 |
| 腾讯会议弹窗 — Waiting Room | Enable Waiting Room | 启用等候室 |
| 腾讯会议弹窗 — 标题 | Tencent Meeting-Schedule Meeting | （通常不变） |
| 主窗口标题 | … - Outlook | … - Outlook（不变） |
| 会议窗口标题 | … - Meeting | … - 会议 |
| 弹窗 — 产品通知 | Product Notice / Activate | 产品通知 / 激活 |
| 弹窗 — 提醒 | Reminder(s) | 提醒 |
| 弹窗 — 关闭按钮 | Close / Close this message | 关闭 / 关闭此消息 |

## 核心原则（按优先级）

1. **以 UIA 树实际 label 为准** — 不要假设一定是表中某个值，始终 `get_window_state` 后读取实际内容
2. **element_index 不受语言影响** — 按索引点击对任何语言都一致，是首选交互方式
3. **`query` 搜索用子串 + 重试** — 一种语言搜不到结果时，换另一种语言的部分关键字再搜（如 "Meeting" → "会议"，"安排" → "Schedule"）
4. **role 定位比 label 更稳定** — `role=Button` 的 "Schedule Meeting" vs "安排会议" 是同一个按钮，索引相同
5. **不同版本措辞可能不同** — 上表只是常见形式，实际可能为 "新建会议"/"预定会议"/"启用等候室"/"开启等候室" 等变体

## 窗口标题匹配

中文 Windows 上 Outlook 主窗口标题为 `收件箱 - ... - Outlook`（日历视图为 `日历 - ... - Outlook`），英文为 `Inbox - ... - Outlook`。截图和窗口查找统一使用 `--title-substring "Outlook"` 适配两种语言。"Tencent Meeting" 对话框标题则与系统语言无关。
