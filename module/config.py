"""
Cấu hình chung cho App Store Build Script.
Thay đổi các giá trị tại đây để tuỳ chỉnh cho repository của bạn.
"""

import os

# ── GitHub ──────────────────────────────────────────────────────
GITHUB_USERNAME = "phucwibu0k"
REPO_NAME       = "my-app-store"
GITHUB_API      = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/releases"

# ── Đường dẫn file / thư mục ────────────────────────────────────
METADATA_FILE    = "app_metadata.json"
ICONS_DIR        = "icons"
TEMP_IPA_DIR     = "temp_ipas"
SCREENSHOTS_DIR  = "screenshots"
OUTPUT_HTML      = "index.html"


def get_github_token() -> str | None:
    """Lấy GitHub Personal Access Token từ biến môi trường GITHUB_TOKEN."""
    return os.environ.get("GITHUB_TOKEN")
