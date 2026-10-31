"""Расход листа, спецификация закупки и безопасная совместимость JSON."""
import copy
import unittest
from math import isclose

from algorithms.nesting import Part, NestResult, Placement, calculate_sheet, validate_result
from algorithms.order_report import build_order_report
from algorithms.project_io import result_from_dict


class OrderV5Tests(unittest.TestCase):
    def setUp(self):
        self.parts = [Part("Прямоугольник", "rectangle", width=50, height=30, quantity=2)]
        self.result = calculate_sheet(self.parts, 100, gap=2, margin=3, length_step=10)

    def test_optional_mass_not_fabricated(self):
        self.assertIsNone(self.result.purchased_mass_kg)
        self.assertIn("Масса: не рассчитана", build_order_report(self.result))

    def test_sheet_and_parts_mass_units(self):
        self.result.material_name = "Паронит"
        self.result.thickness_mm = 2
        self.result.density_g_cm3 = 1.7
        self.assertAlmostEqual(self.result.purchased_mass_kg,
                               self.result.sheet_width * self.result.sheet_length * 2 * 1.7 / 1e6)
        self.assertAlmostEqual(self.result.parts_mass_kg, 2*50*30*2*1.7/1e6)
        report = build_order_report(self.result)
        self.assertIn("Паронит", report)
        self.assertIn("Масса заказываемого листа", report)
        self.assertIn("50 × 30 мм", report)

    def test_lower_bound_includes_edge_margins(self):
        # 100x80: после отступов 10 мм с каждой стороны полезная ширина 80.
        p = Part("К", "rectangle", width=80, height=40, rotate_allowed=False)
        result = calculate_sheet([p], 100, margin=10, length_step=10)
        self.assertAlmostEqual(result.area_lower_bound, 60)
        self.assertAlmostEqual(result.order_length_lower_bound, 60)
        self.assertLessEqual(result.order_length_lower_bound, result.sheet_length)

    def test_min_height_by_allowed_rotations(self):
        # Ширина 40, прямоугольник 80x30 может поместиться только после 90°.
        p = Part("Узкая деталь", "rectangle", width=80, height=30)
        r = calculate_sheet([p], 40)
        self.assertAlmostEqual(r.order_length_lower_bound, 80)
        self.assertGreaterEqual(r.sheet_length, r.order_length_lower_bound)

    def test_new_schema_roundtrip(self):
        self.result.material_name = "Резина МБС"
        self.result.thickness_mm = 4
        self.result.density_g_cm3 = 1.24
        saved = self.result.to_dict()
        self.assertEqual(saved["schema_version"], 2)
        reopened = result_from_dict(saved)
        self.assertEqual(reopened.to_dict(), saved)

    def test_legacy_schema_still_opens(self):
        saved = self.result.to_dict()
        saved["schema_version"] = 1
        for key in ("material_name", "thickness_mm", "density_g_cm3"):
            del saved[key]
        reopened = result_from_dict(saved)
        self.assertIsNone(reopened.purchased_mass_kg)
        self.assertEqual(reopened.material_name, "")
        self.assertTrue(validate_result(reopened))

    def test_reject_tampered_overlap(self):
        saved = self.result.to_dict()
        saved["placements"][1]["x"] = saved["placements"][0]["x"]
        saved["placements"][1]["y"] = saved["placements"][0]["y"]
        with self.assertRaisesRegex(ValueError, "пересечения"):
            result_from_dict(saved)

    def test_reject_nan_and_negative_material_values(self):
        for key, value in (("sheet_length", float('nan')),
                           ("thickness_mm", -2), ("density_g_cm3", float('inf')),
                           ("length_step", 0)):
            saved = self.result.to_dict()
            saved[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                result_from_dict(saved)

    def test_reject_wrong_length_step(self):
        saved = self.result.to_dict()
        saved["length_step"] = 30
        if isclose(saved["sheet_length"] % 30, 0):
            saved["length_step"] = 19
        with self.assertRaises(ValueError):
            result_from_dict(saved)

    def test_invalid_layout_must_not_be_exported(self):
        self.result.placements[1].x = self.result.placements[0].x
        self.result.placements[1].y = self.result.placements[0].y
        with self.assertRaises(ValueError):
            build_order_report(self.result)

    def test_no_unexpected_schema(self):
        saved = self.result.to_dict()
        saved["schema_version"] = 404
        with self.assertRaisesRegex(ValueError, "версия"):
            result_from_dict(saved)


if __name__ == '__main__':
    unittest.main()
