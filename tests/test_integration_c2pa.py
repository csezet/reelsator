"""Integration tests verifying eradication of C2PA provenance manifests across image formats."""

import os
import tempfile
import unittest
from PIL import Image

from core.insta_optimizer import InstaOptimizer, ProcessingConfig
from core.exif_spoofer import MetadataMode
from core.smart_cropper import AspectRatio

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def detect_c2pa_manifest(file_path: str) -> bool:
    """Independent validator checking for presence of C2PA / JUMBF manifest stores in JPEG/PNG."""
    with open(file_path, "rb") as f:
        data = f.read()

    # PNG caBX chunk detection
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        offset = 8
        while offset < len(data) - 8:
            length = int.from_bytes(data[offset : offset + 4], "big")
            chunk_type = data[offset + 4 : offset + 8]
            if chunk_type in (b"caBX", b"c2pa"):
                return True
            offset += 12 + length
        return False

    # JPEG APP11 JUMBF / C2PA marker detection (0xFFEB)
    if data.startswith(b"\xff\xd8"):
        offset = 2
        while offset < len(data) - 4:
            if data[offset] != 0xFF:
                break
            marker = data[offset + 1]
            if marker in (0xD9, 0xDA):  # EOI or SOS
                break
            length = int.from_bytes(data[offset + 2 : offset + 4], "big")
            if marker == 0xEB:  # APP11
                payload = data[offset + 4 : offset + 2 + length]
                if b"jumb" in payload or b"c2pa" in payload or b"JP\x00\x00" in payload:
                    return True
            offset += 2 + length
        return False

    return False


