"""
GitHub Client – lấy danh sách Releases và parse release notes.
"""

import json
import re
import urllib.request
from .config import GITHUB_API, get_github_token

# ── Fetch ────────────────────────────────────────────────────────
def fetch_releases() -> list[dict]:
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

# ── Parse Các thẻ (Tags) tùy chỉnh ───────────────────────────────
def parse_category(body: str) -> str:
    if not body: return "APP"
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("#category:"):
            match = re.match(r"#category:\s*(\w+)", line)
            if match: return match.group(1).upper()
    return "APP"

def parse_direct_install(body: str) -> bool:
    if not body: return False
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("#direct_install:"):
            match = re.match(r"#direct_install:\s*(\w+)", line)
            if match: return match.group(1).lower() == "true"
    return False

def parse_external_link(body: str) -> str:
    if not body: return ""
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("#link:"):
            return line.replace("#link:", "").strip()
    return ""

def parse_custom_name(body: str) -> str:
    if not body: return ""
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("#name:"):
            return line.replace("#name:", "").strip()
    return ""

def parse_custom_ver(body: str) -> str:
    if not body: return ""
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("#ver:"):
            return line.replace("#ver:", "").strip()
    return ""

def parse_video(body: str) -> str:
    """Trích xuất link video từ tag #video: (hỗ trợ R2, host ngoài)"""
    if not body: return ""
    for line in body.split("\n"):
        line = line.strip()
        if line.lower().startswith("#video:"):
            # Dùng regex để bóc tách chính xác link URL, tránh dính các ký tự rác của markdown
            match = re.search(r'#video:\s*(https?://[^\s)\]"\'<]+)', line, re.IGNORECASE)
            if match: 
                return match.group(1).strip()
    return ""

def parse_shorten(body: str) -> bool:
    """Trích xuất tag #shorten: true/false. Nếu không có tag này, mặc định trả về False."""
    if not body: return False
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("#shorten:"):
            # Dùng regex lấy chữ true hoặc false đằng sau
            match = re.match(r"#shorten:\s*(\w+)", line)
            if match: 
                return match.group(1).lower() == "true"
    return False

def parse_mini_note(body: str) -> str:
    """Trích xuất tag #mini_note: giới hạn tối đa 15 ký tự. Dài hơn sẽ trả về rỗng."""
    if not body: return ""
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("#mini_note:"):
            # Lấy nội dung phía sau tag
            content = line.replace("#mini_note:", "").strip()
            # Kiểm tra độ dài
            if len(content) <= 15:
                return content
            else:
                return "" # Vượt quá 15 ký tự thì tự động cho rỗng
    return ""

def parse_note(body: str) -> str:
    """Loại bỏ tất cả các dòng metadata để lấy nội dung Note sạch"""
    if not body: return ""
    _META_PREFIXES = ("#category:", "#direct_install:", "#link:", "#name:", "#ver:", "#video:", "#shorten:", "#mini_note:")
    lines = [
        line for line in body.split("\n")
        if not any(line.strip().startswith(prefix) for prefix in _META_PREFIXES)
    ]
    return "\n".join(lines).strip()
