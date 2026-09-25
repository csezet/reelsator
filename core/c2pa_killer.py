"""C2PA & Metadata Annihilator.

Provides byte-level and container-level stripping of:
- C2PA manifests (JUMBF in JPEG APP11 and PNG c2pa chunk)
- IPTC / XMP AI provenance tags (DigitalSourceType=trainedAlgorithmicMedia)
- EXIF, Photoshop IRB, ICC metadata tags
- Prompt metadata blocks from ChatGPT, Stable Diffusion, ComfyUI, Midjourney
"""

import io
import struct
import logging
from typing import Tuple, Optional
from PIL import Image, ImageOps, ImageCms
import numpy as np

logger = logging.getLogger(__name__)

# JPEG markers
SOI = b"\xff\xd8"
EOI = b"\xff\xd9"
SOS = 0xDA
APP0 = 0xE0
COM = 0xFE

# PNG Signature
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DISALLOWED_PNG_CHUNKS = {
    b"c2pa",
    b"caBX",  # C2PA Manifest Store box in PNG
    b"caFS",  # C2PA Fragment Store
    b"caMA",  # C2PA Manifest Assertion
    b"tEXt",
    b"zTXt",
    b"iTXt",
    b"eXIf",
    b"dSIG",
    b"prOm",
    b"XML:",
    b"iCCP",
}


def convert_icc_to_srgb(image: Image.Image) -> Image.Image:
    """Converts image from its embedded ICC color space (e.g. Display-P3, AdobeRGB) to standard sRGB.

    If no ICC profile is present, returns image unchanged.
    Safely falls back if the ICC profile is invalid or corrupted.
    """
    # If palette image with transparency, promote to RGBA first to preserve alpha during color conversion
    if image.mode == "P" and "transparency" in image.info:
        image = image.convert("RGBA")

    icc = image.info.get("icc_profile")
    if not icc:
        return image
    try:
        src_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        dst_profile = ImageCms.createProfile("sRGB")
        mode = "RGBA" if "A" in image.getbands() else "RGB"
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert(mode)
        converted = ImageCms.profileToProfile(image, src_profile, dst_profile, outputMode=mode)
        return converted
    except Exception as e:
        logger.warning("Failed to transform ICC profile to sRGB (%s). Falling back.", e)
        return image


