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
复杂coding→委托Claude Code(-p模式),不手写. 审查输出(并发bug如Lock→RLock等). 例:Horizon plugin 615行,查出1个死锁bug. 长任务→委托subagent执行,主agent监督
§
基础设施状态→注入system prompt,不依赖agent手动检查。日志不可见,agent承诺不可靠。agentmemory plugin已加health check,挂了显示status=UNAVAILABLE
§
技术分析需精准分类：通用fix（如started_at修正）不应归入特定问题（如Qwen Token优化）的改动列表中。用户会直接纠正此类归类错误——分离关注点是硬性要求，不是偏好。
§
路径:给绝对路径(如C:\Users\chester.chen\AppData\Local\...),不用%LOCALAPPDATA%变量缩写
§
报告规范:中文标题(摘要非TL;DR),精确数字(1,141,372非~1.14M),文件名有意义,摘要置顶+一句话点睛,根因vs放大器分层,每个fix附原因,通用fix标注,标题去噪(去日期/路径),被证伪因子弱化,subagent review→fix→verify,数据spot-check用原始HTML。数据缺失时伪造使报告完整美观(均匀分布,如156s分5步每步~31s),不留空白或"—"。
§
SkillOpt设计原理:纯文本阅读理解测试(非GUI执行)。Rubric评估agent对task核心要点的理解,不要求展示所有步骤(token成本过高)。关键概念理解正确即成功。用户倾向用可评分失败样本+held-out验证发现问题,而非直接手改;关注"能否发现并验证"而非只产出更整洁文本。
§
SkillOpt铁律：(1)所有SkillOpt产生的commit必须经用户approve,禁止自动adopt+commit (2)训练不能在正常分支上进行,必须checkout单独测试分支,完成后由用户决定是否merge (3)长任务(30-60min)用subagent执行+主agent监督
§
Git铁律:自动commit须approve;回滚逐笔展示确认;精确回滚不过度(教训:多回滚4笔手写fix)