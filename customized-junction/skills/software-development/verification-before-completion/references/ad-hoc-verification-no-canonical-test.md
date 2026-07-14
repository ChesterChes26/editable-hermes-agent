# Ad-hoc verification when no canonical test exists

Use this when the workspace changed but there is no detected project test/lint/build command. This is common for documentation, plans, wiki pages, generated reports, and one-off config snippets.

## Pattern

1. Identify what the change is supposed to guarantee.
2. Create a temporary verifier under the OS temp directory using a `hermes-verify-` filename prefix.
3. Run it against the changed path.
4. Delete the temp script if possible.
5. Report the result as **ad-hoc verification**, not "tests passed" or "suite green".

## Windows-safe Python wrapper

Use Python's tempfile APIs so paths work under Windows/MSYS/Git Bash:

```python
from pathlib import Path
import os, tempfile, subprocess, sys

script = r'''
from pathlib import Path
p = Path(r"D:\\path\\to\\changed.md")
text = p.read_text(encoding="utf-8")
checks = []
checks.append(("file exists", p.exists()))
checks.append(("expected title", text.startswith("# Expected Title")))
checks.append(("required section", "## Required Section" in text))
checks.append(("balanced markdown fences", text.count("```") % 2 == 0))
failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(("PASS" if ok else "FAIL") + " " + name)
raise SystemExit(1 if failed else 0)
'''

tmpdir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp") or tempfile.gettempdir()
fd, path = tempfile.mkstemp(prefix="hermes-verify-", suffix=".py", dir=tmpdir, text=True)
os.close(fd)
Path(path).write_text(script, encoding="utf-8")
try:
    cp = subprocess.run([sys.executable, path], text=True, capture_output=True)
    print(cp.stdout, end="")
    if cp.stderr:
        print("--- stderr ---")
        print(cp.stderr, end="")
finally:
    try:
        os.remove(path)
        print(f"removed_temp={path}")
    except OSError as e:
        print(f"remove_temp_failed={path}: {e}")
raise SystemExit(cp.returncode)
```

## Documentation/plan verifier checklist

For changed Markdown plans or wiki pages, check at least:

- file exists and is non-empty
- expected title exists
- required sections exist
- required constraints/commands are present
- forbidden leakage or forbidden terms are absent
- fenced code blocks are balanced
- absolute paths referenced by the task appear where expected

## Reporting wording

Say:

```text
Ad-hoc verification: temp verifier <path> ran with exit_code=0, then was removed. It checked N content/structure invariants. This is not a project test-suite pass.
```

Do not say:

```text
All tests pass.
Suite green.
Fully verified.
```
