WeChat: 72fc9745a445@im.bot | QQ Bot: 1904166052 | Windows 10 中文用户, Obsidian vault D:\obsidian\2026. 好奇 Agent 内部机制, 偏好 Agent 驱动自动化
§
Prefers LLM intent judgment over hardcoded keyword matching. Don't write "if user says X then Y" rules — use semantic understanding to detect intent.
§
反感机械附和。当用户陈述事实或感受时，不要为了迎合而附和（如"天气不错"→"天气确实不错"）。直接承认事实，推进话题。用户曾因此明确纠正。
§
Values portable/reproducible agent setups — wants ability to losslessly replicate Hermes config (skills, platforms, patches) across machines. Currently has weixin+qqbot gateways with heavy source patches, multiple custom skills.
§
追问时要求源码级证据：不接受高层解释，会持续追问直到看见具体的代码路径、文件名、行号。对"LLM 推理 vs 程序固化"的边界有明确兴趣。回答 Hermes 内部机制问题时必须追溯源码。
§
技术对比必须客观中立，不通过措辞暗示优劣（禁用"简单的"vs"高级"等措辞），描述差异和不同设计选择即可。曾被多次纠正：DeepSeek vs Nous/Anthropic 对比时避免价值判断。
§
关注 AI agent 生态中的具体人物和作品，不止公司/项目。已知关注: Rohit Ghumare (rohitg00, agentmemory/skillkit), Andrej Karpathy, Nous Research。提问时引用个人作品，期望 agent 定位到具体的人而非泛泛搜索。
§
用户偏好: 任何skill相关操作必须先skill_view加载再执行, 凭记忆做会被纠正. 区分skill(流程规范)和memory(行为教训); 要求root cause分析非表面修复; 要求验证非假设; 抵触未证实的结论.