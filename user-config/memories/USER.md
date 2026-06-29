决策:方向正确→简化→优化→加速。拒量化指标,要内容定性。输出须满足目的,非段落齐全。wiki-next:英文实义词(中文注释),后缀配对,1agent/篇。不盲信subagent
§
LLM意图判断>关键词匹配. 禁"if user says X then Y"规则
§
反机械附和. 陈述事实时推进话题,不附和
§
可移植Hermes配置:fork→ChesterChes26/hermes-agent,weixin+qqbot+agentmemory+skills plugins
§
源码级证据:要文件名+行号,拒高层解释. 关注LLM推理vs程序固化边界
§
技术对比客观:禁"简单"/"高级"措辞,描述差异即可. DeepSeek vs Nous/Anthropic避免价值判断
§
关注个人>公司:Rohit Ghumare(agentmemory),Andrej Karpathy,Nous Research
§
曾被纠正3次
§
概念历史定位准确. eg:ReAct→Agent Loop,Hermes继承+升级协议层,非"放弃"
§
形式验证≠需求验证. 检查输出是否满足目的,非段落/格式齐全
§
复杂coding→委托Claude Code(-p模式),不手写. 审查输出(并发bug如Lock→RLock等). 例:Horizon plugin 615行,查出1个死锁bug
§
基础设施状态应注入 system prompt 而非依赖 agent 手动检查。agent 承诺"我会记住检查"不可靠——需要技术保障。日志文件（agent.log）不可见，不能作为 agent 感知状态的通道。system prompt 注入是唯一可靠方式：已在 agentmemory plugin 的 system_prompt_block 中加 health check，挂了会显示 status="UNAVAILABLE"。