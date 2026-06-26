# ==========================================
# Module: WPC Qi 2.2.1 / MPP 协议深度解析引擎
# Reference: Qi 2.2.1 Communications Protocol + MPP Communications Protocol (WPC)
# ==========================================
import re

from ..i18n import get_language, tr

# ---------------------------------------------------------------------------
# 常量与查找表
# ---------------------------------------------------------------------------

EPT_REASONS = {
    0x00: 'EPT/nul — 未知 / 未指定',
    0x01: 'EPT/cc — 充电完成',
    0x02: 'EPT/if — 内部故障',
    0x03: 'EPT/ot — 过温',
    0x04: 'EPT/ov — 过压',
    0x05: 'EPT/oc — 过流',
    0x06: 'EPT/bf — 电池故障',
    0x08: 'EPT/nr — 无响应',
    0x0A: 'EPT/an — 协商中止',
    0x0B: 'EPT/rst — 重启功率传输',
    0x0C: 'EPT/rep — 重新 Ping (re-ping)',
}

GRQ_REQUESTS = {
    0x00: 'PTx 标识 (Identification)',
    0x01: 'PTx 能力 (Capabilities)',
    0x02: 'PTx 扩展标识 (Extended ID)',
    0x03: 'PTx 扩展能力 (Extended Capabilities)',
    0x04: '保留',
    0x05: '保留',
    0x20: 'MPP PTx 逆变器电压 (Inverter Voltage)',
    0x30: 'MPP 模式能力 (Mode Capabilities)',
    0x31: 'MPP 扩展模式能力 (Extended Mode Cap)',
}

SRQ_TYPES = {
    0x00: 'SRQ/en — 结束协商',
    0x01: 'SRQ/gp — Guaranteed Load Power',
    0x02: 'SRQ/rp — Reference Power',
    0x03: 'SRQ/fsk — FSK 配置',
    0x04: 'SRQ/rep — Re-ping delay',
    0x05: 'SRQ/rep — Re-ping delay',
    0x06: 'SRQ/cloakl — Cloak Ping Delay (low)',
    0x07: 'SRQ/pch — Power Control Hold-off (MPP) / Cloakh',
    0xA0: 'SRQ/pla — PLA 格式选择 (MPP)',
    0xA1: 'SRQ/xceMethod — 控制误差算法 (MPP)',
    0xA7: 'SRQ/verSel — 版本选择 (MPP)',
    0xA8: 'SRQ/xceGain — 控制增益 (MPP)',
    0xA9: 'SRQ/freqsel — 频率选择 (MPP)',
    0xAA: 'SRQ/egpl — Extended Guaranteed Power (MPP)',
    0xF0: 'SRQ/prop / SRQ/MppProp — 专有参数',
}

FSK_RESPONSE = {
    0x00: ('NAK', '拒绝 / 不支持'),
    0x33: ('ATN', '注意 (Attention)'),
    0x55: ('ND', '未定义 (Not Defined)'),
    0xFF: ('ACK', '确认 (Acknowledge)'),
}

# WPC Power Receiver Manufacturer Codes (PRMC) — 公开/抓包可验证项
# 完整表见 WPC《Power Receiver Manufacturer Codes》独立文档
PRMC_VENDORS = {
    0x005A: 'Apple',
    0x0042: 'Samsung',
    0x010E: 'Google',
    0x0173: 'Xiaomi',
    0x0186: 'Huawei',
    0x01A2: 'OPPO',
    0x01B0: 'Vivo',
    0x0506: 'Infineon',
}
PTMC_VENDORS = PRMC_VENDORS  # 兼容旧名

ASK_MSG_SIZE_OVERRIDE = {}

FSK_DEPTH_LABELS = {
    0: '深度 0',
    1: '深度 1',
    2: '深度 2',
    3: '深度 3',
}

# Qi 2.2.1 Communications Protocol §8.6 Table 27
DSR_TYPES = {
    0x00: ('DSR/nak', '拒绝上一 PTx 数据包'),
    0x33: ('DSR/poll', '邀请 PTx 发送任意数据包'),
    0x55: ('DSR/nd', '上一 PTx 数据包非预期'),
    0xFF: ('DSR/ack', '上一 PTx 数据包已正确处理'),
}

FOD_TYPE_LABELS = {
    0: 'FOD/qf — Reference Quality Factor',
    1: 'FOD/rf — Reference Resonance Frequency',
}

MSR_PREF = {
    0: '无偏好',
    1: '保留功率传输合同',
    2: '不保留功率传输合同',
    3: '保留 (禁用)',
}

MSR_MAIN_MODE = {
    0: 'Continuous Power Mode (CPM)',
    1: 'Nominal Power Mode (NPM)',
    2: 'Low Power Mode (LPM)',
    3: 'High Power Mode (HPM)',
}

MSR_AUX = {
    0: '未选择辅助模式',
    1: 'Gain Measurement 辅助模式',
}

CLOAK_REASONS = {
    0: 'Generic',
    1: 'Forced (拒绝 Uncloak)',
    2: 'Thermally constrained',
    3: 'Insufficient Power',
    4: 'Coex Mitigation',
    5: 'End of Charge',
    6: 'PTx initiated',
    7: 'Foreign Object Detection',
}

RP_MODE_LABELS = {
    0: 'RP/0 — 正常值',
    1: 'RP/1 — 首次校准点',
    2: 'RP/2 — 附加校准点',
    4: 'RP/4 — 正常值 (抑制 Response)',
}

