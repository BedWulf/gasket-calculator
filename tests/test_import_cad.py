"""CAD import regression tests with explicit physical units and failures."""
import math
import tempfile
import unittest
from pathlib import Path
from algorithms.import_cad import import_svg, import_dxf
from algorithms.nesting import calculate_sheet, validate_result

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
    def file(self,name,contents):
        p=Path(self.tmp.name)/name
        if isinstance(contents,bytes):p.write_bytes(contents)
        else:p.write_text(contents,encoding='utf-8')
        return p
    def svg(self,body, extra='width="100mm" height="60mm" viewBox="0 0 100 60"'):
        return self.file('detail.svg',f'<svg xmlns="http://www.w3.org/2000/svg" {extra}>{body}</svg>')
    def test_svg_rectangle_mm(self):
        p=import_svg(self.svg('<rect x="10" y="10" width="60" height="35"/>'))
        self.assertAlmostEqual(p.actual_area(),2100)
        self.assertAlmostEqual(p.geometry().bounds[2],60)
    def test_svg_curved_ring_path(self):
        path='M50 5 A20 20 0 1 1 50 45 A20 20 0 1 1 50 5 Z M50 15 A10 10 0 1 0 50 35 A10 10 0 1 0 50 15 Z'
        p=import_svg(self.svg(f'<path fill-rule="evenodd" d="{path}"/>'))
        self.assertEqual(len(p.holes),1)
        self.assertAlmostEqual(p.actual_area(),math.pi*(20**2-10**2),delta=10)
    def test_svg_bezier_and_transform(self):
        p=import_svg(self.svg('<g transform="translate(10 5)"><path d="M 0 0 C 10 0 20 20 30 20 L 30 30 L 0 30 Z"/></g>'))
        self.assertGreater(p.actual_area(),0)
        self.assertAlmostEqual(p.geometry().bounds[2],30)
    def test_svg_hole_nested_shapes(self):
        p=import_svg(self.svg('<rect width="100" height="60"/><circle cx="50" cy="30" r="10"/>'))
        self.assertEqual(len(p.holes),1)
        self.assertAlmostEqual(p.actual_area(),6000-math.pi*100,delta=3)
    def test_svg_disjoint_rejected(self):
        with self.assertRaisesRegex(ValueError,'несколько независимых'):
            import_svg(self.svg('<rect width="20" height="20"/><rect x="40" width="20" height="20"/>'))
    def test_svg_open_rejected(self):
        with self.assertRaisesRegex(ValueError,'незамкнут'):
            import_svg(self.svg('<path d="M0 0 L10 0 L10 10"/>'))
    def test_svg_unknown_units_rejected(self):
        with self.assertRaisesRegex(ValueError,'единиц'):
            import_svg(self.svg('<rect width="10" height="10"/>',extra='viewBox="0 0 100 60"'))
        p=import_svg(self.svg('<rect width="10" height="10"/>',extra='viewBox="0 0 100 60"'),assume_unit='mm')
        self.assertAlmostEqual(p.actual_area(),100)
    def test_imported_part_fits_sheet(self):
        p=import_svg(self.svg('<path d="M0 0L40 0L40 20L20 20L20 30L0 30Z"/>'))
        p.quantity=2
        result=calculate_sheet([p],100,gap=3,margin=2,length_step=5,quality='thorough')
        self.assertTrue(validate_result(result))
    def test_dxf_units_mm_circle_hole(self):
        import ezdxf
        doc=ezdxf.new('R2013');doc.header['$INSUNITS']=4
        msp=doc.modelspace()
        msp.add_lwpolyline([(0,0),(70,0),(70,50),(0,50)],close=True)
        msp.add_circle((35,25),8)
        path=Path(self.tmp.name)/'ring.dxf'
        doc.saveas(path)
        part=import_dxf(path)
        self.assertEqual(len(part.holes),1)
        self.assertAlmostEqual(part.geometry().bounds[2],70)
        self.assertAlmostEqual(part.actual_area(),3500-math.pi*64,delta=3)
    def test_dxf_unitless_requires_confirmation(self):
        import ezdxf
        doc=ezdxf.new('R2013');doc.header['$INSUNITS']=0
        doc.modelspace().add_lwpolyline([(0,0),(50,0),(50,40),(0,40)],close=True)
        path=Path(self.tmp.name)/'unitless.dxf';doc.saveas(path)
        with self.assertRaisesRegex(ValueError,'единицы'):
            import_dxf(path)
        self.assertAlmostEqual(import_dxf(path,assume_mm=True).actual_area(),2000)

if __name__=='__main__':unittest.main()
