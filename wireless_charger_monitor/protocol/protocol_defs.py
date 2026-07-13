# ==========================================
# WPC Qi BPP/EPP + MPP 协议定义
# Source: docs/bpp_protocol.h, docs/mpp_protocol.h
# ==========================================
"""协议常量、报文注册表与查找表。

所有多字节整数字段在空中均为大端 (BIG-ENDIAN) 传输。
"""

from __future__ import annotations


def get_payload_len(header: int) -> int:
    """等价于 C 宏 GET_PAYLOAD_LEN(header)。"""
    if header <= 0x1F:
        return 1 + header // 32
    if header <= 0x7F:
        return 2 + (header - 32) // 16
    if header <= 0xDF:
        return 8 + (header - 128) // 8
    return 20 + (header - 224) // 4


# ---------------------------------------------------------------------------
# BPP FSK 底层响应模式 (无 Header / Checksum)
# ---------------------------------------------------------------------------
BPP_FSK_PATTERNS = {
    0x55: ('ACK', 'Acknowledge (01010101)'),
    0x00: ('NAK', 'Negative acknowledge (00000000)'),
    0xAA: ('ND', 'Not defined / unsupported (10101010)'),
    0x0F: ('ATN', 'Attention / request communication (00001111)'),
}

# Qi 2.2.1 抓包常见裸 FSK 模式（与 BPP 枚举值不同，并存识别）
QI22_FSK_PATTERNS = {
    0xFF: ('ACK', 'Acknowledge (Qi 2.2.1)'),
    0x00: ('NAK', 'Negative acknowledge'),
    0x55: ('ND', 'Not defined (Qi 2.2.1)'),
    0x33: ('ATN', 'Attention (Qi 2.2.1)'),
}

FSK_BARE_PATTERNS = {**BPP_FSK_PATTERNS, **QI22_FSK_PATTERNS}

# ---------------------------------------------------------------------------
# 查找表
# ---------------------------------------------------------------------------
EPT_REASONS = {
    0x00: 'EPT/nul — Unknown',
    0x01: 'EPT/cc — Charge complete',
    0x02: 'EPT/if — Internal fault',
    0x03: 'EPT/ot — Over temperature',
    0x04: 'EPT/ov — Over voltage',
    0x05: 'EPT/oc — Over current',
    0x06: 'EPT/bf — Battery fault',
    0x08: 'EPT/nr — No response',
    0x0A: 'EPT/an — Negotiation failed',
    0x0B: 'EPT/rst — Request restart',
    0x0C: 'EPT/rep — Re-ping',
    0x0D: 'EPT/nfc — NFC',
}

BPP_GRQ_REQUESTS = {
    0x31: 'PTx Capabilities (CAP)',
    0x32: 'PTx Extended Capabilities (XCAP)',
}

MPP_GRQ_REQUESTS = {
    0x00: 'PTx Identification',
    0x01: 'PTx Capabilities',
    0x02: 'PTx Extended Identification',
    0x03: 'PTx Extended Capabilities',
    0x20: 'MPP Inverter Voltage (INV)',
    0x30: 'MPP Power Modes Capabilities (MODECAP)',
    0x31: 'MPP Extended Power Modes Capabilities (MODEXCAP)',
}

BPP_SRQ_TYPES = {
    0x00: 'SRQ/en — End negotiation',
    0x01: 'SRQ/gp — Guaranteed power',
    0x03: 'SRQ/fsk — FSK configuration',
    0x05: 'SRQ/reping — Re-ping',
}

MPP_SRQ_TYPES = {
    0xA0: 'SRQ/pla — PLA format',
    0xA1: 'SRQ/xceMethod — Control error method',
    0xA7: 'SRQ/verSel — Version select',
    0xA9: 'SRQ/xceGain — Control gain',
    0xF0: 'SRQ/freqsel — Frequency select',
    0xF3: 'SRQ/egpl — Power level',
    0xF5: 'SRQ/cloakl — Cloak ping delay (low byte)',
    0xF6: 'SRQ/pcp — Power control profile',
    0xF7: 'SRQ/cloakh — Cloak ping delay (high byte)',
    0xF8: 'SRQ/detect — Cloak detect ping delay',
}

