"""
main.py — Точка входа в приложение.
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

# Добавляем корень проекта в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Theme, PALETTES  # ← Убедитесь, что импортируется Theme
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Расчёт вместимости прокладок")
    app.setOrganizationName("GasketCalculator")
    
    # Устанавливаем иконку приложения
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "app_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Выбираем тему по умолчанию
    theme = Theme.WARM_LINEN
    
    window = MainWindow(theme=theme)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()