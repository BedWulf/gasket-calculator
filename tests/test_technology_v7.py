"""Технологические зазоры, прокатка, визуальные варианты и обратная совместимость."""
import copy
import json
import unittest
from pathlib import Path

from shapely.affinity import translate

from algorithms.nesting import (
    Part, NestResult, calculate_sheet, calculate_variants, allowed_angles,
    oriented_geometry, validate_result,
)
from algorithms.part_catalog import add_to_order, standard_part
from algorithms.project_io import result_from_dict
from algorithms.order_report import build_order_report
from algorithms.export_svg import build_svg


class TechnologyV7Tests(unittest.TestCase):
    def test_zero_kerf_matches_legacy(self):
        parts = [Part('Пластина', 'rectangle', quantity=2, width=50, height=30)]
        a = calculate_sheet(parts, 100, gap=2, margin=3, length_step=10)
        b = calculate_sheet(parts, 100, gap=2, margin=3, length_step=10,
                            kerf_mm=0, grain_direction='none')
        self.assertEqual(a.to_dict(), b.to_dict())
        self.assertEqual(a.to_dict()['schema_version'], 2)

    def test_kerf_affects_length_and_waste(self):
        parts = [Part('P', 'rectangle', quantity=2, width=50, height=30)]
        basic = calculate_sheet(parts, 100)
        cut = calculate_sheet(parts, 100, kerf_mm=2)
        self.assertGreater(cut.sheet_length, basic.sheet_length)
        self.assertEqual(cut.effective_gap, 2)
        self.assertEqual(cut.effective_margin, 1)
        self.assertTrue(validate_result(cut))
        self.assertGreater(cut.order_length_lower_bound, basic.order_length_lower_bound)
        self.assertEqual(cut.to_dict()['schema_version'], 3)

    def test_kerf_applies_additively_to_clearance(self):
        p = Part('Пластина', 'rectangle', quantity=3, width=40, height=30)
        result = calculate_sheet([p], 95, gap=3, margin=4, kerf_mm=2)
        shapes = [translate(oriented_geometry(p, q.angle), q.x, q.y)
                  for q in result.placements]
        for i, shape in enumerate(shapes):
            self.assertGreaterEqual(shape.bounds[0], 5-1e-6)
            self.assertGreaterEqual(shape.bounds[1], 5-1e-6)
            self.assertLessEqual(shape.bounds[2], 90+1e-6)
            for other in shapes[:i]:
                self.assertGreaterEqual(shape.distance(other), 5-1e-6)
        self.assertTrue(validate_result(result))

    def test_grain_constraints_control_rotation(self):
        p = Part('Направленная', 'rectangle', width=70, height=20,
                 grain_aligned=True)
        across = calculate_sheet([p], 80, grain_direction='width')
        along = calculate_sheet([p], 80, grain_direction='length')
        self.assertEqual(across.placements[0].angle % 180, 0)
        self.assertEqual(along.placements[0].angle % 180, 90)
        self.assertTrue(validate_result(along))
        self.assertEqual(set(allowed_angles(p, grain_direction='length')), {90,270})

    def test_grain_incompatible_inputs_are_rejected(self):
        p = Part('Без поворотов', 'rectangle', width=20, height=50,
                 grain_aligned=True, rotate_allowed=False)
        for axis in ('none', 'length'):
            with self.subTest(axis=axis), self.assertRaises(ValueError):
                calculate_sheet([p], 120, grain_direction=axis)
        for bad in (-1, float('nan'), float('inf')):
            with self.subTest(kerf=bad), self.assertRaises(ValueError):
                calculate_sheet([Part('Обычная', 'circle', diameter=30)],
                                100, kerf_mm=bad)
        with self.assertRaises(ValueError):
            calculate_sheet([Part('Обычная', 'circle', diameter=30)],
                            100, grain_direction='diagonal')

    def test_grain_polygon_fine_rotation(self):
        p = Part('Контур', 'polygon', points=[(0,0),(60,0),(60,15),(0,15)],
                 grain_aligned=True, rotation_step=15)
        self.assertEqual(allowed_angles(p, thorough=True, grain_direction='length'),
                         (90,270))
        result = calculate_sheet([p], 35, grain_direction='length', quality='thorough')
        self.assertIn(result.placements[0].angle, (90,270))
        self.assertTrue(validate_result(result))

    def test_roundtrip_v3_and_reject_tampering(self):
        p = Part('Прокладка', 'rectangle', width=35, height=30, grain_aligned=True)
        result = calculate_sheet([p], 100, kerf_mm=1.5, gap=2,
                                 margin=4, grain_direction='length')
        saved = result.to_dict()
        self.assertEqual(saved['schema_version'], 3)
        self.assertEqual(result_from_dict(saved).to_dict(), saved)
        for key, value in (('kerf_mm',-1),('grain_direction','bad'),
                           ('kerf_mm',float('inf')),('grain_direction','none')):
            bad = copy.deepcopy(saved)
            bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                result_from_dict(bad)
        bad_angle = copy.deepcopy(saved)
        bad_angle['placements'][0]['angle'] = 0
        with self.assertRaises(ValueError):
            result_from_dict(bad_angle)

    def test_older_examples_still_load(self):
        examples = Path(__file__).resolve().parent.parent / 'examples'
        for name in ('demo_request.json', 'nesting_in_ring_v4.json',
                     'round_compaction_v3.json'):
            with self.subTest(name=name):
                p = json.loads((examples / name).read_text(encoding='utf-8'))
                result = result_from_dict(p)
                self.assertTrue(validate_result(result))
                self.assertEqual(result.kerf_mm, 0)
                self.assertEqual(result.grain_direction, 'none')

    def test_reports_reflect_technology(self):
        part = Part('Направленная', 'rectangle', width=35, height=30, grain_aligned=True)
        r = calculate_sheet([part], 100, gap=2, margin=3,
                            kerf_mm=1, grain_direction='width')
        report = build_order_report(r)
        self.assertIn('Ширина реза: 1 мм', report)
        self.assertIn('Расчётное расстояние между контурами: 3 мм', report)
        self.assertIn('вдоль ширины', report)
        self.assertIn('ось X по материалу: да', report)
        self.assertIn('<svg', build_svg(r))

    def test_alternatives_valid_with_technology(self):
        parts = [Part('A', 'rectangle', quantity=3, width=42, height=30),
                 Part('B', 'circle', quantity=2, diameter=25)]
        results = calculate_variants(parts, 110, gap=2, margin=2,
                                     kerf_mm=1.25, max_variants=6)
        self.assertTrue(results)
        self.assertLessEqual(len(results), 6)
        self.assertEqual([r.sheet_length for r in results],
                         sorted(r.sheet_length for r in results))
        self.assertTrue(all(validate_result(r) for r in results))
        self.assertTrue(all(r.kerf_mm == 1.25 for r in results))

    def test_same_simple_form_with_different_grain_flag_not_merged(self):
        a = standard_part(kind='rectangle', width=30, height=40, name='R')
        b = standard_part(kind='rectangle', width=30, height=40,
                          name='R', grain_aligned=True)
        self.assertEqual(len(add_to_order([a], b)), 2)


if __name__ == '__main__':
    unittest.main()
