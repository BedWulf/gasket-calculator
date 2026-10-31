"""Повороты сложных контуров, использование внутренних вырезов и совместимость."""
import unittest

from algorithms.nesting import (
    Part, Placement, NestResult, allowed_angles, calculate_sheet, validate_result
)


class RotationsAndHolesTests(unittest.TestCase):
    def test_custom_step_15_degrees(self):
        part = Part('Контур', 'polygon', points=[(0, 0), (70, 0), (70, 15), (0, 15)],
                    rotation_step=15)
        self.assertEqual(len(allowed_angles(part, thorough=True)), 24)
        self.assertEqual(allowed_angles(part, thorough=False), (0, 90, 180, 270))
        self.assertTrue(validate_result(NestResult(
            200, 200, [Placement(0, 40, 40, 15)], 0, 0, 1, [part])))
        self.assertFalse(validate_result(NestResult(
            200, 200, [Placement(0, 40, 40, 20)], 0, 0, 1, [part])))

    def test_backward_compatible_default_step(self):
        part = Part('Старый контур', 'polygon', points=[(0,0),(15,0),(15,10),(0,10)])
        self.assertEqual(part.rotation_step, 45)
        self.assertIn(45, allowed_angles(part, thorough=True))
        self.assertNotIn(15, allowed_angles(part, thorough=True))

    def test_rotation_forbidden_and_invalid_step(self):
        part = Part('Контур', 'polygon', points=[(0,0),(15,0),(15,10),(0,10)],
                    rotation_step=15, rotate_allowed=False)
        self.assertEqual(allowed_angles(part, thorough=True), (0,))
        self.assertFalse(validate_result(NestResult(
            200, 200, [Placement(0, 40, 40, 15)], 0, 0, 1, [part])))
        part.rotation_step = 20
        with self.assertRaisesRegex(ValueError, 'шаг поворота'):
            part.check()

    def test_real_circle_hole_receives_rectangle(self):
        # Вырез диаметром 70 мм содержит прямоугольник 40x30 мм.
        parts = [Part('Кольцо', 'ring', diameter=110, inner_diameter=70),
                 Part('Внутренняя деталь', 'rectangle', width=40, height=30)]
        result = calculate_sheet(parts, 110, quality='standard')
        self.assertEqual(result.sheet_length, 110)
        self.assertTrue(validate_result(result))
        self.assertEqual({p.part_index for p in result.placements}, {0, 1})

    def test_hole_gap_observed(self):
        parts = [Part('Кольцо', 'ring', diameter=110, inner_diameter=70),
                 Part('Вставка', 'rectangle', width=40, height=30)]
        result = calculate_sheet(parts, 110, gap=5, quality='standard')
        self.assertTrue(validate_result(result))
        # Деталь с зазором 5 мм должна находиться от кольца на расстоянии >= 5 мм.
        self.assertGreaterEqual(result.sheet_length, 110)

    def test_standard_never_worse_than_thorough(self):
        parts = [Part('L', 'polygon', points=[(0, 0), (95,0), (95,23),
                      (25,23), (25,80), (0,80)], rotation_step=15),
                 Part('Уплотнение', 'ring', diameter=40, inner_diameter=20)]
        basic = calculate_sheet(parts, 140, gap=2, quality='standard')
        advanced = calculate_sheet(parts, 140, gap=2, quality='thorough')
        self.assertTrue(validate_result(advanced))
        self.assertLessEqual(advanced.sheet_length, basic.sheet_length)


if __name__ == '__main__':
    unittest.main()
