"""Anti-SynthID & Invisible Watermark Disruptor.

Disrupts frequency-domain, wavelet, and DCT-based latent watermarks (Google SynthID,
OpenAI/DALL-E latent marks, Digimarc) through non-linear geometric desynchronization
and sub-perceptual frequency perturbation.
"""

from typing import Tuple, Optional
from PIL import Image
import numpy as np


def disrupt_watermarks(
    image: Image.Image,
    strength: float = 1.0,
    enable_micro_rotation: bool = True,
    enable_pixel_jitter: bool = True,
    seed: Optional[int] = None,
) -> Image.Image:
    """Applies sub-pixel resampling, micro-rotation, and high-frequency perturbation.

    Args:
        image: PIL Image in RGB mode.
        strength: Multiplier (0.5 = subtle, 1.0 = standard OFM, 1.5 = aggressive).
        enable_micro_rotation: Rotates image by a fractional degree to perturb 8x8 DCT grid.
        enable_pixel_jitter: Adds sub-perceptual LSB dithering.
        seed: Optional integer seed for deterministic testing.

    Returns:
        Perturbed PIL Image.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    w, h = image.size

    # 1. Micro-Rotation (Breaks rectangular 8x8 DCT frequency blocks)
    # We apply a tiny rotation (0.04 - 0.08 deg) and immediately crop out any rotated corner padding
    if enable_micro_rotation and strength > 0.3:
        angle = 0.05 * strength
        # Rotate with BICUBIC
        rotated = image.rotate(angle, resample=Image.BICUBIC, expand=False)
        # Margin to crop black corner slivers: margin = ceil(h * sin(angle))
        # For 0.05 deg on 1000px, margin is ~1 px
        rot_pad = max(1, int(np.ceil(max(w, h) * np.sin(np.radians(abs(angle))))))
        image = rotated.crop((rot_pad, rot_pad, w - rot_pad, h - rot_pad))
        w, h = image.size

    # 2. Sub-pixel Resampling (Misaligns spatial wavelet coordinates)
    scale_factor = max(0.990, min(0.999, 1.0 - (0.003 * strength)))
    new_w = max(4, int(round(w * scale_factor)))
    new_h = max(4, int(round(h * scale_factor)))
    image = image.resize((new_w, new_h), resample=Image.LANCZOS)

    # 3. Asymmetric Micro-Crop
    crop_pixels = max(1, int(round(2 * strength)))
    if new_w > crop_pixels * 4 and new_h > crop_pixels * 4:
        image = image.crop((
            crop_pixels,
            crop_pixels,
            new_w - crop_pixels,
            new_h - crop_pixels,
        ))

    # 4. Sub-perceptual LSB Jitter / Frequency Perturbation
    if enable_pixel_jitter:
        arr = np.asarray(image, dtype=np.int16)
        rng = np.random.default_rng(seed)

        # Gaussian micro-noise (sigma ~ 0.5 - 0.8) generated directly in float32 for memory efficiency
        sigma = 0.6 * strength
        gaussian_noise = rng.standard_normal(arr.shape, dtype=np.float32) * np.float32(sigma)

        # Discrete integer LSB shift (-1, 0, 1) per channel in float32
        discrete_jitter = (rng.integers(-1, 2, size=arr.shape, dtype=np.int8) * 0.5).astype(np.float32)

        arr = arr + np.round(gaussian_noise + discrete_jitter).astype(np.int16)
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        image = Image.fromarray(arr)

    return image

