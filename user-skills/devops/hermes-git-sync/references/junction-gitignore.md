# Junction .gitignore Template (Whitelist Strategy)

Add to `hermes-agent/.gitignore` after setting up reverse junctions.

## Strategy

Default deny all user-* content, then explicitly allow safe file types.
This prevents accidental commit of API keys, tokens, or runtime state.

## Template

```gitignore
# === Default deny all user-* content ===
user-skills/*
user-plugins/*
user-config/hooks/*
user-config/scripts/*
user-config/memories/*

# === Whitelist: safe files to track ===

# Skills
!user-skills/*/SKILL.md
!user-skills/*/DESCRIPTION.md
!user-skills/*/references/
!user-skills/*/references/**
!user-skills/*/templates/
!user-skills/*/templates/**

# Plugins
!user-plugins/*/*.py
!user-plugins/*/plugin.yaml
!user-plugins/*/README.md
!user-plugins/*/requirements.txt

# Hooks
!user-config/hooks/*/*.py
!user-config/hooks/*/HOOK.yaml
!user-config/hooks/*/README.md

# Scripts
!user-config/scripts/*.py
!user-config/scripts/*.sh
!user-config/scripts/README.md

# Memories (only USER.md from default profile)
!user-config/memories/USER.md

# === Explicit deny (defense in depth) ===

# Config with API keys
user-config/config.yaml
user-config/profiles/*/config.yaml
user-config/profiles/*/.env

# Runtime state
*.pyc
__pycache__/
*.lock
.usage.json
.bundled_manifest
.curator_state
.curator_backups/
.hub/

# Worker profile memories (Bearer tokens)
user-config/profiles/*/memories/

# Cron runtime
user-config/cron/output/
user-config/cron/*.lock
```

## Verification

After applying, verify no secrets leak:

```bash
cd ~/.hermes/hermes-agent

# Should return empty
git ls-files | grep -E "(MEMORY\.md|\.lock|config\.yaml|profiles/)"

# Should return empty
git grep -i "api_key\|sk-\|Bearer" -- 'user-*/'
```
