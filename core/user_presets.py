"""Versioned user recipes, stored outside the installation with atomic writes."""

import json
import math
import os
import tempfile
import unicodedata
from dataclasses import fields, replace
from pathlib import Path

from .exif_spoofer import CameraPreset, MetadataMode
from .insta_optimizer import ProcessingConfig
from .photo_effects import GrainMode
from .smart_cropper import AspectRatio

SCHEMA_VERSION = 1
MAX_PRESETS = 100
_SESSION_FIELDS = {"random_seed", "capture_time", "overwrite_existing"}
_ENUM_FIELDS = {
    "aspect_ratio": AspectRatio, "camera_preset": CameraPreset,
    "metadata_mode": MetadataMode, "grain_mode": GrainMode,
}
_BOOL_FIELDS = {
    "enable_photonic_grade", "use_smart_face_centering",
    "enable_bayer_matrix", "enable_isp_enhancement",
}
_BOUNDS = {
    "disrupt_strength": (0, 2), "grain_strength": (0, 2),
    "aberration_px": (0, 2), "vignette_strength": (0, 0.06),
    "bayer_strength": (0, 2), "sharpen_amount": (0, 2),
    "exposure_ev": (-3, 3), "temperature": (-1, 1), "tint": (-1, 1),
    "saturation": (0, 2), "tone_contrast": (-1, 1), "black_lift": (0, 0.15),
    "highlight_rolloff": (0, 1), "bloom_strength": (0, 1),
    "bloom_radius_px": (1, 60), "bloom_threshold": (0.05, 0.95),
    "luma_grain_strength": (0, 12), "chroma_grain_strength": (0, 24),
    "grain_size_px": (1, 4),
}
_RECIPE_FIELDS = {f.name for f in fields(ProcessingConfig)} - _SESSION_FIELDS


class PresetStoreError(ValueError):
    """A human-readable error; failed reads must never be replaced with an empty file."""


def recipe_config(config: ProcessingConfig) -> ProcessingConfig:
    """A style does not freeze file seeds, capture dates or overwrite permission."""
    return replace(config, random_seed=None, capture_time=None, overwrite_existing=False)


def validate_name(name: str) -> str:
    if not isinstance(name, str):
        raise PresetStoreError("Название пресета должно быть текстом.")
    name = unicodedata.normalize("NFC", name.strip())
    if not 1 <= len(name) <= 60 or any(unicodedata.category(c).startswith("C") for c in name):
        raise PresetStoreError("Название: от 1 до 60 символов, без переносов строк и управляющих символов.")
    return name


def config_from_data(data: dict) -> ProcessingConfig:
    if not isinstance(data, dict) or set(data) - _RECIPE_FIELDS:
        raise PresetStoreError("В пресете есть неизвестные поля настроек.")
    values = {}
    for name, value in data.items():
        if name in _ENUM_FIELDS:
            try:
                values[name] = _ENUM_FIELDS[name][value]
            except (KeyError, TypeError):
                raise PresetStoreError(f"Неверное значение настройки {name}.") from None
        elif name in _BOOL_FIELDS:
            if type(value) is not bool:
                raise PresetStoreError(f"Настройка {name} должна быть логическим значением.")
            values[name] = value
        elif name in _BOUNDS:
            lower, upper = _BOUNDS[name]
            if type(value) not in (int, float) or not lower <= value <= upper or not math.isfinite(value):
                raise PresetStoreError(f"Настройка {name}: допустимо от {lower} до {upper}.")
            values[name] = value
        elif name == "jpeg_quality":
            if type(value) is not int or not 1 <= value <= 100:
                raise PresetStoreError("Качество JPEG: целое число от 1 до 100.")
            values[name] = value
        elif name == "alpha_background":
            if (not isinstance(value, (list, tuple)) or len(value) != 3
                    or any(type(v) is not int or not 0 <= v <= 255 for v in value)):
                raise PresetStoreError("Фон прозрачности должен содержать три RGB-значения от 0 до 255.")
            values[name] = tuple(value)
    return ProcessingConfig(**values)


def config_to_data(config: ProcessingConfig) -> dict:
    data = {}
    for name in sorted(_RECIPE_FIELDS):
        value = getattr(config, name)
        if name in _ENUM_FIELDS and not isinstance(value, _ENUM_FIELDS[name]):
            raise PresetStoreError(f"Неверное значение настройки {name}.")
        data[name] = value.name if name in _ENUM_FIELDS else value
    config_from_data(data)  # Validate before touching the on-disk store.
    return data


class PresetStore:
    def __init__(self, path=None):
        app_data = Path(os.environ.get("APPDATA") or (Path.home() / ".config"))
        self.path = Path(path) if path is not None else app_data / "Reelsator" / "presets.json"

    def read(self) -> dict:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except (OSError, UnicodeError) as exc:
            raise PresetStoreError(f"Не удалось прочитать пресеты: {exc}") from exc
        try:
            document = json.loads(text)
            if (not isinstance(document, dict) or type(document.get("version")) is not int
                    or document["version"] != SCHEMA_VERSION):
                raise PresetStoreError("Версия файла пресетов не поддерживается.")
            records = document.get("presets")
            if not isinstance(records, list) or len(records) > MAX_PRESETS:
                raise PresetStoreError(f"Файл должен содержать не более {MAX_PRESETS} пресетов.")
            presets, names = {}, set()
            for record in records:
                if not isinstance(record, dict) or set(record) != {"name", "config"}:
                    raise PresetStoreError("Неверная структура записи пресета.")
                name = validate_name(record["name"])
                if name.casefold() in names:
                    raise PresetStoreError("В файле есть повторяющиеся названия пресетов.")
                names.add(name.casefold())
                presets[name] = config_from_data(record["config"])
            return presets
        except ValueError as exc:
            raise PresetStoreError(f"Не удалось загрузить {self.path.name}: {exc}") from exc

    def _write(self, presets: dict) -> None:
        document = {
            "version": SCHEMA_VERSION,
            "presets": [{"name": name, "config": config_to_data(config)} for name, config in presets.items()],
        }
        payload = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, prefix=".presets-", suffix=".tmp", delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            raise PresetStoreError(f"Не удалось сохранить пресеты: {exc}") from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def save(self, name: str, config: ProcessingConfig, *, overwrite=False) -> str:
        name = validate_name(name)
        data = config_to_data(config)
        presets = self.read()  # Re-read: retain changes saved by another application instance.
        existing = next((n for n in presets if n.casefold() == name.casefold()), None)
        if existing is not None:
            if not overwrite:
                raise PresetStoreError("Такой пресет уже есть. Выберите другое название или нажмите «Обновить».")
            name = existing
        elif len(presets) >= MAX_PRESETS:
            raise PresetStoreError(f"Можно сохранить не более {MAX_PRESETS} пресетов.")
        presets[name] = config_from_data(data)
        self._write(presets)
        return name

    def delete(self, name: str) -> None:
        name = validate_name(name)
        presets = self.read()
        existing = next((n for n in presets if n.casefold() == name.casefold()), None)
        if existing is None:
            raise PresetStoreError("Этот пресет уже удалён.")
        del presets[existing]
        self._write(presets)
