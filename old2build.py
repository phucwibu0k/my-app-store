#!/usr/bin/env python3
"""
App Store Build Script
- Đọc GitHub Releases
- Trích xuất #category từ release notes
- Lấy name, id, ver từ file IPA
- Trích xuất icon (hỗ trợ fix định dạng CgBI của Apple)
- Tạo index.html hiển thị danh sách ứng dụng
"""

import os
import zipfile
import plistlib
import re
import json
import subprocess
import urllib.request
import struct
import zlib
from datetime import datetime
from pathlib import Path

# ========================== CẤU HÌNH ==========================
GITHUB_USERNAME = "phucwibu0k"
REPO_NAME = "my-app-store"
METADATA_FILE = "app_metadata.json"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/releases"


def get_github_token():
    """
    Lấy GitHub Personal Access Token từ biến môi trường.
    
    Mục đích: Cho phép script truy cập GitHub API với quyền cao hơn 
    (tránh giới hạn rate limit của anonymous request).
    """
    return os.environ.get("GITHUB_TOKEN")


def parse_category_from_release_notes(body):
    """
    Trích xuất category từ release notes trên GitHub.
    
    Format mong đợi trong phần mô tả release:
        #category: GAMES
        #category: UTILITIES
        ...
    
    Nếu không tìm thấy dòng #category:, trả về mặc định là 'APP'.
    """
    if not body:
        return 'APP'
    
    for line in body.split('\n'):
        line = line.strip()
        if line.startswith('#category:'):
            match = re.match(r'#category:\s*(\w+)', line)
            if match:
                return match.group(1).upper()
    
    return 'APP'  # Mặc định nếu không tìm thấy


def parse_note_from_release_notes(body):
    """
    Trích xuất phần ghi chú (release notes) và loại bỏ dòng #category.
    
    Chức năng: Giữ lại toàn bộ nội dung mô tả, chỉ bỏ dòng chứa #category
    để hiển thị cho người dùng sau này (nếu cần).
    """
    if not body:
        return ""
    
    lines = []
    for line in body.split('\n'):
        if not line.strip().startswith('#category:'):
            lines.append(line)
            
    return '\n'.join(lines).strip()


def revert_cgbi(input_data):
    """
    Chuyển đổi định dạng PNG đặc biệt của Apple (CgBI) về PNG chuẩn.
    
    Lý do cần hàm này:
    - Apple dùng định dạng PNG biến thể (CgBI) trong file .ipa
    - Định dạng này không hiển thị được trên web/browser thông thường
    - Hàm này "bẻ khóa" và chuyển về PNG chuẩn để icon hiển thị đúng.
    
    Trả về: Dữ liệu PNG chuẩn (bytes)
    """
    if input_data[:8] != b'\x89PNG\r\n\x1a\n':
        return input_data
    
    pos = 8
    chunks = []
    is_cgbi = False
    width = height = 0
    idat_data = bytearray()
    
    while pos < len(input_data):
        length = struct.unpack(">I", input_data[pos:pos+4])[0]
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
        raw_pixels = zlib.decompress(idat_data, -15)
    except Exception:
        return input_data

    # Chuyển đổi thứ tự byte màu (BGRA → RGBA)
    newdata = bytearray()
    if len(raw_pixels) == height * (width * 4 + 1):
        stride = width * 4 + 1
        for y in range(height):
            start = y * stride
            newdata.append(raw_pixels[start])
            for x in range(width):
                idx = start + 1 + x * 4
                newdata.append(raw_pixels[idx+2])  # R
                newdata.append(raw_pixels[idx+1])  # G
                newdata.append(raw_pixels[idx])    # B
                newdata.append(raw_pixels[idx+3])  # A
    else:
        newdata = bytearray(raw_pixels)

    compressed = zlib.compress(newdata)
    
    # Xây dựng lại file PNG chuẩn
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
    """
    Trích xuất file icon từ file .ipa và chuyển sang PNG chuẩn.
    
    Quy trình:
    1. Mở file IPA (là file zip)
    2. Tìm icon theo thứ tự ưu tiên:
       - icon.png
       - AppIcon60x60@2x.png
       - Bất kỳ file nào chứa "appicon" và đuôi .png
    3. Sử dụng hàm revert_cgbi() để fix định dạng Apple
    4. Lưu icon ra thư mục icons/
    
    Trả về: True nếu thành công, False nếu thất bại.
    """
    try:
        with zipfile.ZipFile(ipa_path, 'r') as z:
            # Ưu tiên 1: icon.png
            icon_name = next((f for f in z.namelist() if f.lower().endswith('/icon.png') or f.lower() == 'icon.png'), None)
            
            # Ưu tiên 2: AppIcon60x60@2x.png
            if not icon_name:
                icon_name = next((f for f in z.namelist() if f.lower().endswith('appicon60x60@2x.png')), None)
            
            # Ưu tiên 3: Tìm file chứa "appicon"
            if not icon_name:
                icon_name = next((f for f in z.namelist() if 'appicon' in f.lower() and f.lower().endswith('.png')), None)
                
            if icon_name:
                with z.open(icon_name) as source:
                    raw_data = source.read()
                    fixed_data = revert_cgbi(raw_data)   # Fix CgBI → PNG chuẩn
                    with open(output_path, "wb") as target:
                        target.write(fixed_data)
                return True
    except Exception as e:
        print(f"   ⚠️ Lỗi trích xuất icon: {e}")
    return False


