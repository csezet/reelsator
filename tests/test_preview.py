"""Preview/export agreement, bounded source caching, and pixel inspection regressions."""

import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageCms
import piexif
from PySide6.QtCore import QEventLoop, QSize, QTimer
from PySide6.QtWidgets import QApplication

from core.exif_spoofer import MetadataMode
from core.image_cache import NormalizedImageCache
from core.insta_optimizer import InstaOptimizer, PreviewResult, ProcessingConfig
from core.smart_cropper import AspectRatio
from gui.components.comparison_slider import ComparisonSliderWidget, compute_slider_geometry
from gui.main_window import MainWindow, PreviewWorker

app = QApplication.instance() or QApplication([])


def plain_config(**overrides):
    return replace(ProcessingConfig(
        aspect_ratio=AspectRatio.ORIGINAL,
        disrupt_strength=0,
        grain_strength=0,
        aberration_px=0,
        vignette_strength=0,
        enable_photonic_grade=False,
        use_smart_face_centering=False,
    ), **overrides)


def sample_preview():
    return PreviewResult(
        Image.new("RGB", (64, 48), (32,) * 3),
        Image.new("RGB", (64, 48), (80,) * 3),
        Image.new("RGB", (64, 48), (96,) * 3),
        2048, 90,
    )


