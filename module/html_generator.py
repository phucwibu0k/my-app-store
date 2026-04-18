"""
HTML Generator – tạo index.html hiển thị danh sách ứng dụng dạng card.
"""

from .config import OUTPUT_HTML
from .metadata_store import load_metadata

# ── CSS (tách ra để generate_index_html() gọn hơn) ───────────────

_CSS = """
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
        padding: 20px;
    }
    .container { max-width: 1200px; margin: 0 auto; }
    header {
        text-align: center;
        color: white;
        margin-bottom: 40px;
        padding: 30px 0;
    }
    header h1 { font-size: 2.5em; margin-bottom: 10px; }
    header p  { font-size: 1.1em; opacity: 0.9; }

    .apps-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 20px;
    }

    .apps-grid {
        display: grid;
        /* Chỉnh cột lưới cho vừa với thẻ 240px, thêm khoảng trống an toàn */
        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
        gap: 15px;
        justify-items: center; /* Căn giữa các thẻ */
    }

    .app-card {
        background: white;
        border-radius: 12px;
        padding: 0 10px; /* Giảm padding để có không gian cho chữ */
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        cursor: pointer;
        
        /* Cấu hình thẻ ngang 240x60 */
        display: flex;
        flex-direction: row;
        align-items: center;
        width: 240px;
        height: 60px;
        gap: 10px;
        flex-wrap: nowrap; /* Tuyệt đối cấm rớt dòng */
        box-sizing: border-box;
    }
    .app-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.15);
    }

    .app-icon-wrapper { 
        display: flex; 
        flex-shrink: 0; /* Giữ icon không bị móp */
    }
    .app-icon {
        width: 40px; height: 40px; /* Thu nhỏ icon */
        border-radius: 10px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        display: flex; align-items: center; justify-content: center;
        font-size: 1.2em;
        margin: 0;
    }

    /* WRAPPER ĐỘC LẬP CHỨA CHỮ */
    .app-text-wrapper {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: flex-start;
        flex-grow: 1; /* Chiếm hết không gian còn lại */
        min-width: 0; /* Chìa khóa để chữ bị ép lại khi quá dài */
        overflow: hidden;
    }

    .app-name  { 
        font-size: 15px; 
        font-weight: 600; 
        color: #1c1c1e; 
        margin-bottom: 2px; 
        text-align: left; 
        width: 100%;
        
        /* Cắt chữ dài thành dấu ... */
        white-space: nowrap; 
        overflow: hidden; 
        text-overflow: ellipsis; 
    }
    
    .category-badge { 
        padding: 2px 8px; 
        font-size: 9px; 
        margin-bottom: 2px;
        display: inline-block;
    }
    
    .app-info  { 
        font-size: 11px; 
        color: #8e8e93; 
        text-align: left;
        width: 100%;
        white-space: nowrap; 
        overflow: hidden; 
        text-overflow: ellipsis; 
    }

    .filter-tabs {
        display: flex; justify-content: center;
        gap: 10px; margin-bottom: 30px; flex-wrap: wrap;
    }
    .filter-btn {
        padding: 8px 18px;
        border: 2px solid white; background: transparent; color: white;
        border-radius: 25px; cursor: pointer;
        font-size: 0.95em; font-weight: 500;
        transition: all 0.3s;
    }
    .filter-btn:hover, .filter-btn.active { background: white; color: #667eea; }

    .stats { text-align: center; color: white; margin-bottom: 20px; font-size: 0.9em; }

    @media (max-width: 768px) {
        header h1 { font-size: 1.8em; }
        .apps-grid { grid-template-columns: 1fr; }
    }
    .stats { text-align: center; color: white; margin-bottom: 20px; font-size: 0.9em; }

    /* THÊM CSS MỚI CHO THANH TÌM KIẾM TẠI ĐÂY */
    .search-container { text-align: center; margin-bottom: 20px; }
    .search-input {
        padding: 12px 20px; width: 90%; max-width: 400px;
        border-radius: 25px; border: 2px solid rgba(255,255,255,0.5);
        outline: none; font-size: 1em; background: rgba(255,255,255,0.15);
        color: white; transition: all 0.3s ease;
    }
    .search-input::placeholder { color: rgba(255,255,255,0.7); }
    .search-input:focus { border-color: white; background: rgba(255,255,255,0.25); }

    @media (max-width: 768px) {
        header h1 { font-size: 1.8em; }
        .apps-grid { grid-template-columns: 1fr; }
    }
</style>
"""

