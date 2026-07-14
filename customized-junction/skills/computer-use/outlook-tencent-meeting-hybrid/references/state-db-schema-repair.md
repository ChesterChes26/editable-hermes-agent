# state.db Schema 损坏诊断

## 现象

`SELECT ... FROM sessions` 报 `OperationalError: no such table: sessions`，
但 state.db 文件很大（100+ MB），`file` 命令显示为有效 SQLite 3.x。

## 诊断步骤

```bash
# 1. 确认文件类型和大小
ls -la ~/AppData/Local/hermes/state.db*
file ~/AppData/Local/hermes/state.db

# 2. 查 schema_version（0 表示从未建表）
python -c "
import sqlite3
conn = sqlite3.connect('file:$HOME/AppData/Local/hermes/state.db', uri=True)
print('schema_version:', conn.execute('PRAGMA schema_version').fetchone()[0])
print('tables:', conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall())
conn.close()
"

# 3. 排查时间线 — 对比 errors.log 中不同日期的错误类型
#    有表但缺列: "no such column: session_id"（schema 在，缺列）
#    表消失:     "no such table: sessions"（schema 被清空）
grep "no such.*sessions\|no such.*session_id\|no such column" ~/AppData/Local/hermes/logs/errors.log

# 4. WAL checkpoint 后重新检查（排除 WAL 未合并导致的幻读）
python -c "
import sqlite3
conn = sqlite3.connect('file:$HOME/AppData/Local/hermes/state.db', uri=True)
conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
print('After checkpoint:', conn.execute('PRAGMA schema_version').fetchone())
conn.close()
"
```

## 修复

如果确认 schema 被清空（schema_version=0 且无表），直接跑 Hermes 内置 SCHEMA_SQL 重建：

```bash
python -c "
import sqlite3
conn = sqlite3.connect('$HOME/AppData/Local/hermes/state.db')
conn.execute('PRAGMA journal_mode=WAL')
conn.executescript('''
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, source TEXT NOT NULL, user_id TEXT, model TEXT,
    model_config TEXT, system_prompt TEXT, parent_session_id TEXT,
    started_at REAL NOT NULL, ended_at REAL, end_reason TEXT,
    message_count INTEGER DEFAULT 0, tool_call_count INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0, cache_write_tokens INTEGER DEFAULT 0,
    reasoning_tokens INTEGER DEFAULT 0, cwd TEXT,
    billing_provider TEXT, billing_base_url TEXT, billing_mode TEXT,
    estimated_cost_usd REAL, actual_cost_usd REAL, cost_status TEXT,
    cost_source TEXT, pricing_version TEXT, title TEXT,
    api_call_count INTEGER DEFAULT 0, handoff_state TEXT,
    handoff_platform TEXT, handoff_error TEXT,
    rewind_count INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (parent_session_id) REFERENCES sessions(id)
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL, content TEXT, tool_call_id TEXT, tool_calls TEXT,
    tool_name TEXT, timestamp REAL NOT NULL, token_count INTEGER,
    finish_reason TEXT, reasoning TEXT, reasoning_content TEXT,
    reasoning_details TEXT, codex_reasoning_items TEXT,
    codex_message_items TEXT, platform_message_id TEXT,
    observed INTEGER DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
    compacted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS state_meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS compression_locks (session_id TEXT PRIMARY KEY, holder TEXT NOT NULL);
''')
conn.commit()
print('Schema version:', conn.execute('PRAGMA schema_version').fetchone()[0])
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
print('Tables:', [t[0] for t in tables])
conn.close()
"
```

## 注意事项

- 旧 session 数据不可恢复（无备份）
- 修复后需重启 gateway 或 /new 使 SessionDB 重新初始化
- 文件大小不会自动缩减——孤儿数据页占空间但不影响新 session
- 如果数据库曾被 `DELETE FROM sqlite_master`（表消失但页残留），
  `VACUUM` 可回收孤儿页，但非必需
