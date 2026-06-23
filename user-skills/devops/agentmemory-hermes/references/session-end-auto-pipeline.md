# session 结束时的自动管道 — 源码证据

## 触发链

1. Hermes 退出 → `on_session_end` in plugin `__init__.py:360-363`:
   ```python
   def on_session_end(self, messages, **kwargs):
       _api(self._base, "session/end", {
           "sessionId": kwargs.get("session_id", self._session_id),
       })
   ```

2. `api::session::end` (index.mjs line 15914-15944):
   ```javascript
   // 标记 completed + endedAt
   await kv.update(KV.sessions, sessionId, [
       {type:"set", path:"endedAt", value: new Date().toISOString()},
       {type:"set", path:"status", value:"completed"}
   ]);
   // 触发 event::session::stopped (fire-and-forget)
   sdk.trigger({
       function_id: "event::session::stopped",
       payload: { sessionId },
       action: TriggerAction.Void()
   });
   ```

3. `event::session::stopped` (index.mjs line 19007-19037) — 自动执行:
   ```javascript
   // ① summarize — AWAITED，不是 fire-and-forget
   const summary = await sdk.trigger({
       function_id: "mem::summarize",
       payload: data
   });

   // ② slot-reflect (如果 enabled)
   if (isReflectEnabled()) sdk.trigger("mem::slot-reflect", ...);

   // ③ graph-extract (如果 enabled，且有 compressed observations)
   if (isGraphExtractionEnabled()) {
       const compressed = (await kv.list(KV.observations(data.sessionId)))
           .filter(o => o.title);
       if (compressed.length > 0) sdk.trigger("mem::graph-extract", ...);
   }
   ```

4. `event::session::ended` (index.mjs line 19044-19055) — 独立的队列 subscriber:
   ```javascript
   // 只做同样的事：标记 completed + endedAt
   await kv.update(KV.sessions, data.sessionId, [
       {type:"set", path:"endedAt", ...},
       {type:"set", path:"status", value:"completed"}
   ]);
   ```

## 不发生的事

- ❌ `session::ended` 不调 summarize
- ❌ `session::stopped` 不调 consolidate-pipeline
- ❌ 没有自动 routine 触发后续管道

## 结论

session 结束时自动执行：summarize + (graph-extract + slot-reflect 如果 enabled)。不自动执行：consolidate-pipeline。
