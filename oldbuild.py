import os
import zipfile
import plistlib
import re
import urllib.request
import json
import struct
import zlib
from datetime import datetime

# --- CẤU HÌNH ---
GITHUB_USERNAME = "phucwibu0k"
REPO_NAME = "my-app-store"
BASE_URL = "https://phmod.qzz.io" 
METADATA_FILE = "app_metadata.json"
# ---------------

def revert_cgbi(input_data):
    """Bẻ khóa và Dịch ngược định dạng Apple CgBI PNG thành PNG chuẩn Windows"""
    # Kiểm tra xem có đúng là file PNG không
    if input_data[:8] != b'\x89PNG\r\n\x1a\n':
        return input_data
    
    pos = 8
    chunks = []
    is_cgbi = False
    width = height = 0
    idat_data = bytearray()
    
    # BƯỚC 1: Đọc từng khối dữ liệu (Chunk)
    while pos < len(input_data):
        length = struct.unpack(">I", input_data[pos:pos+4])[0]
        chunk_type = input_data[pos+4:pos+8]
        chunk_data = input_data[pos+8:pos+8+length]
        pos += length + 12 # Chuyển sang chunk tiếp theo
        
        if chunk_type == b'CgBI':
            is_cgbi = True # Phát hiện ảnh bị Apple "chế"
        elif chunk_type == b'IHDR':
            width, height = struct.unpack(">II", chunk_data[:8])
            chunks.append((chunk_type, chunk_data))
        elif chunk_type == b'IDAT':
            idat_data.extend(chunk_data) # Gom dữ liệu ảnh
        elif chunk_type == b'IEND':
            break
        else:
            chunks.append((chunk_type, chunk_data))

    # Nếu không phải CgBI, trả về ảnh gốc
    if not is_cgbi:
        return input_data

    # BƯỚC 2: Giải nén ảnh (Ép giải nén theo kiểu raw deflate -15)
    try:
        raw_pixels = zlib.decompress(idat_data, -15)
    except Exception:
        return input_data

    # BƯỚC 3: Đảo ngược hệ màu từ BGRA về RGBA để Windows đọc được
    newdata = bytearray()
    if len(raw_pixels) == height * (width * 4 + 1):
        stride = width * 4 + 1
        for y in range(height):
            start = y * stride
            newdata.append(raw_pixels[start]) # Giữ nguyên byte filter của dòng
            for x in range(width):
                idx = start + 1 + x * 4
                newdata.append(raw_pixels[idx+2]) # Lấy màu Đỏ (R) từ vị trí Xanh dương (B)
                newdata.append(raw_pixels[idx+1]) # Màu Xanh lá (G) giữ nguyên
                newdata.append(raw_pixels[idx])   # Lấy màu Xanh dương (B) từ vị trí Đỏ (R)
                newdata.append(raw_pixels[idx+3]) # Kênh Alpha (A) giữ nguyên
    else:
        newdata = bytearray(raw_pixels)

    # BƯỚC 4: Nén lại thành PNG chuẩn quốc tế
    compressed = zlib.compress(newdata)
    
    out = bytearray(b'\x89PNG\r\n\x1a\n')
    for c_type, c_data in chunks:
        out.extend(struct.pack(">I", len(c_data)))
        out.extend(c_type)
        out.extend(c_data)
        out.extend(struct.pack(">I", zlib.crc32(c_type + c_data) & 0xffffffff))
        
    out.extend(struct.pack(">I", len(compressed)))
    out.extend(b'IDAT')
    out.extend(compressed)
    out.extend(struct.pack(">I", zlib.crc32(b'IDAT' + compressed) & 0xffffffff))
    
    out.extend(struct.pack(">I", 0))
    out.extend(b'IEND')
    out.extend(struct.pack(">I", zlib.crc32(b'IEND') & 0xffffffff))
    
    return bytes(out)

def extract_icon(ipa_path, output_path):
    """Mổ IPA lấy icon và quét qua bộ giải mã CgBI"""
    try:
        with zipfile.ZipFile(ipa_path, 'r') as z:
            icon_name = next((f for f in z.namelist() if f.lower().endswith('appicon60x60@2x.png')), None)
            if not icon_name:
                icon_name = next((f for f in z.namelist() if 'appicon' in f.lower() and f.lower().endswith('.png')), None)
            if icon_name:
                with z.open(icon_name) as source:
                    raw_data = source.read()
                    
                # Bơm dữ liệu thô qua hàm giải mã
                fixed_data = revert_cgbi(raw_data)
                
                with open(output_path, "wb") as target:
                    target.write(fixed_data)
                return True
    except Exception as e:
        print(f"Lỗi trích xuất: {e}")
    return False

def get_ipa_info(ipa_path):
    try:
        with zipfile.ZipFile(ipa_path, 'r') as z:
            plist_paths = [f for f in z.namelist() if re.match(r'^Payload/[^/]+\.app/Info\.plist$', f)]
            if not plist_paths: return None
            with z.open(plist_paths[0]) as f:
                plist_data = plistlib.load(f)
                return {
                    "name": plist_data.get('CFBundleDisplayName') or plist_data.get('CFBundleName', 'Unknown App'),
                    "id": plist_data.get('CFBundleIdentifier', 'com.unknown'),
                    "ver": plist_data.get('CFBundleShortVersionString', '1.0')
                }
    except: return None

