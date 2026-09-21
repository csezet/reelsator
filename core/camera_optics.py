"""Camera Optics & De-AIfication Engine.

Emulates real physical smartphone/camera optical characteristics:
- Luminance-adaptive CMOS sensor grain (Poisson/Gaussian noise)
- Lateral chromatic aberration towards frame edges
- Natural lens vignette (cos^4 law light falloff)
- Apple Photonic Engine color and contrast calibration
"""

from typing import Tuple, Optional
from PIL import Image
import numpy as np
import cv2


class CameraOptics:
    """Simulates real-world camera sensor and optical characteristics."""

    @staticmethod
    def add_sensor_grain(
        image: Image.Image,
        iso: int = 100,
        grain_strength: float = 1.0,
        seed: Optional[int] = None,
    ) -> Image.Image:
        """Adds luminance-adaptive digital sensor noise mimicking a smartphone CMOS sensor.

        Shadows and midtones receive realistic grain, while bright highlights stay clean.
        """
        if grain_strength <= 0:
            return image

        arr = np.asarray(image, dtype=np.float32)
        h, w, c = arr.shape

        # Calculate luminance Y (0.0 to 1.0)
        lum = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]) / 255.0

        # Luminance mask: highest in shadows and midtones, rolls off in highlights
        # Real sensors have higher visible noise in underexposed/mid regions
        lum_mask = np.clip(1.0 - np.power(lum, 1.4), 0.15, 1.0)
        lum_mask = np.repeat(lum_mask[:, :, np.newaxis], c, axis=2)

        # Noise amplitude based on ISO and strength multiplier
        # ISO 64-100: sigma ~ 1.8-2.4; ISO 400: sigma ~ 4.0
        base_sigma = (1.6 + (iso / 200.0) * 0.8) * grain_strength

        rng = np.random.default_rng(seed)
        # Luminance noise (monochrome component, 80%) + subtle chroma noise (20%)
        mono_noise = rng.normal(0.0, base_sigma * 0.8, (h, w, 1)).astype(np.float32)
        color_noise = rng.normal(0.0, base_sigma * 0.2, (h, w, c)).astype(np.float32)
        total_noise = (mono_noise + color_noise) * lum_mask

        noisy_arr = np.clip(arr + total_noise, 0.0, 255.0).astype(np.uint8)
        return Image.fromarray(noisy_arr)

    @staticmethod
    def add_chromatic_aberration(
        image: Image.Image,
        aberration_px: float = 0.75,
    ) -> Image.Image:
        """Simulates lateral chromatic aberration by radially shifting Red and Blue channels.

        Max effect occurs at the outer corners, vanishing at the optical center.
        """
        if aberration_px <= 0:
            return image

        arr = np.asarray(image)
        h, w, _ = arr.shape
        cx, cy = w / 2.0, h / 2.0
        max_dist = np.sqrt(cx**2 + cy**2)

        # Create coordinate grids
        y_indices, x_indices = np.indices((h, w), dtype=np.float32)
        dx = x_indices - cx
        dy = y_indices - cy
        dist = np.sqrt(dx**2 + dy**2) / max_dist  # 0 at center, 1 at corner

        # Quadratic scaling for aberration displacement
        scale_factor = (dist**2) * aberration_px

        # Red channel displaced radially outwards (+scale)
        map_rx = (x_indices + (dx / np.maximum(dist * max_dist, 1e-5)) * scale_factor).astype(np.float32)
        map_ry = (y_indices + (dy / np.maximum(dist * max_dist, 1e-5)) * scale_factor).astype(np.float32)

        # Blue channel displaced radially inwards (-scale)
        map_bx = (x_indices - (dx / np.maximum(dist * max_dist, 1e-5)) * scale_factor).astype(np.float32)
        map_by = (y_indices - (dy / np.maximum(dist * max_dist, 1e-5)) * scale_factor).astype(np.float32)

        r_shifted = cv2.remap(arr[:, :, 0], map_rx, map_ry, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        g_channel = arr[:, :, 1]
        b_shifted = cv2.remap(arr[:, :, 2], map_bx, map_by, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

        merged = np.stack([r_shifted, g_channel, b_shifted], axis=2)
        return Image.fromarray(merged)

    @staticmethod
    def add_vignette(
        image: Image.Image,
        strength: float = 0.025,
    ) -> Image.Image:
        """Adds subtle radial light falloff (1.5 - 3%) mimicking mobile camera glass optics."""
        if strength <= 0:
            return image

        arr = np.asarray(image, dtype=np.float32)
        h, w, _ = arr.shape
        cx, cy = w / 2.0, h / 2.0
        max_dist = np.sqrt(cx**2 + cy**2)

        y_indices, x_indices = np.indices((h, w), dtype=np.float32)
        dist = np.sqrt((x_indices - cx) ** 2 + (y_indices - cy) ** 2) / max_dist

        # Smooth falloff mask
        vignette_mask = 1.0 - (strength * np.power(dist, 2.2))
        vignette_mask = np.clip(vignette_mask[:, :, np.newaxis], 0.0, 1.0)

        vignetted = np.clip(arr * vignette_mask, 0.0, 255.0).astype(np.uint8)
        return Image.fromarray(vignetted)

    @staticmethod
    def apply_photonic_grade(
        image: Image.Image,
        contrast_boost: float = 1.02,
        warmth: float = 1.01,
    ) -> Image.Image:
        """Applies iPhone-like Photonic Engine color grade (gentle warm skin tones, calibrated S-curve)."""
        arr = np.asarray(image, dtype=np.float32)

        # Subtle S-curve contrast
        # Normalized x in [0, 1]
        x = arr / 255.0
        # Gentle cubic curve
        s_curve = x + (contrast_boost - 1.0) * (x**2 * (3.0 - 2.0 * x) - x)
        arr = np.clip(s_curve * 255.0, 0.0, 255.0)

        # Subtle warmth (boost red channel slightly, keep blue slightly cooler)
        if warmth != 1.0:
            arr[:, :, 0] = np.clip(arr[:, :, 0] * warmth, 0.0, 255.0)
            arr[:, :, 2] = np.clip(arr[:, :, 2] * (2.0 - warmth), 0.0, 255.0)

        return Image.fromarray(arr.astype(np.uint8))

    @staticmethod
    def apply_bayer_matrix(
        image: Image.Image,
        strength: float = 1.0,
    ) -> Image.Image:
        """Emulates the physical Bayer Color Filter Array (RGGB) found on real camera CMOS sensors.

        Injects alternating-row sub-perceptual channel micro-offsets that destroy continuous
        diffusion gradients without visible artifacting to the human eye.
        """
        if strength <= 0:
            return image

        arr = np.array(image, dtype=np.int16)
        # Micro-offset (typically 6-12 levels depending on strength)
        offset = int(round(10.0 * strength))

        # Alternating row Green / Blue micro-displacement
        arr[0::2, :, 1] = np.clip(arr[0::2, :, 1] - offset, 0, 255)
        arr[0::2, :, 2] = np.clip(arr[0::2, :, 2] + offset, 0, 255)

        # Alternating column Red / Green micro-displacement
        arr[:, 0::2, 0] = np.clip(arr[:, 0::2, 0] + (offset // 2), 0, 255)
        arr[:, 0::2, 1] = np.clip(arr[:, 0::2, 1] - (offset // 2), 0, 255)

        return Image.fromarray(arr.astype(np.uint8))

    @staticmethod
    def apply_isp_local_contrast(
        image: Image.Image,
        sharpen_amount: float = 0.45,
        contrast_amount: float = 0.12,
    ) -> Image.Image:
        """Simulates camera Image Signal Processor (ISP) unsharp masking and local contrast expansion.

        Breaks synthetic AI airbrushed skin smoothness by introducing natural micro-frequency edges.
        """
        if sharpen_amount <= 0 and contrast_amount <= 0:
            return image

        arr = np.array(image, dtype=np.float32)
        h, w, c = arr.shape

        # Gaussian blur for high-pass frequency extraction
        kernel_size = max(3, (int(round(min(w, h) / 300)) * 2) + 1)
        blurred = cv2.GaussianBlur(arr, (kernel_size, kernel_size), sigmaX=1.5)

        # High-pass detail boost (unsharp mask)
        detail = arr - blurred
        sharpened = arr + detail * sharpen_amount

        # Local luminance contrast expansion
        lum = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
        local_mean = cv2.blur(lum, (25, 25))

        lum_diff = lum - local_mean
        adjusted_lum = local_mean + lum_diff * (1.0 + contrast_amount)

        # Apply luminance scaling to RGB
        scale = np.where(lum > 1.0, adjusted_lum / np.maximum(lum, 1e-5), 1.0)
        scale = np.repeat(scale[:, :, np.newaxis], c, axis=2)

        final_arr = np.clip(sharpened * scale, 0.0, 255.0).astype(np.uint8)
        return Image.fromarray(final_arr)



    @classmethod
    def apply_all(
        cls,
        image: Image.Image,
        iso: int = 100,
        grain_strength: float = 1.0,
        aberration_px: float = 0.65,
        vignette_strength: float = 0.025,
        enable_photonic: bool = True,
        enable_bayer_matrix: bool = False,
        bayer_strength: float = 0.8,
        enable_isp_enhancement: bool = False,
        sharpen_amount: float = 0.45,
        seed: Optional[int] = None,
    ) -> Image.Image:
        """Executes the complete optical de-AIfication pipeline in sequence."""
        img = image
        if enable_photonic:
            img = cls.apply_photonic_grade(img)
        if enable_bayer_matrix and bayer_strength > 0:
            img = cls.apply_bayer_matrix(img, strength=bayer_strength)
        if enable_isp_enhancement and sharpen_amount > 0:
            img = cls.apply_isp_local_contrast(img, sharpen_amount=sharpen_amount)
        if aberration_px > 0:
            img = cls.add_chromatic_aberration(img, aberration_px)
        if vignette_strength > 0:
            img = cls.add_vignette(img, vignette_strength)
        if grain_strength > 0:
            img = cls.add_sensor_grain(img, iso=iso, grain_strength=grain_strength, seed=seed)
        return img


