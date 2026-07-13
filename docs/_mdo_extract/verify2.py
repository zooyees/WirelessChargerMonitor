import json
from pathlib import Path
from collections import Counter

d = json.loads(Path('docs/_mdo_extract/commands_raw.json').read_text(encoding='utf-8'))
lines = []
for name in ('Horizontal', 'Hard Copy', 'Search', 'Power', 'Measurement', 'Vertical'):
    cmds = []
    for g in d['groups']:
        if name in g['name_en']:
            cmds.extend(c['command'] for c in g['commands'])
    lines.append(f'=== {name} ({len(cmds)}) ===')
    for c in cmds:
        lines.append(c)
    # suspicious: too short, spaces, lowercase start mid
    bad = [c for c in cmds if ' ' in c or len(c) < 3 or c[0].islower()]
    if bad:
        lines.append(f'BAD: {bad}')

# duplicates across all
allc = []
for g in d['groups']:
    if 'Commands' in g['name_en'] or g['name_en'].endswith('Event'):
        allc.extend(c['command'] for c in g['commands'])
lines.append(f'total raw table rows {len(allc)} unique {len(set(allc))}')
# commands that look like English words
suspect = [c for c in set(allc) if ':' not in c and not c.startswith('*') and not c.endswith('?') and len(c) < 8]
lines.append('bare short: ' + ', '.join(sorted(suspect)[:40]))

Path('docs/_mdo_extract/verify2.txt').write_text('\n'.join(lines), encoding='utf-8')
print('ok')
