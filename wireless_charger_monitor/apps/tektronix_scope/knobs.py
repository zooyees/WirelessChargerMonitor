"""Rotary knob with mouse- and touch-friendly interaction."""
from __future__ import annotations

import math

from PyQt5.QtCore import QPointF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class RotaryKnob(QWidget):
    """
    Circular knob matching Tek front-panel rotate + push.

    Mouse:
      - Vertical drag (preferred) or angular drag → ticks
      - Mouse wheel → ticks
      - Click (little movement) or right-click → push
    Touch:
      - Vertical finger drag → ticks (large hit area)
      - Tap → push
    """

    rotated = pyqtSignal(int)  # +1 / -1 per tick
    pushClicked = pyqtSignal()

    def __init__(
        self,
        label: str = '',
        accent: str = '#38BDF8',
        diameter: int = 64,
        parent=None,
        *,
        push_enabled: bool = True,
    ):
        super().__init__(parent)
        self._label = label
        self._accent = QColor(accent)
        self._angle = -90.0
        self._diameter = max(28, int(diameter))
        self._push_enabled = push_enabled

        self._pressed = False
        self._press_pos = QPointF()
        self._last_pos = QPointF()
        self._accum_px = 0.0
        self._tick_emitted = False
        self._px_per_tick = 12.0 if self._diameter < 48 else 14.0
        self._click_slop_px = 10.0

        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        label_pad = 18 if self._diameter < 48 else 26
        self.setMinimumSize(self._diameter + 6, self._diameter + label_pad)
        self.setMaximumHeight(self._diameter + label_pad + 8)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCursor(Qt.SizeVerCursor)
        tip = label
        if push_enabled:
            tip += '\n拖动/滚轮：调节 · 单击/右键：按下'
        else:
            tip += '\n拖动/滚轮：调节'
        self.setToolTip(tip)
        self.setFocusPolicy(Qt.StrongFocus)

    def set_label(self, text: str) -> None:
        self._label = text
        self.update()

    def set_accent(self, color: str) -> None:
        self._accent = QColor(color)
        self.update()

    def sizeHint(self) -> QSize:
        pad = 18 if self._diameter < 48 else 26
        return QSize(self._diameter + 10, self._diameter + pad)

    def minimumSizeHint(self) -> QSize:
        pad = 16 if self._diameter < 48 else 24
        return QSize(self._diameter + 6, self._diameter + pad)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        label_h = 14 if self._diameter < 48 else 16
        d = min(w - 4, h - label_h - 2, self._diameter)
        cx, cy = w / 2.0, (h - label_h) / 2.0
        r = d / 2.0

        # Hit-area hint ring
        p.setPen(QPen(QColor('#475569'), 1, Qt.DotLine))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r + 2, r + 2)

        p.setPen(QPen(QColor('#64748B'), 2))
        p.setBrush(QBrush(QColor('#1E293B')))
        p.drawEllipse(QPointF(cx, cy), r, r)

        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor('#0F172A')))
        p.drawEllipse(QPointF(cx, cy), r * 0.72, r * 0.72)

        rad = math.radians(self._angle)
        ix = cx + math.cos(rad) * r * 0.55
        iy = cy + math.sin(rad) * r * 0.55
        p.setPen(QPen(self._accent, 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(cx, cy), QPointF(ix, iy))

        p.setBrush(QBrush(self._accent))
        p.drawEllipse(QPointF(cx, cy), 4, 4)

        # Up/down chevrons hint for touch
        p.setPen(QPen(QColor('#CBD5E1'), 1))
        font = QFont(self.font())
        font.setPointSize(7)
        p.setFont(font)
        p.drawText(int(cx - 6), int(cy - r + 12), '▲')
        p.drawText(int(cx - 6), int(cy + r - 2), '▼')

        if self._label:
            p.setPen(QColor('#FFFFFF'))
            font.setPointSize(8 if self._diameter < 48 else 9)
            font.setBold(True)
            p.setFont(font)
            p.drawText(0, int(h - label_h), w, label_h, Qt.AlignHCenter | Qt.AlignVCenter, self._label)

    def mousePressEvent(self, event):
        if event.button() in (Qt.LeftButton, Qt.RightButton):
            if event.button() == Qt.RightButton and self._push_enabled:
                self.pushClicked.emit()
                event.accept()
                return
            self._begin_drag(event.localPos())
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._pressed:
            return
        self._drag_to(event.localPos())
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self._pressed:
            self._end_drag()
        event.accept()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y()
        if delta > 0:
            self._emit_ticks(1)
        elif delta < 0:
            self._emit_ticks(-1)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Up, Qt.Key_Right, Qt.Key_Plus):
            self._emit_ticks(1)
            event.accept()
        elif event.key() in (Qt.Key_Down, Qt.Key_Left, Qt.Key_Minus):
            self._emit_ticks(-1)
            event.accept()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and self._push_enabled:
            self.pushClicked.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def event(self, event):
        # Ensure touch synthesizes mouse on platforms that need it;
        # also handle TouchBegin/Update for direct vertical tracking.
        et = event.type()
        from PyQt5.QtCore import QEvent
        if et == QEvent.TouchBegin:
            pts = event.touchPoints()
            if pts:
                self._begin_drag(pts[0].pos())
                return True
        if et == QEvent.TouchUpdate:
            pts = event.touchPoints()
            if pts and self._pressed:
                self._drag_to(pts[0].pos())
                return True
        if et == QEvent.TouchEnd:
            if self._pressed:
                self._end_drag()
                return True
        return super().event(event)

    def _begin_drag(self, pos: QPointF) -> None:
        self._pressed = True
        self._press_pos = QPointF(pos)
        self._last_pos = QPointF(pos)
        self._accum_px = 0.0
        self._tick_emitted = False

    def _drag_to(self, pos: QPointF) -> None:
        # Prefer vertical drag (natural for mouse wheel mental model + touch)
        dy = self._last_pos.y() - pos.y()  # up = positive = increase
        self._last_pos = QPointF(pos)
        self._accum_px += dy
        while self._accum_px >= self._px_per_tick:
            self._accum_px -= self._px_per_tick
            self._emit_ticks(1)
        while self._accum_px <= -self._px_per_tick:
            self._accum_px += self._px_per_tick
            self._emit_ticks(-1)

    def _end_drag(self) -> None:
        dist = (self._last_pos - self._press_pos).manhattanLength()
        if self._push_enabled and not self._tick_emitted and dist <= self._click_slop_px:
            self.pushClicked.emit()
        self._pressed = False
        self._accum_px = 0.0
        self._tick_emitted = False

    def _emit_ticks(self, direction: int) -> None:
        self._tick_emitted = True
        self._angle = (self._angle - 15 * direction) % 360
        self.rotated.emit(direction)
        self.update()


