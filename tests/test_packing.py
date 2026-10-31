"""Регрессионные тесты для расчёта нарезки (не требуют PyQt6)."""
import math
import unittest

from algorithms.packing import PackingAlgorithm
from algorithms.waste import WasteCalculator
from models.gasket import Gasket, GasketShape
from models.sheet import Sheet


class PackingTests(unittest.TestCase):
    def test_rectangle_exactly_fits_even_with_gap(self):
        layout = PackingAlgorithm.pack(Sheet('100×100', 100, 100),
                                       Gasket(GasketShape.RECTANGLE, 100, 100), 10)
        self.assertEqual(layout.total_gaskets, 1)
        self.assertEqual(layout.waste_area, 0)

    def test_gap_between_rectangles_not_at_sheet_edge(self):
        layout = PackingAlgorithm.pack(Sheet('210×100', 210, 100),
                                       Gasket(GasketShape.RECTANGLE, 100, 100), 10)
        self.assertEqual(layout.total_gaskets, 2)
        self.assertEqual([p.x for p in layout.placed_gaskets], [0, 110])

    def test_rotated_layout_is_independent(self):
        sheet = Sheet('100×60', 100, 60)
        gasket = Gasket(GasketShape.RECTANGLE, 60, 30)
        normal, rotated = PackingAlgorithm.pack_both_orientations(sheet, gasket)
        self.assertEqual(normal.total_gaskets, 2)
        self.assertEqual(rotated.total_gaskets, 3)
        self.assertIs(PackingAlgorithm.get_best_layout(sheet, gasket).is_rotated, True)
        self.assertTrue(all(p.x + p.gasket.length <= 100 for p in rotated.placed_gaskets))

    def test_circle_exactly_fits_even_with_gap(self):
        layout = PackingAlgorithm.pack(Sheet('100×100', 100, 100),
                                       Gasket(GasketShape.CIRCLE, diameter=100), 10)
        self.assertEqual(layout.total_gaskets, 1)
        self.assertAlmostEqual(layout.placed_gaskets[0].x, 50)
        self.assertAlmostEqual(layout.placed_gaskets[0].y, 50)

    def test_circle_uses_square_grid_when_better(self):
        layout = PackingAlgorithm.pack(Sheet('200×200', 200, 200),
                                       Gasket(GasketShape.CIRCLE, diameter=100))
        self.assertEqual(layout.total_gaskets, 4)

    def test_hexagonal_rows_can_fit_more(self):
        layout = PackingAlgorithm.pack(Sheet('100×115', 100, 115),
                                       Gasket(GasketShape.CIRCLE, diameter=40))
        self.assertEqual(layout.total_gaskets, 6)

    def test_circle_positions_inside_sheet_and_spaced(self):
        for w, h, d, gap in [(100, 100, 100, 20), (195, 190, 40, 5),
                             (125, 200, 35, 0), (120, 90, 20, 2)]:
            with self.subTest(w=w, h=h, d=d, gap=gap):
                layout = PackingAlgorithm.pack(Sheet('test', w, h),
                                               Gasket(GasketShape.CIRCLE, diameter=d), gap)
                points = [(p.x, p.y) for p in layout.placed_gaskets]
                for x, y in points:
                    self.assertGreaterEqual(x, d/2 - 1e-8)
                    self.assertGreaterEqual(y, d/2 - 1e-8)
                    self.assertLessEqual(x, w - d/2 + 1e-8)
                    self.assertLessEqual(y, h - d/2 + 1e-8)
                for i, a in enumerate(points):
                    for b in points[i+1:]:
                        self.assertGreaterEqual(math.dist(a, b), d + gap - 1e-8)

    def test_total_waste_for_partial_last_sheet(self):
        sheet = Sheet('100×100', 100, 100)
        gasket = Gasket(GasketShape.RECTANGLE, 50, 50)
        layout = PackingAlgorithm.pack(sheet, gasket)
        self.assertEqual(layout.total_gaskets, 4)
        self.assertEqual(WasteCalculator.calculate_total_waste(layout, 5), 7500)
        self.assertEqual(layout.sheets_needed, 2)
        self.assertEqual(WasteCalculator.calculate_total_waste(layout, 0), 0)

    def test_validation(self):
        sheet = Sheet('100×100', 100, 100)
        gasket = Gasket(GasketShape.RECTANGLE, 50, 50)
        for bad_gap in (-1, float('inf'), float('nan')):
            with self.assertRaises(ValueError):
                PackingAlgorithm.pack(sheet, gasket, bad_gap)
        self.assertFalse(Sheet('invalid', float('inf'), 100).is_valid)
        self.assertFalse(Gasket(GasketShape.CIRCLE, diameter=float('nan')).is_valid)


if __name__ == '__main__':
    unittest.main()
