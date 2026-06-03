import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QBrush


class AnimatedBackground(QWidget):
    """Soft, slowly-moving blurred gradient blobs behind everything."""
    def __init__(self, colors):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.set_colors(colors)
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(40)   # ~25 fps, gentle

    def set_colors(self, colors):
        self._c = [QColor(c) for c in colors]
        self.update()

    def _step(self):
        self._t += 0.006
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # base
        p.fillRect(self.rect(), self._c[0].darker(140))

        blobs = [
            (0.25 + 0.10 * math.sin(self._t),
             0.30 + 0.08 * math.cos(self._t * 0.8), self._c[1], 0.55),
            (0.75 + 0.10 * math.cos(self._t * 0.7),
             0.70 + 0.09 * math.sin(self._t * 0.9), self._c[2], 0.55),
            (0.55 + 0.12 * math.sin(self._t * 0.5),
             0.45 + 0.10 * math.cos(self._t), self._c[1], 0.35),
        ]
        for fx, fy, col, alpha in blobs:
            cx, cy = fx * w, fy * h
            rad = max(w, h) * 0.55
            g = QRadialGradient(QPointF(cx, cy), rad)
            c = QColor(col); c.setAlphaF(alpha)
            g.setColorAt(0, c)
            c2 = QColor(col); c2.setAlphaF(0)
            g.setColorAt(1, c2)
            p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, cy), rad, rad)
        p.end()