class KnobControl(QWidget):
    """
    Touch-friendly knob cluster: [−]  knob  [+]  and optional Push button.
    Mouse users can click ±; touch users get large targets.
    """

    rotated = pyqtSignal(int)
    pushClicked = pyqtSignal()

    def __init__(
        self,
        label: str = '',
        accent: str = '#38BDF8',
        diameter: int = 64,
        parent=None,
        *,
        push_enabled: bool = True,
        push_text: str = '按下',
        compact: bool = False,
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(1 if compact else 2)

        row = QHBoxLayout()
        row.setSpacing(2)
        self.btn_minus = QToolButton()
        self.btn_minus.setText('−')
        self.btn_minus.setAutoRepeat(True)
        self.btn_minus.setAutoRepeatDelay(400)
        self.btn_minus.setAutoRepeatInterval(80)
        self.btn_plus = QToolButton()
        self.btn_plus.setText('+')
        self.btn_plus.setAutoRepeat(True)
        self.btn_plus.setAutoRepeatDelay(400)
        self.btn_plus.setAutoRepeatInterval(80)
        for b in (self.btn_minus, self.btn_plus):
            side = 22 if compact else 36
            tall = max(26, diameter - 4) if compact else 44
            b.setFixedSize(side, tall)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                'QToolButton{background:#334155;color:#FFFFFF;border:1px solid #94A3B8;'
                f'border-radius:5px;font-size:{"13" if compact else "18"}px;font-weight:700;}}'
                'QToolButton:pressed{background:#0284C7;}'
            )

        self.knob = RotaryKnob(label=label, accent=accent, diameter=diameter, push_enabled=push_enabled)
        self.knob.rotated.connect(self.rotated.emit)
        self.knob.pushClicked.connect(self.pushClicked.emit)
        self.btn_minus.clicked.connect(lambda: self.rotated.emit(-1))
        self.btn_plus.clicked.connect(lambda: self.rotated.emit(1))

        row.addWidget(self.btn_minus)
        row.addWidget(self.knob, 0, Qt.AlignCenter)
        row.addWidget(self.btn_plus)
        root.addLayout(row)

        self.btn_push = None
        if push_enabled:
            self.btn_push = QPushButton(push_text)
            self.btn_push.setMinimumHeight(22 if compact else 28)
            self.btn_push.setMaximumHeight(26 if compact else 16777215)
            self.btn_push.setCursor(Qt.PointingHandCursor)
            self.btn_push.setToolTip('对应真机旋钮“按下”功能')
            self.btn_push.setStyleSheet(
                'QPushButton{background:#1E293B;color:#FFFFFF;border:1px solid #94A3B8;'
                'border-radius:4px;font-size:10px;font-weight:600;}'
                'QPushButton:pressed{background:#0369A1;color:#FFFFFF;}'
            )
            self.btn_push.clicked.connect(self.pushClicked.emit)
            root.addWidget(self.btn_push)

    def set_label(self, text: str) -> None:
        self.knob.set_label(text)

    def set_push_text(self, text: str) -> None:
        if self.btn_push is not None:
            self.btn_push.setText(text)

    def set_push_tooltip(self, text: str) -> None:
        if self.btn_push is not None:
            self.btn_push.setToolTip(text)
