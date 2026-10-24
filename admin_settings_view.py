from sqladmin import BaseView, expose
from fastapi import Request
from fastapi.responses import HTMLResponse
import config


class PaymentApiConfigView(BaseView):
    name = "Nạp USDT & API"
    icon = "fa-solid fa-sliders"

    @expose("/settings", methods=["GET"])
    async def settings_page(self, request: Request):
        webhook_host = config.WEBHOOK_HOST or "https://shopcl.onrender.com"
        api_upload_url = f"{webhook_host}/api/items/bulk-upload"
        api_inventory_url = f"{webhook_host}/api/inventory/status"
        api_key = config.SQLADMIN_RAW_PASSWORD or "MatKhauAdminCuaBan123"

        html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cấu Hình Nạp USDT & REST API - Bubba Gump</title>
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
                <h3 class="fw-bold mb-1 text-dark"><i class="fa-solid fa-sliders text-primary me-2"></i>Cấu Hình Nạp USDT & REST API Bán Hàng</h3>
                <p class="text-muted mb-0">Hệ thống nạp hàng tự động bằng Tool / API, cổng nạp Crypto tự động và App Binance</p>
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
                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-usdt">
                    <i class="fa-solid fa-coins text-success me-1"></i> 2. Nạp USDT Tự Động (KryptoExpress)
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-binance">
                    <i class="fa-brands fa-bitcoin text-warning me-1"></i> 3. Quét Mã App Binance & Binance Pay
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
                                        <input type="text" class="form-control font-monospace" value="{api_key}" readonly id="inputKey">
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

            <!-- TAB 2: CẤU HÌNH USDT TỰ ĐỘNG -->
            <div class="tab-pane fade" id="tab-usdt">
                <div class="card">
                    <div class="card-header py-3 text-success">
                        <h5 class="card-title mb-0 fw-bold"><i class="fa-solid fa-wallet me-2"></i>Hướng Dẫn Cấu Hình Nạp USDT & Crypto Tự Động (KryptoExpress)</h5>
                    </div>
                    <div class="card-body">
                        <div class="success-pill">
                            <b>Cơ chế hoạt động:</b> Khách hàng bấm <b>💳 Ví</b> ➔ Chọn <b>Nạp tiền</b> ➔ Chọn <b>USDT (BEP20)</b> hoặc <b>USDT (Solana)</b>. Bot tự động tạo ví riêng kèm mã QR. Khách chuyển tiền -> Cổng thanh toán quét Blockchain và gửi Webhook về Bot -> Bot tự động cộng tiền cho khách trong 30 giây!
                        </div>

                        <div class="row g-4 mt-2">
                            <div class="col-lg-6">
                                <div class="card h-100 border-0 bg-light">
                                    <div class="card-body">
                                        <h5 class="fw-bold text-dark"><span class="step-badge">1</span>Đăng ký tài khoản Merchant</h5>
                                        <p class="text-muted">Đăng ký tài khoản hoàn toàn miễn phí, không yêu cầu giấy phép kinh doanh phức tạp.</p>
                                        <ol>
                                            <li>Truy cập <a href="https://kryptoexpress.pro" target="_blank" class="fw-bold">kryptoexpress.pro</a>.</li>
                                            <li>Đăng ký tài khoản Merchant mới.</li>
                                            <li>Vào mục <b>Settings</b> ➔ <b>API Keys</b> ➔ Nhấn <b>Create New Key</b>.</li>
                                            <li>Sao chép: <code>API Key</code> và <code>API Secret</code>.</li>
                                        </ol>
                                    </div>
                                </div>
                            </div>

                            <div class="col-lg-6">
                                <div class="card h-100 border-0 bg-light">
                                    <div class="card-body">
                                        <h5 class="fw-bold text-dark"><span class="step-badge success">2</span>Điền vào Biến Môi Trường Render</h5>
                                        <p class="text-muted">Mở Render Dashboard ➔ Chọn service <b>shopcl</b> ➔ Tab <b>Environment</b> ➔ Điền thêm:</p>
                                        <div class="code-box">
                                            <pre style="margin:0; color:#38bdf8;">KRYPTO_EXPRESS_API_KEY="Dán_API_Key_Vào_Đây"
KRYPTO_EXPRESS_API_SECRET="Dán_API_Secret_Vào_Đây"
KRYPTO_EXPRESS_API_URL="https://kryptoexpress.pro/api"</pre>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="col-12">
                                <div class="card border-0 bg-light">
                                    <div class="card-body">
                                        <h5 class="fw-bold text-dark"><span class="step-badge warning">3</span>Cấu Hình Tự Động Chuyển Tiền Về Ví Sàn Binance Của Bạn (Auto-Forwarding)</h5>
                                        <p>Khi khách nạp tiền thành công, hệ thống có thể tự động bắn thẳng số USDT đó về địa chỉ ví Binance của bạn mà không cần bạn phải vào rút tay!</p>
                                        <p class="mb-2">Điền thêm 3 dòng sau vào Environment trên Render:</p>
                                        <div class="code-box">
                                            <pre style="margin:0; color:#38bdf8;">CRYPTO_FORWARDING_MODE="true"
