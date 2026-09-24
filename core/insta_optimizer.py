"""Instagram Optimizer & Pipeline Orchestrator.

Combines metadata removal, watermark disruption, smart face-centered cropping,
camera physics emulation, and authentic Apple iPhone EXIF injection into a unified
production pipeline.
"""

import io
import os
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Callable, Tuple
from PIL import Image
import piexif

from .c2pa_killer import clean_image_buffer
from .watermark_disruptor import disrupt_watermarks
from .camera_optics import CameraOptics
from .smart_cropper import SmartCropper, AspectRatio
from .exif_spoofer import ExifSpoofer, CameraPreset, MetadataMode

TupleImageResult = Tuple[Image.Image, bytes]
MAX_IMAGE_PIXELS = 50_000_000  # 50 Megapixels safety limit


def validate_image_dimensions(image: Image.Image) -> None:
    """Validates that image dimensions do not exceed the safe limit before raster allocation."""
    w, h = image.size
    pixels = w * h
    if pixels > MAX_IMAGE_PIXELS:
        raise ValueError(
            f"Разрешение изображения {w}x{h} ({pixels / 1e6:.1f} MP) "
            f"превышает безопасный предел {MAX_IMAGE_PIXELS / 1e6:.0f} MP"
        )


@dataclass
class ProcessingConfig:
    aspect_ratio: AspectRatio = AspectRatio.FEED_4_5
    camera_preset: CameraPreset = CameraPreset.IPHONE_15_PRO
    metadata_mode: MetadataMode = MetadataMode.MINIMAL
    disrupt_strength: float = 1.0
    grain_strength: float = 1.0
    aberration_px: float = 0.65
    vignette_strength: float = 0.025
    enable_photonic_grade: bool = True
    use_smart_face_centering: bool = True
    jpeg_quality: int = 90
    enable_bayer_matrix: bool = False
    bayer_strength: float = 0.8
    enable_isp_enhancement: bool = False
    sharpen_amount: float = 0.45
    alpha_background: Tuple[int, int, int] = (255, 255, 255)
    random_seed: Optional[int] = None
    capture_time: Optional[datetime] = None
    overwrite_existing: bool = False


    @classmethod
    def ofm_master(cls) -> "ProcessingConfig":
        """Default recommended profile for AI influencers and models."""
        return cls(
            aspect_ratio=AspectRatio.FEED_4_5,
            camera_preset=CameraPreset.IPHONE_15_PRO,
            disrupt_strength=1.0,
            grain_strength=1.0,
            aberration_px=0.65,
            vignette_strength=0.025,
            enable_photonic_grade=True,
            use_smart_face_centering=True,
            jpeg_quality=90,
            enable_bayer_matrix=False,
            enable_isp_enhancement=False,
        )

    @classmethod
    def anti_classifier(cls) -> "ProcessingConfig":
        """Maximum protection against vision classifiers (Hive Moderation, Sightengine, Meta Vision).

        Injects physical camera CMOS Bayer matrix pattern and ISP local contrast/unsharp masking.
        """
        return cls(
            aspect_ratio=AspectRatio.FEED_4_5,
            camera_preset=CameraPreset.IPHONE_15_PRO,
            disrupt_strength=1.2,
            grain_strength=1.4,
            aberration_px=0.75,
            vignette_strength=0.03,
            enable_photonic_grade=True,
            use_smart_face_centering=True,
            jpeg_quality=89,
            enable_bayer_matrix=True,
            bayer_strength=1.0,
            enable_isp_enhancement=True,
            sharpen_amount=0.55,
        )

    @classmethod
    def iphone_natural(cls) -> "ProcessingConfig":
        """Subtle profile for daylight selfies with iPhone 16 Pro Max signature."""
        return cls(
            aspect_ratio=AspectRatio.FEED_4_5,
            camera_preset=CameraPreset.IPHONE_16_PRO_MAX,
            disrupt_strength=0.7,
            grain_strength=0.7,
            aberration_px=0.4,
            vignette_strength=0.018,
            enable_photonic_grade=True,
            use_smart_face_centering=True,
            jpeg_quality=92,
        )

    @classmethod
    def aggressive_bypass(cls) -> "ProcessingConfig":
        """Maximum anti-detection profile for challenging or heavily watermarked generations."""
        return cls(
            aspect_ratio=AspectRatio.FEED_4_5,
            camera_preset=CameraPreset.IPHONE_15_PRO,
            disrupt_strength=1.4,
            grain_strength=1.35,
            aberration_px=0.85,
            vignette_strength=0.035,
            enable_photonic_grade=True,
            use_smart_face_centering=True,
            jpeg_quality=89,
            enable_bayer_matrix=True,
            bayer_strength=0.7,
        )

    @classmethod
    def story_reels(cls) -> "ProcessingConfig":
        """Profile tailored for 9:16 Instagram Stories and Reels."""
        return cls(
            aspect_ratio=AspectRatio.STORY_9_16,
            camera_preset=CameraPreset.IPHONE_15_PRO,
            disrupt_strength=1.0,
            grain_strength=1.0,
            aberration_px=0.6,
            vignette_strength=0.025,
            enable_photonic_grade=True,
            use_smart_face_centering=True,
            jpeg_quality=90,
        )


