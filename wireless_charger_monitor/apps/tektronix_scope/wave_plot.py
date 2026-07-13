"""PyQtGraph waveform display for Tektronix CURVe data (perf-tuned)."""
from __future__ import annotations

from typing import Any

from PyQt5.QtWidgets import QVBoxLayout, QWidget

CHANNEL_COLORS = {
    'CH1': '#FFEB3B',
    'CH2': '#69F0AE',
    'CH3': '#EA80FC',
    'CH4': '#82B1FF',
    'MATH': '#FF9800',
    'REF1': '#FFFFFF',
}


class ScopeWaveformPlot(QWidget):
    """Multi-channel scope-style plot (time vs volts)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves: dict[str, Any] = {}
        self._plot = None
        self._widget = None
        self._auto_range = True
        self._live = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        try:
            import pyqtgraph as pg

            # Antialias is expensive on dense live waveforms — enable only when idle.
            pg.setConfigOptions(antialias=False, background='#0B1220', foreground='#E2E8F0')
            self._widget = pg.GraphicsLayoutWidget()
            self._plot = self._widget.addPlot(row=0, col=0)
            self._plot.showGrid(x=True, y=True, alpha=0.25)
            self._plot.setLabel('bottom', 'Time', units='s')
            self._plot.setLabel('left', 'Voltage', units='V')
            self._plot.addLegend(offset=(10, 10))
            # Only draw visible region; let pyqtgraph downsample for speed
            self._plot.setClipToView(True)
            self._plot.setDownsampling(mode='peak')
            try:
                self._plot.setDefaultPadding(0.02)
            except Exception:
                pass
            layout.addWidget(self._widget)
        except Exception:
            from PyQt5.QtWidgets import QLabel
            lab = QLabel('pyqtgraph 不可用，无法显示波形')
            lab.setStyleSheet('color:#94A3B8;padding:12px;')
            layout.addWidget(lab)

    def set_live_mode(self, live: bool) -> None:
        """Live mode: skip auto-range every frame; keep view stable."""
        self._live = live
        self._auto_range = not live

    def clear(self) -> None:
        if self._plot is None:
            return
        self._plot.clear()
        self._curves.clear()
        self._plot.addLegend(offset=(10, 10))

    def set_waveform(self, channel: str, x, y) -> None:
        if self._plot is None:
            return
        import pyqtgraph as pg

        ch = channel.upper()
        color = CHANNEL_COLORS.get(ch, '#FFFFFF')
        # Ensure contiguous arrays for fast path
        try:
            import numpy as np
            if not isinstance(x, np.ndarray):
                x = np.asarray(x, dtype=np.float64)
            if not isinstance(y, np.ndarray):
                y = np.asarray(y, dtype=np.float64)
        except ImportError:
            pass

        if ch in self._curves:
            self._curves[ch].setData(x, y, skipFiniteCheck=True)
        else:
            pen = pg.mkPen(color=color, width=1.2)
            curve = self._plot.plot(x, y, pen=pen, name=ch, antialias=False)
            try:
                curve.setClipToView(True)
                curve.setDownsampling(auto=True, method='peak')
            except Exception:
                pass
            self._curves[ch] = curve

    def set_waveforms(self, waves: list[dict], *, auto_range: bool | None = None) -> None:
        """Update curves from a list of {channel,x,y} dicts."""
        if self._plot is None:
            return
        keep = {w['channel'].upper() for w in waves}
        for ch in list(self._curves):
            if ch not in keep:
                self._plot.removeItem(self._curves.pop(ch))
        for w in waves:
            self.set_waveform(w['channel'], w['x'], w['y'])
        do_range = self._auto_range if auto_range is None else auto_range
        if waves and do_range:
            self._plot.autoRange()
