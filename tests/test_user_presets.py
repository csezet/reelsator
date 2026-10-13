"""Persistence failures, complete recipes and user interactions across restarts."""

import json
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from PySide6.QtWidgets import QApplication, QMessageBox

from core.exif_spoofer import MetadataMode
from core.insta_optimizer import InstaOptimizer, ProcessingConfig
from core.smart_cropper import AspectRatio
from core.user_presets import PresetStore, PresetStoreError, config_from_data, config_to_data, recipe_config
from gui.components.settings_panel import SettingsPanelWidget
from gui.main_window import MainWindow

app = QApplication.instance() or QApplication([])


class TestPresetStore(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "settings/presets.json"
        self.store = PresetStore(self.path)

    def test_loading_missing_file_does_not_create_any_files(self):
        self.assertEqual(self.store.read(), {})
        self.assertFalse(self.path.parent.exists())

    def test_round_trip_preserves_recipe_and_does_not_freeze_session_settings(self):
        config = replace(ProcessingConfig.digicam_flash(), alpha_background=(12, 34, 56),
                         bloom_threshold=0.73, bayer_strength=0.35, sharpen_amount=0.25,
                         random_seed=999, capture_time=datetime(2026, 10, 13), overwrite_existing=True)
        self.store.save("  Вспышка дома  ", config)
        restored = PresetStore(self.path).read()["Вспышка дома"]
        self.assertEqual(restored, recipe_config(config))
        self.assertEqual(config.random_seed, 999)
        stored = json.loads(self.path.read_text(encoding="utf-8"))
        data = stored["presets"][0]["config"]
        self.assertEqual(data["grain_mode"], "FILM")
        self.assertNotIn("random_seed", data)
        self.assertNotIn("capture_time", data)
        self.assertNotIn("overwrite_existing", data)

    def test_restored_recipe_produces_same_pixels_with_same_file_seed(self):
        config = replace(ProcessingConfig.soft_flash(), aspect_ratio=AspectRatio.ORIGINAL, random_seed=42)
        self.store.save("Soft", config)
        restored = replace(self.store.read()["Soft"], random_seed=42)
        image = Image.fromarray(np.random.default_rng(7).integers(40, 240, (96, 128, 3), dtype=np.uint8))
        first, _ = InstaOptimizer().process_pil(image, config)
        second, _ = InstaOptimizer().process_pil(image, restored)
        self.assertEqual(first.tobytes(), second.tobytes())

    def test_duplicates_need_explicit_update_and_keep_other_instance_changes(self):
        self.store.save("Мой Flash", ProcessingConfig.soft_flash())
        original = self.path.read_bytes()
        with self.assertRaises(PresetStoreError):
            self.store.save("МОЙ FLASH", ProcessingConfig.digicam_flash())
        self.assertEqual(self.path.read_bytes(), original)
        another = PresetStore(self.path)
        another.save("Второй", ProcessingConfig.iphone_natural())
        saved_name = self.store.save("мой flash", ProcessingConfig.digicam_flash(), overwrite=True)
        self.assertEqual(saved_name, "Мой Flash")
        self.assertEqual(set(self.store.read()), {"Мой Flash", "Второй"})
        self.store.delete("мой flash")
        self.assertEqual(set(another.read()), {"Второй"})

    def test_invalid_names_and_values_never_replace_saved_data(self):
        self.store.save("Valid", ProcessingConfig.soft_flash())
        original = self.path.read_bytes()
        for name in ("", "a" * 61, "two\nlines", "bad\x00name"):
            with self.subTest(name=name), self.assertRaises(PresetStoreError):
                self.store.save(name, ProcessingConfig.soft_flash())
        for overrides in ({"exposure_ev": float("nan")}, {"chroma_grain_strength": 25},
                          {"jpeg_quality": True}, {"alpha_background": (0, 0, 256)}, {"grain_mode": "bad"}):
            with self.subTest(overrides=overrides), self.assertRaises(PresetStoreError):
                self.store.save("Invalid", replace(ProcessingConfig.soft_flash(), **overrides))
        self.assertEqual(self.path.read_bytes(), original)

    def test_damaged_or_future_schema_files_cannot_be_overwritten(self):
        self.path.parent.mkdir()
        for text in ("{broken", json.dumps({"version": 2, "presets": []}),
                     json.dumps({"version": 1, "presets": [{"name": "bad", "config": {"exposure_ev": 9}}]})):
            with self.subTest(text=text):
                self.path.write_text(text, encoding="utf-8")
                with self.assertRaises(PresetStoreError):
                    self.store.read()
                with self.assertRaises(PresetStoreError):
                    self.store.save("New", ProcessingConfig.soft_flash())
                self.assertEqual(self.path.read_text(encoding="utf-8"), text)

    def test_failed_atomic_replace_keeps_old_file_and_cleans_temporary_file(self):
        self.store.save("Soft", ProcessingConfig.soft_flash())
        original = self.path.read_bytes()
        with patch("core.user_presets.os.replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PresetStoreError):
                self.store.save("Digicam", ProcessingConfig.digicam_flash())
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_optional_new_fields_default_and_unknown_fields_are_rejected(self):
        config = config_from_data({"grain_mode": "FILM", "exposure_ev": 0.2})
        self.assertEqual(config.exposure_ev, 0.2)
        self.assertEqual(config.bloom_threshold, 0.65)
        with self.assertRaises(PresetStoreError):
            config_from_data({"run_command": "anything"})


class TestUserPresetGUI(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = PresetStore(Path(self.folder.name) / "presets.json")
        self.panel = SettingsPanelWidget(preset_store=self.store)

    def test_modified_state_and_reset_restore_selected_recipe(self):
        panel = self.panel
        panel.btn_preset_digicam_flash.click()
        panel.slider_jpeg.setValue(92)
        panel._photo_controls["sharpen_amount"][0].setValue(33)
        self.assertIn("изменён", panel.lbl_profile.text())
        self.assertFalse(panel.btn_preset_digicam_flash.isChecked())
        self.assertTrue(panel.btn_reset_profile.isEnabled())
        panel.btn_reset_profile.click()
        self.assertEqual(panel.get_current_config(), ProcessingConfig.digicam_flash())
        self.assertTrue(panel.btn_preset_digicam_flash.isChecked())
        self.assertFalse(panel.btn_reset_profile.isEnabled())

    def test_save_load_update_and_delete_through_controls(self):
        panel = self.panel
        panel.btn_preset_soft_flash.click()
        panel._photo_controls["temperature"][0].setValue(24)
        expected = panel.get_current_config()
        with patch("gui.components.settings_panel.QInputDialog.getText", return_value=("Мой Flash", True)):
            panel.btn_save_preset.click()
        self.assertEqual(self.store.read()["Мой Flash"], expected)
        self.assertEqual(panel.combo_user_presets.currentData(), "Мой Flash")
        self.assertEqual(panel.lbl_profile.text(), "Мой Flash")
        panel.slider_jpeg.setValue(91)
        self.assertTrue(panel.btn_update_preset.isEnabled())
        panel.btn_update_preset.click()
        updated = replace(expected, jpeg_quality=91)
        self.assertEqual(self.store.read()["Мой Flash"], updated)
        self.assertFalse(panel.btn_update_preset.isEnabled())
        restarted = SettingsPanelWidget(preset_store=PresetStore(self.store.path))
        restarted.combo_user_presets.setCurrentIndex(restarted.combo_user_presets.findData("Мой Flash"))
        self.assertEqual(restarted.get_current_config(), updated)
        with patch("gui.components.settings_panel.QMessageBox.question", return_value=QMessageBox.Yes):
            panel.btn_delete_preset.click()
        self.assertEqual(self.store.read(), {})
        self.assertEqual(panel.get_current_config(), updated)
        self.assertFalse(panel.btn_delete_preset.isEnabled())

    def test_cancel_save_and_delete_do_not_touch_file_or_current_settings(self):
        with patch("gui.components.settings_panel.QInputDialog.getText", return_value=("Cancelled", False)):
            self.panel.btn_save_preset.click()
        self.assertFalse(self.store.path.exists())
        self.store.save("Saved", ProcessingConfig.soft_flash())
        self.panel._refresh_user_presets()
        self.panel.combo_user_presets.setCurrentIndex(self.panel.combo_user_presets.findData("Saved"))
        original = self.store.path.read_bytes()
        with patch("gui.components.settings_panel.QMessageBox.question", return_value=QMessageBox.No):
            self.panel.btn_delete_preset.click()
        self.assertEqual(self.store.path.read_bytes(), original)

    def test_corrupt_store_disables_writes_but_builtin_presets_still_work(self):
        self.store.path.write_text("broken", encoding="utf-8")
        panel = SettingsPanelWidget(preset_store=self.store)
        self.assertFalse(panel.btn_save_preset.isEnabled())
        self.assertIn("Не удалось", panel.lbl_preset_message.text())
        panel.btn_preset_soft_flash.click()
        self.assertEqual(panel.get_current_config(), ProcessingConfig.soft_flash())
        self.assertEqual(self.store.path.read_text(encoding="utf-8"), "broken")

    def test_disabled_effect_strengths_are_retained_and_seed_survives_reset(self):
        config = replace(ProcessingConfig.soft_flash(), random_seed=999, sharpen_amount=0.37, bayer_strength=0.24)
        panel = self.panel
        panel.set_config(config)
        self.assertFalse(panel._photo_controls["sharpen_amount"][0].isEnabled())
        panel.chk_isp.setChecked(True)
        self.assertTrue(panel._photo_controls["sharpen_amount"][0].isEnabled())
        self.assertEqual(panel.get_current_config().sharpen_amount, 0.37)
        panel.btn_reset_profile.click()
        self.assertEqual(panel.get_current_config(), config)

    def test_exif_badge_tracks_actual_mode(self):
        window = MainWindow(preset_store=self.store)
        window.settings_panel.set_config(ProcessingConfig(metadata_mode=MetadataMode.NO_EXIF))
        self.assertIn("выкл.", window.lbl_metadata_badge.text())
        window.settings_panel.set_config(ProcessingConfig(metadata_mode=MetadataMode.SYNTHETIC_CAMERA))
        self.assertIn("iPhone", window.lbl_metadata_badge.text())
        window.settings_panel.btn_preset_soft_flash.click()
        self.assertIn("sRGB", window.lbl_metadata_badge.text())
        window.close()


if __name__ == "__main__":
    unittest.main()
