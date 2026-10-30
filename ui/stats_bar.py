"""
stats_bar.py — Компактный виджет статистики для вставки в панель ввода.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QFont
from config import PALETTES, Theme
from models.layout import Layout


class StatsPanel(QFrame):
    """Панель статистики для отображения под кнопкой расчёта."""

    def __init__(self, theme: Theme = Theme.WARM_LINEN, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.colors = PALETTES[theme]
        self.layout_result: Layout | None = None
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        self.title = QLabel("Результаты расчёта")
        self.title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(self.title)
        
        self.label_gaskets = QLabel("Прокладок на листе: —")
        self.label_waste_area = QLabel("Отходы: — мм²")
        self.label_waste_percent = QLabel("Отходы: — %")
        self.label_sheets = QLabel("Листов нужно: —")
        self.label_remainders = QLabel("Остатки: —")
        self.label_remainders.setWordWrap(True)
        
        # Метка стоимости остатка
        self.label_waste_price = QLabel("Стоимость остатка: — руб.")
        self.label_waste_price.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        
        font = QFont("Segoe UI", 11)
        for lbl in [self.label_gaskets, self.label_waste_area, 
                    self.label_waste_percent, self.label_sheets, 
                    self.label_remainders, self.label_waste_price]:
            lbl.setFont(font)
            layout.addWidget(lbl)
        
        layout.addStretch()
        self._apply_colors()
        self.hide()

    def _apply_colors(self):
        c = self.colors
        for lbl in [self.title, self.label_gaskets, self.label_waste_area,
                    self.label_waste_percent, self.label_sheets, self.label_remainders,
                    self.label_waste_price]:
            lbl.setStyleSheet(f"color: {c['text_primary']}; background: transparent;")
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {c['sheet_background']};
                border: 1px solid {c['border']};
                border-radius: 8px;
            }}
        """)

    def update_from_layout(self, layout: Layout, quantity: int = 0, waste_price: float = 0.0):
        """Обновляет данные из результата расчёта."""
        self.layout_result = layout
        
        if quantity > 0:
            layout.calculate_sheets_needed(quantity)
        
        self.label_gaskets.setText(f"Прокладок на листе: {layout.total_gaskets}")
        self.label_waste_area.setText(f"Отходы: {int(layout.waste_area)} мм²")
        self.label_waste_percent.setText(f"Отходы: {layout.waste_percent:.1f}%")
        
        if quantity > 0:
            self.label_sheets.setText(f"Листов нужно: {layout.sheets_needed} шт.")
        else:
            self.label_sheets.setText("Листов нужно: 1 (максимум)")
        
        # Обновление цены
        self.label_waste_price.setText(f"Стоимость остатка: {waste_price:,.2f} руб.")
        
        # Остатки
        if layout.remainder_rects:
            parts = []
            for i, r in enumerate(layout.remainder_rects[:3], 1):
                parts.append(f"{i}. {r.width:.0f}×{r.height:.0f} мм")
            self.label_remainders.setText(f"Остатки ({len(layout.remainder_rects)} шт.):\n" + "\n".join(parts))
        else:
            self.label_remainders.setText("Остатки: нет (лист заполнен полностью)")
        
        self.show()

    def update_orientation_label(self, is_rotated: bool, gasket_shape_name: str):
        """Показывает, какой вариант отображается."""
        if gasket_shape_name == "CIRCLE":
            self.title.setText("Результаты расчёта")
        elif is_rotated:
            self.title.setText("Результаты (детали повёрнуты на 90°)")
        else:
            self.title.setText("Результаты (оптимальный вариант)")