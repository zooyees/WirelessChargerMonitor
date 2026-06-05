# ==========================================
# Module: 无线充电测试报告 PDF 生成引擎
# Author: Roy Zhao @ 御风智联
# ==========================================
import os
import datetime
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

REPORT_VERSION = '2.1'
PROTOCOL_VERSION = 'Qi 2.2.1'
SOFTWARE_NAME = '手机无线充电监控系统'

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
            'CoverTitle', fontName=font_bold, fontSize=28, leading=34,
            textColor=colors.white, alignment=TA_CENTER, spaceAfter=6,
        ),
        'cover_sub': ParagraphStyle(
            'CoverSub', fontName=font_name, fontSize=11, leading=15,
            textColor=colors.HexColor('#94A3B8'), alignment=TA_CENTER,
        ),
        'cover_meta': ParagraphStyle(
            'CoverMeta', fontName=font_name, fontSize=10, leading=14,
            textColor=colors.HexColor('#CBD5E1'), alignment=TA_LEFT,
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


def _kpi_card(label, value, unit, accent, font_name, font_bold):
    data = [
        [Paragraph(f'<font color="{accent.hexval()}"><b>{value}</b></font>',
                   ParagraphStyle('kv', fontName=font_bold, fontSize=15, leading=19, alignment=TA_CENTER)),
         Paragraph(f'<font color="#64748B">{unit}</font>',
                   ParagraphStyle('ku', fontName=font_name, fontSize=7, leading=9, alignment=TA_CENTER))],
        [Paragraph(label, ParagraphStyle('kl', fontName=font_name, fontSize=8, leading=10,
                                         alignment=TA_CENTER, textColor=C_MUTED)), ''],
    ]
    t = Table(data, colWidths=[4.05 * cm], rowHeights=[20, 13])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('LINEBELOW', (0, 0), (-1, 0), 2.5, accent),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return t


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


def _compute_stats(metrics_rows):
    if not metrics_rows:
        return {}
    n = len(metrics_rows)
    powers = [r[8] for r in metrics_rows]
    temps = [r[9] for r in metrics_rows]
    effs = [r[7] for r in metrics_rows if r[7] > 0]
    bats = [r[10] for r in metrics_rows]
    duration = metrics_rows[-1][0] - metrics_rows[0][0] if n > 1 else 0.0

    energy_ws = 0.0
    for i in range(1, n):
        dt = metrics_rows[i][0] - metrics_rows[i - 1][0]
        if dt > 0:
            energy_ws += (metrics_rows[i][8] + metrics_rows[i - 1][8]) / 2 * dt

    sample_rate = n / duration if duration > 0.1 else 0.0
    return {
        'samples': n,
        'duration': duration,
        'sample_rate': sample_rate,
        'energy_wh': energy_ws / 3600.0,
        'max_p': max(powers), 'min_p': min(powers), 'avg_p': sum(powers) / n,
        'max_t': max(temps), 'min_t': min(temps), 'avg_t': sum(temps) / n,
        'max_eff': max(effs) if effs else 0, 'avg_eff': sum(effs) / len(effs) if effs else 0,
        'bat_start': bats[0], 'bat_end': bats[-1],
        'max_v_in': max(r[1] for r in metrics_rows), 'max_v_out': max(r[3] for r in metrics_rows),
        'max_i_in': max(r[2] for r in metrics_rows), 'max_i_out': max(r[4] for r in metrics_rows),
        'avg_v_bat': sum(r[5] for r in metrics_rows) / n,
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


def _evaluate_verdict(session_info, alert_logs, stats):
    if session_info.get('demo_mode'):
        return 'WARN'
    critical = sum(1 for log in alert_logs if '🚨' in log or '硬件保护' in log)
    if critical > 0:
        return 'FAIL'
    if alert_logs:
        return 'WARN'
    if stats.get('samples', 0) < 10:
        return 'WARN'
    return 'PASS'


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


def _styled_table(rows, col_widths, font_name, header_bg='#E0F2FE'):
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#E2E8F0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
    ]))
    return t


