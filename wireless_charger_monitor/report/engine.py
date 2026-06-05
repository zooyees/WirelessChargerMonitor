# ==========================================
# Module: 无线充电测试报告 PDF 生成引擎
# ==========================================
import math
import os
import datetime
import platform
import sys
import tempfile
import logging
import uuid

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether,
)
from reportlab.pdfgen import canvas

logger = logging.getLogger('WirelessChargerMonitor.report')

REPORT_VERSION = '2.2'
PROTOCOL_VERSION = 'Qi 2.2.1'
SOFTWARE_NAME = '手机无线充电监控系统'
DOCUMENT_CLASS = '内部测试记录'
MIN_SAMPLES_FOR_VALID = 10

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm

C_PRIMARY = colors.HexColor('#0EA5E9')
C_DARK = colors.HexColor('#0F172A')
C_TEXT = colors.HexColor('#334155')
C_MUTED = colors.HexColor('#64748B')
C_SUCCESS = colors.HexColor('#22C55E')
C_WARNING = colors.HexColor('#FACC15')
C_DANGER = colors.HexColor('#EF4444')
C_PURPLE = colors.HexColor('#A855F7')
C_PASS_BG = colors.HexColor('#DCFCE7')
C_WARN_BG = colors.HexColor('#FEF9C3')
C_FAIL_BG = colors.HexColor('#FEE2E2')
C_COVER_BG = colors.HexColor('#F8FAFC')
C_COVER_BORDER = colors.HexColor('#E2E8F0')
C_COVER_TITLE = colors.HexColor('#0F172A')
C_COVER_SUB = colors.HexColor('#475569')
C_COVER_META = colors.HexColor('#334155')


def _register_cjk_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular, bold = 'Helvetica', 'Helvetica-Bold'
    pairs = [
        ('YaHei', 'YaHei-Bold', r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\msyhbd.ttc'),
        ('SimHei', 'SimHei-Bold', r'C:\Windows\Fonts\simhei.ttf', r'C:\Windows\Fonts\simhei.ttf'),
        ('SimSun', 'SimSun-Bold', r'C:\Windows\Fonts\simsun.ttc', r'C:\Windows\Fonts\simsun.ttc'),
    ]
    for reg_name, bold_name, reg_path, bold_path in pairs:
        if os.path.exists(reg_path):
            try:
                pdfmetrics.registerFont(TTFont(reg_name, reg_path))
                regular = reg_name
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                    bold = bold_name
                else:
                    bold = reg_name
                return regular, bold
            except Exception as e:
                logger.debug("Font register failed %s: %s", reg_path, e)
    return regular, bold


def _build_styles(font_name, font_bold):
    return {
        'cover_title': ParagraphStyle(
            'CoverTitle', fontName=font_bold, fontSize=26, leading=32,
            textColor=C_COVER_TITLE, alignment=TA_CENTER, spaceAfter=6,
        ),
        'cover_sub': ParagraphStyle(
            'CoverSub', fontName=font_name, fontSize=10, leading=14,
            textColor=C_COVER_SUB, alignment=TA_CENTER,
        ),
        'cover_meta': ParagraphStyle(
            'CoverMeta', fontName=font_name, fontSize=9.5, leading=15,
            textColor=C_COVER_META, alignment=TA_LEFT,
        ),
        'section': ParagraphStyle(
            'Section', fontName=font_bold, fontSize=13, leading=17,
            textColor=C_DARK, spaceBefore=12, spaceAfter=6,
        ),
        'body': ParagraphStyle(
            'Body', fontName=font_name, fontSize=9, leading=13, textColor=C_TEXT,
        ),
        'small': ParagraphStyle(
            'Small', fontName=font_name, fontSize=8, leading=11, textColor=C_MUTED,
        ),
        'cell_bold': ParagraphStyle(
            'CellBold', fontName=font_bold, fontSize=9, leading=12, textColor=C_DARK,
        ),
        'alert': ParagraphStyle(
            'Alert', fontName=font_name, fontSize=8, leading=11, textColor=C_DANGER,
        ),
        'event': ParagraphStyle(
            'Event', fontName=font_name, fontSize=8, leading=11, textColor=C_TEXT,
        ),
        'body_indent': ParagraphStyle(
            'BodyIndent', fontName=font_name, fontSize=9, leading=13, textColor=C_TEXT,
            leftIndent=12, spaceAfter=4,
        ),
        'toc': ParagraphStyle(
            'TOC', fontName=font_name, fontSize=9, leading=14, textColor=C_TEXT,
            leftIndent=8,
        ),
        'figure': ParagraphStyle(
            'Figure', fontName=font_name, fontSize=8, leading=11, textColor=C_MUTED,
            alignment=TA_CENTER, spaceAfter=6,
        ),
    }


class _NumberedCanvas(canvas.Canvas):


    def __init__(self, *args, session_label='', font_name='Helvetica', **kwargs):
        self._session_label = session_label
        self._font_name = font_name
        super().__init__(*args, **kwargs)
        self._saved_page_states = []


    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()


    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_decor(total)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


    def _draw_page_decor(self, page_count):
        if self._pageNumber == 1:
            return
        self.saveState()
        self.setStrokeColor(C_PRIMARY)
        self.setLineWidth(1.5)
        self.line(MARGIN, PAGE_H - 1.15 * cm, PAGE_W - MARGIN, PAGE_H - 1.15 * cm)
        self.setFont(self._font_name, 7)
        self.setFillColor(C_MUTED)
        self.drawString(MARGIN, PAGE_H - 0.95 * cm, f'{SOFTWARE_NAME} · 测试报告 v{REPORT_VERSION}')
        if self._session_label:
            self.drawCentredString(PAGE_W / 2, PAGE_H - 0.95 * cm, self._session_label)
        self.drawRightString(PAGE_W - MARGIN, 0.75 * cm, f'第 {self._pageNumber} / {page_count} 页')
        self.drawString(MARGIN, 0.75 * cm, datetime.datetime.now().strftime('%Y-%m-%d'))
        self.restoreState()


def _section_block(title, styles):
    bar = Table([['']], colWidths=[0.12 * cm], rowHeights=[0.5 * cm])
    bar.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), C_PRIMARY), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    header = Table([[bar, Paragraph(title, styles['section'])]], colWidths=[0.2 * cm, PAGE_W - 2 * MARGIN - 0.2 * cm])
    header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return header


