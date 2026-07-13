"""Extract MDO SCPI commands from programmer-manual text dump."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT = (ROOT / 'docs' / '_mdo_extract' / 'full_text.txt').read_text(encoding='utf-8')
OUT_DIR = ROOT / 'docs' / '_mdo_extract'


def fix_ligatures(s: str) -> str:
    s = unicodedata.normalize('NFKC', s or '')
    s = s.replace('\ufb01', 'fi').replace('\ufb02', 'fl').replace('\ufb00', 'ff')
    s = s.replace('\u00ad', '')
    return s


def preprocess_manual(text: str) -> str:
    """Repair PDF extraction artifacts before parsing."""
    text = fix_ligatures(text)
    # Join SCPI tokens split across lines: FOO:BAR:\nBAZ
    text = re.sub(
        r'([A-Za-z0-9_\]\}]):\s*\n\s*([A-Za-z0-9_\[\<\{])',
        r'\1:\2',
        text,
    )
    # Join wraps where next line continues with ':LEAF...' 
    text = re.sub(
        r'([A-Za-z0-9_\[\]\<\>]+)\s*\n\s*(:[A-Za-z0-9_\[\<\{])',
        r'\1\2',
        text,
    )
    # Join command-only line with following description verb line
    text = re.sub(
        r'([A-Za-z0-9_\[\]\<\>\{\}\|]+\??)\s*\n\s*'
        r'((?:Returns?|Sets?|Set |This |Turns?|Specifies?|Specify |'
        r'Enables?|Disables?|Controls?|Queries?|Clears?|Starts?|Stops?|'
        r'Saves?|Recalls?|Deletes?|Creates?|Copies?|Renames?|Lists?|'
        r'Displays?|Selects?|Adds?|Removes?|Resets?|Sends?|Defines?|'
        r'Performs?|Forces?|Moves?|Changes?|Previews?|Writes?|Reads?|'
        r'Attempts?|Assigns?|Formats?|Move )[^\n]*)',
        r'\1 \2',
        text,
    )
    # Join mid-token wraps like HARDCopy:PRINT er:ADD / MARK:TOT al?
    repairs = [
        (r'HARDCopy:PRINT\s+er:', 'HARDCopy:PRINTer:'),
        (r'MARK:TOT\s+al\?', 'MARK:TOTal?'),
        (r'FILESystem:CO\s+Py', 'FILESystem:COPy'),
        (r'Con\s+figuration', 'Configuration'),
        (r'Cur\s+sor', 'Cursor'),
        (r'Sta\s+tus', 'Status'),
        (r'Vid\s+eo', 'Video'),
        (r'Math Command\s+G\s*roup', 'Math Command Group'),
        (r'Measurement\s+C\s*ommand Group', 'Measurement Command Group'),
        (r'EmailCommands', 'Email Commands'),
        (r'speci\s+fies', 'specifies'),
        (r'Speci\s+fies', 'Specifies'),
        (r'speci\s+fy', 'specify'),
        (r'speci\s+fied', 'specified'),
        (r'de\s+fines', 'defines'),
        (r'De\s+fines', 'Defines'),
        (r'magni\s+fication', 'magnification'),
        (r'de\s+fined', 'defined'),
        (r'De\s+fined', 'Defined'),
        # PDF table misprint: Display backlight vs deskew display — drop bogus row
        (
            r'DISplay:INTENSITy:BACKLight:AUTODim:TIMe\s+'
            r'This command specifies the state of the deskew table display\n?',
            '',
        ),
    ]
    for pat, rep in repairs:
        text = re.sub(pat, rep, text, flags=re.I)
    return text


def clean_body(body: str) -> str:
    body = re.sub(r'\n?\d+-\d+\s+3SeriesMDOOscilloscop[^\n]*\n?', '\n', body)
    body = re.sub(r'\n?3SeriesMDOOscilloscop[^\n]*\n?', '\n', body)
    body = re.sub(r'===== PAGE \d+ =====\n?', '\n', body)
    body = re.sub(r'Command Groups\n?', '\n', body)
    return body


# SCPI token: IEEE *, path with :, optional [n], <x>, {alts}, trailing ?
CMD_TOKEN = re.compile(
    r'^('
    r'\*[A-Za-z][A-Za-z0-9:_\[\]\<\>]*\??'
    r'|[A-Z][A-Za-z0-9_\[\]\<\>]*'
    r'(?:'
    r':[A-Za-z0-9_\[\]\<\>\{\}\|]+'
    r')+\??'
    r'|[A-Z][A-Za-z0-9_\[\]\<\>]+\?'
    r'|[A-Z][A-Za-z0-9_\[\]\<\>]*'
    r'(?:\{:[A-Za-z0-9|_]+\})+'
    r'[A-Za-z0-9:_\[\]\<\>]*\??'
    r'|[A-Z][A-Za-z0-9]{2,}'
    r')\s+(.*)$'
)

DESC_OK = re.compile(
    r'^(Returns?|Sets?|Set |This |Turns?|Specifies?|Specify |Enables?|Disables?|'
    r'Controls?|Queries?|Query |Clears?|Starts?|Stops?|Saves?|Recalls?|'
    r'Deletes?|Creates?|Copies?|Renames?|Lists?|Displays?|Selects?|'
    r'Adds?|Removes?|Resets?|Sends?|Defines?|Performs?|Forces?|'
    r'Moves?|Changes?|Previews?|Writes?|Reads?|Attempts?)',
    re.I,
)

STOP_NARRATIVE = re.compile(
    r'^(Use the|Using the|This manual|Commands in this|NOTE\.|'
    r'.{0,40}Command Group\b|Table\s+2-)',
    re.I,
)


def parse_groups(section: str) -> list[dict]:
    parts = re.split(r'(Table\s+2-\d+:\s*[^\n]+)', section)
    groups: list[dict] = []
    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ''
        m = re.match(r'Table\s+(2-\d+):\s*(.+)', header)
        if not m:
            continue
        tid, tname = m.group(1), fix_ligatures(m.group(2).strip())
        tname = re.sub(r'\s+', ' ', tname)
        body = clean_body(body)
        body = re.sub(r'^Command Description\s*\n', '', body.strip() + '\n', count=1)
        lines = [ln.rstrip() for ln in body.splitlines()]
        cmds: list[dict] = []
        cur_cmd = None
        cur_desc: list[str] = []
        for ln in lines:
            if not ln.strip():
                continue
            if ln.strip() in ('Command Description', 'Command', 'Description'):
                continue
            if STOP_NARRATIVE.match(ln.strip()):
                break
            m2 = CMD_TOKEN.match(ln)
            if m2:
                token, rest = m2.group(1), m2.group(2).strip()
                # Bare roots must have a description that looks like a command summary
                if ':' not in token and not token.startswith('*') and not token.endswith('?'):
                    if not DESC_OK.match(rest):
                        if cur_cmd:
                            cur_desc.append(ln.strip())
                        continue
                if cur_cmd:
                    cmds.append({
                        'command': cur_cmd,
                        'description_en': ' '.join(cur_desc).strip(),
                    })
                cur_cmd = token
                cur_desc = [rest]
                continue
            if cur_cmd:
                if STOP_NARRATIVE.match(ln.strip()):
                    break
                cur_desc.append(ln.strip())
        if cur_cmd:
            cmds.append({
                'command': cur_cmd,
                'description_en': ' '.join(cur_desc).strip(),
            })
        groups.append({'table': tid, 'name_en': tname, 'commands': cmds})
    return groups


def parse_alphabetical(alpha: str) -> list[dict]:
    lines = alpha.splitlines()
    alpha_cmds: list[dict] = []
    i = 0
    title_re = re.compile(r'^(\*?[A-Za-z][A-Za-z0-9:_\[\]\<\>\{\}\|]*)(\s+\([^)]+\))?$')
    while i < len(lines):
        ln = lines[i]
        if not ln.startswith('Group '):
            i += 1
            continue
        group = ln[6:].strip()
        j = i - 1
        title = None
        desc_lines: list[str] = []
        while j >= 0:
            t = lines[j].strip()
            if (
                not t
                or t.startswith('=====')
                or 'ProgrammerManual' in t.replace(' ', '')
                or re.match(r'^2-\d+$', t)
            ):
                j -= 1
                continue
            if t.startswith((
                'Examples ', 'Arguments ', 'Related ', 'Syntax ', 'NOTE', 'Conditions',
            )):
                j -= 1
                continue
            if title_re.match(t) or (':' in t and len(t) < 90 and not t.endswith('.')):
                title = t
                break
            desc_lines.insert(0, t)
            j -= 1
            if len(desc_lines) > 20:
                break

        k = i + 1
        syntax_lines: list[str] = []
        while k < len(lines):
            s = lines[k]
            if s.startswith('Syntax '):
                syntax_lines.append(s[7:].strip())
                k += 1
                while k < len(lines):
                    cont = lines[k].strip()
                    if cont.startswith((
                        'Syntax ', 'Group ', 'Related ', 'Arguments ', 'Examples ',
                        'Conditions ', 'NOTE', '=====',
                    )):
                        break
                    if title_re.match(cont) and syntax_lines:
                        break
                    if cont and (
                        cont.startswith('{')
                        or cont.startswith('<')
                        or '|' in cont
                        or cont.endswith('?')
                        or cont.endswith('}')
                    ):
                        syntax_lines.append(cont)
                        k += 1
                        continue
                    break
                continue
            if s.startswith((
                'Related ', 'Arguments ', 'Examples ', 'Conditions ', 'NOTE', 'Group ', '=====',
            )):
                break
            if title_re.match(s.strip()) and syntax_lines:
                break
            k += 1
            if k > i + 25:
                break
        if title and syntax_lines:
            alpha_cmds.append({
                'title': title,
                'group': group,
                'syntax': syntax_lines,
                'description_en': ' '.join(desc_lines).strip(),
            })
        i = max(k, i + 1)
    return alpha_cmds


def main() -> None:
    text = preprocess_manual(TEXT)
    start = text.find('===== PAGE 33 =====')
    end = text.find('===== PAGE 117 =====')
    groups = parse_groups(text[start:end])
    alpha_cmds = parse_alphabetical(text[end:])
    print('groups', len(groups), 'table cmds', sum(len(g['commands']) for g in groups))
    print('alpha_cmds', len(alpha_cmds))
    # sanity
    for want in ('File System', 'Hard Copy', 'Math'):
        hits = [g for g in groups if want in g['name_en']]
        n = sum(len(g['commands']) for g in hits)
        print(f'  {want}: tables={len(hits)} cmds={n}')
        if hits:
            print('   sample', [c['command'] for c in hits[0]['commands'][:5]])
    out = OUT_DIR / 'commands_raw.json'
    out.write_text(
        json.dumps({'groups': groups, 'alphabetical': alpha_cmds}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print('wrote', out)


if __name__ == '__main__':
    main()
