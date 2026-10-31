"""Проверки независимого выбора альтернативных раскладок."""
import unittest

from algorithms.nesting import Part, calculate_sheet, calculate_variants, validate_result
from algorithms.project_io import result_from_dict


class VariantTests(unittest.TestCase):
    def setUp(self):
        self.parts = [
            Part('Прокладка 1', 'rectangle', quantity=3, width=65, height=30),
            Part('Прокладка 2', 'rectangle', quantity=2, width=50, height=45),
            Part('Шайба', 'ring', quantity=2, diameter=45, inner_diameter=20),
        ]

    def test_best_is_backward_compatible(self):
        candidates = calculate_variants(self.parts, 120, 2, 3, 10, quality='thorough')
        best = calculate_sheet(self.parts, 120, 2, 3, 10, quality='thorough')
        self.assertEqual(candidates[0].to_dict(), best.to_dict())

    def test_candidates_are_distinct_valid_and_sorted(self):
        candidates = calculate_variants(self.parts, 120, 2, 3, 10)
        self.assertGreaterEqual(len(candidates), 2)
        self.assertLessEqual(len(candidates), 6)
        lengths = [r.sheet_length for r in candidates]
        self.assertEqual(lengths, sorted(lengths))
        signatures = []
        for result in candidates:
            self.assertTrue(validate_result(result))
            self.assertEqual(len(result.placements), 7)
            self.assertAlmostEqual(result.sheet_area-result.material_area, result.waste_area)
            self.assertEqual(result.to_dict(), result_from_dict(result.to_dict()).to_dict())
            signatures.append((result.sheet_length, tuple(sorted(
                (p.part_index, round(p.x, 4), round(p.y, 4), p.angle)
                for p in result.placements))))
        self.assertEqual(len(signatures), len(set(signatures)))

    def test_max_variants_and_invalid_limit(self):
        one = calculate_variants(self.parts, 120, max_variants=1)
        self.assertEqual(len(one), 1)
        for bad in (0, -2, 21, 1.5, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                calculate_variants(self.parts, 120, max_variants=bad)

    def test_fixed_width_and_length_step(self):
        results = calculate_variants(self.parts, 160, gap=4, margin=5,
                                     length_step=25, quality='thorough')
        for r in results:
            self.assertEqual(r.sheet_width, 160)
            self.assertEqual(r.sheet_length % 25, 0)
            self.assertGreaterEqual(r.sheet_length, r.order_length_lower_bound)

    def test_single_part_keeps_one_variant(self):
        results = calculate_variants([Part('Круг','circle',diameter=60)], 100)
        self.assertEqual(len(results), 1)
        self.assertTrue(validate_result(results[0]))


if __name__ == '__main__':
    unittest.main()