SRQ_XCE_METHOD = {
    0: 'Uncompensated (Default)',
    1: 'Reserved',
    2: 'Gain Linearization',
    3: 'Reserved',
}

SRQ_FREQ_SELECTOR = {
    0: 'Reserved',
    1: '360 kHz',
    2: 'Reserved',
    3: 'Reserved',
}

SRQ_PCP_PROFILE = {
    0: 'Low-K power profile not selected',
    1: 'Low-K power profile',
}

def srq_type_name(code: int) -> str:
    if code in BPP_SRQ_TYPES:
        return BPP_SRQ_TYPES[code]
    if code in MPP_SRQ_TYPES:
        return MPP_SRQ_TYPES[code]
    if 0xE0 <= code <= 0xEF:
        return f'SRQ/MppProp — Proprietary parameter (0x{code:02X})'
    return f'Request 0x{code:02X}'

BPP_DSR_TYPES = {
    0x00: ('DSR/ack', 'ACK'),
    0x01: ('DSR/poll', 'POLL'),
    0x02: ('DSR/nak', 'NAK'),
    0x03: ('DSR/nd', 'ND'),
}

# PRx Get Request Types — MPP Table 57 (ASK 0x28 / FSK 0x2E parameter 字段)
MPP_GET_PARAMS = {
    0: ('PTx Extended Identification', '0x8F:0 XID'),
    2: ('PTx Inverter Voltage', '0x3F:0 INV'),
    3: ('PTx Power Loss Accounting Parameters', '0x5F PLAP'),
    4: ('PTx Extended Capabilities', '0x8F:1 ECAP'),
    5: ('PTx Regulation Control Status', '0x1E:3 RCS'),
    6: ('PTx Charge Status', '0x1F CHS'),
    7: ('PTx Estimated K', '0x3F:2 KEST'),
    9: ('PTx Error Status', '0x01 ERR'),
    10: ('PTx Power Modes Capabilities', '0x5A MODECAP'),
    11: ('PTx Power Modes Extended Capabilities', '0xA0 MODEXCAP'),
    12: ('PTx Mated-Q Results', '0x40 MATEDQ_RES'),
    13: ('PTx PLA_2 Parameters', '0x88 PLAP_2'),
    14: ('Reserved', None),
    15: ('PTx Gain Measurement Parameters', '0x61 GMP'),
    16: ('PTx Calibration Capabilities', '0x43 CAL_CAP'),
    17: ('PTx dPLoss Calibration Parameters', '0x54 dPCAL_PARAM'),
}

FOD_TYPE_LABELS = {
    0: 'FOD/qf — Reference Q-Factor',
    1: 'FOD/rf — Reference Resonance Frequency',
}

MSR_PREF = {
    0: 'No preference',
    1: 'Keep contract',
    2: 'Do not keep contract',
}

MSR_MAIN_MODE = {
    0: 'CPM (Continuous Power Mode)',
    1: 'NPM (Nominal Power Mode)',
    2: 'LPM (Low Power Mode)',
    3: 'HPM (High Power Mode)',
}

MSS_STATUS = {
    0: 'Success',
    1: 'Pending',
    2: 'Fail',
    3: 'Busy',
}

MSS_ERROR = {
    1: 'Not Supported',
}

SDSR_TYPES = {
    0: 'ACK',
    1: 'UNEXPECTED',
    2: 'ERR_BUSY',
    3: 'ERR_CRC',
}

# ASK 0x48 / FSK 0x4F — Table 63 Simultaneous Auxiliary Data Control Request
SADC_REQUESTS = {
    0: 'Reset all incoming and outgoing data transports (all streams)',
    1: 'Reset incoming and outgoing data transport for stream (stream header)',
    2: 'Close and abort data transport (stream header)',
    3: 'Close and complete data transport (stream header)',
    4: 'Open data transport (stream header)',
    5: 'Reserved',
    6: 'Reserved',
    7: 'Reserved',
}

MATEDQ_FO_RESULT = {
    0: 'Cannot compute',
    1: 'Safe',
    2: 'Unsafe',
    3: 'Uncertain',
}

