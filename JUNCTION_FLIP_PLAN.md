# Junction Flip Completion Plan

## 背景

runtime 目录结构已从 "repo → runtime" 翻转为 "runtime → repo"。
4/5 个 junction 已建立，但 repo/user-* 目录中缺少被 gitignore 的运行时文件。
scripts 的 junction 尚未完成（被 hermes 进程锁住）。

## 前置条件

- **必须停止 hermes 主进程后执行**（PID 26604 hermes.exe, PID 119480 python.exe）
- 停止命令: `taskkill /F /PID 26604 && taskkill /F /PID 119480`
- 由另一个 AI（非 hermes 实例）执行本 Plan

## 路径定义

```
RUNTIME = C:\Users\chester.chen\AppData\Local\hermes
REPO    = C:\Users\chester.chen\AppData\Local\hermes\hermes-agent
```

## 当前状态

### Runtime (junction 已翻转的 4 个)
| runtime 目录 | 类型 | 指向 |
|---|---|---|
| skills | junction | repo/user-skills |
| plugins | junction | repo/user-plugins |
| hooks | junction | repo/user-config/hooks |
| memories | junction | repo/user-config/memories |
| scripts | 空普通目录 | (被锁，非 junction) |

### Backup 位置 (全量备份，含 ignored 文件)
| backup 目录 | 关键 ignored 文件 |
|---|---|
| skills.bak.20260714_112345/ | .usage.json, .hub/, .curator_state, .curator_backups/, apple/ (仅在backup), social-media/ (仅在backup) |
| plugins.bak.20260714_112345/ | __pycache__/ |
| hooks.bak.20260714_112345/ | __pycache__/ |
| memories.bak.20260714_112345/ | MEMORY.md (3KB, 运行时记忆), *.lock |
| scripts.bak.20260714_112345/ | __pycache__/ |

### Repo 当前内容 (只有 git-tracked 文件)
| repo 目录 | 内容 |
|---|---|
| user-skills/ | 18 个分类目录 (无 .usage.json, .hub/ 等) |
| user-plugins/ | agentmemory/, horizon/ (无 __pycache__) |
| user-config/hooks/ | agentmemory-worker/ (无 __pycache__) |
| user-config/memories/ | USER.md (无 MEMORY.md) |
| user-config/scripts/ | agentmemory-watchdog.py |

## 执行步骤

### Step 0: 确认 backup 完整性
```bash
# 列出所有 backup 目录
ls -la $RUNTIME/*.bak.20260714_112345/

# 对比 backup vs repo，找出 backup 中有但 repo 中没有的文件
for pair in "skills:user-skills" "plugins:user-plugins" "hooks:user-config/hooks" "memories:user-config/memories" "scripts:user-config/scripts"; do
    bak="${pair%%:*}.bak.20260714_112345"
    repo_dir="${pair##*:}"
    echo "=== $bak vs $repo_dir ==="
    diff -rq "$RUNTIME/$bak" "$REPO/$repo_dir" | grep "Only in $bak"
done
```
**汇报给用户确认后再继续。**

### Step 1: 停止 hermes
```bash
taskkill /F /PID 26604
taskkill /F /PID 119480
```
验证: `tasklist | grep -i hermes` 应无输出

### Step 2: 删除 runtime 下需要 link 的目录
```bash
# 删除已有的 4 个 junction
rm -f "$RUNTIME/skills"      # junction, rm 只删链接不删目标
rm -f "$RUNTIME/plugins"     # junction
rm -f "$RUNTIME/hooks"       # junction
rm -f "$RUNTIME/memories"    # junction

# 删除 scripts (现在应该不被锁了)
rmdir "$RUNTIME/scripts"     # 必须是空目录才能 rmdir
```

### Step 3: 清空 repo 下 user-* 目录
```bash
# 清空但保留目录本身
rm -rf "$REPO/user-skills/"*
rm -rf "$REPO/user-plugins/"*
rm -rf "$REPO/user-config/hooks/"*
rm -rf "$REPO/user-config/memories/"*
rm -rf "$REPO/user-config/scripts/"*
```
注意: 用 `rm -rf dir/*` 而非 `rm -rf dir`，保留目录本身避免 git 追踪问题。

