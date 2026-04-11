#!/usr/bin/env python3
"""
App Store Build Script – entry point.

Thứ tự thực hiện:
  1. Cập nhật metadata từ GitHub Releases   (metadata_store)
  2. Sinh index.html                         (html_generator)
  3. Build React nếu có package.json         (build_react)
"""

import os
import subprocess

from module.html_generator import generate_index_html
from module.metadata_store import update_metadata_from_releases


# ── React build ──────────────────────────────────────────────────

def build_react() -> bool:
    """
    Build ứng dụng React nếu tồn tại package.json.
    Tự động phát hiện pnpm hoặc npm.
    """
    print("\n🔨 Đang build React...")

    if os.path.exists('pnpm-lock.yaml'):
        cmd = 'pnpm build'
        print("📦 Sử dụng pnpm")
    elif os.path.exists('package-lock.json'):
        cmd = 'npm run build'
        print("📦 Sử dụng npm")
    else:
        print("⚠️ Không tìm thấy pnpm-lock.yaml hoặc package-lock.json – bỏ qua bước build React")
        return False

    try:
        result = subprocess.run(cmd, shell=True, cwd=os.getcwd())
        if result.returncode == 0:
            print("✅ Build React thành công")
            return True
        print("❌ Build React thất bại")
        return False
    except Exception as e:
        print(f"❌ Lỗi khi build: {e}")
        return False


# ── Main ─────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("🚀 App Store Build Script")
    print("=" * 60)

    update_metadata_from_releases()   # Bước 1
    generate_index_html()             # Bước 2
    build_react()                     # Bước 3

    print("\n" + "=" * 60)
    print("✅ Hoàn tất!")
    print("=" * 60)


if __name__ == "__main__":
    main()
