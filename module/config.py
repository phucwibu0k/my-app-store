"""
Cấu hình chung cho App Store Build Script.
Thay đổi các giá trị tại đây để tuỳ chỉnh cho repository của bạn.
"""

import os

# ── GitHub ──────────────────────────────────────────────────────
GITHUB_USERNAME = "phucwibu0k"
REPO_NAME       = "kho_app"
GITHUB_API      = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/releases?per_page=100"

# ── Đường dẫn file / thư mục ────────────────────────────────────
METADATA_FILE    = "app_metadata.json"
ICONS_DIR        = "icons"
TEMP_IPA_DIR     = "temp_ipas"
SCREENSHOTS_DIR  = "screenshots"
OUTPUT_HTML      = "index.html"

# ── Rút gọn link ────────────────────────────────────────────────
# Thay token thực vào biến môi trường hoặc điền trực tiếp nếu cần.
# Nếu để chuỗi rỗng, bước rút gọn sẽ bị bỏ qua.

TAPLAYMA_TOKEN  = os.environ.get("TAPLAYMA_TOKEN", "")
TAPLAYMA_API    = "https://api.taplayma.com/api"

# Đã chuyển từ layma.net sang link4m.co
LINK4M_TOKEN    = os.environ.get("LINK4M_TOKEN", "")
LINK4M_API      = "https://link4m.co/api-shorten/v2"


def get_github_token() -> str | None:
    """Lấy GitHub Personal Access Token từ biến môi trường GITHUB_TOKEN."""
    return os.environ.get("GITHUB_TOKEN")
