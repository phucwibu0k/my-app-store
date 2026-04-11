"""
Metadata Store – quản lý file app_metadata.json và
điều phối việc cập nhật metadata từ GitHub Releases.
"""

import json
import os
import urllib.request
from datetime import datetime

from .config import ICONS_DIR, METADATA_FILE, SCREENSHOTS_DIR, TEMP_IPA_DIR
from .github_client import fetch_releases, parse_category, parse_note
from .ipa_parser import extract_icon, get_ipa_info


# ── Đọc / ghi ────────────────────────────────────────────────────

def load_metadata() -> dict:
    """Đọc app_metadata.json; trả về dict rỗng nếu chưa có."""
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_metadata(metadata: dict) -> None:
    """Ghi metadata ra app_metadata.json."""
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)
    print(f"✅ Đã cập nhật {METADATA_FILE}")


# ── Helpers ──────────────────────────────────────────────────────

def _scan_screenshots(tag: str) -> list[str]:
    """Trả về danh sách đường dẫn ảnh PNG trong screenshots/{tag}/."""
    screenshot_dir = os.path.join(SCREENSHOTS_DIR, tag)
    if not os.path.exists(screenshot_dir):
        return []
    return [
        f"{SCREENSHOTS_DIR}/{tag}/{f}"
        for f in os.listdir(screenshot_dir)
        if f.lower().endswith('.png')
    ]


def _download_ipa(asset: dict, dest_path: str) -> bool:
    """Tải file IPA từ URL release asset về dest_path."""
    try:
        print(f"   ⬇️ Tải IPA...")
        urllib.request.urlretrieve(asset['browser_download_url'], dest_path)
        return True
    except Exception as e:
        print(f"   ❌ Lỗi tải IPA: {e}")
        return False


def _build_entry(rel: dict, tag: str, ipa_info: dict,
                 ipa_asset: dict, has_icon: bool, icon_url: str,
                 screenshots: list[str]) -> dict:
    """Tạo dict metadata cho một release."""
    body = rel.get('body', '')
    return {
        "name":        ipa_info['name'],
        "id":          ipa_info['id'],
        "ver":         ipa_info['ver'],
        "tag":         tag,
        "category":    parse_category(body),
        "note":        parse_note(body),
        "link":        ipa_asset['browser_download_url'],
        "asset_id":    ipa_asset['id'],
        "date":        datetime.strptime(
                           rel['published_at'], "%Y-%m-%dT%H:%M:%SZ"
                       ).strftime("%d/%m/%Y"),
        "has_icon":    has_icon,
        "icon_url":    icon_url,
        "screenshots": screenshots,
    }


# ── Cập nhật chính ───────────────────────────────────────────────

def update_metadata_from_releases() -> bool:
    """
    Lấy GitHub Releases, xử lý từng release còn mới (chưa cache)
    và cập nhật app_metadata.json.

    Quy trình mỗi release:
      1. Tải IPA
      2. Đọc thông tin từ Info.plist
      3. Trích xuất icon (fix CgBI)
      4. Parse category / note từ release body
      5. Quét screenshots
      6. Lưu metadata

    Trả về True nếu có gì đó được cập nhật.
    """
    print("\n📦 Đang lấy thông tin từ GitHub Releases...")

    os.makedirs(ICONS_DIR, exist_ok=True)
    os.makedirs(TEMP_IPA_DIR, exist_ok=True)
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    old_metadata = load_metadata()
    new_metadata: dict = {}

    releases = fetch_releases()
    if not releases:
        print("⚠️ Không có releases nào")
        return False

    for rel in releases:
        tag         = rel['tag_name']
        screenshots = _scan_screenshots(tag)
        ipa_asset   = next((a for a in rel['assets'] if a['name'].endswith('.ipa')), None)

        # Release không có IPA → giữ lại cache cũ nếu có
        if not ipa_asset:
            print(f"⏭️ Bỏ qua (không có file IPA): {tag}")
            if tag in old_metadata:
                new_metadata[tag] = {**old_metadata[tag], "screenshots": screenshots}
            continue

        # Đã cache và asset chưa thay đổi → bỏ qua
        if tag in old_metadata and old_metadata[tag].get('asset_id') == ipa_asset['id']:
            print(f"⏭️ Bỏ qua (đã có cache): {tag}")
            new_metadata[tag] = {**old_metadata[tag], "screenshots": screenshots}
            continue

        print(f"📝 Xử lý: {tag}")

        # Tải IPA
        local_ipa = os.path.join(TEMP_IPA_DIR, ipa_asset['name'])
        if not _download_ipa(ipa_asset, local_ipa):
            continue

        # Đọc thông tin từ IPA
        ipa_info = get_ipa_info(local_ipa)
        if not ipa_info:
            print(f"   ❌ Không thể đọc thông tin từ IPA")
            os.remove(local_ipa)
            continue

        # Trích xuất icon
        icon_url  = f"{ICONS_DIR}/{tag}.png"
        has_icon  = extract_icon(local_ipa, icon_url)

        # Xây dựng entry metadata
        entry = _build_entry(rel, tag, ipa_info, ipa_asset, has_icon, icon_url, screenshots)
        new_metadata[tag] = entry

        print(f"   ✓ Tên:     {entry['name']}")
        print(f"   ✓ Danh mục: {entry['category']}")
        print(f"   ✓ ID:      {entry['id']}")
        print(f"   ✓ Version: {entry['ver']}")

        # Dọn file IPA tạm
        try:
            os.remove(local_ipa)
        except OSError:
            pass

    if new_metadata:
        save_metadata(new_metadata)
        return True
    return False