BNB_FORWARDING_ADDRESS="Địa_chỉ_ví_USDT_mạng_BEP20_trên_Binance_của_bạn"
SOL_FORWARDING_ADDRESS="Địa_chỉ_ví_USDT_mạng_Solana_trên_Binance_của_bạn"</pre>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 3: APP BINANCE TỰ ĐỘNG -->
            <div class="tab-pane fade" id="tab-binance">
                <div class="card">
                    <div class="card-header py-3 text-warning">
                        <h5 class="card-title mb-0 fw-bold"><i class="fa-brands fa-bitcoin me-2"></i>Hướng Dẫn Nạp Tiền Bằng Ứng Dụng Binance</h5>
                    </div>
                    <div class="card-body">
                        <div class="row g-4">
                            <!-- Cách 1: Quét mã QR BEP20 -->
                            <div class="col-lg-6">
                                <div class="border rounded-3 p-4 h-100 bg-white shadow-sm">
                                    <div class="d-flex align-items-center mb-3">
                                        <span class="badge bg-success p-2 me-2"><i class="fa-solid fa-check fs-6"></i></span>
                                        <div>
                                            <h5 class="fw-bold mb-0 text-success">Cách 1: Khách Quét Mã QR Mạng BSC (BEP20)</h5>
                                            <small class="text-muted">Khuyên Dùng Nhất - Chạy ngay 100% không cần đăng ký</small>
                                        </div>
                                    </div>
                                    <p>Mạng <b>BNB Smart Chain (BEP20)</b> là mạng phổ biến nhất trên Binance vì tốc độ cực nhanh và phí rút siêu rẻ (chỉ khoảng <b>~0.19$</b>).</p>
                                    
                                    <h6 class="fw-bold text-dark mt-3">Quy trình nạp tiền của khách:</h6>
                                    <ol class="ps-3 small text-muted">
                                        <li class="mb-2">Khách mở bot Telegram, bấm <b>💳 Ví</b> ➔ Chọn <b>Nạp tiền</b> ➔ Chọn loại tiền: <b>USDT (BEP20)</b>.</li>
                                        <li class="mb-2">Bot lập tức gửi ảnh <b>Mã QR</b> kèm địa chỉ ví nhận và số tiền cần chuyển.</li>
                                        <li class="mb-2">Khách mở ứng dụng <b>Binance</b> trên điện thoại ➔ Bấm vào biểu tượng <b>[ — ] Quét mã QR</b> ở góc trên cùng bên phải màn hình chính.</li>
                                        <li class="mb-2">Quét mã QR của bot ➔ Chọn mạng <b>BNB Smart Chain (BEP20)</b> ➔ Xác nhận rút tiền.</li>
                                        <li class="mb-2">Trong vòng 30s - 1 phút, giao dịch hoàn tất ➔ Bot tự động ting ting cộng số dư tài khoản cho khách!</li>
                                    </ol>
                                </div>
                            </div>

                            <!-- Cách 2: Binance Pay Merchant -->
                            <div class="col-lg-6">
                                <div class="border rounded-3 p-4 h-100 bg-white shadow-sm">
                                    <div class="d-flex align-items-center mb-3">
                                        <span class="badge bg-primary p-2 me-2"><i class="fa-solid fa-mobile-screen fs-6"></i></span>
                                        <div>
                                            <h5 class="fw-bold mb-0 text-primary">Cách 2: Binance Pay Merchant API</h5>
                                            <small class="text-muted">0% Phí - Deeplink 1 chạm mở thẳng App Binance</small>
                                        </div>
                                    </div>
                                    <p>Binance Pay là cổng thanh toán nội bộ của Binance, tiền chuyển giữa các tài khoản Binance với <b>0% phí giao dịch</b>.</p>

                                    <h6 class="fw-bold text-dark mt-3">Các bước tích hợp Binance Pay:</h6>
                                    <ol class="ps-3 small text-muted">
                                        <li class="mb-2">Truy cập cổng đối tác: <a href="https://merchant.binance.com/" target="_blank" class="fw-bold">merchant.binance.com</a>.</li>
                                        <li class="mb-2">Đăng ký tài khoản Merchant và hoàn tất KYC doanh nghiệp hoặc cá nhân.</li>
                                        <li class="mb-2">Vào mục <b>Developer</b> ➔ <b>API Management</b> ➔ Tạo <code>Binance Pay API Key</code> và <code>Secret Key</code>.</li>
                                        <li class="mb-2">Webhook URL nhận kết quả thanh toán từ Binance:
                                            <div class="bg-light p-2 rounded border font-monospace mt-1">{webhook_host}/api/binancepay/webhook</div>
                                        </li>
                                        <li class="mb-2">Khi khách bấm nạp ➔ Bot sinh Deeplink <code>binance://pay?...</code> ➔ Khách bấm vào là App Binance tự mở lên xác nhận bằng vân tay / FaceID!</li>
                                    </ol>
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

        // Tự động load inventory khi mở tab
        document.addEventListener("DOMContentLoaded", function() {{
            updateLineCount();
            fetchInventory();
        }});
    </script>
</body>
</html>"""
        return HTMLResponse(content=html_content)
