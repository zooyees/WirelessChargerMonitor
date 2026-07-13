import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from generate_md import merge_groups, RAW, normalize_text, GROUP_ZH, is_skip_group
import re

# Focus on File/Hard
for g in RAW['groups']:
    key = re.sub(r'\s*\(cont\.\)\s*$', '', normalize_text(g['name_en']), flags=re.I).strip()
    if 'File' in key or 'Hard' in key or 'Math' in key:
        print('RAW', repr(g['name_en']), '->', repr(key), 'ncmds', len(g['commands']))
        print('  in GROUP_ZH', key in GROUP_ZH)
        print('  skip', is_skip_group(key))
        print('  cmds', [c['command'] for c in g['commands'][:8]])

groups = merge_groups(RAW['groups'])
lines = [f"{g['name_en']}\t{len(g['commands'])}" for g in groups]
Path(__file__).with_name('merged.txt').write_text('\n'.join(lines), encoding='utf-8')
print('MERGED', len(groups), sum(len(g['commands']) for g in groups))
for g in groups:
    if 'File' in g['name_en'] or 'Hard' in g['name_en'] or 'Math' in g['name_en']:
        print('MERGED HIT', g['name_en'], len(g['commands']))
