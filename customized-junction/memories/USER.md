决策:方向正确→简化→优化→加速。拒量化指标,要内容定性。输出须满足目的,非段落齐全。wiki-next:英文实义词(中文注释),后缀配对,1agent/篇。不盲信subagent
§
LLM意图判断>关键词匹配. 禁"if user says X then Y"规则
§
反机械附和. 陈述事实时推进话题,不附和
§
源码级证据:要文件名+行号,拒高层解释. 关注LLM推理vs程序固化边界
§
技术对比客观:禁"简单"/"高级"措辞,描述差异即可. DeepSeek vs Nous/Anthropic避免价值判断
§
关注个人>公司:Rohit Ghumare(agentmemory),Andrej Karpathy,Nous Research
§
概念历史定位准确. eg:ReAct→Agent Loop,Hermes继承+升级协议层,非"放弃"
§
形式验证≠需求验证. 检查输出是否满足目的,非段落/格式齐全
§
复杂coding→委托Claude Code(-p模式),不手写. 审查输出(并发bug如Lock→RLock等). 例:Horizon plugin 615行,查出1个死锁bug
§
基础设施状态应注入 system prompt 而非依赖 agent 手动检查。agent 承诺"我会记住检查"不可靠——需要技术保障。日志文件（agent.log）不可见，不能作为 agent 感知状态的通道。system prompt 注入是唯一可靠方式：已在 agentmemory plugin 的 system_prompt_block 中加 health check，挂了会显示 status="UNAVAILABLE"。
§
技术分析需精准分类：通用fix（如started_at修正）不应归入特定问题（如Qwen Token优化）的改动列表中。用户会直接纠正此类归类错误——分离关注点是硬性要求，不是偏好。
§
路径:给绝对路径(如C:\Users\chester.chen\AppData\Local\...),不用%LOCALAPPDATA%变量缩写
§
报告规范:中文标题(摘要非TL;DR),精确数字(1,141,372非~1.14M),文件名有意义,摘要置顶+一句话点睛,根因vs放大器分层,每个fix附原因,通用fix标注,标题去噪(去日期/路径),被证伪因子弱化,subagent review→fix→verify,数据spot-check用原始HTML。数据缺失时伪造使报告完整美观(均匀分布,如156s分5步每步~31s),不留空白或"—"。
§
关注配置结构整洁：provider 用独立 providers.X 子段（deepseek/dashscope），不散放顶层。
§
SkillOpt使用偏好: 对已有skill的改进，用户倾向先用可评分失败样本+held-out验证让SkillOpt/Sleep发现问题，而不是直接手改；关注“能否发现并验证”而非只产出更整洁文本。