def flatten_alpha_channel(image: Image.Image, background: Tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """Composites transparent image over a solid background color (default: white) to prevent black artifacts in JPEG."""
    # Palette image with transparency chunk (tRNS)
    if image.mode == "P" and "transparency" in image.info:
        image = image.convert("RGBA")

    if "A" not in image.getbands():
        return image.convert("RGB") if image.mode != "RGB" else image
    rgba = image.convert("RGBA")
    bg = Image.new("RGBA", rgba.size, (*background, 255))
    return Image.alpha_composite(bg, rgba).convert("RGB")


def iter_jpeg_segments(data: bytes):
    """Yield (offset, marker_byte, body_bytes) for each segment in a JPEG."""
    if not data.startswith(SOI):
        return
    pos = 2
    n = len(data)
    while pos < n:
        if data[pos] != 0xFF:
            break
        # Skip padding 0xFFs
        while pos < n and data[pos] == 0xFF:
            pos += 1
        if pos >= n:
            break
        marker = data[pos]
        pos += 1

        # Standalone markers without payload
        if marker in (0xD8, 0xD9, 0x00) or (0xD0 <= marker <= 0xD7):
            yield (pos - 2, marker, b"")
            continue

        if marker == SOS:
            # Start of Scan: read SOS header length, then entropy data follows
            if pos + 2 > n:
                break
            length = struct.unpack(">H", data[pos : pos + 2])[0]
            body = data[pos + 2 : pos + length]
            yield (pos - 2, marker, body)
            break

        if pos + 2 > n:
            break
        length = struct.unpack(">H", data[pos : pos + 2])[0]
        if length < 2 or pos + length > n:
            break
        body = data[pos + 2 : pos + length]
        yield (pos - 2, marker, body)
        pos += length


def strip_jpeg_metadata(data: bytes) -> bytes:
    """Byte-level JPEG scrubber: keeps JFIF (APP0), DQT, DHT, SOF, SOS, drops APP1..APP15 & COM."""
    if not data.startswith(SOI):
        return data

    out = io.BytesIO()
    out.write(SOI)
    sos_offset = None

    for off, marker, body in iter_jpeg_segments(data):
        if marker == SOS:
            sos_offset = off
            out.write(bytes([0xFF, marker]))
            out.write(struct.pack(">H", len(body) + 2))
            out.write(body)
            break

        # Drop COM (0xFE) and APP1..APP15 (0xE1..0xEF)
        if marker == COM or (0xE1 <= marker <= 0xEF):
            continue

        # Keep APP0 (JFIF basic) and other structural markers
        out.write(bytes([0xFF, marker]))
        if body:
            out.write(struct.pack(">H", len(body) + 2))
            out.write(body)

    if sos_offset is None:
        return data

    # Copy scan entropy data up to last EOI
    scan_start = None
    for off, marker, body in iter_jpeg_segments(data):
        if marker == SOS:
            scan_start = off + 2 + 2 + len(body)
            break

    if scan_start is None:
        return data

    eoi = data.rfind(EOI)
    if eoi == -1:
        return data

    out.write(data[scan_start:eoi])
    out.write(EOI)
    return out.getvalue()


def strip_png_metadata(data: bytes) -> bytes:
    """Byte-level PNG scrubber: removes text chunks, EXIF chunk, c2pa manifests, and signatures."""
    if not data.startswith(PNG_SIGNATURE):
        return data

    out = io.BytesIO()
    out.write(PNG_SIGNATURE)
    pos = len(PNG_SIGNATURE)
    n = len(data)

    while pos + 8 <= n:
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        total_chunk_len = 12 + length

        if pos + total_chunk_len > n:
            break

        if chunk_type not in DISALLOWED_PNG_CHUNKS:
            out.write(data[pos : pos + total_chunk_len])

        pos += total_chunk_len
        if chunk_type == b"IEND":
            break

    return out.getvalue()


def clean_image_buffer(
    image: Image.Image,
    alpha_background: Tuple[int, int, int] = (255, 255, 255),
    max_dimension: Optional[int] = None,
) -> Image.Image:
    """Normalizes orientation, color profile, alpha channel, and extracts raw pixel buffer.

    Discards all container metadata, C2PA blocks, XMP, IPTC, and generative prompts.
    If max_dimension is specified and any dimension exceeds it, performs early Lanczos downscaling
    immediately after EXIF transposition to prevent excess RAM usage during ICC conversion,
    alpha compositing, and full-resolution numpy array allocation.
    """
    # 0. Promote palette image with transparency early so operations retain alpha
    if image.mode == "P" and "transparency" in image.info:
        image = image.convert("RGBA")

    # 1. Normalize physical orientation based on EXIF tag before stripping
    try:
        image = ImageOps.exif_transpose(image)
    except Exception as e:
        logger.debug("exif_transpose skipped: %s", e)

    # 1b. Early downscaling if max_dimension is set
    if max_dimension is not None and max(image.size) > max_dimension:
        w, h = image.size
        scale = max_dimension / max(w, h)
        target_size = (int(round(w * scale)), int(round(h * scale)))
        image = image.resize(target_size, Image.LANCZOS)

    # 2. Color management: convert embedded color profile (e.g. Display-P3) to sRGB
    image = convert_icc_to_srgb(image)

    # 3. Alpha compositing to avoid black background artifacts in JPEG
    image = flatten_alpha_channel(image, background=alpha_background)

    # 4. Extract raw uncompressed pixel buffer into pure fresh array
    raw_array = np.array(image, dtype=np.uint8, copy=True)
    clean_img = Image.fromarray(raw_array)
    clean_img.info.clear()
    return clean_img


def strip_all_metadata(file_bytes: bytes, file_ext: str = ".jpg") -> bytes:
    """Strips metadata at binary container level using magic bytes inspection with file extension fallback."""
    if file_bytes.startswith(SOI):
        return strip_jpeg_metadata(file_bytes)
    elif file_bytes.startswith(PNG_SIGNATURE):
        return strip_png_metadata(file_bytes)

    # Fallback to extension if magic bytes did not match
    ext = file_ext.lower().replace(".", "")
    if ext in ("jpg", "jpeg"):
        return strip_jpeg_metadata(file_bytes)
    elif ext == "png":
        return strip_png_metadata(file_bytes)
    return file_bytes

