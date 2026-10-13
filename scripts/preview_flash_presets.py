"""Reproduce the flash-preset examples with the application's actual JPEG pipeline."""

import argparse
import hashlib
import io
import json
import sys
from dataclasses import asdict, replace
from enum import Enum
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.insta_optimizer import InstaOptimizer, ProcessingConfig


def fresh_directory(requested: Path) -> Path:
    """Keep all previous runs and input assets intact, including on repeated runs."""
    requested.parent.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        candidate = requested if index == 1 else requested.with_name(f"{requested.name}-{index}")
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            index += 1


def _font(size: int):
    for path in ("C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _box(size, center, width=320, height=180):
    w, h = size
    width, height = min(width, w), min(height, h)
    left = max(0, min(w - width, round(w * center[0] - width / 2)))
    top = max(0, min(h - height, round(h * center[1] - height / 2)))
    return left, top, left + width, top + height


def comparison_sheet(images, labels, seed: int):
    """Fit views plus native pixel crops; no additional styling of the results."""
    sheet = Image.new("RGB", (1080, 950), (24, 25, 29))
    draw = ImageDraw.Draw(sheet)
    title_font, font = _font(22), _font(18)
    draw.text((20, 12), f"FLASH PRESETS | JPEG 4:2:0 | seed {seed}", fill="white", font=title_font)
    detail_box = _box(images[0].size, (0.51, 0.267))
    wall_box = _box(images[0].size, (0.16, 0.29), height=128)
    for column, (image, label) in enumerate(zip(images, labels)):
        x = column * 360 + 20
        draw.text((x, 54), label, fill="white", font=title_font)
        fit = image.copy()
        fit.thumbnail((320, 450), Image.Resampling.LANCZOS)
        sheet.paste(fit, (x + (320 - fit.width) // 2, 94 + (450 - fit.height) // 2))
        draw.text((x, 562), "Upper detail: 100%", fill="white", font=font)
        sheet.paste(image.crop(detail_box), (x, 593))
        draw.text((x, 790), "Left detail / grain: 100%", fill="white", font=font)
        sheet.paste(image.crop(wall_box), (x, 821))
    return sheet, {"upper_detail": detail_box, "left_detail": wall_box}


def _json_default(value):
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def render_examples(source: Path, requested_output: Path, seed: int = 1729) -> Path:
    source = source.resolve(strict=True)
    if seed < 0:
        raise ValueError("Seed must be non-negative")
    optimizer = InstaOptimizer()
    presets = (
        ("soft-flash", "Soft Flash", ProcessingConfig.soft_flash()),
        ("digicam-flash", "Digicam Flash", ProcessingConfig.digicam_flash()),
    )
    output = fresh_directory(requested_output.resolve())
    images, reports = [], {}
    before = None
    for name, label, preset in presets:
        config = replace(preset, random_seed=seed)
        preview = optimizer.process_preview_file(str(source), config)
        destination = output / f"{name}.jpg"
        optimizer.process_file(str(source), str(destination), config)
        with Image.open(destination) as saved:
            exported = saved.convert("RGB")
        if exported.tobytes() != preview.jpeg.tobytes() or destination.stat().st_size != preview.jpeg_size_bytes:
            raise RuntimeError(f"Preview/export mismatch for {label}")
        if before is None:
            before = preview.before
        elif before.tobytes() != preview.before.tobytes():
            raise RuntimeError("Presets used different input frames")
        images.append(exported)
        reports[name] = {
            "config": asdict(config), "size_px": exported.size,
            "size_bytes": destination.stat().st_size,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "preview_matches_export": True,
        }

    # The baseline uses the same cropped source and JPEG codec without any effects.
    baseline_bytes = optimizer.encode_jpeg(before, b"", quality=96)
    (output / "source-framed.jpg").write_bytes(baseline_bytes)
    with Image.open(io.BytesIO(baseline_bytes)) as decoded:
        baseline = decoded.convert("RGB")
    sheet, boxes = comparison_sheet([baseline, *images], ["Input", "Soft Flash", "Digicam Flash"], seed)
    sheet.save(output / "comparison.png")
    report = {
        "schema_version": 1,
        "source": source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else source.name,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "seed": seed, "jpeg_subsampling": "4:2:0",
        "detail_boxes_px": boxes, "presets": reports,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8",
    )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "examples/flash-presets/source.png")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "examples/flash-presets/results")
    parser.add_argument("--seed", type=int, default=1729)
    args = parser.parse_args()
    output = render_examples(args.input, args.output_dir, args.seed)
    print(f"Saved comparison and exact JPEG exports to: {output}")


if __name__ == "__main__":
    main()
