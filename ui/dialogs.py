"""
dialogs.py — Диалоговые окна (добавление нового типоразмера листа).
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, 
                             QLineEdit, QPushButton, QDialogButtonBox, QLabel)
from PyQt6.QtCore import Qt
from config import PALETTES, Theme


class AddSheetDialog(QDialog):
    """Диалог для ввода размеров нового листа."""

    def __init__(self, theme: Theme = Theme.WARM_LINEN, parent=None):
        super().__init__(parent)
        self.colors = PALETTES[theme]
        self.setWindowTitle("Добавить новый типоразмер листа")
        self.resize(350, 200)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("например, 2000x4000")
        self.input_width = QLineEdit()
        self.input_width.setPlaceholderText("Ширина (мм)")
        self.input_height = QLineEdit()
        self.input_height.setPlaceholderText("Высота (мм)")

        form.addRow("Название:", self.input_name)
        form.addRow("Ширина:", self.input_width)
        form.addRow("Высота:", self.input_height)
        layout.addLayout(form)

        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Применение мягких стилей к полям ввода
        qss = f"""
            QDialog {{ background-color: {self.colors['app_background']}; }}
            QLabel {{ color: {self.colors['text_primary']}; font-size: 13px; }}
            QLineEdit {{
                background-color: {self.colors['input_background']};
                border: 1px solid {self.colors['border']};
                border-radius: 6px;
                padding: 6px;
                color: {self.colors['text_primary']};
            }}
        """
        self.setStyleSheet(qss)

    def get_data(self) -> tuple[str, float, float] | None:
        """Возвращает данные, если пользователь нажал ОК и ввёл корректные данные."""
        try:
            name = self.input_name.text().strip()
            width = float(self.input_width.text().replace(",", "."))
            height = float(self.input_height.text().replace(",", "."))
            if name and width > 0 and height > 0:
                return name, width, height
        except ValueError:
            pass
        return None