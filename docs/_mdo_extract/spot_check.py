import json
from pathlib import Path

d = json.load(open('docs/_mdo_extract/commands_raw.json', encoding='utf-8'))
out = []
for g in d['groups']:
    if any(k in g['name_en'] for k in ('Hard', 'File', 'Math', 'Horizontal')):
        out.append(f"=== {g['name_en']!r} {len(g['commands'])}")
        for c in g['commands']:
            out.append(f"  {c['command']!r} :: {c['description_en']!r}")
Path('docs/_mdo_extract/spot.txt').write_text('\n'.join(out), encoding='utf-8')
print('ok', len(out))
