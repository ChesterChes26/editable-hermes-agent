# iii-engine HTTP 层卡死诊断配方

## 症状
- `docker ps` 显示容器 running，端口映射正常
- `curl http://localhost:3111/` 超时（exit code 28 或 curl 返回 `000`）
- TCP 握手成功（`socket.create_connection` 能连上）但 recv 超时
- `docker logs --tail 30` 显示容器内部 trigger loop 仍在跑（"Checking trigger scope" 日志持续输出）
- watchdog cron 每次报 "Worker did not come online within 30s"，`jobs.json` 的 `completed` 计数持续增长

## 快速确诊（不依赖 agentmemory 在线）

```bash
# 1. TCP 层面验证
python -c "
import socket
s = socket.socket(); s.settimeout(3)
try:
    s.connect(('127.0.0.1', 3111))
    print('TCP: CONNECTED (port is listening)')
    s.send(b'GET / HTTP/1.0\r\n\r\n')
    import time; time.sleep(0.3)
    data = s.recv(1024)
    print('HTTP: GOT RESPONSE')
except TimeoutError:
    print('TCP: CONNECTED but HTTP: HUNG (recv timeout)')
except ConnectionRefusedError:
    print('TCP: REFUSED (port not listening)')
"

# 2. 容器日志确认（看是否还在跑内部循环）
docker logs --tail 10 agentmemory-iii-engine-1 2>&1 | tail -3
# 如果输出 "Checking trigger scope" → 内部逻辑活着，HTTP 层单独卡死
```

## 为什么 watchdog 救不了

watchdog 的 `tcp_reachable()`（第 37 行 `socket.create_connection`）只验证 TCP 握手，不验证 HTTP 响应。当 iii-engine 处于此状态时：

1. `tcp_reachable()` → True（TCP 握手成功）
2. `worker_alive()` → False（HTTP 超时）
3. 走到「container OK + TCP OK → spawn worker」分支
4. 新 worker 无法注册路由——iii-engine HTTP 层卡死，不接受路由注册
5. 30 秒后 exit 1，下一分钟重复

## 修复

```bash
docker restart agentmemory-iii-engine-1
# 新进程重新绑定端口，HTTP server 恢复正常
```

## 与「worker 断开」的区别

| | HTTP hung | worker 断开 |
|---|---|---|
| TCP 握手 | ✅ 成功 | ✅ 成功 |
| HTTP 响应 | ❌ 超时（无任何字节） | ✅ 返回 404 |
| 容器日志 | 内部 trigger 在跑 | "Worker registered" 消失 |
| watchdog 能否自愈 | ❌ 必须手动 restart | ✅ spawn npx 即可 |
| 修复 | `docker restart` | `npx @agentmemory/agentmemory` |

## 预防：watchdog HTTP 检查（2026-06-24 已实施）

原 `tcp_reachable()` 只做 TCP 握手（`socket.create_connection`），无法区分「HTTP hung」和「TCP stuck」。已改为 `container_http_healthy()`——GET 容器根路径，任何 2xx/3xx/4xx 都算健康（404 = HTTP 活着只是缺 worker），只有 timeout/connection error 才算不健康。

新增函数 `container_http_healthy()` 位于 watchdog 脚本第 44-59 行。主逻辑改为：
- `container_ok and not http_ok` → `docker restart`（之前是 `not tcp_ok`）
- `container_ok and http_ok` → spawn worker（之前是 `tcp_ok`）
- `restart_container()` 等待用 `container_http_healthy()` 替代 `tcp_reachable()`
- `docker start` 后等待同样改为 HTTP 检查

**效果**：下次 iii-engine HTTP 层再死锁时，watchdog 会直接 `docker restart` 自动救活，不再误判为「只缺 worker」然后每分钟弹窗失败。

## 改完必须验证（不要只读代码）

`container_http_healthy()` 用 `GET /` 检查 HTTP 层。但 iii-engine 根路径返回什么？如果返回 500（`r.status >= 500`），会被误判为不健康 → watchdog 反复 `docker restart`。必须实测：

```bash
# 确认 GET / 实际返回值
curl -s --max-time 3 -w "\nHTTP %{http_code}" http://localhost:3111/
# 预期: 404 → 404 < 500 → 健康 ✓
```

然后逐路径推演（不要脑跑，写出来）：
- Path A: 一切正常 → exit 0
- Path B: worker 死 + GET / 404 → spawn worker
- Path C: GET / timeout → docker restart
- Path D: docker ps 找不到 → docker start

**教训（2026-06-24）：** 改健康检查必须实际 curl 看返回值。404 < 500 算健康这件事不能靠读代码推断——这是 iii-engine 的具体行为，不是通用规则。