def get_ipa_info(ipa_path):
    """
    Đọc thông tin ứng dụng từ file Info.plist bên trong file .ipa.
    
    Trích xuất các thông tin chính:
    - name: Tên hiển thị của app (CFBundleDisplayName hoặc CFBundleName)
    - id: Bundle Identifier
    - ver: Phiên bản (CFBundleShortVersionString)
    
    Trả về: dict chứa thông tin hoặc None nếu thất bại.
    """
    try:
        with zipfile.ZipFile(ipa_path, 'r') as z:
            # Tìm file Info.plist trong thư mục Payload/*.app/
            plist_paths = [f for f in z.namelist() if re.match(r'^Payload/[^/]+\.app/Info\.plist$', f)]
            if not plist_paths:
                return None
                
            with z.open(plist_paths[0]) as f:
                plist_data = plistlib.load(f)
                return {
                    "name": plist_data.get('CFBundleDisplayName') or plist_data.get('CFBundleName', 'Unknown App'),
                    "id": plist_data.get('CFBundleIdentifier', 'com.unknown'),
                    "ver": plist_data.get('CFBundleShortVersionString', '1.0')
                }
    except Exception as e:
        print(f"   ⚠️ Lỗi đọc IPA: {e}")
    return None


def fetch_releases():
    """
    Lấy danh sách tất cả Releases từ GitHub repository.
    
    Sử dụng GitHub Releases API.
    Nếu có GITHUB_TOKEN thì dùng để tránh rate limit.
    """
    try:
        req = urllib.request.Request(GITHUB_API)
        token = get_github_token()
        if token:
            req.add_header("Authorization", f"token {token}")
        
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"❌ Lỗi khi fetch releases: {e}")
        return []


def load_metadata():
    """Đọc file metadata hiện có (app_metadata.json)"""
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_metadata(metadata):
    """Lưu metadata vào file app_metadata.json"""
    os.makedirs(os.path.dirname(METADATA_FILE) or '.', exist_ok=True)
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)
    print(f"✅ Đã cập nhật {METADATA_FILE}")


