# ==========================================
# WPC Qi BPP/EPP + MPP 协议深度解析引擎
# Reference: docs/bpp_protocol.h, docs/mpp_protocol.h
# ==========================================
import re
from functools import lru_cache

from ..i18n import tr_in
from ..ui.theme_palette import active_tokens, get_theme
from .protocol_defs import (
    ASK_PACKETS,
    BPP_DSR_TYPES,
    BPP_FSK_PATTERNS,
    BPP_GRQ_REQUESTS,
    BPP_SRQ_TYPES,
    CAL_ENTER_REASON,
    CAL_ENTER_RESPONSE,
    CAL_CAPTURE_OPERATIONS,
    CAL_OP_CODES,
    EPT_REASONS,
    FOD_TYPE_LABELS,
    FSK_BARE_PATTERNS,
    FSK_DEPTH_LABELS,
    FSK_PACKETS,
    MATEDQ_FO_RESULT,
    MPP_GET_PARAMS,
    MPP_GRQ_REQUESTS,
    MPP_SRQ_TYPES,
    MPP_TX_ERR_INFO,
    MSS_ERROR,
    MSS_STATUS,
    MSR_MAIN_MODE,
    MSR_PREF,
    PRMC_VENDORS,
    PTX_POWER_LIMIT_REASON,
    PTX_XID_APP,
    QI22_FSK_PATTERNS,
    REPORT_ID_TYPES,
    PLA_FSK_RESPONSES,
    SRQ_FREQ_SELECTOR,
    SRQ_PCP_PROFILE,
    SRQ_XCE_METHOD,
    srq_type_name,
    RP_MODE_LABELS,
    SADC_REQUESTS,
    SDSR_TYPES,
    get_payload_len,
)

ASK_MSG_SIZE_OVERRIDE: dict[int, int] = {}


def _qi_colors() -> dict[str, str]:
    """解析 tooltip 配色，随浅色/深色主题切换。"""
    t = active_tokens()
    light = get_theme() == 'light'
    return {
        'field': t.TEXT_PRIMARY,
        'hex': t.TEXT_MUTED,
        'border': t.BORDER,
        'title_ask': '#0369A1' if light else '#38BDF8',
        'title_fsk': '#B45309' if light else '#FB923C',
        'byte_ask': '#0369A1' if light else '#38BDF8',
        'byte_fsk': '#B45309' if light else '#FB923C',
        'code': t.FILTER_HIGHLIGHT,
        'ok': t.STATUS_SUCCESS,
        'err': t.STATUS_ERROR,
        'warn': t.STATUS_WARN,
        'neutral': t.TEXT_SECONDARY,
        'muted': t.TEXT_MUTED,
    }


def _s8(val: int) -> int:
    return val - 256 if val > 127 else val


def _s16_be(hi: int, lo: int) -> int:
    val = (hi << 8) | lo
    return val - 65536 if val > 32767 else val


def _u16_be(hi: int, lo: int) -> int:
    return (hi << 8) | lo


def _bits(val: int, hi: int, lo: int) -> int:
    width = hi - lo + 1
    return (val >> lo) & ((1 << width) - 1)


def _hex_bytes(data, limit=16):
    if not data:
        return 'None'
    shown = ' '.join(f'{b:02X}' for b in data[:limit])
    if len(data) > limit:
        shown += f' … (+{len(data) - limit} B)'
    return shown


def _qi_tr(key: str, **kwargs) -> str:
    """Qi parse tooltips always use English (independent of UI language)."""
    return tr_in('en', key, **kwargs)


def _ptmc_vendor(prmc: int) -> str:
    return PRMC_VENDORS.get(prmc, _qi_tr('qi.unknown_vendor', code=prmc))


def _split_payload_checksum(header: int, body: list[int], overrides=None):
    if not body:
        return [], None, 'N/A'
    msg_len = get_payload_len(header) if overrides is None or header not in overrides else overrides[header]
    if len(body) == msg_len:
        return body, None, 'N/A'
    if len(body) >= msg_len + 1:
        payload, cs = body[:msg_len], body[msg_len]
        calc = header
        for b in payload:
            calc ^= b
        ok = calc == cs
        c = _qi_colors()
        status = (
            f"<span style='color:{c['ok']};'>✅ OK</span>"
            if ok
            else f"<span style='color:{c['err']};'>❌ ERR</span>"
        )
        return payload, cs, status
    return body, None, 'N/A'


class _Html:
    @classmethod
    def _c(cls):
        return _qi_colors()

    @classmethod
    def byte(cls, idx, label, val, lines):
        c = cls._c()
        lines.append(
            f"• <span style='color:{c['byte_ask']}'>Byte {idx}:</span> "
            f"0x{val:02X} ({val}) — {label}"
        )

    @classmethod
    def fbyte(cls, idx, label, val, lines):
        c = cls._c()
        lines.append(
            f"• <span style='color:{c['byte_fsk']}'>Byte {idx}:</span> "
            f"0x{val:02X} ({val}) — {label}"
        )

    @classmethod
    def field(cls, text, indent=1):
        pad = '&nbsp;' * (indent * 4)
        return f'{pad}↳ {text}'

    @classmethod
    def join(cls, lines):
        return '<br>'.join(lines)


def _format_get_param(code: int) -> str:
    entry = MPP_GET_PARAMS.get(code)
    if not entry:
        return f'Reserved / undefined (code {code})'
    desc, hdr = entry
    return f'{desc}' + (f' — <b>{hdr}</b>' if hdr else '')