def _kpi_card(label, value, unit, accent, font_name, font_bold, card_w):
    unit_html = f' <font color="#64748B" size="8">{unit}</font>' if unit else ''
    data = [
        [Paragraph(
            f'<font color="{accent.hexval()}"><b>{value}</b></font>{unit_html}',
            ParagraphStyle(
                'kv', fontName=font_bold, fontSize=13, leading=16,
                alignment=TA_CENTER, wordWrap='CJK',
            ),
        )],
        [Paragraph(
            label,
            ParagraphStyle(
                'kl', fontName=font_name, fontSize=8, leading=10,
                alignment=TA_CENTER, textColor=C_MUTED,
            ),
        )],
    ]
    t = Table(data, colWidths=[card_w], rowHeights=[24, 14])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('LINEBELOW', (0, 0), (-1, 0), 2.5, accent),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


def _kpi_row(cards, content_w):
    gap = 0.12 * cm
    card_w = (content_w - gap * (len(cards) - 1)) / len(cards)
    row = Table([cards], colWidths=[card_w] * len(cards), hAlign='LEFT')
    row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return row


def _verdict_badge(verdict, font_bold):
    cfg = {
        'PASS': (C_PASS_BG, C_SUCCESS, '测试通过', '全部指标正常，未发现安全告警'),
        'WARN': (C_WARN_BG, colors.HexColor('#CA8A04'), '测试警告', '存在告警或演示数据，请人工复核'),
        'FAIL': (C_FAIL_BG, C_DANGER, '测试未通过', '触发严重安全告警，不建议判定为合格'),
    }
    bg, fg, title, desc = cfg.get(verdict, cfg['WARN'])
    inner = Table([
        [Paragraph(f'<font color="{fg.hexval()}"><b>{title}</b></font>',
                   ParagraphStyle('vt', fontName=font_bold, fontSize=14, leading=18, alignment=TA_CENTER))],
        [Paragraph(desc, ParagraphStyle('vd', fontName=font_bold, fontSize=8, leading=11,
                                        alignment=TA_CENTER, textColor=C_MUTED))],
    ], colWidths=[5.5 * cm])
    inner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('BOX', (0, 0), (-1, -1), 1, fg),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    return inner


def _format_duration(seconds):
    if seconds < 60:
        return f'{seconds:.1f} 秒'
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f'{minutes} 分 {secs} 秒'
    hours, minutes = divmod(minutes, 60)
    return f'{hours} 时 {minutes} 分 {secs} 秒'


