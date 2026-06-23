# Worker-Bound 诊断实录（2026-06-22）

## 现象

新 Hermes session 中 tools 列表有 memory_search/memory_save/memory_recall，但调用全部返回空/false：

```
memory_search → {"results": []}
memory_save   → {"success": false}
memory_recall → {"results": []}
```

## 诊断过程

### Step 1: Docker 容器确认 running

```bash
$ docker ps --filter name=iii-engine
agentmemory-iii-engine-1  Up 39 minutes  127.0.0.1:3111-3112->3111-3112/tcp
```

容器在跑，端口映射正常。

### Step 2: REST API 端点测试

```bash
$ curl -w "%{http_code}" http://localhost:3111/agentmemory/smart-search -X POST ...
404

$ curl -w "%{http_code}" http://localhost:3111/agentmemory/remember -X POST ...
404
```

全部 404。

### Step 3: Docker 日志分析

```bash
$ docker logs agentmemory-iii-engine-1 2>&1 | grep -E "(register|unregister|worker)" | tail
```

关键时间线（UTC）：
```
05:38:16  Worker registered                    ← 旧 gateway worker 连接
05:39:05  Worker registered                    ← 可能是第二个连接
06:16:36  Unregistering router POST:agentmemory/smart-search
06:16:36  Unregistering router POST:agentmemory/remember
06:16:36  ... (全部路由注销)
06:16:36  Worker unregistered                  ← pid 75356 断开
          worker_id: 97dab266-d39c...
          ip_address: 172.18.0.1              ← Docker host IP
          pid: 75356                           ← 旧 Hermes gateway
06:16:39  New functions detected               ← 无新 worker 注册
```

旧 gateway (pid 75356) 在 06:16:36 断开后，所有 API 路由被 agentmemory 引擎注销。之后没有新 worker 连接。

### Step 4: Gateway 日志查 MCP 连接

```bash
$ grep "MCP.*agentmemory" ~/AppData/Local/hermes/logs/errors.log
```

```
MCP server 'agentmemory' initial connection failed (attempt 1/3)
MCP server 'agentmemory' initial connection failed (attempt 2/3)
MCP server 'agentmemory' initial connection failed (attempt 3/3)
MCP server 'agentmemory' failed initial connection after 3 attempts, giving up:
  1 validation error for StdioServerParameters
    Input should be a valid list [type=list_type, input_value='["-y","@agentmemory/mcp"]', input_type=str]
MCP: registered 0 tool(s) from 0 server(s) (1 failed)
```

### Step 5: config.yaml 确认

```yaml
# 第 674 行 — 问题所在
mcp_servers:
  agentmemory:
    command: npx
    args: '["-y","@agentmemory/mcp"]'    ← JSON 字符串，Pydantic 拒绝
```

## 根因

1. **MCP worker 未启动**：config.yaml 中 `args` 被存为 JSON 字符串而非 YAML 列表，Pydantic `StdioServerParameters` 验证失败，`npx @agentmemory/mcp` 从未执行
2. **无 worker = 无 API**：agentmemory 是 worker-bound 架构，所有 REST 端点由 worker 动态注册；无 worker 时全部返回 404
3. **Memory provider plugin 工具看似正常**：plugin 的 `get_tool_schemas()` 不依赖网络，始终返回 3 个工具；但 `handle_tool_call()` 调 REST API 拿到 404 → 返回空结果

## 修复

cli：
```bash
hermes config set mcp_servers.agentmemory.args -y @agentmemory/mcp
```

或直接编辑 config.yaml：
```yaml
mcp_servers:
  agentmemory:
    command: npx
    args: ["-y", "@agentmemory/mcp"]    ← YAML 列表
```

## 验证 worker 已连接

```bash
# agentmemory 日志应有新的 "Worker registered"
docker logs agentmemory-iii-engine-1 2>&1 | grep "Worker registered"

# 端点应返回 200
curl -w "%{http_code}" http://localhost:3111/agentmemory/smart-search \
  -X POST -H "Content-Type: application/json" -d '{"query":"test"}'
```
