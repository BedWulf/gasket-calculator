"""
canvas.py — Холст с zoom, pan, поворотом и отрисовкой остатков.
"""

from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QWheelEvent, QMouseEvent

from models.layout import Layout
from models.gasket import GasketShape
from config import PALETTES, Theme


class GasketCanvas(QWidget):

    def __init__(self, theme: Theme = Theme.WARM_LINEN, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.colors = PALETTES[theme]
        self.layout: Layout | None = None
        
        self.zoom_level = 1.0
        self.zoom_min = 0.1
        self.zoom_max = 10.0
        self.zoom_step = 0.1
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.is_panning = False
        self.pan_start_x = 0.0
        self.pan_start_y = 0.0
        
        self.rotate_sheet = False
        
        self.setMinimumSize(300, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background-color: {self.colors['app_background']}; border-radius: 8px;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_layout(self, layout: Layout):
        self.layout = layout
        self.rotate_sheet = layout.sheet.height > layout.sheet.width
        self.reset_view()
        self.update()

    def reset_view(self):
        self.zoom_level = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.update()

    def set_zoom(self, level: float):
        self.zoom_level = max(self.zoom_min, min(self.zoom_max, level))
        self.update()

    def toggle_rotate(self):
        self.rotate_sheet = not self.rotate_sheet
        self.reset_view()

    def wheelEvent(self, event: QWheelEvent):
        if self.layout is None:
            return
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_level = min(self.zoom_max, self.zoom_level + self.zoom_step)
        else:
            self.zoom_level = max(self.zoom_min, self.zoom_level - self.zoom_step)
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = True
            self.pan_start_x = event.position().x()
            self.pan_start_y = event.position().y()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.is_panning:
            dx = event.position().x() - self.pan_start_x
            dy = event.position().y() - self.pan_start_y
            self.offset_x += dx
            self.offset_y += dy
            self.pan_start_x = event.position().x()
            self.pan_start_y = event.position().y()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def leaveEvent(self, event):
        self.is_panning = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def paintEvent(self, event):
        if not self.layout:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.setPen(QColor(self.colors['text_secondary']))
            painter.setFont(QFont("Segoe UI", 14))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                           "Введите размеры прокладки и нажмите «Рассчитать»")
            painter.end()
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        margin = 30
        available_w = self.width() - 2 * margin
        available_h = self.height() - 2 * margin

        sheet_w = self.layout.sheet.width
        sheet_h = self.layout.sheet.height

        display_w = sheet_h if self.rotate_sheet else sheet_w
        display_h = sheet_w if self.rotate_sheet else sheet_h

        base_scale = min(available_w / display_w, available_h / display_h)
        scale = base_scale * self.zoom_level
        
        scaled_w = display_w * scale
        scaled_h = display_h * scale

        center_x = self.width() / 2 + self.offset_x
        center_y = self.height() / 2 + self.offset_y
        
        x = center_x - scaled_w / 2
        y = center_y - scaled_h / 2
        sheet_rect = QRectF(x, y, scaled_w, scaled_h)

        # 1. Фон листа
        painter.fillRect(sheet_rect, QColor(self.colors['sheet_background']))
        
        # 2. Остатки (штриховка + кайма) — рисуем ДО деталей
        painter.save()
        painter.setClipRect(sheet_rect)
        waste_color = QColor(self.colors['waste_hatch'])
        waste_color.setAlpha(80)
        hatch_pen = QPen(waste_color, 1.5)
        painter.setPen(hatch_pen)
        
        step = max(4, int(14 / self.zoom_level))
        for i in range(int(-sheet_rect.height()), int(sheet_rect.width() + sheet_rect.height()), step):
            painter.drawLine(
                QPointF(sheet_rect.left() + i, sheet_rect.top()),
                QPointF(sheet_rect.left() + i - sheet_rect.height(), sheet_rect.bottom())
            )
        painter.restore()
        
        # Кайма остатков
        for rem in self.layout.remainder_rects:
            rem_rect = self._transform_rect(rem.x, rem.y, rem.width, rem.height, sheet_rect, scale)
            painter.setPen(QPen(QColor(self.colors['accent']), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rem_rect)

        # Рамка листа
        pen_sheet = QPen(QColor(self.colors['border']), 2)
        painter.setPen(pen_sheet)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(sheet_rect)

        # 3. Прокладки
        gasket_fill = QColor(self.colors['gasket_fill'])
        gasket_stroke = QColor(self.colors['gasket_stroke'])
        stroke_width = max(1, 1.5 / self.zoom_level)
        
        for placed in self.layout.placed_gaskets:
            if placed.gasket.shape == GasketShape.RECTANGLE:
                if self.rotate_sheet:
                    px = sheet_rect.left() + placed.y * scale
                    py = sheet_rect.top() + (sheet_w - placed.x - placed.gasket.length) * scale
                    w = placed.gasket.width * scale
                    h = placed.gasket.length * scale
                else:
                    w = placed.gasket.length * scale
                    h = placed.gasket.width * scale
                    px = sheet_rect.left() + placed.x * scale
                    py = sheet_rect.top() + placed.y * scale
                
                rect = QRectF(px, py, w, h)
                painter.setBrush(QBrush(gasket_fill))
                painter.setPen(QPen(gasket_stroke, stroke_width))
                painter.drawRoundedRect(rect, 3, 3)
                
            elif placed.gasket.shape == GasketShape.CIRCLE:
                d = placed.gasket.diameter * scale
                if self.rotate_sheet:
                    cx = sheet_rect.left() + placed.y * scale
                    cy = sheet_rect.top() + (sheet_w - placed.x) * scale
                else:
                    cx = sheet_rect.left() + placed.x * scale
                    cy = sheet_rect.top() + placed.y * scale
                
                rect = QRectF(cx - d/2, cy - d/2, d, d)
                painter.setBrush(QBrush(gasket_fill))
                painter.setPen(QPen(gasket_stroke, stroke_width))
                painter.drawEllipse(rect)

        # 4. Индикатор zoom
        painter.setPen(QColor(self.colors['text_secondary']))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(10, 20, f"🔍 {self.zoom_level:.1f}x")

        painter.end()

    def _transform_rect(self, x, y, w, h, sheet_rect, scale):
        """Трансформирует координаты прямоугольника с учётом поворота листа."""
        sheet_w = self.layout.sheet.width
        if self.rotate_sheet:
            px = sheet_rect.left() + y * scale
            py = sheet_rect.top() + (sheet_w - x - w) * scale
            sw = h * scale
            sh = w * scale
        else:
            px = sheet_rect.left() + x * scale
            py = sheet_rect.top() + y * scale
            sw = w * scale
            sh = h * scale
        return QRectF(px, py, sw, sh)