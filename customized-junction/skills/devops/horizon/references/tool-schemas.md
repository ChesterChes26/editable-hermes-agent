# Horizon MCP Tool Schemas (captured 2026-06-26, server v1.26.0)

All 13 tools with their input/output shapes. Names use `hz_` prefix (not `mcp_horizon_*`).

## hz_validate_config

Validate Horizon config and required environment variables.

**Input:**
```json
{
  "horizon_path": "string|null (default: null)",
  "config_path": "string|null (default: null)",
  "sources": ["string"]|null (default: null),
  "check_env": "boolean (default: true)"
}
```

**Output:** `{ok, data: {horizon_path, config_path, ai: {provider, model, languages, api_key_env}, filtering: {ai_score_threshold, time_window_hours, max_items, category_groups}, enabled_sources, selected_sources, unknown_sources, missing_env, warnings}}`

**Pitfall:** `check_env=true` initializes LLM client and can hang over stdio. Use `check_env=false` for fast config validation.

## hz_fetch_items

Fetch and deduplicate content into the raw stage.

**Input:**
```json
{
  "hours": "integer (default: 24)",
  "run_id": "string|null (default: null)",
  "horizon_path": "string|null (default: null)",
  "config_path": "string|null (default: null)",
  "sources": ["string"]|null (default: null)
}
```

## hz_score_items

Score a stage into the scored stage. Requires `run_id`.

**Input:**
```json
{
  "run_id": "string (required)",
  "source_stage": "string (default: 'raw')",
  "horizon_path": "string|null (default: null)",
  "config_path": "string|null (default: null)"
}
```

## hz_filter_items

Filter scored items into the filtered stage. Requires `run_id`.

**Input:**
```json
{
  "run_id": "string (required)",
  "threshold": "number|null (default: null)",
  "source_stage": "string (default: 'scored')",
  "topic_dedup": "boolean (default: true)",
  "horizon_path": "string|null (default: null)",
  "config_path": "string|null (default: null)"
}
```

## hz_enrich_items

Enrich filtered items into the enriched stage. Requires `run_id`.

**Input:**
```json
{
  "run_id": "string (required)",
  "source_stage": "string (default: 'filtered')",
  "horizon_path": "string|null (default: null)",
  "config_path": "string|null (default: null)"
}
```

## hz_generate_summary

Generate a markdown summary from a stage. Requires `run_id`.

**Input:**
```json
{
  "run_id": "string (required)",
  "language": "string (default: 'zh')",
  "source_stage": "string|null (default: null)",
  "horizon_path": "string|null (default: null)",
  "config_path": "string|null (default: null)",
  "save_to_horizon_data": "boolean (default: false)"
}
```

## hz_run_pipeline

Run fetch → score → filter → enrich → summarize in one call.

**Input:**
```json
{
  "hours": "integer (default: 24)",
  "languages": ["string"]|null (default: null),
  "threshold": "number|null (default: null)",
  "horizon_path": "string|null (default: null)",
  "config_path": "string|null (default: null)",
  "sources": ["string"]|null (default: null),
  "enrich": "boolean (default: true)",
  "topic_dedup": "boolean (default: true)",
  "save_to_horizon_data": "boolean (default: false)"
}
```

## hz_list_runs

List recent runs and stage states.

**Input:**
```json
{
  "limit": "integer (default: 20)"
}
```

## hz_get_run_meta

Read run metadata. Requires `run_id`.

**Input:**
```json
{
  "run_id": "string (required)"
}
```

## hz_get_run_stage

Read items from a run stage. Requires `run_id` + `stage`.

**Input:**
```json
{
  "run_id": "string (required)",
  "stage": "string (required)",
  "max_items": "integer (default: 200)"
}
```

## hz_get_run_summary

Read a generated run summary. Requires `run_id`.

**Input:**
```json
{
  "run_id": "string (required)",
  "language": "string (default: 'zh')"
}
```

## hz_get_metrics

Read in-memory server metrics (uptime, tool call counts, errors).

**Input:** `{}` (no parameters)

**Output:** `{ok, data: {started_at, tool_calls_total, tool_calls_success, tool_calls_failed, tool_calls_by_name, tool_errors_by_code, tool_last_duration_ms, last_error, uptime_seconds}}`

## hz_send_webhook

Send a webhook notification. Template variables `#{date}`, `#{language}`, `#{important_items}`, `#{all_items}`, `#{result}`, `#{timestamp}`, `#{summary}` are replaced in URL and request_body. Requires `date`.

**Input:**
```json
{
  "date": "string (required)",
  "language": "string (default: 'zh')",
  "important_items": "integer (default: 0)",
  "all_items": "integer (default: 0)",
  "result": "string (default: 'success')",
  "summary": "string (default: '')",
  "horizon_path": "string|null (default: null)",
  "config_path": "string|null (default: null)"
}
```

## Pipeline Stages

```
fetch → raw → score → scored → filter → filtered → enrich → enriched → summarize
```

Each stage is idempotent and read-only. Only `hz_send_webhook` has external side effects.