class Qi22Parser:
    """BPP/EPP + MPP ASK·FSK 报文字段解析器（依据 bpp_protocol.h / mpp_protocol.h）。"""

    @staticmethod
    def _insufficient():
        return f'<i>{_qi_tr("qi.insufficient")}</i>'

    @staticmethod
    def _no_payload():
        return f'<i>{_qi_tr("qi.no_payload")}</i>'

    def parse_message(self, line):
        if not line:
            return None
        normalized = re.sub(r'\s+', ' ', line).strip()
        if not normalized:
            return None
        return self._parse_message_cached(normalized + ' ')

    def clear_parse_cache(self) -> None:
        self._parse_message_cached.cache_clear()

    @lru_cache(maxsize=4096)
    def _parse_message_cached(self, line: str):
        if 'ASK ' in line:
            start = line.find('ASK ') + 4
            end = line.find(' F ', start)
            if end != -1:
                return self._decode_packet(line[start:end].strip(), 'ASK')
        if 'FSK ' in line:
            start = line.find('FSK ') + 4
            end = line.find(' F ', start)
            if end == -1:
                end = line.find('(', start)
            hex_part = line[start:end].strip() if end != -1 else line[start:].strip()
            return self._decode_packet(hex_part, 'FSK')
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
            entry = registry.get(header)
            if entry:
                name, desc, _profile = entry
            else:
                name, desc = f'UNK_0x{header:02X}', _qi_tr('qi.unknown_pkt')
            
            if p_type == 'ASK':
                detail = self._decode_ask_payload(header, payload)
            else:
                detail = self._decode_fsk_payload(header, payload)

            c = _qi_colors()
            title_color = c['title_ask'] if p_type == 'ASK' else c['title_fsk']
            dir_text = _qi_tr('qi.dir_ask') if p_type == 'ASK' else _qi_tr('qi.dir_fsk')
            html = (
                f"<div style='min-width: 260px; font-family: Consolas, monospace; "
                f"color: {c['field']};'>"
                f"<b style='color:{title_color}; font-size: 11pt;'>{dir_text}</b>"
                f"<hr style='border:1px solid {c['border']}; margin: 5px 0;'>"
                f"<b>{_qi_tr('qi.header')}</b> <span style='color:{c['code']};'>0x{header:02X}</span> "
                f"[{name}] {desc}<br>"
                f"<b>{_qi_tr('qi.payload', n=len(payload))}</b> "
                f"<span style='color:{c['hex']}'>{_hex_bytes(payload, 24)}</span><br>"
            )
            if cs is not None:
                html += f"<b>{_qi_tr('qi.xor')}</b> 0x{cs:02X} ({cs_st})<br>"
            html += (
                f"<hr style='border:1px dashed {c['border']}; margin: 5px 0;'>"
                f"<b>{_qi_tr('qi.fields')}</b><br>"
                f"<div style='color:{c['field']}; padding-top: 5px; line-height: 1.45;'>{detail}</div>"
                f"</div>"
            )
            return html
        except Exception as exc:
            return _qi_tr('qi.parse_error', error=exc)

    # ------------------------------------------------------------------
    # ASK 载荷解析 (PRx → PTx)
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
            0x09: self._ask_nego,
            0x13: self._ask_msr,
            0x15: self._ask_dsr,
            0x18: self._ask_cloak,
            0x19: self._ask_xce,
            0x20: self._ask_srq,
            0x22: self._ask_fod,
            0x23: self._ask_cal_op,
            0x25: self._ask_adc,
            0x28: self._ask_get,
            0x29: self._ask_eds,
            0x2C: self._ask_cal_enter,
            0x2D: self._ask_cal_exit,
            0x31: self._ask_rp,
            0x51: self._ask_cfg,
            0x54: self._ask_wpid,
            0x55: self._ask_wpid,
            0x71: self._ask_id,
            0x81: self._ask_xid,
            0x84: self._ask_ecap,
            0x38: self._ask_sdsr,
            0x48: self._ask_sadc,
            0x50: self._ask_kest_coeff,
            0x58: self._ask_report_pla,
            0x78: self._ask_plap,
            0x88: self._ask_pla2,
            0x90: self._ask_plap2,
            0x96: self._ask_cal_capture,
            0xA8: self._ask_matedq_coeff,
        }
        if header in (0x16, 0x17, 0x26, 0x27, 0x36, 0x37, 0x46, 0x47,
                      0x56, 0x57, 0x66, 0x67, 0x76, 0x77, 0x98, 0x99):
            return self._ask_adt(payload)
        if header in (0x1A, 0x1B, 0x2A, 0x2B):
            return self._generic_prop(payload)
        decoder = decoders.get(header)
        if decoder:
            return decoder(payload)
        return self._generic_raw(payload)

    def _ask_ss(self, p):
        if len(p) < 1:
            return self._insufficient()
        lines = []
        _Html.byte(0, 'signal_strength', p[0], lines)
        lines.append(_Html.field(f'Signal strength: <b>{p[0]}</b> / 255 ({p[0] / 255 * 100:.1f}%)'))
        lines.append(_Html.field('Formula: (U / U_max) × 256'))
        return _Html.join(lines)

    def _ask_ept(self, p):
        if len(p) < 1:
            return self._insufficient()
        reason = EPT_REASONS.get(p[0], f'Reserved code 0x{p[0]:02X}')
        c = _qi_colors()
        color = c['ok'] if p[0] == 0x01 else (c['err'] if p[0] in (0x02, 0x03, 0x04, 0x05, 0x06, 0x0B) else c['neutral'])
        detail = f'End reason: <b style="color:{color}">{reason}</b>'
        return (
            f"• <span style='color:{c['byte_ask']}'>Byte 0:</span> reason_code = 0x{p[0]:02X}<br>"
            f"{_Html.field(detail)}"
        )

    def _ask_ce(self, p):
        if len(p) < 1:
            return self._insufficient()
        c = _qi_colors()
        ce = _s8(p[0])
        color = c['ok'] if ce < 0 else c['err']
        lines = []
        _Html.byte(0, 'control_error (int8)', p[0], lines)
        lines.append(_Html.field(f'Control error: <b style="color:{color}">{ce}</b>'))
        lines.append(_Html.field('<i>Positive → increase power; negative → decrease power</i>'))
        return _Html.join(lines)

    def _ask_rp8(self, p):
        if len(p) < 1:
            return self._insufficient()
        lines = []
        _Html.byte(0, 'received_power', p[0], lines)
        lines.append(_Html.field(f'Received power ratio: <b>{p[0]}</b> / 128 = {p[0] / 128 * 100:.1f}% MaxPower'))
        return _Html.join(lines)

    def _ask_chs(self, p):
        if len(p) < 1:
            return self._insufficient()
        c = _qi_colors()
        if p[0] == 0xFF:
            detail = 'Status not available (0xFF)'
        elif p[0] <= 100:
            detail = f'Battery level: <b style="color:{c["ok"]}">{p[0]} %</b>'
        else:
            detail = f'Reserved value 0x{p[0]:02X}'
        return (
            f"• <span style='color:{c['byte_ask']}'>Byte 0:</span> charge_status = 0x{p[0]:02X}<br>"
            f"{_Html.field(detail)}"
        )

    def _ask_pch(self, p):
        if len(p) < 1:
            return self._insufficient()
        c = _qi_colors()
        valid = 5 <= p[0] <= 100
        color = c['ok'] if valid else c['warn']
        detail = f'Hold-off: <b style="color:{color}">{p[0]} ms</b> (valid range 5–100 ms)'
        return (
            f"• <span style='color:{c['byte_ask']}'>Byte 0:</span> hold_off_time = 0x{p[0]:02X}<br>"
            f"{_Html.field(detail)}"
        )

    def _ask_grq(self, p):
        if len(p) < 1:
            return self._insufficient()
        req_bpp = BPP_GRQ_REQUESTS.get(p[0])
        req_mpp = MPP_GRQ_REQUESTS.get(p[0])
        if req_bpp and req_mpp:
            req = f'{req_bpp} / {req_mpp}'
        else:
            req = req_bpp or req_mpp or f'Request header 0x{p[0]:02X}'
        c = _qi_colors()
        return (
            f"• <span style='color:{c['byte_ask']}'>Byte 0:</span> req_header = 0x{p[0]:02X}<br>"
            f"{_Html.field(f'Request PTx response: <b>{req}</b>')}"
        )

    def _ask_nego(self, p):
        if not p:
            return f'<i>{_qi_tr("qi.reneg_no_payload")}</i>'
        c = _qi_colors()
        ok = p[0] == 0x00
        warn = '' if ok else f' — <span style="color:{c["err"]}">must be 0x00</span>'
        return (
            f"• <span style='color:{c['byte_ask']}'>Byte 0:</span> reserved = 0x{p[0]:02X}<br>"
            f"{_Html.field('Must be 0x00' + warn)}"
        )

    def _ask_msr(self, p):
        if len(p) < 1:
            return self._insufficient()
        pref = (p[0] >> 6) & 0x03
        main_mode = (p[0] >> 3) & 0x03
        aux = p[0] & 0x01
        lines = []
        _Html.byte(0, 'mode_cfg', p[0], lines)
        c = _qi_colors()
        if p[0] & 0x20:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">Reserved [b5]: must be 0</span>'
            ))
        if p[0] & 0x06:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">'
                f'Reserved [b2-b1]: must be 0 (current 0x{((p[0] >> 1) & 0x03):X})</span>'
            ))
        lines.append(_Html.field(f'Preference [b7-b6]: <b>{MSR_PREF.get(pref, pref)}</b>'))
        lines.append(_Html.field(f'Main mode [b4-b3]: <b>{MSR_MAIN_MODE.get(main_mode, main_mode)}</b>'))
        lines.append(_Html.field(f'Auxiliary mode [b0]: <b>{"Selected" if aux else "Not selected"}</b>'))
        return _Html.join(lines)

    def _ask_dsr(self, p):
        if len(p) < 1:
            return self._insufficient()
        c = _qi_colors()
        name, desc = BPP_DSR_TYPES.get(p[0], (f'0x{p[0]:02X}', 'Reserved'))
        color = c['ok'] if p[0] == 0x00 else c['neutral']
        lines = ['• bpp_rx_dsr_t — Data Stream Response']
        _Html.byte(0, 'response_code', p[0], lines)
        lines.append(_Html.field(f'Response: <b style="color:{color}">{name}</b> — {desc}'))
        return _Html.join(lines)

    def _ask_cloak(self, p):
        if len(p) < 1:
            return self._insufficient()
        c = _qi_colors()
        ok = p[0] == 0x00
        warn = '' if ok else f' — <span style="color:{c["err"]}">must be 0x00</span>'
        return (
            f"• <span style='color:{c['byte_ask']}'>Byte 0:</span> reserved = 0x{p[0]:02X}<br>"
            f"{_Html.field('Trigger Cloak Phase' + warn)}"
        )

    def _ask_xce(self, p):
        if len(p) < 1:
            return self._insufficient()
        c = _qi_colors()
        ce = _s8(p[0])
        color = c['ok'] if ce < 0 else c['err']
        lines = []
        _Html.byte(0, 'extended_ce (int8)', p[0], lines)
        lines.append(_Html.field(f'Extended control error: <b style="color:{color}">{ce}</b> (value / 100)'))
        return _Html.join(lines)

    def _ask_srq(self, p):
        if len(p) < 1:
            return self._insufficient()
        code = p[0]
        lines = ['• Specific Request — SRQ (0x20)']
        _Html.byte(0, 'request_code', code, lines)
        lines.append(_Html.field(f'Type: <b>{srq_type_name(code)}</b>'))
        if len(p) < 2:
            return _Html.join(lines)
        _Html.byte(1, 'parameter', p[1], lines)
        lines.extend(self._decode_srq_parameter(code, p[1]))
        return _Html.join(lines)

    def _decode_srq_parameter(self, code, param):
        lines = []
        if code == 0x00:
            lines.append(_Html.field('End negotiation — no additional parameter'))
        elif code == 0x01:
            lines.append(_Html.field(f'Guaranteed Load Power parameter: <b>{param}</b>'))
        elif code == 0x03:
            lines.append(_Html.field(f'FSK configuration parameter: <b>0x{param:02X}</b>'))
        elif code == 0x05:
            lines.append(_Html.field(f'Re-ping delay parameter: <b>{param}</b>'))
        elif code == 0xA1:
            method = param & 0x03
            if param & 0xFC:
                lines.append(_Html.field(f'Reserved [b7-b2]: must be 0 (current 0x{(param >> 2):02X})'))
            lines.append(_Html.field(
                f'Control Error Calculation Method [b1-b0]: '
                f'<b>{SRQ_XCE_METHOD.get(method, f"Reserved ({method})")}</b>'
            ))
        elif code == 0xA7:
            major = (param >> 4) & 0x0F
            minor = param & 0x0F
            lines.append(_Html.field(f'Major Version [b7-b4]: <b>{major}</b>'))
            lines.append(_Html.field(f'Minor Version [b3-b0]: <b>{minor}</b>'))
            lines.append(_Html.field(f'Version: <b>{major}.{minor}</b> (MPP should be 2.2)'))
        elif code == 0xA9:
            g_scale = (param >> 4) & 0x0F
            g_target = param & 0x0F
            g_val = g_target / 20.0
            lines.append(_Html.field(f'G_SCALE [b7-b4]: <b>{g_scale}</b>'))
            lines.append(_Html.field(
                f'G_TARGET [b3-b0]: <b>{g_target}</b> → g_target = <b>{g_val:.2f}</b> (×0.05)'
            ))
            if g_target == 0:
                lines.append(_Html.field('<span style="color:{0}">PTx should NAK when G_TARGET=0</span>'.format(
                    _qi_colors()['err']
                )))
        elif code == 0xF0:
            if param & 0xFC:
                lines.append(_Html.field(f'Reserved [b7-b2]: must be 0 (current 0x{(param >> 2):02X})'))
            freq = param & 0x03
            lines.append(_Html.field(
                f'Frequency Selector [b1-b0]: <b>{SRQ_FREQ_SELECTOR.get(freq, freq)}</b>'
            ))
            if freq != 1:
                lines.append(_Html.field('<i>Only 360 kHz (1) allowed during negotiation; PTx should ND for other values</i>'))
        elif code == 0xF3:
            lines.append(_Html.field(
                f'Load Power: <b>{param * 100} mW</b> ({param * 0.1:.1f} W, ×100 mW)'
            ))
        elif code == 0xF5:
            lines.append(_Html.field(
                f'Cloak Ping Delay [low 8 bits]: <b>{param}</b> '
                f'(forms 10-bit with SRQ/cloakh 0xF7 high 2 bits, ×100 ms)'
            ))
            if param == 0:
                lines.append(_Html.field('<i>Both low/high bytes zero is invalid; recommend t_cloak ≥ 500 ms</i>'))
        elif code == 0xF6:
            profile = param & 0x01
            if param & 0xFE:
                lines.append(_Html.field(f'Reserved [b7-b1]: must be 0 (current 0x{(param >> 1):02X})'))
            lines.append(_Html.field(
                f'Profile [b0]: <b>{SRQ_PCP_PROFILE.get(profile, profile)}</b>'
            ))
        elif code == 0xF7:
            high = param & 0x03
            if param & 0xFC:
                lines.append(_Html.field(f'Reserved [b7-b2]: must be 0 (current 0x{(param >> 2):02X})'))
            lines.append(_Html.field(
                f'Cloak Ping Delay [high 2 bits]: <b>{high}</b> '
                f'(forms 10-bit with SRQ/cloakl 0xF5 low 8 bits, ×100 ms)'
            ))
        elif code == 0xF8:
            if param & 0xF0:
                lines.append(_Html.field(f'Reserved [b7-b4]: must be 0 (current 0x{(param >> 4):02X})'))
            detect = param & 0x0F
            if detect == 0:
                lines.append(_Html.field('Cloak Detect Ping Delay: <b>Disabled</b> (value is 0)'))
            else:
                delay_ms = detect * 100
                lines.append(_Html.field(
                    f'Cloak Detect Ping Delay [b3-b0]: <b>{detect}</b> → '
                    f'<b>{delay_ms} ms</b> (×100 ms)'
                ))
                if delay_ms < 500:
                    lines.append(_Html.field('<i>Recommend t_cloakdetect ≥ 500 ms (APP PTx active alignment)</i>'))
        elif 0xE0 <= code <= 0xEF:
            lines.append(_Html.field(
                f'Implementation Specific: <b>0x{param:02X}</b> ({param})'
            ))
            lines.append(_Html.field('<i>Proprietary parameter — not MPP spec managed</i>'))
        else:
            lines.append(_Html.field(f'Parameter value: <b>0x{param:02X}</b> ({param})'))
        return lines

    def _ask_fod(self, p):
        if len(p) < 2:
            return f'<i>FOD requires 2 bytes, got {len(p)} B</i>' + (f'<br>{self._generic_raw(p)}' if p else '')
        f_type = p[0] & 0x01
        lines = []
        _Html.byte(0, 'type_info', p[0], lines)
        lines.append(_Html.field(f'FOD type [b0]: <b>{FOD_TYPE_LABELS.get(f_type, f_type)}</b>'))
        _Html.byte(1, 'support_data', p[1], lines)
        if f_type == 0:
            lines.append(_Html.field(f'Reference Q: <b>{p[1]}</b>'))
        else:
            lines.append(_Html.field(f'Reference frequency: <b>{p[1]}</b>'))
        return _Html.join(lines)

    def _ask_cal_op(self, p):
        if len(p) < 1:
            return self._insufficient()
        op = CAL_OP_CODES.get(p[0], f'0x{p[0]:02X}')
        lines = []
        _Html.byte(0, 'operation', p[0], lines)
        lines.append(_Html.field(f'Calibration operation: <b>{op}</b>'))
        if len(p) >= 2:
            _Html.byte(1, 'parameter', p[1], lines)
        return _Html.join(lines)

    def _ask_adc(self, p):
        if len(p) < 1:
            return self._insufficient()
        lines = []
        _Html.byte(0, 'request', p[0], lines)
        lines.append(_Html.field(f'Request action: <b>0x{p[0]:02X}</b> (e.g. 0x10=Auth, 0x28=Reset)'))
        if len(p) >= 2:
            _Html.byte(1, 'parameter', p[1], lines)
        return _Html.join(lines)

    def _ask_get(self, p):
        if len(p) < 2:
            return self._insufficient()
        lines = ['• mpp_rx_get_t — Get Request (Table 57)']
        _Html.byte(0, 'rsvd', p[0], lines)
        _Html.byte(1, 'parameter', p[1], lines)
        lines.append(_Html.field(f'Request type: {_format_get_param(p[1])}'))
        return _Html.join(lines)

    def _ask_eds(self, p):
        if len(p) < 2:
            return self._insufficient()
        mask = _u16_be(p[0], p[1])
        streams = [i for i in range(16) if mask & (1 << i)]
        lines = []
        _Html.byte(0, 'streams_bitmask MSB', p[0], lines)
        _Html.byte(1, 'streams_bitmask LSB', p[1], lines)
        lines.append(_Html.field(f'Data stream mask: <b>0x{mask:04X}</b>'))
        if streams:
            lines.append(_Html.field(f'Enabled streams: <b>{", ".join(map(str, streams))}</b>'))
        else:
            lines.append(_Html.field('No enabled data streams'))
        return _Html.join(lines)

    def _ask_cal_enter(self, p):
        lines = [f'• mpp_rx_cal_enter_t ({len(p)} B)']
        for i, b in enumerate(p):
            _Html.byte(i, 'reserved_payload', b, lines)
        return _Html.join(lines)

    def _ask_cal_exit(self, p):
        if len(p) < 2:
            return self._insufficient()
        clear = p[0] & 0x01
        lines = []
        _Html.byte(0, 'clear_flag', p[0], lines)
        lines.append(_Html.field(f'Clear [b0]: <b>{"Clear calibration points" if clear else "Keep calibration points"}</b>'))
        _Html.byte(1, 'reserved', p[1], lines)
        return _Html.join(lines)

    def _ask_rp(self, p):
        if len(p) < 3:
            return f'<i>bpp_rx_rp_t requires 3 bytes, got {len(p)} B</i>'
        mode = p[0] & 0x07
        rx_power = _u16_be(p[1], p[2])
        lines = []
        _Html.byte(0, 'mode_info', p[0], lines)
        lines.append(_Html.field(f'Measurement mode [b2-b0]: <b>{RP_MODE_LABELS.get(mode, mode)}</b>'))
        _Html.byte(1, 'rx_power MSB', p[1], lines)
        _Html.byte(2, 'rx_power LSB', p[2], lines)
        lines.append(_Html.field(f'Estimated received power: <b>{rx_power} mW</b>'))
        return _Html.join(lines)

    def _ask_cfg(self, p):
        exp_len = get_payload_len(0x51)
        if len(p) < exp_len:
            return f'<i>bpp_rx_cfg_t requires {exp_len} bytes, got {len(p)} B</i>' + (f'<br>{self._generic_raw(p)}' if p else '')
        ref_pwr = p[0] & 0x3F
        ai = (p[2] >> 6) & 1
        ob = (p[2] >> 4) & 1
        count = p[2] & 0x07
        win_size = (p[3] >> 3) & 0x1F
        win_offset = p[3] & 0x07
        neg = (p[4] >> 7) & 1
        polarity = (p[4] >> 6) & 1
        depth = (p[4] >> 4) & 0x03
        buf_size = (p[4] >> 1) & 0x07
        dup = p[4] & 0x01
        lines = []
        _Html.byte(0, 'ref_power', p[0], lines)
        lines.append(_Html.field(f'Reference Power [b5-b0]: <b>{ref_pwr}</b> (≈ {ref_pwr * 0.5:.1f} W)'))
        _Html.byte(1, 'rsvd1', p[1], lines)
        _Html.byte(2, 'features', p[2], lines)
        lines.append(_Html.field(f'AI [b6]: <b>{"Supported" if ai else "No"}</b>'))
        lines.append(_Html.field(f'OB [b4]: <b>{"Supported" if ob else "No"}</b>'))
        lines.append(_Html.field(f'Optional packet count [b2-b0]: <b>{count}</b>'))
        _Html.byte(3, 'window_cfg', p[3], lines)
        lines.append(_Html.field(f'Window Size [b7-b3]: <b>{win_size}</b>'))
        lines.append(_Html.field(f'Window Offset [b2-b0]: <b>{win_offset}</b>'))
        _Html.byte(4, 'fsk_cfg', p[4], lines)
        lines.append(_Html.field(f'Neg/EPP [b7]: <b>{"EPP" if neg else "BPP"}</b>'))
        lines.append(_Html.field(f'FSK Polarity [b6]: <b>{"Negative" if polarity else "Positive"}</b>'))
        lines.append(_Html.field(f'FSK Depth [b5-b4]: <b>{FSK_DEPTH_LABELS.get(depth, depth)}</b>'))
        lines.append(_Html.field(f'Buffer Size [b3-b1]: <b>{buf_size}</b>'))
        lines.append(_Html.field(f'Dup [b0]: <b>{"Supported" if dup else "No"}</b>'))
        return _Html.join(lines)

    def _ask_wpid(self, p):
        exp_len = get_payload_len(0x54)
        if len(p) < exp_len:
            return f'<i>bpp_rx_wpid_t requires {exp_len} bytes, got {len(p)} B</i>'
        seg_len = exp_len - 2
        crc = _u16_be(p[seg_len], p[seg_len + 1]) if len(p) >= exp_len else 0
        lines = [f'• bpp_rx_wpid_t — WPID segment ({seg_len} B + CRC)']
        for i in range(seg_len):
            _Html.byte(i, f'wpid_segment[{i}]', p[i], lines)
        if len(p) >= exp_len:
            _Html.byte(seg_len, 'crc MSB', p[seg_len], lines)
            _Html.byte(seg_len + 1, 'crc LSB', p[seg_len + 1], lines)
            lines.append(_Html.field(f'CRC16 (BE): <b>0x{crc:04X}</b>'))
        return _Html.join(lines)

    def _ask_id(self, p):
        exp_len = get_payload_len(0x71)
        if len(p) < exp_len:
            return f'<i>bpp_rx_id_t requires {exp_len} bytes, got {len(p)} B</i>' + (f'<br>{self._generic_raw(p)}' if p else '')
        major = p[0] >> 4
        minor = p[0] & 0x0F
        mfg_code = _u16_be(p[1], p[2])
        ext = (p[3] >> 7) & 1
        basic_id = ((p[3] & 0x7F) << 24) | (p[4] << 16) | (p[5] << 8) | p[6]
        lines = []
        _Html.byte(0, 'version', p[0], lines)
        lines.append(_Html.field(f'Qi version: <b>{major}.{minor}</b>'))
        _Html.byte(1, 'mfg_code MSB', p[1], lines)
        _Html.byte(2, 'mfg_code LSB', p[2], lines)
        lines.append(_Html.field(f'Manufacturer code: <b>0x{mfg_code:04X}</b> ({_ptmc_vendor(mfg_code)})'))
        _Html.byte(3, 'basic_dev_id (MSB)', p[3], lines)
        lines.append(_Html.field(f'Ext [b31]: <b>{"Has XID" if ext else "No XID"}</b>'))
        for i in range(4, 7):
            _Html.byte(i, 'basic_dev_id', p[i], lines)
        lines.append(_Html.field(f'Basic Device ID: <b>0x{basic_id:07X}</b>'))
        return _Html.join(lines)

    def _ask_xid(self, p):
        if len(p) >= 1 and p[0] == 0xFE:
            return self._ask_mpp_xid(p)
        return self._ask_bpp_xid(p)

    def _ask_bpp_xid(self, p):
        exp_len = get_payload_len(0x81)
        if len(p) < exp_len:
            return f'<i>bpp_rx_xid_t requires {exp_len} bytes, got {len(p)} B</i>' + (f'<br>{self._generic_raw(p)}' if p else '')
        ext_id = int.from_bytes(p[:exp_len], 'big')
        lines = [f'• bpp_rx_xid_t — Extended Identification ({exp_len} B)']
        for i, b in enumerate(p[:exp_len]):
            _Html.byte(i, 'ext_device_id', b, lines)
        lines.append(_Html.field(f'Extended Device ID: <b>0x{ext_id:0{exp_len * 2}X}</b>'))
        if p[0] == 0xFE:
            lines.append(_Html.field(f'<span style="color:{_qi_colors()["err"]}">B0=0xFE should be MPP-XID</span>'))
        return _Html.join(lines)

    def _ask_mpp_xid(self, p):
        exp_len = get_payload_len(0x81)
        if len(p) < exp_len:
            return f'<i>mpp_rx_xid_t requires {exp_len} bytes, got {len(p)} B</i>'
        restricted = (p[1] >> 7) & 1
        mfg_rsvd_b1 = p[1] & 0x7F
        vrect = p[3]
        alpha0 = _s8(p[4])
        alpha1 = _s8(p[5])
        alpha_k = _s8(p[6])
        lines = [f'• mpp_rx_xid_t — MPP Extended Identification ({exp_len} B)']
        _Html.byte(0, 'fixed_fe', p[0], lines)
        lines.append(_Html.field('MPP Selector: <b>0xFE</b>'))
        _Html.byte(1, 'restricted_mfg', p[1], lines)
        lines.append(_Html.field(
            f'Restricted [b7]: <b>{"Restricted mode" if restricted else "Full capability"}</b>'
        ))
        if mfg_rsvd_b1:
            lines.append(_Html.field(f'Mfg Reserved [b6-b0]: <b>0x{mfg_rsvd_b1:02X}</b>'))
        _Html.byte(2, 'mfg_rsvd', p[2], lines)
        _Html.byte(3, 'v_rect', p[3], lines)
        lines.append(_Html.field(f'VRECT: <b>{vrect * 20} mV</b> ({vrect * 0.02:.2f} V)'))
        _Html.byte(4, 'alpha_0r', p[4], lines)
        lines.append(_Html.field(f'Alpha_0r: <b>{alpha0 / 100:.2f}</b>'))
        _Html.byte(5, 'alpha_1r', p[5], lines)
        lines.append(_Html.field(f'Alpha_1r: <b>{alpha1 / 100:.2f}</b>'))
        _Html.byte(6, 'alpha_k_thr', p[6], lines)
        lines.append(_Html.field(f'Alpha_K threshold: <b>{alpha_k}</b> (typically = 100)'))
        if len(p) >= 8:
            _Html.byte(7, 'mfg_rsvd2', p[7], lines)
        return _Html.join(lines)

    def _ask_ecap(self, p):
        exp_len = get_payload_len(0x84)
        if len(p) < exp_len:
            return f'<i>mpp_rx_ecap_t requires {exp_len} bytes, got {len(p)} B</i>' + (f'<br>{self._generic_raw(p)}' if p else '')
        min_pwr = p[1] & 0x0F
        stream_cnt = (p[3] >> 5) & 0x07
        buf_size = (p[3] >> 2) & 0x07
        c = _qi_colors()
        lines = [f'• mpp_rx_ecap_t ({exp_len} B)']
        _Html.byte(0, 'rsvd', p[0], lines)
        _Html.byte(1, 'min_charge_pwr', p[1], lines)
        if p[1] & 0xF0:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">'
                f'Reserved [b7-b4]: must be 0 (current 0x{(p[1] >> 4):X})</span>'
            ))
        lines.append(_Html.field(f'Minimum charge power [b3-b0]: <b>{min_pwr}</b>'))
        _Html.byte(3, 'data_streams_info', p[3], lines)
        lines.append(_Html.field(f'Concurrent stream count [b7-b5]: <b>{stream_cnt}</b>'))
        lines.append(_Html.field(f'Data stream buffer [b4-b2]: <b>{buf_size}</b>'))
        if p[3] & 0x03:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">'
                f'Reserved [b1-b0]: must be 0 (current 0x{p[3] & 0x03:X})</span>'
            ))
        if len(p) > 4:
            lines.append(_Html.field(f'Manufacturer reserved: {_hex_bytes(p[4:])}'))
        return _Html.join(lines)

    def _ask_sdsr(self, p):
        if len(p) < 3:
            return f'<i>mpp_rx_sdsr_t requires 3 bytes, got {len(p)} B</i>'
        stream = p[1] & 0x0F
        resp_type = p[2] & 0x0F
        c = _qi_colors()
        lines = ['• mpp_rx_sdsr_t — Simultaneous Data Stream Response']
        _Html.byte(0, 'selector_rsvd', p[0], lines)
        _Html.byte(1, 'stream_number', p[1], lines)
        if p[1] & 0xF0:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">'
                f'Reserved [b7-b4]: must be 0 (current 0x{(p[1] >> 4):X})</span>'
            ))
        lines.append(_Html.field(f'Stream Number [b3-b0]: <b>{stream}</b>'))
        _Html.byte(2, 'type_cmd', p[2], lines)
        if p[2] & 0xF0:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">'
                f'Reserved [b7-b4]: must be 0 (current 0x{(p[2] >> 4):X})</span>'
            ))
        lines.append(_Html.field(f'Type [b3-b0]: <b>{SDSR_TYPES.get(resp_type, resp_type)}</b>'))
        return _Html.join(lines)

    def _ask_sadc(self, p):
        if len(p) < 4:
            return f'<i>mpp_rx_sadc_t requires 4 bytes, got {len(p)} B</i>'
        req = p[0] & 0x0F
        stream = p[1] & 0x0F
        param = _u16_be(p[2], p[3])
        c = _qi_colors()
        lines = ['• mpp_rx_sadc_t — Simultaneous Auxiliary Data Control']
        _Html.byte(0, 'request', p[0], lines)
        if p[0] & 0xF0:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">'
                f'Reserved [b7-b4]: must be 0 (current 0x{(p[0] >> 4):X})</span>'
            ))
        lines.append(_Html.field(f'Request [b3-b0]: <b>{SADC_REQUESTS.get(req, f"0x{req:X}")}</b>'))
        _Html.byte(1, 'stream_number', p[1], lines)
        if p[1] & 0xF0:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">'
                f'Reserved [b7-b4]: must be 0 (current 0x{(p[1] >> 4):X})</span>'
            ))
        lines.append(_Html.field(f'Stream Number [b3-b0]: <b>{stream}</b>'))
        _Html.byte(2, 'parameter MSB', p[2], lines)
        _Html.byte(3, 'parameter LSB', p[3], lines)
        lines.append(_Html.field(f'Parameter (BE): <b>0x{param:04X}</b> ({param})'))
        return _Html.join(lines)

    def _ask_kest_coeff(self, p):
        if len(p) < 4:
            return f'<i>mpp_rx_kest_coeff_t requires ≥4 bytes, got {len(p)} B</i>'
        selector = p[0] & 0x01
        alpha0 = _s8(p[1])
        alpha1 = _s8(p[2])
        lines = ['• mpp_rx_kest_coeff_t — K-est Coefficients']
        _Html.byte(0, 'selector', p[0], lines)
        if p[0] & 0xFE:
            lines.append(_Html.field(
                f'<span style="color:{_qi_colors()["warn"]}">'
                f'Reserved [b7-b1]: must be 0 (current 0x{(p[0] >> 1):02X})</span>'
            ))
        lines.append(_Html.field(f'Selector [b0]: <b>{"128kHz HPM" if selector == 0 else selector}</b>'))
        _Html.byte(1, 'alpha_0r', p[1], lines)
        lines.append(_Html.field(f'Alpha_0r: <b>{alpha0 / 100:.2f}</b>'))
        _Html.byte(2, 'alpha_1r', p[2], lines)
        lines.append(_Html.field(f'Alpha_1r: <b>{alpha1 / 100:.2f}</b>'))
        return _Html.join(lines)

    def _ask_report_pla(self, p):
        if len(p) < 5:
            return f'<i>0x58 Report/PLA requires 5 bytes, got {len(p)} B</i>' + (
                f'<br>{self._generic_raw(p)}' if p else ''
            )
        selector = (p[0] >> 5) & 0x07
        if selector == 0:
            return self._ask_report_58(p)
        if selector == 1:
            return self._ask_pla_58(p)
        lines = ['• 0x58 Report/PLA — Unrecognized selector']
        _Html.byte(0, 'B0', p[0], lines)
        lines.append(_Html.field(f'Selector [b7-b5]: <b>{selector}</b> (reserved)'))
        lines.append(_Html.field(f'Data: {_hex_bytes(p[1:])}'))
        return _Html.join(lines)

    def _ask_report_58(self, p):
        """0x58:0 — Report (Figure 122/123, Table 65)."""
        report_id = p[0] & 0x03
        lines = ['• Report — PRx Report (0x58:0)']
        _Html.byte(0, 'B0 selector/report_id', p[0], lines)
        lines.append(_Html.field(f'Selector [b7-b5]: <b>0</b>'))
        rsvd_mid = (p[0] >> 2) & 0x07
        if rsvd_mid:
            lines.append(_Html.field(
                f'<span style="color:{_qi_colors()["warn"]}">'
                f'Reserved [b4-b2]: must be 0 (current {rsvd_mid})</span>'
            ))
        lines.append(_Html.field(
            f'Report ID [b1-b0]: <b>{REPORT_ID_TYPES.get(report_id, f"Reserved ({report_id})")}</b>'
        ))
        if report_id == 2:
            rand_id = ((p[1] & 0x3F) << 14) | (p[2] << 6) | ((p[3] >> 2) & 0x3F)
            _Html.byte(1, 'B1 random_id [b5-b0]', p[1], lines)
            _Html.byte(2, 'B2 random_id', p[2], lines)
            _Html.byte(3, 'B3 random_id [b7-b2]', p[3], lines)
            lines.append(_Html.field(
                f'Random Identifier [20-bit]: <b>0x{rand_id:05X}</b> ({rand_id})'
            ))
            if p[3] & 0x03:
                lines.append(_Html.field(f'Reserved [B3 b1-b0]: {p[3] & 0x03}'))
            _Html.byte(4, 'B4 mfg_reserved', p[4], lines)
            lines.append(_Html.field(
                '<i>Random ID must match value reported in ID packet (Random Device Identifier Policy)</i>'
            ))
        else:
            lines.append(_Html.field('Report Data [B1-B4]: Template Dependent'))
            for i in range(1, 5):
                _Html.byte(i, 'report_data', p[i], lines)
        lines.append(_Html.field('<i>PTx FSK response: ACK only (Table 66)</i>'))
        return _Html.join(lines)

    def _ask_pla_58(self, p):
        """0x58:1 — Power Loss Accounting / PLA (Figure 124, Table 67)."""
        rx_pwr = _u16_be(p[1], p[2])
        p_rect = _u16_be(p[3], p[4])
        lines = ['• PLA — Power Loss Accounting (0x58:1)']
        _Html.byte(0, 'B0 selector', p[0], lines)
        lines.append(_Html.field(f'Selector [b7-b5]: <b>1</b>'))
        if p[0] & 0x1F:
            lines.append(_Html.field(
                f'<span style="color:{_qi_colors()["warn"]}">'
                f'Reserved [b4-b0]: must be 0 (current 0x{p[0] & 0x1F:02X})</span>'
            ))
        _Html.byte(1, 'received_power MSB', p[1], lines)
        _Html.byte(2, 'received_power LSB', p[2], lines)
        lines.append(_Html.field(f'Received Power: <b>{rx_pwr} mW</b> ({rx_pwr / 1000:.3f} W)'))
        _Html.byte(3, 'p_rect MSB', p[3], lines)
        _Html.byte(4, 'p_rect LSB', p[4], lines)
        lines.append(_Html.field(f'P_RECT: <b>{p_rect} mW</b> ({p_rect / 1000:.3f} W)'))
        lines.append(_Html.field('<i>PTx FSK responses (Table 67):</i>'))
        for key, desc in PLA_FSK_RESPONSES.items():
            lines.append(_Html.field(f'{key}: {desc}', indent=2))
        return _Html.join(lines)

    def _ask_plap(self, p):
        """0x78 — Power Loss Accounting Parameters / PLAP (Figure 125)."""
        if len(p) < 7:
            return f'<i>mpp_rx_plap_t requires 7 bytes, got {len(p)} B</i>'
        alpha_fm = _s16_be(p[1], p[2])
        alpha_fm_dc = _s16_be(p[3], p[4])
        g_coil_tx = _s16_be(p[5], p[6])
        lines = ['• PLAP — Power Loss Accounting Parameters (0x78)']
        _Html.byte(0, 'B0 Reserved', p[0], lines)
        if p[0] != 0:
            lines.append(_Html.field(
                f'<span style="color:{_qi_colors()["warn"]}">Reserved must be 0</span>'
            ))
        _Html.byte(1, 'B1 Alpha_FM MSB', p[1], lines)
        _Html.byte(2, 'B2 Alpha_FM LSB', p[2], lines)
        lines.append(_Html.field(
            f"α_FM [int16 BE two's complement]: <b>{alpha_fm}</b> (0x{alpha_fm & 0xFFFF:04X})"
        ))
        lines.append(_Html.field(
            f'→ <b>{alpha_fm * 0.5:g} mΩ</b> (field value × 0.5)'
        ))
        _Html.byte(3, 'B3 Alpha_FM_DC MSB', p[3], lines)
        _Html.byte(4, 'B4 Alpha_FM_DC LSB', p[4], lines)
        lines.append(_Html.field(
            f"α_FM,DC [int16 BE two's complement]: <b>{alpha_fm_dc}</b> (0x{alpha_fm_dc & 0xFFFF:04X})"
        ))
        lines.append(_Html.field(
            f'→ <b>{alpha_fm_dc * 0.5:g} mW</b> (field value × 0.5)'
        ))
        _Html.byte(5, 'B5 g_coil_TX MSB', p[5], lines)
        _Html.byte(6, 'B6 g_coil_TX LSB', p[6], lines)
        lines.append(_Html.field(
            f"g_coil,TX [int16 BE two's complement]: <b>{g_coil_tx}</b> (0x{g_coil_tx & 0xFFFF:04X})"
        ))
        lines.append(_Html.field(
            f'→ <b>{g_coil_tx * 0.0001:g}</b> (field value × 0.0001)'
        ))
        lines.append(_Html.field(
            "<i>All three parameters are signed two's complement for PLA formula (MPP System Specifications §6.3.2.3)</i>"
        ))
        return _Html.join(lines)

    def _ask_pla2(self, p):
        if len(p) < 9:
            return f'<i>mpp_rx_pla2_t requires 9 bytes, got {len(p)} B</i>'
        p_rx = _u16_be(p[1], p[2])
        p_rect = _u16_be(p[3], p[4])
        v_rect = _u16_be(p[5], p[6])
        i_rect = _u16_be(p[7], p[8])
        lines = ['• mpp_rx_pla2_t — Power Loss Accounting 2']
        lines.append(_Html.field(f'P_received: <b>{p_rx} mW</b>'))
        lines.append(_Html.field(f'P_rect: <b>{p_rect} mW</b>'))
        lines.append(_Html.field(f'V_rect: <b>{v_rect} mV</b>'))
        lines.append(_Html.field(f'I_rect: <b>{i_rect} mA</b>'))
        return _Html.join(lines)

    def _ask_plap2(self, p):
        if len(p) < 10:
            return f'<i>mpp_rx_plap2_t requires 10 bytes, got {len(p)} B</i>'
        g_coil = _u16_be(p[1], p[2])
        alpha_itx = _s16_be(p[3], p[4])
        alpha_irect = _s16_be(p[5], p[6])
        alpha_vrect = _s16_be(p[8], p[9])
        lines = ['• mpp_rx_plap2_t — PLA Parameters 2']
        lines.append(_Html.field(f'G_coil_t: <b>{g_coil}</b>'))
        lines.append(_Html.field(f'Alpha_FM_ITX: <b>{alpha_itx}</b>'))
        lines.append(_Html.field(f'Alpha_FM_IRECT: <b>{alpha_irect}</b>'))
        lines.append(_Html.field(f'Alpha_FM_VRECT: <b>{alpha_vrect}</b>'))
        return _Html.join(lines)

    def _ask_cal_capture(self, p):
        """0x96 — Calibration Capture (Figure 130, Table 72)."""
        exp_len = get_payload_len(0x96)
        if len(p) < exp_len:
            return (
                f'<i>mpp_rx_cal_capture_t requires {exp_len} bytes, got {len(p)} B</i>'
                + (f'<br>{self._generic_raw(p)}' if p else '')
            )
        cal_idx = p[0] & 0x7F
        operation = p[1] & 0x03
        rx_pwr = _u16_be(p[2], p[3])
        p_rect = _u16_be(p[4], p[5])
        v_rect = _u16_be(p[6], p[7])
        irect = ((p[8] & 0x0F) << 8) | p[9]
        c = _qi_colors()

        lines = ['• CAL_CAPTURE — Calibration Capture (0x96)']
        _Html.byte(0, 'B0 cal_point_idx', p[0], lines)
        if p[0] & 0x80:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">'
                f'Reserved [b7]: must be 0 (current 0x{(p[0] >> 7):X})</span>'
            ))
        lines.append(_Html.field(f'Calibration Point Index [b6-b0]: <b>{cal_idx}</b>'))

        _Html.byte(1, 'B1 operation', p[1], lines)
        if p[1] & 0xFC:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">'
                f'Reserved [b7-b2]: must be 0 (current 0x{(p[1] >> 2):02X})</span>'
            ))
        op_label = CAL_CAPTURE_OPERATIONS.get(operation, f'Reserved ({operation})')
        lines.append(_Html.field(
            f'Operation [b1-b0]: <b>{op_label}</b>'
        ))

        def _meas(label, val, unit, scale_w=None):
            if val == 0:
                return f'{label}: <b>0</b> (measurement not available)'
            text = f'{label}: <b>{val} {unit}</b>'
            if scale_w is not None:
                text += f' ({val * scale_w:.3f} W)'
            return text

        _Html.byte(2, 'received_power MSB', p[2], lines)
        _Html.byte(3, 'received_power LSB', p[3], lines)
        lines.append(_Html.field(_meas('Received Power', rx_pwr, 'mW', 0.001)))

        _Html.byte(4, 'p_rect MSB', p[4], lines)
        _Html.byte(5, 'p_rect LSB', p[5], lines)
        lines.append(_Html.field(_meas('P_RECT', p_rect, 'mW', 0.001)))

        _Html.byte(6, 'v_rect MSB', p[6], lines)
        _Html.byte(7, 'v_rect LSB', p[7], lines)
        if v_rect == 0:
            lines.append(_Html.field('V_RECT: <b>0</b> (measurement not available)'))
        else:
            lines.append(_Html.field(
                f'V_RECT: <b>{v_rect} mV</b> ({v_rect / 1000:.3f} V)'
            ))

        _Html.byte(8, 'B8 irect MSB nibble + rsvd', p[8], lines)
        if p[8] & 0xF0:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">'
                f'Reserved [B8 b7-b4]: 0x{(p[8] >> 4):X}</span>'
            ))
        _Html.byte(9, 'B9 irect LSB', p[9], lines)
        if irect == 0:
            lines.append(_Html.field(
                f'I_RECT [12-bit]: <b>0</b> (measurement not available)'
            ))
        else:
            lines.append(_Html.field(
                f'I_RECT [12-bit]: <b>{irect} mA</b> ({irect / 1000:.3f} A)'
            ))

        lines.append(_Html.field(
            '<i>PTx response: CAL_CAPTURE_RSP (FSK 0x14)</i>'
        ))
        return _Html.join(lines)

    def _ask_matedq_coeff(self, p):
        if len(p) < 7:
            return f'<i>mpp_rx_matedq_coeff_t requires ≥7 bytes, got {len(p)} B</i>'
        g0 = _s16_be(p[1], p[2])
        g1 = _s16_be(p[3], p[4])
        d0 = _s16_be(p[5], p[6])
        lines = ['• mpp_rx_matedq_coeff_t — Mated-Q Coefficients']
        lines.append(_Html.field(f'g0: <b>{g0 * 0.001:.3f}</b>'))
        lines.append(_Html.field(f'g1: <b>{g1 * 0.001:.3f}</b>'))
        lines.append(_Html.field(f'd0: <b>{d0 * 0.001:.3f}</b>'))
        return _Html.join(lines)

    def _ask_adt(self, p):
        if len(p) < 1:
            return self._no_payload()
        lines = [f'• ADT variable-length packet ({len(p)} B)']
        lines.append(_Html.field(f'Payload: <span style="color:{_qi_colors()["hex"]}">{_hex_bytes(p, 20)}</span>'))
        return _Html.join(lines)

    # ------------------------------------------------------------------
    # FSK 载荷解析 (PTx → PRx)
    # ------------------------------------------------------------------

    def _decode_fsk_payload(self, header, payload):
        if header in FSK_BARE_PATTERNS and not payload:
            return self._fsk_bare_pattern(header)

        decoders = {
            0x00: self._fsk_null,
            0x01: self._fsk_err,
            0x0A: self._fsk_eptr,
            0x13: self._fsk_msn,
            0x14: self._fsk_cal_capture_rsp,
            0x15: self._fsk_dsr,
            0x1B: self._fsk_cal_op_rsp,
            0x1E: self._fsk_cloak_rcs,
            0x1F: self._fsk_chs,
            0x23: self._fsk_mss,
            0x25: self._fsk_adc,
            0x2E: self._fsk_get,
            0x2F: self._fsk_eds,
            0x30: self._fsk_ptx_id,
            0x31: self._fsk_cap,
            0x32: self._fsk_xcap,
            0x34: self._fsk_cal_enter_rsp,
            0x3F: self._fsk_3f,
            0x40: self._fsk_matedq_res,
            0x43: self._fsk_cal_cap,
            0x4F: self._fsk_sadc,
            0x54: self._fsk_dpcal_param,
            0x5A: self._fsk_modecap,
            0x5F: self._fsk_plap,
            0x61: self._fsk_gmp,
            0x8F: self._fsk_xid_ecap,
            0xA0: self._fsk_modexcap,
        }
        if header in (0x16, 0x17, 0x26, 0x27, 0x36, 0x37, 0x46, 0x47,
                      0x56, 0x57, 0x66, 0x67, 0x76, 0x77, 0x98, 0x99):
            return self._ask_adt(payload)
        if header in (0x1C, 0x1D, 0x2C, 0x2D, 0x3E, 0x4E):
            return self._generic_prop(payload)
        if header == 0x11:
            c = _qi_colors()
            return f"<b style='color:{c['ok']}'>✓ FAST-ACK (0x11)</b> — {_qi_tr('qi.fast_ack')}" + (
                f'<br>{self._generic_raw(payload)}' if payload else ''
            )
        decoder = decoders.get(header)
        if decoder:
            return decoder(payload)
        return self._generic_raw(payload)

    def _fsk_bare_pattern(self, header):
        """裸 FSK 模式：0x55 等在 BPP 与 Qi 2.2.1 中语义不同，并列展示。"""
        c = _qi_colors()
        lines = []
        if header in BPP_FSK_PATTERNS:
            name, desc = BPP_FSK_PATTERNS[header]
            lines.append(f"<b style='color:{c['ok']}'>✓ BPP {name}</b> — {desc}")
        qi_entry = QI22_FSK_PATTERNS.get(header)
        bpp_entry = BPP_FSK_PATTERNS.get(header)
        if qi_entry and qi_entry != bpp_entry:
            name, desc = qi_entry
            lines.append(f"<b style='color:{c['warn']}'>✓ Qi 2.2.1 {name}</b> — {desc}")
        elif header not in BPP_FSK_PATTERNS and qi_entry:
            name, desc = qi_entry
            lines.append(f"<b style='color:{c['ok']}'>✓ {name}</b> — {desc}")
        return '<br>'.join(lines) if lines else self._generic_raw([])

    def _fsk_null(self, p):
        c = _qi_colors()
        if not p:
            return f"<b style='color:{c['muted']}'>NULL</b> — bpp_tx_null_t (no payload)"
        ok = p[0] == 0x00
        warn = '' if ok else f'<span style="color:{c["err"]}">must be 0x00</span>'
        return (
            f"• <span style='color:{c['byte_fsk']}'>Byte 0:</span> reserved = 0x{p[0]:02X}<br>"
            f"{_Html.field('Must be 0x00' if ok else warn)}"
        )

    def _fsk_err(self, p):
        if len(p) < 1:
            return self._insufficient()
        info = (p[0] >> 4) & 0x0F
        err = p[0] & 0x07
        c = _qi_colors()
        lines = ['• mpp_tx_err_t — Error Status']
        _Html.fbyte(0, 'error_info', p[0], lines)
        lines.append(_Html.field(f'Info [b7-b4]: <b>{MPP_TX_ERR_INFO.get(info, info)}</b>'))
        if (p[0] >> 3) & 1:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">Reserved [b3]: must be 0</span>'
            ))
        lines.append(_Html.field(f'Error Code [b2-b0]: <b>{err}</b>'))
        return _Html.join(lines)

    def _fsk_eptr(self, p):
        if len(p) < 1:
            return self._insufficient()
        c = _qi_colors()
        return (
            f"• <span style='color:{c['byte_fsk']}'>Byte 0:</span> reason_code = 0x{p[0]:02X}<br>"
            f"{_Html.field(f'End reason: <b>{p[0]}</b> (e.g. 0=mode switch)')}"
        )

    def _fsk_msn(self, p):
        if len(p) < 1:
            return self._insufficient()
        main_mode = (p[0] >> 2) & 0x03
        c = _qi_colors()
        lines = ['• mpp_tx_msn_t — Mode Selection Notification']
        _Html.fbyte(0, 'mode_status', p[0], lines)
        if p[0] & 0xF0:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">'
                f'Reserved [b7-b4]: must be 0 (current 0x{(p[0] >> 4):X})</span>'
            ))
        lines.append(_Html.field(f'Main Mode [b3-b2]: <b>{MSR_MAIN_MODE.get(main_mode, main_mode)}</b>'))
        if p[0] & 0x03:
            lines.append(_Html.field(
                f'<span style="color:{c["warn"]}">'
                f'Reserved [b1-b0]: must be 0 (current 0x{p[0] & 0x03:X})</span>'
            ))
        return _Html.join(lines)

    def _fsk_cal_capture_rsp(self, p):
        if len(p) < 1:
            return self._insufficient()
        c = _qi_colors()
        accepted = p[0] == 0x00
        color = c['ok'] if accepted else c['err']
        result = 'ACCEPTED' if accepted else f'0x{p[0]:02X}'
        detail = f'Capture result: <b style="color:{color}">{result}</b>'
        return (
            f"• <span style='color:{c['byte_fsk']}'>Byte 0:</span> response = 0x{p[0]:02X}<br>"
            f"{_Html.field(detail)}"
        )

    def _fsk_dsr(self, p):
        if len(p) < 1:
            return self._insufficient()
        name, desc = BPP_DSR_TYPES.get(p[0], (f'0x{p[0]:02X}', 'Reserved'))
        lines = ['• bpp_tx_dsr_t — Data Stream Response']
        _Html.fbyte(0, 'response_code', p[0], lines)
        lines.append(_Html.field(f'Response: <b>{name}</b> — {desc}'))
        return _Html.join(lines)

    def _fsk_cal_op_rsp(self, p):
        if len(p) < 1:
            return self._insufficient()
        c = _qi_colors()
        return (
            f"• <span style='color:{c['byte_fsk']}'>Byte 0:</span> status = 0x{p[0]:02X}<br>"
            f"{_Html.field(f'Operation status: <b>{p[0]}</b>')}"
        )

    def _fsk_cloak_rcs(self, p):
        if not p:
            return self._no_payload()
        sub = p[0]
        sub_map = {0x00: 'Cloak Response', 0x03: 'Regulation Control Status (RCS)'}
        sub_label = sub_map.get(sub, f'0x{sub:02X}')
        lines = [f'• mpp_tx_cloak_t / mpp_tx_rcs_t — selector = <b>{sub_label}</b>']
        _Html.fbyte(0, 'selector', p[0], lines)
        if sub != 0x00 and sub != 0x03:
            lines.append(_Html.field(f'<span style="color:{_qi_colors()["warn"]}">Expected selector 0x00 or 0x03</span>'))
        if len(p) > 1:
            lines.append(_Html.field(f'Additional: {_hex_bytes(p[1:])}'))
        return _Html.join(lines)

    def _fsk_chs(self, p):
        if len(p) < 1:
            return self._insufficient()
        c = _qi_colors()
        detail = f'PTx charge level: <b style="color:{c["ok"]}">{p[0]} %</b>' if p[0] <= 100 else f'0x{p[0]:02X}'
        return (
            f"• <span style='color:{c['byte_fsk']}'>Byte 0:</span> charge_status = 0x{p[0]:02X}<br>"
            f"{_Html.field(detail)}"
        )

    def _fsk_mss(self, p):
        if len(p) < 2:
            return f'<i>mpp_tx_mss_t requires 2 bytes, got {len(p)} B</i>'
        status = p[0] & 0x03
        err = p[1] & 0x0F
        lines = ['• mpp_tx_mss_t — Mode Select Status']
        _Html.fbyte(0, 'status_info', p[0], lines)
        lines.append(_Html.field(f'Status [b1-b0]: <b>{MSS_STATUS.get(status, status)}</b>'))
        _Html.fbyte(1, 'error_code', p[1], lines)
        lines.append(_Html.field(f'Error [b3-b0]: <b>{MSS_ERROR.get(err, err)}</b>'))
        return _Html.join(lines)

    def _fsk_adc(self, p):
        if len(p) < 1:
            return self._insufficient()
        lines = ['• bpp_tx_adc_t — Auxiliary Data Control']
        _Html.fbyte(0, 'request', p[0], lines)
        if len(p) >= 2:
            _Html.fbyte(1, 'parameter', p[1], lines)
        return _Html.join(lines)

    def _fsk_get(self, p):
        if len(p) < 2:
            return f'<i>mpp_tx_get_t requires 2 bytes, got {len(p)} B</i>'
        lines = ['• mpp_tx_get_t — Get Request (Table 57)']
        _Html.fbyte(0, 'rsvd', p[0], lines)
        _Html.fbyte(1, 'parameter', p[1], lines)
        lines.append(_Html.field(f'Request type: {_format_get_param(p[1])}'))
        return _Html.join(lines)

    def _fsk_eds(self, p):
        if len(p) < 2:
            return f'<i>mpp_tx_eds_t requires 2 bytes, got {len(p)} B</i>'
        mask = _u16_be(p[0], p[1])
        streams = [i for i in range(16) if mask & (1 << i)]
        lines = ['• mpp_tx_eds_t — Enabled Data Streams']
        lines.append(_Html.field(f'Mask: <b>0x{mask:04X}</b>'))
        if streams:
            lines.append(_Html.field(f'Enabled streams: <b>{", ".join(map(str, streams))}</b>'))
        return _Html.join(lines)

    def _fsk_ptx_id(self, p):
        lines = [f'• bpp_tx_id_t — Power Transmitter ID ({len(p)} B)']
        for i, b in enumerate(p):
            _Html.fbyte(i, f'ptx_id_payload[{i}]', b, lines)
        return _Html.join(lines)

    def _fsk_cap(self, p):
        if len(p) < 3:
            return f'<i>bpp_tx_cap_t requires 3 bytes, got {len(p)} B</i>'
        pwr_class = (p[0] >> 6) & 0x03
        guar_pwr = p[0] & 0x3F
        pot_pwr = p[2]
        lines = ['• bpp_tx_cap_t — Power Transmitter Capabilities']
        _Html.fbyte(0, 'power_info', p[0], lines)
        lines.append(_Html.field(f'Power Class [b7-b6]: <b>{pwr_class}</b>'))
        lines.append(_Html.field(f'Guaranteed Power [b5-b0]: <b>{guar_pwr}</b> (≈ {guar_pwr * 0.5:.1f} W)'))
        _Html.fbyte(1, 'reserved', p[1], lines)
        _Html.fbyte(2, 'potential_power', p[2], lines)
        lines.append(_Html.field(f'Potential Load Power: <b>{pot_pwr}</b> (≈ {pot_pwr * 0.5:.1f} W)'))
        return _Html.join(lines)

    def _fsk_xcap(self, p):
        if len(p) < 3:
            return f'<i>bpp_tx_xcap_t requires 3 bytes, got {len(p)} B</i>'
        lines = ['• bpp_tx_xcap_t — Extended Capabilities']
        _Html.fbyte(0, 'capabilities', p[0], lines)
        lines.append(_Html.field(f'TPS [b7]: <b>{"Yes" if p[0] & 0x80 else "No"}</b>'))
        lines.append(_Html.field(f'TDE [b6]: <b>{"Yes" if p[0] & 0x40 else "No"}</b>'))
        lines.append(_Html.field(f'TDS [b5]: <b>{"Yes" if p[0] & 0x20 else "No"}</b>'))
        return _Html.join(lines)

    def _fsk_cal_enter_rsp(self, p):
        if len(p) < 3:
            return f'<i>mpp_tx_cal_enter_rsp_t requires 3 bytes, got {len(p)} B</i>'
        resp = CAL_ENTER_RESPONSE.get(p[0], f'0x{p[0]:02X}')
        reason = CAL_ENTER_REASON.get(p[1], p[1])
        lines = ['• mpp_tx_cal_enter_rsp_t — Enter Calibration Response']
        _Html.fbyte(0, 'response_code', p[0], lines)
        lines.append(_Html.field(f'Response: <b>{resp}</b>'))
        _Html.fbyte(1, 'reason', p[1], lines)
        lines.append(_Html.field(f'Reject reason: <b>{reason}</b>'))
        _Html.fbyte(2, 'parameter', p[2], lines)
        return _Html.join(lines)

    def _fsk_3f(self, p):
        if len(p) < 1:
            return self._insufficient()
        sel = p[0]
        mod_map = {0x00: 'INV (inverter voltage)', 0x01: 'SDSR (simultaneous stream response)', 0x02: 'KEST (estimated coupling coefficient)'}
        lines = [f"• mpp_tx_inv/sdsr/kest — selector = <b>{mod_map.get(sel, f'0x{sel:02X}')}</b>"]
        _Html.fbyte(0, 'selector', p[0], lines)
        if sel == 0x00 and len(p) >= 3:
            _Html.fbyte(2, 'v_inv', p[2], lines)
            lines.append(_Html.field(f'Inverter voltage: <b>{p[2] * 2} mV</b> ({p[2] * 0.002:.2f} V, ×2 mV)'))
        elif sel == 0x01 and len(p) >= 3:
            stream = p[1] & 0x0F
            resp = p[2] & 0x0F
            lines.append(_Html.field(f'Stream: <b>{stream}</b>, Type: <b>{SDSR_TYPES.get(resp, resp)}</b>'))
        elif sel == 0x02 and len(p) >= 3:
            # Figure 145: Estimated K — 12-bit field = B1[b3:b0] << 8 | B2, K_est = field / 4095
            _Html.fbyte(1, 'estimated_k MSB nibble', p[1], lines)
            if p[1] & 0xF0:
                lines.append(_Html.field(f'Reserved [b7-b4]: 0x{(p[1] >> 4):X}'))
            _Html.fbyte(2, 'estimated_k LSB', p[2], lines)
            field_val = ((p[1] & 0x0F) << 8) | p[2]
            k_est = field_val / 4095.0
            lines.append(_Html.field(
                f'Estimated K field [12-bit]: <b>{field_val}</b> (0x{field_val:03X})'
            ))
            lines.append(_Html.field(
                f'K_est = field value / 4095 = <b>{k_est:.4f}</b>'
            ))
        elif len(p) > 1:
            lines.append(_Html.field(f'Data: {_hex_bytes(p[1:])}'))
        return _Html.join(lines)

    def _fsk_matedq_res(self, p):
        if len(p) < 1:
            return self._insufficient()
        fo = p[0] & 0x07
        lines = ['• mpp_tx_matedq_res_t — Mated-Q Results']
        _Html.fbyte(0, 'result', p[0], lines)
        lines.append(_Html.field(f'Foreign Object [b2-b0]: <b>{MATEDQ_FO_RESULT.get(fo, fo)}</b>'))
        return _Html.join(lines)

    def _fsk_cal_cap(self, p):
        if len(p) < 4:
            return f'<i>mpp_tx_cal_cap_t requires 4 bytes, got {len(p)} B</i>'
        cap = int.from_bytes(p[:4], 'big')
        lines = ['• mpp_tx_cal_cap_t — Calibration Capabilities']
        lines.append(_Html.field(f'Capability mask (BE): <b>0x{cap:08X}</b>'))
        return _Html.join(lines)

    def _fsk_sadc(self, p):
        if len(p) < 4:
            return f'<i>mpp_tx_sadc_t requires 4 bytes, got {len(p)} B</i>'
        req = p[0] & 0x0F
        stream = p[1] & 0x0F
        param = _u16_be(p[2], p[3])
        lines = ['• mpp_tx_sadc_t — Simultaneous Auxiliary Data Control']
        lines.append(_Html.field(f'Request: <b>{SADC_REQUESTS.get(req, req)}</b>'))
        lines.append(_Html.field(f'Stream: <b>{stream}</b>'))
        lines.append(_Html.field(f'Parameter: <b>0x{param:04X}</b>'))
        return _Html.join(lines)

    def _fsk_dpcal_param(self, p):
        if len(p) < 5:
            return f'<i>mpp_tx_dpcal_param_t requires 5 bytes, got {len(p)} B</i>'
        invalid = p[0] & 0x01
        alpha = _u16_be(p[1], p[2])
        beta = _u16_be(p[3], p[4])
        lines = ['• mpp_tx_dpcal_param_t — Calibration Parameter']
        lines.append(_Html.field(f'Invalid [b0]: <b>{"All invalid" if invalid else "Valid"}</b>'))
        lines.append(_Html.field(f'DPLOSS Alpha: <b>{alpha}</b>'))
        lines.append(_Html.field(f'DPLOSS Beta: <b>{beta}</b>'))
        return _Html.join(lines)

    def _fsk_modecap(self, p):
        if len(p) < 2:
            return f'<i>mpp_tx_modecap_t requires ≥2 bytes, got {len(p)} B</i>'
        caps = p[1]
        lines = ['• mpp_tx_modecap_t — Power Modes Capabilities']
        _Html.fbyte(1, 'capabilities', p[1], lines)
        for bit, mode in [(0, 'CPM'), (1, 'NPM'), (2, 'LPM'), (3, 'HPM')]:
            lines.append(_Html.field(f'{mode} [Bit{bit}]: <b>{"✓" if caps & (1 << bit) else "—"}</b>'))
        return _Html.join(lines)

    def _fsk_plap(self, p):
        if len(p) < 3:
            return f'<i>mpp_tx_plap_t requires ≥3 bytes, got {len(p)} B</i>'
        g_coil_r = _s16_be(p[1], p[2])
        lines = ['• mpp_tx_plap_t — Power Loss Accounting Parameters']
        lines.append(_Html.field(f'G_coil_r: <b>{g_coil_r}</b>'))
        return _Html.join(lines)

    def _fsk_gmp(self, p):
        if len(p) < 6:
            return f'<i>mpp_tx_gmp_t requires 6 bytes, got {len(p)} B</i>'
        c_npm = _u16_be(p[0], p[1])
        c_hpm = _u16_be(p[2], p[3])
        c_cpm = _u16_be(p[4], p[5])
        lines = ['• mpp_tx_gmp_t — Gain Measurement Parameters']
        lines.append(_Html.field(f'G_NPM_C0: <b>{c_npm}</b>'))
        lines.append(_Html.field(f'G_HPM_C0: <b>{c_hpm}</b>'))
        lines.append(_Html.field(f'G_CPM_C0: <b>{c_cpm}</b>'))
        return _Html.join(lines)

    def _fsk_xid_ecap(self, p):
        if len(p) < 1:
            return self._insufficient()
        selector = (p[0] >> 4) & 0x0F
        if selector == 0x00:
            return self._fsk_ptx_xid(p)
        if selector == 0x01:
            return self._fsk_ptx_ecap(p)
        lines = [f'• mpp_tx_xid/ecap — selector = <b>0x{selector:X}</b> (reserved)']
        _Html.fbyte(0, 'B0 (selector nibble)', p[0], lines)
        if len(p) > 1:
            lines.append(_Html.field(f'Data: {_hex_bytes(p[1:])}'))
        return _Html.join(lines)

    def _fsk_ptx_xid(self, p):
        """0x8F:0 — Extended PTx Identification (Figure 152, 9 B)."""
        if len(p) < 9:
            return f'<i>mpp_tx_xid_t requires 9 bytes, got {len(p)} B</i>' + (
                f'<br>{self._generic_raw(p)}' if p else ''
            )
        app = (p[0] >> 1) & 0x01
        uid_flag = p[0] & 0x01
        dev_id = ((p[4] & 0x7F) << 13) | (p[5] << 5) | ((p[6] >> 3) & 0x1F)
        mfg_rsvd = ((p[6] & 0x07) << 16) | (p[7] << 8) | p[8]
        lines = ['• mpp_tx_xid_t — Extended PTx Identification (0x8F:0)']
        _Html.fbyte(0, 'B0 selector/APP/UID', p[0], lines)
        lines.append(_Html.field(f'Selector [b7-b4]: <b>0</b>'))
        lines.append(_Html.field(f'APP [b1]: <b>{PTX_XID_APP.get(app, app)}</b>'))
        lines.append(_Html.field(
            f'UID [b0]: <b>{"Manufacturer-generated unique ID" if uid_flag else "Non-unique ID"}</b>'
        ))
        for i in (1, 2, 3):
            _Html.fbyte(i, 'reserved', p[i], lines)
        _Html.fbyte(4, 'B4 device_id + rsvd', p[4], lines)
        _Html.fbyte(5, 'B5 device_id', p[5], lines)
        _Html.fbyte(6, 'B6 device_id + mfg_rsvd', p[6], lines)
        lines.append(_Html.field(f'Device Identifier [20-bit]: <b>0x{dev_id:05X}</b> ({dev_id})'))
        _Html.fbyte(7, 'B7 mfg_reserved', p[7], lines)
        _Html.fbyte(8, 'B8 mfg_reserved', p[8], lines)
        lines.append(_Html.field(f'Mfg Reserved [19-bit]: <b>0x{mfg_rsvd:05X}</b>'))
        return _Html.join(lines)

    def _fsk_ptx_ecap(self, p):
        """0x8F:1 — Extended PTx Capabilities ECAP (Figure 153 + Table 93, 9 B)."""
        if len(p) < 9:
            return f'<i>mpp_tx_ecap_t requires 9 bytes, got {len(p)} B</i>' + (
                f'<br>{self._generic_raw(p)}' if p else ''
            )
        pot_pwr = p[2]
        neg_pwr = p[4]
        cal = (p[5] >> 4) & 0x03
        plr = p[5] & 0x0F
        src = (p[6] >> 6) & 0x03
        buf_n = (p[6] >> 2) & 0x03
        streams = p[6] & 0x03
        buf_bytes = 16 * (1 << buf_n)
        lines = ['• mpp_tx_ecap_t — Extended PTx Capabilities (0x8F:1)']
        _Html.fbyte(0, 'B0 selector', p[0], lines)
        lines.append(_Html.field(f'Selector [b7-b4]: <b>1</b>'))
        _Html.fbyte(1, 'B1 reserved', p[1], lines)
        _Html.fbyte(2, 'B2 potential_load_power', p[2], lines)
        lines.append(_Html.field(
            f'Potential Load Power: <b>{pot_pwr * 100} mW</b> ({pot_pwr * 0.1:.1f} W)'
        ))
        _Html.fbyte(3, 'B3 reserved', p[3], lines)
        _Html.fbyte(4, 'B4 negotiable_load_power', p[4], lines)
        lines.append(_Html.field(
            f'Negotiable Load Power: <b>{neg_pwr * 100} mW</b> ({neg_pwr * 0.1:.1f} W)'
        ))
        _Html.fbyte(5, 'B5 CAL + power_limit_reason', p[5], lines)
        lines.append(_Html.field(
            f'CAL [b5-b4]: <b>{"Calibration protocol supported" if cal else "Not supported"}</b>'
        ))
        lines.append(_Html.field(
            f'Power Limit Reason [b3-b0]: <b>{PTX_POWER_LIMIT_REASON.get(plr, f"Reserved ({plr})")}</b>'
        ))
        _Html.fbyte(6, 'B6 SRC + buffer + streams', p[6], lines)
        lines.append(_Html.field(
            f'SRC [b7-b6]: <b>{"Limited power source (e.g. battery)" if src else "Unlimited power source"}</b>'
        ))
        lines.append(_Html.field(
            f'Buffer Size [b3-b2]: N=<b>{buf_n}</b> → <b>{buf_bytes} B</b> (16×2^N)'
        ))
        lines.append(_Html.field(f'Concurrent Data Streams [b1-b0]: <b>{streams}</b>'))
        for i in (7, 8):
            _Html.fbyte(i, 'reserved', p[i], lines)
        lines.append(_Html.field(
            '<i>PRx response: DSR/ACK (confirm power limit) or NEGO (start negotiation)</i>'
        ))
        return _Html.join(lines)

    def _fsk_modexcap(self, p):
        if len(p) < 12:
            return f'<i>mpp_tx_modexcap_t requires 12 bytes, got {len(p)} B</i>'
        modes = [('CPM', 0), ('LPM', 3), ('NPM', 6), ('HPM', 9)]
        lines = ['• mpp_tx_modexcap_t — Power Modes Extended Capabilities']
        for name, off in modes:
            if off + 2 < len(p):
                v0, v1, pwr = p[off], p[off + 1], p[off + 2]
                lines.append(_Html.field(
                    f'{name}: V_ref0=<b>{v0}</b>, V_ref1=<b>{v1}</b>, '
                    f'Potential=<b>{pwr * 100} mW</b> ({pwr * 0.1:.1f} W)'
                ))
        return _Html.join(lines)

    # ------------------------------------------------------------------
    # 通用辅助
    # ------------------------------------------------------------------

    def _generic_prop(self, p):
        if not p:
            return f'<i>{_qi_tr("qi.prop_no_payload")}</i>'
        hex_part = f'<span style="color:{_qi_colors()["hex"]}">{_hex_bytes(p, 16)}</span>'
        return (
            f'• Proprietary / vendor extension packet<br>'
            f'{_Html.field(f"Length: {len(p)} B")}<br>'
            f'{_Html.field("HEX: " + hex_part)}'
        )

    def _generic_raw(self, p):
        if not p:
            return f'<i>{_qi_tr("qi.empty_pkt")}</i>'
        lines = [f'• Raw payload ({len(p)} B)']
        for i, b in enumerate(p[:12]):
            _Html.byte(i, 'data', b, lines)
        if len(p) > 12:
            lines.append(_Html.field(f'… <span style="color:{_qi_colors()["hex"]}">{_hex_bytes(p[12:])}</span>'))
        return _Html.join(lines)


