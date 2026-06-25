决策框架:方向正确→简化→优化→加速. 拒绝量化指标(行数/段落数)要求内容级定性判断. 区分形式vs需求验证:输出须满足目的,非段落齐全. wiki-next:英文实义词(中文注释),后缀配对,1 subagent/篇. 不盲信subagent
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
要求root cause分析非表面修复; 要求验证非假设; 抵触未证实的结论. 代码修改后必须先逐路径验证再声称完成——被纠正过"你确定改对了？安全吗？"。修改申明必须附带验证证据（四条路径都覆盖/实际curl测试/对照表），不允许"看起来对"就交差.
§
重视概念的历史定位准确性。当用户发现 wiki 文档对某个概念（如 ReAct）的定位有偏差时，会要求修正——不只是改措辞，而是重新确立它在演进脉络中的位置。例：旧文档称 Hermes「放弃」ReAct，被纠正为 ReAct 发明了 Agent Loop，Hermes 继承并升级了协议层，Loop 结构完全同构。用户理解在持续进化——新吸收的信息会触发对旧文档的重新审视。
§
区分形式验证和需求验证：不满足段落齐全/格式/MUST句式等表面检查。要求验证输出是否满足目的——约束无遗漏、agent可执行、认知负担真降低了。机械检查=没检查