MPP_TX_ERR_INFO = {
    1: 'Missing HPM coefficients',
    2: 'Measurement error',
}

CAL_ENTER_RESPONSE = {
    0: 'Reject',
    1: 'Accept',
}

CAL_ENTER_REASON = {
    3: 'FO_DETECTED',
}

CAL_OP_CODES = {
    0x01: 'COMMIT (commit calibration result)',
}

# ASK 0x96 — Table 72 CAL_CAPTURE Operation
CAL_CAPTURE_OPERATIONS = {
    0: 'Reserved',
    1: 'Clear point',
    2: 'Capture power parameters',
    3: 'Reserved',
}

# FSK 0x8F:1 ECAP — Table 93 PTx Power Limit Reason Code
PTX_POWER_LIMIT_REASON = {
    0: 'No Limit (Potential = Negotiable)',
    1: 'Reserved',
    2: 'Foreign Object Presence',
    3: 'Brown-Out Protection',
    4: 'Over Temperature',
    5: 'Maximum Inverter Voltage Reached',
    6: 'Over Current',
    7: 'Maximum Available Power',
    8: 'Active Power Mode',
    9: 'Reserved',
    10: 'Calibration Requirement Not Met',
}

PTX_XID_APP = {
    0: 'Magnetic Attachment (MPP fixed to 0)',
    1: 'Active Alignment',
}

# ASK 0x58:0 Report — Table 65 Report ID
REPORT_ID_TYPES = {
    0: 'Reserved',
    1: 'Reserved',
    2: 'PRx Identification',
    3: 'Reserved',
}

# ASK 0x58:1 PLA — Table 67 FSK Responses (参考)
PLA_FSK_RESPONSES = {
    'ACK': 'Power transfer safe (no foreign object)',
    'NAK': 'Possible foreign object — start power throttling',
    'ND': 'Not allowed',
    'ATN': 'PTx requests communication',
}

