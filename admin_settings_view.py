from sqladmin import BaseView, expose
from fastapi import Request
from starlette.responses import HTMLResponse, RedirectResponse
from utils.utils import decode_token
import config


class PaymentApiConfigView(BaseView):
    name = "Nạp USDT & API"
    icon = "fa-solid fa-sliders"

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

    @expose("/settings", methods=["GET"])
    async def settings_page(self, request: Request):
        # Bat buoc xac thuc dang nhap Admin
        try:
            token = request.session.get("token")
        except Exception:
            token = None

        if not token or not decode_token(token):
            return RedirectResponse(url="/admin/login", status_code=302)

        webhook_host = config.WEBHOOK_HOST or "https://shopcl.onrender.com"
        api_upload_url = f"{webhook_host}/api/items/bulk-upload"
        api_inventory_url = f"{webhook_host}/api/inventory/status"
        api_binance_status = f"{webhook_host}/api/binancepay/status"
        api_binance_check = f"{webhook_host}/api/binancepay/check-now"
        api_key = config.SQLADMIN_RAW_PASSWORD or "MatKhauAdminCuaBan123"

        binance_uid = config.BINANCE_UID or "805398854"
        is_binance_ready = bool(config.BINANCE_API_KEY and config.BINANCE_API_SECRET)
        binance_badge = '<span class="badge bg-success"><i class="fa-solid fa-circle-check me-1"></i> Đang hoạt động tự động</span>' if is_binance_ready else '<span class="badge bg-warning text-dark"><i class="fa-solid fa-triangle-exclamation me-1"></i> Chờ điền API Key & Secret</span>'

        html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cấu Hình Nạp USDT, Binance Pay & REST API - Bubba Gump</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {{ background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1e293b; }}
        .card {{ border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 24px; background: #fff; }}
        .card-header {{ background-color: #ffffff; border-bottom: 1px solid #f1f5f9; font-weight: 600; padding: 14px 20px; }}
        .nav-pills .nav-link {{ color: #475569; font-weight: 500; border-radius: 8px; padding: 10px 16px; margin-right: 8px; transition: all 0.2s; }}
        .nav-pills .nav-link.active {{ background-color: #0d6efd; color: #fff; box-shadow: 0 4px 12px rgba(13,110,253,0.25); }}
        .code-box {{ background-color: #0f172a; color: #f8fafc; padding: 16px; border-radius: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.88rem; position: relative; overflow-x: auto; }}
        .btn-copy {{ position: absolute; top: 10px; right: 10px; z-index: 10; }}
        .step-badge {{ display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: #0d6efd; color: #fff; font-weight: bold; font-size: 0.85rem; margin-right: 8px; }}
        .step-badge.success {{ background: #10b981; }}
        .step-badge.warning {{ background: #f59e0b; }}
        .info-pill {{ background: #eff6ff; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 0 8px 8px 0; margin-bottom: 16px; }}
        .warning-pill {{ background: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 0 8px 8px 0; margin-bottom: 16px; }}
        .success-pill {{ background: #ecfdf5; border-left: 4px solid #10b981; padding: 12px 16px; border-radius: 0 8px 8px 0; margin-bottom: 16px; }}
    </style>
</head>
<body class="p-3 p-md-4">
    <div class="container-fluid" style="max-width: 1400px;">
        <!-- Header -->
        <div class="d-flex flex-wrap justify-content-between align-items-center mb-4 pb-3 border-bottom">
            <div>
                <h3 class="fw-bold mb-1 text-dark"><i class="fa-solid fa-sliders text-primary me-2"></i>Cấu Hình Nạp USDT, Binance Pay & Tool API</h3>
                <p class="text-muted mb-0">Hệ thống nạp hàng tự động bằng Tool / API, Nạp 0% phí qua Binance Pay và Cổng USDT Blockchain</p>
            </div>
            <div class="mt-2 mt-md-0">
                <a href="/admin" class="btn btn-outline-secondary"><i class="fa-solid fa-arrow-left me-1"></i> Quay lại Dashboard</a>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <ul class="nav nav-pills mb-4" id="pills-tab" role="tablist">
            <li class="nav-item">
                <button class="nav-link active" data-bs-toggle="pill" data-bs-target="#tab-fast-upload">
                    <i class="fa-solid fa-bolt text-warning me-1"></i> 1. Nạp Hàng Nhanh & Tool API
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-binance">
                    <i class="fa-brands fa-bitcoin text-warning me-1"></i> 2. Nạp Binance Pay (0% Phí - Nhận 1s)
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-usdt">
                    <i class="fa-solid fa-coins text-success me-1"></i> 3. Nạp USDT Tự Động (KryptoExpress)
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-inventory">
                    <i class="fa-solid fa-boxes-stacked text-info me-1"></i> 4. Xem Tồn Kho & Test API
                </button>
            </li>
        </ul>

        <div class="tab-content" id="pills-tabContent">
            <!-- TAB 1: FORM NẠP HÀNG & API TOOL -->
            <div class="tab-pane fade show active" id="tab-fast-upload">
                <div class="row g-4">
                    <!-- Form nạp trực tiếp -->
                    <div class="col-lg-5">
                        <div class="card border-primary h-100">
                            <div class="card-header bg-primary text-white py-3">
                                <h5 class="card-title mb-0 fw-bold"><i class="fa-solid fa-file-arrow-up me-2"></i>Form Nạp Hàng Nhanh Vào Kho</h5>
                            </div>
                            <div class="card-body">
                                <div class="info-pill small">
                                    Dán danh sách clone Facebook vào đây, hệ thống sẽ tự động tạo danh mục và nạp trực tiếp vào cơ sở dữ liệu Supabase!
                                </div>
                                <form id="fastUploadForm">
                                    <div class="mb-3">
                                        <label class="form-label fw-bold">Danh Mục Chính (Category):</label>
                                        <input type="text" class="form-control" id="formCat" value="Facebook" required>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label fw-bold">Danh Mục Con (Subcategory):</label>
                                        <input type="text" class="form-control" id="formSubcat" value="Clone US 2FA Cổ" placeholder="VD: Clone US 2FA, Clone Seeding, BM Ads..." required>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label fw-bold">Giá bán mỗi tài khoản ($ USD):</label>
                                        <div class="input-group">
                                            <span class="input-group-text">$</span>
                                            <input type="number" step="0.01" class="form-control" id="formPrice" value="1.50" required>
                                        </div>
                                    </div>
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-between align-items-center mb-1">
                                            <label class="form-label fw-bold mb-0">Danh sách tài khoản (Mỗi dòng 1 con):</label>
                                            <span class="badge bg-secondary" id="lineCounter">0 tài khoản</span>
                                        </div>
                                        <textarea class="form-control font-monospace" id="formItems" rows="8" placeholder="100088881|matkhau1|2FA_KEY_1|Cookie_1&#10;100088882|matkhau2|2FA_KEY_2|Cookie_2" oninput="updateLineCount()"></textarea>
                                        <small class="text-muted">Định dạng khuyên dùng: <code>UID|Pass|2FA|Cookie|Email</code></small>
                                    </div>
                                    <button type="button" class="btn btn-success w-100 py-2 fw-bold shadow-sm" onclick="submitUpload()">
                                        <i class="fa-solid fa-bolt me-1"></i> NẠP NGAY VÀO KHO
                                    </button>
                                </form>
                                <div id="uploadResult" class="mt-3" style="display:none;"></div>
                            </div>
                        </div>
                    </div>

                    <!-- Hướng dẫn REST API cho Tool Reg/Nuôi Clone -->
                    <div class="col-lg-7">
                        <div class="card h-100">
                            <div class="card-header py-3 text-primary d-flex justify-content-between align-items-center">
                                <span class="fw-bold"><i class="fa-solid fa-code me-2"></i>Kết Nối REST API Cho Tool Tự Động Nạp Hàng</span>
                                <span class="badge bg-primary">HTTP POST</span>
                            </div>
                            <div class="card-body">
                                <h6 class="fw-bold text-dark mb-2"><i class="fa-solid fa-key text-warning me-1"></i> 1. Cách Lấy Thông Tin API:</h6>
                                <ul>
                                    <li><b>API Endpoint:</b> <code>{api_upload_url}</code></li>
                                    <li><b>Mã X-API-KEY:</b> Chính là mật khẩu đăng nhập Admin của bạn (cấu hình trong biến môi trường Render: <code>SQLADMIN_RAW_PASSWORD</code>).</li>
                                </ul>

                                <div class="mb-3">
                                    <label class="form-label fw-bold small text-muted">URL Endpoint:</label>
                                    <div class="input-group">
                                        <input type="text" class="form-control font-monospace" value="{api_upload_url}" readonly id="inputUrl">
                                        <button class="btn btn-outline-primary" onclick="copyId('inputUrl')"><i class="fa-regular fa-copy"></i> Copy</button>
                                    </div>
                                </div>

                                <div class="mb-3">
                                    <label class="form-label fw-bold small text-muted">X-API-KEY Header:</label>
                                    <div class="input-group">
                                        <input type="password" class="form-control font-monospace" value="{api_key}" readonly id="inputKey">
                                        <button class="btn btn-outline-secondary" type="button" onclick="toggleKeyVisibility()" title="Hi?n/?n"><i class="fa-solid fa-eye" id="eyeIcon"></i></button>
                                        <button class="btn btn-outline-primary" onclick="copyId('inputKey')"><i class="fa-regular fa-copy"></i> Copy</button>
                                    </div>
                                </div>

                                <h6 class="fw-bold text-dark mt-4 mb-2"><i class="fa-solid fa-terminal text-info me-1"></i> 2. Code Python Mẫu (Chạy Trực Tiếp Trong Tool Nuôi/Reg):</h6>
                                <div class="code-box">
                                    <button class="btn btn-sm btn-outline-light btn-copy" onclick="copyPyCode()"><i class="fa-regular fa-copy"></i> Copy Code</button>
                                    <pre style="margin:0; color:#38bdf8;" id="pyCodeText">import requests

url = "{api_upload_url}"
headers = {{
    "Content-Type": "application/json",
    "X-API-KEY": "{api_key}"
}}
payload = {{
    "category_name": "Facebook",
    "subcategory_name": "Clone US 2FA Nuôi Seeding",
    "price": 1.5,
    "description": "Tài khoản Clone Facebook chuẩn US kèm 2FA",
    "items": [
        "1000888801|Password123|2FA_SECRET_KEY|Cookie...",
        "1000888802|Password123|2FA_SECRET_KEY|Cookie..."
    ]
}}

response = requests.post(url, json=payload, headers=headers)
print("Kết quả:", response.json())</pre>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 2: BINANCE PAY (0% PHÍ) -->
            <div class="tab-pane fade" id="tab-binance">
                <div class="card">
                    <div class="card-header py-3 text-warning d-flex justify-content-between align-items-center">
                        <h5 class="card-title mb-0 fw-bold"><i class="fa-brands fa-bitcoin me-2"></i>Nạp Tự Động Bằng Binance Pay (0% Phí - Nhận Ngay 1s)</h5>
                        {binance_badge}
                    </div>
                    <div class="card-body">
                        <div class="success-pill">
                            <b>Ưu điểm vượt trội của Binance Pay:</b><br>
                            • <b>0đ / 0 USDT phí giao dịch</b>: Cả người chuyển và bạn đều hoàn toàn miễn phí 100%.<br>
                            • <b>Nhận ngay trong 1-5 giây</b>: Không cần chờ đợi xác nhận khối Blockchain.<br>
                            • <b>Hạn mức từ 0.01 USDT</b>: Khách nạp bao nhiêu cũng nhận được, tiền về thẳng ví Binance cá nhân của bạn.
                        </div>

                        <!-- Thong tin UID -->
                        <div class="row g-3 my-3">
                            <div class="col-md-4">
                                <div class="p-3 border rounded bg-light">
                                    <div class="small text-muted fw-bold">Binance UID Của Bạn:</div>
                                    <div class="fs-4 fw-bold text-warning font-monospace">{binance_uid}</div>
                                    <small class="text-muted">Tài khoản ví Binance nhận tiền</small>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="p-3 border rounded bg-light">
                                    <div class="small text-muted fw-bold">Trạng Thái Tự Động:</div>
                                    <div class="fs-5 fw-bold text-success mt-1"><i class="fa-solid fa-robot me-1"></i> Background Polling (25s)</div>
                                    <small class="text-muted">Tự quét lịch sử giao dịch và ting ting</small>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="p-3 border rounded bg-light">
                                    <div class="small text-muted fw-bold">Đồng Bộ Nhanh:</div>
                                    <button class="btn btn-warning w-100 mt-1 fw-bold" onclick="syncBinancePay()"><i class="fa-solid fa-rotate me-1"></i> Quét Binance Pay Ngay</button>
                                    <div id="syncResult" class="small mt-1" style="display:none;"></div>
                                </div>
                            </div>
                        </div>

                        <h5 class="fw-bold text-dark mt-4 mb-3"><i class="fa-solid fa-shield-halved text-success me-2"></i>Hướng Dẫn Lấy API Key Binance (Chỉ Đọc - Cực Kỳ An Toàn)</h5>
                        <p class="text-muted">Để Bot có thể đọc lịch sử giao dịch và tự động cộng tiền, bạn chỉ cần tạo 1 API Key <b>chỉ đọc (Enable Reading)</b>:</p>

                        <div class="row g-3">
                            <div class="col-md-6">
                                <div class="border rounded p-3 h-100 bg-light">
                                    <h6 class="fw-bold text-dark"><span class="step-badge">1</span>Tạo API trên Binance</h6>
                                    <ol class="small text-muted ps-3">
                                        <li class="mb-2">Bấm vào avatar tròn cá nhân <b>User-9b21f</b> ở góc trên bên phải trang Binance.</li>
                                        <li class="mb-2">Chọn mục <b>Account</b> ➔ <b>API Management</b>.</li>
                                        <li class="mb-2">Bấm <b>Create API</b> ➔ Chọn loại <b>System generated (HMAC)</b>.</li>
                                        <li class="mb-2">Đặt tên: <code>ShopBotTelegram</code> ➔ Bấm Next và xác minh OTP email / Authenticator.</li>
                                    </ol>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="border rounded p-3 h-100 bg-light">
                                    <h6 class="fw-bold text-dark"><span class="step-badge success">2</span>Cài đặt Quyền & Lưu Key</h6>
                                    <ol class="small text-muted ps-3">
                                        <li class="mb-2"><b>BẢO MẬT:</b> Chỉ tích chọn duy nhất ô <b>Enable Reading</b> (Đọc dữ liệu).</li>
                                        <li class="mb-2"><b>TUYỆT ĐỐI KHÔNG</b> tích chọn ô <i>Enable Withdrawals</i> (Rút tiền) hoặc <i>Enable Spot & Margin Trading</i>. Như vậy ví của bạn an toàn 100%!</li>
                                        <li class="mb-2">Sao chép ngay <b>API Key</b> và <b>Secret Key</b>.</li>
                                    </ol>
                                </div>
                            </div>
                            <div class="col-12">
                                <div class="border rounded p-3 bg-light">
                                    <h6 class="fw-bold text-dark"><span class="step-badge warning">3</span>Điền vào Biến Môi Trường Render</h6>
                                    <p class="small text-muted mb-2">Vào Render Dashboard ➔ Chọn service <b>shopcl</b> ➔ Mục <b>Environment</b> ➔ Điền thêm 3 dòng sau:</p>
                                    <div class="code-box">
                                        <pre style="margin:0; color:#38bdf8;">BINANCE_UID="{binance_uid}"
BINANCE_API_KEY="Dán_API_Key_của_bạn_vào_đây"
BINANCE_API_SECRET="Dán_Secret_Key_của_bạn_vào_đây"</pre>
                                    </div>
                                    <small class="text-success mt-2 d-block"><i class="fa-solid fa-circle-check me-1"></i> Sau khi điền xong, Render sẽ tự động kết nối và kích hoạt nạp tự động Binance Pay 100%!</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 3: CẤU HÌNH USDT TỰ ĐỘNG -->
            <div class="tab-pane fade" id="tab-usdt">
                <div class="card">
                    <div class="card-header py-3 text-success">
                        <h5 class="card-title mb-0 fw-bold"><i class="fa-solid fa-wallet me-2"></i>Hướng Dẫn Cấu Hình Nạp USDT Blockchain (KryptoExpress)</h5>
                    </div>
                    <div class="card-body">
                        <div class="info-pill">
                            <b>Cơ chế On-chain:</b> Dành cho khách muốn nạp qua mạng Blockchain như BNB Smart Chain (BEP20) hoặc Solana (USDT-Solana). Cổng thanh toán KryptoExpress tự quét khối và bắn Webhook xác nhận sau 30 giây.
                        </div>

                        <div class="row g-4 mt-2">
                            <div class="col-lg-6">
                                <div class="card h-100 border-0 bg-light">
                                    <div class="card-body">
                                        <h5 class="fw-bold text-dark"><span class="step-badge">1</span>Đăng ký tài khoản Merchant</h5>
                                        <p class="text-muted">Đăng ký tài khoản hoàn toàn miễn phí tại <a href="https://kryptoexpress.pro" target="_blank" class="fw-bold">kryptoexpress.pro</a>.</p>
                                        <p class="small text-muted">Vào mục <b>Settings</b> ➔ <b>API Keys</b> ➔ Nhấn <b>Create New Key</b> để lấy <code>API Key</code> và <code>API Secret</code>.</p>
                                    </div>
                                </div>
                            </div>

                            <div class="col-lg-6">
                                <div class="card h-100 border-0 bg-light">
                                    <div class="card-body">
                                        <h5 class="fw-bold text-dark"><span class="step-badge success">2</span>Điền vào Biến Môi Trường Render</h5>
                                        <div class="code-box">
                                            <pre style="margin:0; color:#38bdf8;">KRYPTO_EXPRESS_API_KEY="Dán_API_Key_Vào_Đây"
KRYPTO_EXPRESS_API_SECRET="Dán_API_Secret_Vào_Đây"
KRYPTO_EXPRESS_API_URL="https://kryptoexpress.pro/api"</pre>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 4: XEM TỒN KHO & TEST API -->
            <div class="tab-pane fade" id="tab-inventory">
                <div class="card">
                    <div class="card-header py-3 text-info d-flex justify-content-between align-items-center">
                        <h5 class="card-title mb-0 fw-bold"><i class="fa-solid fa-boxes-stacked me-2"></i>Tình Trạng Kho Hàng Hiện Tại (Live Inventory)</h5>
                        <button class="btn btn-sm btn-outline-info" onclick="fetchInventory()"><i class="fa-solid fa-rotate me-1"></i> Làm mới</button>
                    </div>
                    <div class="card-body">
                        <div id="inventoryLoading" class="text-center py-4 text-muted">
                            <i class="fa-solid fa-spinner fa-spin fa-2x mb-2"></i>
                            <div>Đang tải dữ liệu kho hàng...</div>
                        </div>
                        <div id="inventoryContent" style="display:none;"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function updateLineCount() {{
            const val = document.getElementById("formItems").value;
            const lines = val.split('\n').map(s => s.trim()).filter(s => s.length > 0);
            document.getElementById("lineCounter").innerText = lines.length + " tài khoản";
        }}

        function toggleKeyVisibility() {{
            const input = document.getElementById("inputKey");
            const icon = document.getElementById("eyeIcon");
            if (input.type === "password") {{
                input.type = "text";
                icon.className = "fa-solid fa-eye-slash";
            }} else {{
                input.type = "password";
                icon.className = "fa-solid fa-eye";
            }}
        }}

        function copyId(id) {{
            const input = document.getElementById(id);
            input.select();
            navigator.clipboard.writeText(input.value);
            alert("Đã sao chép: " + input.value);
        }}

        function copyPyCode() {{
            const code = document.getElementById("pyCodeText").innerText;
            navigator.clipboard.writeText(code);
            alert("Đã sao chép mã code Python!");
        }}

        async function submitUpload() {{
            const cat = document.getElementById("formCat").value.trim();
            const subcat = document.getElementById("formSubcat").value.trim();
            const price = parseFloat(document.getElementById("formPrice").value);
            const raw = document.getElementById("formItems").value.trim();
            const resDiv = document.getElementById("uploadResult");

            if (!raw) {{
                alert("Vui lòng nhập ít nhất 1 tài khoản clone!");
                return;
            }}

            const items = raw.split('\n').map(s => s.trim()).filter(s => s.length > 0);
            resDiv.style.display = "block";
            resDiv.innerHTML = '<div class="alert alert-info py-2"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang nạp ' + items.length + ' tài khoản vào kho...</div>';

            try {{
                const res = await fetch("{api_upload_url}", {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/json",
                        "X-API-KEY": "{api_key}"
                    }},
                    body: JSON.stringify({{
                        category_name: cat,
                        subcategory_name: subcat,
                        price: price,
                        description: "Nạp trực tiếp từ Web Admin Bubba Gump",
                        items: items
                    }})
                }});

                const data = await res.json();
                if (res.ok) {{
                    resDiv.innerHTML = '<div class="alert alert-success py-2"><i class="fa-solid fa-circle-check me-1"></i> <b>Nạp thành công!</b> Đã thêm ' + data.uploaded_count + ' sản phẩm vào [' + data.category_name + ' > ' + data.subcategory_name + '].</div>';
                    document.getElementById("formItems").value = "";
                    updateLineCount();
                    fetchInventory();
                }} else {{
                    resDiv.innerHTML = '<div class="alert alert-danger py-2">Lỗi: ' + (data.detail || "Không thể nạp hàng") + '</div>';
                }}
            }} catch (err) {{
                resDiv.innerHTML = '<div class="alert alert-danger py-2">Lỗi kết nối: ' + err.message + '</div>';
            }}
        }}

        async function fetchInventory() {{
            const loading = document.getElementById("inventoryLoading");
            const content = document.getElementById("inventoryContent");
            loading.style.display = "block";
            content.style.display = "none";

            try {{
                const res = await fetch("{api_inventory_url}", {{
                    headers: {{ "X-API-KEY": "{api_key}" }}
                }});
                const data = await res.json();
                loading.style.display = "none";
                content.style.display = "block";

                if (data.inventory && data.inventory.length > 0) {{
                    let html = '<div class="table-responsive"><table class="table table-hover align-middle"><thead class="table-light"><tr><th>ID</th><th>Danh Mục</th><th>Số Lượng Clone Còn Trong Kho</th><th>Trạng Thái</th></tr></thead><tbody>';
                    data.inventory.forEach(item => {{
                        const badge = item.in_stock_qty > 0 ? '<span class="badge bg-success">Còn hàng</span>' : '<span class="badge bg-danger">Hết hàng</span>';
                        html += '<tr><td>' + item.category_id + '</td><td class="fw-bold">' + item.category_name + '</td><td><span class="fs-5 fw-bold text-primary">' + item.in_stock_qty + '</span> con</td><td>' + badge + '</td></tr>';
                    }});
                    html += '</tbody></table></div>';
                    content.innerHTML = html;
                }} else {{
                    content.innerHTML = '<div class="text-center py-4 text-muted"><i class="fa-solid fa-inbox fa-2x mb-2"></i><div>Kho hiện tại chưa có sản phẩm nào. Hãy dùng form bên Tab 1 để nạp ngay!</div></div>';
                }}
            }} catch (e) {{
                loading.style.display = "none";
                content.style.display = "block";
                content.innerHTML = '<div class="alert alert-warning py-2">Không thể lấy dữ liệu kho: ' + e.message + '</div>';
            }}
        }}

        async function syncBinancePay() {{
            const resBox = document.getElementById("syncResult");
            resBox.style.display = "block";
            resBox.innerHTML = '<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang kết nối Binance API...</span>';

            try {{
                const res = await fetch("{api_binance_check}", {{
                    method: "POST",
                    headers: {{ "X-API-KEY": "{api_key}" }}
                }});
                const data = await res.json();
                if (res.ok) {{
                    if (data.credited_count > 0) {{
                        resBox.innerHTML = '<span class="text-success fw-bold"><i class="fa-solid fa-circle-check me-1"></i> Đã tìm thấy và cộng tiền cho ' + data.credited_count + ' giao dịch!</span>';
                    }} else {{
                        resBox.innerHTML = '<span class="text-muted"><i class="fa-solid fa-check me-1"></i> Quét hoàn tất: Không có giao dịch mới cần xử lý.</span>';
                    }}
                }} else {{
                    resBox.innerHTML = '<span class="text-danger"><i class="fa-solid fa-triangle-exclamation me-1"></i> ' + (data.detail || "Chưa cấu hình API Key trên Render") + '</span>';
                }}
            }} catch (err) {{
                resBox.innerHTML = '<span class="text-danger">Lỗi kết nối: ' + err.message + '</span>';
            }}
        }}

        document.addEventListener("DOMContentLoaded", function() {{
            updateLineCount();
            fetchInventory();
        }});
    </script>
</body>
</html>"""
        return HTMLResponse(content=html_content)
