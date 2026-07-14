#!/usr/bin/env python3
"""
Path Migration Script

Reads path-map.yaml and replaces all key->value pairs in tracked files
under customized-junction/.

Usage:
  python migrate-paths.py

Logic:
  - Only process mappings where BOTH key and value are non-empty
  - Skip path-map.yaml itself
  - Skip binary files
  - Report what was changed
"""

import os
import sys
import re
from pathlib import Path

# Files to skip
SKIP_FILES = {
    'path-map.yaml',
    'migrate-paths.py',
    'PATH_MIGRATION.md',
}

# Binary extensions to skip
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.exe', '.dll',
    '.so', '.dylib', '.pyc', '.pyo', '.class', '.jar', '.war',
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z',
    '.db', '.sqlite', '.sqlite3',
}

def is_binary(path: Path) -> bool:
    """Check if file is binary by extension."""
    return path.suffix.lower() in BINARY_EXTENSIONS

def parse_yaml_mappings(map_file: Path) -> list:
    """
    Simple YAML parser for path-map.yaml format.
    Returns list of (key, value) tuples where both are non-empty.
    """
    mappings = []
    
    with open(map_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_key = None
    current_value = None
    
    for line in lines:
        line = line.rstrip()
        
        # Skip comments and empty lines
        if not line or line.strip().startswith('#'):
            continue
        
        # Match "- key: ..." or "key: ..."
        key_match = re.match(r'\s*-?\s*key:\s*(.*)', line)
        if key_match:
            # Save previous mapping if complete
            if current_key and current_value:
                mappings.append((current_key, current_value))
            current_key = None
            current_value = None
            
            value = key_match.group(1).strip()
            # Remove quotes
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            
            if value:  # Non-empty key
                current_key = value
            continue
        
        # Match "value: ..."
        value_match = re.match(r'\s*value:\s*(.*)', line)
        if value_match and current_key:
            value = value_match.group(1).strip()
            # Remove quotes
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            
            if value:  # Non-empty value
                current_value = value
    
    # Don't forget the last mapping
    if current_key and current_value:
        mappings.append((current_key, current_value))
    
    return mappings

def replace_in_file(file_path: Path, mappings: list) -> list:
    """Replace all mappings in a file. Returns list of (key, value, count) tuples."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (UnicodeDecodeError, PermissionError):
        return []
    
    original = content
    changes = []
    
    for key, value in mappings:
        count = content.count(key)
        if count > 0:
            content = content.replace(key, value)
            changes.append((key, value, count))
    
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    return changes

def main():
    # Find the customized-junction directory
    script_dir = Path(__file__).parent
    if script_dir.name != 'customized-junction':
        print("Error: migrate-paths.py must be in customized-junction/")
        sys.exit(1)
    
    map_file = script_dir / 'path-map.yaml'
    if not map_file.exists():
        print("Error: path-map.yaml not found")
        sys.exit(1)
    
    # Load mappings
    mappings = parse_yaml_mappings(map_file)
    if not mappings:
        print("No complete mappings found (all values are empty?)")
        print("Edit path-map.yaml and fill in the 'value' fields for your new machine.")
        sys.exit(0)
    
    print(f"Found {len(mappings)} complete mapping(s):")
    for key, value in mappings:
        print(f"  {key!r} -> {value!r}")
    print()
    
    # Scan files
    total_files = 0
    modified_files = 0
    all_changes = []
    
    for root, dirs, files in os.walk(script_dir):
        # Skip .git
        if '.git' in dirs:
            dirs.remove('.git')
        
        for filename in files:
            if filename in SKIP_FILES:
                continue
            
            file_path = Path(root) / filename
            if is_binary(file_path):
                continue
            
            total_files += 1
            changes = replace_in_file(file_path, mappings)
            
            if changes:
                modified_files += 1
                rel_path = file_path.relative_to(script_dir)
                for key, value, count in changes:
                    all_changes.append((rel_path, key, value, count))
    
    # Report
    print(f"Scanned {total_files} files")
    print(f"Modified {modified_files} files")
    print()
    
    if all_changes:
        print("Changes made:")
        for rel_path, key, value, count in all_changes:
            print(f"  {rel_path}: {count} occurrence(s) of {key!r} -> {value!r}")
    else:
        print("No changes made (no matching patterns found)")
    
    print()
    print("Migration complete.")

if __name__ == '__main__':
    main()