class TestPreviewPipeline(unittest.TestCase):
    def test_jpeg_preview_matches_saved_pixels_and_size(self):
        """Large, oriented, ICC-tagged inputs must yield the same decoded JPEG as export."""
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "large.jpg")
            output = os.path.join(folder, "export.jpg")
            pixels = np.random.default_rng(42).integers(0, 256, (1536, 2048, 3), dtype=np.uint8)
            icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            Image.fromarray(pixels).save(
                source, "JPEG", quality=97, icc_profile=icc,
                exif=piexif.dump({"0th": {piexif.ImageIFD.Orientation: 6}}),
            )
            optimizer = InstaOptimizer()
            for quality in (30, 94):
                for mode in MetadataMode:
                    with self.subTest(quality=quality, mode=mode):
                        config = plain_config(
                            aspect_ratio=AspectRatio.FEED_4_5,
                            grain_strength=1.1, disrupt_strength=0.7,
                            metadata_mode=mode, jpeg_quality=quality,
                        )
                        preview = optimizer.process_preview_file(source, config)
                        optimizer.process_file(source, output, config)
                        with Image.open(output) as saved:
                            np.testing.assert_array_equal(np.asarray(preview.jpeg), np.asarray(saved))
                        self.assertEqual(preview.jpeg_size_bytes, os.path.getsize(output))
                        self.assertEqual(preview.before.size, (1080, 1350))
                        self.assertEqual(preview.processed.size, preview.jpeg.size)
                        self.assertIsNone(config.random_seed)

    def test_automatic_seed_is_stable_per_file_and_explicit_seed_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [os.path.join(folder, name) for name in ("a.png", "b.png")]
            for path in paths:
                Image.new("RGB", (64, 48), (128,) * 3).save(path)
            optimizer = InstaOptimizer()
            config = plain_config(grain_strength=2)
            first = optimizer.process_preview_file(paths[0], config)
            second_file = optimizer.process_preview_file(paths[1], config)
            optimizer.process_preview_file(paths[0], replace(config, grain_strength=0.5))
            restored = optimizer.process_preview_file(paths[0], config)
            np.testing.assert_array_equal(np.asarray(first.processed), np.asarray(restored.processed))
            self.assertFalse(np.array_equal(np.asarray(first.processed), np.asarray(second_file.processed)))
            self.assertEqual(optimizer.config_for_file(paths[0], replace(config, random_seed=7)).random_seed, 7)
            self.assertIsNone(config.random_seed)

    def test_concurrent_seed_assignment_is_consistent(self):
        optimizer = InstaOptimizer()
        config = plain_config()
        with ThreadPoolExecutor(max_workers=4) as pool:
            seeds = list(pool.map(lambda _: optimizer.config_for_file("same.png", config).random_seed, range(20)))
        self.assertEqual(len(set(seeds)), 1)
        self.assertIsNone(config.random_seed)

    def test_normalized_source_is_reused_and_changed_file_is_reloaded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "source.png")
            Image.new("RGB", (64, 48), (120, 80, 60)).save(path)
            optimizer = InstaOptimizer()
            with patch("core.insta_optimizer.Image.open", wraps=Image.open) as opened:
                first = optimizer.process_preview_file(path, plain_config())
                optimizer.process_preview_file(path, plain_config(jpeg_quality=60))
                source_reads = [call for call in opened.call_args_list if isinstance(call.args[0], str)]
                self.assertEqual(len(source_reads), 1)
                stat = os.stat(path)
                Image.new("RGB", (64, 48), (30, 60, 90)).save(path)
                os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
                changed = optimizer.process_preview_file(path, plain_config())
                source_reads = [call for call in opened.call_args_list if isinstance(call.args[0], str)]
                self.assertEqual(len(source_reads), 2)
            self.assertNotEqual(first.before.getpixel((0, 0)), changed.before.getpixel((0, 0)))

    def test_alpha_background_and_original_cap_are_part_of_cache_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "source.png")
            Image.new("RGB", (4200, 900), (0,) * 3).save(path, "PNG", transparency=(0, 0, 0))
            optimizer = InstaOptimizer()
            feed = optimizer.process_preview_file(path, plain_config(aspect_ratio=AspectRatio.FEED_4_5))
            original = optimizer.process_preview_file(path, plain_config(alpha_background=(32, 64, 96)))
            self.assertEqual(feed.before.size, (1080, 1350))
            self.assertEqual(feed.before.getpixel((0, 0)), (255,) * 3)
            self.assertEqual(original.before.size, (4096, 878))
            self.assertEqual(original.before.getpixel((0, 0)), (32, 64, 96))

    def test_source_cache_is_bounded_and_owns_its_pixels(self):
        cache = NormalizedImageCache(max_bytes=600)
        source = Image.new("RGB", (10, 10), (128,) * 3)
        cache.put("a", source)
        source.putpixel((0, 0), (0,) * 3)
        cached = cache.get("a")
        self.assertEqual(cached.getpixel((0, 0)), (128,) * 3)
        cached.putpixel((0, 0), (255,) * 3)
        self.assertEqual(cache.get("a").getpixel((0, 0)), (128,) * 3)
        cache.put("b", source)
        cache.get("a")
        cache.put("c", source)
        self.assertIsNone(cache.get("b"))
        self.assertIsNotNone(cache.get("a"))
        self.assertLessEqual(cache.size_bytes, cache.max_bytes)
        cache.put("huge", Image.new("RGB", (100, 100)))
        self.assertIsNone(cache.get("huge"))
        self.assertLessEqual(cache.size_bytes, cache.max_bytes)
        cache.clear()
        self.assertEqual(cache.size_bytes, 0)