# WPC Power Receiver Manufacturer Codes (PRMC)
# Source: MT5820 qi.h — ManufacturerCodeType
# Keys are wire-format values after BE parse (_u16_be); qi.h enum values are byte-swapped.
PRMC_VENDORS = {
    0x0000: 'None',
    0x0010: 'Texas Instruments',
    0x0011: 'Fulton Innovation',
    0x0012: 'Philips',
    0x0013: 'Hanrim Postech',
    0x0014: 'Samsung',
    0x0015: 'HTC',
    0x0016: 'STMicroelectronics',
    0x0017: 'AVID Technologies',
    0x0018: 'Convenient Power',
    0x0019: 'Hosiden Corporation',
    0x0020: 'Atmel Semiconductor Technology',
    0x0021: 'Pantech',
    0x0022: 'LG Electronics',
    0x0023: 'Samsung Electromechanics',
    0x0024: 'nok9 AB',
    0x0025: 'Panasonic',
    0x0026: 'RRC Power Solutions',
    0x0027: 'Rohm',
    0x0028: 'Freescale Semiconductor',
    0x0029: 'Sony',
    0x002A: 'NXP Semiconductors',
    0x0030: 'Uway',
    0x0031: 'PowerKiss',
    0x0032: 'Triune Systems',
    0x0033: 'Toshiba',
    0x0034: 'IPAN',
    0x0035: 'Wisepower',
    0x0036: 'Opentech',
    0x0037: 'Richtek',
    0x0038: 'Logah Technology',
    0x0039: 'MediaTek',
    0x0040: 'Winstream Technology',
    0x0041: 'Adar Generale Telecom Services',
    0x0042: 'Samsung Electronics',
    0x0043: 'Ricoh',
    0x0044: 'ENE Technology',
    0x0045: 'Foxconn Interconnect Technology',
    0x0046: 'PowerbyProxi',
    0x0047: 'NewEdge Technologies',
    0x0048: 'E & E Magnetic Products',
    0x0049: 'Maxim Integrated',
    0x004A: 'Broadcom',
    0x004B: 'Parrot',
    0x004C: 'Wuxi China Resource Semico',
    0x004D: 'Generalplus',
    0x004E: 'Microchip',
    0x004F: 'Motorola Mobility',
    0x0050: 'IDT',
    0x0051: 'Copo Microelectronics',
    0x0052: 'Marvell',
    0x0053: 'Silicon Mitus',
    0x0054: 'Dyson Technology',
    0x0055: 'Continental Automotive',
    0x0056: 'Shenzhen Canpow Technology',
    0x0057: 'Knowmax Technology',
    0x0058: 'Tenx Technology',
    0x0059: 'E-Charging',
    0x005A: 'Apple',
    0x005B: 'EGLO Leuchten',
    0x005C: 'NuVolta Technologies',
    0x005D: 'Belkin',
    0x005E: 'mophie',
    0x005F: 'Xiamen Newyea Micro-electronics',
    0x0060: 'Huawei',
    0x0061: 'Celfras Semiconductor',
    0x0062: 'Bury',
    0x0063: 'LG Innotek',
    0x0064: 'Zinitix',
    0x0065: 'Shenzhen Chipsvision',
    0x0066: 'ASUSTek',
    0x0067: 'Infineon Technologies',
    0x0068: 'Shenzhen VLG Wireless Technology',
    0x0069: 'Shenzhen DBK Electronics',
    0x006A: 'Shanghai Magway Magnetic',
    0x006B: 'Halo Microelectronics',
    0x006C: 'Logitech',
    0x006D: 'Shenzhen BJX Industrial Development',
    0x006E: 'Xiaomi',
    0x006F: 'Powermat Technologies',
    0x0070: 'ZTE',
    0x0071: 'Scosche Industries',
    0x0072: 'Google',
    0x0073: 'Holtek Semiconductor',
    0x0074: 'Annex Products',
    0x0075: 'Weltrend Semiconductor',
    0x0076: 'Foryou Multimedia Electronics',
    0x0086: 'Maxic Technology / Tecno',
    0x008E: 'Anker Innovations',
    0x00A3: 'Hitachi-LG Data Storage',
    0x00A5: 'Apple',
    0x00A6: 'Ugreen Group',
    0x00B5: 'Zimi',
    0x00C1: 'Shenzhen Topband',
    0x00C7: 'Meizu',
    0x00CD: 'OnePlus',
    0x00D7: 'OPPO',
    0x00DB: 'Vivo',
    0x0136: 'WiTS',
    0x014C: 'Shounuoxin',
    0x0159: 'Google Pixel',
    0x015B: 'Seoul Nu Technology',
    0x018D: 'HMD',
    0x1201: 'Lantaisi',
    0x3433: 'Sanyo',
    0x3901: 'CRSPO',
    0xFCB1: 'LS Cable',
}

FSK_DEPTH_LABELS = {
    0: 'Depth 0',
    1: 'Depth 1',
    2: 'Depth 2',
    3: 'Depth 3',
}

RP_MODE_LABELS = {
    0: 'Default',
    1: 'In-band',
    2: 'Out-of-band',
}

# BPP ADT headers (docs/bpp_protocol.h)
BPP_ADT_HEADERS = frozenset({
    0x16, 0x17, 0x26, 0x27, 0x36, 0x37, 0x46, 0x47, 0x56, 0x57, 0x66, 0x67, 0x76, 0x77,
    0x98, 0x99,
})

# MPP ADT / PROP (docs/mpp_protocol.h comments)
MPP_PRX_ADT_HEADERS = frozenset({
    0x1A, 0x1B, 0x2A, 0x2B, 0x26, 0x36,
})
MPP_PTX_ADT_HEADERS = frozenset({
    0x1C, 0x1D, 0x2C, 0x2D, 0x3E, 0x4E,
})

