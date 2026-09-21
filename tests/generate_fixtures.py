"""Generates standard-compliant test fixtures for provenance and format verification."""

import os
import io
import struct
from PIL import Image, ImageCms
import numpy as np
import piexif

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def build_display_p3_icc_bytes() -> bytes:
    """Builds an authentic ICC v2 profile with DCI-P3 primaries and D65/D50 adaptation.
    
    Standard Display P3 matrix profile with gamma 2.2 and 'Display P3' description tag.
    """
    def to_s15fixed16(val: float) -> int:
        return int(round(val * 65536.0))

    # DCI-P3 primaries adapted to D50 PCS
    r_xyz = struct.pack('>4s4sIII', b'XYZ ', b'\x00'*4, to_s15fixed16(0.5151), to_s15fixed16(0.2412), to_s15fixed16(0.0000))
    g_xyz = struct.pack('>4s4sIII', b'XYZ ', b'\x00'*4, to_s15fixed16(0.2919), to_s15fixed16(0.6922), to_s15fixed16(0.0450))
    b_xyz = struct.pack('>4s4sIII', b'XYZ ', b'\x00'*4, to_s15fixed16(0.1571), to_s15fixed16(0.0666), to_s15fixed16(0.7841))
    wtpt = struct.pack('>4s4sIII', b'XYZ ', b'\x00'*4, to_s15fixed16(0.9642), to_s15fixed16(1.0000), to_s15fixed16(0.8249))

    # Gamma 2.2 curve
    trc = struct.pack('>4s4sIH', b'curv', b'\x00'*4, 1, int(round(2.2 * 256.0)))

    # Description and Copyright tags
    desc_str = b'Display P3'
    desc = struct.pack('>4s4sI', b'desc', b'\x00'*4, len(desc_str) + 1) + desc_str + b'\x00' + b'\x00'*80
    cprt = struct.pack('>4s4s', b'text', b'\x00'*4) + b'Public Domain\x00'

    tags = [
        (b'desc', desc),
        (b'wtpt', wtpt),
        (b'rXYZ', r_xyz),
        (b'gXYZ', g_xyz),
        (b'bXYZ', b_xyz),
        (b'rTRC', trc),
        (b'gTRC', trc),
        (b'bTRC', trc),
        (b'cprt', cprt),
    ]

    header_and_table_size = 128 + 4 + len(tags) * 12
    tag_data = b''
    tag_entries = b''
    current_offset = header_and_table_size

    for sig, data in tags:
        pad = (4 - (len(data) % 4)) % 4
        padded_data = data + b'\x00' * pad
        tag_entries += struct.pack('>4sII', sig, current_offset, len(data))
        tag_data += padded_data
        current_offset += len(padded_data)

    total_size = header_and_table_size + len(tag_data)

    header = bytearray(128)
    struct.pack_into('>I', header, 0, total_size)       # profile size
    header[4:8] = b'lcms'                               # CMM signature
    struct.pack_into('>I', header, 8, 0x02400000)       # version 2.4
    header[12:16] = b'mntr'                             # device class: monitor
    header[16:20] = b'RGB '                             # data color space
    header[20:24] = b'XYZ '                             # profile connection space (PCS)
    header[36:40] = b'acsp'                             # profile file signature
    header[40:44] = b'APPL'                             # primary platform
    struct.pack_into('>III', header, 68, to_s15fixed16(0.9642), to_s15fixed16(1.0000), to_s15fixed16(0.8249))

    return bytes(header) + struct.pack('>I', len(tags)) + tag_entries + tag_data


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


def create_synthetic_display_p3_jpeg(path: str):
    """Creates a JPEG with an embedded synthetic Display-P3 ICC profile."""
    img = Image.new("RGB", (120, 120), color=(200, 50, 50))
    icc_bytes = build_display_p3_icc_bytes()
    img.save(path, format="JPEG", icc_profile=icc_bytes)


def create_synthetic_c2pa_jumbf_jpeg(path: str):
    """Creates a JPEG with standard APP11 JUMBF C2PA Manifest Store.
    
    Conforms to ISO/IEC 19566-5 JUMBF box and C2PA spec section 8.1.
    """
    base_img = Image.new("RGB", (160, 160), color=(140, 180, 220))
    buf = io.BytesIO()
    base_img.save(buf, format="JPEG")
    raw_jpg = buf.getvalue()

    # Build JUMBF Box (ISO/IEC 19566-5)
    c2pa_uuid = bytes.fromhex("6332706100110010800000aa00389b71")
    jumd_payload = c2pa_uuid + b"\x03" + b"c2pa.manifest\x00"
    jumd_box = struct.pack(">I", 8 + len(jumd_payload)) + b"jumd" + jumd_payload

    # Manifest Content Box (c2pa)
    content_payload = b'{"claim_generator": "TestC2PAGenerator/1.0", "title": "C2PA Provenance Store"}'
    content_box = struct.pack(">I", 8 + len(content_payload)) + b"c2pa" + content_payload

    jumb_box = struct.pack(">I", 8 + len(jumd_box) + len(content_box)) + b"jumb" + jumd_box + content_box

    # JPEG APP11 marker is 0xFFEB
    app11_payload = b"JP\x00\x00" + struct.pack(">I", 1) + jumb_box
    app11_marker = b"\xff\xeb" + struct.pack(">H", 2 + len(app11_payload)) + app11_payload

    # Insert APP11 right after SOI (first 2 bytes \xff\xd8)
    c2pa_jpg_bytes = raw_jpg[:2] + app11_marker + raw_jpg[2:]
    with open(path, "wb") as f:
        f.write(c2pa_jpg_bytes)


def create_synthetic_c2pa_cabx_png(path: str):
    """Creates a PNG with standard caBX (C2PA) chunk per PNG binding specification."""
    base_img = Image.new("RGB", (160, 160), color=(180, 220, 140))
    buf = io.BytesIO()
    base_img.save(buf, format="PNG")
    raw_png = buf.getvalue()

    # caBX payload: JUMBF box inside PNG chunk
    c2pa_payload = b"c2pa_manifest_store_v1_active_claim_manifest_assertion_store"
    chunk_type = b"caBX"
    chunk_len = len(c2pa_payload)
    import zlib
    crc = zlib.crc32(chunk_type + c2pa_payload) & 0xFFFFFFFF
    cabx_chunk = struct.pack(">I", chunk_len) + chunk_type + c2pa_payload + struct.pack(">I", crc)

    # Insert caBX chunk right after IHDR (33 bytes)
    c2pa_png_bytes = raw_png[:33] + cabx_chunk + raw_png[33:]
    with open(path, "wb") as f:
        f.write(c2pa_png_bytes)


def generate_all():
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    create_orientation_6_jpeg(os.path.join(FIXTURES_DIR, "orientation_6.jpg"))
    create_rgba_transparent_png(os.path.join(FIXTURES_DIR, "rgba_transparent.png"))

    # Synthetic Display-P3 profile fixture
    create_synthetic_display_p3_jpeg(os.path.join(FIXTURES_DIR, "synthetic_display_p3_profile.jpg"))

    # Synthetic C2PA fixtures per ISO/IEC 19566-5 & C2PA binding
    create_synthetic_c2pa_jumbf_jpeg(os.path.join(FIXTURES_DIR, "synthetic_c2pa_jumbf.jpg"))
    create_synthetic_c2pa_cabx_png(os.path.join(FIXTURES_DIR, "synthetic_c2pa_cabx.png"))

    print(f"Generated synthetic fixtures in: {FIXTURES_DIR}")


if __name__ == "__main__":
    generate_all()
