"""
URL Shortener – rút ngắn link qua taplayma.com và link4m.co.
Chỉ gọi khi có IPA mới (asset_id thay đổi).
"""

import json
import urllib.error
import urllib.parse
import urllib.request

# Giả định bạn sẽ đổi tên biến trong config.py cho đúng tên dịch vụ
from .config import LINK4M_API, LINK4M_TOKEN, TAPLAYMA_API, TAPLAYMA_TOKEN


def shorten_taplayma(long_url: str) -> str:
    """Rút ngắn link qua taplayma.com. Trả về link ngắn hoặc chuỗi rỗng nếu lỗi."""
    if not TAPLAYMA_TOKEN or TAPLAYMA_TOKEN == "xxx":
        return ""

    params  = {"token": TAPLAYMA_TOKEN, "url": long_url}
    api_url = TAPLAYMA_API + "?" + urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(api_url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == "success":
            return data.get("shortenedUrl", "")
        print(f"   ⚠️ taplayma: {data.get('message', 'lỗi không xác định')}")
    except urllib.error.URLError as e:
        print(f"   ⚠️ taplayma kết nối thất bại: {e.reason}")
    except json.JSONDecodeError:
        print("   ⚠️ taplayma trả về phản hồi không hợp lệ")
    return ""


def shorten_link4m(long_url: str) -> str:
    """Rút ngắn link qua link4m.co. Trả về link ngắn hoặc chuỗi rỗng nếu lỗi."""
    if not LINK4M_TOKEN or LINK4M_TOKEN == "xxx":
        return ""

    # Link4m dùng tham số 'api' thay vì 'tokenUser'
    params: dict = {
        "api": LINK4M_TOKEN,
        "url": long_url,
    }

    api_url = LINK4M_API + "?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/124.0.0.0 Safari/537.36",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        # Link4m trả về status: success và kết quả ở shortenedUrl
        if data.get("status") == "success":
            return data.get("shortenedUrl", "")
            
        print(f"   ⚠️ link4m.co: {data.get('message', 'trả về thất bại')}")
    except urllib.error.URLError as e:
        print(f"   ⚠️ link4m.co kết nối thất bại: {e.reason}")
    except json.JSONDecodeError:
        print("   ⚠️ link4m.co trả về phản hồi không hợp lệ")
    return ""


def shorten_both(long_url: str) -> tuple[str, str]:
    """
    Rút ngắn cùng một URL qua cả 2 dịch vụ.

    Trả về: (link_taplayma, link_link4m)
    Nếu dịch vụ nào lỗi / chưa cấu hình, trả về chuỗi rỗng cho dịch vụ đó.
    """
    link1 = shorten_taplayma(long_url)
    link2 = shorten_link4m(long_url)
    return link1, link2