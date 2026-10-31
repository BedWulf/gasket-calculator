"""Offscreen smoke tests for the visual contour editor (run on Windows CI)."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
    from ui.contour_editor import ContourEditor
except ImportError:
    QApplication = None
    ContourEditor = None


@unittest.skipUnless(QApplication is not None, 'PyQt6 unavailable')
class ContourEditorGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.editor = ContourEditor([(0,0),(100,0),(100,80),(0,80)])
        self.editor.show()
        self.app.processEvents()

    def tearDown(self):
        self.editor.close()
        self.app.processEvents()

    def test_edge_length_is_edited_in_millimeters(self):
        self.editor.edge_length.setValue(120)
        self.editor.apply_edge_length()
        self.assertEqual(self.editor.rings[0][1], (120,0))
        self.assertEqual(self.editor.active_vertex.value(), 1)
        self.editor.undo()
        self.assertEqual(self.editor.rings[0][1], (100,0))

    def test_invalid_edge_edit_is_rejected_and_unmodified(self):
        from algorithms.contour_ops import rectangular_hole
        self.editor.rings.append(rectangular_hole((50,40),20,20))
        self.editor._draw_all()
        old = [list(ring) for ring in self.editor.rings]
        self.editor.active_ring.setCurrentIndex(0)
        self.editor.active_vertex.setValue(2)
        self.editor.edge_length.setValue(2)
        with patch('ui.contour_editor.QMessageBox.warning') as warning:
            self.editor.apply_edge_length()
        warning.assert_called_once()
        self.assertEqual(self.editor.rings, old)

    def test_hole_placement_mode_changes_buttons(self):
        self.editor.place_round_button.click()
        self.assertEqual(self.editor.placement_kind, 'circle')
        self.assertFalse(self.editor.place_rect_button.isChecked())
        self.editor.place_rect_button.click()
        self.assertEqual(self.editor.placement_kind, 'rectangle')
        self.assertFalse(self.editor.place_round_button.isChecked())
        self.editor._set_placement_mode(None)
        self.assertIsNone(self.editor.placement_kind)

    def test_click_on_canvas_creates_hole(self):
        self.editor._set_placement_mode('rectangle')
        self.editor.view.fitInView(self.editor.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        canvas_point = self.editor.view.mapFromScene(50,40)
        with patch.object(self.editor, '_hole_dialog', return_value=[(40,35),(60,35),(60,45),(40,45)]) as dialog:
            QTest.mouseClick(self.editor.view.viewport(), Qt.MouseButton.LeftButton, pos=canvas_point)
        dialog.assert_called_once()
        self.assertEqual(len(self.editor.rings), 2)
        self.assertIsNone(self.editor.placement_kind)


if __name__ == '__main__':
    unittest.main()