def update_metadata_from_releases():
    """
    Hàm chính cập nhật metadata từ GitHub Releases.
    
    Quy trình cho từng Release:
    1. Tải file .ipa về
    2. Đọc thông tin từ Info.plist
    3. Trích xuất icon và fix CgBI
    4. Đọc category và note từ release description
    5. Lấy danh sách screenshots từ thư mục screenshots/{tag}/
    6. Lưu tất cả vào app_metadata.json
    
    Chỉ xử lý release mới hoặc release có IPA mới (dựa vào asset_id).
    """
    print("\n📦 Đang lấy thông tin từ GitHub Releases...")
    
    # Tạo các thư mục cần thiết
    os.makedirs('icons', exist_ok=True)
    os.makedirs('temp_ipas', exist_ok=True)
    os.makedirs('screenshots', exist_ok=True)
    
    old_metadata = load_metadata()
    new_metadata = {}
    
    releases = fetch_releases()
    if not releases:
        print("⚠️ Không có releases nào")
        return False
    
    for rel in releases:
        tag = rel['tag_name']
        
        # Quét screenshots
        screenshots = []
        screenshot_dir = os.path.join('screenshots', tag)
        if os.path.exists(screenshot_dir):
            for file in os.listdir(screenshot_dir):
                if file.lower().endswith('.png'):
                    screenshots.append(f"screenshots/{tag}/{file}")
        
        ipa_asset = next((a for a in rel['assets'] if a['name'].endswith('.ipa')), None)
        
        # Nếu release không có file .ipa
        if not ipa_asset:
            print(f"⏭️ Bỏ qua (không có file IPA): {tag}")
            if tag in old_metadata:
                new_metadata[tag] = old_metadata[tag]
                new_metadata[tag]['screenshots'] = screenshots
            continue
        
        # Kiểm tra cache (đã xử lý chưa)
        if tag in old_metadata and old_metadata[tag].get('asset_id') == ipa_asset['id']:
            print(f"⏭️ Bỏ qua (đã có cache): {tag}")
            new_metadata[tag] = old_metadata[tag]
            new_metadata[tag]['screenshots'] = screenshots
            continue
        
        print(f"📝 Xử lý: {tag}")
        
        # Tải file IPA về
        local_ipa_path = os.path.join('temp_ipas', ipa_asset['name'])
        try:
            print(f"   ⬇️ Tải IPA...")
            urllib.request.urlretrieve(ipa_asset['browser_download_url'], local_ipa_path)
        except Exception as e:
            print(f"   ❌ Lỗi tải IPA: {e}")
            continue
        
        # Lấy thông tin từ IPA
        ipa_info = get_ipa_info(local_ipa_path)
        if not ipa_info:
            print(f"   ❌ Không thể đọc thông tin từ IPA")
            continue
        
        # Trích xuất icon
        icon_file = f"icons/{tag}.png"
        has_icon = extract_icon(local_ipa_path, icon_file)
        
        # Đọc category và note
        release_notes = rel.get('body', '')
        category = parse_category_from_release_notes(release_notes)
        note = parse_note_from_release_notes(release_notes)
        
        # Tạo metadata entry
        entry = {
            "name": ipa_info['name'],
            "id": ipa_info['id'],
            "ver": ipa_info['ver'],
            "tag": tag,
            "category": category,
            "note": note,
            "link": ipa_asset['browser_download_url'],
            "asset_id": ipa_asset['id'],
            "date": datetime.strptime(rel['published_at'], "%Y-%m-%dT%H:%M:%SZ").strftime("%d/%m/%Y"),
            "has_icon": has_icon,
            "icon_url": icon_file,
            "screenshots": screenshots
        }
        
        new_metadata[tag] = entry
        print(f"   ✓ Tên: {entry['name']}")
        print(f"   ✓ Danh mục: {entry['category']}")
        print(f"   ✓ ID: {entry['id']}")
        print(f"   ✓ Version: {entry['ver']}")
        
        # Xóa file IPA tạm thời
        try:
            os.remove(local_ipa_path)
        except:
            pass
    
    # Lưu metadata
    if new_metadata:
        save_metadata(new_metadata)
        return True
    return False


def build_react():
    """
    Build ứng dụng React (nếu có).
    
    Tự động phát hiện dùng pnpm hay npm để build.
    """
    print("\n🔨 Đang build React...")
    
    if os.path.exists('pnpm-lock.yaml'):
        build_cmd = 'pnpm build'
        print("📦 Sử dụng pnpm")
    elif os.path.exists('package-lock.json'):
        build_cmd = 'npm run build'
        print("📦 Sử dụng npm")
    else:
        print("⚠️ Không tìm thấy package-lock.yaml hoặc pnpm-lock.json")
        return False
    
    try:
        result = subprocess.run(build_cmd, shell=True, cwd=os.getcwd())
        if result.returncode == 0:
            print("✅ Build React thành công")
            return True
        else:
            print(f"❌ Build React thất bại")
            return False
    except Exception as e:
        print(f"❌ Lỗi khi build: {e}")
        return False


