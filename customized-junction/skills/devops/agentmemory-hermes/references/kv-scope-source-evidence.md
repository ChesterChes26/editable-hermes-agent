# KV Scope 索引行为 — 源码证据

每个 claim 附 dist/index.mjs 行号和代码片段。

## observations → BM25 + Vector ✅

`mem::compress` (line 4959-5060):
```javascript
// line 5029: 存 KV
await kv.set(KV.observations(data.sessionId), data.observationId, compressed);

// line 5031: BM25 索引
getSearchIndex().add(compressed);

// line 5040: Vector 索引
await vectorIndexAddGuarded(compressed.id, compressed.sessionId,
    compressed.title + " " + (compressed.narrative || ""), {
        kind: "compressed",
        logId: compressed.id
    });
```

## memories → BM25 + Vector ✅ (重要纠正)

`mem::remember` (line 6050-6145):
```javascript
// line 6118: 存 KV
await kv.set(KV.memories, memory.id, memory);

// line 6120: BM25 索引 — 通过 memoryToObservation 转伪 observation
getSearchIndex().add(memoryToObservation(memory));

// line 6127: Vector 索引
await vectorIndexAddGuarded(memory.id,
    memory.sessionIds?.[0] ?? "memory",
    memory.title + " " + memory.content, {
        kind: "memory",
        logId: memory.id
    });
```

这导致 smart-search 结果中 memories 显示 `sessionId="memory"`。

`mem::forget` (line 6158-6159) 正确清理了两个索引:
```javascript
getSearchIndex().remove(data.memoryId);
vectorIndexRemove(data.memoryId);
```

## generate-rules → BM25 + Vector ✅

`mem::generate-rules` (line ~5850):
```javascript
getSearchIndex().add(memoryToObservation(memory));
await vectorIndexAddGuarded(memory.id, ...);
```

## summaries → 不进索引 ❌

`mem::summarize` (line 5414-5542):
```javascript
// line 5510: 只存 KV，没有索引调用
await kv.set(KV.summaries, sessionId, summary);
// 没有 getSearchIndex().add()
// 没有 vectorIndexAddGuarded()
```

## semantic → 不进索引 ❌

`consolidate-pipeline` (line 8444-8620):
```javascript
// line 8480/8494: 只存 KV，没有索引
await kv.set(KV.semantic, sem.id, sem);
// 没有索引调用
```

## smart-search 实际搜索的索引

`HybridSearch.tripleStreamSearch` (line 2050-2098):
```javascript
const bm25Results = this.bm25.search(query, limit * 2);      // BM25
vectorResults = this.vector.search(queryEmbedding, limit * 2); // Vector
graphResults = await this.graphRetrieval.searchByEntities(...); // Graph
```

注册位置 (line 22069-22070):
```javascript
const hybridSearch = new HybridSearch(bm25Index, vectorIndex, ...);
registerSmartSearchFunction(sdk, kv, (query, limit) => hybridSearch.search(query, limit));
```

## mem::context (prefetch) 实际读取的 scope

`mem::context` (line 5112-5171):
```javascript
const [pinnedSlots, profile, lessons] = await Promise.all([
    listPinnedSlots(kv),              // KV.slots
    kv.get(KV.profiles, data.project), // KV.profiles
    kv.list(KV.lessons)               // KV.lessons
]);
// ...
const sessions = await kv.list(KV.sessions);
const summariesPerSession = await Promise.all(
    sessions.map(s => kv.get(KV.summaries, s.id))  // KV.summaries
);
// 没有 KV.semantic、KV.memories、KV.observations
```

## 实机验证记录 (2026-06-22)

```python
# 创建记忆
POST /agentmemory/remember {"content":"verify-doublecheck-xxx","type":"fact"}
→ 201 {success:true, memory:{id:"mem_mqoxf8x6_ccb93225177f"}}

# 立刻搜索
POST /agentmemory/smart-search {"query":"verify-doublecheck-xxx"}
→ 200 {results:[{sessionId:"memory", type:"decision", title:"这是验证测试记忆-verify-doublecheck-xxx..."}]}

# 结论: sessionId="memory" 证明来自 memoryToObservation() → 确认入索引
```
