import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from generate_md import RAW, normalize_text, GROUP_ZH, is_skip_group
import re

cmd_re = re.compile(
    r'^(\*[A-Za-z][A-Za-z0-9:_]*\??'
    r'|[A-Z][A-Za-z0-9]*(?::[A-Za-z0-9_<>\{\}\|]+)+\??'
    r'|[A-Z][A-Za-z0-9_]+\?'
    r'|[A-Z][A-Za-z0-9]*(?:\{:[A-Za-z0-9|_]+\})+[A-Za-z0-9:_]*\??'
    r'|[A-Z][A-Za-z0-9]{2,})$'
)

merged = {}
order = []
log = []
for g in RAW['groups']:
    key = re.sub(r'\s*\(cont\.\)\s*$', '', normalize_text(g['name_en']), flags=re.I).strip()
    focus = 'File' in key or 'Hard' in key
    if is_skip_group(key):
        if focus: log.append(f'skip {key}')
        continue
    if key not in GROUP_ZH and key not in merged:
        if 'Commands' not in key and key not in GROUP_ZH:
            if not key.endswith('Event'):
                if focus: log.append(f'continue-unknown {key}')
                continue
    if key not in merged:
        merged[key] = {'name_en': key, 'commands': [], 'seen': set()}
        order.append(key)
        if focus: log.append(f'CREATE {key} at order idx {len(order)-1}')
    accepted = 0
    for c in g['commands']:
        cmd = normalize_text(c['command'])
        if not cmd_re.match(cmd):
            if focus: log.append(f'  reject-re {cmd!r}')
            continue
        if ':' not in cmd and not cmd.startswith('*') and not cmd.endswith('?'):
            if cmd.upper() in {
                'THE', 'THIS', 'THAT', 'WHEN', 'WITH', 'FROM', 'EACH', 'NOTE',
                'USE', 'USING', 'FOR', 'AND', 'OR', 'SET', 'GET', 'ALL', 'ANY',
                'DATA', 'TIME', 'MODE', 'TYPE', 'ONLY', 'BOTH', 'ALSO', 'THEN',
            }:
                if focus: log.append(f'  reject-word {cmd!r}')
                continue
        if cmd in merged[key]['seen']:
            if focus: log.append(f'  dup {cmd!r}')
            continue
        merged[key]['seen'].add(cmd)
        merged[key]['commands'].append(cmd)
        accepted += 1
    if focus:
        log.append(f'  after table accepted={accepted} total={len(merged[key]["commands"])}')

log.append('ORDER has File? ' + str(any('File' in x for x in order)))
log.append('ORDER has Hard? ' + str(any('Hard' in x for x in order)))
log.append('keys with File/Hard: ' + str([k for k in order if 'File' in k or 'Hard' in k]))
# Check if somehow overwritten
for k in list(merged):
    if 'File' in k or 'Hard' in k:
        log.append(f'merged[{k!r}] n={len(merged[k]["commands"])}')

Path(__file__).with_name('dbg_out2.txt').write_text('\n'.join(log), encoding='utf-8')
print('wrote dbg_out2')
