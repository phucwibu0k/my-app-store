"""
Metadata Store – quản lý file app_metadata.json và
điều phối việc cập nhật metadata từ GitHub Releases.
"""
import re
import json
import os
import shutil
import urllib.request
from datetime import datetime

from .config import ICONS_DIR, METADATA_FILE, SCREENSHOTS_DIR, TEMP_IPA_DIR
from .github_client import (
    fetch_releases, parse_category, parse_direct_install, 
    parse_note, parse_external_link, parse_custom_name,
    parse_custom_ver, parse_video, parse_shorten, parse_mini_note
)
from .ipa_parser import extract_icon, get_ipa_info
from .url_shortener import shorten_both

# ── Đọc / Ghi Dữ liệu ────────────────────────────────────────────
def load_metadata() -> dict:
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_metadata(metadata: dict) -> None:
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)
    print(f"✅ Đã cập nhật {METADATA_FILE}")

# ── Logic Xử lý Cập nhật (Smart Sync Hybrid) ─────────────────────
# ── Logic Xử lý Cập nhật (Smart Sync Hybrid) ─────────────────────
def update_metadata_from_releases():
    old_metadata = load_metadata()
    new_metadata = {}
    releases = fetch_releases()

    # Bảo vệ các App cũ được thêm thủ công không qua Release (nếu có)
    for tag, entry in old_metadata.items():
        if not entry.get('asset_id') and not str(entry.get('asset_id', '')).startswith('ext_'):
            new_metadata[tag] = entry

    if not os.path.exists(TEMP_IPA_DIR): os.makedirs(TEMP_IPA_DIR)
    if not os.path.exists(ICONS_DIR): os.makedirs(ICONS_DIR)

    for rel in releases:
        tag = rel.get('tag_name')
        if not tag: continue

        # =========================================================
        # 1. BÓC TÁCH METADATA TỪ VĂN BẢN (RELEASE NOTE)
        # =========================================================
        rel_body = rel.get('body', '')
        remote_note = parse_note(rel_body)
        remote_category = parse_category(rel_body)
        remote_direct = parse_direct_install(rel_body)
        remote_link = parse_external_link(rel_body)
        remote_name_custom = parse_custom_name(rel_body)
        remote_ver_custom = parse_custom_ver(rel_body)
        remote_video = parse_video(rel_body)
        remote_shorten = parse_shorten(rel_body)      # THÊM DÒNG NÀY
        remote_mini_note = parse_mini_note(rel_body)  # THÊM DÒNG NÀY
        
        # =========================================================
        # 2. XỬ LÝ ẢNH (SCREENSHOTS) VÀ FILE ĐÍNH KÈM
        # =========================================================
        assets = rel.get('assets', [])
        ipa_asset = next((a for a in assets if a['name'].lower().endswith('.ipa')), None)
        icon_asset = next((a for a in assets if a['name'].lower() in ('icon.png', 'icon.jpg', 'icon.jpeg')), None)
        
        # A. Ảnh up trực tiếp vào Assets của Release
        screenshot_assets = [
            a['browser_download_url'] for a in assets 
            if a['name'].lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) 
            and a['name'].lower() not in ('icon.png', 'icon.jpg', 'icon.jpeg')
        ]
        
        # B. Ảnh dán link trực tiếp trong nội dung Release (trừ link video đã lấy ở trên)
        embedded_images = re.findall(r'https?://[^\s)\]"\'<]+\.(?:png|jpg|jpeg|webp)', rel_body, flags=re.IGNORECASE)
        
        # Gộp tất cả ảnh lại và loại bỏ trùng lặp
        all_screenshots = list(dict.fromkeys(screenshot_assets + embedded_images))

        # =========================================================
        # 3. LỰA CHỌN ĐƯỜNG LINK CÀI ĐẶT
        # =========================================================
        final_link = remote_link if remote_link else (ipa_asset['browser_download_url'] if ipa_asset else None)

        if not final_link:
            print(f"⚠️ Bỏ qua Release [{tag}]: Không có file .ipa và cũng không có #link:")
            continue

        remote_asset_id = ipa_asset['id'] if ipa_asset else f"ext_{rel['id']}"
        current_entry = old_metadata.get(tag)
        icon_path = f"{ICONS_DIR}/{tag}.png"

        # =====================================================================
        # 4. SMART SYNC 3.0: PHÂN TÍCH ĐA TẦNG (MULTI-TIER ANALYSIS)
        # =====================================================================
        if current_entry:
            # A. KIỂM TRA FILE VẬT LÝ (Có thay file cài đặt không?)
            is_same_file = (
                current_entry.get('asset_id') == remote_asset_id and 
                current_entry.get('link') == final_link
            )

            # B. KIỂM TRA SỨC KHỎE DỮ LIỆU (Có bị lỗi mất hình/mất số không?)
            needs_rescue = False
            if current_entry.get('has_icon') and not os.path.exists(icon_path): needs_rescue = True
            elif not current_entry.get('has_icon'): needs_rescue = True
            elif current_entry.get('ver') in ['N/A', '', None]: needs_rescue = True

            # C. KIỂM TRA METADATA (Text, Ảnh, Video, Thẻ Name/Ver)
            is_same_metadata = (
                current_entry.get('note') == remote_note and
                current_entry.get('category') == remote_category and
                current_entry.get('direct_install') == remote_direct and
                current_entry.get('video') == remote_video and
                current_entry.get('screenshots') == all_screenshots and
                current_entry.get('shorten') == remote_shorten and       # THÊM DÒNG NÀY
                current_entry.get('mini_note') == remote_mini_note       # THÊM DÒNG NÀY
            )
            # Nếu trên Release có gắn thẻ #name/#ver mà dưới JSON không khớp -> Metadata đã thay đổi
            if remote_name_custom and current_entry.get('name') != remote_name_custom: is_same_metadata = False
            if remote_ver_custom and current_entry.get('ver') != remote_ver_custom: is_same_metadata = False

            # -----------------------------------------------------------
            # TẦNG 1: HOÀN HẢO (BỎ QUA)
            # -----------------------------------------------------------
            if is_same_file and is_same_metadata and not needs_rescue:
                print(f"⏩ Tầng 1 (Skip) [{tag}]: Không có sự thay đổi nào.")
                new_metadata[tag] = current_entry
                continue

            # -----------------------------------------------------------
            # TẦNG 2: SOFT UPDATE (CẬP NHẬT NHẸ)
            # -----------------------------------------------------------
            # File game giữ nguyên, nhưng bạn có sửa lỗi chính tả, đổi ảnh, video hoặc đổi tên/ver
            if is_same_file and not is_same_metadata and not needs_rescue:
                print(f"📝 Tầng 2 (Soft Update) [{tag}]: Cập nhật Ghi chú/Ảnh/Video (Không tải lại IPA)...")
                current_entry['note'] = remote_note
                current_entry['category'] = remote_category
                current_entry['direct_install'] = remote_direct
                current_entry['video'] = remote_video
                current_entry['screenshots'] = all_screenshots
                current_entry['shorten'] = remote_shorten          # THÊM DÒNG NÀY
                current_entry['mini_note'] = remote_mini_note      # THÊM DÒNG NÀY
                
                if remote_name_custom: current_entry['name'] = remote_name_custom
                if remote_ver_custom: current_entry['ver'] = remote_ver_custom

                # Lấy lại custom icon nếu bạn lỡ up đè file icon.png mới trên Release
                if icon_asset:
                    try:
                        urllib.request.urlretrieve(icon_asset['browser_download_url'], icon_path)
                        print(f"   🖼️  Đã kéo Logo cập nhật từ Release.")
                    except: pass

                new_metadata[tag] = current_entry
                continue

            # -----------------------------------------------------------
            # TẦNG 3: HARD UPDATE / RESCUE MODE
            # -----------------------------------------------------------
            if needs_rescue:
                print(f"🚑 Tầng 3 (Rescue) [{tag}]: Dữ liệu lỗi (Mất Icon/Ver), ép tải IPA để mổ xẻ...")
            else:
                print(f"📦 Tầng 3 (Hard Update) [{tag}]: Phát hiện File/Link cài đặt mới...")

        else:
            print(f"🆕 Phát hiện App hoàn toàn mới: {tag}...")

        has_icon = False
        app_name = remote_name_custom if remote_name_custom else rel.get('name', tag)
        app_id = tag
        app_ver = remote_ver_custom if remote_ver_custom else "N/A"

        # BƯỚC A: Lấy Logo thủ công đính kèm Release (CHỈ ÁP DỤNG KHI APP CÓ #link:)
        if remote_link:
            if icon_asset:
                try:
                    urllib.request.urlretrieve(icon_asset['browser_download_url'], icon_path)
                    has_icon = True
                    print(f"   🖼️  Đã tải Logo từ file đính kèm Release (App dùng link ngoài).")
                except Exception as e: print(f"   ⚠️ Lỗi tải custom icon: {e}")
            else:
                print(f"   ⚠️ App dùng link ngoài nhưng chưa đính kèm file icon.png trong Release!")

        # BƯỚC B: Mổ xẻ file IPA (Để lấy Name, Ver, ID và tự động bung Icon)
        if ipa_asset:
            local_ipa = os.path.join(TEMP_IPA_DIR, f"{tag}.ipa")
            try:
                urllib.request.urlretrieve(ipa_asset['browser_download_url'], local_ipa)
                ipa_info = get_ipa_info(local_ipa)
                if ipa_info:
                    if not remote_name_custom: app_name = ipa_info['name']
                    if not remote_ver_custom: app_ver = ipa_info['version']
                    app_id = ipa_info['id']

                # TỰ ĐỘNG BUNG IPA LẤY ICON (CHỈ ÁP DỤNG KHI KHÔNG CÓ #link:)
                if not remote_link:
                    has_icon = extract_icon(local_ipa, icon_path)
                    if has_icon:
                        print(f"   ⚙️ Đã tự động bung file IPA để trích xuất Icon thành công.")
                    else:
                        print(f"   ⚠️ Không tìm thấy icon hợp lệ trong file IPA.")

                if os.path.exists(local_ipa): os.remove(local_ipa)
            except Exception as e:
                print(f"   ❌ Lỗi mổ xẻ IPA {tag}: {e}")


        short_ipa_links = ("", "")
        short_install_links = ("", "")

        if remote_shorten:
            # Rút gọn link tải IPA
            short_ipa_links = shorten_both(final_link)
    
            # Tạo và rút gọn link cài đặt trực tiếp (itms-services)
            short_install_links = ("", "")
            if final_link:
                # Thay đuôi .ipa thành .plist để tạo cấu trúc link cài đặt
                plist_url = final_link.replace('.ipa', '.plist')
                install_url = f"itms-services://?action=download-manifest&url={plist_url}"
                short_install_links = shorten_both(install_url)

        # 5. GHI SỔ VÀO METADATA MỚI
        new_metadata[tag] = {
            "name": app_name,
            "id": app_id,
            "ver": app_ver,
            "tag": tag,
            "category": remote_category,
            "direct_install": remote_direct,
            "note": remote_note,
            "video": remote_video,  # Trường video mới lưu trữ link Cloudflare R2
            "shorten": remote_shorten,      # THÊM DÒNG NÀY
            "mini_note": remote_mini_note,  # THÊM DÒNG NÀY
            "link": final_link,
            "asset_id": remote_asset_id,
            "date": rel.get('published_at', '')[:10].replace('-', '/'),
            "has_icon": has_icon or os.path.exists(icon_path),
            "icon_url": icon_path,
            "screenshots": all_screenshots, # Chứa toàn bộ ảnh (asset + nội dung)
            "short_ipa_1": short_ipa_links[0] if short_ipa_links else "",
            "short_ipa_2": short_ipa_links[1] if short_ipa_links else "",
            "short_install_1": short_install_links[0] if short_install_links else "",
            "short_install_2": short_install_links[1] if short_install_links else ""
        }

    save_metadata(new_metadata)

    if os.path.exists(TEMP_IPA_DIR): shutil.rmtree(TEMP_IPA_DIR)