ASK_PACKETS = {
    0x01: ('SS', '信号强度 (Signal Strength)'),
    0x02: ('EPT', '结束功率传输 (End Power Transfer)'),
    0x03: ('CE', '控制误差 (Control Error, 8-bit)'),
    0x04: ('RP8', '接收功率 8-bit (Received Power)'),
    0x05: ('CHS', '充电状态 (Charge Status)'),
    0x06: ('PCH', '功率控制保持 (Power Control Hold-off)'),
    0x07: ('GRQ', '通用请求 (General Request)'),
    0x09: ('RENEG', '重新协商 (Renegotiate)'),
    0x13: ('MSR', '模式选择请求 (Mode Select Request)'),
    0x15: ('DSR', '数据流响应 (Data Stream Response)'),
    0x18: ('CLOAK', 'Cloak 请求 (Power Pause)'),
    0x19: ('XCE', '扩展控制误差 (Extended Control Error)'),
    0x1A: ('PROP/1A', 'MPP PRx 专有包'),
    0x1B: ('PROP/1B', 'MPP PRx 专有包'),
    0x20: ('SRQ', '特定请求 (Specific Request)'),
    0x22: ('FOD', '异物检测状态 (FOD Status)'),
    0x23: ('CAL_OP', '校准操作 (Calibration Operation)'),
    0x26: ('SADT/1e', 'SADT (even)'),
    0x27: ('SADT/1o', 'SADT (odd)'),
    0x28: ('GET', 'Get 请求'),
    0x29: ('EDS', '已启用数据流 (Enabled Data Streams)'),
    0x2A: ('PROP/2A', 'MPP PRx 专有包'),
    0x2B: ('PROP/2B', 'MPP PRx 专有包'),
    0x2C: ('CAL_ENTER', '进入校准'),
    0x2D: ('CAL_EXIT', '退出校准'),
    0x31: ('RP24', '接收功率 24-bit (Received Power)'),
    0x36: ('SADT/2e', 'SADT (even)'),
    0x37: ('SADT/2o', 'SADT (odd)'),
    0x38: ('SDSR', '数据流响应 (Data Stream Response)'),
    0x39: ('PROP/39', 'MPP PRx 专有包'),
    0x46: ('SADT/3e', 'SADT (even)'),
    0x47: ('SADT/3o', 'SADT (odd)'),
    0x48: ('SADC', 'SADT 控制 (Aux Data Control)'),
    0x49: ('PROP/49', 'MPP PRx 专有包'),
    0x50: ('KEST-COEFF', 'K-est 系数'),
    0x51: ('CFG', '配置 (Configuration)'),
    0x56: ('SADT/4e', 'SADT (even)'),
    0x57: ('SADT/4o', 'SADT (odd)'),
    0x58: ('REPORT/PLA', 'PLA 报告 (Power Loss Accounting)'),
    0x59: ('PROP/59', 'MPP PRx 专有包'),
    0x66: ('SADT/5e', 'SADT (even)'),
    0x67: ('SADT/5o', 'SADT (odd)'),
    0x71: ('ID', '身份识别 (Identification)'),
    0x76: ('SADT/6e', 'SADT (even)'),
    0x77: ('SADT/6o', 'SADT (odd)'),
    0x78: ('PLAP', 'PLA 参数 (Power Loss Accounting Params)'),
    0x79: ('PROP/79', 'MPP PRx 专有包'),
    0x81: ('XID', '扩展身份 (XID / MPP-XID)'),
    0x84: ('ECAP', '扩展接收能力 (Extended Capabilities)'),
    0x85: ('PROP/85', 'MPP PRx 专有包'),
    0x88: ('PLA_2', 'Power Loss Accounting v2'),
    0x90: ('PLAP_2', 'PLA 参数 v2'),
    0x96: ('CAL_CAPTURE', '校准捕获'),
    0xA8: ('MATEDQ-COEFF', 'Mated-Q 系数'),
}

FSK_PACKETS = {
    0x00: ('NAK', '拒绝'),
    0x01: ('ACK-P', '带载荷确认 (Acknowledge + Payload)'),
    0x0A: ('EPTR', '结束功率传输请求'),
    0x11: ('FAST-ACK', 'MPP 快速 ACK / 状态'),
    0x14: ('CAL_CAPTURE_RSP', '校准捕获响应'),
    0x1B: ('CAL_OP_RSP', '校准操作响应'),
    0x1C: ('PROP/1C', 'MPP PTx 专有包'),
    0x1D: ('PROP/1D', 'MPP PTx 专有包'),
    0x1E: ('CLOAK/RCS', 'Cloak / 调节控制状态'),
    0x1F: ('CHS', '充电状态 (Charge Status)'),
    0x23: ('MSS', '模式选择状态 (Mode Select Status)'),
    0x26: ('SADT/1e', 'SADT (even)'),
    0x27: ('SADT/1o', 'SADT (odd)'),
    0x2C: ('PROP/2C', 'MPP PTx 专有包'),
    0x2D: ('PROP/2D', 'MPP PTx 专有包'),
    0x2E: ('GET', 'Get 请求'),
    0x2F: ('EDS', '已启用数据流'),
    0x30: ('INV', '逆变器电压 (Inverter Voltage)'),
    0x33: ('ATN', '注意 (Attention)'),
    0x34: ('CAL_ENTER_RSP', '进入校准响应'),
    0x36: ('SADT/2e', 'SADT (even)'),
    0x37: ('SADT/2o', 'SADT (odd)'),
    0x3E: ('PROP/3E', 'MPP PTx 专有包'),
    0x3F: ('INV/SDSR/KEST', '逆变器电压 / SDSR / K-est'),
    0x40: ('CAP', 'PTx 能力 (Capabilities)'),
    0x43: ('CAL_CAP', '校准能力'),
    0x46: ('SADT/3e', 'SADT (even)'),
    0x47: ('SADT/3o', 'SADT (odd)'),
    0x4E: ('PROP/4E', 'MPP PTx 专有包'),
    0x4F: ('SADC', 'SADT 控制'),
    0x54: ('dPCAL_PARAM', '校准参数'),
    0x55: ('ND', '未定义'),
    0x56: ('SADT/4e', 'SADT (even)'),
    0x57: ('SADT/4o', 'SADT (odd)'),
    0x5A: ('MODECAP', '功率模式能力'),
    0x5E: ('PROP/5E', 'MPP PTx 专有包'),
    0x5F: ('PLAP', 'PLA 参数'),
    0x61: ('GMP', '增益测量参数'),
    0x66: ('SADT/5e', 'SADT (even)'),
    0x67: ('SADT/5o', 'SADT (odd)'),
    0x76: ('SADT/6e', 'SADT (even)'),
    0x77: ('SADT/6o', 'SADT (odd)'),
    0x88: ('PLAP_2', 'PLA 参数 v2'),
    0x8E: ('PROP/8E', 'MPP PTx 专有包'),
    0x8F: ('XID/ECAP', 'PTx 扩展标识 / 扩展能力'),
    0xA0: ('MODEXCAP', '扩展模式能力'),
    0xFF: ('ACK', '确认 (Acknowledge)'),
}


def _s8(val):
    return val - 256 if val > 127 else val


def _s16_be(hi, lo):
    val = (hi << 8) | lo
    return val - 65536 if val > 32767 else val


def _bits(val, hi, lo):
    width = hi - lo + 1
    return (val >> lo) & ((1 << width) - 1)


def _hex_bytes(data, limit=16):
    if not data:
        return 'None'
    shown = ' '.join(f'{b:02X}' for b in data[:limit])
    if len(data) > limit:
        shown += f' … (+{len(data) - limit} B)'
    return shown


def _qi_message_size(header, overrides=None):
    """按 Qi Header 编码计算 Message 字节数（不含 Header / Checksum）。"""
    if overrides and header in overrides:
        return overrides[header]
    if header <= 0x1F:
        return 1 + (header - 0) // 32
    if header <= 0x7F:
        return 2 + (header - 32) // 16
    if header <= 0xDF:
        return 8 + (header - 128) // 8
    return 20 + (header - 224) // 4


def _ptmc_vendor(prmc):
    return PRMC_VENDORS.get(prmc, tr('qi.unknown_vendor', code=prmc))


def _localize_pkt_desc(desc: str) -> str:
    if get_language() != 'en':
        return desc
    match = re.search(r'\(([A-Za-z][A-Za-z0-9 /\-_.]*)\)\s*$', desc)
    if match:
        return match.group(1).strip()
    return desc


