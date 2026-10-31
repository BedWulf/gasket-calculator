"""Рабочее окно заказного листа: смешанный раскрой, SVG, сохранение, ручное перемещение.

Математика и геометрическая проверка вынесены в algorithms.nesting, чтобы
при смене интерфейса или последующем переносе в общую систему их не переписывать.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from PyQt6.QtCore import QPointF, Qt, QTimer, QSettings, QByteArray
from PyQt6.QtGui import QColor, QBrush, QPen, QPainter, QPainterPath, QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGraphicsItem, QGraphicsPathItem, QGraphicsRectItem,
    QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView, QScrollArea, QGridLayout, QFrame,
)
from shapely.affinity import translate

from algorithms.part_catalog import standard_part, add_to_order, STANDARD_KINDS
from algorithms.export_svg import build_svg, COLORS
from algorithms.order_report import build_order_report
from algorithms.project_io import result_from_dict
from algorithms.import_cad import import_svg, import_dxf
from ui.contour_editor import ContourEditor
from algorithms.nesting import (
    Part, Placement, NestResult, calculate_variants, oriented_geometry, validate_result,
)

SHAPE_NAMES = {
    "rectangle": "Прямоугольник",
    "rounded_rectangle": "Со скруглениями",
    "circle": "Круг",
    "ring": "Кольцо",
    "polygon": "Контур с отверстиями",
}


def _spin(value=0.0, minimum=0.0, maximum=100000.0, decimals=2) -> QDoubleSpinBox:
    w = QDoubleSpinBox()
    w.setDecimals(decimals)
    w.setRange(minimum, maximum)
    w.setValue(value)
    w.setSuffix(" мм")
    w.setSingleStep(1)
    return w


def _format_points(points) -> str:
    return "; ".join(f"{x:g},{y:g}" for x, y in points)


def _parse_points(value: str) -> list[tuple[float, float]]:
    if not value.strip():
        return []
    points = []
    for pair in value.split(";"):
        if not pair.strip():
            continue
        fields = pair.strip().split(",")
        if len(fields) != 2:
            raise ValueError("Координаты: вводите пары x,y, разделённые точкой с запятой")
        try:
            points.append((float(fields[0].strip()), float(fields[1].strip())))
        except ValueError as ex:
            raise ValueError("В координатах используйте точку как десятичный разделитель") from ex
    return points


class PartEditor(QDialog):
    """Ввод стандартных геометрий и произвольного контура через точки в мм."""

    def __init__(self, part: Part | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Параметры детали")
        self.resize(480, 510)
        self.name = QLineEdit(part.name if part else "Деталь")
        self.kind = QComboBox()
        for key, value in SHAPE_NAMES.items():
            self.kind.addItem(value, key)
        if part:
            self.kind.setCurrentIndex(self.kind.findData(part.kind))
        self.qty = QSpinBox()
        self.qty.setRange(1, 300)
        self.qty.setValue(part.quantity if part else 1)
        self.width_input = _spin(part.width if part else 100)
        self.height_input = _spin(part.height if part else 60)
        self.diameter = _spin(part.diameter if part else 100)
        self.inner = _spin(part.inner_diameter if part else 40)
        self.radius = _spin(part.corner_radius if part else 10)
        self.grain_aligned = QCheckBox("Ось X детали вдоль направления материала (прокатки/волокон)")
        self.grain_aligned.setChecked(part.grain_aligned if part else False)
        self.rotation = QCheckBox("Разрешить повороты")
        self.rotation.setChecked(part.rotate_allowed if part else True)
        self.rotation_step = QComboBox()
        for angle in (15, 30, 45, 90):
            self.rotation_step.addItem(f"{angle}°", angle)
        self.rotation_step.setCurrentIndex(self.rotation_step.findData(part.rotation_step if part else 45))
        self.rotation.toggled.connect(self.rotation_step.setEnabled)
        self.rotation_step.setEnabled(self.rotation.isChecked())
        self.points = QPlainTextEdit(_format_points(part.points) if part else "0,0; 150,0; 150,30; 80,30; 80,90; 0,90")
        self.points.setPlaceholderText("0,0; 150,0; 150,30; 80,30; 80,90; 0,90")
        self.points.setMaximumHeight(70)
        self.holes = QPlainTextEdit("\n".join(_format_points(row) for row in part.holes) if part else "")
        self.holes.setPlaceholderText("Каждое отверстие — новая строка: 10,10; 40,10; 40,40; 10,40")
        self.holes.setMaximumHeight(70)
        form = QFormLayout()
        for name, control in (
            ("Название:",self.name), ("Форма:",self.kind), ("Количество:",self.qty),
            ("Ширина:",self.width_input), ("Высота:",self.height_input),
            ("Внешний диаметр:",self.diameter), ("Внутренний диаметр:",self.inner),
            ("Радиус скругления:",self.radius),
            ("Вершины (x,y; x,y):",self.points), ("Отверстия (по строке):",self.holes),
        ):
            form.addRow(name,control)
        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(self.rotation)
        main.addWidget(self.grain_aligned)
        step_row = QFormLayout()
        step_row.addRow("Шаг поворота сложного контура:", self.rotation_step)
        main.addLayout(step_row)
        self.open_drawer = QPushButton("✏ Нарисовать / изменить контур мышью")
        self.open_drawer.clicked.connect(self.open_contour_editor)
        main.addWidget(self.open_drawer)
        help_label = QLabel("Координаты в миллиметрах. Для соблюдения прокатки отметьте ось X и "
                            "укажите направление листа в основном окне. Контур и отверстия замкнуты; "+
                            "последняя вершина соединяется с первой автоматически. Без самопересечений.")
        help_label.setWordWrap(True)
        main.addWidget(help_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        main.addWidget(buttons)
        self._part = None
        self.kind.currentIndexChanged.connect(self._update_fields)
        self._update_fields()
        # Здесь не применяем единый стиль окна: используется текущая тема основного приложения.

    def _update_fields(self):
        kind = self.kind.currentData()
        f = self.layout().itemAt(0).layout()
        visible = {
            self.width_input: kind in ("rectangle", "rounded_rectangle"),
            self.height_input: kind in ("rectangle", "rounded_rectangle"),
            self.diameter: kind in ("circle", "ring"),
            self.inner: kind == "ring",
            self.radius: kind == "rounded_rectangle",
            self.points: kind == "polygon",
            self.holes: kind == "polygon",
        }
        self.open_drawer.setVisible(kind == "polygon")
        self.rotation_step.setVisible(kind == "polygon")
        for field, show in visible.items():
            field.setVisible(show)
            label = f.labelForField(field)
            if label is not None:
                label.setVisible(show)

    def open_contour_editor(self):
        try:
            points = _parse_points(self.points.toPlainText())
            holes = [_parse_points(row) for row in self.holes.toPlainText().splitlines() if row.strip()]
            if points and len(points) < 3:
                raise ValueError('Наружный контур должен иметь минимум три вершины')
        except ValueError as exc:
            QMessageBox.warning(self, 'Координаты', str(exc))
            return
        d = ContourEditor(points, holes, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            outer, inner = d.get_geometry()
            self.points.setPlainText(_format_points(outer))
            self.holes.setPlainText("\n".join(_format_points(row) for row in inner))

    def _accept(self):
        try:
            part = Part(
                name=self.name.text().strip(), kind=self.kind.currentData(),
                quantity=self.qty.value(), width=self.width_input.value(), height=self.height_input.value(),
                diameter=self.diameter.value(), inner_diameter=self.inner.value(),
                corner_radius=self.radius.value(),
                points=_parse_points(self.points.toPlainText()) if self.kind.currentData() == "polygon" else [],
                holes=[_parse_points(row) for row in self.holes.toPlainText().splitlines() if row.strip()]
                if self.kind.currentData() == "polygon" else [],
                rotate_allowed=self.rotation.isChecked(),
                rotation_step=self.rotation_step.currentData(),
                grain_aligned=self.grain_aligned.isChecked(),
            )
            part.check()
            self._part = part
        except ValueError as e:
            QMessageBox.warning(self, "Проверьте деталь", str(e))
            return
        self.accept()

    def get_part(self) -> Part:
        return self._part


def _path_for_geom(geom):
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    polygons = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    for polygon in polygons:
        for ring in [polygon.exterior, *polygon.interiors]:
            coords = list(ring.coords)
            if not coords:
                continue
            path.moveTo(*coords[0])
            for x, y in coords[1:]:
                path.lineTo(x, y)
            path.closeSubpath()
    return path


class DragPartItem(QGraphicsPathItem):
    def __init__(self, dialog: "OrderSheetDialog", pos_idx: int, path: QPainterPath):
        super().__init__(path)
        self.dialog = dialog
        self.pos_idx = pos_idx
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.dialog.result is not None:
            target = QPointF(value)
            if not self.dialog.is_valid_position(self.pos_idx, target.x(), target.y()):
                return self.pos()
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.dialog.sync_item_position(self.pos_idx, self.pos())
        return super().itemChange(change, value)


class SheetView(QGraphicsView):
    def wheelEvent(self, event):
        self.scale(1.15 if event.angleDelta().y() > 0 else 1/1.15,
                   1.15 if event.angleDelta().y() > 0 else 1/1.15)


class VariantsComparisonDialog(QDialog):
    """До шести схем рядом: геометрия только для просмотра, выбор в основном окне."""

    def __init__(self, variants: list[NestResult], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Сравнение вариантов раскроя")
        self.resize(1050, 740)
        self.selected_index: int | None = None
        self.previews = []
        root = QVBoxLayout(self)
        note = QLabel("Сравните длину, площадь отходов и положение деталей. "
                      "Выбранный вариант появится в основном окне для проверки и редактирования.")
        note.setWordWrap(True)
        root.addWidget(note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        wrap = QWidget()
        grid = QGridLayout(wrap)
        for i, result in enumerate(variants):
            panel = QGroupBox(("Рекомендуемый · " if i == 0 else "") + f"Вариант {i+1}")
            layout = QVBoxLayout(panel)
            metrics = QLabel(f"<b>{result.sheet_width:g} × {result.sheet_length:g} мм</b>  |  "
                             f"Использование: {result.utilization:.1f}%<br>"
                             f"Отходы: {result.waste_area/1e6:.5f} м²")
            layout.addWidget(metrics)
            scene = QGraphicsScene(panel)
            scene.addRect(0, 0, result.sheet_width, result.sheet_length,
                          QPen(QColor('#343a40'), 1), QBrush(QColor('white')))
            for placement in result.placements:
                geometry = oriented_geometry(result.parts[placement.part_index], placement.angle)
                item = scene.addPath(_path_for_geom(geometry))
                color = QColor(COLORS[placement.part_index % len(COLORS)])
                color.setAlpha(170)
                item.setBrush(QBrush(color))
                item.setPen(QPen(color.darker(160), 0.75))
                item.setPos(placement.x, placement.y)
            view = QGraphicsView(scene)
            view.setRenderHint(QPainter.RenderHint.Antialiasing)
            view.setBackgroundBrush(QColor('#e6e8eb'))
            view.setMinimumSize(235, 205)
            layout.addWidget(view, 1)
            button = QPushButton("Выбрать эту раскладку")
            button.clicked.connect(lambda _, index=i: self._choose(index))
            layout.addWidget(button)
            grid.addWidget(panel, i // 3, i % 3)
            self.previews.append(view)
        scroll.setWidget(wrap)
        root.addWidget(scroll, stretch=1)
        close = QPushButton("Закрыть без выбора")
        close.clicked.connect(self.reject)
        root.addWidget(close)
        QTimer.singleShot(0, self._fit_previews)

    def _fit_previews(self):
        for view in self.previews:
            view.fitInView(view.scene().sceneRect().adjusted(-4, -4, 4, 4),
                           Qt.AspectRatioMode.KeepAspectRatio)

    def _choose(self, index: int):
        self.selected_index = index
        self.accept()


class OrderSheetDialog(QDialog):
    def __init__(self, parent=None, initial_parts: list[Part] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Заказной лист — смешанный раскрой")
        # Do not open a window taller than the available desktop on scaled screens.
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            work_area = screen.availableGeometry()
            self.resize(min(1300, max(700, work_area.width() - 24)),
                        min(780, max(500, work_area.height() - 32)))
        else:
            self.resize(1300, 780)
        self.parts: list[Part] = list(initial_parts or [])
        self.result: NestResult | None = None
        self.variants: list[NestResult] = []
        self._variant_index = -1
        self._updating_variants = False
        self.items: list[DragPartItem] = []
        self._loading_scene = False
        self._build_ui()
        self._refresh_table()
        QTimer.singleShot(0, self._restore_panel_state)

    def _build_ui(self):
        top = QVBoxLayout(self)
        title = QLabel("Расчёт длины листа — известна только ширина")
        title.setStyleSheet("font-size: 18px; font-weight: 700; padding: 4px;")
        top.addWidget(title)
        intro = QLabel("Добавьте простые детали через быстрый ввод, а сложные — через редактор или импорт. "
                       "После нажатия кнопки программа сама подберёт длину и расположение всех деталей.")
        intro.setWordWrap(True)
        top.addWidget(intro)
        split = QSplitter(Qt.Orientation.Horizontal)
        top.addWidget(split, stretch=1)
        self.main_splitter = split
        # Keep the calculation and variant controls accessible at all times.
        # Only the settings, quick-entry form and part list scroll.
        self.left_column = QWidget()
        left_column_layout = QVBoxLayout(self.left_column)
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        left_column_layout.setSpacing(6)
        split.addWidget(self.left_column)
        self.left_scroll = QScrollArea()
        self.left_scroll.setObjectName("orderInputScroll")
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.left_column.setMinimumWidth(340)
        self.left_column.setMaximumWidth(590)
        self.left_scroll.setMinimumWidth(335)
        self.left_scroll.setMinimumHeight(200)
        left = QWidget()
        left.setObjectName("orderInputContent")
        l = QVBoxLayout(left)
        l.setContentsMargins(5, 5, 9, 5)
        l.setSpacing(8)
        self.left_scroll.setWidget(left)
        left_column_layout.addWidget(self.left_scroll, stretch=1)
        settings = QGroupBox("Заказываемый лист")
        f = QGridLayout(settings)
        f.setHorizontalSpacing(8)
        f.setVerticalSpacing(5)
        self.sheet_width = _spin(1000, 1)
        self.gap = _spin(5)
        self.margin = _spin(5)
        self.step = _spin(10, 0.01)
        for row, column, label, control in (
            (0, 0, "Ширина:", self.sheet_width),
            (0, 2, "Зазор:", self.gap),
            (1, 0, "Кромка:", self.margin),
            (1, 2, "Шаг заказа:", self.step),
        ):
            f.addWidget(QLabel(label), row, column)
            f.addWidget(control, row, column + 1)
        self.sheet_width.setToolTip("Фиксированная ширина. Длина будет найдена автоматически.")
        self.step.setToolTip("Длина заказа округляется вверх до этого шага (например, 10 мм).")
        l.addWidget(settings)
        # Редко используемые реквизиты заказа скрыты, чтобы не замедлять
        # быстрый ввод простых форм: достаточно ширины, зазора и размеров.
        self.material_details_toggle = QPushButton("▶ Материал и масса (необязательно)")
        self.material_details_toggle.setCheckable(True)
        l.addWidget(self.material_details_toggle)
        self.material_details = QWidget()
        extra = QFormLayout(self.material_details)
        self.material_name = QLineEdit()
        self.material_name.setPlaceholderText("Например, паронит ПОН-Б")
        self.thickness = _spin(0, 0, 1000, 2)
        self.density = QDoubleSpinBox()
        self.density.setRange(0, 50)
        self.density.setDecimals(3)
        self.density.setSingleStep(0.1)
        self.density.setSuffix(" г/см³")
        self.density.setSpecialValueText("Не задана")
        self.thickness.setSpecialValueText("Не задана")
        extra.addRow("Марка материала:", self.material_name)
        extra.addRow("Толщина (для массы):", self.thickness)
        extra.addRow("Плотность (для массы):", self.density)
        self.material_details.setVisible(False)
        self.material_details_toggle.toggled.connect(self._toggle_material_details)
        l.addWidget(self.material_details)
        self.technology_toggle = QPushButton("▶ Технология резки и направление материала")
        self.technology_toggle.setCheckable(True)
        l.addWidget(self.technology_toggle)
        self.technology_details = QWidget()
        technology = QFormLayout(self.technology_details)
        self.kerf = _spin(0, 0, 100, 2)
        self.kerf.setToolTip("Дополнительно к зазору: учитывается ширина удаляемого резом материала. "
                             "Отступ от края увеличивается на половину ширины реза.")
        self.grain_direction = QComboBox()
        for label, value in (("Не задано", "none"),
                             ("Вдоль ширины листа (ось X)", "width"),
                             ("Вдоль длины листа (ось Y)", "length")):
            self.grain_direction.addItem(label, value)
        technology.addRow("Ширина реза:", self.kerf)
        technology.addRow("Направление материала:", self.grain_direction)
        self.technology_details.setVisible(False)
        self.technology_toggle.toggled.connect(self._toggle_technology_details)
        l.addWidget(self.technology_details)
        self._build_quick_entry(l)
        l.addWidget(QLabel("Список деталей — раскрой одним листом"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Наименование", "Форма / размер", "Шт."])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(lambda row, _: self.edit_part(row))
        # The list has its own scroll bar; keep actions below it reachable.
        self.table.setMinimumHeight(155)
        self.table.setMaximumHeight(225)
        l.addWidget(self.table)
        p_row = QHBoxLayout()
        for label, callback in (("Изменить",self.edit_part), ("Удалить",self.remove_part)):
            b = QPushButton(label)
            b.clicked.connect(callback)
            p_row.addWidget(b)
        l.addLayout(p_row)
        complex_row = QHBoxLayout()
        draw_button = QPushButton("✏ Создать сложную деталь")
        draw_button.clicked.connect(self.add_complex_part)
        complex_row.addWidget(draw_button)
        import_button = QPushButton("📂 Импорт SVG / DXF")
        import_button.clicked.connect(self.import_part)
        complex_row.addWidget(import_button)
        l.addLayout(complex_row)
        mode=QHBoxLayout()
        mode.addWidget(QLabel('Качество поиска:'))
        self.quality=QComboBox()
        self.quality.addItem('Быстро', 'standard')
        self.quality.addItem('Тщательно (до 55 деталей; повороты 15°–90°)', 'thorough')
        self.quality.setCurrentIndex(1)
        mode.addWidget(self.quality,stretch=1)
        l.addLayout(mode)
        self.calculate_button = QPushButton("📐 Подобрать длину листа автоматически")
        self.calculate_button.setObjectName("orderCalculateButton")
        self.calculate_button.setMinimumHeight(42)
        self.calculate_button.setToolTip("Кнопка доступна при любой прокрутке параметров слева.")
        self.calculate_button.clicked.connect(self.calculate)
        left_column_layout.addWidget(self.calculate_button)
        variant_row = QHBoxLayout()
        variant_row.addWidget(QLabel("Вариант раскроя:"))
        self.variant_combo = QComboBox()
        self.variant_combo.setEnabled(False)
        self.variant_combo.setToolTip(
            "Сравните варианты по длине и отходам; выбор меняет чертёж и спецификацию.")
        self.variant_combo.currentIndexChanged.connect(self._select_variant)
        variant_row.addWidget(self.variant_combo, stretch=1)
        left_column_layout.addLayout(variant_row)
        self.compare_button = QPushButton("▦ Сравнить схемы рядом")
        self.compare_button.setEnabled(False)
        self.compare_button.clicked.connect(self.compare_variants)
        left_column_layout.addWidget(self.compare_button)
        # Results are deliberately outside the left input scroller.
        # They remain visible while the operator edits a long parts list.
        r = QWidget()
        split.addWidget(r)
        right = QVBoxLayout(r)
        # Operator can allocate more space to either the drawing or the text.
        self.result_splitter = QSplitter(Qt.Orientation.Vertical)
        self.result_splitter.setObjectName("orderResultSplitter")
        self.result_splitter.setChildrenCollapsible(False)
        right.addWidget(self.result_splitter, stretch=1)
        self.scene = QGraphicsScene(self)
        self.view = SheetView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(QColor("#e6e8eb"))
        self.view.setMinimumSize(300, 190)
        self.result_splitter.addWidget(self.view)

        results_box = QGroupBox("Результат расчёта и рекомендуемая длина листа")
        results_layout = QVBoxLayout(results_box)
        results_layout.setContentsMargins(6, 6, 6, 6)
        self.summary_scroll = QScrollArea()
        self.summary_scroll.setObjectName("orderResultScroll")
        self.summary_scroll.setWidgetResizable(True)
        self.summary_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.summary_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.summary_scroll.setMinimumHeight(108)
        self.summary = QLabel(
            "Укажите ширину и количество деталей. Длина вычисляется автоматически. "
            "Все размеры — в мм.")
        self.summary.setObjectName("orderResultText")
        self.summary.setWordWrap(True)
        self.summary.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.summary.setContentsMargins(8, 6, 8, 6)
        self.summary_scroll.setWidget(self.summary)
        results_layout.addWidget(self.summary_scroll)
        self.result_splitter.addWidget(results_box)
        self.result_splitter.setSizes([520, 170])
        hint = QLabel("Колёсико — масштаб • ЛКМ по детали — перемещение • Ctrl+S — сохранение проекта. "+
                      "Красивый чертёж не заменяет технологическую проверку реза.")
        hint.setWordWrap(True)
        right.addWidget(hint)
        # Two compact rows avoid clipped action buttons on narrow screens.
        buttons = QGridLayout()
        buttons.setHorizontalSpacing(6)
        buttons.setVerticalSpacing(4)
        for i, (text, slot) in enumerate((
            ("Сохранить JSON", self.save_project),
            ("Открыть JSON", self.load_project),
            ("Экспорт SVG", self.export_svg),
            ("Спецификация TXT", self.export_report),
            ("Вписать лист", self.fit_view),
        )):
            b = QPushButton(text)
            b.clicked.connect(slot)
            buttons.addWidget(b, i // 3, i % 3)
        right.addLayout(buttons)
        split.setChildrenCollapsible(False)
        split.setSizes([475, 825])
        # После изменения входных параметров прежний раскрой неактуален.
        for spin in (self.sheet_width, self.gap, self.margin, self.step,
                     self.thickness, self.density, self.kerf):
            spin.valueChanged.connect(self._reset_layout)
        self.material_name.textChanged.connect(self._reset_layout)
        self.quality.currentIndexChanged.connect(self._reset_layout)
        self.grain_direction.currentIndexChanged.connect(self._reset_layout)

    def _toggle_material_details(self, visible: bool):
        self.material_details.setVisible(visible)
        self.material_details_toggle.setText(
            ("▼" if visible else "▶") + " Материал и масса (необязательно)")

    def _toggle_technology_details(self, visible: bool):
        self.technology_details.setVisible(visible)
        self.technology_toggle.setText(
            ("▼" if visible else "▶") + " Технология резки и направление материала")

    def _build_quick_entry(self, layout: QVBoxLayout):
        """Compact, one-click standard shape entry, without opening a dialog."""
        group = QGroupBox("Быстро добавить типовую деталь")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(5)
        self.quick_grid = grid
        self.quick_kind = QComboBox()
        for kind in STANDARD_KINDS:
            self.quick_kind.addItem(SHAPE_NAMES[kind], kind)
        self.quick_name = QLineEdit()
        self.quick_name.setPlaceholderText("Название (необязательно)")
        self.quick_qty = QSpinBox()
        self.quick_qty.setRange(1, 300)
        self.quick_qty.setValue(1)
        self.quick_width = _spin(100, 0.01)
        self.quick_height = _spin(60, 0.01)
        self.quick_diameter = _spin(100, 0.01)
        self.quick_inner = _spin(40, 0.01)
        self.quick_radius = _spin(10, 0)
        self.quick_rotation = QCheckBox("Поворот разрешён")
        self.quick_rotation.setChecked(True)
        self.quick_grain = QCheckBox("Учитывать направление материала")
        self.quick_grain.setToolTip("Ось X детали ориентирована вдоль прокатки/волокон.")
        grid.addWidget(QLabel("Форма:"), 0, 0)
        grid.addWidget(self.quick_kind, 0, 1)
        grid.addWidget(QLabel("Штук:"), 0, 2)
        grid.addWidget(self.quick_qty, 0, 3)
        grid.addWidget(self.quick_name, 1, 0, 1, 4)
        self._quick_dimension_widgets = {}
        for label, control, row, column in (
            ("Ширина:", self.quick_width, 2, 0),
            ("Высота:", self.quick_height, 2, 2),
            ("Диаметр:", self.quick_diameter, 2, 0),
            ("Внутр. Ø:", self.quick_inner, 2, 2),
            ("Радиус R:", self.quick_radius, 3, 0),
        ):
            caption = QLabel(label)
            self._quick_dimension_widgets[control] = caption
            grid.addWidget(caption, row, column)
            grid.addWidget(control, row, column + 1)
        grid.addWidget(self.quick_rotation, 4, 0, 1, 2)
        grid.addWidget(self.quick_grain, 4, 2, 1, 2)
        self.quick_submit = QPushButton("＋ Добавить в список")
        self.quick_submit.setMinimumHeight(34)
        grid.addWidget(self.quick_submit, 5, 0, 1, 4)
        self.quick_submit.clicked.connect(self.add_quick_part)
        self.quick_name.returnPressed.connect(self.add_quick_part)
        self.quick_kind.currentIndexChanged.connect(self._update_quick_fields)
        self._update_quick_fields()
        layout.addWidget(group)

    def _update_quick_fields(self):
        kind = self.quick_kind.currentData()
        visible = {
            self.quick_width: kind in ("rectangle", "rounded_rectangle"),
            self.quick_height: kind in ("rectangle", "rounded_rectangle"),
            self.quick_diameter: kind in ("circle", "ring"),
            self.quick_inner: kind == "ring",
            self.quick_radius: kind == "rounded_rectangle",
        }
        for field, show in visible.items():
            field.setVisible(show)
            self._quick_dimension_widgets[field].setVisible(show)

    def _restore_panel_state(self):
        """Restore sizes without restoring window position across monitors."""
        settings = QSettings("GasketCalculator", "OrderSheet")
        for key, splitter in (("input_splitter", self.main_splitter),
                              ("result_splitter", self.result_splitter)):
            state = settings.value(key)
            if isinstance(state, QByteArray) and not state.isEmpty():
                splitter.restoreState(state)
        for key, toggle in (("material_open", self.material_details_toggle),
                            ("technology_open", self.technology_toggle)):
            toggle.setChecked(str(settings.value(key, "false")).lower() == "true")

    def closeEvent(self, event):
        """Keep operator-adjusted panel proportions for the next launch."""
        settings = QSettings("GasketCalculator", "OrderSheet")
        settings.setValue("input_splitter", self.main_splitter.saveState())
        settings.setValue("result_splitter", self.result_splitter.saveState())
        settings.setValue("material_open", self.material_details_toggle.isChecked())
        settings.setValue("technology_open", self.technology_toggle.isChecked())
        super().closeEvent(event)

    def add_quick_part(self):
        """Ввод типовой детали без открытия диалогов; одинаковые строки объединяются."""
        try:
            part = standard_part(
                kind=self.quick_kind.currentData(), name=self.quick_name.text(),
                quantity=self.quick_qty.value(), width=self.quick_width.value(),
                height=self.quick_height.value(), diameter=self.quick_diameter.value(),
                inner_diameter=self.quick_inner.value(), corner_radius=self.quick_radius.value(),
                rotate_allowed=self.quick_rotation.isChecked(),
                grain_aligned=self.quick_grain.isChecked())
            self.parts = add_to_order(self.parts, part)
        except ValueError as exc:
            QMessageBox.warning(self, "Проверьте размеры детали", str(exc))
            return
        self._refresh_table()
        self._reset_layout()
        self.quick_qty.setValue(1)
        self.quick_name.clear()
        self.quick_name.setFocus()

    def add_complex_part(self):
        """Сложная форма рисуется отдельно и только затем попадает в заказ."""
        part = Part(name="Сложная прокладка", kind="polygon", quantity=1,
                    points=[(0,0),(150,0),(150,30),(80,30),(80,90),(0,90)])
        editor = PartEditor(part, self)
        editor.kind.setEnabled(False)
        editor.setWindowTitle("Сложная деталь — рисунок, отверстия, координаты")
        if editor.exec() == QDialog.DialogCode.Accepted:
            try:
                self.parts = add_to_order(self.parts, editor.get_part())
            except ValueError as exc:
                QMessageBox.warning(self, "Не удалось добавить", str(exc))
                return
            self._refresh_table()
            self._reset_layout()

    def _part_desc(self, p: Part):
        if p.kind in ("rectangle", "rounded_rectangle"):
            return f"{SHAPE_NAMES[p.kind]} {p.width:g}×{p.height:g}"
        if p.kind == "polygon":
            return f"Контур ({len(p.points)} вершин, {len(p.holes)} отв.)"
        if p.kind == "ring":
            return f"Ø{p.diameter:g} / Ø{p.inner_diameter:g}"
        return f"Ø{p.diameter:g}"

    def _refresh_table(self):
        self.table.setRowCount(len(self.parts))
        for row, part in enumerate(self.parts):
            for col, value in enumerate((part.name, self._part_desc(part), str(part.quantity))):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _reset_layout(self):
        self.result = None
        self.variants = []
        self._variant_index = -1
        self._updating_variants = True
        self.variant_combo.clear()
        self.variant_combo.setEnabled(False)
        self.compare_button.setEnabled(False)
        self._updating_variants = False
        self.scene.clear()
        self.items = []
        self.summary.setText("Данные изменены. Нажмите «Подобрать длину листа автоматически».")

    def add_part(self):
        """Для обратной совместимости фокусируем форму быстрого ввода."""
        self.quick_name.setFocus()

    def edit_part(self, row=None):
        row = self.table.currentRow() if not isinstance(row, int) else row
        if row < 0 or row >= len(self.parts):
            return
        d = PartEditor(self.parts[row], self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.parts[row] = d.get_part()
            self._refresh_table()
            self._reset_layout()

    def remove_part(self):
        row = self.table.currentRow()
        if row >= 0:
            del self.parts[row]
            self._refresh_table()
            self._reset_layout()

    def import_part(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Импорт замкнутой детали', '',
                                               'Чертежи (*.svg *.dxf);;SVG (*.svg);;DXF (*.dxf)')
        if not path:
            return
        try:
            suffix=Path(path).suffix.lower()
            if suffix == '.dxf':
                try:
                    part=import_dxf(path)
                except ValueError as exc:
                    if 'неизвестные единицы' not in str(exc):
                        raise
                    answer=QMessageBox.question(self, 'Масштаб DXF',
                        'В DXF не указаны единицы. Подтвердить, что 1 единица чертежа = 1 мм?\n'
                        'Если неизвестно, выберите «Нет» и уточните масштаб в CAD.',
                        QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No)
                    if answer!=QMessageBox.StandardButton.Yes:return
                    part=import_dxf(path,assume_mm=True)
            elif suffix == '.svg':
                try:
                    part=import_svg(path)
                except ValueError as exc:
                    if 'единиц' not in str(exc):raise
                    answer=QMessageBox.question(self, 'Масштаб SVG',
                        'SVG не содержит явно заданных единиц. Предположить миллиметры для единиц чертежа?\n'
                        'Если исходный масштаб неизвестен, нажмите «Нет».',
                        QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No)
                    if answer!=QMessageBox.StandardButton.Yes:return
                    part=import_svg(path,assume_unit='mm')
            else:
                raise ValueError('Поддерживаются SVG и DXF')
            d=PartEditor(part,self)
            if d.exec()==QDialog.DialogCode.Accepted:
                self.parts = add_to_order(self.parts, d.get_part())
                self._refresh_table()
                self._reset_layout()
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Невозможно импортировать',str(exc))

    @staticmethod
    def _variant_label(index: int, result: NestResult) -> str:
        """Информация для сравнения без выдачи эвристики за оптимум."""
        return (f"{index + 1}. {result.sheet_width:g} × {result.sheet_length:g} мм · "
                f"отходы {result.waste_area / 1e6:.4f} м² · "
                f"исп. {result.utilization:.1f}%")

    def _set_variants(self, candidates: list[NestResult], *, loaded: bool = False):
        """Смену списка синхронизируем с Qt без промежуточного переключения."""
        self._updating_variants = True
        self.variants = candidates
        self._variant_index = 0 if candidates else -1
        self.variant_combo.clear()
        for i, candidate in enumerate(candidates):
            label = self._variant_label(i, candidate)
            self.variant_combo.addItem(("Загружено · " if loaded else "") + label)
        self.variant_combo.setEnabled(len(candidates) > 1)
        self.compare_button.setEnabled(len(candidates) > 1)
        self.variant_combo.setCurrentIndex(self._variant_index)
        self._updating_variants = False
        self.result = deepcopy(candidates[0]) if candidates else None
        if self.result:
            self._draw_scene()

    def _select_variant(self, index: int):
        if self._updating_variants or index < 0 or index >= len(self.variants):
            return
        if self.result is not None and 0 <= self._variant_index < len(self.variants):
            # Пользователь мог передвинуть детали вручную. Его исправленная
            # раскладка остаётся доступной при переключении туда и обратно.
            self.variants[self._variant_index] = deepcopy(self.result)
        self._variant_index = index
        self.result = deepcopy(self.variants[index])
        self._draw_scene()

    def compare_variants(self):
        if len(self.variants) < 2:
            return
        if self.result is not None and 0 <= self._variant_index < len(self.variants):
            self.variants[self._variant_index] = deepcopy(self.result)
        dialog = VariantsComparisonDialog(self.variants, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_index is not None:
            self.variant_combo.setCurrentIndex(dialog.selected_index)

    def calculate(self):
        try:
            candidates = calculate_variants(
                self.parts, self.sheet_width.value(), self.gap.value(),
                self.margin.value(), self.step.value(),
                quality=self.quality.currentData(), max_variants=6,
                kerf_mm=self.kerf.value(),
                grain_direction=self.grain_direction.currentData())
            for candidate in candidates:
                candidate.material_name = self.material_name.text().strip()
                candidate.thickness_mm = self.thickness.value()
                candidate.density_g_cm3 = self.density.value()
        except (ValueError, RuntimeError) as e:
            QMessageBox.warning(self, "Не удалось рассчитать", str(e))
            return
        self._set_variants(candidates)

    def _draw_scene(self):
        if not self.result:
            return
        result = self.result
        self._loading_scene = True
        self.scene.clear()
        self.items = []
        sheet = self.scene.addRect(0,0,result.sheet_width,result.sheet_length,
                                   QPen(QColor("#444e5a"), 2), QBrush(QColor("#fefdf9")))
        sheet.setZValue(-1)
        if result.margin:
            self.scene.addRect(result.margin,result.margin,
                result.sheet_width-2*result.margin,result.sheet_length-2*result.margin,
                QPen(QColor("#aeb6c0"),1,Qt.PenStyle.DashLine))
        for idx, p in enumerate(result.placements):
            geom = oriented_geometry(result.parts[p.part_index], p.angle)
            item = DragPartItem(self, idx, _path_for_geom(geom))
            col = QColor(COLORS[p.part_index % len(COLORS)])
            col.setAlpha(180)
            item.setBrush(QBrush(col))
            item.setPen(QPen(col.darker(150), 1))
            self.scene.addItem(item)
            item.setPos(p.x,p.y)
            item.setToolTip(f"{result.parts[p.part_index].name}, поворот {p.angle}°")
            self.items.append(item)
        self._loading_scene = False
        self._update_summary()
        self.fit_view()

    def fit_view(self):
        if self.result:
            self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-25,-25,25,25),
                                Qt.AspectRatioMode.KeepAspectRatio)

    def _update_summary(self):
        if not self.result:
            return
        r = self.result
        self.summary.setText(
            f"<b>Рекомендуемый заказ: {r.sheet_width:g} × {r.sheet_length:g} мм</b><br>"
            f"Деталей: {len(r.placements)} шт. ({len(r.parts)} типоразмеров)<br>"
            f"Площадь деталей: {r.material_area/1e6:.4f} м²<br>"
            f"Площадь листа: {r.sheet_area/1e6:.4f} м²<br>"
            f"Использование материала: {r.utilization:.1f}%<br>"
            f"Отходы (включая зазоры): {r.waste_area/1e6:.4f} м²<br>"
            f"Расчётный промежуток с резом: {r.effective_gap:g} мм; "
            f"допуск у края: {r.effective_margin:g} мм.<br>"
            f"Теоретическая нижняя граница длины: {r.order_length_lower_bound:g} мм.<br>"
            + (f"Масса листа: {r.purchased_mass_kg:.3f} кг; "
               f"масса деталей: {r.parts_mass_kg:.3f} кг.<br>"
               if r.purchased_mass_kg is not None else "") +
            "<i>Длина получена эвристически. Перед заказом проверьте технологические допуски."+
            (" Тщательный поиск ограничен 55 деталями." if self.quality.currentData() == "thorough" and len(r.placements)>55 else "")+
            "</i>")

    def is_valid_position(self, index: int, x: float, y: float) -> bool:
        r = self.result
        if r is None:
            return False
        p = r.placements[index]
        g = translate(oriented_geometry(r.parts[p.part_index], p.angle),x,y)
        a,b,c,d = g.bounds
        eps = 1e-6
        if (a < r.effective_margin-eps or b < r.effective_margin-eps or
                c > r.sheet_width-r.effective_margin+eps or
                d > r.sheet_length-r.effective_margin+eps):
            return False
        for j, other_p in enumerate(r.placements):
            if index == j:
                continue
            other = translate(oriented_geometry(r.parts[other_p.part_index],other_p.angle),other_p.x,other_p.y)
            if (g.intersection(other).area > eps if r.effective_gap == 0 else
                    g.distance(other) < r.effective_gap-eps):
                return False
        return True

    def sync_item_position(self, index: int, point: QPointF):
        if self._loading_scene or not self.result:
            return
        p = self.result.placements[index]
        p.x, p.y = round(point.x(), 5), round(point.y(), 5)

    def save_project(self):
        if self.result is None:
            QMessageBox.information(self,"Сохранение", "Сначала рассчитайте лист")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить задание", "раскрой.json", "JSON (*.json)")
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(self.result.to_dict(),ensure_ascii=False,indent=2),encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self,"Ошибка сохранения",str(exc))

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть задание", "", "JSON (*.json)")
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            result = result_from_dict(payload)
            parts = result.parts
            # Сигналы изменения параметров сбрасывают старый чертёж,
            # поэтому сохранённый result устанавливаем только после параметров.
            self.sheet_width.setValue(result.sheet_width)
            self.gap.setValue(result.gap)
            self.margin.setValue(result.margin)
            self.step.setValue(result.length_step)
            self.kerf.setValue(result.kerf_mm)
            self.grain_direction.setCurrentIndex(
                self.grain_direction.findData(result.grain_direction))
            self.technology_toggle.setChecked(bool(result.kerf_mm or result.grain_direction != "none"))
            self.material_name.setText(result.material_name)
            self.thickness.setValue(result.thickness_mm)
            self.density.setValue(result.density_g_cm3)
            self.material_details_toggle.setChecked(bool(result.material_name or
                result.thickness_mm or result.density_g_cm3))
            self.parts = parts
            self._refresh_table()
            self._set_variants([result], loaded=True)
        except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
            QMessageBox.warning(self,"Не удалось открыть",str(exc))

    def export_svg(self):
        if self.result is None:
            QMessageBox.information(self,"Экспорт", "Сначала рассчитайте лист")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Экспортировать контуры", "раскрой.svg", "SVG (*.svg)")
        if not path:
            return
        try:
            Path(path).write_text(build_svg(self.result), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self,"Ошибка экспорта",str(exc))

    def export_report(self):
        """Спецификация закупки; не заменяет утверждённую технологическую карту."""
        if self.result is None:
            QMessageBox.information(self, "Спецификация", "Сначала рассчитайте лист")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Спецификация заказного листа",
                                               "заказ_листа.txt", "Текст UTF-8 (*.txt)")
        if not path:
            return
        try:
            Path(path).write_text(build_order_report(self.result), encoding="utf-8-sig")
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Ошибка экспорта спецификации", str(exc))
