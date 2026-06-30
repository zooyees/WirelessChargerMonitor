"""PyQtGraph waveform charts for the scope tool."""
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QVBoxLayout

from ...ui.theme import (
    CHART_AXIS,
    CHART_BG,
    CHART_CURRENT,
    CHART_POWER,
    CHART_TEXT,
    CHART_VOLTAGE,
    FS_CAPTION,
    FS_SUBTITLE,
)


def attach_waveform_charts(ui) -> None:
    """Inject linked power / V-I plots into ``ui.chart_container``."""
    layout = ui.chart_container.layout()
    if layout is None:
        layout = QVBoxLayout(ui.chart_container)
    else:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
    layout.setContentsMargins(0, 0, 0, 0)

    ui.graph_widget = pg.GraphicsLayoutWidget()
    layout.addWidget(ui.graph_widget)

    screen = QApplication.primaryScreen()
    scale = max(1.0, screen.logicalDotsPerInchX() / 96.0) if screen else 1.0
    ui.graph_widget.ci.layout.setSpacing(12)
    ui.graph_widget.ci.layout.setContentsMargins(10, 10, 15, 10)

    ui.vbs = []
    ui.dual_plots = []
    chart_fs = max(FS_CAPTION, min(FS_SUBTITLE, round(FS_CAPTION * scale)))
    font_css = {'font-size': f'{chart_fs}pt', 'font-family': 'Microsoft YaHei', 'font-weight': 'bold'}
    axis_pen = pg.mkPen(color=CHART_AXIS, width=1.2)
    text_pen = pg.mkPen(color=CHART_TEXT)

    def add_plot(row, label1, color1, label2=None, color2=None, link_plot=None):
        plot = ui.graph_widget.addPlot(row=row, col=0)
        plot.getViewBox().setBackgroundColor(CHART_BG)
        plot.setDefaultPadding(0.08)
        plot.setMinimumHeight(int(120 * scale))
        plot.enableAutoRange(x=False, y=True)
        plot.getViewBox().enableAutoRange(x=False, y=True)

        ax_left = plot.getAxis('left')
        ax_left.setLabel(label1, color=color1, **font_css)
        ax_left.setPen(axis_pen)
        ax_left.setTextPen(text_pen)
        ax_left.setGrid(100)

        ax_bottom = plot.getAxis('bottom')
        ax_bottom.setPen(axis_pen)
        ax_bottom.setTextPen(text_pen)
        ax_bottom.setGrid(100)

        if link_plot:
            plot.setXLink(link_plot)
        else:
            ui.p_main = plot

        line1 = plot.plot(pen=pg.mkPen(color=color1, width=2.2))
        line2 = None
        if label2 and color2:
            vb2 = pg.ViewBox()
            vb2.enableAutoRange(x=False, y=True)
            ui.vbs.append((plot, vb2))
            plot.scene().addItem(vb2)
            plot.getAxis('right').linkToView(vb2)
            vb2.setXLink(plot)
            vb2.setZValue(10)
            ax_right = plot.getAxis('right')
            ax_right.setLabel(label2, color=color2, **font_css)
            ax_right.setPen(axis_pen)
            ax_right.setTextPen(text_pen)
            plot.showAxis('right')
            line2 = pg.PlotDataItem(pen=pg.mkPen(color=color2, width=2.0))
            vb2.addItem(line2)
        return plot, line1, line2

    ui.p_p, ui.line_power, _ = add_plot(0, 'POWER (W)', CHART_POWER)
    ui.p_in, ui.line_v_in, ui.line_i_in = add_plot(
        1, 'INPUT (V)', CHART_VOLTAGE, 'INPUT (A)', CHART_CURRENT, link_plot=ui.p_p,
    )
    ui.p_out, ui.line_v_out, ui.line_i_out = add_plot(
        2, 'OUTPUT (V)', CHART_VOLTAGE, 'OUTPUT (A)', CHART_CURRENT, link_plot=ui.p_p,
    )
    ui.p_bat, ui.line_v_bat, ui.line_i_bat = add_plot(
        3, 'BATTERY (V)', CHART_VOLTAGE, 'BATTERY (A)', CHART_CURRENT, link_plot=ui.p_p,
    )

    ui.dual_plots = [
        (ui.p_in, ui.vbs[0][1], 'vi', 'ii'),
        (ui.p_out, ui.vbs[1][1], 'vo', 'io'),
        (ui.p_bat, ui.vbs[2][1], 'vb', 'ib'),
    ]

    ui.p_p.getAxis('bottom').setStyle(showValues=False)
    ui.p_in.getAxis('bottom').setStyle(showValues=False)
    ui.p_out.getAxis('bottom').setStyle(showValues=False)

    def update_views():
        for plot, vb in ui.vbs:
            vb.setGeometry(plot.vb.sceneBoundingRect())
            vb.linkedViewChanged(plot.vb, vb.XAxis)

    update_views()
    for plot, _ in ui.vbs:
        plot.vb.sigResized.connect(update_views)
