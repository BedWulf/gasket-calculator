"""Regression tests for exact edge dimensions and drawing-based holes."""
import unittest
from shapely.geometry import Polygon

from algorithms.contour_ops import (set_edge_length, rectangular_hole,
                                    circular_hole)
from algorithms.nesting import Part


class ContourDimensionTests(unittest.TestCase):
    def test_set_edge_length_preserves_anchor_and_direction(self):
        pts = [(0, 0), (40, 0), (40, 30), (0, 30)]
        resized = set_edge_length(pts, 0, 70)
        self.assertEqual(resized, [(0, 0), (70, 0), (40, 30), (0, 30)])
        self.assertEqual(pts[1], (40, 0))
        self.assertAlmostEqual(Polygon(resized).area, 1650)

    def test_wraparound_edge_can_be_resized(self):
        pts = [(0, 0), (40, 0), (40, 30), (0, 30)]
        resized = set_edge_length(pts, 3, 15)
        self.assertEqual(resized[0], (0, 15))
        self.assertEqual(resized[3], (0, 30))

    def test_diagonal_edge_preserves_angle(self):
        pts = [(0, 0), (30, 40), (0, 50)]
        resized = set_edge_length(pts, 0, 10)
        self.assertEqual(resized[1], (6, 8))

    def test_bad_length_or_bad_index_rejected(self):
        pts = [(0, 0), (10, 0), (10, 10)]
        for length in (0, -1, float('inf'), float('nan')):
            with self.subTest(length=length), self.assertRaises(ValueError):
                set_edge_length(pts, 1, length)
        with self.assertRaises(ValueError):
            set_edge_length(pts, 3, 10)

    def test_rectangle_hole_has_requested_size_and_center(self):
        points = rectangular_hole((40, 30), 20, 10)
        self.assertEqual(Polygon(points).bounds, (30, 25, 50, 35))
        self.assertEqual(Polygon(points).area, 200)

    def test_circle_hole_has_requested_diameter(self):
        points = circular_hole((25, 30), 12)
        x0, y0, x1, y1 = Polygon(points).bounds
        self.assertAlmostEqual(x1-x0, 12, places=5)
        self.assertAlmostEqual(y1-y0, 12, places=5)
        self.assertTrue(Polygon(points).is_valid)

    def test_holes_accepted_by_real_geometry_validation(self):
        outer = [(0, 0), (100, 0), (100, 80), (0, 80)]
        holes = [rectangular_hole((20, 20), 10, 10), circular_hole((65, 40), 20)]
        Part('Gasket', 'polygon', points=outer, holes=holes).check()

    def test_invalid_holes_rejected_at_boundary(self):
        outer = [(0, 0), (100, 0), (100, 80), (0, 80)]
        hole = circular_hole((1, 40), 20)
        with self.assertRaises(ValueError):
            Part('Bad hole', 'polygon', points=outer, holes=[hole]).check()


if __name__ == '__main__':
    unittest.main()
