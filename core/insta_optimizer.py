"""Instagram Optimizer & Pipeline Orchestrator.

Combines metadata removal, watermark disruption, smart face-centered cropping,
camera physics emulation, and authentic Apple iPhone EXIF injection into a unified
production pipeline.
"""

import io
import os
import secrets
from threading import Lock
from datetime import datetime
from dataclasses import dataclass, replace
from typing import Optional, Callable, Tuple
from PIL import Image
import piexif

from .c2pa_killer import clean_image_buffer
from .watermark_disruptor import disrupt_watermarks
from .camera_optics import CameraOptics
from .smart_cropper import SmartCropper, AspectRatio
from .exif_spoofer import ExifSpoofer, CameraPreset, MetadataMode
from .image_cache import NormalizedImageCache
from .photo_effects import PhotoEffects, GrainMode

TupleImageResult = Tuple[Image.Image, bytes]
MAX_IMAGE_PIXELS = 50_000_000  # 50 Megapixels safety limit
MAX_ORIGINAL_DIMENSION = 4096   # Maximum dimension cap for Original mode to guarantee safe RAM usage


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
    exposure_ev: float = 0.0
    temperature: float = 0.0
    tint: float = 0.0
    saturation: float = 1.0
    tone_contrast: float = 0.0
    black_lift: float = 0.0
    highlight_rolloff: float = 0.0
    bloom_strength: float = 0.0
    bloom_radius_px: float = 12.0
    bloom_threshold: float = 0.65
    grain_mode: GrainMode = GrainMode.SENSOR
    luma_grain_strength: float = 3.0
    chroma_grain_strength: float = 1.5
    grain_size_px: float = 1.0


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
        """Profile combining neutral microtexture, grain, and ISP local contrast/unsharp masking."""
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
    def soft_flash(cls) -> "ProcessingConfig":
        """Warm, muted direct-flash look with subtle predominantly luminance grain."""
        return cls(
            aspect_ratio=AspectRatio.FEED_4_5,
            metadata_mode=MetadataMode.MINIMAL,
            disrupt_strength=0,
            grain_strength=0,
            aberration_px=0.15,
            vignette_strength=0.025,
            enable_photonic_grade=False,
            enable_bayer_matrix=False,
            enable_isp_enhancement=False,
            exposure_ev=0.25,
            temperature=0.12,
            tint=0,
            saturation=0.84,
            tone_contrast=-0.08,
            black_lift=0.018,
            highlight_rolloff=0.4,
            bloom_strength=0.03,
            bloom_radius_px=14,
            bloom_threshold=0.68,
            grain_mode=GrainMode.FILM,
            luma_grain_strength=4,
            chroma_grain_strength=0.6,
            grain_size_px=1.1,
            jpeg_quality=94,
        )

    @classmethod
    def digicam_flash(cls) -> "ProcessingConfig":
        """Brighter direct-flash look with defined details and visible colored grain."""
        return cls(
            aspect_ratio=AspectRatio.FEED_4_5,
            metadata_mode=MetadataMode.MINIMAL,
            disrupt_strength=0,
            grain_strength=0,
            aberration_px=0.3,
            vignette_strength=0.025,
            enable_photonic_grade=False,
            enable_bayer_matrix=False,
            enable_isp_enhancement=True,
            sharpen_amount=0.18,
            exposure_ev=0.45,
            temperature=-0.04,
            tint=-0.03,
            saturation=0.92,
            tone_contrast=0.22,
            black_lift=0.004,
            highlight_rolloff=0.55,
            bloom_strength=0.06,
            bloom_radius_px=8,
            bloom_threshold=0.7,
            grain_mode=GrainMode.FILM,
            luma_grain_strength=7,
            chroma_grain_strength=18,
            grain_size_px=1.3,
            jpeg_quality=96,
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


@dataclass
class PreviewResult:
    before: Image.Image
    processed: Image.Image
    jpeg: Image.Image
    jpeg_size_bytes: int
    jpeg_quality: int


class InstaOptimizer:
    """End-to-end processor for transforming AI images into Instagram-ready camera captures."""

    def __init__(self):
        self.cropper = SmartCropper()
        self.source_cache = NormalizedImageCache()
        self._file_seeds = {}
        self._seed_lock = Lock()
        self._crop_lock = Lock()

    def config_for_file(self, input_path: str, config: ProcessingConfig) -> ProcessingConfig:
        """Use the same automatic seed for this file throughout the optimizer's lifetime."""
        if config.random_seed is not None:
            return replace(config)
        key = os.path.normcase(os.path.realpath(input_path))
        with self._seed_lock:
            if key not in self._file_seeds:
                self._file_seeds[key] = secrets.randbits(63)
            seed = self._file_seeds[key]
        return replace(config, random_seed=seed)

    @staticmethod
    def _normalize(image: Image.Image, config: ProcessingConfig) -> Image.Image:
        validate_image_dimensions(image)
        max_dim = MAX_ORIGINAL_DIMENSION if config.aspect_ratio == AspectRatio.ORIGINAL else None
        return clean_image_buffer(image, alpha_background=config.alpha_background, max_dimension=max_dim)

    def _load_normalized_file(self, input_path: str, config: ProcessingConfig) -> Image.Image:
        file_path = os.path.normcase(os.path.realpath(input_path))
        stat = os.stat(file_path)
        max_dim = MAX_ORIGINAL_DIMENSION if config.aspect_ratio == AspectRatio.ORIGINAL else None
        key = (file_path, stat.st_mtime_ns, stat.st_size, tuple(config.alpha_background), max_dim)
        cached = self.source_cache.get(key)
        if cached is not None:
            return cached
        with Image.open(file_path) as source:
            normalized = self._normalize(source, config)
        self.source_cache.put(key, normalized)
        return normalized

    def process_pil(
        self,
        image: Image.Image,
        config: ProcessingConfig,
    ) -> TupleImageResult:
        """Processes a PIL Image through the complete pipeline and returns (clean_image, exif_bytes)."""
        _, processed, exif = self._process_normalized(self._normalize(image, config), config)
        return processed, exif

    def _process_normalized(self, clean_img: Image.Image, config: ProcessingConfig):
        """Shared framing and effects path for previews, PIL callers, and file export."""
        normalized_size = clean_img.size

        # Step 2: Smart Face-Centered Cropping to Target Instagram Aspect Ratio (Memory Optimization)
        # Cropping and scaling first dramatically reduces memory footprint for downstream pixel operations
        if config.aspect_ratio == AspectRatio.ORIGINAL:
            # Preserve normalized dimensions (post-orientation transposition),
            # already safely capped at MAX_ORIGINAL_DIMENSION during early clean_image_buffer
            framed_img = clean_img
            target_size = normalized_size
        else:
            # OpenCV cascade instances are shared between preview and batch workers.
            with self._crop_lock:
                framed_img = self.cropper.crop_and_scale(
                    clean_img,
                    aspect_ratio=config.aspect_ratio,
                    use_smart_face_centering=config.use_smart_face_centering,
                )
            target_size = framed_img.size

        before_img = framed_img

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

        # Step 4: Color and tone before detail processing; grain is added last.
        if config.enable_photonic_grade:
            framed_img = CameraOptics.apply_photonic_grade(framed_img)
        graded_img = PhotoEffects.apply_grade(
            framed_img,
            exposure_ev=config.exposure_ev,
            temperature=config.temperature,
            tint=config.tint,
            saturation=config.saturation,
            tone_contrast=config.tone_contrast,
            black_lift=config.black_lift,
            highlight_rolloff=config.highlight_rolloff,
            bloom_strength=config.bloom_strength,
            bloom_radius_px=config.bloom_radius_px,
            bloom_threshold=config.bloom_threshold,
        )
        final_img = CameraOptics.apply_all(
            graded_img,
            iso=100,
            grain_strength=0,
            aberration_px=config.aberration_px,
            vignette_strength=config.vignette_strength,
            enable_photonic=False,
            enable_bayer_matrix=config.enable_bayer_matrix,
            bayer_strength=config.bayer_strength,
            enable_isp_enhancement=config.enable_isp_enhancement,
            sharpen_amount=config.sharpen_amount,
            seed=config.random_seed,
        )
        if GrainMode(config.grain_mode) == GrainMode.FILM:
            final_img = PhotoEffects.add_film_grain(
                final_img,
                luma_strength=config.luma_grain_strength,
                chroma_strength=config.chroma_grain_strength,
                size_px=config.grain_size_px,
                seed=config.random_seed,
            )
        else:
            final_img = CameraOptics.add_sensor_grain(
                final_img, iso=100, grain_strength=config.grain_strength, seed=config.random_seed,
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

        return before_img, final_img, exif_bytes

    @staticmethod
    def encode_jpeg(image: Image.Image, exif_bytes: bytes, quality: int) -> bytes:
        """The single JPEG encoder used by both preview and atomic file export."""
        buffer = io.BytesIO()
        kwargs = {"format": "JPEG", "quality": quality, "subsampling": 2, "optimize": True}
        if exif_bytes:
            kwargs["exif"] = exif_bytes
        image.save(buffer, **kwargs)
        return buffer.getvalue()

    def _render_file(self, input_path: str, config: ProcessingConfig):
        effective = self.config_for_file(input_path, config)
        before, processed, exif = self._process_normalized(
            self._load_normalized_file(input_path, effective), effective,
        )
        jpeg_bytes = self.encode_jpeg(processed, exif, effective.jpeg_quality)
        return before, processed, jpeg_bytes

    def process_preview_file(self, input_path: str, config: ProcessingConfig) -> PreviewResult:
        """Render at export resolution and decode the exact export JPEG for inspection."""
        before, processed, jpeg_bytes = self._render_file(input_path, config)
        with Image.open(io.BytesIO(jpeg_bytes)) as decoded:
            jpeg = decoded.convert("RGB")
        return PreviewResult(before, processed, jpeg, len(jpeg_bytes), config.jpeg_quality)

    def process_file(
        self,
        input_path: str,
        output_path: str,
        config: Optional[ProcessingConfig] = None,
    ) -> str:
        """Processes an image file from disk and saves the optimized JPEG atomically."""
        if config is None:
            config = ProcessingConfig.ofm_master()

        _, _, jpeg_bytes = self._render_file(input_path, config)

        # Ensure target directory exists
        target_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(target_dir, exist_ok=True)

        # Atomic write: save to a temporary file first, then replace
        base_name = os.path.basename(output_path)
        tmp_name = f".tmp_{os.getpid()}_{base_name}"
        tmp_path = os.path.join(target_dir, tmp_name)

        try:
            with open(tmp_path, "wb") as output:
                output.write(jpeg_bytes)
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


