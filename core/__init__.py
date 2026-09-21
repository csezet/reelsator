"""Core processing modules for Reelsator - Instagram AI Photo Cleaner & Optimizer."""

from .c2pa_killer import strip_all_metadata, clean_image_buffer
from .watermark_disruptor import disrupt_watermarks
from .camera_optics import CameraOptics
from .smart_cropper import SmartCropper
from .exif_spoofer import ExifSpoofer, CameraPreset
from .insta_optimizer import InstaOptimizer, ProcessingConfig

__all__ = [
    "strip_all_metadata",
    "clean_image_buffer",
    "disrupt_watermarks",
    "CameraOptics",
    "SmartCropper",
    "ExifSpoofer",
    "CameraPreset",
    "InstaOptimizer",
    "ProcessingConfig",
]