def _split_payload_checksum(header, body, overrides=None):
    """按规范 Message 长度划分 Payload 与 XOR 校验字节。"""
    if not body:
        return [], None, 'N/A'
    msg_len = _qi_message_size(header, overrides)
    if len(body) == msg_len:
        return body, None, 'N/A'
    if len(body) == msg_len + 1:
        payload, cs = body[:msg_len], body[-1]
        calc = header
        for b in payload:
            calc ^= b
        ok = calc == cs
        status = "<span style='color:#22C55E;'>✅ OK</span>" if ok else "<span style='color:#EF4444;'>❌ ERR</span>"
        return payload, cs, status
    if len(body) > msg_len + 1:
        payload, cs = body[:msg_len], body[msg_len]
        calc = header
        for b in payload:
            calc ^= b
        ok = calc == cs
        status = "<span style='color:#22C55E;'>✅ OK</span>" if ok else "<span style='color:#EF4444;'>❌ ERR</span>"
        return payload, cs, status
    return body, None, 'N/A'


class _Html:
    B = "#38BDF8"
    O = "#FB923C"
    Y = "#FACC15"
    G = "#22C55E"
    R = "#EF4444"
    M = "#94A3B8"

    @classmethod
    def byte(cls, idx, label, val, lines):
        lines.append(
            f"• <span style='color:{cls.B}'>Byte {idx}:</span> "
            f"0x{val:02X} ({val}) — {label}"
        )

    @classmethod
    def field(cls, text, indent=1):
        pad = '&nbsp;' * (indent * 4)
        return f"{pad}↳ {text}"

    @classmethod
    def join(cls, lines):
        return '<br>'.join(lines)


