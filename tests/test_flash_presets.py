"""Flash looks remain distinct after JPEG and survive real UI interactions."""

import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import piexif
from PIL import Image, JpegImagePlugin
from PySide6.QtWidgets import QApplication

from core.exif_spoofer import MetadataMode
from core.insta_optimizer import InstaOptimizer, ProcessingConfig
from core.photo_effects import GrainMode
from core.smart_cropper import AspectRatio
from gui.components.settings_panel import SettingsPanelWidget
from scripts.preview_flash_presets import render_examples

app = QApplication.instance() or QApplication([])
LUMA = np.array((0.2126, 0.7152, 0.0722), dtype=np.float32)
PRESETS = (ProcessingConfig.soft_flash, ProcessingConfig.digicam_flash)


class TestFlashPresets(unittest.TestCase):
    def test_decoded_jpeg_looks_have_distinct_luminance_and_color_grain(self):
        image = Image.new("RGB", (512, 512), (135,) * 3)
        optimizer = InstaOptimizer()
        metrics = []
        for factory in PRESETS:
            config = replace(factory(), aspect_ratio=AspectRatio.ORIGINAL, random_seed=1729)
            result, exif = optimizer.process_pil(image, config)
            encoded = optimizer.encode_jpeg(result, exif, config.jpeg_quality)
            with Image.open(io.BytesIO(encoded)) as jpeg:
                pixels = np.asarray(jpeg, dtype=np.float32)[64:-64, 64:-64]
            residual = pixels - cv2.GaussianBlur(pixels, (0, 0), 1)
            lum_noise = residual @ LUMA
            color_noise = residual - lum_noise[:, :, None]
            metrics.append((float((pixels @ LUMA).mean()), lum_noise.std(), color_noise.std()))
        soft, digicam = metrics
        self.assertGreater(digicam[0], soft[0] + 5)
        self.assertGreater(soft[1], 1)  # Soft texture is visible in the saved JPEG too.
        self.assertGreater(digicam[2], soft[2] * 3 + 1)

    def test_highlight_ramp_keeps_detail_with_both_presets(self):
        ramp = np.repeat(np.linspace(180, 255, 512, dtype=np.uint8)[None, :, None], 3, axis=2)
        image = Image.fromarray(np.repeat(ramp, 128, axis=0))
        optimizer = InstaOptimizer()
        for factory in PRESETS:
            with self.subTest(preset=factory.__name__):
                config = replace(factory(), aspect_ratio=AspectRatio.ORIGINAL, random_seed=1729)
                output, _ = optimizer.process_pil(image, config)
                pixels = np.asarray(output)
                mean_columns = pixels.mean(axis=(0, 2))
                self.assertGreater(mean_columns[-1], mean_columns[256] + 5)
                self.assertGreater(len(np.unique(mean_columns[320:])), 20)
                self.assertLess(np.mean(np.all(pixels == 255, axis=2)), 0.3)

    def test_factories_return_independent_configs(self):
        for factory in PRESETS:
            with self.subTest(preset=factory.__name__):
                first, second = factory(), factory()
                first.chroma_grain_strength = 0
                self.assertGreater(second.chroma_grain_strength, 0)
                self.assertEqual(second.grain_mode, GrainMode.FILM)
                self.assertEqual(second.metadata_mode, MetadataMode.MINIMAL)

    def test_examples_match_exports_and_keep_previous_runs_and_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.png"
            pixels = np.random.default_rng(7).integers(50, 220, (120, 96, 3), dtype=np.uint8)
            Image.fromarray(pixels).save(source)
            original_bytes = source.read_bytes()
            # A previously rendered directory must never be overwritten.
            requested = root / "results"
            requested.mkdir()
            marker = requested / "soft-flash.jpg"
            marker.write_bytes(b"previous result")
            actual = render_examples(source, requested, seed=1729)
            self.assertEqual(actual, root / "results-2")
            self.assertEqual(marker.read_bytes(), b"previous result")
            self.assertEqual(source.read_bytes(), original_bytes)
            report = json.loads((actual / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["seed"], 1729)
            exports = []
            for name in ("soft-flash", "digicam-flash"):
                entry = report["presets"][name]
                self.assertTrue(entry["preview_matches_export"])
                with Image.open(actual / f"{name}.jpg") as saved:
                    self.assertEqual(saved.size, (1080, 1350))
                    self.assertEqual(JpegImagePlugin.get_sampling(saved), 2)
                    exif = piexif.load(saved.info["exif"])
                    self.assertNotIn(piexif.ImageIFD.Make, exif["0th"])
                    self.assertNotIn(piexif.ImageIFD.Model, exif["0th"])
                    exports.append(saved.tobytes())
            self.assertNotEqual(*exports)
            with Image.open(actual / "comparison.png") as sheet:
                self.assertEqual(sheet.size, (1080, 950))


class TestFlashPresetsGUI(unittest.TestCase):
    def test_clicking_flash_presets_updates_controls_and_emits_one_config(self):
        panel = SettingsPanelWidget()
        emitted = []
        panel.config_changed.connect(emitted.append)
        for button, factory in (
            (panel.btn_preset_soft_flash, ProcessingConfig.soft_flash),
            (panel.btn_preset_digicam_flash, ProcessingConfig.digicam_flash),
        ):
            with self.subTest(preset=factory.__name__):
                emitted.clear()
                button.click()
                expected = factory()
                self.assertEqual(emitted, [expected])
                self.assertEqual(panel.get_current_config(), expected)
                self.assertTrue(button.isChecked())
                self.assertEqual(sum(b.isChecked() for b in panel.preset_group.buttons()), 1)
                self.assertEqual(panel.combo_grain_mode.currentData(), GrainMode.FILM)
                slider = panel._photo_controls["chroma_grain_strength"][0]
                self.assertEqual(slider.value() / 10, expected.chroma_grain_strength)
                self.assertFalse(panel.combo_camera.isEnabled())

    def test_jpeg_edit_preserves_flash_tuning_and_hidden_threshold(self):
        panel = SettingsPanelWidget()
        for name, factory in (("soft_flash", ProcessingConfig.soft_flash), ("digicam_flash", ProcessingConfig.digicam_flash)):
            with self.subTest(preset=name):
                panel._select_preset(name)
                panel.slider_jpeg.setValue(92)
                self.assertEqual(panel.get_current_config(), replace(factory(), jpeg_quality=92))

    def test_returning_to_legacy_preset_restores_neutral_photo_controls(self):
        panel = SettingsPanelWidget()
        panel.btn_preset_digicam_flash.click()
        panel.btn_preset_ofm.click()
        self.assertEqual(panel.get_current_config(), ProcessingConfig.ofm_master())
        self.assertEqual(panel.combo_grain_mode.currentData(), GrainMode.SENSOR)
        self.assertFalse(panel._photo_controls["chroma_grain_strength"][0].isEnabled())
        self.assertTrue(panel.btn_preset_ofm.isChecked())


if __name__ == "__main__":
    unittest.main()
