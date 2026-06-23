patches: WeChat ITEM_NOTE(type8)+obsidian-sync auto-load | weixin.py; qqbot auto-load obsidian-sync
§
wiki: D:/obsidian/2026/wiki/; YAML frontmatter+wikilinks; index.md/log.md per category; dirs: concepts(概念)/entities(实体)/comparisons(对比)/queries(问答)/raw(源材料); SCHEMA tags; new pages update index+log
§
vault: D:/obsidian/2026→github.com/ChesterChes26/obsidian-2026 (leon88726@hotmail.com); .gitignore: .obsidian/ .trash/; post-edit: git add -A && git commit -m "..." && git push
§
wiki风格: 口语化中文, 标题用问句/隐喻, 先动机后机制, 末句总结; 保留技术细节换包装. in llm-wiki skill
§
A2A: default(A,:8642,WeChat/QQ入口)+worker(B,:8643,纯推理); A curl B→B curl A异步链; API_SERVER_KEY per-profile; Gateway与CLI独立进程; B=127.0.0.1外部不可达
§
A2A caller: [CALLER: hermes-a/b/c] msg prefix软约定; B仅认a/c; 127.0.0.1故外部不可达; C远程需反向代理硬认证(per-caller key/IP/TLS)
§
network: corp DNS blocks Google; Bing OK(limited CN results); GitHub API works; DDG often empty; VPN→SSL unstable; Google搜索多路径或请用户分享URL
§
agentmemory: Docker(:3111), DeepSeek flash, 本地embed. 恢复: docker restart→/new(init→session/start); sync_turn自愈. Gateway /new靠init重build. 吞错链: run_agent:3085(except:pass×2)+memory_manager:591(debug不落盘)+__init__:168(return None)+daemon. 排查搜except:pass+return None. /new竞态已修复: flush→end→clear→start.
§
教训: compact-memory执行前必须skill_view加载, 凭记忆做漏了Phase顺序+日志格式. 任何skill相关操作先加载再执行.
§
plugin diag pitfall: logger需要import logging+getLogger否则NameError; on_session_switch exception→logger.debug(不落盘) vs initialize_all→logger.warning(落盘). plugin logger不传播到root handler→DIAG不可见; 用state.db验证.
§
state.db验证法: system_prompt查<memory-context>(true tag, memory_manager.py:157), 非<agentmemory-context>(用户笔记误报). DIAG日志不可靠→plugin logger不传播.
§
_memory_manager=None第4路径: agent_init.py:1145 strip() check失败→全段跳过→无日志. mem_config无provider或空值时触发. sync_turn自愈前提: _memory_manager已有provider注册.
§
agentmemory /new fix (2026-06-23): sync_turn tracks observe daemon threads in _pending_observes set. on_session_end+on_session_switch(reset=True) call _flush_observes() before session/end. reset path: flush→session/end(parent)→clear→session/start(new). daemon try/finally ensures discard. observe still async. ref: agentmemory-hermes/references/new-session-no-reinit.md updated.