class Qi22Parser:
    """Qi 2.2.1 / MPP ASK·FSK 报文字段解析器。"""

    @staticmethod
    def _insufficient():
        return f'<i>{tr("qi.insufficient")}</i>'

    @staticmethod
    def _no_payload():
        return f'<i>{tr("qi.no_payload")}</i>'

    def parse_message(self, line):
        line = re.sub(r'\s+', ' ', line).strip() + ' '
        if 'ASK ' in line:
            start = line.find('ASK ') + 4
            end = line.find(' F ', start)
            if end != -1:
                return self._decode_packet(line[start:end].strip(), 'ASK')
        if 'FSK ' in line:
            start = line.find('FSK ') + 4
            return self._decode_packet(line[start:].strip().split('(')[0], 'FSK')
        return None

    def _decode_packet(self, hex_str, p_type):
        try:
            raw = [int(x, 16) for x in hex_str.replace('0x', '').replace(',', ' ').split() if x]
            if not raw:
                return None

            header = raw[0]
            overrides = ASK_MSG_SIZE_OVERRIDE if p_type == 'ASK' else None
            payload, cs, cs_st = _split_payload_checksum(header, raw[1:], overrides)

            registry = ASK_PACKETS if p_type == 'ASK' else FSK_PACKETS
            name, desc = registry.get(header, (f'UNK_0x{header:02X}', tr('qi.unknown_pkt')))
            desc = _localize_pkt_desc(desc)
            if p_type == 'ASK':
                detail = self._decode_ask_payload(header, payload)
            else:
                detail = self._decode_fsk_payload(header, payload)

            title_color = '#38BDF8' if p_type == 'ASK' else '#FB923C'
            dir_text = tr('qi.dir_ask') if p_type == 'ASK' else tr('qi.dir_fsk')
            html = (
                f"<div style='min-width: 260px; font-family: Consolas, monospace;'>"
                f"<b style='color:{title_color}; font-size: 11pt;'>{dir_text}</b>"
                f"<hr style='border:1px solid #334155; margin: 5px 0;'>"
                f"<b>{tr('qi.header')}</b> <span style='color:#FACC15;'>0x{header:02X}</span> "
                f"[{name}] {desc}<br>"
                f"<b>{tr('qi.payload', n=len(payload))}</b> "
                f"<span style='color:#94A3B8'>{_hex_bytes(payload, 24)}</span><br>"
            )
            if cs is not None:
                html += f"<b>{tr('qi.xor')}</b> 0x{cs:02X} ({cs_st})<br>"
            html += (
                f"<hr style='border:1px dashed #334155; margin: 5px 0;'>"
                f"<b>{tr('qi.fields')}</b><br>"
                f"<div style='color:#E2E8F0; padding-top: 5px; line-height: 1.45;'>{detail}</div>"
                f"</div>"
            )
            return html
        except Exception as exc:
            return tr('qi.parse_error', error=exc)

    # ------------------------------------------------------------------
    # ASK 载荷解析
    # ------------------------------------------------------------------

    def _decode_ask_payload(self, header, payload):
        decoders = {
            0x01: self._ask_ss,
            0x02: self._ask_ept,
            0x03: self._ask_ce,
            0x04: self._ask_rp8,
            0x05: self._ask_chs,
            0x06: self._ask_pch,
            0x07: self._ask_grq,
            0x09: self._ask_reneg,
            0x13: self._ask_msr,
            0x15: self._ask_dsr,
            0x18: self._ask_cloak,
            0x19: self._ask_xce,
            0x20: self._ask_srq,
            0x22: self._ask_fod,
            0x23: self._ask_cal_op,
            0x28: self._ask_get,
            0x29: self._ask_eds,
            0x31: self._ask_rp24,
            0x51: self._ask_cfg,
            0x71: self._ask_id,
            0x81: self._ask_xid,
            0x84: self._ask_ecap,
            0x48: self._ask_sadc,
            0x38: self._ask_sdsr,
            0x78: self._ask_plap,
            0x88: self._ask_pla,
            0x96: self._ask_cal_capture,
            0xA8: self._ask_matedq,
        }
        if header in (0x26, 0x27, 0x36, 0x37, 0x46, 0x47, 0x56, 0x57, 0x66, 0x67, 0x76, 0x77):
            return self._ask_sadt(payload)
        if header in (0x1A, 0x1B, 0x2A, 0x2B, 0x39, 0x49, 0x59, 0x79, 0x85):
            return self._generic_prop(payload)
        if header in (0x2C, 0x2D, 0x50, 0x58, 0x90):
            return self._generic_structured(payload, '校准 / PLA / 系数')
        decoder = decoders.get(header)
        if decoder:
            return decoder(payload)
        return self._generic_raw(payload)

    def _ask_ss(self, p):
        if len(p) < 1:
            return self._insufficient()
        lines = []
        _Html.byte(0, 'Signal Strength', p[0], lines)
        lines.append(_Html.field(f"耦合强度: <b>{p[0]}</b> / 255 ({p[0] / 255 * 100:.1f}%)"))
        lines.append(_Html.field(f"估算: SS = V / Vmax × 256"))
        return _Html.join(lines)

    def _ask_ept(self, p):
        if len(p) < 1:
            return self._insufficient()
        reason = EPT_REASONS.get(p[0], f'保留码 0x{p[0]:02X}')
        color = '#22C55E' if p[0] == 0x01 else ('#EF4444' if p[0] in (0x02, 0x03, 0x04, 0x05, 0x06, 0x0B) else '#E2E8F0')
        detail = f'结束原因: <b style="color:{color}">{reason}</b>'
        return (
            f"• <span style='color:{_Html.B}'>Byte 0:</span> 0x{p[0]:02X}<br>"
            f"{_Html.field(detail)}"
        )

    def _ask_ce(self, p):
        if len(p) < 1:
            return self._insufficient()
        ce = _s8(p[0])
        color = '#22C55E' if ce < 0 else '#EF4444'
        lines = []
        _Html.byte(0, 'Control Error (signed 8-bit)', p[0], lines)
        lines.append(_Html.field(f"误差值: <b style='color:{color}'>{ce}</b> ({ce / 128 * 100:+.1f}% 参考)"))
        lines.append(_Html.field('<i>负值 → PTx 降功率；正值 → PTx 升功率</i>'))
        return _Html.join(lines)

    def _ask_rp8(self, p):
        if len(p) < 1:
            return self._insufficient()
        lines = []
        _Html.byte(0, 'Received Power (8-bit)', p[0], lines)
        lines.append(_Html.field(f"接收功率比: <b>{p[0]}</b> / 128 = {p[0] / 128 * 100:.1f}% MaxPower"))
        return _Html.join(lines)

    def _ask_chs(self, p):
        if len(p) < 1:
            return self._insufficient()
        if p[0] == 0xFF:
            detail = '无电池 / 无法获取电量 (0xFF)'
        elif p[0] <= 100:
            detail = f'电池电量: <b style="color:#22C55E">{p[0]} %</b>'
        else:
            detail = f'保留值 0x{p[0]:02X}'
        return (
            f"• <span style='color:{_Html.B}'>Byte 0:</span> 0x{p[0]:02X}<br>"
            f"{_Html.field(detail)}"
        )

    def _ask_pch(self, p):
        if len(p) < 1:
            return self._insufficient()
        return (
            f"• <span style='color:{_Html.B}'>Byte 0:</span> 0x{p[0]:02X}<br>"
            f"{_Html.field(f'Hold-off 时间: <b>{p[0]} ms</b> (毫秒，规范直接取值)')}"
        )

    def _ask_grq(self, p):
        if len(p) < 1:
            return self._insufficient()
        req = GRQ_REQUESTS.get(p[0], f'请求类型 0x{p[0]:02X}')
        return (
            f"• <span style='color:{_Html.B}'>Byte 0:</span> 0x{p[0]:02X}<br>"
            f"{_Html.field(f'请求内容: <b>{req}</b>')}"
        )

    def _ask_reneg(self, p):
        return f'<i>{tr("qi.reneg_no_payload")}</i>' if not p else self._generic_raw(p)

    def _ask_msr(self, p):
        if len(p) < 1:
            return self._insufficient()
        pref = (p[0] >> 6) & 0x03
        main_mode = (p[0] >> 2) & 0x03
        aux = p[0] & 0x01
        lines = []
        _Html.byte(0, 'Mode Select Request', p[0], lines)
        lines.append(_Html.field(
            f'Preference [Bit7-6]: <b>{MSR_PREF.get(pref, pref)}</b>'
        ))
        lines.append(_Html.field(
            f'Main Mode [Bit3-2]: <b>{MSR_MAIN_MODE.get(main_mode, main_mode)}</b>'
        ))
        lines.append(_Html.field(f'Aux [Bit0]: <b>{MSR_AUX.get(aux, aux)}</b>'))
        if (p[0] >> 4) & 0x03:
            lines.append(_Html.field(f'Reserved [Bit5-4]: {(p[0] >> 4) & 0x03}'))
        if (p[0] >> 1) & 0x01:
            lines.append(_Html.field(f'Reserved [Bit1]: {(p[0] >> 1) & 1}'))
        return _Html.join(lines)

    def _ask_dsr(self, p):
        if len(p) < 1:
            return self._insufficient()
        name, desc = DSR_TYPES.get(p[0], (f'0x{p[0]:02X}', '保留 / 未定义'))
        color = '#22C55E' if p[0] == 0xFF else ('#FACC15' if p[0] == 0x33 else '#E2E8F0')
        lines = ['• 数据流响应 DSR (Qi 2.2.1 §8.6, Header 0x15)']
        _Html.byte(0, 'Type', p[0], lines)
        lines.append(_Html.field(
            f'类型: <b style="color:{color}">{name}</b> — {desc}'
        ))
        return _Html.join(lines)

    def _ask_cloak(self, p):
        if len(p) < 1:
            return self._insufficient()
        reason = (p[0] & 0x0F) if len(p) == 1 else p[0]
        reason_text = CLOAK_REASONS.get(reason, f'0x{reason:X}')
        return (
            f"• <span style='color:{_Html.B}'>Byte 0:</span> 0x{p[0]:02X}<br>"
            f"{_Html.field(f'Cloak Reason [低 4 bit]: <b>{reason_text}</b>')}<br>"
            f"{_Html.field('请求进入 Cloak (Power Pause) 阶段')}"
        )

    def _ask_xce(self, p):
        if len(p) < 1:
            return self._insufficient()
        ce = _s8(p[0])
        color = '#22C55E' if ce < 0 else '#EF4444'
        lines = []
        _Html.byte(0, 'Control Error Value (8-bit)', p[0], lines)
        lines.append(_Html.field(
            f"MPP 扩展控制误差: <b style='color:{color}'>{ce}</b> (详见 MPP System 规范)"
        ))
        return _Html.join(lines)

    def _ask_srq(self, p):
        if len(p) < 1:
            return self._insufficient()
        req = SRQ_TYPES.get(p[0], f'请求 0x{p[0]:02X}')
        lines = []
        _Html.byte(0, 'Specific Request Type', p[0], lines)
        lines.append(_Html.field(f'含义: <b>{req}</b>'))
        if len(p) >= 2:
            lines.append(_Html.field(f'参数: {_hex_bytes(p[1:])}'))
        return _Html.join(lines)

    def _ask_fod(self, p):
        if len(p) < 2:
            return f'<i>FOD Status 需要 2 字节，当前 {len(p)} B</i>' + (
                f'<br>{self._generic_raw(p)}' if p else ''
            )
        f_type = p[0] & 0x07
        support = p[1]
        lines = []
        _Html.byte(0, 'Reserved + Type', p[0], lines)
        lines.append(_Html.field(
            f'Type [Bit2-0]: <b>{FOD_TYPE_LABELS.get(f_type, f"保留 ({f_type})")}</b>'
        ))
        if p[0] & 0xF8:
            lines.append(_Html.field(f'Reserved [Bit7-3]: 0x{p[0] >> 3:02X}'))
        _Html.byte(1, 'FOD Support Data', support, lines)
        if f_type == 0:
            lines.append(_Html.field(f'Reference Q 因子: <b>{support}</b>'))
        elif f_type == 1:
            lines.append(_Html.field(f'Reference 谐振频率编码: <b>{support}</b>'))
        return _Html.join(lines)

    def _ask_cal_op(self, p):
        if len(p) < 1:
            return self._insufficient()
        op = {0x00: '查询能力', 0x01: '开始捕获', 0x02: '停止捕获'}.get(p[0], f'0x{p[0]:02X}')
        lines = [_Html.field(f'校准操作: <b>{op}</b>')]
        if len(p) >= 2:
            lines.append(_Html.field(f'参数: {_hex_bytes(p[1:])}'))
        return _Html.join([f"• <span style='color:{_Html.B}'>Byte 0:</span> 0x{p[0]:02X}"] + lines)

    def _ask_get(self, p):
        if len(p) < 1:
            return self._insufficient()
        return (
            f"• <span style='color:{_Html.B}'>Byte 0:</span> 0x{p[0]:02X}<br>"
            f"{_Html.field(f'请求 PTx 发送 Header <b>0x{p[0]:02X}</b> 的 FSK 包')}"
        )

    def _ask_eds(self, p):
        if not p:
            return self._no_payload()
        streams = [i for i in range(min(len(p) * 8, 32)) if (p[i // 8] >> (i % 8)) & 1]
        lines = [f"• 已启用数据流位图 ({len(p)} B): {_hex_bytes(p)}"]
        if streams:
            lines.append(_Html.field(f'启用 Stream ID: <b>{", ".join(map(str, streams))}</b>'))
        else:
            lines.append(_Html.field('无活跃数据流'))
        return _Html.join(lines)

    def _ask_rp24(self, p):
        if len(p) < 3:
            return f'<i>{tr("qi.need_payload_3b")}</i>'
        mode = p[0] & 0x07
        rp_val = (p[1] << 8) | p[2]
        lines = []
        _Html.byte(0, 'Reserved + Mode', p[0], lines)
        _Html.byte(1, 'Estimated RP MSB', p[1], lines)
        _Html.byte(2, 'Estimated RP LSB', p[2], lines)
        lines.append(_Html.field(
            f'Mode [Bit2-0]: <b>{RP_MODE_LABELS.get(mode, f"0x{mode:X}")}</b>'
        ))
        if p[0] & 0xF8:
            lines.append(_Html.field(f'Reserved [Bit7-3]: 0x{p[0] >> 3:02X}'))
        lines.append(_Html.field(
            f'Estimated Received Power: <b>{rp_val}</b> (见 FOD 规范换算)'
        ))
        return _Html.join(lines)

    def _ask_cfg(self, p):
        exp_len = _qi_message_size(0x51)
        if len(p) < exp_len:
            return f'<i>Configuration 需要 {exp_len} 字节，当前 {len(p)} B</i>' + (
                f'<br>{self._generic_raw(p)}' if p else ''
            )
        ref_pwr = p[0] & 0x3F
        ai = (p[2] >> 6) & 1
        ob = (p[2] >> 3) & 1
        count = p[2] & 0x0F
        win_size = (p[3] >> 4) & 0x0F
        win_offset = p[3] & 0x0F
        neg = (p[4] >> 7) & 1
        polarity = (p[4] >> 6) & 1
        depth = (p[4] >> 4) & 0x03
        buf_size = (p[4] >> 1) & 0x07
        dup = p[4] & 0x01
        buf_bytes = 32 * (1 << (buf_size - 1)) if buf_size >= 1 else 0
        lines = []
        _Html.byte(0, 'Reference Power', p[0], lines)
        lines.append(_Html.field(
            f'Reference Power [Bit5-0]: <b>{ref_pwr}</b> '
            f'(≈ {ref_pwr / 2:.1f} W，合约参考功率)'
        ))
        if p[0] & 0xC0:
            lines.append(_Html.field(f'Power Class [Bit7-6]: 应为 00 (当前 0x{(p[0] >> 6):X})'))
        _Html.byte(1, 'Reserved', p[1], lines)
        _Html.byte(2, 'AI + OB + Count', p[2], lines)
        lines.append(_Html.field(f'Authentication (AI) [Bit6]: <b>{"支持" if ai else "不支持"}</b>'))
        lines.append(_Html.field(f'Out-of-band (OB) [Bit3]: <b>{"支持" if ob else "不支持"}</b>'))
        lines.append(_Html.field(f'配置阶段可选包 Count [Bit3-0]: <b>{count}</b>'))
        _Html.byte(3, 'Window Size + Offset', p[3], lines)
        lines.append(_Html.field(f'Window Size [高半字节]: <b>{win_size}</b> (×4 ms = {win_size * 4} ms)'))
        lines.append(_Html.field(f'Window Offset [低半字节]: <b>{win_offset}</b> (×4 ms = {win_offset * 4} ms)'))
        _Html.byte(4, 'Neg + FSK + Buffer', p[4], lines)
        lines.append(_Html.field(f'Extended Protocol (Neg) [Bit7]: <b>{"支持" if neg else "Baseline"}</b>'))
        lines.append(_Html.field(f'FSK Polarity [Bit6]: <b>{"负极性" if polarity else "正极性"}</b>'))
        lines.append(_Html.field(f'FSK Depth [Bit5-4]: <b>{FSK_DEPTH_LABELS.get(depth, depth)}</b>'))
        lines.append(_Html.field(
            f'Buffer Size [Bit3-1]: <b>{buf_size}</b>'
            + (f' (≈ {buf_bytes} B 接收缓冲)' if buf_bytes else '')
        ))
        lines.append(_Html.field(f'Dup 双向数据流 [Bit0]: <b>{"支持" if dup else "不支持"}</b>'))
        return _Html.join(lines)

    def _ask_id(self, p):
        exp_len = _qi_message_size(0x71)
        if len(p) < exp_len:
            return f'<i>Identification 需要 {exp_len} 字节，当前 {len(p)} B</i>' + (
                f'<br>{self._generic_raw(p)}' if p else ''
            )
        major = p[0] >> 4
        minor = p[0] & 0x0F
        prmc = (p[1] << 8) | p[2]
        ext = (p[3] >> 7) & 1
        basic_id = ((p[3] & 0x7F) << 24) | (p[4] << 16) | (p[5] << 8) | p[6]
        vendor = _ptmc_vendor(prmc)
        profile = {
            (1, 1): 'BPP', (1, 2): 'BPP', (1, 3): 'BPP',
            (2, 0): 'EPP/MPP', (2, 1): 'EPP/MPP', (2, 2): 'MPP',
        }
        prof_hint = profile.get((major, minor), '')
        lines = []
        _Html.byte(0, 'Major + Minor Version', p[0], lines)
        ver_text = f'{major}.{minor}' + (f' ({prof_hint})' if prof_hint else '')
        lines.append(_Html.field(f'Qi 版本 [Bit7-4 / Bit3-0]: <b>{ver_text}</b>'))
        _Html.byte(1, 'PRMC High', p[1], lines)
        _Html.byte(2, 'PRMC Low', p[2], lines)
        lines.append(_Html.field(f'制造商代码 (PRMC): <b>0x{prmc:04X}</b> ({vendor})'))
        _Html.byte(3, 'Ext + Basic ID (MSB)', p[3], lines)
        lines.append(_Html.field(f'Ext [Bit7]: <b>{"是 (配置阶段含 XID/MPP-XID)" if ext else "否"}</b>'))
        for i, b in enumerate(p[4:7], start=4):
            _Html.byte(i, 'Basic Device Identifier', b, lines)
        lines.append(_Html.field(f'Basic Device ID: <b>0x{basic_id:07X}</b>'))
        return _Html.join(lines)

    def _ask_xid(self, p):
        """0x81: Baseline Extended ID (B0≠0xFE) 或 MPP-XID (B0=0xFE)。"""
        if len(p) >= 1 and p[0] == 0xFE:
            return self._ask_mpp_xid(p)
        return self._ask_baseline_xid(p)

    def _ask_baseline_xid(self, p):
        exp_len = _qi_message_size(0x81)
        if len(p) < exp_len:
            return (
                f'<i>Extended Identification (XID) 需要 {exp_len} 字节，当前 {len(p)} B</i>'
                + (f'<br>{self._generic_raw(p)}' if p else '')
            )
        ext_id = int.from_bytes(p[:exp_len], 'big')
        lines = [f'• Extended Identification — XID (Qi 2.2.1 §8.8, {exp_len} B)']
        for i, b in enumerate(p[:exp_len]):
            _Html.byte(i, 'Extended Device Identifier', b, lines)
        lines.append(_Html.field(
            f'Extended Device ID: <b>0x{ext_id:0{exp_len * 2}X}</b>'
        ))
        if p[0] == 0xFE:
            lines.append(_Html.field(
                '<span style="color:#EF4444">B0=0xFE 违反 Baseline XID 规范，应为 MPP-XID</span>'
            ))
        return _Html.join(lines)

    def _ask_mpp_xid(self, p):
        exp_len = _qi_message_size(0x81)
        if len(p) < exp_len:
            return (
                f'<i>MPP-XID 需要 {exp_len} 字节，当前 {len(p)} B</i>'
                + (f'<br>{self._generic_raw(p)}' if p else '')
            )
        if p[0] != 0xFE:
            return (
                f'<i>B0 应为 MPP Selector 0xFE，当前 0x{p[0]:02X}</i>'
                f'<br>{self._generic_raw(p)}'
            )
        restricted = p[1] & 0x01
        vrect = p[3]
        alpha0 = _s8(p[4])
        alpha1 = _s8(p[5])
        alpha_k = p[6]
        lines = [f'• MPP-XID (Qi 2.2.1 MPP §8.1.29, {exp_len} B)']
        _Html.byte(0, 'XID Sub-Header (Selector)', p[0], lines)
        lines.append(_Html.field('MPP Selector: <b>0xFE</b>'))
        _Html.byte(1, 'Restricted + Mfg Rsvd', p[1], lines)
        lines.append(_Html.field(
            f'Restricted [Bit0]: <b>{"MPP Restricted (360 kHz)" if restricted else "MPP Full"}</b>'
        ))
        _Html.byte(2, 'Manufacturer Reserved', p[2], lines)
        _Html.byte(3, 'VRECT', p[3], lines)
        lines.append(_Html.field(f'VRECT: <b>{vrect * 20} mV</b> ({vrect * 0.02:.3f} V, ×20 mV)'))
        _Html.byte(4, 'Alpha0 Rx', p[4], lines)
        lines.append(_Html.field(f'Alpha0 × 100: <b>{alpha0}</b>'))
        _Html.byte(5, 'Alpha1 Rx', p[5], lines)
        lines.append(_Html.field(f'Alpha1 × 100: <b>{alpha1}</b>'))
        _Html.byte(6, 'Alpha-Kth Rx', p[6], lines)
        lines.append(_Html.field(f'Alpha-Kth × 100: <b>{alpha_k}</b> (阈值通常 = 100)'))
        _Html.byte(7, 'Manufacturer Reserved', p[7], lines)
        return _Html.join(lines)

    def _ask_ecap(self, p):
        if len(p) < 2:
            return self._generic_raw(p)
        lines = [f"• 扩展接收能力 ({len(p)} B)"]
        _Html.byte(0, 'Capabilities B0', p[0], lines)
        lines.append(_Html.field(f'EPP 支持 [Bit0]: <b>{"是" if p[0] & 0x01 else "否"}</b>'))
        lines.append(_Html.field(f'MPP 支持 [Bit1]: <b>{"是" if p[0] & 0x02 else "否"}</b>'))
        lines.append(_Html.field(f'Auth 支持 [Bit2]: <b>{"是" if p[0] & 0x04 else "否"}</b>'))
        if len(p) >= 2:
            _Html.byte(1, 'Max Power / Profile', p[1], lines)
            lines.append(_Html.field(f'协商最大功率: <b>{p[1] * 0.5:.1f} W</b>'))
        if len(p) > 2:
            lines.append(_Html.field(f'附加: {_hex_bytes(p[2:])}'))
        return _Html.join(lines)

    def _ask_sadc(self, p):
        return self._stream_control(p, 'SADC (Aux Data Control)')

    def _ask_sdsr(self, p):
        if len(p) < 1:
            return self._insufficient()
        name, desc = DSR_TYPES.get(p[0], (f'0x{p[0]:02X}', '数据流响应码'))
        lines = [
            f"• <span style='color:{_Html.B}'>Byte 0:</span> 0x{p[0]:02X}",
            _Html.field(f'数据流响应 (SDSR): <b>{name}</b> — {desc}'),
        ]
        if len(p) >= 2:
            lines.append(_Html.field(f'Stream ID: <b>{p[1]}</b>'))
        return _Html.join(lines)

    def _ask_sadt(self, p):
        if len(p) < 2:
            return self._generic_raw(p)
        stream_id = p[0]
        seq = p[1]
        data = p[2:]
        lines = [
            f"• SADT 数据流包 ({len(p)} B)",
            _Html.field(f'Stream ID: <b>{stream_id}</b>'),
            _Html.field(f'序列号: <b>{seq}</b>'),
            _Html.field(f'数据: <span style="color:#94A3B8">{_hex_bytes(data, 12)}</span>'),
        ]
        return _Html.join(lines)

    def _ask_plap(self, p):
        return self._pla_params(p, 'PLAP (Power Loss Accounting Parameters)')

    def _ask_pla(self, p):
        if len(p) < 4:
            return self._generic_raw(p)
        lines = [f"• PLA v2 报告 ({len(p)} B)"]
        ploss = p[0] | (p[1] << 8)
        lines.append(_Html.field(f'Power Loss: <b>{ploss}</b> (原始单位)'))
        if len(p) >= 4:
            lines.append(_Html.field(f'附加字段: {_hex_bytes(p[2:])}'))
        return _Html.join(lines)

    def _ask_cal_capture(self, p):
        if len(p) < 1:
            return self._insufficient()
        return (
            f"• <span style='color:{_Html.B}'>Byte 0:</span> 0x{p[0]:02X}<br>"
            f"{_Html.field(f'捕获阶段: <b>{p[0]}</b>')}<br>"
            f"{_Html.field(f'数据: {_hex_bytes(p[1:])}' if len(p) > 1 else '')}"
        )

    def _ask_matedq(self, p):
        if len(p) < 4:
            return self._generic_raw(p)
        lines = [f"• Mated-Q 系数 ({len(p)} B)"]
        for i, b in enumerate(p[:8]):
            _Html.byte(i, f'Coeff {i}', b, lines)
        return _Html.join(lines)

    # ------------------------------------------------------------------
    # FSK 载荷解析
    # ------------------------------------------------------------------

    def _decode_fsk_payload(self, header, payload):
        if header in FSK_RESPONSE and not payload:
            name, desc = FSK_RESPONSE[header]
            return f"<b style='color:#22C55E'>✓ {name}</b> — {desc}"

        decoders = {
            0x01: self._fsk_ack_payload,
            0x11: self._fsk_fast_ack,
            0x1E: self._fsk_cloak_rcs,
            0x1F: self._fsk_chs,
            0x23: self._fsk_mss,
            0x2E: self._fsk_get,
            0x30: self._fsk_inv,
            0x3F: self._fsk_3f,
            0x40: self._fsk_cap,
            0x43: self._fsk_cal_cap,
            0x4F: self._fsk_sadc,
            0x5A: self._fsk_modecap,
            0x5F: self._fsk_plap,
            0x61: self._fsk_gmp,
            0x8F: self._fsk_xid_ecap,
            0xA0: self._fsk_modexcap,
        }
        if header in (0x26, 0x27, 0x36, 0x37, 0x46, 0x47, 0x56, 0x57, 0x66, 0x67, 0x76, 0x77):
            return self._ask_sadt(payload)
        if header in (0x1C, 0x1D, 0x2C, 0x2D, 0x3E, 0x4E, 0x5E, 0x8E):
            return self._generic_prop(payload)
        decoder = decoders.get(header)
        if decoder:
            return decoder(payload)
        return self._generic_raw(payload)

    def _fsk_ack_payload(self, p):
        if not p:
            return f"<b style='color:#22C55E'>✓ ACK</b> — {tr('qi.ack_prx')}"
        resp = {0x00: 'ACK', 0x01: 'NACK', 0x02: 'ND', 0x03: 'ATN'}.get(p[0], f'0x{p[0]:02X}')
        return (
            f"• <span style='color:{_Html.O}'>Byte 0:</span> 0x{p[0]:02X}<br>"
            f"{_Html.field(f'响应类型: <b>{resp}</b>')}"
        )

    def _fsk_fast_ack(self, p):
        return f"<b style='color:#22C55E'>✓ MPP Fast ACK (0x11)</b> — {tr('qi.fast_ack')}" + (
            f'<br>{self._generic_raw(p)}' if p else ''
        )

    def _fsk_cloak_rcs(self, p):
        if not p:
            return self._no_payload()
        sub = _bits(p[0], 3, 0) if len(p) == 1 else p[0]
        sub_map = {0: 'Cloak Request', 3: 'Regulation Control Status (RCS)'}
        lines = [
            f"• <span style='color:{_Html.O}'>Sub-type:</span> <b>{sub_map.get(sub, f'0x{sub:X}')}</b>",
        ]
        if sub == 3 and len(p) >= 2:
            _Html.byte(1, 'RCS Flags', p[1], lines)
            pwr = '<b style="color:#EF4444">是</b>' if p[1] & 0x01 else '否'
            tmp = '<b style="color:#EF4444">是</b>' if p[1] & 0x02 else '否'
            lines.append(_Html.field(f'功率限制: {pwr}'))
            lines.append(_Html.field(f'温度限制: {tmp}'))
        elif len(p) > 1:
            lines.append(_Html.field(f'参数: {_hex_bytes(p[1:])}'))
        return _Html.join(lines)

    def _fsk_chs(self, p):
        if len(p) < 1:
            return self._insufficient()
        detail = f'PTx 报告电量/状态: <b style="color:#22C55E">{p[0]} %</b>'
        return (
            f"• <span style='color:{_Html.O}'>Byte 0:</span> 0x{p[0]:02X}<br>"
            f"{_Html.field(detail)}"
        )

    def _fsk_mss(self, p):
        if len(p) < 1:
            return self._insufficient()
        mode = {0: 'BPP', 1: 'EPP', 2: 'MPP Full', 3: 'MPP Restricted'}.get(p[0] & 0x03, f'{p[0] & 0x03}')
        return (
            f"• <span style='color:{_Html.O}'>Byte 0:</span> 0x{p[0]:02X}<br>"
            f"{_Html.field(f'选定模式: <b>{mode}</b>')}<br>"
            f"{_Html.field(f'附加: {_hex_bytes(p[1:])}' if len(p) > 1 else '')}"
        )

    def _fsk_get(self, p):
        if len(p) < 1:
            return self._insufficient()
        return (
            f"• <span style='color:{_Html.O}'>Byte 0:</span> 0x{p[0]:02X}<br>"
            f"{_Html.field(f'PTx 主动请求 PRx 发送 Header <b>0x{p[0]:02X}</b>')}"
        )

    def _fsk_inv(self, p):
        if len(p) < 2:
            return self._generic_raw(p)
        voltage = (p[0] << 8) | p[1]
        lines = [
            f"• 逆变器电压 (Inverter Voltage)",
            _Html.field(f'Byte0-1: 0x{p[0]:02X} 0x{p[1]:02X}'),
            _Html.field(f'电压: <b>{voltage} mV</b> ({voltage / 1000:.3f} V)'),
        ]
        if len(p) > 2:
            lines.append(_Html.field(f'附加: {_hex_bytes(p[2:])}'))
        return _Html.join(lines)

    def _fsk_3f(self, p):
        if len(p) < 1:
            return self._insufficient()
        mod = p[0]
        mod_map = {0x00: 'Inverter Voltage', 0x01: 'SDSR (Data Stream Response)', 0x02: 'KEST (Estimated K)'}
        lines = [
            f"• <span style='color:{_Html.O}'>Modifier:</span> 0x{mod:02X} — <b>{mod_map.get(mod, '保留')}</b>",
        ]
        if mod == 0x00 and len(p) >= 3:
            voltage = (p[1] << 8) | p[2]
            lines.append(_Html.field(f'逆变器电压: <b>{voltage} mV</b> ({voltage / 1000:.3f} V)'))
        elif mod == 0x01 and len(p) >= 2:
            lines.append(_Html.field(f'SDSR 响应: <b>{p[1]}</b>'))
        elif mod == 0x02 and len(p) >= 3:
            kest = (p[1] << 8) | p[2]
            lines.append(_Html.field(f'Estimated K: <b>{kest}</b>'))
        elif len(p) > 1:
            lines.append(_Html.field(f'数据: {_hex_bytes(p[1:])}'))
        return _Html.join(lines)

    def _fsk_cap(self, p):
        if len(p) < 1:
            return self._insufficient()
        lines = [f"• PTx 能力标志 (Capabilities)"]
        _Html.byte(0, 'Status Flags', p[0], lines)
        pwr_lim = '<b style="color:#EF4444">降额</b>' if p[0] & 0x01 else '正常'
        tmp_lim = '<b style="color:#EF4444">过温</b>' if p[0] & 0x02 else '正常'
        fod = '<b style="color:#EF4444">是</b>' if p[0] & 0x04 else '<b style="color:#22C55E">正常</b>'
        lines.append(_Html.field(f'功率限制 [Bit0]: {pwr_lim}'))
        lines.append(_Html.field(f'温度限制 [Bit1]: {tmp_lim}'))
        lines.append(_Html.field(f'FOD 报警 [Bit2]: {fod}'))
        lines.append(_Html.field(f"鉴权状态 [Bit3]: {'进行中/完成' if p[0] & 0x08 else '无'}"))
        if len(p) >= 2:
            max_p = p[1] * 0.5
            lines.append(_Html.field(f'保证功率 [Byte1]: <b>{max_p:.1f} W</b>'))
        return _Html.join(lines)

    def _fsk_cal_cap(self, p):
        if len(p) < 2:
            return self._generic_raw(p)
        max_p = p[0] * 0.5
        auth = (p[1] >> 4) & 1
        lines = [
            f"• 校准能力 (Calibration Capabilities)",
            _Html.field(f'保证功率: <b>{max_p:.1f} W</b>'),
            _Html.field(f'鉴权硬件: <b>{"具备" if auth else "不具备"}</b>'),
        ]
        if len(p) > 2:
            lines.append(_Html.field(f'附加: {_hex_bytes(p[2:])}'))
        return _Html.join(lines)

    def _fsk_sadc(self, p):
        return self._stream_control(p, 'SADC (PTx Aux Data Control)')

    def _fsk_modecap(self, p):
        if len(p) < 2:
            return self._generic_raw(p)
        lines = [f"• 功率模式能力 (Mode Capabilities)"]
        _Html.byte(0, 'Supported Modes', p[0], lines)
        lines.append(_Html.field(f'BPP [Bit0]: {"✓" if p[0] & 0x01 else "—"}'))
        lines.append(_Html.field(f'EPP [Bit1]: {"✓" if p[0] & 0x02 else "—"}'))
        lines.append(_Html.field(f'MPP [Bit2]: {"✓" if p[0] & 0x04 else "—"}'))
        _Html.byte(1, 'Max MPP Power', p[1], lines)
        lines.append(_Html.field(f'MPP 最大功率: <b>{p[1] * 0.5:.1f} W</b>'))
        return _Html.join(lines)

    def _fsk_plap(self, p):
        return self._pla_params(p, 'PLAP (PTx Power Loss Accounting Params)')

    def _fsk_gmp(self, p):
        if len(p) < 2:
            return self._generic_raw(p)
        lines = [f"• 增益测量参数 (Gain Measurement)"]
        gain = (p[0] << 8) | p[1]
        lines.append(_Html.field(f'增益值: <b>{gain}</b>'))
        if len(p) > 2:
            lines.append(_Html.field(f'附加: {_hex_bytes(p[2:])}'))
        return _Html.join(lines)

    def _fsk_xid_ecap(self, p):
        if len(p) < 1:
            return self._insufficient()
        sub = p[0]
        sub_map = {0x00: 'Extended PTx Identification', 0x01: 'Extended PTx Capabilities'}
        lines = [
            f"• <span style='color:{_Html.O}'>Sub-type:</span> 0x{sub:02X} — <b>{sub_map.get(sub, '保留')}</b>",
        ]
        if sub == 0x00 and len(p) >= 5:
            ptmc = (p[1] << 8) | p[2]
            lines.append(_Html.field(
                f'PTMC: <b>0x{ptmc:04X}</b> ({_ptmc_vendor(ptmc)})'
            ))
            lines.append(_Html.field(f'PTx ID: {_hex_bytes(p[3:7]) if len(p) >= 7 else _hex_bytes(p[3:])}'))
        elif sub == 0x01 and len(p) >= 2:
            lines.append(_Html.field(f'MPP 支持: {"是" if p[1] & 0x01 else "否"}'))
            lines.append(_Html.field(f'Auth 支持: {"是" if p[1] & 0x02 else "否"}'))
            if len(p) >= 3:
                lines.append(_Html.field(f'最大功率: <b>{p[2] * 0.5:.1f} W</b>'))
        else:
            lines.append(_Html.field(f'数据: {_hex_bytes(p[1:])}'))
        return _Html.join(lines)

    def _fsk_modexcap(self, p):
        if len(p) < 2:
            return self._generic_raw(p)
        lines = [f"• 扩展模式能力 (Extended Mode Cap)"]
        for i, b in enumerate(p[:6]):
            _Html.byte(i, f'Cap Byte {i}', b, lines)
        return _Html.join(lines)

    # ------------------------------------------------------------------
    # 通用辅助
    # ------------------------------------------------------------------

    def _stream_control(self, p, title):
        if len(p) < 1:
            return f'<i>{title}: 载荷不足</i>'
        lines = [f"• {title}"]
        _Html.byte(0, 'Control', p[0], lines)
        lines.append(_Html.field(f'Stream ID [Bit0-4]: <b>{p[0] & 0x1F}</b>'))
        lines.append(_Html.field(f'Close Stream [Bit5]: <b>{"是" if p[0] & 0x20 else "否"}</b>'))
        if len(p) > 1:
            lines.append(_Html.field(f'参数: {_hex_bytes(p[1:])}'))
        return _Html.join(lines)

    def _pla_params(self, p, title):
        if len(p) < 4:
            return f'<i>{title}: 需要 ≥4 字节</i>' + (f'<br>{self._generic_raw(p)}' if p else '')
        lines = [f"• {title} ({len(p)} B)"]
        for i in range(0, min(len(p), 8), 2):
            if i + 1 < len(p):
                val = (p[i] << 8) | p[i + 1]
                lines.append(_Html.field(f'Param {i // 2}: 0x{p[i]:02X}{p[i+1]:02X} = <b>{val}</b>'))
        if len(p) > 8:
            lines.append(_Html.field(f'… {_hex_bytes(p[8:])}'))
        return _Html.join(lines)

    def _generic_prop(self, p):
        if not p:
            return f'<i>{tr("qi.prop_no_payload")}</i>'
        hex_part = f'<span style="color:#94A3B8">{_hex_bytes(p, 16)}</span>'
        return (
            f"• 专有 / 厂商扩展包<br>"
            f"{_Html.field(f'长度: {len(p)} B')}<br>"
            f"{_Html.field('HEX: ' + hex_part)}"
        )

    def _generic_structured(self, p, label):
        if not p:
            return f'<i>{label} — 无载荷</i>'
        lines = [f"• {label} ({len(p)} B)"]
        for i, b in enumerate(p[:10]):
            _Html.byte(i, f'Data', b, lines)
        if len(p) > 10:
            lines.append(_Html.field(f'… {_hex_bytes(p[10:])}'))
        return _Html.join(lines)

    def _generic_raw(self, p):
        if not p:
            return f'<i>{tr("qi.empty_pkt")}</i>'
        lines = [f"• 原始载荷 ({len(p)} B)"]
        for i, b in enumerate(p[:12]):
            _Html.byte(i, 'Data', b, lines)
        if len(p) > 12:
            lines.append(_Html.field(f'… <span style="color:#94A3B8">{_hex_bytes(p[12:])}</span>'))
        return _Html.join(lines)
