"""agentmemory ingestion 端到端验证脚本

测试全链路：session/start → observe → smart-search。
当 sync_turn 静默失败时，这是唯一的确诊手段。

用法：python verify-ingestion.py [base_url]

返回 0 = 全链路正常（observe 写入后 smart-search 可查到）
返回 1 = 链路中断（打印失败环节）
"""
import json
import os
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError

BASE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
    "AGENTMEMORY_URL", "http://localhost:3111"
)
TIMEOUT = 10
SID = f"verify-{int(time.time())}"
PROJ = os.getcwd()
FAILED = False


def api(path: str, body: dict | None = None, method: str = "POST") -> tuple[int, dict]:
    """Call agentmemory REST API, return (http_status, parsed_json)."""
    url = f"{BASE}/agentmemory/{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    auth = os.environ.get("AGENTMEMORY_SECRET", "")
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, json.loads(resp.read().decode())
    except URLError as e:
        return 0, {"error": str(e)}
    except json.JSONDecodeError:
        return 0, {"error": "invalid JSON response"}


# ---- Step 1: session/start ----
status, body = api("session/start", {
    "sessionId": SID, "project": PROJ, "cwd": PROJ
})
if status != 200:
    print(f"FAIL session/start: HTTP {status} {body}")
    sys.exit(1)
print(f"OK   session/start → {SID} (obs={body.get('session', {}).get('observationCount', '?')})")

# ---- Step 2: observe ----
status, body = api("observe", {
    "hookType": "post_tool_use",
    "sessionId": SID,
    "project": PROJ,
    "cwd": PROJ,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "data": {
        "tool_name": "conversation",
        "tool_input": "hello verify",
        "tool_output": "world verify",
    },
})
if status != 201:
    print(f"FAIL observe: HTTP {status} {body}")
    sys.exit(1)
obs_id = body.get("observationId", "?")
print(f"OK   observe → {obs_id}")

# ---- Step 3: smart-search (retry up to 3 times, BM25 index takes 5-6s) ----
for attempt in range(1, 4):
    time.sleep(2)
    status, body = api("smart-search", {"query": "hello verify", "limit": 5})
    if status != 200:
        print(f"FAIL smart-search: HTTP {status} {body}")
        sys.exit(1)

    results = body.get("results", [])
    found = any("hello verify" in r.get("title", "") for r in results)
    if found:
        print(f"OK   smart-search → found observe in {len(results)} results (attempt {attempt})")
        print("ALL PASS — agentmemory ingestion chain is working.")
        sys.exit(0)
    print(f"     smart-search attempt {attempt}: not found yet, retrying...")

print(f"FAIL smart-search: observe was ingested (201) but not found after 3 attempts")
for r in results:
    print(f"     {r.get('title', '?')} [{r.get('sessionId', '?')}]")
sys.exit(1)