# Guard against accidental renames (e.g. bulk tr( → _t( corrupting _fsk_eptr).
_QI22_DECODER_METHODS = frozenset({
    '_ask_ss', '_ask_ept', '_ask_ce', '_ask_rp8', '_ask_chs', '_ask_pch', '_ask_grq',
    '_ask_nego', '_ask_msr', '_ask_dsr', '_ask_cloak', '_ask_xce', '_ask_srq', '_ask_fod',
    '_ask_cal_op', '_ask_adc', '_ask_get', '_ask_eds', '_ask_cal_enter', '_ask_cal_exit',
    '_ask_rp', '_ask_cfg', '_ask_wpid', '_ask_id', '_ask_xid', '_ask_ecap', '_ask_sdsr',
    '_ask_sadc', '_ask_kest_coeff', '_ask_report_pla', '_ask_plap', '_ask_pla2', '_ask_plap2',
    '_ask_cal_capture', '_ask_matedq_coeff', '_ask_adt', '_ask_mpp_xid', '_ask_bpp_xid',
    '_ask_report_58', '_ask_pla_58',
    '_fsk_bare_pattern', '_fsk_null', '_fsk_err', '_fsk_eptr', '_fsk_msn',
    '_fsk_cal_capture_rsp', '_fsk_dsr', '_fsk_cal_op_rsp', '_fsk_cloak_rcs', '_fsk_chs',
    '_fsk_mss', '_fsk_adc', '_fsk_get', '_fsk_eds', '_fsk_ptx_id', '_fsk_cap', '_fsk_xcap',
    '_fsk_cal_enter_rsp', '_fsk_3f', '_fsk_matedq_res', '_fsk_cal_cap', '_fsk_sadc',
    '_fsk_dpcal_param', '_fsk_modecap', '_fsk_plap', '_fsk_gmp', '_fsk_xid_ecap',
    '_fsk_ptx_xid', '_fsk_ptx_ecap', '_fsk_modexcap',
    '_generic_prop', '_generic_raw',
})


def _validate_qi22_decoder_bindings() -> None:
    missing = sorted(name for name in _QI22_DECODER_METHODS if not hasattr(Qi22Parser, name))
    if missing:
        raise RuntimeError(f'Qi22Parser decoder binding check failed: missing {missing}')


_validate_qi22_decoder_bindings()
