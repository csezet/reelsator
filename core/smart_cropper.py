"""Smart Instagram Cropper & Framing Engine.

Intelligently frames and crops images for Instagram specifications:
- 4:5 Portrait Feed (1080 × 1350 px) [Optimal Instagram Feed]
- 1:1 Square Feed (1080 × 1080 px)
- 9:16 Stories & Reels (1080 × 1920 px)
- Original (Downscales cleanly to max 1080 px width if necessary)

Uses OpenCV Face Detection to position faces naturally according to the Rule of Thirds.
"""

import os
from enum import Enum
from typing import Tuple, Optional
from PIL import Image
import numpy as np
import cv2


class AspectRatio(str, Enum):
    FEED_4_5 = "4:5 (1080x1350)"
    SQUARE_1_1 = "1:1 (1080x1080)"
    STORY_9_16 = "9:16 (1080x1920)"
    ORIGINAL = "Original"


TARGET_DIMENSIONS = {
    AspectRatio.FEED_4_5: (1080, 1350),
    AspectRatio.SQUARE_1_1: (1080, 1080),
    AspectRatio.STORY_9_16: (1080, 1920),
}


class SmartCropper:
    """Detects subjects and performs golden-ratio framing for Instagram."""

    def __init__(self):
        # Locate OpenCV cascade files
        cascade_dir = cv2.data.haarcascades
        self.frontal_cascade_path = os.path.join(cascade_dir, "haarcascade_frontalface_default.xml")
        self.profile_cascade_path = os.path.join(cascade_dir, "haarcascade_profileface.xml")

        self.frontal_face_cascade = cv2.CascadeClassifier(self.frontal_cascade_path) if os.path.exists(self.frontal_cascade_path) else None
        self.profile_face_cascade = cv2.CascadeClassifier(self.profile_cascade_path) if os.path.exists(self.profile_cascade_path) else None

    def detect_face(self, image: Image.Image) -> Optional[Tuple[int, int, int, int]]:
        """Detects the primary face in the image and returns (x, y, w, h).

        Returns None if no face is detected.
        """
        cv_img = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

        faces = []
        if self.frontal_face_cascade and not self.frontal_face_cascade.empty():
            faces = self.frontal_face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
            )

        if len(faces) == 0 and self.profile_face_cascade and not self.profile_face_cascade.empty():
            faces = self.profile_face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
            )

        if len(faces) == 0:
            return None

        # Return the largest face by area (primary subject)
        primary_face = max(faces, key=lambda b: b[2] * b[3])
        return tuple(primary_face)

    def crop_and_scale(
        self,
        image: Image.Image,
        aspect_ratio: AspectRatio = AspectRatio.FEED_4_5,
        use_smart_face_centering: bool = True,
    ) -> Image.Image:
        """Crops and rescales the image to the specified Instagram target format."""
        if aspect_ratio == AspectRatio.ORIGINAL:
            # Scale proportionally so width does not exceed 1080 px or height 1350 px
            w, h = image.size
            if w > 1080:
                new_h = int(round(h * (1080 / w)))
                return image.resize((1080, new_h), resample=Image.LANCZOS)
            return image

        target_w, target_h = TARGET_DIMENSIONS[aspect_ratio]
        target_ratio = target_w / target_h

        img_w, img_h = image.size
        img_ratio = img_w / img_h

        # Find face if smart centering is requested
        face = self.detect_face(image) if use_smart_face_centering else None

        if abs(img_ratio - target_ratio) < 0.005:
            # Aspect ratio already matches
            crop_box = (0, 0, img_w, img_h)
        elif img_ratio > target_ratio:
            # Image is wider than target -> crop horizontally (left/right)
            crop_w = int(round(img_h * target_ratio))
            crop_h = img_h

            if face is not None:
                fx, fy, fw, fh = face
                face_center_x = fx + (fw / 2.0)
                # Center crop around face
                left = int(round(face_center_x - (crop_w / 2.0)))
                left = max(0, min(img_w - crop_w, left))
            else:
                left = (img_w - crop_w) // 2

            crop_box = (left, 0, left + crop_w, crop_h)
        else:
            # Image is taller than target -> crop vertically (top/bottom)
            crop_w = img_w
            crop_h = int(round(img_w / target_ratio))

            if face is not None:
                fx, fy, fw, fh = face
                # Position face at roughly 30% from the top of the crop (golden ratio)
                desired_top = int(round(fy - (crop_h * 0.28)))
                top = max(0, min(img_h - crop_h, desired_top))
            else:
                # Default portrait framing: slightly favor top (40% top / 60% bottom)
                top = int(round((img_h - crop_h) * 0.40))

            crop_box = (0, top, crop_w, top + crop_h)

        cropped = image.crop(crop_box)
        resized = cropped.resize((target_w, target_h), resample=Image.LANCZOS)
        return resized
