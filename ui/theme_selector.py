"""
theme_selector.py — Виджет для переключения цветовых тем.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from config import Theme, PALETTES


class ThemeSelector(QWidget):
    """Виджет с кнопками переключения тем."""
    
    theme_changed = pyqtSignal(Theme)  # Сигнал при смене темы
    
    def __init__(self, current_theme: Theme = Theme.WARM_LINEN, parent=None):
        super().__init__(parent)
        self.current_theme = current_theme
        self._init_ui()
        
    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        label = QLabel("Тема:")
        label.setFont(QFont("Segoe UI", 12))
        layout.addWidget(label)
        
        # Кнопки для каждой темы
        self.theme_buttons = {}
        for theme in Theme:
            btn = QPushButton(theme.value)
            btn.setFixedHeight(32)
            btn.setFont(QFont("Segoe UI", 11))
            btn.clicked.connect(lambda checked, t=theme: self._on_theme_selected(t))
            self.theme_buttons[theme] = btn
            layout.addWidget(btn)
        
        self._update_button_styles()
    
    def _on_theme_selected(self, theme: Theme):
        """Обработчик выбора темы."""
        if self.current_theme != theme:
            self.current_theme = theme
            self._update_button_styles()
            self.theme_changed.emit(theme)
    
    def _update_button_styles(self):
        """Обновляет стили кнопок (активная/неактивная)."""
        for theme, btn in self.theme_buttons.items():
            if theme == self.current_theme:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #8FA87A;
                        color: #FFFFFF;
                        border: 2px solid #6B8058;
                        border-radius: 6px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #7A9465;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #EDE4D0;
                        color: #5C4A3A;
                        border: 1px solid #D4C4A8;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: #D4C4A8;
                    }
                """)