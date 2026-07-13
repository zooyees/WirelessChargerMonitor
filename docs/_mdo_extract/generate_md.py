"""Generate Chinese Markdown catalog of MDO SCPI commands."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = json.loads((ROOT / 'docs' / '_mdo_extract' / 'commands_raw.json').read_text(encoding='utf-8'))
OUT = ROOT / 'docs' / 'MDO3014_SCPI命令手册.md'


def fix_ligatures(s: str) -> str:
    s = unicodedata.normalize('NFKC', s or '')
    s = s.replace('\ufb01', 'fi').replace('\ufb02', 'fl').replace('\ufb00', 'ff')
    s = s.replace('\u00ad', '')
    return s


def normalize_group_name(s: str) -> str:
    """Normalize Command Group table titles only (never SCPI mnemonics)."""
    s = fix_ligatures(s)
    repairs = [
        (r'Con\s+figuration', 'Configuration'),
        (r'Cur\s+sor', 'Cursor'),
        (r'Sta\s+tus', 'Status'),
        (r'Vid\s+eo', 'Video'),
        (r'EmailCommands', 'Email Commands'),
        (r'FileSystem\s+Commands', 'File System Commands'),
        (r'HardCopy\s+Commands', 'Hard Copy Commands'),
        (r'W\s+aveform', 'Waveform'),
        (r'Transfer\s+ring', 'Transferring'),
        (r'Transferri\s+ng', 'Transferring'),
        (r'Exa\s+mple', 'Example'),
    ]
    for pat, rep in repairs:
        s = re.sub(pat, rep, s, flags=re.I)
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'\s*\(cont\.\)\s*$', '', s, flags=re.I).strip()
    return s


def normalize_desc(s: str) -> str:
    s = fix_ligatures(s)
    repairs = [
        (r'speci\s+fies', 'specifies'),
        (r'Speci\s+fies', 'Specifies'),
        (r'speci\s+fy', 'specify'),
        (r'speci\s+fied', 'specified'),
        (r'de\s+fines', 'defines'),
        (r'de\s+fined', 'defined'),
        (r'magni\s+fication', 'magnification'),
        (r'wavef\s+orm', 'waveform'),
        (r'W\s+aveform', 'Waveform'),
    ]
    for pat, rep in repairs:
        s = re.sub(pat, rep, s, flags=re.I)
    return re.sub(r'\s+', ' ', s).strip()


# Complete Chinese for high-priority / frequently mangled rows
CMD_ZH: dict[str, str] = {
    'FILESystem?': '返回文件系统相关设置。',
    'FILESystem:COPy': '将指定文件复制为新文件。',
    'FILESystem:CWD': '设置或查询文件系统当前工作目录。',
    'FILESystem:DELEte': '删除指定文件或目录。',
    'FILESystem:DIR?': '返回当前目录内容列表。',
    'FILESystem:FORMat': '格式化指定驱动器。',
    'FILESystem:FREESpace?': '返回当前驱动器剩余空间（字节）。',
    'FILESystem:LDIR?': '返回文件夹内所有文件与目录的分号分隔列表。',
    'FILESystem:MKDir': '创建新目录。',
    'FILESystem:MOUNT:AVAILable?': '返回可用于挂载网络驱动器的盘符列表（逗号分隔）。',
    'FILESystem:MOUNT:DRIve': '挂载由引号字符串指定的网络驱动器。',
    'FILESystem:MOUNT:LIST?': '返回已挂载网络驱动器列表（盘符、服务器、路径、类型）；无挂载时返回空字符串。',
    'FILESystem:READFile': '读取指定文件内容并通过当前接口返回。',
    'FILESystem:REName': '将已有文件重命名为新名称。',
    'FILESystem:RMDir': '删除指定目录。',
    'FILESystem:UNMOUNT:DRIve': '卸载由引号字符串指定的网络驱动器。',
    'FILESystem:WRITEFile': '将指定块数据写入示波器当前工作目录中的文件。',
    'HARDCopy': '将屏幕显示内容发送到所选打印机。',
    'HARDCopy:ACTIVeprinter': '设置或查询当前活动打印机。',
    'HARDCopy:INKSaver': '切换 InkSaver：在白底上打印彩色波形与格线。',
    'HARDCopy:LAYout': '设置或查询硬拷贝页面方向。',
    'HARDCopy:PREVIEW': '预览应用 InkSaver 调色板后的当前屏幕内容。',
    'HARDCopy:PRINTer:ADD': '向可用打印机列表添加网络或电子邮件打印机。',
    'HARDCopy:PRINTer:DELete': '从可用打印机列表移除网络打印机。',
    'HARDCopy:PRINTer:LIST?': '显示当前已定义的打印机列表。',
    'HARDCopy:PRINTer:REName': '重命名可用打印机列表中的网络或电子邮件打印机。',
    'MATH[1]?': '返回数学波形的定义与相关设置。',
    'MATH[1]:AUTOSCale': '设置或查询数学波形自动垂直缩放状态。',
    'MATH[1]:DEFine': '以文本字符串设置当前数学函数表达式。',
    'MATH[1]:HORizontal:POSition': '设置 FFT 或（非实时）数学参考波形的水平显示位置。',
    'MATH[1]:HORizontal:SCAle': '设置 FFT 或双波形数学的水平显示时基。',
    'MATH[1]:HORizontal:UNIts': '返回数学波形水平单位。',
    'MATH[1]:LABel': '设置或查询数学波形标签。',
    'MATH[1]:SPECTral:MAG': '设置数学字符串中频谱幅度的单位。',
    'MATH[1]:SPECTral:WINdow': '设置数学波形频谱输入数据的窗函数。',
    'MATH[1]:TYPe': '设置数学波形类型（DUAL / FFT / ADVanced / SPECTRUM），需配合 MATH:DEFine。',
    'MATH[1]:VERTical:POSition': '设置当前数学类型的垂直位置。',
    'MATH[1]:VERTical:SCAle': '设置当前数学类型的垂直标度。',
    'MATH[1]:VERTical:UNIts': '返回数学波形垂直单位。',
    'MATHVAR?': '返回数学表达式中使用的全部数值变量。',
    'MATHVAR:VAR<x>': '设置可在数学表达式中使用的数值变量 VAR<x>。',
    'DESkew:DISplay': '设置或查询 deskew 表显示状态。',
    'HORizontal?': '返回水平系统相关设置。',
    'HORizontal:DELay:MODe': '设置或查询水平延迟模式。',
    'HORizontal:DELay:TIMe': '设置或查询水平延迟时间。',
    'HORizontal:DIGital:RECOrdlength:MAGnivu?': '返回 MagniVu 数字采集的记录长度。',
    'HORizontal:DIGital:RECOrdlength:MAIn?': '返回主数字采集的记录长度。',
    'HORizontal:DIGital:SAMPLERate:MAGnivu?': '返回 MagniVu 数字采集的采样率。',
    'HORizontal:DIGital:SAMPLERate:MAIn?': '返回主数字采集的采样率。',
    'HORizontal:POSition': '设置水平位置（百分比；延迟关闭时使用）。',
    'HORizontal:PREViewstate?': '返回显示系统预览状态。',
    'HORizontal:RECOrdlength': '设置或查询记录长度。',
    'HORizontal:SAMPLERate?': '查询采样率（秒）。',
    'HORizontal:SCAle': '设置或查询水平时基（秒/格）。',
    'ETHERnet:SUBNETMask': '设置或查询远程接口子网掩码。',
}


def normalize_cmd(s: str) -> str:
    """Normalize SCPI mnemonic — must NOT insert spaces into tokens."""
    s = fix_ligatures(s)
    s = re.sub(r'HARDCopy:PRINT\s+er:', 'HARDCopy:PRINTer:', s)
    s = re.sub(r'MARK:TOT\s+al\?', 'MARK:TOTal?', s)
    return re.sub(r'\s+', '', s).strip()  # SCPI names have no spaces


GROUP_ZH = {
    'Acquisition Commands': '采集 (Acquisition)',
    'Act on Event': '事件动作 (Act on Event)',
    'AFG Commands': '任意函数发生器 (AFG)',
    'Alias Commands': '别名 (Alias)',
    'ARB Commands': '任意波形 (ARB)',
    'Bus Commands': '总线解码 (Bus)',
    'Calibration and Diagnostic Commands': '校准与诊断 (Calibration/Diagnostic)',
    'Configuration Commands': '配置 (Configuration)',
    'Cursor Commands': '光标 (Cursor)',
    'Display Commands': '显示 (Display)',
    'DVM Commands': '数字万用表 (DVM)',
    'Email Commands': '邮件 (Email)',
    'Ethernet Commands': '以太网 (Ethernet)',
    'File System Commands': '文件系统 (File System)',
    'Hard Copy Commands': '硬拷贝/截屏 (Hard Copy)',
    'Horizontal Commands': '水平时基 (Horizontal)',
    'Mark Commands': '标记 (Mark)',
    'Math Commands': '数学运算 (Math)',
    'Measurement Commands': '自动测量 (Measurement)',
    'Miscellaneous Commands': '杂项与 IEEE488.2 (Miscellaneous)',
    'Power Commands': '电源分析 (Power)',
    'RF Commands': '射频分析 (RF)',
    'Save and Recall Commands': '保存与调用 (Save/Recall)',
    'Search Commands': '搜索 (Search)',
    'Status and Error Commands': '状态与错误 (Status/Error)',
    'Trigger Commands': '触发 (Trigger)',
    'Vertical Commands': '垂直通道 (Vertical)',
    'Video Picture Commands': '视频画面 (Video Picture)',
    'Waveform Transfer Commands': '波形传输 (Waveform Transfer)',
    'Zoom Commands': '缩放 (Zoom)',
}

SKIP_GROUP_PREFIXES = (
    'Example Command Sequence',
    'Digital Collection',
    'Further Explanation',
    'Scaling Waveform',
    'Transferring a Waveform',
)


def group_zh(name_en: str) -> str:
    return GROUP_ZH.get(name_en, name_en)


# Longer / more specific phrases first (sorted by length in translate)
PHRASES: list[tuple[str, str]] = [
    ('Sets or queries the', '设置或查询'),
    ('sets or queries the', '设置或查询'),
    ('Sets or queries', '设置或查询'),
    ('sets or queries', '设置或查询'),
    ('Sets (or queries) which', '设置（或查询）哪个'),
    ('Sets (or queries) the', '设置（或查询）'),
    ('Sets (or queries)', '设置（或查询）'),
    ('sets (or queries)', '设置（或查询）'),
    ('This command specifies or returns', '本指令设置或返回'),
    ('This command specifies the', '本指令设置'),
    ('This command specifies', '本指令设置'),
    ('This command is used to add', '本指令用于添加'),
    ('This command is used along with', '本指令需配合'),
    ('This command is used', '本指令用于'),
    ('This command attempts to', '本指令尝试'),
    ('This command returns the', '本指令返回'),
    ('This command returns', '本指令返回'),
    ('This command controls the', '本指令控制'),
    ('This command controls', '本指令控制'),
    ('This command saves', '本指令保存'),
    ('This query returns the', '本查询返回'),
    ('This query returns', '本查询返回'),
    ('Returns the current', '返回当前'),
    ('Returns the number of', '返回数量：'),
    ('Returns the maximum', '返回最大'),
    ('Returns the definition of', '返回…的定义：'),
    ('Returns the', '返回'),
    ('Returns all', '返回全部'),
    ('Returns ', '返回'),
    ('Return the', '返回'),
    ('Turns fast acquisition mode on or off, or queries the state of the mode.',
     '打开或关闭快速采集模式，或查询该模式状态。'),
    ('Turns ', '切换'),
    ('on or off, or queries the state of the mode', '开/关，或查询该模式状态'),
    ('on or off', '开或关'),
    ('or queries the state of the mode', '或查询该模式状态'),
    ('or queries', '或查询'),
    ('Starts or stops the acquisition system', '启动或停止采集系统'),
    ('Starts or stops', '启动或停止'),
    ('Sends a copy of the screen display to the selected printer',
     '将屏幕显示内容发送到所选打印机'),
    ('Changes hard copy output to print color traces and graticule on a white background',
     '将硬拷贝输出改为在白底上打印彩色波形与格线（InkSaver）'),
    ('Previews the current screen contents with the InkSaver palette applied',
     '预览应用 InkSaver 调色板后的当前屏幕内容'),
    ('Removes a network printer from the list of available printers',
     '从可用打印机列表中移除网络打印机'),
    ('Displays the list of currently defined printers.',
     '显示当前已定义的打印机列表。'),
    ('Renames a network or email printer on the list of available printers',
     '重命名可用打印机列表中的网络或电子邮件打印机'),
    ('Writes the specified block data to the oscilloscope current working directory',
     '将指定块数据写入示波器当前工作目录'),
    ('Deletes a named directory', '删除指定目录'),
    ('whether the acquisition is continuous or single sequence',
     '采集为连续还是单次序列'),
    ('acquisition mode of the oscilloscope for all analog channel waveforms',
     '示波器全部模拟通道波形的采集模式'),
    ('acquisition parameters', '采集参数'),
    ('fast acquisition feature', '快速采集功能'),
    ('fast acquisition mode', '快速采集模式'),
    ('MagniVu feature', 'MagniVu 功能'),
    ('maximum real-time sample rate', '最大实时采样率'),
    ('number of acquisitions that have occurred', '已发生的采集次数'),
    ('number of acquisitions for an averaged waveform', '平均波形所用的采集次数'),
    ('number of envelopes', '包络次数'),
    ('number of acquisitions in the sequence completed so far', '序列中目前已完成的采集次数'),
    ('number of acquisitions used in the sequence', '序列使用的采集次数'),
    ('which palette to use for fast acquisition mode', '快速采集模式使用的调色板'),
    ('the acquisition system', '采集系统'),
    ('page orientation for hard copy', '硬拷贝页面方向'),
    ('currently active printer', '当前活动打印机'),
    ('math waveform type', '数学波形类型'),
    ('math waveform', '数学波形'),
    ('math expression', '数学表达式'),
    ('numerical values used within math expressions', '数学表达式中使用的数值'),
    ('numerical values you can use within math expressions', '可在数学表达式中使用的数值'),
    ('automatic vertical scaling of the math waveform', '数学波形自动垂直缩放'),
    ('current math function as a text string', '当前数学函数（文本字符串）'),
    ('Query Only', '仅查询'),
    ('No Query', '无查询形式'),
    ('Specifies the', '设置'),
    ('Specify the', '设置'),
    ('Specifies ', '设置'),
    ('Enables ', '使能'),
    ('Disables ', '禁用'),
    ('Enable ', '使能'),
    ('Disable ', '禁用'),
    ('Creates a', '创建'),
    ('Deletes a', '删除'),
    ('Copies ', '复制'),
    ('Renames ', '重命名'),
    ('oscilloscope', '示波器'),
    ('waveforms', '波形'),
    ('waveform', '波形'),
    ('acquisition', '采集'),
    ('sample rate', '采样率'),
    ('record length', '记录长度'),
    ('channel', '通道'),
    ('trigger', '触发'),
    ('horizontal', '水平'),
    ('vertical', '垂直'),
    ('measurement', '测量'),
    ('cursor', '光标'),
    ('display', '显示'),
    ('hard copy', '硬拷贝'),
    ('file format', '文件格式'),
    ('reference', '参考'),
    ('search', '搜索'),
    ('zoom', '缩放'),
    ('calibration', '校准'),
    ('diagnostic', '诊断'),
    ('factory', '出厂'),
    ('default setup', '默认设置'),
    ('current working directory', '当前工作目录'),
    ('network drive', '网络驱动器'),
    ('printer', '打印机'),
    ('directory', '目录'),
    ('save', '保存'),
    ('recall', '调用'),
]


def translate_desc(en: str, cmd: str = '') -> str:
    if cmd and cmd in CMD_ZH:
        return CMD_ZH[cmd]
    # Also try without [1]
    if cmd:
        alt = re.sub(r'\[1\]', '', cmd)
        if alt in CMD_ZH:
            return CMD_ZH[alt]
    s = normalize_desc(en)
    if not s:
        return '（手册分组表未给出摘要，请结合 Syntax 与正文。）'
    out = s
    for eng, zh in sorted(PHRASES, key=lambda x: -len(x[0])):
        out = out.replace(eng, zh)
    out = re.sub(r'\s+', ' ', out).strip()
    non_ascii = sum(1 for ch in out if ord(ch) > 127)
    if non_ascii < max(3, len(out) // 8):
        low = s.lower()
        if low.startswith('returns') or 'query only' in low:
            tag = '【返回/查询】'
        elif 'sets or queries' in low or 'set or query' in low or 'sets (or queries)' in low:
            tag = '【设置或查询】'
        elif low.startswith(('sets', 'specifies', 'specify', 'this command specifies')):
            tag = '【设置】'
        elif 'on or off' in low or low.startswith('turns'):
            tag = '【开关】'
        elif low.startswith('starts'):
            tag = '【启停】'
        elif low.startswith('enables') or low.startswith('enable'):
            tag = '【使能】'
        elif low.startswith('disables') or low.startswith('disable'):
            tag = '【禁用】'
        elif low.startswith('sends'):
            tag = '【发送】'
        elif low.startswith(('creates', 'deletes', 'copies', 'renames', 'writes', 'reads', 'assigns', 'formats')):
            tag = '【操作】'
        else:
            tag = '【控制】'
        out = f'{tag}{s}'
    if not out.endswith(('。', '.', '！', '？', '!', '?')):
        out += '。'
    return out


def is_skip_group(name: str) -> bool:
    return any(name.startswith(p) for p in SKIP_GROUP_PREFIXES)


CMD_OK = re.compile(
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
    r')$'
)

BARE_REJECT = {
    'THE', 'THIS', 'THAT', 'WHEN', 'WITH', 'FROM', 'EACH', 'NOTE',
    'USE', 'USING', 'FOR', 'AND', 'OR', 'SET', 'GET', 'ALL', 'ANY',
    'DATA', 'TIME', 'MODE', 'TYPE', 'ONLY', 'BOTH', 'ALSO', 'THEN',
}


def merge_groups(groups: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for g in groups:
        key = normalize_group_name(g['name_en'])
        if is_skip_group(key):
            continue
        if key not in GROUP_ZH and key not in merged:
            if 'Commands' not in key and not key.endswith('Event'):
                continue
        if key not in merged:
            merged[key] = {'name_en': key, 'commands': [], 'seen': set()}
            order.append(key)
        for c in g['commands']:
            cmd = normalize_cmd(c['command'])
            if not CMD_OK.match(cmd):
                continue
            if ':' not in cmd and not cmd.startswith('*') and not cmd.endswith('?'):
                if cmd.upper() in BARE_REJECT:
                    continue
            if cmd in merged[key]['seen']:
                continue
            merged[key]['seen'].add(cmd)
            desc = normalize_desc(c['description_en'])
            # Drop bleed from next Command Group title into last row description
            desc = re.split(
                r'\s+(?:File\s+System|Hard\s+Copy|Horizontal|Mark|Math|'
                r'Measurement|Miscellaneous|Power|RF|Save\s+and\s+Recall|'
                r'Search|Status|Trigger|Vertical|Video|Waveform|Zoom|'
                r'Acquisition|Alias|Bus|Calibration|Configuration|Cursor|'
                r'Display|DVM|Email|Ethernet|AFG|ARB)'
                r'\s+Co\s*mmand\s+Group\b.*$',
                desc,
                flags=re.I,
            )[0].strip()
            desc = re.split(r'\s+Use\s+the\s+commands\s+in\s+the\b.*$', desc, flags=re.I)[0].strip()
            merged[key]['commands'].append({
                'command': cmd,
                'description_en': desc,
            })
    return [
        {
            'name_en': merged[k]['name_en'],
            'name_zh': group_zh(merged[k]['name_en']),
            'commands': merged[k]['commands'],
        }
        for k in order
        if merged[k]['commands']
    ]


def build_syntax_index(alpha: list[dict]) -> dict[str, list[str]]:
    idx: dict[str, list[str]] = {}
    for e in alpha:
        for syn in e.get('syntax') or []:
            syn = normalize_desc(syn)
            base = syn.split('{')[0].split('<')[0].strip().rstrip('?')
            if not base or ' ' in base[:3]:
                continue
            key = base.upper().replace('[1]', '').replace('[X]', '<X>')
            idx.setdefault(key, [])
            if syn not in idx[key]:
                idx[key].append(syn)
        title = normalize_desc(e.get('title') or '')
        title_base = title.split('(')[0].strip().rstrip('?')
        if title_base and (':' in title_base or title_base.startswith('*')) and e.get('syntax'):
            key = title_base.upper().replace('[1]', '').replace('[X]', '<X>')
            for syn in e['syntax']:
                syn = normalize_desc(syn)
                idx.setdefault(key, [])
                if syn not in idx[key]:
                    idx[key].append(syn)
    return idx


def find_syntax(cmd: str, idx: dict[str, list[str]]) -> list[str]:
    # Manual corrections where alphabetical parse attached wrong Syntax block
    overrides = {
        'HARDCopy:PRINTer:LIST?': ['HARDCopy:PRINTer:LIST?'],
        'HARDCopy:INKSaver': ['HARDCopy:INKSaver {ON|OFF|<NR1>}', 'HARDCopy:INKSaver?'],
    }
    if cmd in overrides:
        return overrides[cmd]
    base = cmd.split('{')[0].split('<')[0].strip().rstrip('?')
    base2 = re.sub(r'\{[^}]*\}', '', base)
    variants = [
        base,
        base2,
        re.sub(r'\[\d+\]', '', base),
        re.sub(r'\[\d+\]', '', base2),
        re.sub(r'\[1\]', '', base),
        cmd.rstrip('?'),
    ]
    for candidate in variants:
        key = candidate.upper()
        hit = idx.get(key)
        if hit:
            leaf = candidate.split(':')[-1].upper()
            preferred = [s for s in hit if leaf and leaf in s.upper().replace('?', '')]
            return preferred[:3] or hit[:3]
        hit = idx.get(key.replace('<X>', '<x>'))
        if hit:
            return hit[:3]
    return []


def main() -> None:
    groups = merge_groups(RAW['groups'])
    syntax_idx = build_syntax_index(RAW['alphabetical'])
    total = sum(len(g['commands']) for g in groups)

    lines: list[str] = []
    lines.append('# Tektronix 3 Series MDO（含 MDO3014）SCPI 控制指令手册（中文整理）')
    lines.append('')
    lines.append('> **来源**：`docs/3-MDO-Oscilloscope-Programmer-Manual-077149800.pdf`（Tektronix *3 Series MDO Oscilloscopes Programmer Manual*，文档号 077-1498-00）')
    lines.append('>')
    lines.append('> **整理方式**：按手册 **Command Groups** 功能分组表提取全部指令；功能说明译为中文；Syntax 保留手册原文（SCPI 大写为最短合法缩写）。')
    lines.append('>')
    lines.append('> **用途**：支撑 WiParse 将 MDO3014 全量遥控能力接入 **PC GUI** 与 **CLI/AI**。')
    lines.append('')
    lines.append('## 1. 阅读约定')
    lines.append('')
    lines.append('| 记号 | 含义 |')
    lines.append('|------|------|')
    lines.append('| `ACQuire:MODe` | 最短可写 `ACQ:MOD`（大写必写，小写可选） |')
    lines.append('| `{A\\|B\\|C}` | 枚举参数，三选一 |')
    lines.append('| `<NR1>` / `<NR3>` / `<QString>` | 整数 / 浮点 / 引号字符串 |')
    lines.append('| 指令名以 `?` 结尾 | 查询（Query） |')
    lines.append('| `CH<x>` / `REF<x>` / `MEAS<x>` / `MATH[1]` | 通道/参考/测量/数学波形占位符 |')
    lines.append('')
    lines.append('## 2. WiParse 集成优先级（MDO3014）')
    lines.append('')
    lines.append('| 优先级 | 分组 | 典型 CLI / GUI 用途 |')
    lines.append('|--------|------|---------------------|')
    lines.append('| P0 | Hard Copy / Save and Recall | `scope shot` 截屏 PNG、保存/加载 setup |')
    lines.append('| P0 | Waveform Transfer | `CURVe?` + `DATa:SOUrce` / `WFMOutpre` 数值波形 |')
    lines.append('| P0 | Horizontal / Vertical / Acquisition | 时基、通道开关/伏格、RUN/STOP |')
    lines.append('| P0 | File System | 远程读写文件、工作目录 |')
    lines.append('| P1 | Trigger | 边沿等触发源、耦合、电平 |')
    lines.append('| P1 | Measurement / Cursor | 自动测量与光标读数给 AI |')
    lines.append('| P2 | Math / Zoom / Display | 运算波形、缩放、显示风格 |')
    lines.append('| P2 | Status and Error / Miscellaneous | `*IDN?`、`*OPC?`、错误队列 |')
    lines.append('| P3 | Bus / Search / RF / Power / AFG / ARB… | 按测试场景逐步覆盖 |')
    lines.append('')
    lines.append('## 3. 分组目录')
    lines.append('')
    for i, g in enumerate(groups, 1):
        lines.append(f"{i}. **{g['name_zh']}** — {len(g['commands'])} 条")
    lines.append('')
    lines.append(f'**合计：{len(groups)} 组，{total} 条指令（分组表汇总并去重）。**')
    lines.append('')
    lines.append('---')
    lines.append('')

    for gi, g in enumerate(groups, 1):
        lines.append(f"## {gi}. {g['name_zh']}")
        lines.append('')
        lines.append(f'手册原名：*{g["name_en"]}*')
        lines.append('')
        lines.append('| 指令 | 功能说明（中文） | Syntax（手册原文，节选） |')
        lines.append('|------|------------------|-------------------------|')
        for c in g['commands']:
            cmd = c['command'].replace('|', '\\|')
            zh = translate_desc(c['description_en'], c['command']).replace('|', '\\|')
            syns = find_syntax(c['command'], syntax_idx)
            if syns:
                syn_cell = '<br>'.join(f'`{s}`' for s in syns[:3]).replace('|', '\\|')
            else:
                syn_cell = f'`{cmd}`'
            lines.append(f'| `{cmd}` | {zh} | {syn_cell} |')
        lines.append('')

    lines.append('---')
    lines.append('')
    lines.append('## 附录 A：IEEE 488.2 公用指令速查')
    lines.append('')
    lines.append('| 指令 | 功能说明（中文） |')
    lines.append('|------|------------------|')
    lines.append('| `*IDN?` | 查询仪器识别信息（厂商、型号、序列号、固件版本）。 |')
    lines.append('| `*RST` | 复位仪器到已知状态。 |')
    lines.append('| `*OPC` / `*OPC?` | 操作完成：置位或查询 OPC。 |')
    lines.append('| `*WAI` | 等待挂起操作完成后再继续。 |')
    lines.append('| `*CLS` | 清除状态与错误队列等相关信息。 |')
    lines.append('| `*ESE` / `*ESE?` | 设置/查询事件状态使能寄存器。 |')
    lines.append('| `*ESR?` | 查询（并清除）标准事件状态寄存器。 |')
    lines.append('| `*SRE` / `*SRE?` | 设置/查询服务请求使能寄存器。 |')
    lines.append('| `*STB?` | 查询状态字节寄存器。 |')
    lines.append('| `*TST?` | 自检并返回结果码。 |')
    lines.append('')
    lines.append('## 附录 B：与现有 WiParse 示波器能力的对应')
    lines.append('')
    lines.append('| WiParse 现状 | 手册指令 | 说明 |')
    lines.append('|--------------|----------|------|')
    lines.append('| `scope shot` / HARDCopy PNG | `SAVe:IMAGe:*` / `HARDCopy` 组 | 已实现截屏 |')
    lines.append('| `scope wave`（规划中） | `DATa:SOUrce`、`CURVe?`、`WFMOutpre:*` | 数值波形导出 |')
    lines.append('| 连接/`*IDN?` | Miscellaneous / Configuration | 识别 TEKTRONIX,MDO3014 |')
    lines.append('| 文件系统（规划中） | `FILESystem:*` | CWD、读写、挂载网络盘 |')
    lines.append('')
    lines.append('## 修订记录')
    lines.append('')
    lines.append('| 日期 | 说明 |')
    lines.append('|------|------|')
    lines.append('| 2026-07-13 | 基于 077-1498-00 全文提取 Command Groups，生成中文功能说明手册。 |')
    lines.append('| 2026-07-13 | 修复 FILESystem/HARDCopy 被误拆词、MATH[1] 漏提、硬拷贝换行断裂；补全文件系统/硬拷贝/数学分组。 |')
    lines.append('')

    OUT.write_text('\n'.join(lines), encoding='utf-8')
    print('wrote', OUT)
    print('groups', len(groups), 'commands', total)
    for g in groups:
        print(f"  - {g['name_zh']}: {len(g['commands'])}")


if __name__ == '__main__':
    main()
