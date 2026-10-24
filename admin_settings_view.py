from sqladmin import BaseView, expose
from fastapi import Request
from starlette.responses import HTMLResponse, RedirectResponse
from utils.utils import decode_token
import config


class PaymentApiConfigView(BaseView):
    name = "Nạp USDT & Binance"
    icon = "fa-solid fa-coins"

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
        # 1. Bắt buộc kiểm tra đăng nhập Admin
        try:
            token = request.session.get("token")
        except Exception:
            token = None

        if not token or not decode_token(token):
            return RedirectResponse(url="/admin/login", status_code=302)

        webhook_host = config.WEBHOOK_HOST or "https://shopcl.onrender.com"
        api_binance_check = f"{webhook_host}/api/binancepay/check-now"
        api_settings_save = f"{webhook_host}/api/settings/save"
        api_key = config.SQLADMIN_RAW_PASSWORD or "MatKhauAdminCuaBan123"

        from db import get_db_session
        from services.settings import SettingsService

        async with get_db_session() as session:
            cur_settings = await SettingsService.get_all_settings(session)

        binance_uid = cur_settings.get("BINANCE_UID") or "805398854"
        binance_api_key = cur_settings.get("BINANCE_API_KEY") or ""
        binance_api_secret = cur_settings.get("BINANCE_API_SECRET") or ""

        krypto_api_key = cur_settings.get("KRYPTO_EXPRESS_API_KEY") or ""
        krypto_api_secret = cur_settings.get("KRYPTO_EXPRESS_API_SECRET") or ""
        krypto_api_url = cur_settings.get("KRYPTO_EXPRESS_API_URL") or "https://kryptoexpress.pro/api"

        fwd_mode = cur_settings.get("CRYPTO_FORWARDING_MODE", False)
        bnb_fwd = cur_settings.get("BNB_FORWARDING_ADDRESS") or ""
        sol_fwd = cur_settings.get("SOL_FORWARDING_ADDRESS") or ""

        is_binance_ready = bool(binance_api_key and binance_api_secret)
        binance_badge = '<span class="badge bg-success"><i class="fa-solid fa-circle-check me-1"></i> Đang hoạt động tự động</span>' if is_binance_ready else '<span class="badge bg-warning text-dark"><i class="fa-solid fa-triangle-exclamation me-1"></i> Chưa cấu hình API Key & Secret</span>'

        fwd_checked_attr = "checked" if fwd_mode else ""

        html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cấu Hình Cổng Nạp USDT & Binance Pay - Bubba Gump</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {{ background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1e293b; }}
        .card {{ border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 24px; background: #fff; }}
        .card-header {{ background-color: #ffffff; border-bottom: 1px solid #f1f5f9; font-weight: 600; padding: 14px 20px; }}
        .nav-pills .nav-link {{ color: #475569; font-weight: 500; border-radius: 8px; padding: 10px 16px; margin-right: 8px; transition: all 0.2s; }}
        .nav-pills .nav-link.active {{ background-color: #0d6efd; color: #fff; box-shadow: 0 4px 12px rgba(13,110,253,0.25); }}
        .step-badge {{ display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: #0d6efd; color: #fff; font-weight: bold; font-size: 0.85rem; margin-right: 8px; }}
        .step-badge.success {{ background: #10b981; }}
        .step-badge.warning {{ background: #f59e0b; }}
    </style>
</head>
<body class="p-3 p-md-4">
    <div class="container-fluid" style="max-width: 1400px;">
        <!-- Header -->
        <div class="d-flex flex-wrap justify-content-between align-items-center mb-4 pb-3 border-bottom">
            <div>
                <h3 class="fw-bold mb-1 text-dark"><i class="fa-solid fa-coins text-warning me-2"></i>Cấu Hình Cổng Nạp Tiền Trực Tiếp</h3>
                <p class="text-muted mb-0">Cấu hình trực tiếp tại đây để lưu vào Database Supabase mà <b>KHÔNG CẦN</b> phải vào Render chỉnh biến môi trường!</p>
            </div>
            <div class="mt-2 mt-md-0">
                <a href="/admin" class="btn btn-outline-secondary"><i class="fa-solid fa-arrow-left me-1"></i> Quay lại Dashboard</a>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <ul class="nav nav-pills mb-4" id="pills-tab" role="tablist">
            <li class="nav-item">
                <button class="nav-link active" data-bs-toggle="pill" data-bs-target="#tab-binance">
                    <i class="fa-brands fa-bitcoin text-warning me-1"></i> 1. Cổng Nạp Binance Pay (0% Phí - Quét Mã App & API)
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-usdt">
                    <i class="fa-solid fa-wallet text-success me-1"></i> 2. Cổng Nạp USDT Tự Động (KryptoExpress) & Rút Ví
                </button>
            </li>
        </ul>

        <div class="tab-content" id="pills-tabContent">
            <!-- TAB 1: BINANCE PAY -->
            <div class="tab-pane fade show active" id="tab-binance">
                <div class="row g-4">
                    <!-- Cột 1: Form lưu trực tiếp -->
                    <div class="col-lg-6">
                        <div class="card border-warning h-100 shadow-sm">
                            <div class="card-header bg-warning bg-opacity-10 py-3 d-flex justify-content-between align-items-center">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-brands fa-bitcoin text-warning me-2"></i>Cấu Hình Binance Pay & Open API</h5>
                                {binance_badge}
                            </div>
                            <div class="card-body">
                                <div class="alert alert-success py-2 small mb-3">
                                    <i class="fa-solid fa-bolt me-1"></i> <b>Nạp 0% Phí - Nhận 1s:</b> Khách chuyển tiền nội bộ Binance vào UID của bạn, Bot tự đọc lịch sử qua API và tự động cộng số dư ngay lập tức!
                                </div>

                                <form id="binanceForm" onsubmit="event.preventDefault(); saveBinanceSettings();">
                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">1. Binance UID Cá Nhân Của Bạn (Pay ID):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-id-badge text-warning"></i></span>
                                            <input type="text" class="form-control font-monospace fw-bold" id="binance_uid" value="{binance_uid}" placeholder="VD: 805398854" required>
                                        </div>
                                        <div class="form-text small">UID hiển thị trên app Binance của bạn để khách chuyển USDT vào.</div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">2. Binance API Key (Chỉ đọc - Read-only):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-key"></i></span>
                                            <input type="password" class="form-control font-monospace" id="binance_api_key" value="{binance_api_key}" placeholder="Dán Binance API Key vào đây">
                                            <button class="btn btn-outline-secondary" type="button" onclick="togglePass('binance_api_key', this)"><i class="fa-solid fa-eye"></i></button>
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">3. Binance Secret Key:</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-lock"></i></span>
                                            <input type="password" class="form-control font-monospace" id="binance_api_secret" value="{binance_api_secret}" placeholder="Dán Binance Secret Key vào đây">
                                            <button class="btn btn-outline-secondary" type="button" onclick="togglePass('binance_api_secret', this)"><i class="fa-solid fa-eye"></i></button>
                                        </div>
                                    </div>

                                    <div id="binanceSaveResult" class="mb-3" style="display:none;"></div>

                                    <div class="d-flex flex-wrap gap-2 pt-2 border-top">
                                        <button type="submit" class="btn btn-warning fw-bold px-4">
                                            <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Cấu Hình Binance Ngay
                                        </button>
                                        <button type="button" class="btn btn-outline-secondary" onclick="syncBinancePay()">
                                            <i class="fa-solid fa-rotate me-1"></i> Quét Giao Dịch Ngay
                                        </button>
                                    </div>
                                </form>
                                <div id="syncResult" class="mt-3 p-2 bg-light rounded small" style="display:none;"></div>
                            </div>
                        </div>
                    </div>

                    <!-- Cột 2: Hướng dẫn lấy key -->
                    <div class="col-lg-6">
                        <div class="card h-100 shadow-sm">
                            <div class="card-header py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-shield-halved text-success me-2"></i>Hướng Dẫn Lấy API Key Binance (An Toàn 100%)</h5>
                            </div>
                            <div class="card-body">
                                <p class="text-muted small">Bạn chỉ cần cấp quyền <b>Chỉ Đọc (Read-only)</b> để bot kiểm tra giao dịch nạp. Bot tuyệt đối không thể rút tiền hay giao dịch spot, tiền trong ví an toàn tuyệt đối.</p>
                                <div class="d-flex align-items-start mb-3">
                                    <span class="step-badge">1</span>
                                    <div>
                                        <b>Mở Quản lý API trên Binance:</b>
                                        <div class="small text-muted">Mở Binance trên web ➔ Bấm Avatar góc trên ➔ Chọn <b>Account</b> ➔ <b>API Management</b>. Hoặc truy cập: <a href="https://www.binance.com/en/my/settings/api-management" target="_blank" class="text-decoration-none">binance.com/en/my/settings/api-management</a></div>
                                    </div>
                                </div>
                                <div class="d-flex align-items-start mb-3">
                                    <span class="step-badge">2</span>
                                    <div>
                                        <b>Tạo API Key:</b>
                                        <div class="small text-muted">Bấm <b>Create API</b> ➔ Chọn loại <b>System generated (HMAC)</b> ➔ Đặt tên ví dụ: <code>ShopBotTelegram</code> ➔ Xác thực OTP.</div>
                                    </div>
                                </div>
                                <div class="d-flex align-items-start mb-3">
                                    <span class="step-badge warning">3</span>
                                    <div>
                                        <b>Cài đặt Quyền (API Restrictions):</b>
                                        <div class="small text-muted"><span class="badge bg-success">Chỉ tích: Enable Reading</span>. <span class="badge bg-danger">KHÔNG TÍCH</span> <i>Enable Withdrawals</i> hay <i>Enable Spot Trading</i>.</div>
                                    </div>
                                </div>
                                <div class="d-flex align-items-start">
                                    <span class="step-badge success">4</span>
                                    <div>
                                        <b>Dán vào Form & Bấm Lưu:</b>
                                        <div class="small text-muted">Copy <b>API Key</b> và <b>Secret Key</b> dán sang form bên trái rồi bấm nút <b>Lưu Cấu Hình Binance Ngay</b>. Cài đặt được lưu vào Supabase và kích hoạt ngay tức thì!</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 2: KRYPTOEXPRESS & AUTO FORWARDING -->
            <div class="tab-pane fade" id="tab-usdt">
                <div class="row g-4">
                    <!-- Cột 1: Cấu hình KryptoExpress -->
                    <div class="col-lg-6">
                        <div class="card border-success h-100 shadow-sm">
                            <div class="card-header bg-success bg-opacity-10 py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-wallet text-success me-2"></i>Cấu Hình Cổng Nạp USDT (KryptoExpress)</h5>
                            </div>
                            <div class="card-body">
                                <div class="alert alert-info py-2 small mb-3">
                                    Cổng nạp USDT on-chain qua mạng BEP20, Solana, TRC20, Polygon... Tự động tạo ví riêng kèm mã QR cho từng đơn nạp.
                                </div>

                                <form id="kryptoForm" onsubmit="event.preventDefault(); saveKryptoSettings();">
                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">1. KryptoExpress API Key:</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-key"></i></span>
                                            <input type="password" class="form-control font-monospace" id="krypto_api_key" value="{krypto_api_key}" placeholder="Dán KryptoExpress API Key vào đây">
                                            <button class="btn btn-outline-secondary" type="button" onclick="togglePass('krypto_api_key', this)"><i class="fa-solid fa-eye"></i></button>
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">2. KryptoExpress API Secret:</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-lock"></i></span>
                                            <input type="password" class="form-control font-monospace" id="krypto_api_secret" value="{krypto_api_secret}" placeholder="Dán KryptoExpress API Secret vào đây">
                                            <button class="btn btn-outline-secondary" type="button" onclick="togglePass('krypto_api_secret', this)"><i class="fa-solid fa-eye"></i></button>
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">3. API Base URL:</label>
                                        <input type="text" class="form-control font-monospace small" id="krypto_api_url" value="{krypto_api_url}" required>
                                    </div>

                                    <div class="mb-3 p-2 bg-light rounded small">
                                        <b>Webhook URL dán vào KryptoExpress:</b>
                                        <div class="input-group input-group-sm mt-1">
                                            <input type="text" class="form-control font-monospace" value="{webhook_host}/cryptoprocessing/event" readonly id="kryptoWebhook">
                                            <button class="btn btn-outline-secondary" type="button" onclick="navigator.clipboard.writeText(document.getElementById('kryptoWebhook').value); alert('Đã sao chép Webhook URL!');"><i class="fa-regular fa-copy"></i> Copy</button>
                                        </div>
                                    </div>

                                    <div id="kryptoSaveResult" class="mb-3" style="display:none;"></div>

                                    <div class="pt-2 border-top">
                                        <button type="submit" class="btn btn-success fw-bold px-4">
                                            <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Cấu Hình KryptoExpress
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>

                    <!-- Cột 2: Cấu hình tự động bắn tiền về ví sàn Binance (Auto-Forwarding) -->
                    <div class="col-lg-6">
                        <div class="card border-primary h-100 shadow-sm">
                            <div class="card-header bg-primary bg-opacity-10 py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-arrow-right-arrow-left text-primary me-2"></i>Tự Động Bắn Tiền Về Ví Sàn Binance (Auto-Forwarding)</h5>
                            </div>
                            <div class="card-body">
                                <div class="alert alert-primary py-2 small mb-3">
                                    Khi khách nạp tiền thành công, cổng thanh toán có thể tự động bắn thẳng số USDT đó về địa chỉ ví Binance của bạn mà không cần bạn phải thao tác rút tay!
                                </div>

                                <form id="forwardingForm" onsubmit="event.preventDefault(); saveForwardingSettings();">
                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="crypto_forwarding_mode" {fwd_checked_attr}>
                                        <label class="form-check-label fw-bold" for="crypto_forwarding_mode">Bật tự động chuyển tiếp tiền về ví cá nhân</label>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">Địa chỉ ví USDT (Mạng BNB Smart Chain - BEP20):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-brands fa-ethereum text-warning"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="bnb_forwarding_address" value="{bnb_fwd}" placeholder="0x... (Lấy trong mục Nạp USDT của Binance)">
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">Địa chỉ ví USDT (Mạng Solana - SOL):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-sun text-info"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="sol_forwarding_address" value="{sol_fwd}" placeholder="Địa chỉ ví SOL trên Binance">
                                        </div>
                                    </div>

                                    <div id="fwdSaveResult" class="mb-3" style="display:none;"></div>

                                    <div class="pt-2 border-top">
                                        <button type="submit" class="btn btn-primary fw-bold px-4">
                                            <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Cấu Hình Ví Chuyển Tiếp
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function togglePass(id, btn) {{
            const input = document.getElementById(id);
            const icon = btn.querySelector('i');
            if (input.type === 'password') {{
                input.type = 'text';
                icon.className = 'fa-solid fa-eye-slash';
            }} else {{
                input.type = 'password';
                icon.className = 'fa-solid fa-eye';
            }}
        }}

        async function saveSettingsPayload(payload, resultDivId) {{
            const resDiv = document.getElementById(resultDivId);
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang lưu cài đặt vào Database Supabase...</span>';

            try {{
                const res = await fetch("{api_settings_save}", {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-API-KEY': "{api_key}"
                    }},
                    body: JSON.stringify({{ settings: payload }})
                }});
                const data = await res.json();
                if (res.ok) {{
                    resDiv.innerHTML = '<div class="alert alert-success py-2 mb-0"><i class="fa-solid fa-circle-check me-1"></i> <b>Lưu thành công!</b> Cấu hình đã được lưu vĩnh viễn vào Supabase và kích hoạt ngay lập tức mà KHÔNG CẦN sửa gì trên Render.</div>';
                    setTimeout(() => {{ location.reload(); }}, 1500);
                }} else {{
                    resDiv.innerHTML = '<div class="alert alert-danger py-2 mb-0">Lỗi: ' + (data.detail || 'Không thể lưu cài đặt') + '</div>';
                }}
            }} catch (err) {{
                resDiv.innerHTML = '<div class="alert alert-danger py-2 mb-0">Lỗi kết nối: ' + err.message + '</div>';
            }}
        }}

        function saveBinanceSettings() {{
            const payload = {{
                'BINANCE_UID': document.getElementById('binance_uid').value.trim(),
                'BINANCE_API_KEY': document.getElementById('binance_api_key').value.trim(),
                'BINANCE_API_SECRET': document.getElementById('binance_api_secret').value.trim()
            }};
            saveSettingsPayload(payload, 'binanceSaveResult');
        }}

        function saveKryptoSettings() {{
            const payload = {{
                'KRYPTO_EXPRESS_API_KEY': document.getElementById('krypto_api_key').value.trim(),
                'KRYPTO_EXPRESS_API_SECRET': document.getElementById('krypto_api_secret').value.trim(),
                'KRYPTO_EXPRESS_API_URL': document.getElementById('krypto_api_url').value.trim()
            }};
            saveSettingsPayload(payload, 'kryptoSaveResult');
        }}

        function saveForwardingSettings() {{
            const payload = {{
                'CRYPTO_FORWARDING_MODE': document.getElementById('crypto_forwarding_mode').checked ? 'true' : 'false',
                'BNB_FORWARDING_ADDRESS': document.getElementById('bnb_forwarding_address').value.trim(),
                'SOL_FORWARDING_ADDRESS': document.getElementById('sol_forwarding_address').value.trim()
            }};
            saveSettingsPayload(payload, 'fwdSaveResult');
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
    </script>
</body>
</html>"""
        return HTMLResponse(content=html_content)
