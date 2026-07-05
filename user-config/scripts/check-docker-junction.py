"""
检查 Docker WSL junction 是否仍然指向 E 盘
如果 C 盘出现真实的 vhdx 文件，说明 junction 被 Docker Desktop 覆盖了
"""
import os
import sys
import subprocess

C_DOCKER_WSL = os.path.join(os.environ["USERPROFILE"], r"AppData\Local\Docker\wsl")
E_TARGET = r"E:\new_workspace\docker-wsl-data"

def is_junction_or_symlink(path):
    """Windows: 检查路径是否是 junction 或 symlink"""
    try:
        os.readlink(path)
        return True
    except OSError:
        return False

def get_junction_target(path):
    """读取 junction 目标"""
    try:
        return os.readlink(path)
    except OSError:
        return None

errors = []

# 1. 检查路径是否存在
if not os.path.exists(C_DOCKER_WSL):
    errors.append(f"Junction 不存在: {C_DOCKER_WSL}")
else:
    # 2. 检查是否是 junction
    is_link = is_junction_or_symlink(C_DOCKER_WSL)
    target = get_junction_target(C_DOCKER_WSL)

    if not is_link:
        # 不是 junction，检查 C 盘是否有 vhdx（说明 Docker 重建了）
        main_vhdx = os.path.join(C_DOCKER_WSL, "main", "ext4.vhdx")
        disk_vhdx = os.path.join(C_DOCKER_WSL, "disk", "docker_data.vhdx")
        for vhdx in [main_vhdx, disk_vhdx]:
            if os.path.exists(vhdx):
                size_mb = os.path.getsize(vhdx) / (1024 * 1024)
                if size_mb > 50:  # >50MB 说明是真实数据，不是残留
                    errors.append(f"C 盘 vhdx 增长中: {vhdx} ({size_mb:.0f}MB)")
        if not errors:
            errors.append(f"{C_DOCKER_WSL} 不是 junction，已被替换为真实目录！")
    else:
        # 是 junction，检查目标
        # os.readlink 在 Windows 上可能返回 \\?\ 前缀，统一去掉
        target_clean = target.replace("\\\\?\\", "").rstrip("\\")
        e_clean = E_TARGET.rstrip("\\")
        if target_clean != e_clean:
            errors.append(f"Junction 指向错误目标: {target} (应为 {E_TARGET})")

if errors:
    print("❌ DOCKER WSL JUNCTION 告警:")
    for e in errors:
        print(f"   {e}")
    print(f"\n   立即修复: E:\\new_workspace\\fix-docker-junction.bat")
    sys.exit(1)
else:
    if is_link:
        print(f"✓ Junction 正常: {C_DOCKER_WSL} → {target}")
    else:
        print(f"✓ 目录正常 (非 junction 模式，但无异常 vhdx)")