def main():
    print("Khởi tạo thư mục...")
    for folder in ['plists', 'pages', 'icons', 'temp_ipas']:
        os.makedirs(folder, exist_ok=True)

    metadata = {}
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except: metadata = {}

    token = os.environ.get("GITHUB_TOKEN")
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/releases"
    req = urllib.request.Request(api_url)
    if token: req.add_header("Authorization", f"token {token}")
    
    with urllib.request.urlopen(req) as response:
        releases = json.loads(response.read().decode())

    updated_metadata = {}

    for rel in releases:
        tag = rel['tag_name']
        ipa_asset = next((a for a in rel['assets'] if a['name'].endswith('.ipa')), None)
        if not ipa_asset: continue

        if tag in metadata and metadata[tag].get('asset_id') == ipa_asset['id']:
            print(f"Bỏ qua (Dùng lại cache): {tag}")
            updated_metadata[tag] = metadata[tag]
            continue

        print(f"Đang xử lý mới: {tag}...")
        local_path = os.path.join('temp_ipas', ipa_asset['name'])
        urllib.request.urlretrieve(ipa_asset['browser_download_url'], local_path)

        info = get_ipa_info(local_path)
        if info:
            icon_file = f"icons/{tag}.png"
            # NẠP ICON VÀ TỰ ĐỘNG FIX LỖI APPLE
            has_icon = extract_icon(local_path, icon_file)
            
            updated_metadata[tag] = {
                "name": info['name'],
                "id": info['id'],
                "ver": info['ver'],
                "tag": tag,
                "link": ipa_asset['browser_download_url'],
                "asset_id": ipa_asset['id'],
                "date": datetime.strptime(rel['published_at'], "%Y-%m-%dT%H:%M:%SZ").strftime("%d/%m/%Y"),
                "has_icon": has_icon,
                "icon_url": icon_file
            }

    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(updated_metadata, f, ensure_ascii=False, indent=4)

    # --- TẠO GIAO DIỆN WEB ---
    css_style = """
    <style>
        body { font-family: -apple-system, sans-serif; background: #f2f2f7; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; }
        .card { background: white; border-radius: 15px; padding: 15px; margin-bottom: 12px; display: flex; align-items: center; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .app-icon { width: 55px; height: 55px; border-radius: 12px; margin-right: 15px; object-fit: cover; border: 1px solid #eaeaea; }
        .app-info { flex-grow: 1; }
        .app-name { font-weight: bold; margin: 0; font-size: 16px; color: #1c1c1e; }
        .app-meta { color: #8e8e93; font-size: 12px; margin-top: 3px; }
        .btn { background: #007aff; color: white; padding: 6px 15px; border-radius: 15px; text-decoration: none; font-weight: bold; font-size: 13px; }
    </style>
    """

    index_html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1'>{css_style}</head><body><div class='container'><h1> App Store</h1>"

    for tag, app in updated_metadata.items():
        plist_url = f"{BASE_URL}/plists/{tag}.plist"
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>items</key><array><dict><key>assets</key><array><dict><key>kind</key><string>software-package</string><key>url</key><string>{app['link']}</string></dict></array><key>metadata</key><dict><key>bundle-identifier</key><string>{app['id']}</string><key>bundle-version</key><string>{app['ver']}</string><key>kind</key><string>software</string><key>title</key><string>{app['name']}</string></dict></dict></array></dict></plist>"""
        with open(f"plists/{tag}.plist", 'w', encoding='utf-8') as f: f.write(plist_content)

        page_html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1'>{css_style}</head><body><div class='container'><a href='../index.html' style='text-decoration:none;'>← Quay lại</a><div style='text-align:center; padding-top:30px;'><img src='../{app['icon_url']}' style='width:100px; height:100px; border-radius:22px; object-fit:cover; box-shadow: 0 4px 10px rgba(0,0,0,0.1);'><br><h2 style='color:#1c1c1e;'>{app['name']}</h2><p style='color:#8e8e93;'>Phiên bản: {app['ver']}</p><br><a href='itms-services://?action=download-manifest&url={plist_url}' class='btn' style='padding:12px 30px; font-size: 16px;'>CÀI ĐẶT</a></div></div></body></html>"
        with open(f"pages/{tag}.html", 'w', encoding='utf-8') as f: f.write(page_html)

        icon_img = f"<img src='{app['icon_url']}' class='app-icon'>" if app['has_icon'] else "<div class='app-icon' style='background:#ccc'></div>"
        index_html += f"<div class='card'>{icon_img}<div class='app-info'><p class='app-name'>{app['name']}</p><p class='app-meta'>v{app['ver']} • {app['date']}</p></div><a href='pages/{tag}.html' class='btn'>XEM</a></div>"

    index_html += "</div></body></html>"
    with open('index.html', 'w', encoding='utf-8') as f: f.write(index_html)
    print("Xong!")

if __name__ == "__main__": main()