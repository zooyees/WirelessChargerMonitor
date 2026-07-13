import json
import unicodedata
import re
from pathlib import Path

d = json.loads(Path('docs/_mdo_extract/commands_raw.json').read_text(encoding='utf-8'))
names = []
for g in d['groups']:
    n = g['name_en']
    n2 = unicodedata.normalize('NFKC', n).replace('\ufb01', 'fi').replace('\ufb02', 'fl')
    names.append((repr(n), repr(n2), len(g['commands'])))
Path('docs/_mdo_extract/group_names.txt').write_text(
    '\n'.join(f'{a} => {b} ({c})' for a, b, c in names), encoding='utf-8'
)
print('wrote group_names.txt', len(names))
