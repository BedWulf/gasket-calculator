"""GUI regressions for compact, operator-resizable order window (Qt offscreen)."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt6.QtWidgets import QApplication
    from ui.order_sheet_dialog import OrderSheetDialog
except ImportError:
    QApplication = None
    OrderSheetDialog = None


@unittest.skipUnless(QApplication is not None, "PyQt6 unavailable")
class CompactOrderWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialog = OrderSheetDialog()
        self.dialog.resize(1000, 620)
        self.dialog.show()
        self.app.processEvents()

    def tearDown(self):
        self.dialog.close()
        self.app.processEvents()

    def test_calculate_button_is_visible_outside_scrollable_inputs(self):
        self.assertFalse(self.dialog.left_scroll.isAncestorOf(self.dialog.calculate_button))
        self.assertTrue(self.dialog.calculate_button.isVisible())
        bar = self.dialog.left_scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        bar.setValue(bar.maximum())
        self.app.processEvents()
        self.assertTrue(self.dialog.calculate_button.isVisible())

    def test_user_can_resize_results_independently_of_preview(self):
        self.assertEqual(self.dialog.result_splitter.count(), 2)
        self.assertTrue(self.dialog.summary_scroll.isVisible())
        self.assertTrue(self.dialog.view.isVisible())
        self.dialog.result_splitter.setSizes([210, 260])
        self.app.processEvents()
        self.assertGreater(self.dialog.result_splitter.sizes()[1], 120)

    def test_quick_entry_only_shows_relevant_sizes(self):
        self.dialog.quick_kind.setCurrentIndex(self.dialog.quick_kind.findData("circle"))
        self.app.processEvents()
        self.assertTrue(self.dialog.quick_diameter.isVisible())
        self.assertFalse(self.dialog.quick_width.isVisible())
        self.assertFalse(self.dialog.quick_height.isVisible())
        self.assertFalse(self.dialog.quick_inner.isVisible())
        self.dialog.quick_kind.setCurrentIndex(self.dialog.quick_kind.findData("ring"))
        self.app.processEvents()
        self.assertTrue(self.dialog.quick_inner.isVisible())
        self.assertTrue(self.dialog.quick_diameter.isVisible())
        self.dialog.quick_kind.setCurrentIndex(self.dialog.quick_kind.findData("rectangle"))
        self.app.processEvents()
        self.assertTrue(self.dialog.quick_width.isVisible())
        self.assertTrue(self.dialog.quick_height.isVisible())
        self.assertFalse(self.dialog.quick_diameter.isVisible())

    def test_quick_entry_still_appends_detail_to_order(self):
        self.dialog.quick_kind.setCurrentIndex(self.dialog.quick_kind.findData("ring"))
        self.dialog.quick_diameter.setValue(80)
        self.dialog.quick_inner.setValue(40)
        self.dialog.quick_qty.setValue(3)
        self.dialog.add_quick_part()
        self.assertEqual(len(self.dialog.parts), 1)
        self.assertEqual(self.dialog.parts[0].quantity, 3)
        self.assertEqual(self.dialog.table.rowCount(), 1)


if __name__ == '__main__':
    unittest.main()
