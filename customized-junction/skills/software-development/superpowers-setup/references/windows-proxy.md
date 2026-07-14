# Windows Proxy Configuration

Git operations through proxy `127.0.0.1:7897` (Clash).

## Git Clone with Proxy

```bash
git clone --depth 1 --branch main \
  -c http.proxy=http://127.0.0.1:7897 \
  -c https.proxy=http://127.0.0.1:7897 \
  <repo-url> <target-dir>
```

The `-c` flags apply per-command without modifying global git config.

## Proxy Check

Before cloning, verify proxy is reachable:
```bash
curl -s --proxy http://127.0.0.1:7897 https://github.com -o /dev/null -w "%{http_code}"
```
Expect `200`. If connection refused or timeout, proxy is down.

## Clash Exit Side Effect

When Clash exits, a ProxyServer registry value may persist under `HKCU`, causing WeChat to read it and route through the down proxy → timeout. Delete the stale registry value if this occurs.
