"""C2PA & Metadata Annihilator.

Provides byte-level and container-level stripping of:
- C2PA manifests (JUMBF in JPEG APP11 and PNG c2pa chunk)
- IPTC / XMP AI provenance tags (DigitalSourceType=trainedAlgorithmicMedia)
- EXIF, Photoshop IRB, ICC metadata tags
- Prompt metadata blocks from ChatGPT, Stable Diffusion, ComfyUI, Midjourney
"""

import io
import struct
from typing import Tuple
from PIL import Image
import numpy as np

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


def clean_image_buffer(image: Image.Image) -> Image.Image:
    """Creates a completely fresh PIL Image from raw pixel data, discarding all container metadata.

    This ensures no residual prompts, C2PA blocks, XMP, or hidden headers persist in memory.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    raw_array = np.array(image, dtype=np.uint8, copy=True)
    clean_img = Image.fromarray(raw_array)
    clean_img.info.clear()
    return clean_img


def strip_all_metadata(file_bytes: bytes, file_ext: str = ".jpg") -> bytes:
    """Strips metadata at binary level according to file extension."""
    ext = file_ext.lower().replace(".", "")
    if ext in ("jpg", "jpeg"):
        return strip_jpeg_metadata(file_bytes)
    elif ext == "png":
        return strip_png_metadata(file_bytes)
    return file_bytes
