"""agentmemory worker watchdog — auto-restart if dead.

Two-tier health check before any action:
  1. Container: docker ps + HTTP GET -> restart if stuck/dead
  2. Worker:    smart-search endpoint → spawn if missing

Container restart uses docker.exe (native binary, no cmd window).
Worker spawn uses CREATE_NO_WINDOW (suppresses cmd flash on Windows).
"""
import os, subprocess, sys, time

API_URL = os.environ.get("AGENTMEMORY_URL", "http://localhost:3111")
SMART_SEARCH_URL = f"{API_URL}/agentmemory/smart-search"
CONTAINER_NAME = "agentmemory-iii-engine-1"

NPM_PREFIX = os.environ.get("NPM_PREFIX", r"C:\Program Files\nodejs")
NPX = os.path.join(NPM_PREFIX, "npx.cmd" if sys.platform == "win32" else "npx")

# ---- helpers ----

def container_running():
    """True if docker ps shows the container."""
    try:
        r = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}", "--filter", f"name={CONTAINER_NAME}"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return CONTAINER_NAME in r.stdout
    except Exception:
        return False



def container_http_healthy(host="127.0.0.1", port=3111, timeout=5):
    """True if the container responds to an HTTP request.

    Goes beyond a bare TCP handshake — the iii-engine can accept
    connections while its HTTP server is internally deadlocked.
    Only a real HTTP round-trip catches that state.
    """
    from urllib.request import Request, urlopen
    try:
        # Use the root endpoint as a lightweight health check;
        # any 2xx/3xx/4xx response means the HTTP layer is alive.
        req = Request(f"http://{host}:{port}/", method="GET")
        with urlopen(req, timeout=timeout) as r:
            return r.status < 500
    except Exception:
        return False


def worker_alive():
    """True if smart-search endpoint responds 200."""
    from urllib.request import Request, urlopen
    try:
        req = Request(SMART_SEARCH_URL, data=b'{"query":"h","limit":1}',
                      headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def restart_container():
    """Restart the Docker container."""
    subprocess.run(
        ["docker", "restart", CONTAINER_NAME],
        capture_output=True, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    # Give container + worker time to come up
    for _ in range(10):
        time.sleep(2)
        if container_http_healthy():
            time.sleep(2)  # extra grace for HTTP server init
            return True
    return False


def spawn_worker():
    """Start agentmemory worker with no console window."""
    env = os.environ.copy()
    env["AGENTMEMORY_USE_DOCKER"] = "1"
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.Popen(
        [NPX, "@agentmemory/agentmemory"],
        env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


# ---- main ----

if worker_alive():
    sys.exit(0)

# Worker appears dead.  First determine if the container itself is the problem.
container_ok = container_running()
http_ok = container_http_healthy()

if not container_ok:
    print("[watchdog] Container missing — starting...")
    # Container isn't running at all.  Try docker start, then spawn worker.
    subprocess.run(
        ["docker", "start", CONTAINER_NAME],
        capture_output=True, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    for _ in range(10):
        time.sleep(2)
        if container_http_healthy():
            time.sleep(2)
            spawn_worker()
            break
    else:
        print("[watchdog] Container did not start within 20s.")
    sys.exit(0)

if container_ok and not http_ok:
    print("[watchdog] Container HTTP-stuck — restarting...")
    if restart_container():
        print("[watchdog] Container restarted, checking worker...")
        # Worker should auto-reconnect after container restart.
        # If not, spawn.
        time.sleep(3)
        if not worker_alive():
            spawn_worker()
            for _ in range(10):
                time.sleep(3)
                if worker_alive():
                    print("[watchdog] Worker online.")
                    sys.exit(0)
            print("[watchdog] Worker did not come online within 30s.")
            sys.exit(1)
    else:
        print("[watchdog] Container restart failed.")
        sys.exit(1)
    sys.exit(0)

# Container + HTTP both OK, but worker not responding.  Worker-only restart.
if container_ok and http_ok:
    print("[watchdog] Worker down, starting...")
    spawn_worker()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        time.sleep(3)
        if worker_alive():
            print("[watchdog] Worker online.")
            sys.exit(0)
    print("[watchdog] Worker did not come online within 30s.")
    sys.exit(1)
