from sqladmin import BaseView, expose
from fastapi import Request
from starlette.responses import HTMLResponse, RedirectResponse
from utils.utils import decode_token
import config


class BulkUploadAdminView(BaseView):
    name = "⚡ Nạp Hàng Loạt (1000+)"
    icon = "fa-solid fa-cloud-arrow-up"

    def is_accessible(self, request: Request) -> bool:
        try:
            token = request.session.get("token")
            return bool(token and decode_token(token))
        except Exception:
            return False

    def is_visible(self, request: Request) -> bool:
        try:
            token = request.session.get("token")
            return bool(token and decode_token(token))
        except Exception:
            return False

    @expose("/bulk-upload", methods=["GET"])
    async def bulk_upload_page(self, request: Request):
        try:
            token = request.session.get("token")
        except Exception:
            token = None

        if not token or not decode_token(token):
            return RedirectResponse(url="/admin/login", status_code=302)

        webhook_host = (config.WEBHOOK_HOST or "https://shopcl.onrender.com").rstrip("/")
        api_upload = "/api/items/bulk-upload"
        api_key = config.SQLADMIN_RAW_PASSWORD or "MatKhauAdminCuaBan123"
        admin_token = token or ""

        from db import get_db_session
        from models.category import Category
        from models.subcategory import Subcategory
        from models.item import Item
        from sqlalchemy import select, func
        import html as html_lib

        async with get_db_session() as session:
            cat_stmt = select(Category).order_by(Category.name)
            categories = (await session.execute(cat_stmt)).scalars().all()

            stats_stmt = (
                select(
                    Subcategory.name.label("subcategory_name"),
                    Category.name.label("category_name"),
                    func.count(Item.id).filter(Item.is_sold == False).label("live_count"),
                    func.count(Item.id).filter(Item.is_sold == True).label("sold_count"),
                    func.max(Item.price).label("latest_price"),
                    func.max(Item.description).label("latest_desc")
                )
                .join(Item, Item.subcategory_id == Subcategory.id, isouter=True)
                .join(Category, Item.category_id == Category.id, isouter=True)
                .group_by(Subcategory.name, Category.name)
                .order_by(Subcategory.name.asc())
            )
            rows = (await session.execute(stats_stmt)).all()

        subcat_dict = {}
        for r in rows:
            name = r.subcategory_name
            if not name:
                continue
            if name not in subcat_dict:
                subcat_dict[name] = {
                    "name": name,
                    "category": r.category_name or "",
                    "live_count": int(r.live_count or 0),
                    "sold_count": int(r.sold_count or 0),
                    "price": float(r.latest_price or 0.25),
                    "description": r.latest_desc or "Clone Facebook chất lượng cao, bao login, 2FA đầy đủ"
                }
            else:
                subcat_dict[name]["live_count"] += int(r.live_count or 0)
                subcat_dict[name]["sold_count"] += int(r.sold_count or 0)
                if r.category_name and not subcat_dict[name]["category"]:
                    subcat_dict[name]["category"] = r.category_name

        cat_options_html = ""
        for c in categories:
            cat_options_html += f'<option value="{html_lib.escape(c.name)}">{html_lib.escape(c.name)}</option>\n'

        subcat_options_html = ""
        table_rows_html = ""
        if not subcat_dict:
            table_rows_html = '<tr><td colspan="6" class="text-center text-muted py-4">Chưa có sản phẩm nào trong kho. Hãy tạo danh mục con bên dưới để bắt đầu nạp hàng!</td></tr>'
        else:
            for name, data in subcat_dict.items():
                esc_name = html_lib.escape(name)
                esc_cat = html_lib.escape(data["category"] or "Chưa gán")
                esc_desc = html_lib.escape(data["description"])
                price_val = data["price"]
                live_val = data["live_count"]
                sold_val = data["sold_count"]

                subcat_options_html += (
                    f'<option value="{esc_name}" data-price="{price_val}" data-stock="{live_val}" '
                    f'data-category="{esc_cat}" data-desc="{esc_desc}">'
                    f'{esc_name} (Còn {live_val:,} acc LIVE | ${price_val:g})</option>\n'
                )

                status_badge = (
                    f'<span class="badge bg-success"><i class="fa-solid fa-circle-check me-1"></i>Còn {live_val:,} LIVE</span>'
                    if live_val > 0 else
                    f'<span class="badge bg-secondary"><i class="fa-solid fa-circle-xmark me-1"></i>Hết hàng (0)</span>'
                )

                table_rows_html += f"""
                    <tr>
                        <td class="fw-bold text-dark"><i class="fa-solid fa-folder-open text-primary me-2"></i>{esc_name}</td>
                        <td><span class="badge bg-light text-dark border">{esc_cat}</span></td>
                        <td class="fw-bold text-success">${price_val:g}</td>
                        <td>{status_badge}</td>
                        <td class="text-muted">{sold_val:,} acc</td>
                        <td class="text-end">
                            <button type="button" class="btn btn-sm btn-outline-primary"
                                    onclick="quickSelectSubcat('{esc_name}')">
                                <i class="fa-solid fa-cloud-arrow-up me-1"></i> Nạp thêm
                            </button>
                        </td>
                    </tr>
                """

        html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ Nạp Hàng Hàng Loạt (1.000 - 10.000 Tài Khoản) - Bubba Gump</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {{ background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1e293b; }}
        .card {{ border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 24px; background: #fff; }}
        .card-header {{ background-color: #ffffff; border-bottom: 1px solid #f1f5f9; font-weight: 600; padding: 14px 20px; }}
        .step-badge {{ display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: #0d6efd; color: #fff; font-size: 14px; font-weight: bold; margin-right: 8px; }}
        .code-box {{ background-color: #0f172a; color: #38bdf8; padding: 14px 18px; border-radius: 8px; font-family: Consolas, monospace; font-size: 13px; position: relative; }}
        .copy-btn {{ position: absolute; top: 10px; right: 10px; }}
        .dropzone {{ border: 2px dashed #0d6efd; border-radius: 10px; padding: 25px; text-align: center; background-color: #f0f7ff; cursor: pointer; transition: all 0.2s; }}
        .dropzone:hover {{ background-color: #e0efff; border-color: #0b5ed7; }}
        .counter-badge {{ font-size: 1rem; font-weight: 600; padding: 8px 16px; border-radius: 20px; }}
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4 shadow-sm">
        <div class="container-fluid px-4">
            <a class="navbar-brand fw-bold" href="/admin">
                <i class="fa-solid fa-shrimp text-warning me-2"></i>Bubba Gump Admin
            </a>
            <div class="d-flex gap-2">
                <a href="/admin/item/list" class="btn btn-outline-light btn-sm">
                    <i class="fa-solid fa-boxes-stacked me-1"></i> Quản Lý Kho Hàng
                </a>
                <a href="/admin/settings" class="btn btn-outline-info btn-sm">
                    <i class="fa-solid fa-sliders me-1"></i> Cài Đặt Shop
                </a>
                <a href="/admin" class="btn btn-secondary btn-sm">
                    <i class="fa-solid fa-arrow-left me-1"></i> Quay lại Admin
                </a>
            </div>
        </div>
    </nav>

    <div class="container pb-5">
        <div class="d-flex align-items-center justify-content-between mb-4">
            <div>
                <h3 class="fw-bold text-dark mb-1">
                    <i class="fa-solid fa-cloud-arrow-up text-primary me-2"></i>⚡ Nạp Hàng Hàng Loạt (Bulk Upload 1.000+ Nick)
                </h3>
                <p class="text-muted mb-0">Nhập cùng lúc hàng nghìn clone/via Facebook hoặc tài khoản số. Tự động tách dòng, quét live và lưu vào kho!</p>
            </div>
            <div>
                <a href="/admin/item/list" class="btn btn-outline-primary">
                    <i class="fa-solid fa-box-archive me-1"></i> Xem danh sách kho ({len(categories)} danh mục)
                </a>
            </div>
        </div>

        <!-- Banner giải thích -->
        <div class="alert alert-primary d-flex align-items-center mb-4 shadow-sm" role="alert">
            <i class="fa-solid fa-circle-info fs-3 me-3"></i>
            <div>
                <b>Không còn phải bấm tạo từng tài khoản một!</b>
                Bạn chỉ cần chọn file <code>.txt</code> từ máy tính hoặc dán 1.000 - 10.000 dòng tài khoản (mỗi dòng 1 nick: <code>UID|Pass|2FA...</code>). Hệ thống sẽ tự động tách dòng, lọc nick DIE và lưu toàn bộ vào kho hàng chỉ với 1 click chuột!
            </div>
        </div>

        <!-- BẢNG TỔNG QUAN KHO HÀNG (ĐÃ GỘP GỌN THEO MỤC CON) -->
        <div class="card shadow-sm mb-4">
            <div class="card-header bg-white d-flex justify-content-between align-items-center py-3">
                <div class="fw-bold fs-6 text-primary">
                    <i class="fa-solid fa-boxes-stacked me-2"></i>📊 TỔNG QUAN KHO HÀNG HIỆN TẠI (TẤT CẢ DANH MỤC CON)
                </div>
                <span class="badge bg-info text-dark px-3 py-2">
                    <i class="fa-solid fa-layer-group me-1"></i> Gộp theo loại hàng - Hiển thị số lượng nick LIVE & Giá bán
                </span>
            </div>
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="table-light">
                        <tr>
                            <th>Loại Clone (Mục Con)</th>
                            <th>Danh Mục</th>
                            <th>Giá Bán</th>
                            <th>Số Lượng LIVE Trong Kho</th>
                            <th>Đã Bán</th>
                            <th class="text-end">Hành Động</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="row">
            <!-- Cột trái: Form cấu hình & nạp hàng -->
            <div class="col-lg-8">
                <!-- BƯỚC 1: THÔNG TIN SẢN PHẨM -->
                <div class="card shadow-sm">
                    <div class="card-header bg-white">
                        <span class="step-badge">1</span>
                        <b>Thông Tin Sản Phẩm & Danh Mục</b>
                    </div>
                    <div class="card-body">
                        <div class="row g-3">
                            <!-- Danh mục chính -->
                            <div class="col-md-6">
                                <label class="form-label fw-bold">Danh Mục Chính (Category):</label>
                                <select id="categorySelect" class="form-select" onchange="handleCatChange()">
                                    <option value="">-- Chọn danh mục có sẵn --</option>
                                    {cat_options_html}
                                    <option value="__NEW__" class="fw-bold text-primary">➕ Tạo danh mục mới...</option>
                                </select>
                                <input type="text" id="newCategoryInput" class="form-control mt-2" placeholder="Nhập tên danh mục mới (vd: Clone Facebook, VIA Ngoại...)" style="display:none;">
                            </div>

                            <!-- Danh mục con -->
                            <div class="col-md-6">
                                <label class="form-label fw-bold">Danh Mục Con (Subcategory):</label>
                                <select id="subcategorySelect" class="form-select" onchange="handleSubcatChange()">
                                    <option value="">-- Chọn mục con có sẵn --</option>
                                    {subcat_options_html}
                                    <option value="__NEW__" class="fw-bold text-primary">➕ Tạo mục con mới...</option>
                                </select>
                                <input type="text" id="newSubcategoryInput" class="form-control mt-2" placeholder="Nhập tên mục con mới (vd: Clone US ngâm 6 tháng, VIA 902...)" style="display:none;">
                                <div id="subcatInfoBadge" class="alert alert-success py-2 px-3 mt-2 small" style="display:none;"></div>
                            </div>

                            <!-- Giá bán ($) -->
                            <div class="col-md-6">
                                <label class="form-label fw-bold">Giá Bán Mỗi Tài Khoản ($ USD):</label>
                                <div class="input-group">
                                    <span class="input-group-text">$</span>
                                    <input type="number" id="itemPrice" class="form-control" value="0.25" step="0.01" min="0.001" oninput="updateRatePreview()">
                                </div>
                                <div class="form-text text-success fw-semibold" id="priceVndPreview">
                                    ≈ 6,546 VNĐ / tài khoản (theo tỷ giá USDT ~26,185đ)
                                </div>
                            </div>

                            <!-- Mô tả sản phẩm -->
                            <div class="col-md-6">
                                <label class="form-label fw-bold">Mô Tả Sản Phẩm:</label>
                                <input type="text" id="itemDescription" class="form-control" value="Clone Facebook chất lượng cao, bao login, 2FA đầy đủ" placeholder="Nhập mô tả cho khách mua thấy...">
                            </div>
                        </div>
                    </div>
                </div>

                <!-- BƯỚC 2: NHẬP DANH SÁCH 1000 TÀI KHOẢN -->
                <div class="card shadow-sm" id="uploadStep2Card">
                    <div class="card-header bg-white d-flex justify-content-between align-items-center">
                        <div>
                            <span class="step-badge">2</span>
                            <b>Nhập Danh Sách Tài Khoản (Hỗ trợ 1.000 - 10.000 Nick)</b>
                        </div>
                        <span id="counterBadge" class="badge bg-secondary counter-badge">
                            <i class="fa-solid fa-calculator me-1"></i> <span id="detectedCount">0</span> tài khoản
                        </span>
                    </div>
                    <div class="card-body">
                        <!-- Cách 1: Chọn file .txt -->
                        <div class="dropzone mb-3" onclick="document.getElementById('txtFileInput').click()">
                            <i class="fa-solid fa-file-arrow-up fs-2 text-primary mb-2"></i>
                            <div class="fw-bold text-primary">Bấm vào đây để CHỌN FILE .TXT từ máy tính</div>
                            <div class="text-muted small">Hỗ trợ file .txt chứa 1.000 đến 10.000 dòng tài khoản (định dạng UID|Pass|2FA...)</div>
                            <input type="file" id="txtFileInput" accept=".txt,.csv" style="display:none;" onchange="handleFileSelect(this)">
                        </div>

                        <div id="fileInfoAlert" class="alert alert-success py-2 mb-3" style="display:none;">
                            <i class="fa-solid fa-circle-check me-1"></i> <span id="fileInfoText"></span>
                        </div>

                        <!-- Cách 2: Khung Textarea dán trực tiếp -->
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <label class="form-label fw-bold mb-0">Hoặc Dán Danh Sách Trực Tiếp Tại Đây (Mỗi dòng 1 nick):</label>
                            <div class="btn-group btn-group-sm">
                                <button type="button" class="btn btn-outline-secondary" onclick="pasteFromClipboard()">
                                    <i class="fa-solid fa-paste me-1"></i> Dán từ Clipboard
                                </button>
                                <button type="button" class="btn btn-outline-danger" onclick="clearTextarea()">
                                    <i class="fa-solid fa-trash-can me-1"></i> Xóa trắng
                                </button>
                            </div>
                        </div>

                        <textarea id="rawItemsInput" class="form-control font-monospace" rows="13" style="font-size: 13px; line-height: 1.45;" placeholder="Dán 1.000 tài khoản vào đây, mỗi dòng một tài khoản.&#10;Ví dụ:&#10;10008892182|Pass123|2FA_CODE|mail@domain.com|mailpass&#10;10008892183|Pass456|2FA_CODE|mail@domain.com|mailpass&#10;10008892184|Pass789|2FA_CODE|mail@domain.com|mailpass&#10;..." oninput="updateLineCount()"></textarea>
                    </div>
                </div>

                <!-- BƯỚC 3: CHECK LIVE FACEBOOK & NẠP VÀO KHO -->
                <div class="card shadow-sm">
                    <div class="card-header bg-white">
                        <span class="step-badge">3</span>
                        <b>Tùy Chọn Quét Live Facebook & Hoàn Tất</b>
                    </div>
                    <div class="card-body">
                        <div class="form-check form-switch mb-2">
                            <input class="form-check-input" type="checkbox" id="checkLiveSwitch" checked>
                            <label class="form-check-label fw-bold" for="checkLiveSwitch">
                                <i class="fa-brands fa-facebook text-primary me-1"></i> Tự động Check Live Facebook qua Graph API
                            </label>
                            <div class="form-text">Hệ thống sẽ kiểm tra từng UID xem còn sống (LIVE) hay đã DIE.</div>
                        </div>

                        <div class="form-check form-switch mb-3">
                            <input class="form-check-input" type="checkbox" id="deleteDieSwitch" checked>
                            <label class="form-check-label fw-bold" for="deleteDieSwitch">
                                <i class="fa-solid fa-filter-circle-xmark text-danger me-1"></i> Tự động Loại Bỏ & Xóa Nick DIE (Chỉ nạp tài khoản LIVE vào kho)
                            </label>
                            <div class="form-text">Những tài khoản DIE sẽ bị loại bỏ ngay, khách mua luôn nhận được nick sống 100%.</div>
                        </div>

                        <button id="btnSubmitUpload" class="btn btn-primary btn-lg w-100 py-3 fw-bold fs-5 shadow" onclick="startBulkUpload()">
                            <i class="fa-solid fa-rocket me-2"></i> BẮT ĐẦU NẠP VÀO KHO HÀNG
                        </button>

                        <!-- Vùng hiển thị tiến trình và kết quả -->
                        <div id="uploadProgressBox" class="mt-4" style="display:none;"></div>
                    </div>
                </div>
            </div>

            <!-- Cột phải: Hướng dẫn & Tích hợp API tự động -->
            <div class="col-lg-4">
                <!-- Card xem nhanh kho -->
                <div class="card shadow-sm border-primary">
                    <div class="card-body">
                        <h5 class="fw-bold text-primary mb-2">
                            <i class="fa-solid fa-warehouse me-1"></i> Quản Lý Kho Nhanh
                        </h5>
                        <p class="text-muted small mb-3">Sau khi nạp hàng, bạn có thể kiểm tra danh sách kho hàng, xuất file Excel hoặc chỉnh sửa giá.</p>
                        <a href="/admin/item/list" class="btn btn-primary w-100 mb-2">
                            <i class="fa-solid fa-boxes-stacked me-1"></i> Mở Danh Sách Kho Hàng
                        </a>
                        <a href="/admin/settings" class="btn btn-outline-secondary w-100">
                            <i class="fa-solid fa-sliders me-1"></i> Cài Đặt Tự Động Facebook
                        </a>
                    </div>
                </div>

                <!-- Card Định dạng clone Facebook -->
                <div class="card shadow-sm">
                    <div class="card-header bg-white fw-bold">
                        <i class="fa-brands fa-facebook text-primary me-1"></i> Các Định Dạng Clone Được Hỗ Trợ
                    </div>
                    <div class="card-body small">
                        <p class="mb-2">Hệ thống tự động nhận diện UID Facebook theo mọi định dạng phổ biến trên thị trường:</p>
                        <ul class="list-unstyled mb-0 font-monospace">
                            <li class="mb-1 text-primary">✓ UID|Pass</li>
                            <li class="mb-1 text-primary">✓ UID|Pass|2FA</li>
                            <li class="mb-1 text-primary">✓ UID|Pass|2FA|Mail|PassMail</li>
                            <li class="mb-1 text-primary">✓ UID|Pass|2FA|Cookie|Token</li>
                            <li class="mb-1 text-primary">✓ UID:Pass:2FA...</li>
                        </ul>
                    </div>
                </div>

                <!-- Card API cho Tool Reg / Nuôi Nick -->
                <div class="card shadow-sm">
                    <div class="card-header bg-white fw-bold">
                        <i class="fa-solid fa-code text-success me-1"></i> API Nạp Hàng Tự Động (Dành Cho Tool)
                    </div>
                    <div class="card-body small">
                        <p class="mb-2">Nếu bạn dùng Tool reg nick hoặc tool nuôi clone, có thể gọi API sau để tự động đẩy nick vào shop:</p>

                        <div class="mb-2 fw-semibold">Endpoint:</div>
                        <div class="code-box mb-3" style="padding: 8px 12px; font-size: 11px;">
                            POST {api_upload}
                        </div>

                        <div class="mb-2 fw-semibold">Python Script mẫu:</div>
                        <div class="code-box" style="font-size: 11px; max-height: 220px; overflow-y: auto;">
import requests

url = "{api_upload}"
headers = {{"X-API-KEY": "{api_key}"}}
data = {{
    "category_name": "Facebook Clone",
    "subcategory_name": "Clone US 2FA",
    "price": 0.25,
    "description": "Bao login, 2FA đầy đủ",
    "items": [
        "10008892182|Pass123|2FACODE",
        "10008892183|Pass456|2FACODE"
    ],
    "check_live": True,
    "delete_die": True
}}
r = requests.post(url, json=data, headers=headers)
print(r.json())
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const API_UPLOAD_URL = "{api_upload}";
        const API_KEY = "{api_key}";

        function updateRatePreview() {{
            const price = parseFloat(document.getElementById('itemPrice').value) || 0;
            const vnd = Math.round(price * 26185);
            document.getElementById('priceVndPreview').innerText = '≈ ' + vnd.toLocaleString('vi-VN') + ' VNĐ / tài khoản (theo tỷ giá USDT ~26,185đ)';
        }}

        function handleCatChange() {{
            const sel = document.getElementById('categorySelect');
            const inp = document.getElementById('newCategoryInput');
            if (sel.value === '__NEW__') {{
                inp.style.display = 'block';
                inp.focus();
            }} else {{
                inp.style.display = 'none';
            }}
        }}

        function handleSubcatChange() {{
            const sel = document.getElementById('subcategorySelect');
            const inp = document.getElementById('newSubcategoryInput');
            const infoBadge = document.getElementById('subcatInfoBadge');
            if (sel.value === '__NEW__') {{
                inp.style.display = 'block';
                inp.focus();
                if (infoBadge) infoBadge.style.display = 'none';
            }} else {{
                inp.style.display = 'none';
                const opt = sel.options[sel.selectedIndex];
                if (opt && opt.dataset && opt.dataset.price) {{
                    // TỰ ĐỘNG ĐIỀN GIÁ CŨ & MÔ TẢ ĐÃ CÓ - KHÔNG CẦN NHẬP LẠI
                    document.getElementById('itemPrice').value = opt.dataset.price;
                    updateRatePreview();
                    if (opt.dataset.desc) {{
                        document.getElementById('itemDescription').value = opt.dataset.desc;
                    }}
                    if (opt.dataset.category) {{
                        const catSel = document.getElementById('categorySelect');
                        for (let i = 0; i < catSel.options.length; i++) {{
                            if (catSel.options[i].value === opt.dataset.category) {{
                                catSel.selectedIndex = i;
                                handleCatChange();
                                break;
                            }}
                        }}
                    }}
                    if (infoBadge) {{
                        const stockNum = Number(opt.dataset.stock || 0);
                        infoBadge.innerHTML = `<i class="fa-solid fa-circle-check text-success me-1"></i> Mục con <b>${opt.value}</b> đã có sẵn giá bán <b>$${opt.dataset.price}</b>, hiện còn <b>${stockNum.toLocaleString('vi-VN')} nick LIVE</b> trong kho. Bạn chỉ cần dán thêm nick bên dưới là xong!`;
                        infoBadge.style.display = 'block';
                    }}
                }} else {{
                    if (infoBadge) infoBadge.style.display = 'none';
                }}
            }}
        }}

        function quickSelectSubcat(name) {{
            const sel = document.getElementById('subcategorySelect');
            for (let i = 0; i < sel.options.length; i++) {{
                if (sel.options[i].value === name) {{
                    sel.selectedIndex = i;
                    handleSubcatChange();
                    const step2 = document.getElementById('uploadStep2Card');
                    if (step2) step2.scrollIntoView({{ behavior: 'smooth' }});
                    const rawInp = document.getElementById('rawItemsInput');
                    if (rawInp) rawInp.focus();
                    break;
                }}
            }}
        }}

        function getSelectedCategory() {{
            const sel = document.getElementById('categorySelect');
            if (sel.value === '__NEW__') {{
                return document.getElementById('newCategoryInput').value.trim();
            }}
            return sel.value.trim();
        }}

        function getSelectedSubcategory() {{
            const sel = document.getElementById('subcategorySelect');
            if (sel.value === '__NEW__') {{
                return document.getElementById('newSubcategoryInput').value.trim();
            }}
            return sel.value.trim();
        }}

        function getLines() {{
            const text = document.getElementById('rawItemsInput').value;
            return text.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
        }}

        function updateLineCount() {{
            const lines = getLines();
            const count = lines.length;
            document.getElementById('detectedCount').innerText = count.toLocaleString('vi-VN');
            const badge = document.getElementById('counterBadge');
            if (count > 0) {{
                badge.className = 'badge bg-success counter-badge';
            }} else {{
                badge.className = 'badge bg-secondary counter-badge';
            }}
        }}

        function clearTextarea() {{
            document.getElementById('rawItemsInput').value = '';
            document.getElementById('fileInfoAlert').style.display = 'none';
            updateLineCount();
        }}

        async function pasteFromClipboard() {{
            try {{
                const text = await navigator.clipboard.readText();
                if (text) {{
                    const cur = document.getElementById('rawItemsInput').value;
                    document.getElementById('rawItemsInput').value = (cur ? cur + '\\n' : '') + text;
                    updateLineCount();
                }}
            }} catch (err) {{
                alert('Không thể đọc Clipboard tự động. Vui lòng nhấn phím Ctrl + V trực tiếp vào ô văn bản!');
            }}
        }}

        function handleFileSelect(input) {{
            const file = input.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function(e) {{
                const content = e.target.result;
                document.getElementById('rawItemsInput').value = content;
                updateLineCount();

                const lines = getLines();
                document.getElementById('fileInfoText').innerHTML = '<b>Đã đọc file:</b> ' + file.name + ' (' + lines.length.toLocaleString('vi-VN') + ' tài khoản)';
                document.getElementById('fileInfoAlert').style.display = 'block';
            }};
            reader.readAsText(file);
        }}

        async function startBulkUpload() {{
            const catName = getSelectedCategory();
            const subcatName = getSelectedSubcategory();
            const price = parseFloat(document.getElementById('itemPrice').value);
            const desc = document.getElementById('itemDescription').value.trim() || 'Tài khoản chất lượng cao';
            const lines = getLines();
            const checkLive = document.getElementById('checkLiveSwitch').checked;
            const deleteDie = document.getElementById('deleteDieSwitch').checked;

            if (!catName) {{
                alert('Vui lòng chọn hoặc nhập tên Danh Mục Chính!');
                return;
            }}
            if (!subcatName) {{
                alert('Vui lòng chọn hoặc nhập tên Danh Mục Con!');
                return;
            }}
            if (isNaN(price) || price <= 0) {{
                alert('Giá bán phải lớn hơn 0 $!');
                return;
            }}
            if (lines.length === 0) {{
                alert('Danh sách tài khoản trống! Vui lòng chọn file .txt hoặc dán danh sách tài khoản.');
                return;
            }}

            const btn = document.getElementById('btnSubmitUpload');
            const progressBox = document.getElementById('uploadProgressBox');

            btn.disabled = true;
            btn.innerHTML = '<i class=\"fa-solid fa-spinner fa-spin me-2\"></i> Đang xử lý nạp ' + lines.length.toLocaleString('vi-VN') + ' tài khoản vào kho...';

            progressBox.style.display = 'block';
            progressBox.innerHTML = `
                <div class=\"alert alert-info py-3 shadow-sm\">
                    <div class=\"d-flex align-items-center mb-2\">
                        <div class=\"spinner-border spinner-border-sm text-primary me-2\" role=\"status\"></div>
                        <b>Hệ thống đang xử lý:</b>
                    </div>
                    <ul class=\"mb-0 small\">
                        <li>Đang kiểm tra ` + lines.length.toLocaleString('vi-VN') + ` tài khoản...</li>
                        ` + (checkLive ? '<li>Đang kết nối Facebook Graph API để quét Live/Die...</li>' : '<li>Chế độ nạp nhanh (bỏ qua check live)...</li>') + `
                        <li>Đang lưu trữ dữ liệu vào database Supabase...</li>
                    </ul>
                </div>
            `;

            try {{
                const payload = {{
                    category_name: catName,
                    subcategory_name: subcatName,
                    price: price,
                    description: desc,
                    items: lines,
                    check_live: checkLive,
                    delete_die: deleteDie
                }};

                const res = await fetch(API_UPLOAD_URL, {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-API-KEY': API_KEY,
                        'Authorization': "Bearer {admin_token}"
                    }},
                    credentials: 'include',
                    body: JSON.stringify(payload)
                }});

                const data = await res.json();

                if (res.ok) {{
                    const liveCount = data.live_count || data.uploaded_count || lines.length;
                    const dieCount = data.die_count || data.dead_removed_count || 0;

                    progressBox.innerHTML = `
                        <div class=\"card border-success shadow\">
                            <div class=\"card-header bg-success text-white fw-bold py-3 fs-5\">
                                <i class=\"fa-solid fa-circle-check me-2\"></i>🎉 NẠP HÀNG THÀNH CÔNG VÀO KHO!
                            </div>
                            <div class=\"card-body\">
                                <h5 class=\"card-title text-success fw-bold\">` + data.message + `</h5>
                                <div class=\"row g-3 my-2 text-center\">
                                    <div class=\"col-md-4\">
                                        <div class=\"p-3 bg-light rounded border\">
                                            <div class=\"text-muted small\">Tổng gửi lên</div>
                                            <div class=\"fs-3 fw-bold text-dark\">` + data.total_submitted.toLocaleString('vi-VN') + `</div>
                                        </div>
                                    </div>
                                    <div class=\"col-md-4\">
                                        <div class=\"p-3 bg-light rounded border border-success\">
                                            <div class=\"text-success small fw-bold\">🟢 Nạp Vào Kho (LIVE)</div>
                                            <div class=\"fs-3 fw-bold text-success\">` + liveCount.toLocaleString('vi-VN') + `</div>
                                        </div>
                                    </div>
                                    <div class=\"col-md-4\">
                                        <div class=\"p-3 bg-light rounded border border-danger\">
                                            <div class=\"text-danger small fw-bold\">🔴 Đã Loại Bỏ (DIE)</div>
                                            <div class=\"fs-3 fw-bold text-danger\">` + dieCount.toLocaleString('vi-VN') + `</div>
                                        </div>
                                    </div>
                                </div>

                                <div class=\"d-flex gap-2 mt-4\">
                                    <a href=\"/admin/item/list\" class=\"btn btn-success btn-lg flex-fill\">
                                        <i class=\"fa-solid fa-boxes-stacked me-2\"></i> Xem Danh Sách Kho Hàng Ngay
                                    </a>
                                    <button class=\"btn btn-outline-secondary btn-lg\" onclick=\"clearFormForNext()\">
                                        <i class=\"fa-solid fa-plus me-1\"></i> Tiếp Tục Nạp Thêm
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;

                    // Xoa textarea de tranh an nham lan 2
                    document.getElementById('rawItemsInput').value = '';
                    updateLineCount();
                }} else {{
                    progressBox.innerHTML = `
                        <div class=\"alert alert-danger py-3 shadow-sm\">
                            <h5 class=\"fw-bold mb-1\"><i class=\"fa-solid fa-triangle-exclamation me-2\"></i> Nạp Hàng Thất Bại</h5>
                            <div>` + (data.detail || JSON.stringify(data)) + `</div>
                        </div>
                    `;
                }}
            }} catch (err) {{
                progressBox.innerHTML = `
                    <div class=\"alert alert-danger py-3 shadow-sm\">
                        <h5 class=\"fw-bold mb-1\"><i class=\"fa-solid fa-triangle-exclamation me-2\"></i> Lỗi Kết Nối</h5>
                        <div>` + err.message + `</div>
                    </div>
                `;
            }} finally {{
                btn.disabled = false;
                btn.innerHTML = '<i class=\"fa-solid fa-rocket me-2\"></i> BẮT ĐẦU NẠP VÀO KHO HÀNG';
            }}
        }}

        function clearFormForNext() {{
            document.getElementById('uploadProgressBox').style.display = 'none';
            document.getElementById('fileInfoAlert').style.display = 'none';
            document.getElementById('rawItemsInput').value = '';
            updateLineCount();
        }}
    </script>
</body>
</html>"""
        return HTMLResponse(content=html_content)
