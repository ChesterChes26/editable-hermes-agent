# DashScope (Alibaba) Provider Configuration

## Provider Block

```yaml
providers:
  dashscope:
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    model: qwen3.6-plus
```

Env var: `DASHSCOPE_API_KEY` in `~/.hermes/.env`

DashScope uses OpenAI-compatible endpoints (not Anthropic format).
The `base_url` above is the `/compatible-mode/v1` path.

## China vs International Endpoints

DashScope has two API endpoints. Your API key is region-specific:

| Endpoint | URL | Region |
|----------|-----|--------|
| China | `https://dashscope.aliyuncs.com/compatible-mode/v1` | China-mainland keys (`sk-...`) |
| International | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | International keys |

**Pitfall:** Hermes's credential pool may auto-create an `alibaba` entry
pointing to the international endpoint, while your key is a China-region
key. Python direct tests pass (using config.yaml's China URL), but Hermes
gets 401 because the credential pool overrides to the international URL.

**Detection:** In the Hermes error, look at the `Endpoint:` line. If it
shows `dashscope-intl.aliyuncs.com` but you need `dashscope.aliyuncs.com`,
the credential pool is wrong. Fix by writing `api_key` directly into the
provider config via Python — see the hermes-provider-setup skill's credential
pool pitfall section.

## Model ID Testing Results (2026-07-09)

Key: `sk-40dbd...` (35 chars, valid)

| Model ID              | HTTP | Notes                         |
|-----------------------|------|-------------------------------|
| `qwen3.6-plus`        | 200  | Works. Returns reasoning_content in response. |
| `qwen-plus-latest`    | 403  | Model.AccessDenied            |
| `qwen-turbo-latest`   | 403  | Model.AccessDenied            |
| `qwen-max-latest`     | 404  | Not found                     |
| `qwen3-235b-a22b`     | 403  | Model.AccessDenied            |

Conclusion: `qwen3.6-plus` is the only confirmed working model ID
on this key. Other models may require different API key scopes or
separate enablement in the Alibaba Cloud console.

## API Response Shape

DashScope responses include a `reasoning_content` field alongside
`content` in the message object — this contains the model's internal
chain-of-thought. The `usage` block includes `completion_tokens_details`
with `reasoning_tokens` and `text_tokens` breakdown.

Example successful response snippet:
```json
{
  "choices": [{
    "message": {
      "content": "Hi",
      "reasoning_content": "Here's a thinking process:\n\n1. **Analyze User Input:**...",
      "role": "assistant"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 422,
    "total_tokens": 437,
    "completion_tokens_details": {
      "reasoning_tokens": 417,
      "text_tokens": 422
    }
  },
  "model": "qwen3.6-plus"
}
```

## Error Responses

401: `{"error": {"message": "You didn't provide an API key...", "type": "invalid_request_error"}}`
403: `{"error": {"message": "Model access denied.", "type": "Model.AccessDenied", "code": "Model.AccessDenied"}}`
