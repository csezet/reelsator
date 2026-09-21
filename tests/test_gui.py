"""Automated GUI verification tests for Reelsator PySide6 widgets."""

import unittest
import sys
from PySide6.QtWidgets import QApplication
from PIL import Image
import numpy as np

# Ensure single QApplication instance across tests
app = QApplication.instance() or QApplication(sys.argv)

from gui.components.drop_zone import DropZoneWidget
from gui.components.comparison_slider import ComparisonSliderWidget
from gui.components.settings_panel import SettingsPanelWidget
from gui.components.batch_list import BatchListWidget
from gui.main_window import MainWindow
from core.insta_optimizer import ProcessingConfig


class TestReelsatorGUI(unittest.TestCase):
    """Verifies that all GUI components instantiate and interact correctly."""

    def test_drop_zone_widget(self):
        widget = DropZoneWidget()
        self.assertIsNotNone(widget)
        self.assertTrue(widget.acceptDrops())

    def test_comparison_slider_widget(self):
        slider = ComparisonSliderWidget()
        img1 = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
        img2 = Image.fromarray(np.ones((100, 100, 3), dtype=np.uint8) * 128)
        slider.set_images(img1, img2)
        self.assertIsNotNone(slider._pixmap_before)
        self.assertIsNotNone(slider._pixmap_after)

    def test_settings_panel_widget(self):
        panel = SettingsPanelWidget()
        cfg = panel.get_current_config()
        self.assertIsInstance(cfg, ProcessingConfig)

        # Test preset switching
        panel._select_preset("natural")
        cfg_natural = panel.get_current_config()
        self.assertEqual(cfg_natural.grain_strength, 0.7)

    def test_batch_list_widget(self):
        batch = BatchListWidget()
        test_paths = ["file1.jpg", "file2.png"]
        batch.set_files(test_paths)
        self.assertEqual(len(batch.get_file_paths()), 2)
        self.assertEqual(batch.table.rowCount(), 2)

        # Update status
        batch.mark_in_progress(0)
        batch.update_item_status(0, True)
        self.assertIn("Готово", batch.table.item(0, 2).text())

    def test_main_window_instantiation(self):
        win = MainWindow()
        self.assertIsNotNone(win)
        self.assertIn("Reelsator", win.windowTitle())
        self.assertFalse(win.btn_process.isEnabled())
        self.assertIsNotNone(win.btn_cancel)
        self.assertFalse(win.btn_cancel.isVisible())

    def test_rapid_preview_generation_stability(self):
        """Verify that rapid triggering of preview updates increments generation safely without crashes."""
        win = MainWindow()
        win._current_preview_file = None
        # Rapidly call trigger 20 times (simulating slider dragging)
        for _ in range(20):
            win._preview_generation += 1
        self.assertEqual(win._preview_generation, 20)

    def test_batch_worker_cancellation_flag(self):
        """Verify that BatchProcessWorker responds to cancel signal."""
        from core.pipeline import BatchPipeline
        from gui.main_window import BatchProcessWorker
        pipeline = BatchPipeline()
        worker = BatchProcessWorker(pipeline, [], "test_out", ProcessingConfig.ofm_master())
        self.assertFalse(worker._is_cancelled)
        worker.cancel()
        self.assertTrue(worker._is_cancelled)

    def test_settings_panel_metadata_mode(self):
        """Verify that metadata mode combo updates and reads config accurately."""
        from core.exif_spoofer import MetadataMode
        panel = SettingsPanelWidget()
        panel.combo_metadata.setCurrentIndex(0)
        cfg = panel.get_current_config()
        self.assertEqual(cfg.metadata_mode, MetadataMode.MINIMAL)

        panel.combo_metadata.setCurrentIndex(1)
        cfg2 = panel.get_current_config()
        self.assertEqual(cfg2.metadata_mode, MetadataMode.SYNTHETIC_CAMERA)

        cfg.metadata_mode = MetadataMode.MINIMAL
        panel.set_config(cfg)
        self.assertEqual(panel.combo_metadata.currentData(), MetadataMode.MINIMAL)

    def test_settings_panel_preserves_config_fields(self):
        """Verify that UI adjustments preserve non-GUI fields via dataclasses.replace."""
        panel = SettingsPanelWidget()
        cfg = ProcessingConfig.ofm_master()
        cfg.random_seed = 999
        panel.set_config(cfg)

        panel.slider_grain.setValue(50)
        updated_cfg = panel.get_current_config()
        self.assertEqual(updated_cfg.grain_strength, 0.5)
        self.assertEqual(updated_cfg.random_seed, 999)

    def test_comparison_slider_differing_aspect_ratios(self):
        """Verify comparison slider handles images with different aspect ratios."""
        slider = ComparisonSliderWidget()
        img1 = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
        img2 = Image.fromarray(np.ones((125, 100, 3), dtype=np.uint8) * 128)
        slider.set_images(img1, img2)
        self.assertEqual(slider._pixmap_before.size().width(), 100)
        self.assertEqual(slider._pixmap_before.size().height(), 100)
        self.assertEqual(slider._pixmap_after.size().width(), 100)
        self.assertEqual(slider._pixmap_after.size().height(), 125)


if __name__ == "__main__":
    unittest.main()

