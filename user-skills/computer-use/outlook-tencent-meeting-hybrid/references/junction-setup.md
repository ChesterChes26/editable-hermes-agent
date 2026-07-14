# Hermes Junction 部署

本 skill 通过 Windows 目录 junction 部署到 Hermes runtime，无需复制文件。

## 当前 Junction

```
Runtime:  C:\Users\chester.chen\AppData\Local\hermes\skills\computer-use\outlook-tencent-meeting-hybrid\
    ↳ →  D:\workspace\outlook-tencent-metting\.hermes\skills\computer-use\outlook-tencent-meeting-hybrid\
```

## 效果

- 项目 `git pull` → Hermes 立即读到最新 skill 文件
- 修改 skill → junction 双向透明（两边是同一份文件）
- Hermes curator 运行时文件（`.usage.json` 等）由项目 `.gitignore` 过滤

## 验证 Junction 是否正常

```bash
# 方法 1：检查 junction 属性
cmd.exe /c "dir /al C:\Users\chester.chen\AppData\Local\hermes\skills\computer-use\"

# 方法 2：确认两边文件一致
diff -rq \
  "C:/Users/chester.chen/AppData/Local/hermes/skills/computer-use/outlook-tencent-meeting-hybrid/" \
  "D:/workspace/outlook-tencent-metting/.hermes/skills/computer-use/outlook-tencent-meeting-hybrid/" \
  --exclude="__pycache__" --exclude="*.pyc"
# 预期：完全一致（无输出）
```

## 重建 Junction（如果丢失）

### 1. 清理可能的孤儿文件

```bash
# 这些是上次 copy 操作的残留，不属于上游 computer-use 技能
rm -rf "C:/Users/chester.chen/AppData/Local/hermes/skills/computer-use/references"
rm -rf "C:/Users/chester.chen/AppData/Local/hermes/skills/computer-use/scripts"
```

### 2. 创建 Junction

```powershell
# PowerShell（推荐 — 编码无问题）
New-Item -ItemType Junction `
  -Path 'C:\Users\chester.chen\AppData\Local\hermes\skills\computer-use\outlook-tencent-meeting-hybrid' `
  -Target 'D:\workspace\outlook-tencent-metting\.hermes\skills\computer-use\outlook-tencent-meeting-hybrid'
```

```cmd
# 或 cmd（需要管理员权限）
mklink /J "C:\Users\chester.chen\AppData\Local\hermes\skills\computer-use\outlook-tencent-meeting-hybrid" ^
          "D:\workspace\outlook-tencent-metting\.hermes\skills\computer-use\outlook-tencent-meeting-hybrid"
```

### 3. 验证

```bash
hermes skills list | grep outlook-tencent
# 预期：outlook-tencent-meeting-hybrid │ computer-use │ local │ enabled
```

## 注意事项

- Junction 需要 Windows 开发者模式 或 管理员权限
- 如果项目路径变更（如 D 盘换盘符），需删除旧 junction 后重建
- Hermes 启动时扫描 `skills/` 目录，新 junction 立即生效（无需重启）
- 不要在 junction 目录内创建大量临时文件——会直接落到项目 git 仓库中