class InstaOptimizer:
    """End-to-end processor for transforming AI images into Instagram-ready camera captures."""

    def __init__(self):
        self.cropper = SmartCropper()

    def process_pil(
        self,
        image: Image.Image,
        config: ProcessingConfig,
    ) -> TupleImageResult:
        """Processes a PIL Image through the complete pipeline and returns (clean_image, exif_bytes)."""
        validate_image_dimensions(image)

        # Step 1: Strip all metadata containers, normalize orientation, color profile, and alpha
        clean_img = clean_image_buffer(image, alpha_background=config.alpha_background)
        normalized_size = clean_img.size

        # Step 2: Smart Face-Centered Cropping to Target Instagram Aspect Ratio (Memory Optimization)
        # Cropping and scaling first dramatically reduces memory footprint for downstream pixel operations
        if config.aspect_ratio == AspectRatio.ORIGINAL:
            # Preserve normalized dimensions (post-orientation transposition)
            if clean_img.size != normalized_size:
                framed_img = clean_img.resize(normalized_size, Image.LANCZOS)
            else:
                framed_img = clean_img
            target_size = normalized_size
        else:
            framed_img = self.cropper.crop_and_scale(
                clean_img,
                aspect_ratio=config.aspect_ratio,
                use_smart_face_centering=config.use_smart_face_centering,
            )
            target_size = framed_img.size

        # Step 3: Perturb latent frequency watermarks / grid artifacts at target resolution
        if config.disrupt_strength > 0:
            framed_img = disrupt_watermarks(
                framed_img,
                strength=config.disrupt_strength,
                enable_micro_rotation=True,
                enable_pixel_jitter=True,
                seed=config.random_seed,
            )
            # Ensure precise target dimension adherence after micro-rotation
            if framed_img.size != target_size:
                framed_img = framed_img.resize(target_size, Image.LANCZOS)

        # Step 4: Apply Physical Camera Optics & Film Emulation
        final_img = CameraOptics.apply_all(
            framed_img,
            iso=100,
            grain_strength=config.grain_strength,
            aberration_px=config.aberration_px,
            vignette_strength=config.vignette_strength,
            enable_photonic=config.enable_photonic_grade,
            enable_bayer_matrix=config.enable_bayer_matrix,
            bayer_strength=config.bayer_strength,
            enable_isp_enhancement=config.enable_isp_enhancement,
            sharpen_amount=config.sharpen_amount,
            seed=config.random_seed,
        )

        # Step 5: Synthesize Camera EXIF Profile
        w, h = final_img.size
        mode_val = MetadataMode(config.metadata_mode) if isinstance(config.metadata_mode, str) else config.metadata_mode
        exif_bytes = ExifSpoofer.generate_exif(
            width=w,
            height=h,
            device=config.camera_preset,
            capture_time=config.capture_time,
            randomize_exposure=True,
            mode=mode_val,
            random_seed=config.random_seed,
        )

        return final_img, exif_bytes

    def process_file(
        self,
        input_path: str,
        output_path: str,
        config: Optional[ProcessingConfig] = None,
    ) -> str:
        """Processes an image file from disk and saves the optimized JPEG atomically."""
        if config is None:
            config = ProcessingConfig.ofm_master()

        with Image.open(input_path) as src:
            validate_image_dimensions(src)
            src.load()
            processed_img, exif_bytes = self.process_pil(src, config)


        # Ensure target directory exists
        target_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(target_dir, exist_ok=True)

        # Atomic write: save to a temporary file first, then replace
        base_name = os.path.basename(output_path)
        tmp_name = f".tmp_{os.getpid()}_{base_name}"
        tmp_path = os.path.join(target_dir, tmp_name)

        save_kwargs = {
            "format": "JPEG",
            "quality": config.jpeg_quality,
            "subsampling": 2,
            "optimize": True,
        }
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes

        try:
            processed_img.save(tmp_path, **save_kwargs)
            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                raise IOError(f"Failed to generate output JPEG at {tmp_path}")

            os.replace(tmp_path, output_path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        return output_path