# ---------------------------------------------------------------------------
# ASK 报文注册表 (PRx → PTx)
# profile: 'bpp' | 'mpp' | 'both'
# ---------------------------------------------------------------------------
ASK_PACKETS: dict[int, tuple[str, str, str]] = {
    # BPP baseline (0x01-0x09)
    0x01: ('SS', 'Signal Strength', 'bpp'),
    0x02: ('EPT', 'End Power Transfer', 'bpp'),
    0x03: ('CE', 'Control Error', 'bpp'),
    0x04: ('RP8', 'Received Power 8-bit', 'bpp'),
    0x05: ('CHS', 'Charge Status', 'bpp'),
    0x06: ('PCH', 'Power Control Hold-off', 'bpp'),
    0x07: ('GRQ', 'General Request', 'bpp'),
    0x09: ('NEGO', 'Renegotiate', 'bpp'),
    0x15: ('DSR', 'Data Stream Response', 'bpp'),
    0x20: ('SRQ', 'Specific Request', 'both'),
    0x22: ('FOD', 'FOD Status', 'bpp'),
    0x25: ('ADC', 'Auxiliary Data Control', 'bpp'),
    0x31: ('RP', 'Received Power 16-bit', 'bpp'),
    0x51: ('CFG', 'Configuration', 'bpp'),
    0x54: ('WPID/hi', 'WPID high segment', 'bpp'),
    0x55: ('WPID/lo', 'WPID low segment', 'bpp'),
    0x71: ('ID', 'Identification', 'bpp'),
    0x81: ('XID', 'Extended Identification', 'both'),
    # MPP extensions
    0x13: ('MSR', 'Mode Select Request', 'mpp'),
    0x18: ('CLOAK', 'Cloak Request', 'mpp'),
    0x19: ('XCE', 'Extended Control Error', 'mpp'),
    0x23: ('CAL_OP', 'Calibration Operation', 'mpp'),
    0x28: ('GET', 'Get Request', 'mpp'),
    0x29: ('EDS', 'Enabled Data Streams', 'mpp'),
    0x2C: ('CAL_ENTER', 'Enter Calibration', 'mpp'),
    0x2D: ('CAL_EXIT', 'Exit Calibration', 'mpp'),
    0x38: ('SDSR', 'Simultaneous Data Stream Response', 'mpp'),
    0x48: ('SADC', 'Simultaneous Auxiliary Data Control', 'mpp'),
    0x50: ('KEST_COEFF', 'K-est Coefficients', 'mpp'),
    0x58: ('REPORT/PLA', 'Report / PLA', 'mpp'),
    0x78: ('PLAP', 'Power Loss Accounting Parameters', 'mpp'),
    0x84: ('ECAP', 'Extended Capabilities', 'mpp'),
    0x88: ('PLA_2', 'Power Loss Accounting 2 (PLA 2)', 'mpp'),
    0x90: ('PLAP_2', 'PLA Parameters 2 (PLAP 2)', 'mpp'),
    0x96: ('CAL_CAPTURE', 'Calibration Capture', 'mpp'),
    0xA8: ('MATEDQ_COEFF', 'Mated-Q Coefficients', 'mpp'),
}

# ADT / PROP 动态长度包
for _h, _name in [
    (0x16, 'ADT/16'), (0x17, 'ADT/17'), (0x18, 'PROP/18'),
    (0x26, 'ADT/26'), (0x27, 'ADT/27'), (0x36, 'ADT/36'), (0x37, 'ADT/37'),
    (0x46, 'ADT/46'), (0x47, 'ADT/47'), (0x56, 'ADT/56'), (0x57, 'ADT/57'),
    (0x66, 'ADT/66'), (0x67, 'ADT/67'), (0x76, 'ADT/76'), (0x77, 'ADT/77'),
    (0x98, 'ADT/98'), (0x99, 'ADT/99'),
    (0x1A, 'PROP/1A'), (0x1B, 'PROP/1B'), (0x2A, 'PROP/2A'), (0x2B, 'PROP/2B'),
]:
    if _h not in ASK_PACKETS:
        ASK_PACKETS[_h] = (_name, f'Variable-length packet ({_name})', 'dynamic')

