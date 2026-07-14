# Claude Code Skill → Hermes 适配清单

从 Claude Code 项目（`.claude/skills/`）迁移 skill 到 Hermes runtime（`skills/`）时的逐项检查。

## 工具名映射

| Claude Code | Hermes |
|------------|--------|
| `get_window_state(...)` | `mcp_cua_driver_get_window_state(...)` |
| `launch_app(...)` | `mcp_cua_driver_launch_app(...)` |
| `list_windows(...)` | `mcp_cua_driver_list_windows(...)` |
| `click(...)` | `mcp_cua_driver_click(...)` |
| `type_text(...)` | `mcp_cua_driver_type_text(...)` |
| `press_key(...)` | `mcp_cua_driver_press_key(...)` |
| `scroll(...)` | `mcp_cua_driver_scroll(...)` |
| `hotkey(...)` | `mcp_cua_driver_hotkey(...)` |
| `get_config` | `mcp_cua_driver_get_config` |

## pid/window_id（关键差异）

Claude Code 从上次 `get_window_state` 自动继承 `pid`/`window_id`，Hermes **不自动继承**。每个窗口操作工具调用都必须显式传递：

```text
# Hermes 必须手动跟踪:
launch_result = mcp_cua_driver_launch_app({path: "..."})
outlook_pid = launch_result['pid']
outlook_window_id = launch_result['windows'][0]['window_id']

mcp_cua_driver_get_window_state(pid=outlook_pid, window_id=outlook_window_id)
mcp_cua_driver_click(pid=outlook_pid, window_id=outlook_window_id, element_index=5)
```

## 路径

| Claude Code | Hermes |
|------------|--------|
| `.claude/skills/.../scripts/xxx.py` | `$SKILL_DIR/scripts/xxx.py` |
| `.claude/skills/.../snapshots/` | `$SKILL_DIR/snapshots/` |

## Token 追踪

Claude Code 用 JSONL session log，Hermes 用 SQLite `%LOCALAPPDATA%/hermes/state.db`。`report.py` 需双后端（检测 `CLAUDE_CODE_SESSION_ID` 环境变量自动切换）。

## 脚本

所有 `scripts/*.py` 是纯 COM/Win32 API，无 agent 依赖，**直接复制，内容一致**（仅 `report.py` 的双后端差异为有意为之）。

## Junction 开发模式

项目内 `.hermes/` 目录通过 junction 链接到 Hermes runtime：
```powershell
New-Item -ItemType Junction -Path "<runtime>/skills/.../<skill>" -Target "<project>/.hermes/skills/.../<skill>"
```
> 用 PowerShell `New-Item` 而非 `cmd.exe /c mklink` — git-bash 下后者不可靠。

## COM 验证注意

Step 0 COM 验证必须只读（`Dispatch + Inspectors.Count`），禁止 `CreateItem/Save/Delete` — 数据修改触发 Outlook 安全弹窗，阻塞后续 compose.py。
