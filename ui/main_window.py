"""
main_window.py — Главное окно приложения (полная версия с ценой, зазором и поворотом).
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QRadioButton, QButtonGroup,
    QPushButton, QTabWidget, QFrame, QMessageBox, QMenu,
    QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QAction

from config import Theme, PALETTES, APP_TITLE, APP_WIDTH, APP_HEIGHT
from models import Gasket, GasketShape, Sheet
from algorithms import PackingAlgorithm
from storage.sheet_repository import SheetRepository

from ui.canvas import GasketCanvas
from ui.stats_bar import StatsPanel
from ui.dialogs import AddSheetDialog


class MainWindow(QMainWindow):
    def __init__(self, theme: Theme = Theme.WARM_LINEN):
        super().__init__()
        self.theme = theme
        self.colors = PALETTES[theme]

        self.repository = SheetRepository()
        self.sheets = self.repository.sheets

        self.setWindowTitle(APP_TITLE)
        self.resize(APP_WIDTH, APP_HEIGHT)
        
        # Храним оба варианта упаковки
        self.layout_normal = None
        self.layout_rotated = None
        self.current_layout = None
        self.current_quantity = 0

        self._init_ui()
        self._apply_stylesheet()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        top_bar = self._create_top_bar()
        main_layout.addWidget(top_bar)

        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self.input_panel = self._create_input_panel()
        content_layout.addWidget(self.input_panel, stretch=0)

        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)

        tabs_header = self._create_tabs_header()
        center_layout.addWidget(tabs_header)

        self.canvas = GasketCanvas(theme=self.theme)
        center_layout.addWidget(self.canvas, stretch=1)

        zoom_controls = self._create_zoom_controls()
        center_layout.addWidget(zoom_controls)

        content_layout.addWidget(center_widget, stretch=1)
        main_layout.addWidget(content_widget, stretch=1)

    def _create_top_bar(self) -> QWidget:
        top_bar = QWidget()
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("📐 Расчёт вместимости прокладок")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {self.colors['text_primary']}; padding: 4px;")
        layout.addWidget(title)

        layout.addStretch()

        theme_label = QLabel("🎨 Стиль:")
        theme_label.setStyleSheet(f"color: {self.colors['text_secondary']}; font-size: 13px;")
        layout.addWidget(theme_label)

        self.theme_combo = QComboBox()

        self.theme_combo.addItem("═══ Светлые темы ═══", None)
        self.theme_combo.model().item(self.theme_combo.count() - 1).setEnabled(False)
        self.theme_combo.addItem("Тёплый лён", Theme.WARM_LINEN.value)
        self.theme_combo.addItem("Оливковая роща", Theme.OLIVE_GROVE.value)
        self.theme_combo.addItem("Какао с молоком", Theme.COCOA_MILK.value)

        self.theme_combo.addItem("═══ Тёмные темы ═══", None)
        self.theme_combo.model().item(self.theme_combo.count() - 1).setEnabled(False)
        self.theme_combo.addItem("Индустриальная сталь", Theme.INDUSTRIAL_STEEL.value)
        self.theme_combo.addItem("Глубокий океан", Theme.DEEP_OCEAN.value)
        self.theme_combo.addItem("Кибер-цех", Theme.CYBER_WORKSHOP.value)

        self.theme_combo.addItem("═══ Литейный цех ═══", None)
        self.theme_combo.model().item(self.theme_combo.count() - 1).setEnabled(False)
        self.theme_combo.addItem("Раскалённая форма", Theme.MOLTEN_FORM.value)
        self.theme_combo.addItem("Чугунный цех", Theme.CAST_IRON.value)
        self.theme_combo.addItem("Литейная форма", Theme.FOUNDRY_MOLD.value)

        self.theme_combo.addItem("═══ Корпоративные ═══", None)
        self.theme_combo.model().item(self.theme_combo.count() - 1).setEnabled(False)
        self.theme_combo.addItem("ОНИИП Корпоративный", Theme.ONIIP_CORPORATE.value)
        self.theme_combo.addItem("Инженерный синий", Theme.ENGINEERING_BLUE.value)

        current_theme_name = self.theme.value
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemText(i) == current_theme_name:
                self.theme_combo.setCurrentIndex(i)
                break

        self.theme_combo.setFixedWidth(240)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        layout.addWidget(self.theme_combo)

        return top_bar

    def _on_theme_changed(self, index: int):
        theme_value = self.theme_combo.itemData(index)
        if theme_value is None:
            for i in range(self.theme_combo.count()):
                if self.theme_combo.itemData(i) == self.theme.value:
                    self.theme_combo.setCurrentIndex(i)
                    return
            return

        theme_map = {theme.value: theme for theme in Theme}
        new_theme = theme_map.get(theme_value, Theme.WARM_LINEN)

        if new_theme != self.theme:
            self.theme = new_theme
            self.colors = PALETTES[new_theme]
            self._reapply_theme()

    def _reapply_theme(self):
        self._apply_stylesheet()

        if hasattr(self, 'canvas'):
            self.canvas.theme = self.theme
            self.canvas.colors = self.colors
            if self.canvas.layout:
                self.canvas.update()

        if hasattr(self, 'stats_panel'):
            self.stats_panel.theme = self.theme
            self.stats_panel.colors = self.colors
            self.stats_panel._apply_colors()

        for child in self.findChildren(QLabel):
            if "🎨 Стиль:" in child.text():
                child.setStyleSheet(f"color: {self.colors['text_secondary']}; font-size: 13px;")
            elif "Расчёт вместимости" in child.text():
                child.setStyleSheet(f"color: {self.colors['text_primary']}; padding: 4px;")

    def _create_zoom_controls(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        btn_zoom_out = QPushButton("➖ Отдалить")
        btn_zoom_out.setFixedHeight(32)
        btn_zoom_out.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom_level - 0.2))

        btn_zoom_in = QPushButton("➕ Приблизить")
        btn_zoom_in.setFixedHeight(32)
        btn_zoom_in.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom_level + 0.2))

        btn_reset = QPushButton(" Сброс")
        btn_reset.setFixedHeight(32)
        btn_reset.clicked.connect(lambda: self.canvas.reset_view())

        btn_rotate = QPushButton("↻ Повернуть лист")
        btn_rotate.setFixedHeight(32)
        btn_rotate.clicked.connect(lambda: self.canvas.toggle_rotate())

        layout.addWidget(btn_zoom_out)
        layout.addWidget(btn_zoom_in)
        layout.addWidget(btn_reset)
        layout.addWidget(btn_rotate)
        layout.addStretch()

        return widget

    def _create_tabs_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.sheet_tabs = QTabWidget()
        self._refresh_tabs()
        layout.addWidget(self.sheet_tabs, stretch=1)

        btn_container = QWidget()
        btn_layout = QVBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)

        self.btn_add = QPushButton("＋")
        self.btn_add.setFixedWidth(44)
        self.btn_add.setFixedHeight(36)
        self.btn_add.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.btn_add.setToolTip("Добавить новый типоразмер листа")
        self.btn_add.clicked.connect(self._add_new_sheet)
        btn_layout.addWidget(self.btn_add)

        self.btn_remove = QPushButton("−")
        self.btn_remove.setFixedWidth(44)
        self.btn_remove.setFixedHeight(36)
        self.btn_remove.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.btn_remove.setToolTip("Удалить текущий лист")
        self.btn_remove.clicked.connect(self._remove_current_sheet)
        btn_layout.addWidget(self.btn_remove)

        layout.addWidget(btn_container)
        return header

    def _refresh_tabs(self):
        self.sheet_tabs.clear()
        for i, sheet in enumerate(self.sheets):
            tab = QWidget()
            self.sheet_tabs.addTab(tab, sheet.name)

        self.sheet_tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sheet_tabs.customContextMenuRequested.connect(self._on_tab_context_menu)

    def _on_tab_context_menu(self, position):
        index = self.sheet_tabs.tabBar().tabAt(position)
        if index < 0 or index >= len(self.sheets):
            return

        menu = QMenu(self)
        delete_action = QAction(f"Удалить \"{self.sheets[index].name}\"", self)
        delete_action.triggered.connect(lambda: self._remove_sheet_at(index))
        menu.addAction(delete_action)
        menu.exec(self.sheet_tabs.mapToGlobal(position))

    def _add_new_sheet(self):
        dialog = AddSheetDialog(theme=self.theme, parent=self)
        if dialog.exec() == AddSheetDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data:
                name, width, height = data
                new_sheet = Sheet(name=name, width=width, height=height)
                self.repository.add_sheet(new_sheet)
                self.sheets = self.repository.sheets
                self._refresh_tabs()
                self.sheet_tabs.setCurrentIndex(len(self.sheets) - 1)

    def _remove_current_sheet(self):
        index = self.sheet_tabs.currentIndex()
        self._remove_sheet_at(index)

    def _remove_sheet_at(self, index: int):
        if len(self.sheets) <= 1:
            QMessageBox.warning(self, "Внимание",
                "Нельзя удалить последний лист! Должен остаться хотя бы один типоразмер.")
            return

        if index < 0 or index >= len(self.sheets):
            return

        sheet_name = self.sheets[index].name
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Вы уверены, что хотите удалить лист \"{sheet_name}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.repository.remove_sheet(index)
            self.sheets = self.repository.sheets
            self._refresh_tabs()
            new_index = max(0, min(index, len(self.sheets) - 1))
            self.sheet_tabs.setCurrentIndex(new_index)

    def _create_input_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(280)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Размеры прокладки")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        shape_group = QButtonGroup(self)
        self.radio_rect = QRadioButton("Прямоугольная")
        self.radio_circle = QRadioButton("Круглая")
        self.radio_rect.setChecked(True)
        shape_group.addButton(self.radio_rect)
        shape_group.addButton(self.radio_circle)

        shape_layout = QVBoxLayout()
        shape_layout.addWidget(self.radio_rect)
        shape_layout.addWidget(self.radio_circle)
        layout.addLayout(shape_layout)

        layout.addWidget(QLabel("Длина (мм):"))
        self.input_length = QLineEdit()
        self.input_length.setPlaceholderText("150")
        layout.addWidget(self.input_length)

        layout.addWidget(QLabel("Ширина (мм):"))
        self.input_width = QLineEdit()
        self.input_width.setPlaceholderText("100")
        layout.addWidget(self.input_width)

        self.label_diameter = QLabel("Диаметр (мм):")
        self.label_diameter.hide()
        layout.addWidget(self.label_diameter)

        self.input_diameter = QLineEdit()
        self.input_diameter.setPlaceholderText("80")
        self.input_diameter.hide()
        layout.addWidget(self.input_diameter)

        # Поле зазора
        layout.addWidget(QLabel("Зазор между деталями (мм):"))
        self.input_gap = QLineEdit()
        self.input_gap.setPlaceholderText("0")
        self.input_gap.setToolTip("Расстояние между деталями для удобства вырезания")
        layout.addWidget(self.input_gap)

        # Поле количества
        layout.addWidget(QLabel("Количество деталей (необязательно):"))
        self.input_quantity = QLineEdit()
        self.input_quantity.setPlaceholderText("пусто = максимум на 1 лист")
        self.input_quantity.setToolTip("Если заполнено — рассчитает нужное количество листов")
        layout.addWidget(self.input_quantity)

        # Поле цены листа
        layout.addWidget(QLabel("Цена 1 листа (руб.):"))
        self.input_price = QLineEdit()
        self.input_price.setPlaceholderText("0.00")
        self.input_price.setToolTip("Введите стоимость одного листа материала для расчёта цены остатка")
        layout.addWidget(self.input_price)

        self.radio_rect.toggled.connect(self._on_shape_changed)

        layout.addSpacing(8)
        self.btn_calculate = QPushButton("Рассчитать и показать")
        self.btn_calculate.setFixedHeight(44)
        self.btn_calculate.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_calculate.clicked.connect(self._on_calculate)
        layout.addWidget(self.btn_calculate)

        # Кнопка поворота деталей
        self.btn_rotate_gasket = QPushButton("↻ Повернуть детали (90°)")
        self.btn_rotate_gasket.setFixedHeight(36)
        self.btn_rotate_gasket.setFont(QFont("Segoe UI", 11))
        self.btn_rotate_gasket.clicked.connect(self._on_rotate_gasket)
        self.btn_rotate_gasket.hide()
        layout.addWidget(self.btn_rotate_gasket)

        # Кнопка подбора листа
        self.btn_fit_sheet = QPushButton("📏 Подобрать оптимальный лист")
        self.btn_fit_sheet.setFixedHeight(36)
        self.btn_fit_sheet.setFont(QFont("Segoe UI", 11))
        self.btn_fit_sheet.clicked.connect(self._on_fit_sheet)
        layout.addWidget(self.btn_fit_sheet)

        # Панель статистики (под кнопкой расчёта)
        self.stats_panel = StatsPanel(theme=self.theme)
        layout.addWidget(self.stats_panel)

        layout.addStretch()
        return panel

    def _on_shape_changed(self, is_rect: bool):
        if is_rect:
            self.input_length.show()
            self.input_width.show()
            self.label_diameter.hide()
            self.input_diameter.hide()
            self.btn_rotate_gasket.show()
        else:
            self.input_length.hide()
            self.input_width.hide()
            self.label_diameter.show()
            self.input_diameter.show()
            self.btn_rotate_gasket.hide()

    def _on_calculate(self):
        """Основной расчёт — считаем оба варианта, показываем лучший."""
        gasket = self._read_gasket()
        if not gasket:
            return

        gap = self._safe_float(self.input_gap.text()) or 0.0
        quantity = int(self._safe_float(self.input_quantity.text()) or 0)
        sheet_price = self._safe_float(self.input_price.text()) or 0.0
        
        self.current_quantity = quantity

        sheet = self._get_current_sheet()
        if not sheet:
            return

        # Считаем оба варианта
        self.layout_normal, self.layout_rotated = PackingAlgorithm.pack_both_orientations(
            sheet, gasket, gap
        )

        # Показываем лучший
        if self.layout_normal.total_gaskets >= self.layout_rotated.total_gaskets:
            self.current_layout = self.layout_normal
        else:
            self.current_layout = self.layout_rotated

        # Расчёт стоимости остатка
        waste_price = 0.0
        if sheet_price > 0 and self.current_layout.sheet.area > 0:
            waste_price = (self.current_layout.waste_area / self.current_layout.sheet.area) * sheet_price

        self._display_current_layout(waste_price)

    def _on_rotate_gasket(self):
        """Переключение между прямым и повёрнутым вариантом."""
        if not self.layout_normal or not self.layout_rotated:
            return
        
        # Переключаем
        if self.current_layout == self.layout_normal:
            self.current_layout = self.layout_rotated
        else:
            self.current_layout = self.layout_normal
        
        # Пересчитываем цену для отображаемого варианта
        sheet_price = self._safe_float(self.input_price.text()) or 0.0
        waste_price = 0.0
        if sheet_price > 0 and self.current_layout.sheet.area > 0:
            waste_price = (self.current_layout.waste_area / self.current_layout.sheet.area) * sheet_price
            
        self._display_current_layout(waste_price)

    def _display_current_layout(self, waste_price: float = 0.0):
        """Отображает текущий вариант на холсте и в статистике."""
        if not self.current_layout:
            return
        
        self.canvas.set_layout(self.current_layout)
        self.stats_panel.update_from_layout(self.current_layout, self.current_quantity, waste_price)
        
        gasket_shape = "RECTANGLE" if self.radio_rect.isChecked() else "CIRCLE"
        self.stats_panel.update_orientation_label(
            self.current_layout.is_rotated, gasket_shape
        )

    def _on_fit_sheet(self):
        """Подбор оптимального листа из существующих типоразмеров."""
        gasket = self._read_gasket()
        if not gasket:
            return

        gap = self._safe_float(self.input_gap.text()) or 0.0
        quantity = int(self._safe_float(self.input_quantity.text()) or 0)
        
        if quantity <= 0:
            QMessageBox.information(self, "Внимание",
                "Для подбора листа укажите количество деталей в поле «Количество».")
            return

        best_sheet = None
        best_sheets_needed = float('inf')
        best_waste = float('inf')
        best_layout = None

        for sheet in self.sheets:
            layout = PackingAlgorithm.get_best_layout(sheet, gasket, gap)
            if layout.total_gaskets == 0:
                continue
            layout.calculate_sheets_needed(quantity)
            total_waste = layout.waste_area * layout.sheets_needed
            
            if layout.sheets_needed < best_sheets_needed:
                best_sheets_needed = layout.sheets_needed
                best_waste = total_waste
                best_sheet = sheet
                best_layout = layout
            elif layout.sheets_needed == best_sheets_needed and total_waste < best_waste:
                best_waste = total_waste
                best_sheet = sheet
                best_layout = layout

        if not best_sheet:
            QMessageBox.warning(self, "Не удалось подобрать",
                "Ни один из имеющихся листов не подходит для указанных деталей.")
            return

        for i, sheet in enumerate(self.sheets):
            if sheet.name == best_sheet.name:
                self.sheet_tabs.setCurrentIndex(i)
                break

        self.current_layout = best_layout
        self.current_quantity = quantity
        
        sheet_price = self._safe_float(self.input_price.text()) or 0.0
        waste_price = (best_layout.waste_area / best_layout.sheet.area) * sheet_price if sheet_price > 0 else 0.0
        
        self._display_current_layout(waste_price)

        QMessageBox.information(self, "Оптимальный лист найден",
            f"Лист: {best_sheet.name}\n"
            f"Деталей на листе: {best_layout.total_gaskets}\n"
            f"Нужно листов: {best_layout.sheets_needed}\n"
            f"Общие отходы: {int(best_waste)} мм²")

    def _read_gasket(self):
        """Считывает размеры прокладки из полей ввода."""
        if self.radio_rect.isChecked():
            length = self._safe_float(self.input_length.text())
            width = self._safe_float(self.input_width.text())
            if not length or not width:
                QMessageBox.warning(self, "Ошибка ввода", "Введите длину и ширину прокладки.")
                return None
            return Gasket(shape=GasketShape.RECTANGLE, length=length, width=width)
        else:
            diameter = self._safe_float(self.input_diameter.text())
            if not diameter:
                QMessageBox.warning(self, "Ошибка ввода", "Введите диаметр прокладки.")
                return None
            return Gasket(shape=GasketShape.CIRCLE, diameter=diameter)

    def _get_current_sheet(self):
        current_index = self.sheet_tabs.currentIndex()
        if current_index < 0 or current_index >= len(self.sheets):
            QMessageBox.information(self, "Внимание", "Выберите вкладку с листом для расчета.")
            return None
        return self.sheets[current_index]

    @staticmethod
    def _safe_float(text: str):
        try:
            value = float(text.replace(",", "."))
            return value if value > 0 else None
        except (ValueError, AttributeError):
            return None

    def _apply_stylesheet(self):
        c = self.colors
        qss = f"""
        QMainWindow {{ background-color: {c['app_background']}; }}
        QWidget {{
            background-color: {c['app_background']};
            color: {c['text_primary']};
            font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
            font-size: 13px;
        }}
        QFrame {{
            background-color: {c['panel_background']};
            border: 1px solid {c['border']};
            border-radius: 12px;
        }}
        QLabel {{ background-color: transparent; color: {c['text_primary']}; }}
        QLineEdit {{
            background-color: {c['input_background']};
            border: 1px solid {c['border']};
            border-radius: 8px;
            padding: 8px;
            color: {c['text_primary']};
            font-size: 13px;
        }}
        QLineEdit:focus {{ border: 2px solid {c['accent']}; }}
        QRadioButton {{ color: {c['text_primary']}; spacing: 10px; padding: 6px; font-size: 13px; }}
        QRadioButton::indicator {{
            width: 18px; height: 18px; border-radius: 9px;
            border: 2px solid {c['border']}; background-color: {c['input_background']};
        }}
        QRadioButton::indicator:checked {{ background-color: {c['accent']}; border: 2px solid {c['accent']}; }}
        QPushButton {{
            background-color: {c['accent']}; color: #FFFFFF; border: none;
            border-radius: 8px; padding: 8px 12px; font-weight: bold; font-size: 13px;
        }}
        QPushButton:hover {{ background-color: {c['accent_hover']}; }}
        QPushButton:pressed {{ background-color: {c['text_secondary']}; }}
        QTabWidget {{ background-color: transparent; border: none; }}
        QTabWidget::pane {{
            border: 1px solid {c['border']}; border-radius: 8px;
            background-color: {c['panel_background']};
        }}
        QTabBar::tab {{
            background-color: {c['panel_background']}; color: {c['text_secondary']};
            padding: 10px 20px; border: 1px solid {c['border']}; border-bottom: none;
            border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px;
            font-size: 13px;
        }}
        QTabBar::tab:selected {{
            background-color: {c['accent']}; color: #FFFFFF; font-weight: bold;
        }}
        QComboBox {{
            background-color: {c['input_background']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 6px 10px;
            color: {c['text_primary']};
            font-size: 13px;
            min-height: 28px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {c['panel_background']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            selection-background-color: {c['accent']};
            selection-color: #FFFFFF;
        }}
        QMessageBox {{ background-color: {c['app_background']}; }}
        QMessageBox QLabel {{ color: {c['text_primary']}; font-size: 14px; }}
        QMessageBox QPushButton {{
            background-color: {c['accent']}; color: white;
            padding: 8px 16px; min-width: 80px;
        }}
        QMenu {{
            background-color: {c['panel_background']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 4px;
        }}
        QMenu::item {{
            color: {c['text_primary']};
            padding: 8px 20px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {c['accent']};
            color: #FFFFFF;
        }}
        """
        self.setStyleSheet(qss)