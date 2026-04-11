"""
IPA Parser – đọc thông tin app và trích xuất icon từ file .ipa.
Bao gồm xử lý định dạng CgBI (PNG biến thể của Apple).
"""

import re
import struct
import zipfile
import zlib
import plistlib


# ── CgBI → PNG chuẩn ────────────────────────────────────────────

def revert_cgbi(input_data: bytes) -> bytes:
    """
    Chuyển PNG định dạng CgBI (Apple) về PNG chuẩn có thể hiển thị trên browser.

    Apple dùng CgBI trong các file .ipa: dữ liệu pixel bị nén raw (wbits=-15)
    và thứ tự kênh màu là BGRA thay vì RGBA.

    Trả về dữ liệu PNG chuẩn (bytes), hoặc input gốc nếu không phải CgBI.
    """
    PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
    if input_data[:8] != PNG_MAGIC:
        return input_data

    pos = 8
    chunks = []
    is_cgbi = False
    width = height = 0
    idat_data = bytearray()

    # Đọc từng chunk PNG
    while pos < len(input_data):
        length     = struct.unpack(">I", input_data[pos:pos+4])[0]
        chunk_type = input_data[pos+4:pos+8]
        chunk_data = input_data[pos+8:pos+8+length]
        pos += length + 12

        if chunk_type == b'CgBI':
            is_cgbi = True
        elif chunk_type == b'IHDR':
            width, height = struct.unpack(">II", chunk_data[:8])
            chunks.append((chunk_type, chunk_data))
        elif chunk_type == b'IDAT':
            idat_data.extend(chunk_data)
        elif chunk_type == b'IEND':
            break
        else:
            chunks.append((chunk_type, chunk_data))

    if not is_cgbi:
        return input_data

    try:
        raw_pixels = zlib.decompress(idat_data, -15)  # raw deflate
    except Exception:
        return input_data

    # Chuyển BGRA → RGBA từng pixel
    newdata = bytearray()
    stride = width * 4 + 1          # 1 byte filter + 4 bytes/pixel
    if len(raw_pixels) == height * stride:
        for y in range(height):
            start = y * stride
            newdata.append(raw_pixels[start])  # filter byte
            for x in range(width):
                idx = start + 1 + x * 4
                newdata.append(raw_pixels[idx+2])  # R ← B
                newdata.append(raw_pixels[idx+1])  # G
                newdata.append(raw_pixels[idx])    # B ← R
                newdata.append(raw_pixels[idx+3])  # A
    else:
        newdata = bytearray(raw_pixels)

    compressed = zlib.compress(newdata)

    # Tái tạo file PNG hợp lệ
    out = bytearray(PNG_MAGIC)

    def write_chunk(c_type: bytes, c_data: bytes) -> None:
        out.extend(struct.pack(">I", len(c_data)))
        out.extend(c_type)
        out.extend(c_data)
        out.extend(struct.pack(">I", zlib.crc32(c_type + c_data) & 0xFFFFFFFF))

    for c_type, c_data in chunks:
        write_chunk(c_type, c_data)

    write_chunk(b'IDAT', compressed)
    write_chunk(b'IEND', b'')

    return bytes(out)


# ── Đọc thông tin app ────────────────────────────────────────────

def get_ipa_info(ipa_path: str) -> dict | None:
    """
    Đọc Info.plist bên trong file .ipa và trả về dict:
        { "name": str, "id": str, "ver": str }

    Trả về None nếu không đọc được.
    """
    try:
        with zipfile.ZipFile(ipa_path, 'r') as z:
            plist_paths = [
                f for f in z.namelist()
                if re.match(r'^Payload/[^/]+\.app/Info\.plist$', f)
            ]
            if not plist_paths:
                return None

            with z.open(plist_paths[0]) as f:
                plist = plistlib.load(f)
                return {
                    "name": plist.get("CFBundleDisplayName") or plist.get("CFBundleName", "Unknown App"),
                    "id":   plist.get("CFBundleIdentifier", "com.unknown"),
                    "ver":  plist.get("CFBundleShortVersionString", "1.0"),
                }
    except Exception as e:
        print(f"   ⚠️ Lỗi đọc IPA: {e}")
    return None


# ── Trích xuất icon ──────────────────────────────────────────────

_ICON_CANDIDATES = [
    lambda files: next((f for f in files if f.lower().endswith('/icon.png') or f.lower() == 'icon.png'), None),
    lambda files: next((f for f in files if f.lower().endswith('appicon60x60@2x.png')), None),
    lambda files: next((f for f in files if 'appicon' in f.lower() and f.lower().endswith('.png')), None),
]


def extract_icon(ipa_path: str, output_path: str) -> bool:
    """
    Trích xuất icon từ file .ipa, fix CgBI nếu cần, lưu ra output_path.

    Thứ tự tìm icon:
      1. icon.png (root hoặc subdirectory)
      2. AppIcon60x60@2x.png
      3. Bất kỳ file chứa 'appicon' và đuôi .png

    Trả về True nếu thành công.
    """
    try:
        with zipfile.ZipFile(ipa_path, 'r') as z:
            files = z.namelist()
            icon_name = None
            for candidate_fn in _ICON_CANDIDATES:
                icon_name = candidate_fn(files)
                if icon_name:
                    break

            if not icon_name:
                return False

            with z.open(icon_name) as src:
                raw_data   = src.read()
                fixed_data = revert_cgbi(raw_data)

            with open(output_path, "wb") as dst:
                dst.write(fixed_data)

            return True
    except Exception as e:
        print(f"   ⚠️ Lỗi trích xuất icon: {e}")
    return False
