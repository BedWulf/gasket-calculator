"""GUI regression: settings and result text remain accessible on a short screen.

Runs with Qt's offscreen backend in CI; skipped where PyQt6 is not installed.
"""
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
class ResponsiveOrderWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialog = OrderSheetDialog()
        self.dialog.resize(960, 560)
        self.dialog.show()
        self.app.processEvents()

    def tearDown(self):
        self.dialog.close()
        self.app.processEvents()

    def test_input_panel_can_scroll_without_hiding_results(self):
        self.assertTrue(self.dialog.left_scroll.isVisible())
        self.assertGreater(self.dialog.left_scroll.verticalScrollBar().maximum(), 0)
        self.assertTrue(self.dialog.summary_scroll.isVisible())
        self.assertTrue(self.dialog.summary.isVisible())
        self.assertTrue(self.dialog.calculate_button.isVisible())

    def test_long_result_is_scrollable_and_selectable(self):
        self.dialog.summary.setText("<br>".join(["Результат расчета: 123 мм"] * 50))
        self.app.processEvents()
        bar = self.dialog.summary_scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        bar.setValue(bar.maximum())
        self.assertEqual(bar.value(), bar.maximum())
        self.assertTrue(self.dialog.summary.textInteractionFlags())


if __name__ == "__main__":
    unittest.main()
