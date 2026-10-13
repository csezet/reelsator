"""Photographic color, tone, highlight glow, and independently controlled grain."""

import math
from enum import Enum
from typing import Optional

import cv2
import numpy as np
from PIL import Image


class GrainMode(str, Enum):
    SENSOR = "sensor"
    FILM = "film"


_LUMA = np.array((0.2126, 0.7152, 0.0722), dtype=np.float32)
_CHROMA_1 = np.array((_LUMA[1], -_LUMA[0], 0), dtype=np.float32)
_CHROMA_1 /= np.linalg.norm(_CHROMA_1)
_CHROMA_2 = np.cross(_LUMA, _CHROMA_1)
_CHROMA_2 /= np.linalg.norm(_CHROMA_2)


def _validate(name: str, value: float, lower: float, upper: float) -> None:
    if not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError(f"{name}: допустимо значение от {lower} до {upper}")


def _linearize(rgb: np.ndarray) -> np.ndarray:
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def _encode_srgb(linear: np.ndarray) -> np.ndarray:
    linear = np.maximum(linear, 0)
    return np.where(linear <= 0.0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - 0.055)


class PhotoEffects:
    """Works on normalized RGB images at their final export resolution."""

    @staticmethod
    def apply_grade(
        image: Image.Image,
        *,
        exposure_ev: float = 0,
        temperature: float = 0,
        tint: float = 0,
        saturation: float = 1,
        tone_contrast: float = 0,
        black_lift: float = 0,
        highlight_rolloff: float = 0,
        bloom_strength: float = 0,
        bloom_radius_px: float = 12,
        bloom_threshold: float = 0.65,
    ) -> Image.Image:
        """Apply exposure/WB in linear light, then tone/color and highlight-only glow.

        Temperature and tint are relative artistic controls, not Kelvin values.
        All calculations stay in float32 until a single rounded 8-bit conversion.
        """
        for name, value, lower, upper in (
            ("Экспозиция (EV)", exposure_ev, -3, 3),
            ("Температура", temperature, -1, 1),
            ("Оттенок", tint, -1, 1),
            ("Насыщенность", saturation, 0, 2),
            ("Контраст кривой", tone_contrast, -1, 1),
            ("Подъём чёрного", black_lift, 0, 0.15),
            ("Смягчение светов", highlight_rolloff, 0, 1),
            ("Свечение", bloom_strength, 0, 1),
            ("Радиус свечения (px)", bloom_radius_px, 1, 60),
            ("Порог свечения", bloom_threshold, 0.05, 0.95),
        ):
            _validate(name, value, lower, upper)
        if image.mode != "RGB":
            raise ValueError("Обработка цвета требует нормализованного RGB-изображения")
        if (
            exposure_ev == temperature == tint == tone_contrast == black_lift == 0
            and saturation == 1 and highlight_rolloff == bloom_strength == 0
        ):
            return image

        rgb = np.asarray(image, dtype=np.float32) / np.float32(255)
        linear = _linearize(rgb)
        linear *= np.float32(2 ** exposure_ev)

        if temperature != 0 or tint != 0:
            gains = np.array((
                2 ** (0.25 * temperature + 0.075 * tint),
                2 ** (-0.15 * tint),
                2 ** (-0.25 * temperature + 0.075 * tint),
            ), dtype=np.float32)
            gains /= np.dot(gains, _LUMA)
            linear *= gains

        if highlight_rolloff > 0:
            # A smooth shoulder starts at 0.6 in linear light, including values
            # above 1 created by exposure. At full strength it approaches white.
            excess = np.maximum(linear - np.float32(0.6), 0)
            compressed = np.float32(0.6) + excess / (1 + excess / np.float32(0.4))
            linear += (compressed - linear) * (excess > 0) * np.float32(highlight_rolloff)

        rgb = np.clip(_encode_srgb(linear), 0, 1)
        if saturation != 1:
            luminance = np.sum(rgb * _LUMA, axis=2, keepdims=True)
            rgb = np.clip(luminance + (rgb - luminance) * np.float32(saturation), 0, 1)
        if tone_contrast != 0:
            smooth = rgb * rgb * (3 - 2 * rgb)
            rgb += np.float32(tone_contrast) * (smooth - rgb)
        if black_lift > 0:
            rgb = np.float32(black_lift) + rgb * np.float32(1 - black_lift)

        if bloom_strength > 0:
            linear = _linearize(rgb)
            luminance = np.sum(linear * _LUMA, axis=2, keepdims=True)
            mask = np.clip((luminance - bloom_threshold) / (1 - bloom_threshold), 0, 1)
            mask = mask * mask * (3 - 2 * mask)
            glow = cv2.GaussianBlur(
                linear * mask, (0, 0), sigmaX=bloom_radius_px, sigmaY=bloom_radius_px,
                borderType=cv2.BORDER_REFLECT_101,
            )
            # Available headroom keeps white pixels from becoming brighter while
            # allowing soft light to spread to adjacent, darker pixels.
            linear += glow * np.float32(bloom_strength) * (1 - linear)
            rgb = _encode_srgb(linear)

        return Image.fromarray(np.rint(np.clip(rgb, 0, 1) * 255).astype(np.uint8))

    @staticmethod
    def _noise_field(h: int, w: int, size_px: float, seed) -> np.ndarray:
        shape = (max(1, math.ceil(h / size_px)), max(1, math.ceil(w / size_px)))
        field = np.random.default_rng(seed).standard_normal(shape, dtype=np.float32)
        if shape != (h, w):
            field = cv2.resize(field, (w, h), interpolation=cv2.INTER_LINEAR)
        field -= field.mean()
        deviation = field.std()
        if deviation > 1e-6:
            field /= deviation
        return field

    @classmethod
    def add_film_grain(
        cls,
        image: Image.Image,
        *,
        luma_strength: float = 3,
        chroma_strength: float = 1.5,
        size_px: float = 1,
        seed: Optional[int] = None,
    ) -> Image.Image:
        """Add luminance and zero-luminance chroma noise at final pixel scale.

        Independent random streams keep one component's pattern unchanged when
        the other component is enabled or its intensity is edited.
        """
        _validate("Яркостное зерно", luma_strength, 0, 12)
        _validate("Цветное зерно", chroma_strength, 0, 24)
        _validate("Размер зерна (px)", size_px, 1, 4)
        if image.mode != "RGB":
            raise ValueError("Зерно требует нормализованного RGB-изображения")
        if luma_strength == chroma_strength == 0:
            return image

        arr = np.asarray(image, dtype=np.float32)
        h, w, _ = arr.shape
        luminance = np.clip(np.sum(arr * _LUMA, axis=2) / np.float32(255), 0, 1)
        mask = np.float32(0.35) + np.float32(0.65) * (1 - luminance) ** np.float32(0.75)
        streams = np.random.SeedSequence(seed).spawn(3)
        noise = np.zeros_like(arr)
        if luma_strength > 0:
            field = cls._noise_field(h, w, size_px, streams[0])
            noise += (field * mask * np.float32(luma_strength))[:, :, None]
        if chroma_strength > 0:
            for stream, basis in zip(streams[1:], (_CHROMA_1, _CHROMA_2)):
                field = cls._noise_field(h, w, size_px, stream)
                noise += (field * mask * np.float32(chroma_strength))[:, :, None] * basis
        return Image.fromarray(np.rint(np.clip(arr + noise, 0, 255)).astype(np.uint8))
