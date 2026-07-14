"""agentmemory-worker hook — auto-start agentmemory worker on gateway startup."""

import asyncio
import os
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError

AGENTMEMORY_URL = os.environ.get("AGENTMEMORY_URL", "http://localhost:3111")
HEALTH_URL = f"{AGENTMEMORY_URL}/agentmemory/smart-search"
STARTUP_TIMEOUT = 30


def _worker_running() -> bool:
    try:
        req = Request(
            HEALTH_URL,
            data=b'{"query":"healthcheck","limit":1}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except (URLError, TimeoutError, OSError):
        return False


async def handle(event_type: str, context: dict) -> None:
    # ALWAYS print on any event to confirm hook fires
    print(f"[agentmemory-worker] EVENT: {event_type}", flush=True, file=sys.stderr)
    print(f"[agentmemory-worker] Worker running: {_worker_running()}", flush=True, file=sys.stderr)

    if event_type != "gateway:startup":
        return

    if _worker_running():
        print("[agentmemory-worker] Worker already connected, skipping.", flush=True, file=sys.stderr)
        return

    print("[agentmemory-worker] Starting agentmemory worker...", flush=True, file=sys.stderr)

    env = os.environ.copy()
    env["AGENTMEMORY_USE_DOCKER"] = "1"

    # Log PATH for debugging
    print(f"[agentmemory-worker] PATH has npx: {'npx' in os.environ.get('PATH', '')}", flush=True, file=sys.stderr)
    try:
        subprocess.Popen(
            ["npx", "@agentmemory/agentmemory"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.path.expanduser("~"),
        )
        print("[agentmemory-worker] Worker spawned.", flush=True, file=sys.stderr)
    except FileNotFoundError:
        print("[agentmemory-worker] ERROR: npx not found.", flush=True, file=sys.stderr)
        return
    except Exception as exc:
        print(f"[agentmemory-worker] ERROR: {exc}", flush=True, file=sys.stderr)
        return

    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        await asyncio.sleep(2)
        if _worker_running():
            print("[agentmemory-worker] Worker online and serving requests.", flush=True, file=sys.stderr)
            return

    print(f"[agentmemory-worker] WARNING: Worker did not come online within {STARTUP_TIMEOUT}s.", flush=True, file=sys.stderr)
