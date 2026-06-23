patches: WeChat ITEM_NOTE (收藏/笔记 type 8) + auto-load obsidian-sync skill as default | weixin.py; qqbot adapter auto-loads obsidian-sync as default | technical(技术)/environment
§
wiki at D:/obsidian/2026/wiki/, follows SCHEMA.md conventions: YAML frontmatter, wikilinks, index.md per category, log.md append-only. Directory: concepts(概念)/, entities(实体)/, comparisons(对比)/, queries(问答)/, raw(源材料)/. Tags taxonomy defined in SCHEMA. New pages must update index and log.
§
vault git: D:/obsidian/2026 → https://github.com/ChesterChes26/obsidian-2026.git (user: ChesterChes26, email: leon88726@hotmail.com). .gitignore excludes .obsidian/ and .trash/. After edits: cd vault && git add -A && git commit -m "..." && git push
§
wiki写作风格: 用户明确要求口语化中文而非学术腔。标题用问句/陈述（"这东西解决什么问题"而非"概述"），用日常比喻（"脑子里记着三件事"），保留全部技术细节但改包装，先讲动机再讲机制，末尾用一句话总结。已嵌入 llm-wiki 技能。
§
identity: I am Hermes-B, a backend worker agent. Hermes-A delegates tasks to me; I execute them and report back. Callback: POST http://127.0.0.1:8642/v1/chat/completions, Header: Authorization: Bearer tnjIud00FcZdT8OktdJUeGbsHLDkAFk8ZyWD9qZ8VRM. curl skeleton: curl -s -X POST http://127.0.0.1:8642/v1/chat/completions -H 'Content-Type: application/json' -H 'Authorization: Bearer tnjIud00FcZdT8OktdJUeGbsHLDkAFk8ZyWD9qZ8VRM' -d 'JSON_PAYLOAD'