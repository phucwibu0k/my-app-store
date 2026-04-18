"""
IPA Parser – đọc thông tin app và trích xuất icon từ file .ipa.
Bao gồm xử lý định dạng CgBI (PNG biến thể của Apple).
"""

import re
import struct
import zipfile
import zlib
import plistlib
from PIL import Image
import io

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
        { "name": str, "id": str, "version": str }

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
                
                # Cải tiến lấy Version: Ưu tiên ShortVersion, nếu không có thì lấy Version nội bộ, cuối cùng mới dùng 1.0
                app_version = plist.get("CFBundleShortVersionString") or plist.get("CFBundleVersion", "1.0")
                
                return {
                    "name": plist.get("CFBundleDisplayName") or plist.get("CFBundleName", "Unknown App"),
                    "id":   plist.get("CFBundleIdentifier", "com.unknown"),
                    "version":  app_version, # Đã đổi "ver" thành "version"
                }
    except Exception as e:
        print(f"   ⚠️ Lỗi đọc IPA: {e}")
    return None


# ── Trích xuất icon ──────────────────────────────────────────────

def find_largest_square_png(z: zipfile.ZipFile, files: list[str]) -> str | None:
    """
    Tìm file PNG có kích thước vuông lớn nhất trong IPA
    """
    from PIL import Image
    import io

    best_file = None
    best_size = 0

    for f in files:
        if not f.lower().endswith('.png'):
            continue

        try:
            with z.open(f) as src:
                data = src.read()

            data = revert_cgbi(data)  # fix PNG Apple nếu có

            img = Image.open(io.BytesIO(data))
            w, h = img.size

            # chỉ lấy ảnh vuông
            if w == h and w > best_size:
                best_size = w
                best_file = f

        except Exception:
            continue  # bỏ qua file lỗi

    return best_file

# ── Cập nhật logic tìm kiếm ứng viên ─────────────────────────────
def get_icon_candidates(files: list[str]) -> list[str]:
    """
    Tạo danh sách các ứng viên icon tiềm năng theo thứ tự ưu tiên.
    Lấy tất cả các file khớp thay vì chỉ lấy file đầu tiên để tăng tỷ lệ dự phòng.
    """
    candidates = []
    
    # 1. Ưu tiên icon.png (root hoặc trong thư mục)
    candidates.extend([f for f in files if f.lower().endswith('/icon.png') or f.lower() == 'icon.png'])
    
    # 2. Ưu tiên AppIcon60x60@2x.png
    candidates.extend([f for f in files if f.lower().endswith('appicon60x60@2x.png') and f not in candidates])
    
    # 3. Chứa 60x60@2x.png
    candidates.extend([f for f in files if '60x60@2x.png' in f.lower() and f not in candidates])
    
    # 4. Chứa 76x76@2x~ipad.png
    candidates.extend([f for f in files if '76x76@2x~ipad.png' in f.lower() and f not in candidates])
    
    return candidates

# ── Hàm trích xuất icon tối ưu ───────────────────────────────────

def extract_icon(ipa_path: str, output_path: str) -> bool:
    """
    Trích xuất icon từ file .ipa, fix CgBI nếu cần, lưu ra output_path.
    Tự động bỏ qua các file hỏng và tiếp tục tìm kiếm.
    """
    try:
        with zipfile.ZipFile(ipa_path, 'r') as z:
            files = z.namelist()
            candidates = get_icon_candidates(files)
            
            # Thử từng ứng viên trong danh sách ưu tiên
            for icon_name in candidates:
                try:
                    with z.open(icon_name) as src:
                        raw_data = src.read()
                        
                    # Fix CgBI nếu có
                    fixed_data = revert_cgbi(raw_data)
                    
                    # BƯỚC QUAN TRỌNG: Xác thực tính toàn vẹn của ảnh
                    # Lệnh verify() sẽ đọc header của file, nếu file rác/hỏng nó sẽ văng lỗi ngay
                    img = Image.open(io.BytesIO(fixed_data))
                    img.verify() 
                    
                    # Nếu không có lỗi xảy ra, ghi file và kết thúc
                    with open(output_path, "wb") as dst:
                        dst.write(fixed_data)
                    return True
                    
                except Exception as e:
                    # Nếu file hiện tại hỏng, in cảnh báo nhẹ và vòng lại (continue)
                    print(f"   ⚠️ File {icon_name} lỗi hoặc hỏng ({e}). Đang thử file tiếp theo...")
                    continue 
            
            # Fallback thứ 5: Nếu toàn bộ danh sách candidates đều hỏng hoặc rỗng
            print("   ⚠️ Không tìm thấy icon chuẩn hợp lệ, kích hoạt quét PNG vuông lớn nhất...")
            fallback_icon = find_largest_square_png(z, files)
            
            if fallback_icon:
                try:
                    with z.open(fallback_icon) as src:
                        raw_data = src.read()
                    fixed_data = revert_cgbi(raw_data)
                    
                    # Hàm find_largest_square_png của bạn đã test PIL.Image rồi nên ở đây là an toàn
                    with open(output_path, "wb") as dst:
                        dst.write(fixed_data)
                    return True
                except Exception as e:
                    print(f"   ⚠️ Lỗi khi ghi icon từ fallback ({fallback_icon}): {e}")
                    
            return False
            
    except Exception as e:
        print(f"   ⚠️ Lỗi mở gói IPA: {e}")
    return False