class TestPreviewGUI(unittest.TestCase):
    def test_preview_load_does_not_decode_on_ui_thread(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "source.png")
            Image.new("RGB", (64, 48)).save(path)
            window = MainWindow()
            try:
                with patch("core.insta_optimizer.Image.open") as opened:
                    window._load_preview(path)
                    opened.assert_not_called()
                self.assertTrue(window._preview_timer.isActive())
            finally:
                window._preview_timer.stop()
                window.close()

    def test_worker_renders_in_background(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "source.png")
            Image.new("RGB", (64, 48)).save(path)
            optimizer = InstaOptimizer()
            real_render = optimizer.process_preview_file
            thread_ids, results, errors = [], [], []

            def render(*args):
                thread_ids.append(threading.get_ident())
                return real_render(*args)

            worker = PreviewWorker(optimizer, path, plain_config(), 1)
            worker.preview_ready.connect(lambda *args: results.append(args))
            worker.preview_failed.connect(lambda *args: errors.append(args))
            loop = QEventLoop()
            worker.finished.connect(loop.quit)
            timeout = QTimer()
            timeout.setSingleShot(True)
            timeout.timeout.connect(loop.quit)
            with patch.object(optimizer, "process_preview_file", side_effect=render):
                worker.start()
                timeout.start(5000)
                loop.exec()
                timeout.stop()
                self.assertTrue(worker.wait(5000))
            self.assertEqual(errors, [])
            self.assertEqual(len(results), 1)
            self.assertNotEqual(thread_ids[0], threading.get_ident())

    def test_jpeg_toggle_uses_rendered_versions_without_reprocessing(self):
        window = MainWindow()
        try:
            window._current_preview_file = "sample.png"
            window._on_preview_ready(0, "sample.png", sample_preview())
            self.assertEqual(window.comparison_slider._pixmap_after.toImage().pixelColor(0, 0).red(), 96)
            with patch.object(window.optimizer, "process_preview_file") as render:
                window.chk_jpeg_preview.setChecked(False)
                self.assertEqual(window.comparison_slider._pixmap_after.toImage().pixelColor(0, 0).red(), 80)
                window.chk_jpeg_preview.setChecked(True)
                render.assert_not_called()
            self.assertIn("JPEG 90", window.lbl_preview_info.text())
        finally:
            window.close()

    def test_stale_results_are_discarded_and_settings_hide_old_preview(self):
        window = MainWindow()
        try:
            window._current_preview_file = "sample.png"
            window._preview_generation = 2
            result = sample_preview()
            window._on_preview_ready(1, "sample.png", result)
            window._on_preview_ready(2, "other.png", result)
            self.assertIsNone(window._preview_result)
            window._on_preview_ready(2, "sample.png", result)
            self.assertIs(window._preview_result, result)
            window.settings_panel.slider_jpeg.setValue(70)
            self.assertEqual(window.settings_panel.get_current_config().jpeg_quality, 70)
            self.assertIsNone(window.comparison_slider._pixmap_after)
            self.assertIsNone(window._preview_result)
            window._on_preview_ready(2, "sample.png", result)
            self.assertIsNone(window._preview_result)
            window._on_clear_queue()
            self.assertFalse(window._preview_timer.isActive())
        finally:
            window._preview_timer.stop()
            window.close()

    def test_native_geometry_respects_physical_pixels_on_hidpi(self):
        size = QSize(1200, 800)
        before, after, _, _ = compute_slider_geometry(size, size, 1000, 800, native_scale=0.5)
        self.assertEqual(before.width() * 2, size.width())
        self.assertEqual(before.height() * 2, size.height())
        self.assertEqual(before, after)

    def test_zoom_100_scrolls_and_fit_restores_viewport(self):
        window = MainWindow()
        try:
            window.show()
            window.drop_zone.hide()
            window.preview_toolbar.show()
            window.preview_scroll.show()
            window.comparison_slider.show()
            image = Image.new("RGB", (1280, 1600), (128,) * 3)
            window.comparison_slider.set_images(image, image)
            window.btn_preview_100.click()
            app.processEvents()
            ratio = window.comparison_slider.devicePixelRatioF()
            self.assertEqual(window.comparison_slider.width(), round(image.width / ratio))
            self.assertEqual(window.comparison_slider.height(), round(image.height / ratio))
            self.assertGreater(window.preview_scroll.verticalScrollBar().maximum(), 0)
            window.btn_preview_fit.click()
            app.processEvents()
            self.assertTrue(window.preview_scroll.widgetResizable())
            self.assertFalse(window.comparison_slider._zoom_100)
            self.assertEqual(window.preview_scroll.horizontalScrollBar().maximum(), 0)
            self.assertEqual(window.preview_scroll.verticalScrollBar().maximum(), 0)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
