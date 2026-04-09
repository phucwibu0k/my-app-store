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
BASE_URL = f"https://{GITHUB_USERNAME}.github.io/{REPO_NAME}"
# ---------------

def get_ipa_info(ipa_path):
    try:
        with zipfile.ZipFile(ipa_path, 'r') as z:
            plist_paths = [f for f in z.namelist() if re.match(r'^Payload/[^/]+\.app/Info\.plist$', f)]
            if not plist_paths:
                return None
            with z.open(plist_paths[0]) as f:
                plist_data = plistlib.load(f)
                return {
                    "name": plist_data.get('CFBundleDisplayName') or plist_data.get('CFBundleName', 'Unknown App'),
                    "id": plist_data.get('CFBundleIdentifier', 'com.unknown.app'),
                    "ver": plist_data.get('CFBundleShortVersionString', '1.0'),
                }
    except Exception as e:
        print(f"Lỗi khi đọc {ipa_path}: {e}")
        return None

def main():
    print("Bắt đầu dọn dẹp và khởi tạo thư mục...")
    os.makedirs('plists', exist_ok=True)
    os.makedirs('pages', exist_ok=True) # Thư mục chứa các web con
    os.makedirs('temp_ipas', exist_ok=True)

    token = os.environ.get("GITHUB_TOKEN")
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/releases"
    
    req = urllib.request.Request(api_url)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")

    try:
        with urllib.request.urlopen(req) as response:
            releases = json.loads(response.read().decode())
    except Exception as e:
        print(f"Lỗi gọi API GitHub: {e}")
        return

    apps_data = []

    # 1. Quét toàn bộ Release để lấy IPA
    for rel in releases:
        tag_name = rel['tag_name']
        app_title = rel['name'] if rel['name'] else tag_name
        
        # Tìm file .ipa trong release này
        ipa_asset = next((a for a in rel['assets'] if a['name'].endswith('.ipa')), None)
        if not ipa_asset:
            continue

        download_url = ipa_asset['browser_download_url']
        file_name = ipa_asset['name']
        local_path = os.path.join('temp_ipas', file_name)

        print(f"Đang tải và phân tích: {app_title} (Tag: {tag_name})...")
        urllib.request.urlretrieve(download_url, local_path)

        info = get_ipa_info(local_path)
        if info:
            info['tag'] = tag_name
            info['release_name'] = app_title
            info['link'] = download_url
            # Format ngày tháng
            date_obj = datetime.strptime(rel['published_at'], "%Y-%m-%dT%H:%M:%SZ")
            info['date'] = date_obj.strftime("%d/%m/%Y")
            apps_data.append(info)

    # 2. Xây dựng giao diện (HTML Tổng và HTML Con)
    print("Bắt đầu tạo Website...")
    
    # CSS dùng chung
    css_style = """
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f2f2f7; margin: 0; padding: 20px; color: #1c1c1e; }
        .container { max-width: 600px; margin: 0 auto; }
        h1 { text-align: center; font-weight: 800; margin-bottom: 30px; }
        .card { background: white; border-radius: 16px; padding: 20px; margin-bottom: 16px; box-shadow: 0 4px 14px rgba(0,0,0,0.05); }
        .card-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 15px; margin-bottom: 15px; }
        .app-name { font-size: 20px; font-weight: bold; margin: 0; }
        .app-ver { color: #007aff; font-weight: 600; background: #e5f1ff; padding: 4px 10px; border-radius: 8px; font-size: 14px; }
        .btn { display: block; text-align: center; background-color: #007aff; color: white; text-decoration: none; padding: 14px 20px; border-radius: 14px; font-weight: bold; font-size: 16px; transition: 0.2s; }
        .btn:hover { background-color: #005bb5; }
        .btn-outline { background-color: transparent; color: #007aff; border: 2px solid #007aff; }
        .back-link { display: inline-block; margin-bottom: 20px; color: #007aff; text-decoration: none; font-weight: 600; }
        .meta-text { color: #8e8e93; font-size: 14px; margin: 5px 0; }
    </style>
    """

    # --- TẠO TRANG CHỦ (index.html) ---
    index_html = f"""<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Kho Ứng Dụng Cá Nhân</title>{css_style}</head><body><div class="container"><h1> App Store</h1>"""

    for app in apps_data:
        plist_filename = f"{app['tag']}.plist"
        plist_path = os.path.join('plists', plist_filename)
        plist_url = f"{BASE_URL}/plists/{plist_filename}"
        
        # Tạo file Plist
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>items</key><array><dict><key>assets</key><array><dict><key>kind</key><string>software-package</string><key>url</key><string>{app['link']}</string></dict></array><key>metadata</key><dict><key>bundle-identifier</key><string>{app['id']}</string><key>bundle-version</key><string>{app['ver']}</string><key>kind</key><string>software</string><key>title</key><string>{app['name']}</string></dict></dict></array></dict></plist>"""
        with open(plist_path, 'w', encoding='utf-8') as f:
            f.write(plist_content)

        # --- TẠO WEB CON (pages/tag_name.html) ---
        page_filename = f"{app['tag']}.html"
        page_path = os.path.join('pages', page_filename)
        page_html = f"""<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{app['name']} - App Store</title>{css_style}</head><body><div class="container">
            <a href="../index.html" class="back-link">← Quay lại danh sách</a>
            <div class="card">
                <div class="card-header">
                    <h2 class="app-name">{app['release_name']}</h2>
                    <span class="app-ver">v{app['ver']}</span>
                </div>
                <div style="margin-bottom: 25px;">
                    <p class="meta-text"><strong>Tên gói (ID):</strong> {app['id']}</p>
                    <p class="meta-text"><strong>Cập nhật lần cuối:</strong> {app['date']}</p>
                    <p class="meta-text"><strong>Kích thước:</strong> ~{round(os.path.getsize(os.path.join('temp_ipas', app['filename'])) / (1024*1024), 1)} MB</p>
                </div>
                <a href="itms-services://?action=download-manifest&url={plist_url}" class="btn">Cài đặt trực tiếp</a>
            </div>
        </div></body></html>"""
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write(page_html)

        # Thêm App vào list của Trang chủ
        index_html += f"""
        <div class="card">
            <div class="card-header">
                <p class="app-name">{app['release_name']}</p>
                <span class="app-ver">v{app['ver']}</span>
            </div>
            <a href="pages/{page_filename}" class="btn btn-outline">Xem chi tiết</a>
        </div>
        """

    index_html += "</div></body></html>"
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(index_html)

    print("Thành công! Website đã được nâng cấp.")

if __name__ == "__main__":
    main()
