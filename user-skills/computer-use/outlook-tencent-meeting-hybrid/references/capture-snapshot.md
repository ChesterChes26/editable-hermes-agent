# 截图工具 (capture_snapshot.py)

独立窗口截图工具，使用与 cua-driver 相同的 `PrintWindow + PW_RENDERFULLCONTENT` API，可截取后台/被遮挡窗口。只要窗口不是最小化状态（`SW_SHOWNOACTIVATE` 恢复但不激活），截图就可靠。

## 前置条件

```bash
pip install pywin32 Pillow
```

## 用法

```bash
# 按标题子串匹配（用 "Outlook" 适配中英文，中文标题为 "收件箱/日历 - ... - Outlook"）
python capture_snapshot.py --title-substring "Outlook" --output step1.png

# 按窗口类名匹配
python capture_snapshot.py --class-name "rctrl_renwnd32" --output step3.png

# Warn-only 模式（窗口找不到不报错）
python capture_snapshot.py --title-substring "Outlook" --output step5.png --warn-only

# 自动更新 compose state JSON
python capture_snapshot.py --title-substring "Outlook" --output step1.png --update-state-key step1

# 多窗口歧义消除：优先匹配标题中也含 "Calendar" 的窗口
python capture_snapshot.py --title-substring "Outlook" --prefer-substring "Calendar" --output step5.png

# Pre-capture 延迟（等待 UI 过渡完成，单位 ms）
python capture_snapshot.py --title-substring "Outlook" --delay 500 --output step5.png

# 截图后尺寸校验（拦截 PrintWindow 静默失败产生的空白位图）
python capture_snapshot.py --title-substring "Outlook" --min-width 200 --min-height 200 --output step1.png
```

## 创建截图目录

```bash
python -c "import os, uuid; d='.claude/skills/computer-use/outlook-tencent-meeting-hybrid/snapshots/'+str(uuid.uuid4()); os.makedirs(d, exist_ok=True); print(d)"
```

Agent 读取输出作为 `<SNAPSHOT_DIR>`（UUID 唯一），后续步骤硬编码使用。

## 5 步截图策略

| 步骤 | 截图内容 | 窗口匹配方式 | 触发方式 |
|------|----------|-------------|----------|
| Step 1 | 清理弹窗后的 Outlook 主窗口 | `--title-substring "Outlook"` | Bash 调用 |
| Step 2 | 腾讯会议插件设置对话框 | `--title-substring "Tencent Meeting"` | Bash 调用（⚠️ 先截后点 OK） |
| Step 3 | 已填入字段的会议表单 | `--class-name "rctrl_renwnd32"` | compose.py 自动截 |
| Step 4 | 发送后的 Outlook 主窗口 | `--title-substring "Outlook" --warn-only` | Bash 调用 |
| Step 5 | Calendar 视图 | `--title-substring "Outlook" --prefer-substring "<日历 或 Calendar>" --delay 500` | Bash 调用（需先用 CUA 点 Calendar 按钮 + 验证视图已加载） |

> **中英文适配：** Step 1/4/5 使用 `"Outlook"` 而非 `"Inbox"`/`"Calendar"`，因中文 Windows 标题为 `收件箱`/`日历`。`"Outlook"` 在两种语言下均能匹配。

## 错误处理

- 所有截图失败**不阻断**主流程（会议照常发送）
- Step 4、5 使用 `--warn-only`，窗口找不到时打印 warning 但退出码为 0
- State 文件写入使用原子操作（临时文件 + rename），防止并发损坏
