"""Photographic controls, noise separation, and export integration regressions."""

import os
import tempfile
import unittest
import warnings
from dataclasses import replace

import numpy as np
from PIL import Image
from PySide6.QtWidgets import QApplication

from core.camera_optics import CameraOptics
from core.insta_optimizer import InstaOptimizer, ProcessingConfig
from core.photo_effects import GrainMode, PhotoEffects
from core.smart_cropper import AspectRatio
from gui.components.settings_panel import SettingsPanelWidget

app = QApplication.instance() or QApplication([])
LUMA = np.array((0.2126, 0.7152, 0.0722))


def plain_config(**overrides):
    return replace(ProcessingConfig(
        aspect_ratio=AspectRatio.ORIGINAL,
        disrupt_strength=0,
        grain_strength=0,
        aberration_px=0,
        vignette_strength=0,
        enable_photonic_grade=False,
        use_smart_face_centering=False,
        random_seed=42,
    ), **overrides)


class TestPhotoEffects(unittest.TestCase):
    def test_neutral_grade_preserves_pixels_and_active_grade_does_not_mutate_source(self):
        pixels = np.random.default_rng(7).integers(0, 256, (64, 48, 3), dtype=np.uint8)
        image = Image.fromarray(pixels)
        np.testing.assert_array_equal(np.asarray(PhotoEffects.apply_grade(image)), pixels)
        result = PhotoEffects.apply_grade(image, exposure_ev=0.5, saturation=0.8, bloom_strength=0.1)
        np.testing.assert_array_equal(np.asarray(image), pixels)
        self.assertFalse(np.array_equal(np.asarray(result), pixels))
        self.assertEqual(result.size, image.size)

    def test_exposure_uses_linear_light(self):
        for level, ev, expected in ((64, 1, 90), (64, -1, 44), (128, 1, 176)):
            with self.subTest(level=level, ev=ev):
                image = Image.new("RGB", (8, 8), (level,) * 3)
                result = PhotoEffects.apply_grade(image, exposure_ev=ev)
                self.assertLessEqual(abs(result.getpixel((0, 0))[0] - expected), 1)

    def test_temperature_and_tint_have_expected_directions(self):
        image = Image.new("RGB", (8, 8), (128,) * 3)
        warm = PhotoEffects.apply_grade(image, temperature=0.6).getpixel((0, 0))
        cool = PhotoEffects.apply_grade(image, temperature=-0.6).getpixel((0, 0))
        magenta = PhotoEffects.apply_grade(image, tint=0.6).getpixel((0, 0))
        green = PhotoEffects.apply_grade(image, tint=-0.6).getpixel((0, 0))
        self.assertGreater(warm[0], warm[2])
        self.assertLess(cool[0], cool[2])
        self.assertLess(magenta[1], min(magenta[0], magenta[2]))
        self.assertGreater(green[1], max(green[0], green[2]))

    def test_zero_saturation_produces_grayscale(self):
        image = Image.new("RGB", (16, 16), (210, 80, 50))
        result = np.asarray(PhotoEffects.apply_grade(image, saturation=0))
        np.testing.assert_array_equal(result[:, :, 0], result[:, :, 1])
        np.testing.assert_array_equal(result[:, :, 1], result[:, :, 2])
        gray = Image.new("RGB", (8, 8), (128,) * 3)
        self.assertEqual(PhotoEffects.apply_grade(gray, saturation=2).tobytes(), gray.tobytes())

    def test_tone_curve_is_monotonic_and_black_lift_preserves_white(self):
        ramp = np.repeat(np.arange(256, dtype=np.uint8)[None, :, None], 3, axis=2)
        image = Image.fromarray(ramp)
        for contrast in (-1, 0, 1):
            with self.subTest(contrast=contrast):
                result = np.asarray(PhotoEffects.apply_grade(image, tone_contrast=contrast, black_lift=0.04))
                self.assertTrue(np.all(np.diff(result[0, :, 0].astype(np.int16)) >= 0))
                self.assertGreater(result[0, 0, 0], 0)
                self.assertEqual(result[0, -1, 0], 255)
        contrast = np.asarray(PhotoEffects.apply_grade(image, tone_contrast=0.8))
        self.assertLess(contrast[0, 32, 0], 32)
        self.assertGreater(contrast[0, 224, 0], 224)

    def test_highlight_rolloff_retains_detail_after_positive_exposure(self):
        ramp = np.repeat(np.arange(208, 256, dtype=np.uint8)[None, :, None], 3, axis=2)
        image = Image.fromarray(ramp)
        clipped = np.asarray(PhotoEffects.apply_grade(image, exposure_ev=2))
        protected = np.asarray(PhotoEffects.apply_grade(image, exposure_ev=2, highlight_rolloff=1))
        self.assertTrue(np.all(clipped == 255))
        self.assertLess(protected.max(), 255)
        self.assertGreater(len(np.unique(protected)), 1)
        self.assertTrue(np.all(np.diff(protected[0, :, 0].astype(np.int16)) >= 0))

    def test_bloom_spreads_highlights_without_washing_out_uniform_midtones(self):
        midtones = Image.new("RGB", (64, 64), (128,) * 3)
        self.assertEqual(PhotoEffects.apply_grade(midtones, bloom_strength=0.8).tobytes(), midtones.tobytes())
        pixels = np.zeros((64, 64, 3), dtype=np.uint8)
        pixels[30:35, 30:35] = 255
        image = Image.fromarray(pixels)
        result = np.asarray(PhotoEffects.apply_grade(image, bloom_strength=0.8, bloom_radius_px=4))
        self.assertGreater(result[32, 28, 0], 0)
        self.assertEqual(result[32, 32, 0], 255)
        self.assertLessEqual(result[0, 0, 0], 1)
        np.testing.assert_array_equal(np.asarray(image), pixels)

    def test_zero_film_grain_preserves_pixels(self):
        image = Image.new("RGB", (32, 32), (100, 130, 160))
        result = PhotoEffects.add_film_grain(image, luma_strength=0, chroma_strength=0, seed=7)
        self.assertEqual(result.tobytes(), image.tobytes())

    def test_luma_grain_does_not_tint_neutral_colors(self):
        image = Image.new("RGB", (256, 256), (128,) * 3)
        result = np.asarray(PhotoEffects.add_film_grain(image, luma_strength=6, chroma_strength=0, seed=7))
        np.testing.assert_array_equal(result[:, :, 0], result[:, :, 1])
        np.testing.assert_array_equal(result[:, :, 1], result[:, :, 2])
        self.assertGreater(result[:, :, 0].std(), 2)
        self.assertLess(abs(result.mean() - 128), 0.1)

    def test_chroma_grain_has_low_luminance_variation(self):
        image = Image.new("RGB", (256, 256), (128,) * 3)
        result = np.asarray(PhotoEffects.add_film_grain(image, luma_strength=0, chroma_strength=8, seed=7), dtype=float)
        luminance = np.sum(result * LUMA, axis=2)
        self.assertLess(luminance.std(), 0.35)
        self.assertGreater((result[:, :, 0] - result[:, :, 2]).std(), 3)
        self.assertLess(abs(luminance.mean() - 128), 0.1)

    def test_grain_is_reproducible_and_components_are_independent(self):
        image = Image.new("RGB", (256, 256), (128,) * 3)
        luma = np.asarray(PhotoEffects.add_film_grain(image, luma_strength=4, chroma_strength=0, seed=42), dtype=np.int16)
        chroma = np.asarray(PhotoEffects.add_film_grain(image, luma_strength=0, chroma_strength=3, seed=42), dtype=np.int16)
        combined = PhotoEffects.add_film_grain(image, luma_strength=4, chroma_strength=3, seed=42)
        repeated = PhotoEffects.add_film_grain(image, luma_strength=4, chroma_strength=3, seed=42)
        self.assertEqual(combined.tobytes(), repeated.tobytes())
        difference = np.asarray(combined, dtype=np.int16) - (luma + chroma - 128)
        self.assertLessEqual(np.abs(difference).max(), 1)

    def test_grain_size_changes_correlation_without_losing_intensity(self):
        image = Image.new("RGB", (256, 256), (128,) * 3)
        fine = np.asarray(PhotoEffects.add_film_grain(image, luma_strength=6, chroma_strength=0, size_px=1, seed=42))[:, :, 0]
        coarse = np.asarray(PhotoEffects.add_film_grain(image, luma_strength=6, chroma_strength=0, size_px=3, seed=42))[:, :, 0]
        fine_corr = np.corrcoef(fine[:, :-1].ravel(), fine[:, 1:].ravel())[0, 1]
        coarse_corr = np.corrcoef(coarse[:, :-1].ravel(), coarse[:, 1:].ravel())[0, 1]
        self.assertGreater(coarse_corr, fine_corr + 0.5)
        self.assertGreater(coarse.std() / fine.std(), 0.9)
        self.assertLess(coarse.std() / fine.std(), 1.1)

    def test_tiny_black_and_white_images_remain_finite(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            for size in ((1, 1), (2, 3)):
                for level in (0, 255):
                    with self.subTest(size=size, level=level):
                        image = Image.new("RGB", size, (level,) * 3)
                        graded = PhotoEffects.apply_grade(
                            image, exposure_ev=3, temperature=1, tint=1, saturation=2,
                            tone_contrast=1, black_lift=0.15, highlight_rolloff=1,
                            bloom_strength=1, bloom_radius_px=60,
                        )
                        grain = PhotoEffects.add_film_grain(image, luma_strength=12, chroma_strength=24, size_px=4, seed=42)
                        self.assertEqual(graded.size, size)
                        self.assertEqual(grain.size, size)

    def test_invalid_controls_are_rejected(self):
        image = Image.new("RGB", (8, 8))
        for kwargs in (
            {"exposure_ev": float("nan")}, {"temperature": float("inf")}, {"tint": 2},
            {"saturation": -0.1}, {"tone_contrast": 1.1}, {"black_lift": -0.1},
            {"highlight_rolloff": 1.1}, {"bloom_strength": 1.1},
            {"bloom_radius_px": 0}, {"bloom_threshold": 1},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                PhotoEffects.apply_grade(image, **kwargs)
        for kwargs in ({"luma_strength": -1}, {"chroma_strength": float("nan")}, {"chroma_strength": 24.1}, {"size_px": 0.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                PhotoEffects.add_film_grain(image, **kwargs)


class TestPhotoEffectsPipeline(unittest.TestCase):
    def test_neutral_new_controls_preserve_legacy_camera_processing(self):
        image = Image.fromarray(np.random.default_rng(7).integers(0, 256, (96, 128, 3), dtype=np.uint8))
        config = plain_config(
            enable_photonic_grade=True, grain_strength=1.3, aberration_px=0.4,
            vignette_strength=0.03, enable_bayer_matrix=True, bayer_strength=0.7,
            enable_isp_enhancement=True, sharpen_amount=0.5,
        )
        expected = CameraOptics.apply_all(
            image, iso=100, grain_strength=config.grain_strength,
            aberration_px=config.aberration_px, vignette_strength=config.vignette_strength,
            enable_photonic=True, enable_bayer_matrix=True, bayer_strength=config.bayer_strength,
            enable_isp_enhancement=True, sharpen_amount=config.sharpen_amount, seed=config.random_seed,
        )
        actual, _ = InstaOptimizer().process_pil(image, config)
        self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_film_mode_uses_one_grain_layer(self):
        image = Image.new("RGB", (64, 48), (128,) * 3)
        config = plain_config(grain_mode=GrainMode.FILM, grain_strength=2)
        actual, _ = InstaOptimizer().process_pil(image, config)
        expected = PhotoEffects.add_film_grain(
            image, luma_strength=config.luma_grain_strength,
            chroma_strength=config.chroma_grain_strength, size_px=config.grain_size_px,
            seed=config.random_seed,
        )
        self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_grain_is_applied_at_final_export_resolution(self):
        config = plain_config(aspect_ratio=AspectRatio.FEED_4_5, grain_mode=GrainMode.FILM, grain_size_px=2)
        optimizer = InstaOptimizer()
        small, _ = optimizer.process_pil(Image.new("RGB", (1080, 1350), (128,) * 3), config)
        large, _ = optimizer.process_pil(Image.new("RGB", (2160, 2700), (128,) * 3), config)
        self.assertEqual(small.size, (1080, 1350))
        self.assertEqual(small.tobytes(), large.tobytes())

    def test_color_glow_and_film_grain_keep_jpeg_preview_export_agreement(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "source.png")
            output = os.path.join(folder, "output.jpg")
            pixels = np.random.default_rng(7).integers(0, 256, (128, 96, 3), dtype=np.uint8)
            Image.fromarray(pixels).save(source)
            config = plain_config(
                exposure_ev=0.4, temperature=0.2, tint=-0.1, saturation=0.9,
                tone_contrast=0.25, black_lift=0.015, highlight_rolloff=0.8,
                bloom_strength=0.12, bloom_radius_px=6,
                grain_mode=GrainMode.FILM, grain_size_px=2,
            )
            optimizer = InstaOptimizer()
            preview = optimizer.process_preview_file(source, config)
            optimizer.process_file(source, output, config)
            with Image.open(output) as saved:
                self.assertEqual(preview.jpeg.tobytes(), saved.tobytes())
            self.assertEqual(preview.jpeg_size_bytes, os.path.getsize(output))


class TestPhotoEffectsGUI(unittest.TestCase):
    def test_editing_color_preserves_other_photo_controls_and_hidden_parameters(self):
        panel = SettingsPanelWidget()
        config = plain_config(
            exposure_ev=0.4, temperature=0.2, tint=-0.1, saturation=0.9,
            tone_contrast=0.25, black_lift=0.015, highlight_rolloff=0.8,
            bloom_strength=0.12, bloom_radius_px=6, bloom_threshold=0.73,
            grain_mode=GrainMode.FILM, luma_grain_strength=3.2, chroma_grain_strength=2.4,
            grain_size_px=2, bayer_strength=0.7, sharpen_amount=0.35,
        )
        panel.set_config(config)
        panel._photo_controls["exposure_ev"][0].setValue(80)
        self.assertEqual(panel.get_current_config(), replace(config, exposure_ev=0.8))

    def test_switching_grain_modes_retains_both_sets_of_settings(self):
        panel = SettingsPanelWidget()
        config = plain_config(grain_strength=1.3, luma_grain_strength=3.2, chroma_grain_strength=2.4, grain_size_px=2)
        panel.set_config(config)
        panel.combo_grain_mode.setCurrentIndex(panel.combo_grain_mode.findData(GrainMode.FILM))
        self.assertFalse(panel.slider_grain.isEnabled())
        self.assertTrue(panel._photo_controls["luma_grain_strength"][0].isEnabled())
        panel._photo_controls["luma_grain_strength"][0].setValue(47)
        panel.combo_grain_mode.setCurrentIndex(panel.combo_grain_mode.findData(GrainMode.SENSOR))
        self.assertTrue(panel.slider_grain.isEnabled())
        self.assertEqual(panel.get_current_config(), replace(config, luma_grain_strength=4.7))


if __name__ == "__main__":
    unittest.main()
