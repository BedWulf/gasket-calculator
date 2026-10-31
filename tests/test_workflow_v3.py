"""Пользовательский сценарий v3: быстро добавить формы и автоматически подобрать длину."""
import unittest

from algorithms.nesting import Part, Placement, NestResult, calculate_sheet, validate_result
from algorithms.part_catalog import standard_part, add_to_order


class WorkflowV3Tests(unittest.TestCase):
    def test_quick_entry_various_shapes(self):
        order = []
        order = add_to_order(order, standard_part(kind='rectangle', width=70, height=30, quantity=2))
        order = add_to_order(order, standard_part(kind='ring', diameter=50, inner_diameter=25, quantity=4))
        order = add_to_order(order, standard_part(kind='circle', diameter=35, quantity=3))
        self.assertEqual(len(order), 3)
        self.assertEqual(sum(p.quantity for p in order), 9)
        result = calculate_sheet(order, 260, gap=3, margin=5, length_step=10)
        self.assertEqual(result.sheet_width, 260)
        self.assertEqual(len(result.placements), 9)
        self.assertTrue(validate_result(result))
        self.assertEqual(result.sheet_length % 10, 0)

    def test_identical_quick_part_merges_without_mutating_original(self):
        original = [standard_part(kind='circle', diameter=40, quantity=2)]
        result = add_to_order(original, standard_part(kind='circle', diameter=40, quantity=4))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].quantity, 6)
        self.assertEqual(original[0].quantity, 2)

    def test_different_nomenclature_not_merged(self):
        order = [standard_part(kind='rectangle', width=30, height=20, name='A')]
        result = add_to_order(order, standard_part(kind='rectangle', width=30, height=20, name='B'))
        self.assertEqual(len(result), 2)

    def test_rejected_invalid_and_overlimit(self):
        with self.assertRaises(ValueError):
            standard_part(kind='circle', diameter=0)
        with self.assertRaises(ValueError):
            standard_part(kind='polygon')
        original = [standard_part(kind='circle', diameter=40, quantity=299)]
        with self.assertRaisesRegex(ValueError, '300'):
            add_to_order(original, standard_part(kind='circle', diameter=40, quantity=2))
        self.assertEqual(original[0].quantity, 299)

    def test_dense_staggered_circles_reduce_sheet_length(self):
        # Старый алгоритм укладывал 4 круга двумя квадратными рядами на 200 мм.
        # Смещение второго ряда на полдиаметра позволяет 190 мм (шаг 10 мм).
        parts = [Part('Шайба', 'circle', quantity=4, diameter=100)]
        result = calculate_sheet(parts, 250, length_step=10, gap=0, margin=0)
        self.assertEqual(result.sheet_length, 190)
        self.assertTrue(validate_result(result))
        self.assertEqual(len(result.placements), 4)

    def test_staggered_with_gap_is_safe(self):
        result = calculate_sheet([Part('Шайба', 'circle', quantity=6, diameter=70)],
                                 180, length_step=5, gap=3, margin=5)
        self.assertTrue(validate_result(result))

    def test_complex_part_and_standard_on_same_sheet(self):
        complex_part = Part('L профиль', 'polygon', quantity=2,
                            points=[(0,0),(100,0),(100,25),(30,25),(30,90),(0,90)])
        base = [standard_part(kind='circle', quantity=2, diameter=30)]
        order = add_to_order(base, complex_part)
        result = calculate_sheet(order, 170, gap=2, margin=3, length_step=10)
        self.assertTrue(validate_result(result))

    def test_45_degree_complex_rotation_is_valid(self):
        part = Part('Контур', 'polygon', points=[(0,0),(20,0),(20,10),(0,10)])
        # Use a spacious sheet to test validation separately from heuristic placement.
        result = NestResult(100, 100, [Placement(0,30,30,45)],0,0,1,[part])
        self.assertTrue(validate_result(result))
        part.rotate_allowed = False
        self.assertFalse(validate_result(result))


if __name__ == '__main__':
    unittest.main()