# ---------------------------------------------------------------------------
# FSK 报文注册表 (PTx → PRx)
# ---------------------------------------------------------------------------
FSK_PACKETS: dict[int, tuple[str, str, str]] = {
    # BPP
    0x00: ('NULL', 'Data Not Available', 'bpp'),
    0x15: ('DSR', 'Data Stream Response', 'bpp'),
    0x25: ('ADC', 'Auxiliary Data Control', 'bpp'),
    0x30: ('PTx_ID', 'Power Transmitter ID', 'bpp'),
    0x31: ('CAP', 'Capabilities', 'bpp'),
    0x32: ('XCAP', 'Extended Capabilities', 'bpp'),
    # MPP
    0x01: ('ERR', 'Error Status', 'mpp'),
    0x0A: ('EPTR', 'End Power Transfer Request', 'mpp'),
    0x13: ('MSN', 'Mode Selection Notification', 'mpp'),
    0x14: ('CAL_CAPTURE_RSP', 'Calibration Capture Response', 'mpp'),
    0x1B: ('CAL_OP_RSP', 'Calibration Operation Response', 'mpp'),
    0x1E: ('CLOAK/RCS', 'Cloak Response / Regulation Control Status', 'mpp'),
    0x1F: ('CHS', 'Charge Status', 'mpp'),
    0x23: ('MSS', 'Mode Select Status', 'mpp'),
    0x2E: ('GET', 'Get Request', 'mpp'),
    0x2F: ('EDS', 'Enabled Data Streams', 'mpp'),
    0x34: ('CAL_ENTER_RSP', 'Enter Calibration Response', 'mpp'),
    0x3F: ('INV/SDSR/KEST', 'Inverter Voltage / SDSR / K-est', 'mpp'),
    0x40: ('MATEDQ_RES', 'Mated-Q Results', 'mpp'),
    0x43: ('CAL_CAP', 'Calibration Capabilities', 'mpp'),
    0x4F: ('SADC', 'Simultaneous Auxiliary Data Control', 'mpp'),
    0x54: ('dPCAL_PARAM', 'Calibration Parameter', 'mpp'),
    0x5A: ('MODECAP', 'Power Modes Capabilities', 'mpp'),
    0x5F: ('PLAP', 'PLA Parameters', 'mpp'),
    0x61: ('GMP', 'Gain Measurement Parameters', 'mpp'),
    0x8F: ('XID/ECAP', 'Extended PTx ID / Extended Capabilities', 'mpp'),
    0xA0: ('MODEXCAP', 'Extended Power Modes Capabilities', 'mpp'),
}

# 裸 FSK 模式（无载荷）
for _h, (_n, _d) in FSK_BARE_PATTERNS.items():
    if _h not in FSK_PACKETS:
        FSK_PACKETS[_h] = (_n, _d, 'fsk_pattern')

# ADT / PROP
for _h, _name in [
    (0x1C, 'PROP/1C'), (0x1D, 'PROP/1D'), (0x26, 'ADT/26'), (0x27, 'ADT/27'),
    (0x2C, 'PROP/2C'), (0x2D, 'PROP/2D'), (0x36, 'ADT/36'), (0x37, 'ADT/37'),
    (0x3E, 'PROP/3E'), (0x46, 'ADT/46'), (0x47, 'ADT/47'), (0x4E, 'PROP/4E'),
    (0x56, 'ADT/56'), (0x57, 'ADT/57'), (0x66, 'ADT/66'), (0x67, 'ADT/67'),
    (0x76, 'ADT/76'), (0x77, 'ADT/77'),
]:
    if _h not in FSK_PACKETS:
        FSK_PACKETS[_h] = (_name, f'Variable-length packet ({_name})', 'dynamic')

# Qi 2.2.1 抓包常见额外 FSK 头（兼容）
FSK_PACKETS.setdefault(0x11, ('FAST-ACK', 'MPP Fast ACK', 'mpp'))
FSK_PACKETS.setdefault(0xFF, ('ACK', 'Acknowledge (Qi 2.2.1)', 'fsk_pattern'))
FSK_PACKETS.setdefault(0x33, ('ATN', 'Attention (Qi 2.2.1)', 'fsk_pattern'))
FSK_PACKETS.setdefault(0x55, ('ND/WPID', 'Not defined (Qi 2.2.1) / BPP ACK', 'fsk_pattern'))


def all_known_ask_headers() -> frozenset[int]:
    return frozenset(ASK_PACKETS.keys())


def all_known_fsk_headers() -> frozenset[int]:
    return frozenset(FSK_PACKETS.keys())
