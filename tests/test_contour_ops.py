import unittest
from shapely.geometry import Polygon
from algorithms.contour_ops import fillet_corner

class ContourToolsTests(unittest.TestCase):
    def test_fillet_convex_corner(self):
        p=[(0,0),(100,0),(100,100),(0,100)]
        result=fillet_corner(p,1,10)
        self.assertTrue(Polygon(result).is_valid)
        self.assertLess(Polygon(result).area,Polygon(p).area)
        self.assertAlmostEqual(result[1][0],90)
    def test_cw_and_ccw_contours(self):
        p=[(0,0),(100,0),(100,100),(0,100)]
        self.assertAlmostEqual(Polygon(fillet_corner(p,1,10)).area,
                               Polygon(fillet_corner(list(reversed(p)),2,10)).area)
    def test_too_large_radius_rejected(self):
        p=[(0,0),(20,0),(20,20),(0,20)]
        with self.assertRaisesRegex(ValueError,'велик'):
            fillet_corner(p,1,25)
    def test_concave_corner_rejected(self):
        p=[(0,0),(100,0),(100,30),(30,30),(30,100),(0,100)]
        with self.assertRaisesRegex(ValueError,'выпуклые'):
            fillet_corner(p,3,5)

if __name__=='__main__':unittest.main()
