# YouTube Transcript Fallback: yt-dlp

When `fetch_transcript.py` (youtube-transcript-api) fails (exit code 49, empty output, or timeout), fall back to yt-dlp:

```bash
# Install if missing
uv pip install yt-dlp

# Fetch auto-generated English captions, skip video download
yt-dlp --write-auto-subs --sub-lang en --skip-download -o "/tmp/vttest" "https://www.youtube.com/watch?v=VIDEO_ID"

# Output is at /tmp/vttest.en.vtt
```

**Proxy note**: On environments where HTTP_PROXY is set globally, yt-dlp may fail silently with `--proxy`. Try without `--proxy` first. If that also fails, try with explicit proxy.

## VTT Parsing

YouTube auto-captions in VTT format have three layers of near-duplicate cue blocks per timestamp. A robust parsing approach:

```python
import re
from collections import defaultdict

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Split into cue blocks
blocks = re.split(r'\n\n+', content.strip())
timestamps = []

for block in blocks:
    lines = block.strip().split('\n')
    if not lines or '-->' not in lines[0]:
        continue
    ts = lines[0].strip()
    text_parts = []
    for line in lines[1:]:
        line = line.strip()
        if line.startswith('align:') or line.startswith('position:'):
            continue
        text = re.sub(r'<[^>]+>', '', line).strip()
        if text:
            text_parts.append(text)
    if text_parts:
        timestamps.append((ts, ' '.join(text_parts)))

# Group by timestamp second, take longest variant
grouped = defaultdict(list)
for ts, text in timestamps:
    m = re.match(r'(\d+):(\d+):(\d+)\.(\d+)', ts)
    if m:
        secs = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3))
        grouped[secs].append(text)

# Take longest for each second
final = []
for secs in sorted(grouped.keys()):
    best = max(grouped[secs], key=len)
    m, s = secs // 60, secs % 60
    final.append(f"[{m:02d}:{s:02d}] {best}")

full_text = '\n'.join(final)
```

This produces clean, deduplicated, timestamped text from any YouTube VTT file.
