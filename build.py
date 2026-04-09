import os
import zipfile
import plistlib
import re
import urllib.request
import json
from datetime import datetime

# --- CẤU HÌNH ---
GITHUB_USERNAME = "phucwibu0k"
REPO_NAME = "my-app-store"
BASE_URL = "https://phmod.qzz.io" # Thay bằng tên miền của bạn
METADATA_FILE = "app_metadata.json"
# ---------------

def extract_icon(ipa_path, output_path):
    try:
        with zipfile.ZipFile(ipa_path, 'r') as z:
            icon_name = next((f for f in z.namelist() if f.lower().endswith('appicon60x60@2x.png')), None)
            if not icon_name:
                icon_name = next((f for f in z.namelist() if 'appicon' in f.lower() and f.lower().endswith('.png')), None)
            if icon_name:
                with z.open(icon_name) as source, open(output_path, "wb") as target:
                    target.write(source.read())
                return True
    except: pass
    return False

def get_ipa_info(ipa_path):
    try:
        with zipfile.ZipFile(ipa_path, 'r') as z:
            plist_paths = [f for f in z.namelist() if re.match(r'^Payload/[^/]+\.app/Info\.plist$', f)]
            if not plist_paths: return None
            with z.open(plist_paths[0]) as f:
                plist_data = plistlib.load(f)
                return {
                    "name": plist_data.get('CFBundleDisplayName') or plist_data.get('CFBundleName', 'Unknown'),
                    "id": plist_data.get('CFBundleIdentifier', 'com.unknown'),
                    "ver": plist_data.get('CFBundleShortVersionString', '1.0')
                }
    except: return None

def main():
    for folder in ['plists', 'pages', 'temp_ipas', 'icons']:
        os.makedirs(folder, exist_ok=True)

    # Tải bộ nhớ đệm cũ (nếu có)
    metadata = {}
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

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

        # KIỂM TRA: Nếu tag đã có trong metadata và không thay đổi gì thì dùng lại luôn
        if tag in metadata and metadata[tag].get('asset_id') == ipa_asset['id']:
            print(f"Bỏ qua (Đã có sẵn): {tag}")
            updated_metadata[tag] = metadata[tag]
            continue

        # Nếu là App mới hoặc bản cập nhật mới thì mới tải về
        print(f"Đang xử lý mới: {tag}...")
        local_path = os.path.join('temp_ipas', ipa_asset['name'])
        urllib.request.urlretrieve(ipa_asset['browser_download_url'], local_path)

        info = get_ipa_info(local_path)
        if info:
            icon_file = f"icons/{tag}.png"
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

    # Lưu lại bộ nhớ đệm mới
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(updated_metadata, f, ensure_ok=False, indent=4)

    # --- ĐOẠN CODE TẠO HTML (GIỮ NGUYÊN NHƯ BẢN TRƯỚC NHƯNG DÙNG updated_metadata) ---
    # (Để tiết kiệm không gian, bạn dùng lại logic tạo HTML từ updated_metadata.values())
    print("Đang tạo lại giao diện web...")
    # ... (Code tạo index.html và pages/ y hệt như bản Icon mình gửi lúc nãy) ...
