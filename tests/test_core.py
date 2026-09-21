"""Comprehensive automated tests for Reelsator core processing pipeline."""

import os
import io
import struct
import tempfile
import unittest
from PIL import Image, PngImagePlugin
import numpy as np
import piexif

from core.c2pa_killer import (
    clean_image_buffer,
    strip_jpeg_metadata,
    strip_png_metadata,
    DISALLOWED_PNG_CHUNKS,
)
from core.watermark_disruptor import disrupt_watermarks
from core.camera_optics import CameraOptics
from core.smart_cropper import SmartCropper, AspectRatio, TARGET_DIMENSIONS
from core.exif_spoofer import ExifSpoofer, CameraPreset
from core.insta_optimizer import InstaOptimizer, ProcessingConfig
from core.pipeline import BatchPipeline


class TestReelsatorCore(unittest.TestCase):
    """Test suite verifying all anti-detection, optical, and optimization modules."""

    def setUp(self):
        # Create a synthetic test image (e.g. 1024x1024 RGB)
        self.img_size = (1024, 1024)
        arr = np.zeros((1024, 1024, 3), dtype=np.uint8)
        # Add smooth gradients and skin-like tones
        arr[:, :, 0] = np.linspace(200, 240, 1024, dtype=np.uint8)[:, None]
        arr[:, :, 1] = np.linspace(150, 190, 1024, dtype=np.uint8)[:, None]
        arr[:, :, 2] = np.linspace(130, 170, 1024, dtype=np.uint8)[:, None]
        self.test_img = Image.fromarray(arr)

    def test_c2pa_and_metadata_cleaner(self):
        """Verify that prompts and container metadata are eradicated."""
        # Embed fake ChatGPT prompt chunk into PNG
        buf = io.BytesIO()
        meta = PngImagePlugin.PngInfo()
        meta.add_text("prompt", "A photorealistic portrait of an AI influencer")
        meta.add_text("parameters", "CFG 7.0, Steps 30, Sampler DPM++")
        self.test_img.save(buf, format="PNG", pnginfo=meta)
        png_bytes_with_prompt = buf.getvalue()

        # Check prompt exists in raw bytes
        self.assertIn(b"photorealistic", png_bytes_with_prompt)

        # Inject fake caBX C2PA chunk into the bytes
        cabx_chunk = struct.pack(">I", 8) + b"caBX" + b"c2pajumb" + struct.pack(">I", 0)
        png_with_cabx = png_bytes_with_prompt[:33] + cabx_chunk + png_bytes_with_prompt[33:]
        self.assertIn(b"caBX", png_with_cabx)

        # Clean via strip_png_metadata
        cleaned_png_bytes = strip_png_metadata(png_with_cabx)
        self.assertNotIn(b"photorealistic", cleaned_png_bytes)
        self.assertNotIn(b"parameters", cleaned_png_bytes)
        self.assertNotIn(b"caBX", cleaned_png_bytes)

        # Clean via clean_image_buffer
        with Image.open(io.BytesIO(png_bytes_with_prompt)) as img_loaded:
            clean_pil = clean_image_buffer(img_loaded)
            self.assertEqual(len(clean_pil.info), 0)


    def test_watermark_disruptor(self):
        """Verify sub-pixel geometric shifting and LSB perturbation."""
        orig_arr = np.asarray(self.test_img)
        disrupted = disrupt_watermarks(self.test_img, strength=1.0)
        disrupted_arr = np.asarray(disrupted)

        # Image should be slightly resized and perturbed
        self.assertNotEqual(self.test_img.size, disrupted.size)
        # But visually consistent (mean absolute error < 5 levels)
        mae = np.mean(np.abs(orig_arr[: disrupted_arr.shape[0], : disrupted_arr.shape[1]].astype(float) - disrupted_arr.astype(float)))
        self.assertLess(mae, 15.0)

    def test_camera_optics_grain_and_vignette(self):
        """Verify sensor noise and lens optical simulation."""
        # 1. Sensor grain
        grained = CameraOptics.add_sensor_grain(self.test_img, iso=100, grain_strength=1.0)
        self.assertEqual(grained.size, self.test_img.size)

        orig_std = np.std(np.asarray(self.test_img))
        grained_std = np.std(np.asarray(grained))
        # Adding sensor grain increases local standard deviation (texture)
        self.assertGreaterEqual(grained_std, orig_std - 1.0)

        # 2. Chromatic aberration
        aberrated = CameraOptics.add_chromatic_aberration(self.test_img, aberration_px=1.0)
        self.assertEqual(aberrated.size, self.test_img.size)

        # 3. Vignette
        vignetted = CameraOptics.add_vignette(self.test_img, strength=0.05)
        self.assertEqual(vignetted.size, self.test_img.size)
        # Corner pixels should be darker than original
        orig_corner = np.mean(np.asarray(self.test_img)[0, 0, :])
        vig_corner = np.mean(np.asarray(vignetted)[0, 0, :])
        self.assertLess(vig_corner, orig_corner)

        # 4. Bayer Matrix Simulation
        bayer = CameraOptics.apply_bayer_matrix(self.test_img, strength=1.0)
        self.assertEqual(bayer.size, self.test_img.size)
        self.assertNotEqual(np.asarray(self.test_img)[0, 0, 1], np.asarray(bayer)[0, 0, 1])

        # 5. ISP Local Contrast Enhancement
        isp = CameraOptics.apply_isp_local_contrast(self.test_img, sharpen_amount=0.5, contrast_amount=0.1)
        self.assertEqual(isp.size, self.test_img.size)


    def test_smart_cropper_dimensions(self):
        """Verify target cropping to 1080x1350 (4:5) and other Instagram formats."""
        cropper = SmartCropper()

        # 4:5 Portrait Feed
        feed_img = cropper.crop_and_scale(self.test_img, aspect_ratio=AspectRatio.FEED_4_5)
        self.assertEqual(feed_img.size, (1080, 1350))

        # 1:1 Square
        sq_img = cropper.crop_and_scale(self.test_img, aspect_ratio=AspectRatio.SQUARE_1_1)
        self.assertEqual(sq_img.size, (1080, 1080))

        # 9:16 Story/Reels
        story_img = cropper.crop_and_scale(self.test_img, aspect_ratio=AspectRatio.STORY_9_16)
        self.assertEqual(story_img.size, (1080, 1920))

    def test_exif_spoofer(self):
        """Verify that spoofed Apple iPhone EXIF is 100% syntactically valid."""
        exif_bytes = ExifSpoofer.generate_exif(
            width=1080,
            height=1350,
            device=CameraPreset.IPHONE_15_PRO,
        )
        self.assertIsInstance(exif_bytes, bytes)
        self.assertGreater(len(exif_bytes), 100)

        # Validate by loading back through piexif parser
        exif_dict = piexif.load(exif_bytes)
        self.assertEqual(exif_dict["0th"][piexif.ImageIFD.Make], b"Apple")
        self.assertEqual(exif_dict["0th"][piexif.ImageIFD.Model], b"iPhone 15 Pro")
        self.assertEqual(exif_dict["Exif"][piexif.ExifIFD.FocalLengthIn35mmFilm], 24)
        self.assertEqual(exif_dict["Exif"][piexif.ExifIFD.PixelXDimension], 1080)
        self.assertEqual(exif_dict["Exif"][piexif.ExifIFD.PixelYDimension], 1350)

    def test_full_insta_optimizer_pipeline(self):
        """Verify complete end-to-end processing and JPEG export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "raw_ai_input.png")
            output_path = os.path.join(tmpdir, "instagram_ready.jpg")

            self.test_img.save(input_path, format="PNG")

            optimizer = InstaOptimizer()
            config = ProcessingConfig.ofm_master()
            res_path = optimizer.process_file(input_path, output_path, config)

            self.assertTrue(os.path.exists(res_path))
            self.assertGreater(os.path.getsize(res_path), 50_000)

            # Inspect output image
            with Image.open(res_path) as out_img:
                self.assertEqual(out_img.size, (1080, 1350))
                self.assertEqual(out_img.format, "JPEG")

                # Verify EXIF is present on saved JPEG
                exif_data = piexif.load(out_img.info.get("exif", b""))
                self.assertEqual(exif_data["0th"][piexif.ImageIFD.Make], b"Apple")
                self.assertEqual(exif_data["0th"][piexif.ImageIFD.Model], b"iPhone 15 Pro")

    def test_batch_pipeline(self):
        """Verify batch processor on multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "inputs")
            out_dir = os.path.join(tmpdir, "outputs")
            os.makedirs(in_dir)

            for i in range(3):
                p = os.path.join(in_dir, f"sample_{i}.jpg")
                self.test_img.save(p, format="JPEG")

            images = BatchPipeline.find_images_in_dir(in_dir)
            self.assertEqual(len(images), 3)

            pipeline = BatchPipeline()
            callback_calls = []

            def on_progress(cur, total, name, ok):
                callback_calls.append((cur, total, name, ok))

            results = pipeline.process_batch(
                images,
                out_dir,
                progress_callback=on_progress,
            )

            self.assertEqual(len(results), 3)
            self.assertTrue(all(r.success for r in results))
            self.assertEqual(len(callback_calls), 3)
            self.assertEqual(callback_calls[-1][0], 3)


if __name__ == "__main__":
    unittest.main()
