from PyQt6.QtWidgets import QWidget, QPushButton, QFrame, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QLinearGradient,
                         QPainterPath, QFont)
import math


class PowerButton(QPushButton):
    def __init__(self, accent="#4f8cff"):
        super().__init__()
        self.setFixedSize(170, 170)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._accent = QColor(accent)
        self._connected = False
        self._connecting = False
        self._glow = 0.0
        self._angle = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._anim)
        self._timer.start(33)

    def set_accent(self, c):
        self._accent = QColor(c); self.update()

    def set_state(self, connected, connecting=False):
        self._connected = connected; self._connecting = connecting; self.update()

    def _anim(self):
        if self._connecting:
            self._angle = (self._angle + 8) % 360
        if self._connected:
            self._glow = (self._glow + 0.04) % (2 * math.pi)
        if self._connecting or self._connected:
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        cx, cy = r.width() / 2, r.height() / 2
        radius = 68
        if self._connected:
            glow = 18 + 10 * (0.5 + 0.5 * math.sin(self._glow))
            steps = max(1, int(glow))
            for i in range(steps, 0, -3):
                alpha = int(55 * (1 - i / glow))
                col = QColor(self._accent); col.setAlpha(max(0, alpha))
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(col)
                p.drawEllipse(QPointF(cx, cy), radius + i, radius + i)
        if self._connected:
            grad = QLinearGradient(0, 0, 0, r.height())
            grad.setColorAt(0, self._accent.lighter(125))
            grad.setColorAt(1, self._accent.darker(120))
            p.setBrush(QBrush(grad)); p.setPen(Qt.PenStyle.NoPen)
        else:
            p.setBrush(QColor(255, 255, 255, 12))
            p.setPen(QPen(QColor(255, 255, 255, 40), 2))
        p.drawEllipse(QPointF(cx, cy), radius, radius)
        if self._connecting:
            pen = QPen(self._accent, 4); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
            p.drawArc(rect, int(self._angle * 16), 90 * 16)
        pen = QPen(QColor("#ffffff") if self._connected else self._accent, 5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 26), QPointF(cx, cy - 2))
        arc = QRectF(cx - 24, cy - 26, 48, 48)
        p.drawArc(arc, 35 * 16, -250 * 16)
        p.end()


class TrafficChart(QWidget):
    def __init__(self, accent="#4f8cff", accent2="#7db1ff"):
        super().__init__()
        self.setMinimumHeight(170)
        self._accent = QColor(accent); self._accent2 = QColor(accent2)
        self._data = []

    def set_accent(self, a, a2):
        self._accent = QColor(a); self._accent2 = QColor(a2); self.update()

    def set_data(self, data):
        self._data = list(data); self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor(255, 255, 255, 12), 1))
        for i in range(1, 4):
            y = h / 4 * i; p.drawLine(0, int(y), w, int(y))
        if not self._data:
            p.setPen(QColor(150, 160, 180, 130))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data yet")
            p.end(); return
        downs = [d[0] for d in self._data]; ups = [d[1] for d in self._data]
        mx = max(1.0, max(downs), max(ups)); n = max(2, len(self._data))

        def pts(arr):
            return [QPointF(i / (n - 1) * w,
                            h - (v / mx) * (h - 16) - 6)
                    for i, v in enumerate(arr)]

        dp = pts(downs)
        path = QPainterPath(); path.moveTo(dp[0])
        for pt in dp[1:]: path.lineTo(pt)
        fill = QPainterPath(path); fill.lineTo(w, h); fill.lineTo(0, h)
        fill.closeSubpath()
        grad = QLinearGradient(0, 0, 0, h)
        c0 = QColor(self._accent); c0.setAlpha(120); grad.setColorAt(0, c0)
        c1 = QColor(self._accent); c1.setAlpha(0); grad.setColorAt(1, c1)
        p.fillPath(fill, QBrush(grad))
        p.setPen(QPen(self._accent, 2)); p.drawPath(path)
        up_p = pts(ups); path2 = QPainterPath(); path2.moveTo(up_p[0])
        for pt in up_p[1:]: path2.lineTo(pt)
        p.setPen(QPen(self._accent2, 2)); p.drawPath(path2)
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(self._accent);  p.drawText(w - 140, 16, "download")
        p.setPen(self._accent2); p.drawText(w - 55, 16, "upload")
        p.end()


class StatCard(QFrame):
    def __init__(self, label, accent="#4f8cff"):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self); lay.setContentsMargins(18, 16, 18, 16)
        self.lbl = QLabel(label); self.lbl.setObjectName("statLabel")
        self.val = QLabel("0"); self.val.setObjectName("statVal")
        self.sub = QLabel(""); self.sub.setObjectName("statSub")
        lay.addWidget(self.lbl); lay.addWidget(self.val); lay.addWidget(self.sub)

    def set(self, val, sub=""):
        self.val.setText(val)
        self.sub.setText(sub)


def fmt_bytes(b):
    b = b or 0
    if b < 1024: return f"{b:.0f} B"
    if b < 1024**2: return f"{b/1024:.1f} KB"
    if b < 1024**3: return f"{b/1024**2:.2f} MB"
    if b < 1024**4: return f"{b/1024**3:.2f} GB"
    return f"{b/1024**4:.2f} TB"


def fmt_speed(b):
    return fmt_bytes(b) + "/s"


def fmt_time(secs):
    if not secs or secs < 0: return "00:00:00"
    h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}"