### Step 4: 从 backup 恢复全量数据到 repo
```bash
# 从 backup 复制所有文件(含 ignored)到 repo
cp -a "$RUNTIME/skills.bak.20260714_112345/."  "$REPO/user-skills/"
cp -a "$RUNTIME/plugins.bak.20260714_112345/." "$REPO/user-plugins/"
cp -a "$RUNTIME/hooks.bak.20260714_112345/."   "$REPO/user-config/hooks/"
cp -a "$RUNTIME/memories.bak.20260714_112345/." "$REPO/user-config/memories/"
cp -a "$RUNTIME/scripts.bak.20260714_112345/." "$REPO/user-config/scripts/"

# 删除 backup 中的 .lock 文件(运行时锁，无需保留)
find "$REPO/user-skills" "$REPO/user-plugins" "$REPO/user-config" -name "*.lock" -delete
```

### Step 5: 重新建立 junction (runtime → repo)
```bash
cmd.exe /c "mklink /J \"C:\Users\chester.chen\AppData\Local\hermes\skills\" \"C:\Users\chester.chen\AppData\Local\hermes\hermes-agent\user-skills\""
cmd.exe /c "mklink /J \"C:\Users\chester.chen\AppData\Local\hermes\plugins\" \"C:\Users\chester.chen\AppData\Local\hermes\hermes-agent\user-plugins\""
cmd.exe /c "mklink /J \"C:\Users\chester.chen\AppData\Local\hermes\hooks\" \"C:\Users\chester.chen\AppData\Local\hermes\hermes-agent\user-config\hooks\""
cmd.exe /c "mklink /J \"C:\Users\chester.chen\AppData\Local\hermes\memories\" \"C:\Users\chester.chen\AppData\Local\hermes\hermes-agent\user-config\memories\""
cmd.exe /c "mklink /J \"C:\Users\chester.chen\AppData\Local\hermes\scripts\" \"C:\Users\chester.chen\AppData\Local\hermes\hermes-agent\user-config\scripts\""
```

### Step 6: 验证
```bash
# 6a. 验证 junction 指向正确
for d in skills plugins hooks memories scripts; do
    echo "--- $d ---"
    ls -la "$RUNTIME/$d" | head -1
done

# 6b. 验证内容完整: junction 下能看到 backup 中的所有文件
echo "=== skills file count ==="
find "$RUNTIME/skills" -type f | wc -l
echo "=== memories content ==="
ls -la "$RUNTIME/memories/"
echo "=== scripts content ==="
ls -la "$RUNTIME/scripts/"

# 6c. 验证 git status 只显示 tracked 文件(ignored 文件不出现)
cd "$REPO" && git status --short

# 6d. 验证 MEMORY.md 存在且内容完整
wc -c "$RUNTIME/memories/MEMORY.md"
# 应该 ≈ 3045 bytes

# 6e. 验证 hermes 能正常启动
# (可选，如果另一个 AI 能启动 hermes)
```

### Step 7: Git commit and push
```bash
cd "$REPO"
git add -A
git status  # 确认只有 git-tracked 文件被 staged
git commit -m "refactor: complete junction flip - runtime→repo with full content

- All 5 runtime dirs now junction to repo/user-* dirs
- Repo contains full runtime content (gitignore controls tracking)
- Backup preserved at runtime/*.bak.20260714_112345/"
git push
```

## 回滚方案

如果出错，backup 目录完整保留了原始数据:
```bash
# 删除 junction
rm -f "$RUNTIME/skills" "$RUNTIME/plugins" "$RUNTIME/hooks" "$RUNTIME/memories" "$RUNTIME/scripts"

# 从 backup 恢复 runtime 原始结构
mv "$RUNTIME/skills.bak.20260714_112345" "$RUNTIME/skills"
mv "$RUNTIME/plugins.bak.20260714_112345" "$RUNTIME/plugins"
mv "$RUNTIME/hooks.bak.20260714_112345" "$RUNTIME/hooks"
mv "$RUNTIME/memories.bak.20260714_112345" "$RUNTIME/memories"
mv "$RUNTIME/scripts.bak.20260714_112345" "$RUNTIME/scripts"
```

## 给执行 AI 的指令模板

```
[CALLER: hermes-a] USER: weixin:<uid> TASK:
执行 junction flip completion plan。
读取 C:\Users\chester.chen\AppData\Local\hermes\hermes-agent\JUNCTION_FLIP_PLAN.md
按步骤执行，Step 0 完成后汇报结果等待确认，其余步骤连续执行。
每步执行后验证结果再继续下一步。
```