def _format_hms(seconds):
    total = int(max(0, seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f'{h:02d}:{m:02d}:{s:02d}'
    return f'{m:02d}:{s:02d}'


def _percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return ordered[int(k)]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def _std_dev(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def _result_cell(text, font_name, font_bold, styles):
    color = {
        '符合': C_SUCCESS, '不符合': C_DANGER, '警告': colors.HexColor('#CA8A04'), 'N/A': C_MUTED,
    }.get(text, C_TEXT)
    return Paragraph(
        f'<font color="{color.hexval()}"><b>{text}</b></font>',
        ParagraphStyle('rc', fontName=font_bold, fontSize=9, leading=12, alignment=TA_CENTER),
    )


def _compute_stats(metrics_rows):
    if not metrics_rows:
        return {}
    n = len(metrics_rows)
    powers = [r[8] for r in metrics_rows]
    temps = [r[9] for r in metrics_rows]
    effs = [r[7] for r in metrics_rows if r[7] > 0]
    bats = [r[10] for r in metrics_rows]
    v_ins = [r[1] for r in metrics_rows]
    i_ins = [r[2] for r in metrics_rows]
    duration = metrics_rows[-1][0] - metrics_rows[0][0] if n > 1 else 0.0

    energy_ws = input_ws = 0.0
    max_gap = 0.0
    for i in range(1, n):
        dt = metrics_rows[i][0] - metrics_rows[i - 1][0]
        if dt > 0:
            max_gap = max(max_gap, dt)
            p_avg = (metrics_rows[i][8] + metrics_rows[i - 1][8]) / 2
            pin_avg = (metrics_rows[i][1] * metrics_rows[i][2] + metrics_rows[i - 1][1] * metrics_rows[i - 1][2]) / 2
            energy_ws += p_avg * dt
            input_ws += pin_avg * dt

    sample_rate = n / duration if duration > 0.1 else 0.0
    expected = duration * sample_rate if sample_rate > 0 else n
    completeness = min(100.0, n / expected * 100) if expected > 0 else 100.0

    return {
        'samples': n,
        'duration': duration,
        'duration_text': _format_duration(duration),
        'duration_hms': _format_hms(duration),
        'sample_rate': sample_rate,
        'max_gap': max_gap,
        'completeness': completeness,
        'energy_wh': energy_ws / 3600.0,
        'input_energy_wh': input_ws / 3600.0,
        'max_p': max(powers), 'min_p': min(powers), 'avg_p': sum(powers) / n,
        'p95_p': _percentile(powers, 95), 'std_p': _std_dev(powers),
        'max_t': max(temps), 'min_t': min(temps), 'avg_t': sum(temps) / n,
        'temp_rise': max(temps) - min(temps),
        'max_eff': max(effs) if effs else 0, 'min_eff': min(effs) if effs else 0,
        'avg_eff': sum(effs) / len(effs) if effs else 0,
        'bat_start': bats[0], 'bat_end': bats[-1],
        'max_v_in': max(v_ins), 'min_v_in': min(v_ins), 'avg_v_in': sum(v_ins) / n,
        'max_v_out': max(r[3] for r in metrics_rows), 'max_i_in': max(i_ins), 'max_i_out': max(r[4] for r in metrics_rows),
        'avg_i_in': sum(i_ins) / n,
        'avg_v_bat': sum(r[5] for r in metrics_rows) / n,
        't_start': metrics_rows[0][0], 't_end': metrics_rows[-1][0],
    }


def _analyze_phases(metrics_rows):
    if len(metrics_rows) < 20:
        return {}
    cc = cv = trickle = idle = 0
    for i, r in enumerate(metrics_rows):
        p, ib = r[8], r[6]
        if p < 0.5:
            idle += 1
        elif ib < 0.15:
            trickle += 1
        else:
            vb0 = metrics_rows[max(0, i - 20)][5]
            ib0 = metrics_rows[max(0, i - 20)][6]
            dv, di = r[5] - vb0, r[6] - ib0
            if abs(dv) <= 0.05 and di < -0.05:
                cv += 1
            elif dv > 0.02:
                cc += 1
    total = len(metrics_rows)
    return {
        'cc_pct': cc / total * 100, 'cv_pct': cv / total * 100,
        'trickle_pct': trickle / total * 100, 'idle_pct': idle / total * 100,
    }


def _evaluate_verdict(session_info, alert_logs, stats, compliance_rows=None):
    if session_info.get('demo_mode'):
        return 'WARN'
    critical = sum(1 for log in alert_logs if '🚨' in log or '硬件保护' in log)
    if critical > 0:
        return 'FAIL'
    if compliance_rows and any(r['result'] == '不符合' for r in compliance_rows):
        return 'FAIL'
    if alert_logs:
        return 'WARN'
    if stats.get('samples', 0) < MIN_SAMPLES_FOR_VALID:
        return 'WARN'
    return 'PASS'


def _build_compliance(stats, config, alert_logs, session_info):
    alerts = config.get('alerts', {})
    ovp = alerts.get('ovp_threshold', 25.0)
    ocp = alerts.get('ocp_threshold', 3.0)
    otp = alerts.get('temp_warning_threshold', 60)
    critical = sum(1 for log in alert_logs if '🚨' in log or '硬件保护' in log)

    def _check(item_id, item, criterion, measured, ok, warn=False):
        if session_info.get('demo_mode') and item_id.startswith('C-0'):
            result = 'N/A'
        elif ok:
            result = '符合'
        elif warn:
            result = '警告'
        else:
            result = '不符合'
        return {'id': item_id, 'item': item, 'criterion': criterion, 'measured': measured, 'result': result}

    rows = [
        _check('C-01', '输入过压 OVP', f'Vin ≤ {ovp:.1f} V', f"{stats.get('max_v_in', 0):.3f} V",
               stats.get('max_v_in', 0) <= ovp),
        _check('C-02', '输入过流 OCP', f'Iin ≤ {ocp:.1f} A', f"{stats.get('max_i_in', 0):.3f} A",
               stats.get('max_i_in', 0) <= ocp),
        _check('C-03', '线圈过温 OTP', f'T ≤ {otp:.0f} °C', f"{stats.get('max_t', 0):.1f} °C",
               stats.get('max_t', 0) <= otp),
        _check('C-04', '采样完整性', f'有效采样 ≥ {MIN_SAMPLES_FOR_VALID} 点',
               f"{stats.get('samples', 0)} 点", stats.get('samples', 0) >= MIN_SAMPLES_FOR_VALID),
        _check('C-05', '测试时长', '有效时长 ≥ 5 s', stats.get('duration_text', '-'),
               stats.get('duration', 0) >= 5.0),
        _check('C-06', '严重保护事件', '无硬件保护/严重告警',
               f'{critical} 次' if critical else '无', critical == 0),
        _check('C-07', '传输效率', '平均效率 > 0（有效传输）',
               f"{stats.get('avg_eff', 0):.1f} %", stats.get('avg_eff', 0) > 0, warn=stats.get('avg_eff', 0) == 0),
    ]
    if alert_logs:
        rows.append(_check('C-08', '安全告警记录', '无未处理告警',
                           f'{len(alert_logs)} 条', False, warn=True))
    else:
        rows.append(_check('C-08', '安全告警记录', '无未处理告警', '无', True))
    return rows


def _compliance_table(compliance_rows, font_name, font_bold, styles, content_w):
    header = [
        Paragraph('<b>编号</b>', styles['cell_bold']),
        Paragraph('<b>检查项目</b>', styles['cell_bold']),
        Paragraph('<b>判定准则</b>', styles['cell_bold']),
        Paragraph('<b>实测值</b>', styles['cell_bold']),
        Paragraph('<b>结果</b>', styles['cell_bold']),
    ]
    data = [header]
    for row in compliance_rows:
        data.append([
            row['id'], row['item'], row['criterion'], row['measured'],
            _result_cell(row['result'], font_name, font_bold, styles),
        ])
    widths = [1.2 * cm, 3.2 * cm, 4.5 * cm, 3.5 * cm, 1.8 * cm]
    t = Table(data, colWidths=widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E0F2FE')),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#BAE6FD')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (4, 0), (4, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
    ]))
    return t


def _downsample(rows, max_points=1200):
    if len(rows) <= max_points:
        return rows
    step = len(rows) // max_points
    return rows[::step]


def _generate_chart_images(metrics_rows, temp_dir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    rows = _downsample(metrics_rows)
    if not rows:
        return []

    t = [r[0] for r in rows]
    col_idx = {
        'v_in': 1, 'i_in': 2, 'v_out': 3, 'i_out': 4, 'v_bat': 5,
        'i_bat': 6, 'eff': 7, 'power': 8, 'temp': 9, 'battery': 10,
    }
    charts = [
        ('power', '输出功率', [('power', '#A855F7', 'P (W)')]),
        ('input', '输入端电压 / 电流', [('v_in', '#FACC15', 'Vin (V)'), ('i_in', '#22C55E', 'Iin (A)')]),
        ('output', '输出端电压 / 电流', [('v_out', '#FACC15', 'Vout (V)'), ('i_out', '#22C55E', 'Iout (A)')]),
        ('battery', '电池端电压 / 电流', [('v_bat', '#FACC15', 'Vbat (V)'), ('i_bat', '#22C55E', 'Ibat (A)')]),
        ('eff_temp', '传输效率 / 线圈温度', [('eff', '#38BDF8', 'Eff (%)'), ('temp', '#FB923C', 'Temp (°C)')]),
    ]
    plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'Arial'], 'axes.unicode_minus': False})
    paths = []

    for key, title, series in charts:
        fig, ax1 = plt.subplots(figsize=(7.4, 2.5), dpi=160)
        fig.patch.set_facecolor('#0F172A')
        ax1.set_facecolor('#0F172A')
        ax1.set_title(title, color='#CBD5E1', fontsize=10, fontweight='bold', pad=8)
        ax1.text(0.99, 0.02, f'n={len(rows)}', transform=ax1.transAxes, ha='right', va='bottom',
                 color='#64748B', fontsize=6)
        ax1.tick_params(colors='#64748B', labelsize=7)
        ax1.set_xlabel('时间 (s)', color='#64748B', fontsize=7)
        for spine in ax1.spines.values():
            spine.set_color('#334155')

        k0, c0, l0 = series[0]
        ax1.plot(t, [r[col_idx[k0]] for r in rows], color=c0, linewidth=1.6, label=l0)
        ax1.set_ylabel(l0, color=c0, fontsize=7)
        ax1.grid(True, alpha=0.12, color='#64748B', linestyle='--')

        if len(series) > 1:
            ax2 = ax1.twinx()
            k1, c1, l1 = series[1]
            ax2.plot(t, [r[col_idx[k1]] for r in rows], color=c1, linewidth=1.3, label=l1)
            ax2.set_ylabel(l1, color=c1, fontsize=7)
            ax2.tick_params(colors='#64748B', labelsize=7)
            for spine in ax2.spines.values():
                spine.set_color('#334155')

        path = os.path.join(temp_dir, f'chart_{key}.png')
        fig.tight_layout()
        fig.savefig(path, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
        plt.close(fig)
        paths.append((title, path))
    return paths


def _styled_table(rows, col_widths, font_name, header_bg='#E0F2FE', header_row=True):
    t = Table(rows, colWidths=col_widths)
    style_cmds = [
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
    ]
    if header_row:
        style_cmds.insert(0, ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(header_bg)))
        style_cmds.append(('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]))
    else:
        style_cmds.append(('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]))
    t.setStyle(TableStyle(style_cmds))
    return t


def _document_control_page(report_id, generated_at, session_info, font_name, styles, content_w):
    host = platform.node() or '-'
    py_ver = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
    blocks = []
    blocks.append(_section_block('文档说明与使用限制', styles))
    blocks.append(Spacer(1, 6))
    blocks.append(Paragraph(
        '本报告由手机无线充电监控系统自动生成，用于记录单次 Qi 无线充电测试会话的电气参数、'
        '安全事件及过程波形。报告结论基于系统配置的阈值与启发式算法，'
        '<b>不构成型式认证或第三方检测报告</b>，正式交付前须由授权人员复核。',
        styles['body'],
    ))
    blocks.append(Spacer(1, 10))
    blocks.append(_styled_table([
        [Paragraph('<b>项目</b>', styles['cell_bold']), Paragraph('<b>内容</b>', styles['cell_bold']),
         Paragraph('<b>项目</b>', styles['cell_bold']), Paragraph('<b>内容</b>', styles['cell_bold'])],
        ['文档名称', '无线充电测试分析报告', '文档密级', DOCUMENT_CLASS],
        ['报告编号', report_id, '报告版本', f'v{REPORT_VERSION}'],
        ['生成系统', SOFTWARE_NAME, '生成时间', generated_at],
        ['运行主机', host, 'Python 版本', py_ver],
        ['协议标准', PROTOCOL_VERSION, '数据模式',
         '演示模式（无效力）' if session_info.get('demo_mode') else '真实串口采集'],
    ], [3.0 * cm, 5.5 * cm, 3.0 * cm, 5.5 * cm], font_name, header_bg='#F1F5F9'))
    blocks.append(Spacer(1, 14))
    blocks.append(_section_block('目录', styles))
    blocks.append(Spacer(1, 6))
    toc_items = [
        '1. 测试执行摘要',
        '2. 测试范围与方法',
        '3. 测量结果与符合性评估',
        '4. 安全告警与保护事件',
        '5. 充电过程波形记录',
        '6. 数据质量说明',
        '7. 测试结论与判定',
        '8. 附录 — 术语、环境与签审',
    ]
    for item in toc_items:
        blocks.append(Paragraph(item, styles['toc']))
    return blocks


def _methodology_section(config, session_info, stats, styles):
    alerts = config.get('alerts', {})
    ui_cfg = config.get('ui', {})
    blocks = [
        _section_block('2. 测试范围与方法', styles),
        Spacer(1, 6),
        Paragraph('<b>2.1 测试目的</b>', styles['body']),
        Paragraph(
            '验证被测无线充电链路在完整充电周期内的输入/输出电气特性、传输效率、线圈温升及保护响应，'
            '为设计迭代、可靠性评估与问题定位提供可追溯的量化记录。',
            styles['body_indent'],
        ),
        Spacer(1, 6),
        Paragraph('<b>2.2 测试对象与接口</b>', styles['body']),
        Paragraph(
            f'通信接口：串口 {session_info.get("port", "-")}，波特率 {session_info.get("baudrate", "-")} bps；'
            f'协议参照 {PROTOCOL_VERSION} 数据帧解析；采样时间基准为会话相对时间（t=0 为会话开始）。',
            styles['body_indent'],
        ),
        Spacer(1, 6),
        Paragraph('<b>2.3 测量参数</b>', styles['body']),
        Paragraph(
            'Vin / Iin（输入端）、Vout / Iout（无线输出端）、Vbat / Ibat（电池等效端）、'
            'Pout（输出功率）、Eff（传输效率）、Tcoil（线圈温度）、SOC（电量百分比）。',
            styles['body_indent'],
        ),
        Spacer(1, 6),
        Paragraph('<b>2.4 采样与判定配置</b>', styles['body']),
    ]
    cfg_table = _styled_table([
        ['UI 刷新周期', f"{ui_cfg.get('render_interval_ms', 100)} ms",
         '图表窗口', f"{ui_cfg.get('default_window_size_sec', 60)} s"],
        ['OVP 阈值', f"{alerts.get('ovp_threshold', 25.0)} V",
         'OCP 阈值', f"{alerts.get('ocp_threshold', 3.0)} A"],
        ['OTP 阈值', f"{alerts.get('temp_warning_threshold', 60)} °C",
         'OTP 恢复', f"{alerts.get('temp_recovery_threshold', 55)} °C"],
        ['满电判定去抖', f"{alerts.get('full_charge_debounce_sec', 20)} s",
         '有效采样数', f"{stats.get('samples', 0)} 点"],
    ], [3.4 * cm, 4.3 * cm, 3.4 * cm, 4.3 * cm], styles['body'].fontName, header_bg='#F0F9FF')
    blocks.extend([cfg_table, Spacer(1, 6)])
    blocks.append(Paragraph(
        '<b>2.5 阶段划分方法</b>：恒流（CC）、恒压（CV）、涓流及待机阶段依据 Vbat/Ibat 变化率启发式推断，'
        '与 BMS 内部状态可能存在偏差，仅供过程分析参考。',
        styles['body'],
    ))
    return blocks


class ReportEngine:
    @staticmethod
    def generate(filename, session_info, metrics_rows, alert_logs, config=None, key_events=None):
        config = config or {}
        key_events = key_events or []
        font_name, font_bold = _register_cjk_fonts()
        styles = _build_styles(font_name, font_bold)
        stats = _compute_stats(metrics_rows)
        phases = _analyze_phases(metrics_rows)
        compliance_rows = _build_compliance(stats, config, alert_logs, session_info)
        verdict = _evaluate_verdict(session_info, alert_logs, stats, compliance_rows)
        pass_count = sum(1 for r in compliance_rows if r['result'] == '符合')
        report_id = f"RPT-{datetime.datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        generated_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        temp_dir = tempfile.mkdtemp(prefix='qi_report_')
        chart_items = _generate_chart_images(metrics_rows, temp_dir)

        sid = session_info.get('session_id', '-')
        suuid = session_info.get('session_uuid', '')
        session_label = f"会话 #{sid}" + (f" ({suuid})" if suuid else '')

        doc = SimpleDocTemplate(
            filename, pagesize=A4,
            leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=1.55 * cm, bottomMargin=1.35 * cm,
        )


        def _canvas_maker(filename_, **kwargs):
            return _NumberedCanvas(filename_, session_label=session_label, font_name=font_name, **kwargs)

        story = []
        content_w = PAGE_W - 2 * MARGIN

        # ========== 封面 ==========
        meta_lines = [
            f"<b>报告编号</b>　{report_id}",
            f"<b>会话编号</b>　#{sid}　　<b>UUID</b>　{suuid or '-'}",
            f"<b>测试时间</b>　{session_info.get('started_at', '-')} — {session_info.get('ended_at') or '进行中'}",
            f"<b>通信端口</b>　{session_info.get('port', '-')} @ {session_info.get('baudrate', '-')} bps",
            f"<b>协议标准</b>　{PROTOCOL_VERSION}　　<b>数据模式</b>　{'演示模式' if session_info.get('demo_mode') else '真实采集'}",
            f"<b>文档密级</b>　{DOCUMENT_CLASS}　　<b>报告版本</b>　v{REPORT_VERSION}",
            f"<b>生成时间</b>　{generated_at}",
        ]
        cover_accent = Table([['']], colWidths=[content_w], rowHeights=[0.18 * cm])
        cover_accent.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C_PRIMARY),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        cover_rows = [
            [cover_accent],
            [Spacer(1, 0.45 * cm)],
            [Paragraph('无线充电测试分析报告', styles['cover_title'])],
            [Paragraph('Wireless Charging Test Analysis Report', styles['cover_sub'])],
            [Spacer(1, 0.35 * cm)],
            [Paragraph('<br/>'.join(meta_lines), styles['cover_meta'])],
            [Spacer(1, 0.4 * cm)],
            [Table([[ _verdict_badge(verdict, font_bold) ]], colWidths=[content_w],
                   style=TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))],
            [Spacer(1, 0.3 * cm)],
            [Paragraph(
                f'符合性检查 {pass_count}/{len(compliance_rows)} 项通过 · 判定依据见第 3 章',
                styles['cover_sub'],
            )],
        ]
        cover = Table(cover_rows, colWidths=[content_w], rowHeights=None)
        cover.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C_COVER_BG),
            ('BOX', (0, 0), (-1, -1), 0.8, C_COVER_BORDER),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
            ('LEFTPADDING', (0, 0), (-1, -1), 22),
            ('RIGHTPADDING', (0, 0), (-1, -1), 22),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(Spacer(1, 0.8 * cm))
        story.append(cover)
        story.append(PageBreak())
        story.extend(_document_control_page(report_id, generated_at, session_info, font_name, styles, content_w))
        story.append(PageBreak())

        # ========== 1. 执行摘要 ==========
        story.append(_section_block('1. 测试执行摘要', styles))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            '本章汇总本次测试会话的核心指标与总体判定，详细测量数据、符合性矩阵及波形见后续章节。',
            styles['body'],
        ))
        story.append(Spacer(1, 8))

        kpi_w = (content_w - 0.36 * cm) / 4
        kpi_row = _kpi_row([
            _kpi_card('测试时长', stats.get('duration_hms', '-'), '', C_PRIMARY, font_name, font_bold, kpi_w),
            _kpi_card('采样点数', str(stats.get('samples', 0)), '个', C_PRIMARY, font_name, font_bold, kpi_w),
            _kpi_card('峰值功率', f"{stats.get('max_p', 0):.2f}", 'W', C_PURPLE, font_name, font_bold, kpi_w),
            _kpi_card('输出能量', f"{stats.get('energy_wh', 0):.3f}", 'Wh', C_PURPLE, font_name, font_bold, kpi_w),
        ], content_w)
        story.append(kpi_row)
        story.append(Spacer(1, 8))

        summary = _styled_table([
            [Paragraph('<b>指标项目</b>', styles['cell_bold']), Paragraph('<b>测量值</b>', styles['cell_bold']),
             Paragraph('<b>指标项目</b>', styles['cell_bold']), Paragraph('<b>测量值</b>', styles['cell_bold'])],
            ['测试时段', f"{stats.get('t_start', 0):.1f} s → {stats.get('t_end', 0):.1f} s",
             '采样频率', f"{stats.get('sample_rate', 0):.1f} Hz"],
            ['平均输出功率', f"{stats.get('avg_p', 0):.2f} W", 'P95 功率', f"{stats.get('p95_p', 0):.2f} W"],
            ['输入能量（估算）', f"{stats.get('input_energy_wh', 0):.3f} Wh",
             '输出能量（估算）', f"{stats.get('energy_wh', 0):.3f} Wh"],
            ['最大输入电压', f"{stats.get('max_v_in', 0):.3f} V", '最大输出电压', f"{stats.get('max_v_out', 0):.3f} V"],
            ['最大输入电流', f"{stats.get('max_i_in', 0):.3f} A", '最大输出电流', f"{stats.get('max_i_out', 0):.3f} A"],
            ['平均传输效率', f"{stats.get('avg_eff', 0):.1f} %", '效率范围',
             f"{stats.get('min_eff', 0):.1f} – {stats.get('max_eff', 0):.1f} %"],
            ['峰值 / 平均温度', f"{stats.get('max_t', 0):.1f} / {stats.get('avg_t', 0):.1f} °C",
             '温升 ΔT', f"{stats.get('temp_rise', 0):.1f} °C"],
            ['电量变化', f"{stats.get('bat_start', 0)} % → {stats.get('bat_end', 0)} %",
             '符合性通过', f'{pass_count} / {len(compliance_rows)} 项'],
        ], [3.4 * cm, 4.3 * cm, 3.4 * cm, 4.3 * cm], font_name)
        story.append(summary)

        if phases:
            story.append(Spacer(1, 10))
            story.append(Paragraph('<b>充电阶段时间占比</b>（启发式推断，见 2.5 节说明）', styles['small']))
            phase_table = _styled_table([
                ['恒流 CC', f"{phases.get('cc_pct', 0):.1f} %", '恒压 CV', f"{phases.get('cv_pct', 0):.1f} %"],
                ['涓流', f"{phases.get('trickle_pct', 0):.1f} %", '待机', f"{phases.get('idle_pct', 0):.1f} %"],
            ], [4.3 * cm, 4.3 * cm, 4.3 * cm, 4.3 * cm], font_name, header_bg='#F0FDF4')
            story.append(phase_table)

        story.append(PageBreak())
        story.extend(_methodology_section(config, session_info, stats, styles))

        # ========== 3. 测量结果与符合性 ==========
        story.append(PageBreak())
        story.append(_section_block('3. 测量结果与符合性评估', styles))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            '下表将关键测量值与系统配置阈值逐项对照。任一「不符合」项将直接导致总体判定为未通过。',
            styles['body'],
        ))
        story.append(Spacer(1, 8))
        story.append(_compliance_table(compliance_rows, font_name, font_bold, styles, content_w))
        story.append(Spacer(1, 14))

        # ========== 4. 安全告警 ==========
        story.append(_section_block('4. 安全告警与保护事件', styles))
        story.append(Spacer(1, 6))
        alerts_cfg = config.get('alerts', {})
        cond = _styled_table([
            ['过压阈值 OVP', f"{alerts_cfg.get('ovp_threshold', 25.0)} V", '过流阈值 OCP', f"{alerts_cfg.get('ocp_threshold', 3.0)} A"],
            ['过温阈值 OTP', f"{alerts_cfg.get('temp_warning_threshold', 60)} °C", '告警总数', str(len(alert_logs))],
        ], [3.4 * cm, 4.3 * cm, 3.4 * cm, 4.3 * cm], font_name, header_bg='#FFF7ED')
        story.append(cond)
        story.append(Spacer(1, 8))

        if alert_logs:
            alert_data = [[Paragraph('<b>#</b>', styles['cell_bold']), Paragraph('<b>事件记录</b>', styles['cell_bold'])]]
            for i, log in enumerate(alert_logs[:25], 1):
                clean = log.replace('🚨', '[严重]').replace('⚠️', '[警告]').replace('🎉', '[提示]')
                alert_data.append([str(i), Paragraph(clean, styles['alert'])])
            alert_t = Table(alert_data, colWidths=[0.9 * cm, content_w - 0.9 * cm])
            alert_t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FEE2E2')),
                ('FONTNAME', (0, 0), (-1, -1), font_name),
                ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#FECACA')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(alert_t)
            if len(alert_logs) > 25:
                story.append(Paragraph(f'… 另有 {len(alert_logs) - 25} 条，请导出完整日志查看。', styles['small']))
        else:
            story.append(Paragraph(
                '✓ 本次测试未记录 OVP/OCP/OTP 类安全告警，实测电气参数均在配置阈值范围内。',
                styles['body'],
            ))

        if key_events:
            story.append(Spacer(1, 10))
            story.append(Paragraph('关键事件', styles['small']))
            ev_data = [[Paragraph('<b>#</b>', styles['cell_bold']), Paragraph('<b>事件</b>', styles['cell_bold'])]]
            for i, ev in enumerate(key_events[:10], 1):
                ev_data.append([str(i), Paragraph(ev.replace('🎉', '[完成]'), styles['event'])])
            ev_t = Table(ev_data, colWidths=[0.9 * cm, content_w - 0.9 * cm])
            ev_t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E0F2FE')),
                ('FONTNAME', (0, 0), (-1, -1), font_name),
                ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#BAE6FD')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(ev_t)

        story.append(PageBreak())

        # ========== 5. 波形图 ==========
        story.append(_section_block('5. 充电过程波形记录', styles))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            '以下波形由本次会话全部采样数据绘制；当采样点超过 1200 时自动等间隔降采样，'
            '不影响统计章节的完整数据计算。横轴为会话相对时间（秒）。',
            styles['small'],
        ))
        story.append(Spacer(1, 6))
        img_w = content_w
        for fig_idx, (title, path) in enumerate(chart_items, 1):
            if os.path.exists(path):
                fig_no = f'图 5-{fig_idx}'
                story.append(KeepTogether([
                    Paragraph(f'<b>{fig_no}　{title}</b>', styles['body']),
                    Spacer(1, 3),
                    Image(path, width=img_w, height=img_w * 0.26),
                    Paragraph(f'{fig_no}　{title}（t = {stats.get("t_start", 0):.0f}–{stats.get("t_end", 0):.0f} s）',
                              styles['figure']),
                    Spacer(1, 10),
                ]))

        story.append(PageBreak())

        # ========== 6. 数据质量 ==========
        story.append(_section_block('6. 数据质量说明', styles))
        story.append(Spacer(1, 6))
        quality = _styled_table([
            [Paragraph('<b>质量指标</b>', styles['cell_bold']), Paragraph('<b>数值</b>', styles['cell_bold']),
             Paragraph('<b>质量指标</b>', styles['cell_bold']), Paragraph('<b>数值</b>', styles['cell_bold'])],
            ['原始采样点数', f"{stats.get('samples', 0)} 点", '有效测试时长', stats.get('duration_text', '-')],
            ['平均采样率', f"{stats.get('sample_rate', 0):.2f} Hz", '最大采样间隔',
             f"{stats.get('max_gap', 0):.3f} s"],
            ['数据完整度（估算）', f"{stats.get('completeness', 0):.1f} %", '功率标准差',
             f"{stats.get('std_p', 0):.3f} W"],
            ['时间范围', f"{stats.get('t_start', 0):.3f} – {stats.get('t_end', 0):.3f} s",
             '波形降采样上限', '1200 点/图'],
        ], [3.4 * cm, 4.3 * cm, 3.4 * cm, 4.3 * cm], font_name, header_bg='#FAF5FF')
        story.append(quality)
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            '<b>说明：</b>能量值为梯形积分估算；若采样间隔不均匀，完整度指标仅供参考。'
            '建议结合原始 CSV/数据库记录进行计量复核。',
            styles['small'],
        ))
        story.append(Spacer(1, 14))

        # ========== 7. 测试结论 ==========
        story.append(_section_block('7. 测试结论与判定', styles))
        story.append(Spacer(1, 8))
        story.append(Table([[ _verdict_badge(verdict, font_bold) ]], colWidths=[content_w],
                            style=TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')])))
        story.append(Spacer(1, 12))
        conclusion = _build_conclusion(stats, phases, alert_logs, session_info, verdict, compliance_rows)
        story.append(Paragraph(conclusion, styles['body']))

        story.append(Spacer(1, 16))
        story.append(_section_block('8. 附录 — 术语、环境与签审', styles))
        story.append(Spacer(1, 6))
        story.append(Paragraph('<b>8.1 缩略语</b>', styles['body']))
        glossary = _styled_table([
            ['CC', '恒流充电阶段（Constant Current）', 'CV', '恒压充电阶段（Constant Voltage）'],
            ['OVP', '输入过压保护（Over-Voltage Protection）', 'OCP', '输入过流保护（Over-Current Protection）'],
            ['OTP', '过温保护（Over-Temperature Protection）', 'SOC', '电量状态（State of Charge）'],
            ['Eff', '无线传输效率', 'Pout', '输出功率'],
        ], [2.0 * cm, 6.5 * cm, 2.0 * cm, 6.5 * cm], font_name, header_bg='#F8FAFC')
        story.append(glossary)
        story.append(Spacer(1, 10))
        story.append(Paragraph('<b>8.2 测试环境</b>', styles['body']))
        appendix = _styled_table([
            ['软件名称', SOFTWARE_NAME, '报告编号', report_id],
            ['协议版本', PROTOCOL_VERSION, '报告版本', f'v{REPORT_VERSION}'],
            ['串口 / 波特率', f"{session_info.get('port', '-')} @ {session_info.get('baudrate', '-')} bps",
             '运行主机', platform.node() or '-'],
            ['会话 UUID', suuid or '-', '生成时间', generated_at],
            ['测试开始', session_info.get('started_at', '-'), '测试结束', session_info.get('ended_at') or '进行中'],
        ], [3.0 * cm, 5.5 * cm, 3.0 * cm, 5.5 * cm], font_name, header_bg='#F1F5F9')
        story.append(appendix)
        story.append(Spacer(1, 12))
        story.append(Paragraph('<b>8.3 签审栏</b>', styles['body']))
        sign_table = _styled_table([
            ['编制 / 日期', '____________________', '审核 / 日期', '____________________'],
            ['批准 / 日期', '____________________', '备注', ''],
        ], [3.0 * cm, 5.5 * cm, 3.0 * cm, 5.5 * cm], font_name, header_bg='#FFFFFF', header_row=False)
        story.append(sign_table)
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            f'— 报告结束 · {SOFTWARE_NAME} v{REPORT_VERSION} —',
            ParagraphStyle('end', fontName=font_name, fontSize=8, alignment=TA_CENTER, textColor=C_MUTED),
        ))

        doc.build(story, canvasmaker=_canvas_maker)

        for _, path in chart_items:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass

        logger.info("PDF report generated: %s (verdict=%s, id=%s)", filename, verdict, report_id)
        return {'report_id': report_id, 'verdict': verdict}


