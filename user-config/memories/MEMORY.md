fork:ChesterChes26/editable-hermes-agent;plugins:agentmemory+horizon;restore:clone+checkout chester+cp user-*→runtime;5-pair diff:skills/plugins/hooks/scripts/memories→user-*/user-config/
§
Obsidian:D:/obsidian/2026→github/ChesterChes26/obsidian-2026;old wiki废弃;wiki-next活跃(86文件:36对+14独立),约束密度定拆否;git push after edits
§
GitHub: curl/browser→github.* triggers firewall alert, never use. git via proxy 127.0.0.1:7897 safe
§
subagent审查:用户不信任盲信结果;批量审查需独立agent做review;逐条追问判断逻辑→不接受单agent结论
§
WeChat MP:JS-rendered;clean URL(去query params)避UTF-8解码;全文:browser_console→document.querySelector('#js_content').innerText
§
shallow clone→git merge-base空→git fetch --unshallow;merge前check:.git/shallow||git rev-parse --is-shallow-repository
§
agentmemory:Docker:3111,DeepSeek flash;/new竞态:flush→end→clear→start;吞错3处;watchdog:container_http_healthy()四层,HTTP hung→docker restart;非git→plugin update安全
§
wiki-guide-split v2.0:Phase0底板→Phase1密度→拆分/单文件→写入管线;target:wiki-next/;必须Phase0;3agent并5篇→逐对review六段/交叉链接/减负比
§
A2A:A(:8642,WeChat/QQ),B(:8643推理);[CALLER]前缀,B仅认a/c;API_SERVER_KEY per-profile。ACP=协议(工具调agent),MCP=协议(agent调工具),A2A=通信模式(agent委托agent)。可交叉
§
hermes sync:git跟踪user-*≠运行时*;commit前diff五对;push经127.0.0.1:7897;上游:fetch upstream→merge main→push→merge chester→uv sync→gateway restart
§
skill操作前先skill_view加载;凭记忆patch必因旧字符串不匹配失败(已验证)。compact-memory同样先加载
§
Office:经典版C2R v16.0.20131;ODT→OfficeSetup.exe;WinHTTP代理须同步并绕过*.msauth.net/*.live.com;WinINET同上;中文UILanguage=2052
§
腾讯会议:下载页JS动态生成链接(curl/wget拿不到URL);Outlook插件仅支持经典Outlook(COM add-in),不支持新版olk.exe;前提需客户端≥2.10+经典Outlook
§
Horizon:PER_TOOL_TIMEOUT=900s;stderr→%TEMP%/horizon_stderr.log;devnull;prod_only锁写工具;绝不用主线程→delegate/cronjob
§
cua-driver:Outlook会议窗(rctrl_renwnd32)UIA不可用(0x80040201);COM hybrid:win32com Dispatch→Inspectors→AppointmentItem;PostMessage Tab/Alt+S无效;type_text须带window_id;GetActiveObject挂→Dispatch;skill:computer-use refs/outlook-form-limitation
§
协作风格:验证session参与架构设计,实时反馈桌面状态纠盲点;偏好混合方案战胜单工具死磕