_JS = """
<script>
    function filterCategory(category) {
        // Xóa nội dung ô tìm kiếm khi bấm lọc
        document.getElementById('searchInput').value = '';
        
        document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
        event.target.classList.add('active');
        document.querySelectorAll('.app-card').forEach(card => {
            card.style.display = (category === 'ALL' || card.dataset.category === category)
                ? 'block' : 'none';
        });
    }

    // THÊM HÀM TÌM KIẾM MỚI
    function searchApps() {
        const keyword = document.getElementById('searchInput').value.toLowerCase();
        
        // Bỏ active của các nút filter
        document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
        
        document.querySelectorAll('.app-card').forEach(card => {
            const appName = card.querySelector('.app-name').innerText.toLowerCase();
            if (appName.includes(keyword)) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    }
</script>
"""


# ── Helpers ──────────────────────────────────────────────────────

def _icon_html(app: dict, name: str) -> str:
    if app.get('has_icon') and app.get('icon_url'):
        return f'<img src="{app["icon_url"]}" alt="{name}" class="app-icon" style="object-fit:cover;">'
    return f'<div class="app-icon">{name[0].upper()}</div>'


def _card_html(tag: str, app: dict) -> str:
    category = app.get('category', 'APP').upper()
    name     = app.get('name', tag)
    ver      = app.get('ver', '1.0.0')
    date     = app.get('date', 'N/A')

    return (
        f'<div class="app-card" data-category="{category}" '
        f'onclick="window.location.href=\'app.html?tag={tag}\'">\n'
        f'    <div class="app-icon-wrapper">{_icon_html(app, name)}</div>\n'
        f'    <div class="app-text-wrapper">\n'
        f'        <div class="app-name">{name}</div>\n'
        f'        <span class="category-badge">{category}</span>\n'
        f'        <div class="app-info">v{ver} • {date}</div>\n'
        f'    </div>\n'
        f'</div>\n'
    )


def _filter_buttons(categories: list[str]) -> str:
    buttons = '<button class="filter-btn active" onclick="filterCategory(\'ALL\')">Tất cả</button>\n'
    for cat in categories:
        buttons += f'<button class="filter-btn" onclick="filterCategory(\'{cat}\')">{cat}</button>\n'
    return buttons


# ── Public ───────────────────────────────────────────────────────

def generate_index_html() -> bool:
    """
    Đọc app_metadata.json rồi tạo index.html với:
      - filter tab theo category
      - card hiển thị icon, tên, version, ngày
      - click card → app.html?tag=...

    Trả về True nếu thành công.
    """
    print(f"\n📄 Đang tạo {OUTPUT_HTML}...")

    metadata = load_metadata()
    if not metadata:
        print("⚠️ Không có metadata")
        return False

    categories = sorted({app.get('category', 'APP').upper() for app in metadata.values()})
    cards_html = "".join(_card_html(tag, app) for tag, app in metadata.items())

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="App Store - Tải các ứng dụng mới nhất">
    <title>App Store</title>
    {_CSS}
</head>
<body>
<div class="container">
    <header>
        <h1>📱 App Store</h1>
        <p>Khám phá các ứng dụng tuyệt vời</p>
    </header>

    <div class="stats">Có {len(metadata)} ứng dụng • {len(categories)} danh mục</div>

    <div class="search-container">
        <input type="text" id="searchInput" class="search-input" placeholder="Tìm kiếm ứng dụng..." onkeyup="searchApps()">
    </div>

    <div class="filter-tabs">
        {_filter_buttons(categories)}
    </div>

    <div class="apps-grid" id="appsContainer">
        {cards_html}
    </div>
</div>
{_JS}
</body>
</html>
"""

    try:
        with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ Tạo {OUTPUT_HTML} với {len(metadata)} apps")
        return True
    except Exception as e:
        print(f"❌ Lỗi khi tạo {OUTPUT_HTML}: {e}")
        return False
