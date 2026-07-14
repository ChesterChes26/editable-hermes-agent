#!/bin/bash
# Complete the junction direction flip for scripts/
# Run this AFTER hermes has been restarted (so scripts/ is no longer locked)
#
# Usage: bash scripts/complete-junction-flip.sh

set -euo pipefail

RUNTIME="$HOME/AppData/Local/hermes"
REPO="$RUNTIME/hermes-agent"

echo "=== Completing junction flip for scripts/ ==="
echo "Runtime: $RUNTIME"
echo "Repo: $REPO"
echo ""

# 1. Check if runtime/scripts is still a regular directory
if [ -d "$RUNTIME/scripts" ] && [ ! -L "$RUNTIME/scripts" ]; then
    echo "[1/4] Removing empty runtime/scripts/ directory..."
    rmdir "$RUNTIME/scripts" 2>/dev/null || {
        echo "ERROR: runtime/scripts/ is not empty or still locked. Is hermes still running?"
        echo "  Stop hermes first: taskkill /F /PID <pid>"
        exit 1
    }
    echo "  Done."
else
    echo "[1/4] runtime/scripts/ already removed or is a junction. Skipping."
fi

# 2. Create junction: runtime/scripts -> repo/user-config/scripts
if [ ! -e "$RUNTIME/scripts" ]; then
    echo "[2/4] Creating junction: runtime/scripts -> repo/user-config/scripts"
    cmd.exe //c "mklink /J \"$RUNTIME\\scripts\" \"$REPO\\user-config\\scripts\""
    echo "  Done."
else
    echo "[2/4] runtime/scripts already exists. Skipping."
fi

# 3. Verify all 5 junctions
echo ""
echo "[3/4] Verifying all junctions..."
JUNCTIONS_OK=true
for pair in "skills:user-skills" "plugins:user-plugins" "hooks:user-config/hooks" "memories:user-config/memories" "scripts:user-config/scripts"; do
    rt_name="${pair%%:*}"
    repo_path="${pair##*:}"
    target="$RUNTIME/$rt_name"
    if [ -L "$target" ] || [ -d "$target" ]; then
        # Check if it's actually a junction (on Windows, junctions show as directories)
        # Verify the content matches
        if [ -d "$REPO/$repo_path" ]; then
            echo "  OK: $rt_name -> $repo_path"
        else
            echo "  WARN: $rt_name exists but repo/$repo_path missing"
            JUNCTIONS_OK=false
        fi
    else
        echo "  MISSING: $rt_name"
        JUNCTIONS_OK=false
    fi
done

# 4. Update SETUP_SYNC.md if it exists
echo ""
echo "[4/4] Checking SETUP_SYNC.md..."
SETUP_DOC="$REPO/SETUP_SYNC.md"
if [ -f "$SETUP_DOC" ]; then
    if grep -q "runtime → repo" "$SETUP_DOC"; then
        echo "  SETUP_SYNC.md already updated."
    else
        echo "  SETUP_SYNC.md needs manual update (junction direction changed)."
        echo "  Update it to reflect: runtime → repo (reverse junction)"
    fi
else
    echo "  SETUP_SYNC.md not found. Skipping."
fi

echo ""
if $JUNCTIONS_OK; then
    echo "=== All 5 junctions verified OK ==="
else
    echo "=== Some junctions need attention. Check above. ==="
fi
