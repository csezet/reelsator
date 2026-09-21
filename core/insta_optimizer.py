"""Instagram Optimizer & Pipeline Orchestrator.

Combines metadata removal, watermark disruption, smart face-centered cropping,
camera physics emulation, and authentic Apple iPhone EXIF injection into a unified
production pipeline.
"""

import io
import os
from dataclasses import dataclass
from typing import Optional, Callable, Tuple
from PIL import Image
import piexif

from .c2pa_killer import clean_image_buffer
from .watermark_disruptor import disrupt_watermarks
from .camera_optics import CameraOptics
from .smart_cropper import SmartCropper, AspectRatio
from .exif_spoofer import ExifSpoofer, CameraPreset

TupleImageResult = Tuple[Image.Image, bytes]


@dataclass
class ProcessingConfig:
    aspect_ratio: AspectRatio = AspectRatio.FEED_4_5
    camera_preset: CameraPreset = CameraPreset.IPHONE_15_PRO
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
        # Step 1: Strip all metadata containers and prompts by extracting pure raw pixels
        clean_img = clean_image_buffer(image)

        # Step 2: Disrupt latent frequency watermarks (SynthID / DALL-E)
        if config.disrupt_strength > 0:
            clean_img = disrupt_watermarks(
                clean_img,
                strength=config.disrupt_strength,
                enable_micro_rotation=True,
                enable_pixel_jitter=True,
            )

        # Step 3: Smart Face-Centered Cropping to Instagram Aspect Ratio
        framed_img = self.cropper.crop_and_scale(
            clean_img,
            aspect_ratio=config.aspect_ratio,
            use_smart_face_centering=config.use_smart_face_centering,
        )

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
        )


        # Step 5: Synthesize Authentic Apple iPhone EXIF Profile
        w, h = final_img.size
        exif_bytes = ExifSpoofer.generate_exif(
            width=w,
            height=h,
            device=config.camera_preset,
            randomize_exposure=True,
        )

        return final_img, exif_bytes

    def process_file(
        self,
        input_path: str,
        output_path: str,
        config: Optional[ProcessingConfig] = None,
    ) -> str:
        """Processes an image file from disk and saves the optimized JPEG."""
        if config is None:
            config = ProcessingConfig.ofm_master()

        with Image.open(input_path) as src:
            processed_img, exif_bytes = self.process_pil(src, config)

        # Ensure target directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Save as optimized JPEG with injected iPhone EXIF
        # Subsampling 4:2:0 ('2') is standard for mobile camera JPEGs
        processed_img.save(
            output_path,
            format="JPEG",
            quality=config.jpeg_quality,
            subsampling=2,
            optimize=True,
            exif=exif_bytes,
        )

        return output_path