class TestC2PAIntegration(unittest.TestCase):
    """Verifies that Reelsator eradicates real C2PA manifest stores and normalizes files."""

    def setUp(self):
        self.optimizer = InstaOptimizer()
        self.config = ProcessingConfig.ofm_master()
        self.config.aspect_ratio = AspectRatio.ORIGINAL
        self.config.metadata_mode = MetadataMode.MINIMAL

    def test_c2pa_cai_signed_manifest_eradication(self):
        """Verify authentic signed C2PA manifest from Content Authenticity Initiative is eradicated."""
        fixture_path = os.path.join(FIXTURES_DIR, "c2pa_cai_reference.jpg")
        self.assertTrue(os.path.exists(fixture_path), f"Fixture not found: {fixture_path}")
        self.assertTrue(detect_c2pa_manifest(fixture_path), "Validator failed to detect signed C2PA manifest in CAI fixture")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "output.jpg")
            self.optimizer.process_file(fixture_path, out_path, self.config)

            self.assertTrue(os.path.exists(out_path))
            self.assertFalse(detect_c2pa_manifest(out_path), "Signed C2PA manifest still detected in output after Reelsator")

            with Image.open(out_path) as res:
                self.assertEqual(res.mode, "RGB")

    def test_c2pa_synthetic_jumbf_eradication(self):
        """Verify synthetic ISO/IEC 19566-5 APP11 JUMBF C2PA manifest is detected and eradicated."""
        fixture_path = os.path.join(FIXTURES_DIR, "synthetic_c2pa_jumbf.jpg")
        self.assertTrue(os.path.exists(fixture_path), f"Fixture not found: {fixture_path}")
        self.assertTrue(detect_c2pa_manifest(fixture_path), "Validator failed to detect C2PA in synthetic JUMBF fixture")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "output.jpg")
            self.optimizer.process_file(fixture_path, out_path, self.config)

            self.assertTrue(os.path.exists(out_path))
            self.assertFalse(detect_c2pa_manifest(out_path), "C2PA manifest still detected in output of synthetic JUMBF")

            with Image.open(out_path) as res:
                self.assertEqual(res.mode, "RGB")
                self.assertEqual(res.size, (160, 160))

    def test_c2pa_synthetic_cabx_eradication(self):
        """Verify synthetic C2PA caBX PNG chunk is detected and eradicated after processing."""
        fixture_path = os.path.join(FIXTURES_DIR, "synthetic_c2pa_cabx.png")
        self.assertTrue(os.path.exists(fixture_path), f"Fixture not found: {fixture_path}")
        self.assertTrue(detect_c2pa_manifest(fixture_path), "Validator failed to detect C2PA in synthetic caBX PNG")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "output.jpg")
            self.optimizer.process_file(fixture_path, out_path, self.config)

            self.assertTrue(os.path.exists(out_path))
            self.assertFalse(detect_c2pa_manifest(out_path), "C2PA caBX still detected in output of synthetic PNG")

            with Image.open(out_path) as res:
                self.assertEqual(res.mode, "RGB")
                self.assertEqual(res.size, (160, 160))

    def test_orientation_6_fixture(self):
        """Verify physical 200x100 Orientation=6 fixture normalizes to 100x200."""
        fixture_path = os.path.join(FIXTURES_DIR, "orientation_6.jpg")
        self.assertTrue(os.path.exists(fixture_path))

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "output.jpg")
            self.optimizer.process_file(fixture_path, out_path, self.config)

            with Image.open(out_path) as res:
                self.assertEqual(res.size, (100, 200))

    def test_rgba_transparent_fixture(self):
        """Verify transparent PNG fixture exports over solid white without black artifacts."""
        fixture_path = os.path.join(FIXTURES_DIR, "rgba_transparent.png")
        self.assertTrue(os.path.exists(fixture_path))

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "output.jpg")
            self.optimizer.process_file(fixture_path, out_path, self.config)

            with Image.open(out_path) as res:
                self.assertEqual(res.mode, "RGB")
                # Center pixel (which was transparent) must be solid white (>=240, accounting for JPEG DCT quantization)
                px = res.getpixel((60, 60))
                self.assertGreaterEqual(px[0], 240)
                self.assertGreaterEqual(px[1], 240)
                self.assertGreaterEqual(px[2], 240)

    def test_display_p3_reference_fixture(self):
        """Verify reference Display P3 fixture from W3C is recognized with Apple profile and converted to sRGB."""
        import io
        from PIL import ImageCms

        fixture_path = os.path.join(FIXTURES_DIR, "display_p3_reference.jpg")
        self.assertTrue(os.path.exists(fixture_path), f"Fixture not found: {fixture_path}")

        # Verify authentic Apple Display P3 profile is embedded
        with Image.open(fixture_path) as src:
            icc_raw = src.info.get("icc_profile")
            self.assertIsNotNone(icc_raw, "Missing ICC profile in display_p3_reference.jpg")
            profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_raw))
            self.assertIn("Display P3", ImageCms.getProfileDescription(profile))
            self.assertIn("Apple", ImageCms.getProfileCopyright(profile))

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "output.jpg")
            self.optimizer.process_file(fixture_path, out_path, self.config)

            with Image.open(out_path) as res:
                self.assertEqual(res.mode, "RGB")
                self.assertEqual(res.size, (120, 120))
                # Color shift assertion: Display-P3 (200, 50, 50) converts into ~ (218, 24, 40) in sRGB
                px = res.getpixel((60, 60))
                self.assertGreater(px[0], 205, f"Expected transformed red > 205, got {px[0]}")
                self.assertLess(px[1], 35, f"Expected transformed green < 35, got {px[1]}")

    def test_display_p3_synthetic_fixture(self):
        """Verify synthetic Display P3 fixture is converted cleanly into standard sRGB."""
        import io
        from PIL import ImageCms

        fixture_path = os.path.join(FIXTURES_DIR, "synthetic_display_p3_profile.jpg")
        self.assertTrue(os.path.exists(fixture_path), f"Fixture not found: {fixture_path}")

        with Image.open(fixture_path) as src:
            icc_raw = src.info.get("icc_profile")
            self.assertIsNotNone(icc_raw, "Missing ICC profile in synthetic_display_p3_profile.jpg")
            profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_raw))
            self.assertIn("Display P3", ImageCms.getProfileDescription(profile))

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "output.jpg")
            self.optimizer.process_file(fixture_path, out_path, self.config)

            with Image.open(out_path) as res:
                self.assertEqual(res.mode, "RGB")
                self.assertEqual(res.size, (120, 120))
                px = res.getpixel((60, 60))
                self.assertGreater(px[0], 205)
                self.assertLess(px[1], 35)


if __name__ == "__main__":
    unittest.main()

