"""Расчёт размещения прямоугольных и круглых прокладок на листе.

Зазор требуется *между* деталями; у границ листа он не добавляется.
Координаты прямоугольников — левый верхний угол, кругов — центр.
"""

import math
from typing import Tuple

from models.sheet import Sheet
from models.gasket import Gasket, GasketShape
from models.layout import Layout, PlacedGasket


class PackingAlgorithm:
    @staticmethod
    def _validate_gap(gap: float) -> None:
        if not math.isfinite(gap) or gap < 0:
            raise ValueError("Зазор между деталями должен быть конечным неотрицательным числом")

    @staticmethod
    def pack(sheet: Sheet, gasket: Gasket, gap: float = 0.0) -> Layout:
        PackingAlgorithm._validate_gap(gap)
        if not sheet.is_valid or not gasket.is_valid:
            return Layout(sheet=sheet)
        if gasket.shape == GasketShape.RECTANGLE:
            return PackingAlgorithm._pack_rectangles(sheet, gasket, gap)
        if gasket.shape == GasketShape.CIRCLE:
            return PackingAlgorithm._pack_circles(sheet, gasket, gap)
        return Layout(sheet=sheet)

    @staticmethod
    def pack_both_orientations(sheet: Sheet, gasket: Gasket, gap: float = 0.0) -> Tuple[Layout, Layout]:
        """Два независимых варианта: без поворота и с поворотом детали на 90°."""
        PackingAlgorithm._validate_gap(gap)
        normal = PackingAlgorithm.pack(sheet, gasket, gap)
        normal.is_rotated = False
        normal.analyze_remainders()

        if gasket.shape != GasketShape.RECTANGLE or not gasket.is_valid or not sheet.is_valid:
            return normal, normal

        turned = Gasket(shape=GasketShape.RECTANGLE, length=gasket.width, width=gasket.length)
        rotated = PackingAlgorithm._pack_rectangles(sheet, turned, gap)
        rotated.is_rotated = True
        rotated.analyze_remainders()
        return normal, rotated

    @staticmethod
    def get_best_layout(sheet: Sheet, gasket: Gasket, gap: float = 0.0) -> Layout:
        normal, rotated = PackingAlgorithm.pack_both_orientations(sheet, gasket, gap)
        return normal if normal.total_gaskets >= rotated.total_gaskets else rotated

    @staticmethod
    def _fit_count(available: float, piece: float, gap: float) -> int:
        """Количество деталей при размере n*piece + (n-1)*gap <= available."""
        if available < piece:
            return 0
        return max(0, math.floor((available + gap) / (piece + gap) + 1e-10))

    @staticmethod
    def _pack_rectangles(sheet: Sheet, gasket: Gasket, gap: float) -> Layout:
        cols = PackingAlgorithm._fit_count(sheet.width, gasket.length, gap)
        rows = PackingAlgorithm._fit_count(sheet.height, gasket.width, gap)
        layout = Layout(sheet=sheet)
        layout.placed_gaskets = [
            PlacedGasket(gasket=gasket, x=col * (gasket.length + gap),
                         y=row * (gasket.width + gap))
            for row in range(rows) for col in range(cols)
        ]
        layout.total_gaskets = len(layout.placed_gaskets)
        layout.calculate_waste()
        return layout

    @staticmethod
    def _pack_circles(sheet: Sheet, gasket: Gasket, gap: float) -> Layout:
        """Сравнить прямую сетку и оба направления шестигранной раскладки.

        Центры размещаем внутри листа на расстоянии не менее d/2 от края;
        шаг между соседними центрами = d + gap. Сравниваем оба варианта
        первого смещённого ряда, чтобы не терять прокладки у края.
        """
        diameter = gasket.diameter
        radius = diameter / 2
        step = diameter + gap
        pitch = step * math.sqrt(3) / 2
        best_centers = []

        # Прямая сетка иногда выгоднее шахматной (например, на узком листе).
        cols = PackingAlgorithm._fit_count(sheet.width, diameter, gap)
        rows = PackingAlgorithm._fit_count(sheet.height, diameter, gap)
        best_centers = [(radius + col * step, radius + row * step)
                        for row in range(rows) for col in range(cols)]

        # Шахматная сетка по строкам и по столбцам.
        for stagger_along_x in (True, False):
            main_limit = sheet.height if stagger_along_x else sheet.width
            cross_limit = sheet.width if stagger_along_x else sheet.height
            if main_limit < diameter or cross_limit < diameter:
                continue
            line_count = math.floor((main_limit - diameter) / pitch + 1e-10) + 1
            for start_shifted in (False, True):
                centers = []
                for line in range(line_count):
                    shift = step / 2 if (line % 2 == int(start_shifted)) else 0.0
                    free_length = cross_limit - diameter - shift
                    n = max(0, math.floor(free_length / step + 1e-10) + 1)
                    main_coordinate = radius + line * pitch
                    for i in range(n):
                        cross_coordinate = radius + shift + i * step
                        x, y = ((cross_coordinate, main_coordinate) if stagger_along_x
                                else (main_coordinate, cross_coordinate))
                        centers.append((x, y))
                if len(centers) > len(best_centers):
                    best_centers = centers

        layout = Layout(sheet=sheet)
        layout.placed_gaskets = [PlacedGasket(gasket=gasket, x=x, y=y)
                                 for x, y in best_centers]
        layout.total_gaskets = len(layout.placed_gaskets)
        layout.calculate_waste()
        return layout
