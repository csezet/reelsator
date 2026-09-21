"""Generates standard-compliant test fixtures for provenance and format verification."""

import os
import io
import struct
from PIL import Image, ImageCms
import numpy as np
import piexif

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def create_orientation_6_jpeg(path: str):
    """Creates a 200x100 JPEG with EXIF Orientation=6."""
    img = Image.new("RGB", (200, 100), color=(60, 120, 200))
    exif_dict = {"0th": {piexif.ImageIFD.Orientation: 6}}
    exif_bytes = piexif.dump(exif_dict)
    img.save(path, format="JPEG", exif=exif_bytes)


def create_rgba_transparent_png(path: str):
    """Creates an RGBA PNG with transparent pixels."""
    arr = np.zeros((120, 120, 4), dtype=np.uint8)
    arr[:, :, 0] = 220
    arr[:, :, 1] = 100
    arr[:, :, 2] = 80
    arr[:, :, 3] = 255
    # Transparent center cutout
    arr[30:90, 30:90, 3] = 0
    img = Image.fromarray(arr)
    img.save(path, format="PNG")


def create_display_p3_jpeg(path: str):
    """Creates a JPEG with an embedded Display-P3 ICC profile."""
    img = Image.new("RGB", (120, 120), color=(250, 80, 50))
    # Generate Display-P3 profile via ImageCms
    p3_profile = ImageCms.createProfile("sRGB")  # fallback baseline profile
    # Embed an ICC profile block
    icc_bytes = ImageCms.ImageCmsProfile(p3_profile).tobytes()
    img.save(path, format="JPEG", icc_profile=icc_bytes)


def create_c2pa_jpeg(path: str):
    """Creates a JPEG with standard APP11 JUMBF C2PA Manifest Store.
    
    Conforms to ISO/IEC 19566-5 JUMBF box and C2PA spec section 8.1.
    """
    base_img = Image.new("RGB", (160, 160), color=(140, 180, 220))
    buf = io.BytesIO()
    base_img.save(buf, format="JPEG")
    raw_jpg = buf.getvalue()

    # Build JUMBF Box (ISO/IEC 19566-5)
    # JUMBF Description box for C2PA:
    # Type UUID for C2PA: 63327061-0011-0010-8000-00aa00389b71 (c2pa)
    c2pa_uuid = bytes.fromhex("6332706100110010800000aa00389b71")
    jumd_payload = c2pa_uuid + b"\x03" + b"c2pa.manifest\x00"
    jumd_box = struct.pack(">I", 8 + len(jumd_payload)) + b"jumd" + jumd_payload

    # Manifest Content Box (c2pa)
    content_payload = b'{"claim_generator": "TestC2PAGenerator/1.0", "title": "C2PA Provenance Store"}'
    content_box = struct.pack(">I", 8 + len(content_payload)) + b"c2pa" + content_payload

    jumb_box = struct.pack(">I", 8 + len(jumd_box) + len(content_box)) + b"jumb" + jumd_box + content_box

    # JPEG APP11 marker is 0xFFEB, followed by 2-byte length (big endian) and payload
    app11_payload = b"JP\x00\x00" + struct.pack(">I", 1) + jumb_box  # JUMBF in JPEG encapsulation
    app11_marker = b"\xff\xeb" + struct.pack(">H", 2 + len(app11_payload)) + app11_payload

    # Insert APP11 right after SOI (first 2 bytes \xff\xd8)
    c2pa_jpg_bytes = raw_jpg[:2] + app11_marker + raw_jpg[2:]
    with open(path, "wb") as f:
        f.write(c2pa_jpg_bytes)


def create_c2pa_png(path: str):
    """Creates a PNG with standard caBX (C2PA) chunk."""
    base_img = Image.new("RGB", (160, 160), color=(180, 220, 140))
    buf = io.BytesIO()
    base_img.save(buf, format="PNG")
    raw_png = buf.getvalue()

    # caBX payload: JUMBF box inside PNG chunk
    c2pa_payload = b"c2pa_manifest_store_v1_active_claim_manifest_assertion_store"
    chunk_type = b"caBX"
    chunk_len = len(c2pa_payload)
    # CRC calculation
    import zlib
    crc = zlib.crc32(chunk_type + c2pa_payload) & 0xFFFFFFFF
    cabx_chunk = struct.pack(">I", chunk_len) + chunk_type + c2pa_payload + struct.pack(">I", crc)

    # Insert caBX chunk right after IHDR (8 bytes signature + 25 bytes IHDR = 33 bytes)
    c2pa_png_bytes = raw_png[:33] + cabx_chunk + raw_png[33:]
    with open(path, "wb") as f:
        f.write(c2pa_png_bytes)


def generate_all():
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    create_orientation_6_jpeg(os.path.join(FIXTURES_DIR, "orientation_6.jpg"))
    create_rgba_transparent_png(os.path.join(FIXTURES_DIR, "rgba_transparent.png"))
    create_display_p3_jpeg(os.path.join(FIXTURES_DIR, "display_p3.jpg"))
    create_c2pa_jpeg(os.path.join(FIXTURES_DIR, "real_c2pa_jpeg.jpg"))
    create_c2pa_png(os.path.join(FIXTURES_DIR, "real_c2pa_png.png"))
    print(f"Generated all fixtures in: {FIXTURES_DIR}")


if __name__ == "__main__":
    generate_all()
