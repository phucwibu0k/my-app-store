"""
GitHub Client – lấy danh sách Releases và parse release notes.
"""

import json
import re
import urllib.request
from config import GITHUB_API, get_github_token


# ── Fetch ────────────────────────────────────────────────────────

def fetch_releases() -> list[dict]:
    """
    Lấy toàn bộ releases từ GitHub API.
    Sử dụng GITHUB_TOKEN nếu có để tránh rate-limit.
    """
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


# ── Parse release notes ──────────────────────────────────────────

def parse_category(body: str) -> str:
    """
    Trích xuất category từ release notes.
    Format: #category: GAMES
    Mặc định trả về 'APP'.
    """
    if not body:
        return "APP"

    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("#category:"):
            match = re.match(r"#category:\s*(\w+)", line)
            if match:
                return match.group(1).upper()

    return "APP"


def parse_direct_install(body: str) -> bool:
    """
    Trích xuất direct_install từ release notes.
    Format mong đợi:
        #direct_install: true
        #direct_install: false

    Mặc định trả về False nếu không tìm thấy.
    """
    if not body:
        return False

    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("#direct_install:"):
            match = re.match(r"#direct_install:\s*(true|false)", line, re.IGNORECASE)
            if match:
                return match.group(1).lower() == "true"
    return False


def parse_note(body: str) -> str:
    """
    Trả về nội dung release notes sau khi loại bỏ dòng #category và #direct_install.
    """
    if not body:
        return ""

    lines = [
        line for line in body.split("\n")
        if not line.strip().startswith("#category:") and not line.strip().startswith("#direct_install:")
    ]
    return "\n".join(lines).strip()