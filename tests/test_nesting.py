"""Автоматические проверки заказного листа и сложных контуров."""
import json
import math
import random
import unittest

from algorithms.nesting import (
    NestResult, Part, Placement, calculate_sheet, oriented_geometry, validate_result,
)


class NestingTests(unittest.TestCase):
    def test_six_rectangles_exact_fit(self):
        r = calculate_sheet([Part("A", "rectangle", quantity=6, width=100, height=50)],200)
        self.assertEqual(r.sheet_length, 150)
        self.assertEqual(len(r.placements), 6)
        self.assertTrue(validate_result(r))
        self.assertAlmostEqual(r.utilization, 100)

    def test_multiple_types_in_one_sheet(self):
        parts = [Part("Прямоугольная", "rectangle", quantity=4, width=90, height=55),
                 Part("Круглая", "circle", quantity=2, diameter=50),
                 Part("Кольцевая", "ring", quantity=1, diameter=60, inner_diameter=20)]
        r = calculate_sheet(parts, 260, gap=3, margin=5, length_step=10)
        self.assertEqual(len(r.placements), 7)
        self.assertTrue(validate_result(r))
        self.assertEqual(round(r.sheet_length)%10, 0)
        self.assertGreater(r.waste_area,0)

    def test_rotation_allows_fit_narrow_sheet(self):
        r = calculate_sheet([Part("A", "rectangle", width=140, height=90)], 100)
        self.assertEqual(r.placements[0].angle,90)
        self.assertEqual(r.sheet_length,140)

    def test_fixed_width_too_small(self):
        with self.assertRaisesRegex(ValueError, "удаётся разместить"):
            calculate_sheet([Part("A", "rectangle", width=150, height=160)],100)

    def test_margin_and_gap(self):
        r = calculate_sheet([Part("A", "rectangle", quantity=2, width=100, height=50)],105,
                            gap=5,margin=2,length_step=10)
        self.assertTrue(validate_result(r))
        self.assertGreaterEqual(r.sheet_length,110)
        self.assertGreaterEqual(min(p.x for p in r.placements),2)
        self.assertGreaterEqual(min(p.y for p in r.placements),2)

    def test_ring_has_hole(self):
        p = Part("Кольцо", "ring", diameter=100, inner_diameter=50)
        g = p.geometry()
        self.assertEqual(len(g.interiors),1)
        self.assertAlmostEqual(p.actual_area(), math.pi*(100**2-50**2)/4)

    def test_polygon_with_hole(self):
        p = Part("Рамка", "polygon", points=[(0,0),(140,0),(140,100),(0,100)],
                 holes=[[(30,20),(110,20),(110,80),(30,80)]])
        self.assertAlmostEqual(p.actual_area(),140*100-80*60)
        r = calculate_sheet([p,Part("Шайба", "circle",diameter=20)],160,gap=2,margin=5)
        self.assertTrue(validate_result(r))

    def test_invalid_contours(self):
        for p in (
            Part("invalid", "polygon", points=[(0,0),(100,100),(0,100),(100,0)]),
            Part("bad ring", "ring", diameter=40, inner_diameter=40),
            Part("rounded", "rounded_rectangle", width=10,height=10,corner_radius=8),
        ):
            with self.subTest(p=p.name), self.assertRaises(ValueError):
                p.check()

    def test_collision_detection(self):
        p = Part("A","rectangle",quantity=2,width=10,height=10)
        bad = NestResult(100,100,[Placement(0,0,0,0),Placement(0,5,5,0)],0,0,1,[p])
        self.assertFalse(validate_result(bad))
        bad.placements[1] = Placement(0,90,95,0)
        self.assertFalse(validate_result(bad))

    def test_json_roundtrip(self):
        parts = [Part("X","polygon",quantity=2,
                      points=[(0,0),(30,0),(30,20),(0,20)])]
        r = calculate_sheet(parts,70,margin=2,gap=1)
        payload = json.loads(json.dumps(r.to_dict(),ensure_ascii=False))
        clone = NestResult(payload['sheet_width'],payload['sheet_length'],
                           [Placement(**entry) for entry in payload['placements']],
                           payload['gap'],payload['margin'],payload['length_step'],
                           [Part(**entry) for entry in payload['parts']])
        self.assertTrue(validate_result(clone))

    def test_random_mixed_orders(self):
        rng = random.Random(42)
        for _ in range(25):
            parts = [Part(f"R{i}","rectangle",quantity=rng.randint(1,3),
                          width=rng.randint(10,80),height=rng.randint(10,90))
                     for i in range(3)]
            parts += [Part("C","circle",quantity=2,diameter=rng.randint(15,50))]
            r=calculate_sheet(parts,180,gap=rng.randint(0,5),margin=3,length_step=5)
            self.assertTrue(validate_result(r))
            self.assertEqual(len(r.placements),sum(p.quantity for p in parts))

if __name__ == '__main__':
    unittest.main()
