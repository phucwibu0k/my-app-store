import os
import zipfile
import plistlib
import re

# --- CẤU HÌNH ---
GITHUB_USERNAME = "TEN_GITHUB_CUA_BAN"  # VD: phuc123
REPO_NAME = "TEN_REPO_CUA_BAN"          # VD: ios-store
BASE_URL = f"https://{GITHUB_USERNAME}.github.io/{REPO_NAME}"
# ---------------

def get_ipa_info(ipa_path):
    try:
        with zipfile.ZipFile(ipa_path, 'r') as z:
            # Tìm file Info.plist nằm trong thư mục Payload/*.app/
            plist_paths = [f for f in z.namelist() if re.match(r'^Payload/[^/]+\.app/Info\.plist$', f)]
            if not plist_paths:
                return None
            
            with z.open(plist_paths[0]) as f:
                plist_data = plistlib.load(f)
                return {
                    "name": plist_data.get('CFBundleDisplayName') or plist_data.get('CFBundleName', 'Unknown App'),
                    "id": plist_data.get('CFBundleIdentifier', 'com.unknown.app'),
                    "ver": plist_data.get('CFBundleShortVersionString', '1.0'),
                    "filename": os.path.basename(ipa_path)
                }
    except Exception as e:
        print(f"Lỗi khi đọc {ipa_path}: {e}")
        return None

def main():
    # Tạo thư mục chứa file plist và thư mục tạm chứa file ipa
    os.makedirs('plists', exist_ok=True)
    apps_dir = 'apps'
    
    if not os.path.exists(apps_dir):
        os.makedirs(apps_dir)

    apps_data = []
    
    # Quét đọc các file .ipa đã được tải về bởi GitHub Actions
    for file in os.listdir(apps_dir):
        if file.endswith('.ipa'):
            print(f"Đang xử lý: {file}")
            info = get_ipa_info(os.path.join(apps_dir, file))
            if info:
                # Trỏ link cài đặt thẳng về file trong mục Release mới nhất (latest)
                info['link'] = f"https://github.com/{GITHUB_USERNAME}/{REPO_NAME}/releases/latest/download/{info['filename']}"
                apps_data.append(info)

    # Khởi tạo giao diện trang Web HTML
    html_content = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kho Ứng Dụng Cá Nhân</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f2f2f7; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; }
        h1 { text-align: center; color: #1c1c1e; }
        .app-card { background: white; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); display: flex; justify-content: space-between; align-items: center; }
        .app-info h3 { margin: 0 0 4px 0; color: #1c1c1e; }
        .app-info p { margin: 0; color: #8e8e93; font-size: 14px; }
        .install-btn { background-color: #007aff; color: white; text-decoration: none; padding: 8px 16px; border-radius: 20px; font-weight: bold; font-size: 14px; }
        .install-btn:hover { background-color: #005bb5; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Kho Ứng Dụng</h1>
"""

    for app in apps_data:
        plist_filename = f"{app['id']}.plist"
        plist_path = os.path.join('plists', plist_filename)
        plist_url = f"{BASE_URL}/plists/{plist_filename}"
        
        # Cấu trúc file manifest.plist
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>items</key>
    <array>
        <dict>
            <key>assets</key>
            <array>
                <dict>
                    <key>kind</key>
                    <string>software-package</string>
                    <key>url</key>
                    <string>{app['link']}</string>
                </dict>
            </array>
            <key>metadata</key>
            <dict>
                <key>bundle-identifier</key>
                <string>{app['id']}</string>
                <key>bundle-version</key>
                <string>{app['ver']}</string>
                <key>kind</key>
                <string>software</string>
                <key>title</key>
                <string>{app['name']}</string>
            </dict>
        </dict>
    </array>
</dict>
</plist>"""
        
        # Ghi đè file plist
        with open(plist_path, 'w', encoding='utf-8') as f:
            f.write(plist_content)
            
        # Thêm thông tin app vào Web
        html_content += f"""
        <div class="app-card">
            <div class="app-info">
                <h3>{app['name']}</h3>
                <p>Phiên bản: {app['ver']} | ID: {app['id']}</p>
            </div>
            <a href="itms-services://?action=download-manifest&url={plist_url}" class="install-btn">Cài đặt</a>
        </div>
        """

    html_content += """
    </div>
</body>
</html>
"""

    # Xuất file index.html
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

    print("Hoàn tất Build Web và Plist!")

if __name__ == "__main__":
    main()