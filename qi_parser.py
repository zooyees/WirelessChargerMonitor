# ==========================================
# Module: WPC Qi 2.2.1 协议深度解析引擎
# Author: Roy Zhao @ 御风智联
# Date: 2026-04-13
# ==========================================
import re

class Qi22Parser:
    def __init__(self):
        # 初始化解析字典，剥离主业务逻辑
        pass

    def parse_message(self, line):
        """主入口：解析原始串口行数据"""
        line = re.sub(r'\s+', ' ', line).strip() + " "
        if "ASK " in line:
            start = line.find("ASK ") + 4
            end = line.find(" F ", start)
            if end != -1: return self._decode_mpp_full(line[start:end].strip(), "ASK")
        if "FSK " in line:
            start = line.find("FSK ") + 4
            return self._decode_mpp_full(line[start:].strip().split('(')[0], "FSK")
        return None

    def _decode_mpp_full(self, hex_str, p_type):
        try:
            raw = [int(x, 16) for x in hex_str.replace('0x','').replace(',',' ').split()]
            if not raw: 
                return None
            header = raw[0]
            
            cs, payload, cs_st = None, raw[1:], "N/A"
            if len(raw) > 1:
                calc = 0
                for b in raw[:-1]: calc ^= b
                if calc == raw[-1]: 
                    cs, payload, cs_st = raw[-1], raw[1:-1], "<span style='color:#22C55E;'>✅ OK</span>"
                else: 
                    cs, payload, cs_st = raw[-1], raw[1:-1], "<span style='color:#EF4444;'>❌ ERR</span>"
            
            if p_type == "ASK": info, detail = self._ask_qi22_map(header, payload)
            else: info, detail = self._fsk_qi22_map(header, payload)

            title_color = '#38BDF8' if p_type == 'ASK' else '#FB923C'
            html = f"<div style='min-width: 200px; font-family: Consolas, monospace;'>"
            html += f"<b style='color:{title_color}; font-size: 11pt;'>{'🔵 ASK (PRx ➔ PTx)' if p_type=='ASK' else '🟠 FSK (PTx ➔ PRx)'}</b>"
            html += f"<hr style='border:1px solid #334155; margin: 5px 0;'>"
            html += f"<b>指令 Header:</b> <span style='color:#FACC15;'>0x{header:02X}</span> [{info}]<br>"
            html += f"<b>原始 Payload:</b> {' '.join([f'{x:02X}' for x in payload]) if payload else 'None'}<br>"
            if cs is not None: 
                html += f"<b>XOR 校验和:</b> 0x{cs:02X} ({cs_st})<br>"
            html += f"<hr style='border:1px dashed #334155; margin: 5px 0;'>"
            html += f"<b>📑 字节/位级深度破译:</b><br><div style='color:#E2E8F0; padding-top: 5px; line-height: 1.4;'>{detail}</div>"
            html += "</div>"
            return html
        except Exception as e: 
            return f"解析异常: {e}"

    def _ask_qi22_map(self, header, payload):
        d = {
            0x01: ("SIG", "信号强度 (Signal Strength)"),
            0x02: ("EPT", "停止充电 (End Power Transfer)"),
            0x03: ("CE", "控制误差 (Control Error)"),
            0x04: ("RP8", "接收功率 (8-bit Received Power)"),
            0x05: ("CHS", "充电状态 (Charge Status)"),
            0x06: ("PCH", "功率控制保持 (Power Control Hold-off)"),
            0x07: ("GRQ", "通用请求 (General Request)"),
            0x09: ("RENEG", "重新协商 (Renegotiate)"),
            0x22: ("FOD", "异物检测状态 (FOD Status)"),
            0x31: ("RP24", "接收功率 (24-bit Received Power)"),
            0x51: ("CFG", "配置数据包 (Configuration)"),
            0x71: ("ID", "身份识别数据包 (Identification)"),
            0x13:("MSR", " Mode Select Request"),
            0x18:("CLOAK", " Cloak Request"),
            0x19:("XCE", " Extended Control Error"),
            0x1A:("PROP/1a", " MPP PRx Proprietary Packet"),
            0x1B:("PROP/1b", " MPP PRx Proprietary Packet"),
            0x20:("SRQ", " Specific Request [PLA]"),
            0x23:("CAL_OP", " Calibration Operation"),
            0x26:("SADT/1e", " Simultaneous Auxiliary Data Transport (even)"),
            0x27:("SADT/1o", " Simultaneous Auxiliary Data Transport (odd)"), 
            0x28:("GET Get", " request"),
            0x29:("EDS", " Enabled Data Streams"),
            0x2A:("PROP/2a", " MPP PRx Proprietary Packet"),
            0x2B:("PROP/2b", " MPP PRx Proprietary Packet"),
            0x2C:("CAL_ENTER", " Enter Calibration"),
            0x2D:("CAL_EXIT", " Exit Calibration"),
            0x36:("SADT/2e", " Simultaneous Auxiliary Data Transport (even)"),
            0x37:("SADT/2o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x38:("SDSR", " Simultaneous Data Stream Response"),
            0x39:("PROP/39", " MPP PRx Proprietary Packet"),
            0x46:("SADT/3e", " Simultaneous Auxiliary Data Transport (even)"),
            0x47:("SADT/3o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x48:("SADC", " Simultaneous Auxiliary Data Control"),
            0x49:("PROP/49", " MPP PRx Proprietary Packet"),
            0x50:("KEST-COEFF", " K-est Coefficients"),
            0x56:("SADT/4e", " Simultaneous Auxiliary Data Transport (even)"),
            0x57:("SADT/4o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x58:("REPORT/PLA", " Report/Power Loss Accounting"),
            0x59:("PROP/59", " MPP PRx Proprietary Packet"),
            0x66:("SADT/5e", " Simultaneous Auxiliary Data Transport (even)"),
            0x67:("SADT/5o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x78:("PLAP", " Power Loss Accounting Parameters"),
            0x76:("SADT/6e", " Simultaneous Auxiliary Data Transport (even)"),
            0x77:("SADT/6o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x79:("PROP/79", " MPP PRx Proprietary Packet "),
            0x81:("MPP-XID", " MPP Extended Identification"),
            0x84:("ECAP", " Extended Received Capabilities"),
            0x85:("PROP/85", " MPP PRx Proprietary Packet "),
            0x88:("PLA_2", " Power Loss Accounting"),
            0x90:("PLAP_2", " Power Loss Accounting Parameters"),
            0x96:("CAL_CAPTURE", " Calibration Capture"),
            0xA8:("MATEDQ-COEFF", " Mated-Q Coefficients"),
        }
        name, _ = d.get(header, (f"UNK_0x{header:02X}", "未知/专有指令"))
        desc = ""
        plen = len(payload)

        if header == 0x01 and plen >= 1:
            val = payload[0]
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{val:02X}<br>"
            desc += f"  ↳ 耦合强度映射值: <b>{val}</b> / 255 ({(val/255)*100:.1f}%)"
        elif header == 0x02 and plen >= 1:
            e_map = {0x00: "未知", 0x01: "<span style='color:#22C55E'>充电完成</span>", 0x02: "<span style='color:#EF4444'>内部故障</span>", 0x03: "<span style='color:#EF4444'>过温</span>", 0x04: "<span style='color:#EF4444'>过压</span>", 0x05: "<span style='color:#EF4444'>过流</span>", 0x06: "<span style='color:#EF4444'>电池故障</span>", 0x0A: "重启传输", 0x0B: "<span style='color:#EF4444'>鉴权失败</span>"}
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X} ➔ <b>{e_map.get(payload[0], '保留原因')}</b>"
        elif header == 0x03 and plen >= 1:
            val = payload[0]
            ce = val - 256 if val > 127 else val
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{val:02X}<br>"
            desc += f"  ↳ 误差值 (Signed 8-bit): <b style='color:{'#22C55E' if ce<0 else '#EF4444'};'>{ce}</b><br>"
            desc += f"  <i>* 负值要求 PTx 降功率，正值要求升功率</i>"
        elif header == 0x04 and plen >= 1:
            val = payload[0]
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{val:02X}<br>"
            desc += f"  ↳ 接收功率比: <b>{val}</b> / 128 ({(val/128)*100:.1f}% Max Power)"
        elif header == 0x05 and plen >= 1:
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X} ➔ 电池电量: <b style='color:#22C55E'>{payload[0]} %</b>"
        elif header == 0x06 and plen >= 1:
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X} ➔ 保持时间: <b>{payload[0] * 10} ms</b>"
        elif header == 0x13 and plen >= 1:
            align = payload[0] & 0x0F
            couple = (payload[0] >> 4) & 0x0F
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X} (磁吸状态)<br>"
            desc += f"  ↳ 对齐质量 (Alignment) [Bit 0-3]: <b>{align}</b>/15<br>"
            desc += f"  ↳ 耦合强度 (Coupling)  [Bit 4-7]: <b>{couple}</b>/15<br>"
            if plen >= 2:
                flags = payload[1]
                desc += f"• <span style='color:#38BDF8'>Byte 1:</span> 0x{flags:02X} (PRx Flags)<br>"
                desc += f"  ↳ Bit 0 (过压保护): {'<b style=''color:#EF4444''>触发</b>' if flags & 0x01 else '正常'}<br>"
                desc += f"  ↳ Bit 1 (过流保护): {'<b style=''color:#EF4444''>触发</b>' if flags & 0x02 else '正常'}"
        elif header == 0x23 and plen >= 2:
            val = (payload[0] << 8) | payload[1]
            ce = val - 65536 if val > 32767 else val
            desc = f"• <span style='color:#38BDF8'>Byte 0-1:</span> 0x{payload[0]:02X} 0x{payload[1]:02X}<br>"
            desc += f"  ↳ 16-bit 高精度误差: <b style='color:{'#22C55E' if ce<0 else '#EF4444'};'>{ce}</b>"
        elif header == 0x28 and plen >= 1:
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X} ➔ 请求 PTx 发送 <b>0x{payload[0]:02X}</b> 报文"
        elif header == 0x31 and plen >= 3:
            mode = payload[0] & 0x07
            val = payload[1] | (payload[2] << 8)
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X} ➔ 功率计算模式: Mode <b>{mode}</b><br>"
            desc += f"• <span style='color:#38BDF8'>Byte 1-2:</span> 0x{payload[1]:02X} 0x{payload[2]:02X}<br>"
            desc += f"  ↳ 24-bit 接收功率参考值: <b>{val}</b>"
        elif header == 0x51 and plen >= 5:
            p_class = payload[0] >> 6
            max_p_val = payload[0] & 0x3F
            prop = (payload[1] >> 7) & 1
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X}<br>"
            desc += f"  ↳ 功率级别 (Power Class): Class <b>{p_class}</b><br>"
            desc += f"  ↳ 最大协商功率 (Max Pwr): <b>{max_p_val * 0.5:.1f} W</b><br>"
            desc += f"• <span style='color:#38BDF8'>Byte 1:</span> 0x{payload[1]:02X}<br>"
            desc += f"  ↳ 专有扩展标志 (Proprietary): <b>{'Yes' if prop else 'No'}</b><br>"
            desc += f"  ↳ 窗口极性/深度位掩码: [0x{payload[1]&0x7F:02X}]<br>"
            desc += f"• <span style='color:#38BDF8'>Byte 3:</span> 0x{payload[3]:02X} ➔ 期望包数 (Count): <b>{payload[3]}</b><br>"
            desc += f"• <span style='color:#38BDF8'>Byte 4:</span> 0x{payload[4]:02X} ➔ 窗口时间偏移 (Window Offset)"
        elif header == 0x71 and plen >= 7:
            ver_major = payload[0] >> 4
            ver_minor = payload[0] & 0x0F
            ext = (payload[0] >> 7) & 1
            ptmc = (payload[1] << 8) | payload[2]
            dev_id = f"{payload[3]:02X} {payload[4]:02X} {payload[5]:02X} {payload[6]:02X}"
            desc = f"• <span style='color:#38BDF8'>Byte 0:</span> 0x{payload[0]:02X}<br>"
            desc += f"  ↳ Qi 版本号: <b>{ver_major}.{ver_minor}</b> (Ext: {ext})<br>"
            desc += f"• <span style='color:#38BDF8'>Byte 1-2:</span> 0x{payload[1]:02X} 0x{payload[2]:02X}<br>"
            desc += f"  ↳ 制造商代码 (PTMC): <b>0x{ptmc:04X}</b><br>"
            desc += f"• <span style='color:#38BDF8'>Byte 3-6:</span> {dev_id}<br>"
            desc += f"  ↳ 基本设备 ID (Basic Device ID)"
        elif header in [0x48, 0x38, 0xA8]:
            desc = f"• 鉴权安全负载 (Auth Data Stream)<br>"
            desc += f"• 负载长度: <b>{plen} Bytes</b><br>"
            desc += f"• 报文片段: <span style='color:#94A3B8'>{' '.join([f'{b:02X}' for b in payload[:12]])} ...</span>"
        else:
            if not payload: desc = "<i>无 Payload (Empty Packet)</i>"
            else:
                desc = f"• 载荷长度: {plen} Bytes<br>"
                desc += f"• HEX: <span style='color:#94A3B8'>{' '.join([f'{b:02X}' for b in payload])}</span>"

        return name, desc

    def _fsk_qi22_map(self, header, payload):
        d = {
            0x00: ("NAK", "拒绝"),
            0x55: ("ND", "未定义 (Not Defined)"),
            0x33: ("ATN", "注意 (Attention)"),
            0xFF: ("ACK", "同意 (Acknowledge)"),
            0x01: ("ERR", "Error Status"),
            0x0A: ("EPTR", "End Power Transfer Request"),
            0x14: ("CAL_CAPTURE_RSP", " Calibration Capture Response"),
            0x1C: ("PROP/1c", " MPP PTx Proprietary Packet"),
            0x1B: ("CAL_OP_RSP", " Calibration Operation Response"),
            0x1D: ("PROP/1d MPP", " PTx Proprietary Packet"),
            0x1E: ("0x00 CLOAK", " Cloak Request"),
            0x1F: ("CHS", " Charge Status"),
            0x23: ("MSS", " Mode Select Status"),
            0x26: ("SADT/1e", " Simultaneous Auxiliary Data Transport (even)"),
            0x27: ("SADT/1o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x2C: ("PROP/2c", " MPP PTx Proprietary Packet"),
            0x2D: ("PROP/2d", " MPP PTx Proprietary Packet"),
            0x2E: ("GET", " Get Request"),
            0x2F: ("EDS", " Enabled Data Streams"),
            0x34: ("CAL_ENTER_RSP", " Enter Calibration Response"),
            0x36: ("SADT/2e", " Simultaneous Auxiliary Data Transport (even)"),
            0x37: ("SADT/2o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x3E: ("PROP/3e", " MPP PTx Proprietary Packet "),
            0x3F: ("INV/SDSR/KEST", "0x00:Inverter Voltage 0x01:Simultaneous Data Stream Response 0x02:Estimated K"),
            0x40: ("MATEDQ_RES", " Mated-Q Results "),
            0x43: ("CAL_CAP", " Calibration Capabilities "),
            0x46: ("SADT/3e", " Simultaneous Auxiliary Data Transport (even) "),
            0x47: ("SADT/3o", " Simultaneous Auxiliary Data Transport (odd) "),
            0x4E: ("PROP/4e", " MPP PTx Proprietary Packet "),
            0x4F: ("SADC", " Simultaneous Auxiliary Data Control "),
            0x54: ("dPCAL_PARAM", " Calibration Parameter "),
            0x56: ("SADT/4e", " Simultaneous Auxiliary Data Transport (even)"),
            0x57: ("SADT/4o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x5A: ("MODECAP", " Power Modes Capabilities"),
            0x5E: ("PROP/5e", " MPP PTx Proprietary Packet"),
            0x5F: ("PLAP", " Power Loss Accounting Parameters"),
            0x61: ("GMP", " Gain Measurement Parameters"),
            0x66: ("SADT/5e", " Simultaneous Auxiliary Data Transport (even)"),
            0x67: ("SADT/5o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x76: ("SADT/6e", " Simultaneous Auxiliary Data Transport (even)"),
            0x77: ("SADT/6o", " Simultaneous Auxiliary Data Transport (odd)"),
            0x88: ("PLAP_2", " Power Loss Accounting Parameters"),
            0x8E: ("PROP/8e", " MPP PTx Proprietary Packet"),
            0x8F: ("XID/ECAP", " 0x00:Extended Power Transmitter Identification 0x01:Extended Power Transmitter Extended Capabilities"),
            0xA0: ("MODEXCAP", " Power Modes Extended Capabilities"),
        }
        name, _ = d.get(header, (f"UNK_0x{header:02X}", "扩展/专有 FSK 指令"))
        desc = ""
        plen = len(payload)

        if header == 0x01: desc = "<b style='color:#22C55E'>✓ ACK (接受/确认上一条 PRx 指令)</b>"
        elif header == 0x02: desc = "<b style='color:#EF4444'>✗ NACK (拒绝/条件不支持)</b>"
        elif header == 0x03: desc = "<b style='color:#FACC15'>⚠ ND (指令格式不识别)</b>"
        elif header == 0x09 and plen >= 1:
            r = {0x00: "<b style='color:#22C55E'>ACK</b>", 0x01: "<b style='color:#EF4444'>NACK</b>", 0x02: "<b style='color:#FACC15'>ND</b>", 0x03: "<b style='color:#38BDF8'>ATN</b>"}
            desc = f"• <span style='color:#FB923C'>Byte 0:</span> 0x{payload[0]:02X} ➔ 响应类型: {r.get(payload[0], 'Reserved')}"
        elif header == 0x40 and plen >= 1:
            flags = payload[0]
            desc = f"• <span style='color:#FB923C'>Byte 0:</span> 0x{flags:02X} (PTx 状态标志位图)<br>"
            desc += f"  ↳ Bit 0 (功率限制): {'<b style=''color:#EF4444''>触发降额</b>' if flags & 0x01 else '未激活'}<br>"
            desc += f"  ↳ Bit 1 (温度限制): {'<b style=''color:#EF4444''>触发过温保护</b>' if flags & 0x02 else '未激活'}<br>"
            desc += f"  ↳ Bit 2 (疑似异物 FOD): {'<b style=''color:#EF4444''>报警 (FOD)</b>' if flags & 0x04 else '<b style=''color:#22C55E''>正常</b>'}<br>"
            desc += f"  ↳ Bit 3 (鉴权状态): {'<b style=''color:#38BDF8''>处理中/完成</b>' if flags & 0x08 else '无鉴权'}"
        elif header == 0x43 and plen >= 2:
            max_p = payload[0] * 0.5
            auth_cap = (payload[1] >> 4) & 1
            desc = f"• <span style='color:#FB923C'>Byte 0:</span> 0x{payload[0]:02X}<br>"
            desc += f"  ↳ PTx 保证输出功率 (Guaranteed): <b>{max_p:.1f} W</b><br>"
            desc += f"• <span style='color:#FB923C'>Byte 1:</span> 0x{payload[1]:02X}<br>"
            desc += f"  ↳ 鉴权硬件 (Auth Capable): <b>{'具备' if auth_cap else '不具备'}</b>"
        elif header in [0x11, 0x76, 0x77]:
            desc = f"• PTx 鉴权下行安全通道 (Security Channel)<br>"
            desc += f"• 负载长度: <b>{plen} Bytes</b><br>"
            if plen > 0:
                desc += f"• 报文片段: <span style='color:#94A3B8'>{' '.join([f'{b:02X}' for b in payload[:12]])} ...</span>"
        else:
            if not payload: desc = "<i>无 Payload (Empty Packet)</i>"
            else:
                desc = f"• 载荷长度: {plen} Bytes<br>"
                desc += f"• HEX: <span style='color:#94A3B8'>{' '.join([f'{b:02X}' for b in payload])}</span>"
        
        return name, desc