def _build_conclusion(stats, phases, alert_logs, session_info, verdict, compliance_rows=None):
    compliance_rows = compliance_rows or []
    parts = []
    verdict_text = {
        'PASS': '综合判定：<b>测试通过（PASS）</b>',
        'WARN': '综合判定：<b>测试警告（WARN）</b> — 存在需人工复核项',
        'FAIL': '综合判定：<b>测试未通过（FAIL）</b> — 不符合交付要求',
    }
    parts.append(f'<font color="#0F172A">{verdict_text.get(verdict, "")}</font>')

    if session_info.get('demo_mode'):
        parts.append(
            '<br/><br/><b>数据效力说明：</b>本次数据来自<b>演示模式</b>，'
            '报告仅供界面与流程验证，<b>不具有正式测试效力</b>。'
        )

    samples = stats.get('samples', 0)
    if samples == 0:
        return '本次会话未采集到有效数据，无法形成测试结论。'

    fail_items = [r for r in compliance_rows if r['result'] == '不符合']
    warn_items = [r for r in compliance_rows if r['result'] == '警告']

    parts.append('<br/><br/><b>1. 测试概况</b>')
    parts.append(
        f'<br/>会话有效时长 <b>{stats.get("duration_text", "-")}</b>，'
        f'共 <b>{samples}</b> 个采样点（{stats.get("sample_rate", 0):.1f} Hz）。'
        f'估算输入能量 <b>{stats.get("input_energy_wh", 0):.3f} Wh</b>，'
        f'输出能量 <b>{stats.get("energy_wh", 0):.3f} Wh</b>。'
    )
    parts.append(
        f'<br/>峰值功率 <b>{stats.get("max_p", 0):.2f} W</b>（P95 {stats.get("p95_p", 0):.2f} W），'
        f'线圈温度峰值 <b>{stats.get("max_t", 0):.1f} °C</b>（温升 {stats.get("temp_rise", 0):.1f} °C）。'
    )

    if stats.get('avg_eff', 0) > 0:
        parts.append(
            f'<br/>传输效率平均 <b>{stats.get("avg_eff", 0):.1f}%</b>，'
            f'范围 {stats.get("min_eff", 0):.1f}% – {stats.get("max_eff", 0):.1f}%。'
        )

    bat_delta = stats.get('bat_end', 0) - stats.get('bat_start', 0)
    if bat_delta != 0:
        sign = '+' if bat_delta > 0 else ''
        parts.append(
            f'<br/>电量由 {stats.get("bat_start")}% 变化至 {stats.get("bat_end")}%（{sign}{bat_delta}%）。'
        )

    if phases:
        parts.append('<br/><br/><b>2. 充电过程特征</b>')
        parts.append(
            f'<br/>阶段占比（启发式）：恒流 {phases.get("cc_pct", 0):.0f}% / '
            f'恒压 {phases.get("cv_pct", 0):.0f}% / '
            f'涓流 {phases.get("trickle_pct", 0):.0f}% / '
            f'待机 {phases.get("idle_pct", 0):.0f}%。'
        )

    parts.append('<br/><br/><b>3. 符合性与安全</b>')
    pass_n = sum(1 for r in compliance_rows if r['result'] == '符合')
    parts.append(f'<br/>符合性检查共 {len(compliance_rows)} 项，通过 {pass_n} 项。')
    if fail_items:
        items = '、'.join(r['item'] for r in fail_items)
        parts.append(f'<br/><font color="#EF4444"><b>不符合项：</b>{items}。须排查后重新测试。</font>')
    if warn_items:
        items = '、'.join(r['item'] for r in warn_items)
        parts.append(f'<br/><font color="#CA8A04"><b>警告项：</b>{items}。建议人工复核。</font>')
    if alert_logs:
        parts.append(
            f'<br/><font color="#EF4444">共记录 <b>{len(alert_logs)}</b> 条安全相关事件，'
            f'请结合第 4 章事件列表与第 5 章波形分析根因。</font>'
        )
    elif verdict == 'PASS' and not fail_items:
        parts.append('<br/><font color="#22C55E">未触发安全告警，关键指标均在阈值内，充电过程正常。</font>')

    parts.append('<br/><br/><b>4. 建议</b>')
    if verdict == 'PASS':
        parts.append('<br/>• 测试记录完整，可作为内部设计验证与归档依据。')
        parts.append('<br/>• 如需对外交付，请完成签审栏并附原始数据备份。')
    elif verdict == 'WARN':
        parts.append('<br/>• 请复核警告项及演示/数据完整性因素后再做交付判定。')
        parts.append('<br/>• 建议导出完整 TX 日志与原始 metrics 以备追溯。')
    else:
        parts.append('<br/>• 存在不符合项或严重保护事件，<b>不建议</b>判定为合格。')
        parts.append('<br/>• 请排查硬件保护触发原因后重新执行完整充电测试。')

    return ''.join(parts)
