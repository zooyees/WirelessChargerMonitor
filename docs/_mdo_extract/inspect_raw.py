import json
from pathlib import Path

d = json.loads(Path('docs/_mdo_extract/commands_raw.json').read_text(encoding='utf-8'))
print('groups', len(d['groups']))
for g in d['groups']:
    print(f"{g['table']:6} {g['name_en'][:45]:45} {len(g['commands']):4}")
print('--- sample Acquisition ---')
for c in d['groups'][0]['commands'][:8]:
    print(c)
print('--- alpha sample ---')
for c in d['alphabetical'][:10]:
    print(repr(c['title']), '|', c['syntax'][:2], '|', c['description_en'][:70])
good = sum(
    1 for c in d['alphabetical']
    if ':' in c['title'] or c['title'].startswith('*') or c['title'].endswith('?')
)
print('good titles', good, '/', len(d['alphabetical']))