def generate_index_html():
    """
    Tạo file index.html tĩnh hiển thị tất cả các ứng dụng dưới dạng card.
    
    Chức năng:
    - Nhóm app theo category
    - Tạo filter tab theo category
    - Hiển thị card với icon, tên, version, ngày phát hành
    - Hỗ trợ click vào card để chuyển đến trang chi tiết (app.html?tag=...)
    """
    print("\n📄 Đang tạo index.html...")
    
    metadata = load_metadata()
    if not metadata:
        print("⚠️ Không có metadata")
        return False
    
    # CSS styling
    css = """
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
            padding: 30px 0;
        }
        header h1 { font-size: 2.5em; margin-bottom: 10px; }
        header p { font-size: 1.1em; opacity: 0.9; }
        
        .apps-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
        }
        
        .app-card {
            background: white;
            border-radius: 20px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: all 0.3s ease;
            cursor: pointer;
        }
        
        .app-card:hover {
            transform: translateY(-10px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }
        
        .app-icon-wrapper {
            text-align: center;
            margin-bottom: 15px;
        }
        
        .app-icon {
            width: 80px;
            height: 80px;
            border-radius: 18px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.5em;
            margin: 0 auto;
        }
        
        .app-name {
            font-size: 1.1em;
            font-weight: 600;
            color: #1c1c1e;
            margin-bottom: 5px;
            text-align: center;
        }
        
        .app-info {
            font-size: 0.85em;
            color: #8e8e93;
            text-align: center;
            margin-bottom: 10px;
        }
        
        .category-badge {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75em;
            margin-bottom: 10px;
        }
        
        .app-description {
            font-size: 0.85em;
            color: #666;
            margin-bottom: 15px;
            text-align: center;
            line-height: 1.4;
            min-height: 40px;
        }
        
        .btn-install {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.3s;
            font-size: 1em;
        }
        
        .btn-install:hover {
            opacity: 0.9;
        }
        
        .btn-install:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .filter-tabs {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        
        .filter-btn {
            padding: 8px 18px;
            border: 2px solid white;
            background: transparent;
            color: white;
            border-radius: 25px;
            cursor: pointer;
            font-size: 0.95em;
            transition: all 0.3s;
            font-weight: 500;
        }
        
        .filter-btn:hover,
        .filter-btn.active {
            background: white;
            color: #667eea;
        }
        
        .stats {
            text-align: center;
            color: white;
            margin-bottom: 20px;
            font-size: 0.9em;
        }
        
        @media (max-width: 768px) {
            header h1 { font-size: 1.8em; }
            .apps-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
    """
    
    # Nhóm apps theo category
    apps_by_category = {}
    for tag, app in metadata.items():
        category = app.get('category', 'APP').upper()
        if category not in apps_by_category:
            apps_by_category[category] = []
        apps_by_category[category].append((tag, app))
    
    categories = sorted(apps_by_category.keys())
    
    # HTML
    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="App Store - Tải các ứng dụng mới nhất">
    <title>App Store</title>
    {css}
</head>
<body>
    <div class="container">
        <header>
            <h1>📱 App Store</h1>
            <p>Khám phá các ứng dụng tuyệt vời</p>
        </header>
        
        <div class="stats">
            Có {len(metadata)} ứng dụng • {len(categories)} danh mục
        </div>
        
        <div class="filter-tabs">
            <button class="filter-btn active" onclick="filterCategory('ALL')">Tất cả</button>
"""
    
    for category in categories:
        html += f'            <button class="filter-btn" onclick="filterCategory(\'{category}\')">{category}</button>\n'
    
    html += """        </div>
        
        <div class="apps-grid" id="appsContainer">
"""
    
    # Tạo app cards
    for tag, app in metadata.items():
        category = app.get('category', 'APP').upper()
        name = app.get('name', tag)
        ver = app.get('ver', '1.0.0')
        date = app.get('date', 'N/A')
        has_icon = app.get('has_icon', False)
        icon_url = app.get('icon_url', '')
        
        # Lấy ký tự đầu của tên làm icon
        icon_char = name[0].upper()
        
        # HTML cho icon
        if has_icon and icon_url:
            icon_html = f'<img src="{icon_url}" alt="{name}" class="app-icon" style="object-fit: cover;">'
        else:
            icon_html = f'<div class="app-icon">{icon_char}</div>'
        
        html += f"""            <div class="app-card" data-category="{category}" onclick="window.location.href='app.html?tag={tag}'">
                <div class="app-icon-wrapper">
                    {icon_html}
                </div>
                <span class="category-badge">{category}</span>
                <h3 class="app-name">{name}</h3>
                <div class="app-info">v{ver} • {date}</div>
            </div>
"""
    
    html += """        </div>
    </div>
    
    <script>
        function filterCategory(category) {
            const cards = document.querySelectorAll('.app-card');
            const buttons = document.querySelectorAll('.filter-btn');
            
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            cards.forEach(card => {
                if (category === 'ALL' || card.dataset.category === category) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }
    </script>
</body>
</html>
"""
    
    try:
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ Tạo index.html với {len(metadata)} apps")
        return True
    except Exception as e:
        print(f"❌ Lỗi khi tạo index.html: {e}")
        return False


def main():
    """
    Hàm chính điều phối toàn bộ quá trình build.
    
    Thứ tự thực hiện:
    1. Cập nhật metadata từ GitHub Releases
    2. Tạo file index.html
    3. Build React (nếu có)
    """
    print("=" * 60)
    print("🚀 App Store Build Script")
    print("=" * 60)
    
    # Bước 1: Cập nhật metadata
    metadata_updated = update_metadata_from_releases()
    
    # Bước 2: Tạo trang chính
    generate_index_html()
    
    # Bước 3: Build React (tùy chọn)
    build_react()
    
    print("\n" + "=" * 60)
    print("✅ Hoàn tất!")
    print("=" * 60)


if __name__ == "__main__":
    main()