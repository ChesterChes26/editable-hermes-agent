# WeChat & QQ Bot Migration Checklist

Copy these to another machine to bind the same bot accounts.

## WeChat (weixin)

### Environment Variables (`.env`)

```
WEIXIN_ACCOUNT_ID=72fc9745a445@im.bot
WEIXIN_TOKEN=<full token from .env>
WEIXIN_BASE_URL=https://ilinkai.weixin.qq.com
WEIXIN_CDN_BASE_URL=https://novac2c.cdn.weixin.qq.com/c2c
WEIXIN_DM_POLICY=pairing
WEIXIN_ALLOW_ALL_USERS=false
WEIXIN_ALLOWED_USERS=
WEIXIN_GROUP_POLICY=disabled
WEIXIN_GROUP_ALLOWED_USERS=
WEIXIN_HOME_CHANNEL=<your wechat openid>@im.wechat
```

### Credential Files

Copy the entire directory:
```
~/.hermes/weixin/accounts/
```
Contains:
- `72fc9745a445@im.bot.json` — account token + base_url
- `72fc9745a445@im.bot.sync.json` — polling sync state

## QQ Bot (qqbot)

### Environment Variables (`.env`)

```
QQ_APP_ID=<your QQ bot app ID>
QQ_CLIENT_SECRET=<your QQ bot client secret>
QQ_ALLOW_ALL_USERS=false
QQ_ALLOWED_USERS=<your QQ openid>
QQBOT_HOME_CHANNEL=<your QQ openid>
```

No credential files needed for qqbot — all auth is via env vars (OAuth2
client credentials flow, access token refreshed on gateway startup).

## Verification

After migration, on the new machine:

```bash
hermes gateway status
```

Look for:
```
weixin: connected
qqbot: connected
```

## Important: Don't Run Two Gateways Simultaneously

WeChat and QQ Bot WebSocket connections typically reject duplicate logins.
Stop the old gateway before starting the new one:

```bash
# On old machine:
hermes gateway stop

# On new machine:
hermes gateway start
```

## Reference: Gateway State Inspection

The gateway's live state is at `~/.hermes/gateway_state.json`:

```json
{
  "platforms": {
    "weixin": {"state": "connected", "updated_at": "..."},
    "qqbot": {"state": "connected", "updated_at": "..."}
  }
}
```

Logs for troubleshooting:
```bash
tail -f ~/.hermes/logs/gateway.log | grep -E "weixin|qqbot"
```
