"""Batch Pipeline and Processing Queue Manager.

Manages batch queues, file discovery, progress callbacks, and metadata logging
for bulk-processing AI images into Instagram-ready posts.
"""

import os
import time
from dataclasses import dataclass
from typing import List, Callable, Optional, Dict, Any
from .insta_optimizer import InstaOptimizer, ProcessingConfig


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


@dataclass
class ProcessItemResult:
    input_path: str
    output_path: str
    success: bool
    error_message: Optional[str] = None
    input_size_bytes: int = 0
    output_size_bytes: int = 0
    duration_seconds: float = 0.0


class BatchPipeline:
    """Processes queues of images with progress reporting."""

    def __init__(self, optimizer: Optional[InstaOptimizer] = None):
        self.optimizer = optimizer or InstaOptimizer()

    @staticmethod
    def find_images_in_dir(dir_path: str, recursive: bool = False) -> List[str]:
        """Finds all supported image files in a directory."""
        images = []
        if not os.path.exists(dir_path):
            return images

        if recursive:
            for root, _, files in os.walk(dir_path):
                for f in files:
                    if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS:
                        images.append(os.path.join(root, f))
        else:
            for f in os.listdir(dir_path):
                full_path = os.path.join(dir_path, f)
                if os.path.isfile(full_path) and os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS:
                    images.append(full_path)

        return sorted(images)

    def process_batch(
        self,
        input_paths: List[str],
        output_dir: str,
        config: Optional[ProcessingConfig] = None,
        progress_callback: Optional[Callable[[int, int, str, bool], None]] = None,
    ) -> List[ProcessItemResult]:
        """Processes a list of files into the target output directory."""
        if config is None:
            config = ProcessingConfig.ofm_master()

        os.makedirs(output_dir, exist_ok=True)
        results = []
        total = len(input_paths)

        for idx, input_path in enumerate(input_paths, start=1):
            file_name = os.path.basename(input_path)
            base_name, _ = os.path.splitext(file_name)
            output_file_name = f"{base_name}_insta.jpg"
            output_path = os.path.join(output_dir, output_file_name)

            start_t = time.perf_counter()
            in_size = os.path.getsize(input_path) if os.path.exists(input_path) else 0

            try:
                self.optimizer.process_file(input_path, output_path, config)
                out_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
                dur = time.perf_counter() - start_t

                item_res = ProcessItemResult(
                    input_path=input_path,
                    output_path=output_path,
                    success=True,
                    input_size_bytes=in_size,
                    output_size_bytes=out_size,
                    duration_seconds=dur,
                )
                results.append(item_res)
                if progress_callback:
                    progress_callback(idx, total, file_name, True)

            except Exception as e:
                dur = time.perf_counter() - start_t
                item_res = ProcessItemResult(
                    input_path=input_path,
                    output_path=output_path,
                    success=False,
                    error_message=str(e),
                    input_size_bytes=in_size,
                    duration_seconds=dur,
                )
                results.append(item_res)
                if progress_callback:
                    progress_callback(idx, total, file_name, False)

        return results
