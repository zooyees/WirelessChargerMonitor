import json
import re
import unicodedata
from pathlib import Path

def normalize_text(s):
    s = unicodedata.normalize('NFKC', s or '')
    s = s.replace('\ufb01', 'fi').replace('\ufb02', 'fl').replace('\ufb00', 'ff')
    s = s.replace('\u00ad', '')
    repairs = [
        (r'Con\s+figuration', 'Configuration'),
        (r'Cur\s+sor', 'Cursor'),
        (r'Sta\s+tus', 'Status'),
        (r'Vid\s+eo', 'Video'),
    ]
    for pat, rep in repairs:
        s = re.sub(pat, rep, s, flags=re.I)
    return re.sub(r'\s+', ' ', s).strip()

cmd_re = re.compile(
    r'^(\*[A-Za-z][A-Za-z0-9:_]*\??'
    r'|[A-Z][A-Za-z0-9]*(?::[A-Za-z0-9_<>\{\}\|]+)+\??'
    r'|[A-Z][A-Za-z0-9_]+\?'
    r'|[A-Z][A-Za-z0-9]*(?:\{:[A-Za-z0-9|_]+\})+[A-Za-z0-9:_]*\??'
    r'|[A-Z][A-Za-z0-9]{2,})$'
)

d = json.load(open('docs/_mdo_extract/commands_raw.json', encoding='utf-8'))
lines = []
for g in d['groups']:
    key = re.sub(r'\s*\(cont\.\)\s*$', '', normalize_text(g['name_en']), flags=re.I).strip()
    if 'File System' in key or 'Hard Copy' in key:
        lines.append(f'GROUP key={key!r}')
        for c in g['commands']:
            cmd = normalize_text(c['command'])
            ok = bool(cmd_re.match(cmd))
            lines.append(f'  ok={ok} cmd={cmd!r}')
Path('docs/_mdo_extract/dbg.txt').write_text('\n'.join(lines), encoding='utf-8')
print('wrote dbg')