class ReportEngine:
    @staticmethod
    def generate(filename, session_info, metrics_rows, alert_logs, config=None, key_events=None):
        config = config or {}
        key_events = key_events or []
        font_name, font_bold = _register_cjk_fonts()
        styles = _build_styles(font_name, font_bold)
        stats = _compute_stats(metrics_rows)
        phases = _analyze_phases(metrics_rows)
        verdict = _evaluate_verdict(session_info, alert_logs, stats)
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
            f"<b>生成时间</b>　{generated_at}　　<b>报告版本</b>　v{REPORT_VERSION}",
        ]
        cover_rows = [
            [Paragraph('无线充电测试分析报告', styles['cover_title'])],
            [Paragraph('Wireless Charging Test Analysis Report', styles['cover_sub'])],
            [Spacer(1, 0.6 * cm)],
            [Paragraph('<br/>'.join(meta_lines), styles['cover_meta'])],
            [Spacer(1, 0.5 * cm)],
            [Table([[ _verdict_badge(verdict, font_bold) ]], colWidths=[content_w],
                   style=TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))],
            [Spacer(1, 0.4 * cm)],
            [Paragraph('御风智联 · Yufeng Zhilian', styles['cover_sub'])],
        ]
        cover = Table(cover_rows, colWidths=[content_w], rowHeights=None)
        cover.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C_DARK),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 24),
            ('RIGHTPADDING', (0, 0), (-1, -1), 24),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(Spacer(1, 1.2 * cm))
        story.append(cover)
        story.append(PageBreak())

        # ========== 1. 执行摘要 ==========
        story.append(_section_block('1. 测试执行摘要', styles))
        story.append(Spacer(1, 8))

        kpi_row = [
            _kpi_card('测试时长', f"{stats.get('duration', 0):.1f}", '秒', C_PRIMARY, font_name, font_bold),
            _kpi_card('采样点数', str(stats.get('samples', 0)), '个', C_PRIMARY, font_name, font_bold),
            _kpi_card('峰值功率', f"{stats.get('max_p', 0):.2f}", 'W', C_PURPLE, font_name, font_bold),
            _kpi_card('传输能量', f"{stats.get('energy_wh', 0):.3f}", 'Wh', C_PURPLE, font_name, font_bold),
        ]
        story.append(Table([kpi_row], colWidths=[4.15 * cm] * 4))
        story.append(Spacer(1, 8))

        summary = _styled_table([
            [Paragraph('<b>指标项目</b>', styles['cell_bold']), Paragraph('<b>测量值</b>', styles['cell_bold']),
             Paragraph('<b>指标项目</b>', styles['cell_bold']), Paragraph('<b>测量值</b>', styles['cell_bold'])],
            ['平均输出功率', f"{stats.get('avg_p', 0):.2f} W", '峰值线圈温度', f"{stats.get('max_t', 0):.1f} °C"],
            ['最大输入电压', f"{stats.get('max_v_in', 0):.3f} V", '最大输出电压', f"{stats.get('max_v_out', 0):.3f} V"],
            ['最大输入电流', f"{stats.get('max_i_in', 0):.3f} A", '最大输出电流', f"{stats.get('max_i_out', 0):.3f} A"],
            ['平均传输效率', f"{stats.get('avg_eff', 0):.1f} %", '最高传输效率', f"{stats.get('max_eff', 0):.1f} %"],
            ['电量变化', f"{stats.get('bat_start', 0)} % → {stats.get('bat_end', 0)} %",
             '采样频率', f"{stats.get('sample_rate', 0):.1f} Hz"],
        ], [3.4 * cm, 4.3 * cm, 3.4 * cm, 4.3 * cm], font_name)
        story.append(summary)

        if phases:
            story.append(Spacer(1, 10))
            story.append(Paragraph('充电阶段时间占比（基于电参启发式推断）', styles['small']))
            phase_table = _styled_table([
                ['恒流 CC', f"{phases.get('cc_pct', 0):.1f} %", '恒压 CV', f"{phases.get('cv_pct', 0):.1f} %"],
                ['涓流', f"{phases.get('trickle_pct', 0):.1f} %", '待机', f"{phases.get('idle_pct', 0):.1f} %"],
            ], [4.3 * cm, 4.3 * cm, 4.3 * cm, 4.3 * cm], font_name, header_bg='#F0FDF4')
            story.append(phase_table)

        story.append(Spacer(1, 14))

        # ========== 2. 安全告警 ==========
        story.append(_section_block('2. 安全告警与保护事件', styles))
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
            story.append(Paragraph('✓ 本次测试未触发安全告警，所有参数均在配置阈值范围内。', styles['body']))

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

        # ========== 3. 波形图 ==========
        story.append(_section_block('3. 完整充电周期波形', styles))
        story.append(Spacer(1, 6))
        story.append(Paragraph('以下波形由本次会话全部采样数据绘制（高密度数据已自动降采样以优化显示）。', styles['small']))
        story.append(Spacer(1, 6))
        img_w = content_w
        for title, path in chart_items:
            if os.path.exists(path):
                story.append(KeepTogether([
                    Paragraph(f'<b>{title}</b>', styles['body']),
                    Spacer(1, 3),
                    Image(path, width=img_w, height=img_w * 0.26),
                    Spacer(1, 10),
                ]))

        story.append(PageBreak())

        # ========== 4. 测试结论 ==========
        story.append(_section_block('4. 测试结论与判定', styles))
        story.append(Spacer(1, 8))
        story.append(Table([[ _verdict_badge(verdict, font_bold) ]], colWidths=[content_w],
                            style=TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')])))
        story.append(Spacer(1, 12))
        conclusion = _build_conclusion(stats, phases, alert_logs, session_info, verdict)
        story.append(Paragraph(conclusion, styles['body']))

        story.append(Spacer(1, 16))
        story.append(_section_block('5. 附录 — 测试环境', styles))
        story.append(Spacer(1, 6))
        appendix = _styled_table([
            ['软件名称', SOFTWARE_NAME, '报告编号', report_id],
            ['协议版本', PROTOCOL_VERSION, '报告版本', f'v{REPORT_VERSION}'],
            ['串口', str(session_info.get('port', '-')), '波特率', f"{session_info.get('baudrate', '-')} bps"],
            ['会话 UUID', suuid or '-', '生成时间', generated_at],
        ], [3.0 * cm, 5.5 * cm, 3.0 * cm, 5.5 * cm], font_name, header_bg='#F1F5F9')
        story.append(appendix)

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


def _build_conclusion(stats, phases, alert_logs, session_info, verdict):
    parts = []
    verdict_text = {'PASS': '综合判定：<b>测试通过</b>', 'WARN': '综合判定：<b>测试警告</b>（需人工复核）',
                    'FAIL': '综合判定：<b>测试未通过</b>'}
    parts.append(f'<font color="#0F172A">{verdict_text.get(verdict, "")}</font>')

    if session_info.get('demo_mode'):
        parts.append('<br/><br/><b>注意：</b>本次数据来自<b>演示模式</b>，报告仅供界面验证，不具有正式测试效力。')

    samples = stats.get('samples', 0)
    if samples == 0:
        return '本次会话未采集到有效数据，无法形成测试结论。'

    parts.append(f'<br/><br/>本次测试共采集 <b>{samples}</b> 个数据点，有效时长 <b>{stats.get("duration", 0):.1f}</b> 秒，'
                 f'估算传输能量 <b>{stats.get("energy_wh", 0):.3f} Wh</b>。')
    parts.append(f'峰值输出功率 <b>{stats.get("max_p", 0):.2f} W</b>（平均 {stats.get("avg_p", 0):.2f} W），'
                 f'峰值线圈温度 <b>{stats.get("max_t", 0):.1f} °C</b>。')

    if stats.get('avg_eff', 0) > 0:
        parts.append(f'平均传输效率 <b>{stats.get("avg_eff", 0):.1f}%</b>，最高 <b>{stats.get("max_eff", 0):.1f}%</b>。')

    bat_delta = stats.get('bat_end', 0) - stats.get('bat_start', 0)
    if bat_delta > 0:
        parts.append(f'测试期间电量由 {stats.get("bat_start")}% 上升至 {stats.get("bat_end")}%（+{bat_delta}%）。')

    if phases:
        parts.append(f'充电阶段占比：恒流 {phases.get("cc_pct", 0):.0f}% / 恒压 {phases.get("cv_pct", 0):.0f}% / '
                     f'涓流 {phases.get("trickle_pct", 0):.0f}% / 待机 {phases.get("idle_pct", 0):.0f}%。')

    if alert_logs:
        parts.append(f'<br/><br/><font color="#EF4444">共记录 <b>{len(alert_logs)}</b> 条安全相关事件，'
                     f'建议结合波形与报文日志进一步分析根因。</font>')
    elif verdict == 'PASS':
        parts.append('<br/><br/><font color="#22C55E">测试期间参数稳定，未触发安全告警，充电过程正常。</font>')

    return ''.join(parts)
