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
# Sau khi bạn cấu hình Cloudflare xong, hãy thay link này bằng https://phmod.qzz.io
BASE_URL = f"https://{GITHUB_USERNAME}.github.io/{REPO_NAME}"
# ---------------

def extract_icon(ipa_path, output_path):
    """Trích xuất icon từ file IPA"""
    try:
        with zipfile.ZipFile(ipa_path, 'r') as z:
            # Tìm file icon theo đúng tên user yêu cầu (AppIcon60x60@2x.png)
            # Dùng .lower() để tránh lỗi chữ hoa chữ thường
            icon_name = next((f for f in z.namelist() if f.lower().endswith('appicon60x60@2x.png')), None)
            
            # Nếu không tìm thấy file cụ thể đó, thử tìm file bất kỳ có tên 'AppIcon' và đuôi '.png'
            if not icon_name:
                icon_name = next((f for f in z.namelist() if 'appicon' in f.lower() and f.lower().endswith('.png')), None)
            
            if icon_name:
                with z.open(icon_name) as source, open(output_path, "wb") as target:
                    target.write(source.read())
                return True
    except Exception as e:
        print(f"Lỗi khi trích xuất icon: {e}")
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
                    "id": plist_data.get('CFBundleIdentifier', 'com.unknown.app'),
                    "ver": plist_data.get('CFBundleShortVersionString', '1.0'),
                    "filename": os.path.basename(ipa_path)
                }
    except:
        return None

def main():
    print("Khởi tạo thư mục hệ thống...")
    for folder in ['plists', 'pages', 'temp_ipas', 'icons']:
        os.makedirs(folder, exist_ok=True)

    token = os.environ.get("GITHUB_TOKEN")
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/releases"
    
    req = urllib.request.Request(api_url)
    if token: req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")

    try:
        with urllib.request.urlopen(req) as response:
            releases = json.loads(response.read().decode())
    except Exception as e:
        print(f"Lỗi API: {e}"); return

    apps_data = []

    for rel in releases:
        tag_name = rel['tag_name']
        ipa_asset = next((a for a in rel['assets'] if a['name'].endswith('.ipa')), None)
        if not ipa_asset: continue

        local_path = os.path.join('temp_ipas', ipa_asset['name'])
        print(f"Đang xử lý: {tag_name}...")
        urllib.request.urlretrieve(ipa_asset['browser_download_url'], local_path)

        # Trích xuất icon
        icon_file = f"{tag_name}.png"
        icon_path = os.path.join('icons', icon_file)
        has_icon = extract_icon(local_path, icon_path)

        info = get_ipa_info(local_path)
        if info:
            info.update({
                "tag": tag_name, "link": ipa_asset['browser_download_url'],
                "has_icon": has_icon, "icon_url": f"icons/{icon_file}",
                "date": datetime.strptime(rel['published_at'], "%Y-%m-%dT%H:%M:%SZ").strftime("%d/%m/%Y")
            })
            apps_data.append(info)

    print("Tạo Website với giao diện Icon mới...")
    
    css_style = """
    <style>
        body { font-family: -apple-system, system-ui, sans-serif; background: #f2f2f7; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; }
        h1 { text-align: center; color: #1c1c1e; }
        .card { background: white; border-radius: 18px; padding: 15px; margin-bottom: 15px; display: flex; align-items: center; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .app-icon { width: 60px; height: 60px; border-radius: 13px; margin-right: 15px; object-fit: cover; border: 0.5px solid #ddd; }
        .app-info { flex-grow: 1; }
        .app-name { font-size: 17px; font-weight: bold; margin: 0; }
        .app-meta { color: #8e8e93; font-size: 13px; margin: 3px 0; }
        .btn { background: #007aff; color: white; padding: 8px 16px; border-radius: 20px; text-decoration: none; font-weight: bold; font-size: 14px; }
        .detail-card { background: white; border-radius: 20px; padding: 25px; text-align: center; }
        .large-icon { width: 100px; height: 100px; border-radius: 22px; margin-bottom: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    </style>
    """

    index_html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1'>{css_style}</head><body><div class='container'><h1> App Store</h1>"

    for app in apps_data:
        icon_tag = f"<img src='{app['icon_url']}' class='app-icon'>" if app['has_icon'] else "<div class='app-icon' style='background:#ccc'></div>"
        
        # Tạo file Plist
        plist_filename = f"{app['tag']}.plist"
        plist_url = f"{BASE_URL}/plists/{plist_filename}"
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>items</key><array><dict><key>assets</key><array><dict><key>kind</key><string>software-package</string><key>url</key><string>{app['link']}</string></dict></array><key>metadata</key><dict><key>bundle-identifier</key><string>{app['id']}</string><key>bundle-version</key><string>{app['ver']}</string><key>kind</key><string>software</string><key>title</key><string>{app['name']}</string></dict></dict></array></dict></plist>"""
        with open(os.path.join('plists', plist_filename), 'w') as f: f.write(plist_content)

        # Tạo trang chi tiết
        page_html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1'>{css_style}</head><body><div class='container'><a href='../index.html' style='color:#007aff; text-decoration:none;'>← Quay lại</a><div class='detail-card'><img src='../{app['icon_url']}' class='large-icon'><h2>{app['name']}</h2><p class='app-meta'>Phiên bản: {app['ver']}</p><p class='app-meta'>ID: {app['id']}</p><br><a href='itms-services://?action=download-manifest&url={plist_url}' class='btn' style='padding: 15px 40px;'>Cài đặt ngay</a></div></div></body></html>"
        with open(os.path.join('pages', f"{app['tag']}.html"), 'w') as f: f.write(page_html)

        # Thêm vào trang chủ
        index_html += f"<div class='card'>{icon_tag}<div class='app-info'><p class='app-name'>{app['name']}</p><p class='app-meta'>v{app['ver']} • {app['date']}</p></div><a href='pages/{app['tag']}.html' class='btn'>Xem</a></div>"

    index_html += "</div></body></html>"
    with open('index.html', 'w') as f: f.write(index_html)
    print("Xong! Web đã có Icon.")

if __name__ == "__main__": main()
