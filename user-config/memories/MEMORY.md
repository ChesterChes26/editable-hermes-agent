fork: github/ChesterChes26/hermes-agent;origin→fork,upstream→NousResearch;src:weixin+qqbot+agent_init;plugins:agentmemory+skills;restore:clone+checkout chester+cp ~/.hermes/+env
§
Obsidian:D:/obsidian/2026→github/ChesterChes26/obsidian-2026;old wiki废弃;wiki-next活跃(86文件:36对+14独立),约束密度定拆否;git push after edits
§
A2A:A(:8642,WeChat/QQ),B(:8643推理);[CALLER:a/b/c]前缀,B仅认a/c;C远程需反向代理硬认证;A↔B异步;API_SERVER_KEY per-profile
§
agentmemory:Docker:3111,DeepSeek flash;/new竞态:flush→end→clear→start;吞错3处(L3085/591/168);diag查state.db;watchdog:HTTP hung→docker restart
§
教训: compact-memory执行前必须skill_view加载, 凭记忆做漏了Phase顺序+日志格式. 任何skill相关操作先加载再执行.
§
plugin update:git pull --ff-only,无.git→报错;agentmemory非git→安全失败;需git init+upstream恢复升级
§
agentmemory watchdog:iii-engine TCP ok但HTTP hung,原tcp_reachable误判→npx弹窗。fix:container_http_healthy()+四层诊断,hung→docker restart
§
ACP(JSON-RPC/stdio)=协议,MCP=协议,A2A(HTTP+[CALLER]前缀)=通信模式。ACP工具调agent,MCP agent调工具,A2A agent委托agent。可交叉
§
GitHub: curl/browser→github.* triggers firewall alert, never use. git via proxy 127.0.0.1:7897 safe
§
subagent审查:用户不信任盲信结果;批量审查需独立agent做review;逐条追问判断逻辑→不接受单agent结论
§
wiki入口:wiki-guide-split v2.0(唯一);obsidian导入已废弃。流程:Phase0底板→Phase1密度→Phase2a拆分或2b单文件→写入管线(index/log/git)。target:wiki-next/
§
wiki拆分:subagent派发前逐篇读内容做密度判断(非看frontmatter);3 subagent并行各5篇走Phase0→2a;完事后逐对review六段/交叉链接/认知减负比
§
wiki-guide-split纪律:即使预判Phase2b(不拆)也必须先Phase0落底板再正式判断。禁止跳Phase0直接写带frontmatter/wikilink/章节结构的成品。底板是纯叙事,不做约束提取。
§
WeChat MP articles: JS-rendered, curl只拿壳。browser_navigate带?scene=等query params可能UTF-8解码失败→去掉params用clean URL即可。全文提取最优: browser_console执行document.querySelector('#js_content').innerText，比snapshot逐段滚动完整且快。
§
hermes skills+plugins sync: git跟踪user-skills/≠运行时skills/; user-plugins/≠plugins/(同构风险)。skill_manage/curator改→落runtime目录; git只看user-*目录→报clean。commit前diff两目录: diff -rq skills/<name>/ hermes-agent/user-skills/<name>/ (plugins同理)。rsync不可用用cp -r。push经代理http://127.0.0.1:7897。