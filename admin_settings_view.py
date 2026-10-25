from sqladmin import BaseView, expose
from fastapi import Request
from starlette.responses import HTMLResponse, RedirectResponse
from utils.utils import decode_token
import config


class PaymentApiConfigView(BaseView):
    name = "Cài đặt & Clone FB"
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
        # 1. Bắt buộc kiểm tra đăng nhập Admin
        try:
            token = request.session.get("token")
        except Exception:
            token = None

        if not token or not decode_token(token):
            return RedirectResponse(url="/admin/login", status_code=302)

        webhook_host = config.WEBHOOK_HOST or "https://shopcl.onrender.com"
        webhook_host = (config.WEBHOOK_HOST or "https://shopcl.onrender.com").rstrip("/")
        api_binance_check = "/api/binancepay/check-now"
        api_settings_save = "/api/settings/save"
        api_fb_check_uid = "/api/facebook/check-uid"
        api_fb_scan_stock = "/api/facebook/scan-stock"
        api_fb_clean_die = "/api/facebook/clean-die"
        api_fb_clean_dups = "/api/facebook/clean-duplicates"
        api_key = config.SQLADMIN_RAW_PASSWORD or "MatKhauAdminCuaBan123"
        admin_token = token or ""

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

        bank_token = cur_settings.get("BANK_BIDV_TOKEN") or ""
        bank_acc_num = cur_settings.get("BANK_ACCOUNT_NUMBER") or "8880117869"
        bank_acc_name = cur_settings.get("BANK_ACCOUNT_NAME") or "CHU TAI KHOAN"
        bank_code = cur_settings.get("BANK_CODE") or "BIDV"
        bank_rate = cur_settings.get("BANK_EXCHANGE_RATE", 26000)
        bank_auto_check = cur_settings.get("BANK_AUTO_CHECK", True)
        bank_auto_attr = "checked" if bank_auto_check else ""
        is_bank_ready = bool(bank_token)
        bank_badge = '<span class="badge bg-success"><i class="fa-solid fa-circle-check me-1"></i> Đang hoạt động tự động</span>' if is_bank_ready else '<span class="badge bg-warning text-dark"><i class="fa-solid fa-triangle-exclamation me-1"></i> Chưa điền Token ThueApi.pro</span>'
        api_bank_check = "/api/bank/check-now"

        fwd_mode = cur_settings.get("CRYPTO_FORWARDING_MODE", False)
        only_usdt = cur_settings.get("ONLY_USDT_MODE", False)
        bnb_fwd = cur_settings.get("BNB_FORWARDING_ADDRESS") or ""
        sol_fwd = cur_settings.get("SOL_FORWARDING_ADDRESS") or ""
        eth_fwd = cur_settings.get("ETH_FORWARDING_ADDRESS") or ""
        btc_fwd = cur_settings.get("BTC_FORWARDING_ADDRESS") or ""
        ltc_fwd = cur_settings.get("LTC_FORWARDING_ADDRESS") or ""
        doge_fwd = cur_settings.get("DOGE_FORWARDING_ADDRESS") or ""

        only_usdt_checked_attr = "checked" if only_usdt else ""

        fb_filter_dups = cur_settings.get("FB_FILTER_DUPLICATE_UIDS", True)
        fb_filter_dups_attr = "checked" if fb_filter_dups else ""
        fb_check_upload = cur_settings.get("FB_AUTO_CHECK_ON_UPLOAD", True)
        fb_delete_upload = cur_settings.get("FB_AUTO_DELETE_DIE_ON_UPLOAD", True)
        fb_check_delivery = cur_settings.get("FB_CHECK_LIVE_BEFORE_DELIVERY", True)
        fb_delete_delivery = cur_settings.get("FB_AUTO_DELETE_DIE_ON_DELIVERY", True)
        fb_keywords = cur_settings.get("FB_CATEGORY_KEYWORDS", "facebook, fb, clone, via, bm")

        fb_check_up_attr = "checked" if fb_check_upload else ""
        fb_del_up_attr = "checked" if fb_delete_upload else ""
        fb_check_deliv_attr = "checked" if fb_check_delivery else ""
        fb_del_deliv_attr = "checked" if fb_delete_delivery else ""
        fb_cron_interval = cur_settings.get("FB_CRON_CHECK_INTERVAL_MINUTES", 30)
        fb_cron_notify = cur_settings.get("FB_CRON_NOTIFY_ADMIN", True)
        fb_cron_notify_attr = "checked" if fb_cron_notify else ""
        cron_webhook_url = f"{webhook_host}/api/cron/check-live?token={api_key}&delete_die=true"

        is_binance_ready = bool(binance_api_key and binance_api_secret)
        binance_badge = '<span class="badge bg-success"><i class="fa-solid fa-circle-check me-1"></i> Đang hoạt động tự động</span>' if is_binance_ready else '<span class="badge bg-warning text-dark"><i class="fa-solid fa-triangle-exclamation me-1"></i> Chưa cấu hình API Key & Secret</span>'

        fwd_checked_attr = "checked" if fwd_mode else ""

        deposit_bonus_enabled = cur_settings.get("DEPOSIT_BONUS_ENABLED", False)
        deposit_bonus_enabled_attr = "checked" if deposit_bonus_enabled else ""
        deposit_bonus_tiers = cur_settings.get("DEPOSIT_BONUS_TIERS") or "100:2,200:5,300:6,500:7,1000:8"
        bonus_badge = '<span class="badge bg-success"><i class="fa-solid fa-circle-check me-1"></i> Đang BẬT khuyến mãi</span>' if deposit_bonus_enabled else '<span class="badge bg-secondary"><i class="fa-solid fa-power-off me-1"></i> Đang TẮT</span>'

        from enums.language import Language
        from services.deposit_bonus import DepositBonusService
        preview_text = DepositBonusService.get_bonus_display_text(Language.VI)
        if not preview_text:
            preview_bonus_html = "Nhập số USDT muốn nạp (tối thiểu 1):\n(Khuyến mãi đang TẮT - Bot chỉ hiện khung nhập tiền sạch, không có chữ thưởng)"
        else:
            preview_bonus_html = f"Nhập số USDT muốn nạp (tối thiểu 1):\n\n{preview_text}"

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
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-bank">
                    <i class="fa-solid fa-building-columns text-info me-1"></i> 3. Cổng Nạp Ngân Hàng BIDV (ThueApi.pro & VietQR)
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-facebook">
                    <i class="fa-brands fa-facebook text-primary me-1"></i> 4. Cấu Hình Clone Facebook (Check Live & Tự Động Xóa DIE)
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-bonus">
                    <i class="fa-solid fa-gift text-danger me-1"></i> 5. Khuyến Mãi Nạp Tiền (Deposit Bonus)
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
                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded border border-info">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="only_usdt_mode" {only_usdt_checked_attr}>
                                        <label class="form-check-label fw-bold text-primary" for="only_usdt_mode">⚡ Chế độ Nạp Gọn: Chỉ hiện Binance Pay & USDT trên Bot</label>
                                        <div class="small text-muted ms-4">Ẩn bớt các coin phí cao (BTC, ETH, LTC, DOGE...) để khách không nạp nhầm. Khi bật, bot chỉ hiện Binance Pay (0% phí) và các mạng USDT (BEP20, SOL).</div>
                                    </div>

                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded border">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="crypto_forwarding_mode" {fwd_checked_attr}>
                                        <label class="form-check-label fw-bold text-success" for="crypto_forwarding_mode">🔁 Bật tự động chuyển tiếp tiền về ví cá nhân (Auto-Forwarding)</label>
                                        <div class="small text-muted ms-4">Khi khách nạp coin nào, KryptoExpress sẽ tự động chuyển thẳng coin đó về đúng địa chỉ ví tương ứng bên dưới.</div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">1. Địa chỉ ví USDT / BNB (Mạng BNB Smart Chain - BEP20 - Rẻ nhất):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-brands fa-ethereum text-warning"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="bnb_forwarding_address" value="{bnb_fwd}" placeholder="0x... (Lấy trong mục Nạp USDT mạng BEP20 của Binance)">
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">2. Địa chỉ ví USDT / SOL (Mạng Solana - SOL):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-sun text-info"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="sol_forwarding_address" value="{sol_fwd}" placeholder="Địa chỉ ví SOL trên Binance">
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">3. Địa chỉ ví USDT / ETH / USDC (Mạng ERC-20 - Ethereum):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-brands fa-ethereum text-primary"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="eth_forwarding_address" value="{eth_fwd}" placeholder="0x... (Địa chỉ ví ERC20 trên Binance)">
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">4. Địa chỉ ví Bitcoin (BTC):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-brands fa-bitcoin text-warning"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="btc_forwarding_address" value="{btc_fwd}" placeholder="Địa chỉ ví BTC trên Binance">
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">5. Địa chỉ ví Litecoin (LTC):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-coins text-secondary"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="ltc_forwarding_address" value="{ltc_fwd}" placeholder="Địa chỉ ví LTC trên Binance">
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">6. Địa chỉ ví Dogecoin (DOGE):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-dog text-warning"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="doge_forwarding_address" value="{doge_fwd}" placeholder="Địa chỉ ví DOGE trên Binance">
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

<!-- TAB: NGÂN HÀNG VIỆT NAM (BIDV / THUEAPI.PRO) -->
            <div class="tab-pane fade" id="tab-bank">
                <div class="row g-4">
                    <!-- Cột 1: Form cấu hình BIDV & ThueApi.pro -->
                    <div class="col-lg-6">
                        <div class="card border-info h-100 shadow-sm">
                            <div class="card-header bg-info bg-opacity-10 py-3 d-flex justify-content-between align-items-center">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-building-columns text-info me-2"></i>Cấu Hình Ngân Hàng BIDV (ThueApi.pro)</h5>
                                {bank_badge}
                            </div>
                            <div class="card-body">
                                <div class="alert alert-info py-2 small mb-3">
                                    <i class="fa-solid fa-bolt me-1"></i> <b>Tự động 100%:</b> Khách nạp qua mã VietQR, tiền vào tài khoản BIDV của bạn, hệ thống gọi API <b>ThueApi.pro</b> đọc lịch sử giao dịch và tự động cộng tiền USD vào số dư bot sau 10-30 giây!
                                </div>

                                <form id="bankForm" onsubmit="event.preventDefault(); saveBankSettings();">
                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">1. Token BIDV (Lấy từ ThueApi.pro):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-key text-info"></i></span>
                                            <input type="password" class="form-control font-monospace" id="bank_token" value="{bank_token}" placeholder="Dán token BIDV từ thueapi.pro vào đây" required>
                                            <button class="btn btn-outline-secondary" type="button" onclick="togglePass('bank_token', this)"><i class="fa-solid fa-eye"></i></button>
                                        </div>
                                        <div class="form-text small">Lấy trong mục API V2 tại <code>thueapi.pro/historyapibidvv2/:tokenbidv</code></div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">2. Số Tài Khoản Nhận Tiền (STK):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-credit-card text-success"></i></span>
                                            <input type="text" class="form-control font-monospace fw-bold" id="bank_account_number" value="{bank_acc_num}" placeholder="VD: 8880117869" required>
                                        </div>
                                        <div class="form-text small">Số tài khoản BIDV của bạn để khách chuyển tiền tới.</div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">3. Tên Chủ Tài Khoản:</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-user text-primary"></i></span>
                                            <input type="text" class="form-control" id="bank_account_name" value="{bank_acc_name}" placeholder="VD: NGUYEN VAN A">
                                        </div>
                                        <div class="form-text small">Tên in trên tài khoản ngân hàng (viết hoa không dấu).</div>
                                    </div>

                                    <div class="row g-2 mb-3">
                                        <div class="col-sm-6">
                                            <label class="form-label fw-bold small text-muted">4. Mã Ngân Hàng:</label>
                                            <input type="text" class="form-control font-monospace fw-bold" id="bank_code" value="{bank_code}" placeholder="BIDV" readonly>
                                        </div>
                                        <div class="col-sm-6">
                                            <label class="form-label fw-bold small text-muted">5. Tỷ Giá Quy Đổi (VNĐ / 1$):</label>
                                            <div class="input-group">
                                                <input type="number" class="form-control font-monospace fw-bold text-success" id="bank_exchange_rate" value="{bank_rate}" step="100" min="1000">
                                                <span class="input-group-text small">đ / 1$</span>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded border border-info">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="bank_auto_check" {bank_auto_attr}>
                                        <label class="form-check-label fw-bold text-dark" for="bank_auto_check">
                                            <i class="fa-solid fa-robot text-info me-1"></i> Tự Động Quét & Cộng Tiền Ngân Hàng (24/7)
                                        </label>
                                        <div class="small text-muted ms-4">Bot sẽ tự động quét API ThueApi.pro mỗi 15 giây. Khi khách chuyển đúng nội dung <code>NAP &lt;id&gt;</code>, số dư sẽ được cộng ngay lập tức!</div>
                                    </div>

                                    <div id="bankSaveResult" class="mb-3" style="display:none;"></div>

                                    <div class="pt-2 border-top d-flex gap-2">
                                        <button type="submit" class="btn btn-info text-white fw-bold px-4">
                                            <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Cấu Hình Ngân Hàng
                                        </button>
                                        <button type="button" class="btn btn-outline-info fw-bold" onclick="checkBankTransactionsNow()">
                                            <i class="fa-solid fa-rotate me-1"></i> Quét Giao Dịch Ngay
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>

                    <!-- Cột 2: Hướng dẫn lấy token từ ThueApi.pro -->
                    <div class="col-lg-6">
                        <div class="card bg-light border-0 shadow-sm h-100">
                            <div class="card-body">
                                <h5 class="fw-bold text-dark mb-3"><i class="fa-solid fa-book-open-reader text-info me-2"></i>Hướng Dẫn Tích Hợp ThueApi.pro (3 Bước)</h5>

                                <div class="step-item d-flex mb-3">
                                    <div class="step-num me-3 bg-info text-white rounded-circle d-flex align-items-center justify-content-center fw-bold" style="width: 32px; height: 32px; min-width: 32px;">1</div>
                                    <div>
                                        <div class="fw-bold">Đăng ký & Thêm tài khoản BIDV trên ThueApi.pro:</div>
                                        <div class="small text-muted">Truy cập <a href="https://thueapi.pro" target="_blank" class="fw-bold text-info">https://thueapi.pro</a> ➔ Cổng thanh toán ➔ Thêm tài khoản ngân hàng BIDV của bạn (STK <code>8880117869</code>).</div>
                                    </div>
                                </div>

                                <div class="step-item d-flex mb-3">
                                    <div class="step-num me-3 bg-info text-white rounded-circle d-flex align-items-center justify-content-center fw-bold" style="width: 32px; height: 32px; min-width: 32px;">2</div>
                                    <div>
                                        <div class="fw-bold">Lấy Token BIDV:</div>
                                        <div class="small text-muted">Vào menu <b>Nhà phát triển</b> ➔ Chọn <b>API V2</b> ➔ Chọn tab <b>BIDV</b> ➔ Copy đoạn token trong đường dẫn <code>https://thueapi.pro/historyapibidvv2/<b>:tokenbidv</b></code>.</div>
                                    </div>
                                </div>

                                <div class="step-item d-flex mb-3">
                                    <div class="step-num me-3 bg-info text-white rounded-circle d-flex align-items-center justify-content-center fw-bold" style="width: 32px; height: 32px; min-width: 32px;">3</div>
                                    <div>
                                        <div class="fw-bold">Dán Token & Lưu Cấu Hình:</div>
                                        <div class="small text-muted">Dán token vào ô <b>Token BIDV</b> bên trái và bấm <b>Lưu Cấu Hình Ngân Hàng</b>. Hệ thống sẽ lưu vào Supabase và bắt đầu tự động quét giao dịch 24/7!</div>
                                    </div>
                                </div>

                                <div class="alert alert-success mt-4 small">
                                    <div class="fw-bold mb-1"><i class="fa-solid fa-qrcode me-1"></i> Cơ chế tạo mã VietQR tự động:</div>
                                    Khi khách nạp qua bot, bot tự sinh mã VietQR chuẩn Napas quốc gia có sẵn STK <b>8880117869</b>, số tiền chính xác và cú pháp <code>NAP &lt;telegram_id&gt;</code>. Khách chỉ cần mở app ngân hàng quét là tự điền đúng mọi thông tin!
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 3: FACEBOOK CLONE SETTINGS & AUTO CHECK LIVE -->
            <div class="tab-pane fade" id="tab-facebook">
                <div class="row g-4">
                    <!-- Cột 1: Cấu hình Bật/Tắt Check Live & Xóa DIE -->
                    <div class="col-lg-6">
                        <div class="card border-primary h-100 shadow-sm">
                            <div class="card-header bg-primary bg-opacity-10 py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-brands fa-facebook text-primary me-2"></i>Cấu Hình Tự Động Check Live & Xóa Nick DIE</h5>
                            </div>
                            <div class="card-body">
                                <div class="alert alert-info py-2 small mb-3">
                                    <i class="fa-solid fa-circle-check me-1"></i> Tự động kiểm tra trực tiếp qua <b>Facebook Graph API</b> (tốc độ cao, không cần cookie, không sợ bị khóa).
                                </div>

                                <form id="facebookForm" onsubmit="event.preventDefault(); saveFacebookSettings();">
                                    <h6 class="fw-bold text-primary border-bottom pb-1 mb-3">1. Khi Nạp / Đăng Hàng Vào Kho:</h6>

                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded border border-warning">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="fb_filter_duplicate_uids" {fb_filter_dups_attr}>
                                        <label class="form-check-label fw-bold text-dark" for="fb_filter_duplicate_uids">
                                            <i class="fa-solid fa-clone text-warning me-1"></i> Tự động LỌC & CHẶN TRÙNG UID Facebook khi nạp
                                        </label>
                                        <div class="small text-muted ms-4">Nếu UID đã có trong kho hàng (hoặc lặp lại trong danh sách nạp), hệ thống sẽ tự động loại bỏ để <b>không bao giờ bán trùng nick</b> cho khách.</div>
                                    </div>
                                    
                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="fb_auto_check_on_upload" {fb_check_up_attr}>
                                        <label class="form-check-label fw-bold" for="fb_auto_check_on_upload">Tự động check LIVE UID khi nạp hàng</label>
                                        <div class="small text-muted ms-4">Khi nạp clone qua Web, API, Bot hoặc File TXT, hệ thống sẽ tự động quét trạng thái từng UID.</div>
                                    </div>

                                    <div class="form-check form-switch mb-4 p-2 bg-light rounded">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="fb_auto_delete_die_on_upload" {fb_del_up_attr}>
                                        <label class="form-check-label fw-bold text-danger" for="fb_auto_delete_die_on_upload">Tự động XÓA / LOẠI BỎ tài khoản DIE khi nạp</label>
                                        <div class="small text-muted ms-4">Nếu bật, các nick DIE sẽ bị lọc bỏ ngay lập tức, chỉ những nick <b>LIVE 100%</b> mới được đưa vào kho.</div>
                                    </div>

                                    <h6 class="fw-bold text-success border-bottom pb-1 mb-3">2. Khi Khách Mua Hàng (Giao Cho Khách):</h6>

                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="fb_check_live_before_delivery" {fb_check_deliv_attr}>
                                        <label class="form-check-label fw-bold" for="fb_check_live_before_delivery">Check LIVE UID trước khi giao hàng cho khách</label>
                                        <div class="small text-muted ms-4">Khi khách thanh toán, Bot sẽ quét lại ngay tại thời điểm giao để đảm bảo khách không bao giờ nhận phải acc DIE.</div>
                                    </div>

                                    <div class="form-check form-switch mb-4 p-2 bg-light rounded">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="fb_auto_delete_die_on_delivery" {fb_del_deliv_attr}>
                                        <label class="form-check-label fw-bold text-danger" for="fb_auto_delete_die_on_delivery">Tự động xóa nick DIE và lấy nick LIVE khác bù vào</label>
                                        <div class="small text-muted ms-4">Nếu acc trong kho bị die sau thời gian lưu trữ, bot sẽ xóa nick die đó và tự động bốc nick LIVE khác giao cho khách.</div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">Từ khóa nhận diện danh mục Facebook (phân cách bằng dấu phẩy):</label>
                                        <input type="text" class="form-control font-monospace small" id="fb_category_keywords" value="{fb_keywords}" placeholder="facebook, fb, clone, via, bm">
                                        <div class="form-text small">Các danh mục chứa từ khóa này sẽ tự động được áp dụng cơ chế lọc Facebook clone.</div>
                                    </div>

                                    <h6 class="fw-bold text-info border-bottom pb-1 mb-3 mt-4"><i class="fa-solid fa-clock-rotate-left me-1"></i> 3. Cron Tự Động Quét Kho Theo Chu Kỳ (Sau mỗi XX phút):</h6>

                                    <div class="mb-3 p-2 bg-light rounded border">
                                        <label class="form-label fw-bold small text-dark mb-1">Chu kỳ tự động check LIVE kho (phút):</label>
                                        <div class="input-group" style="max-width: 250px;">
                                            <input type="number" class="form-control fw-bold" id="fb_cron_check_interval_minutes" value="{fb_cron_interval}" min="0" max="1440">
                                            <span class="input-group-text">phút</span>
                                        </div>
                                        <div class="form-text small">Đặt <b>30</b> = Quét 30 phút/lần. Đặt <b>60</b> = Quét 1 tiếng/lần. Đặt <b>0</b> = Tắt cron tự động.</div>
                                    </div>

                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded border">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="fb_cron_notify_admin" {fb_cron_notify_attr}>
                                        <label class="form-check-label fw-bold" for="fb_cron_notify_admin">Gửi thông báo báo cáo về Telegram Admin khi quét</label>
                                    </div>

                                    <div class="mb-3 p-3 bg-light rounded border">
                                        <label class="form-label fw-bold small text-dark mb-1"><i class="fa-solid fa-link me-1"></i> Link Webhook Cron Cho Dịch Vụ Ngoài (Cron-job.org / Vercel / UptimeRobot):</label>
                                        <div class="input-group">
                                            <input type="text" class="form-control font-monospace small" id="cronWebhookUrl" value="{cron_webhook_url}" readonly>
                                            <button class="btn btn-outline-primary" type="button" onclick="navigator.clipboard.writeText(document.getElementById('cronWebhookUrl').value); alert('Đã sao chép link Cron!')">
                                                <i class="fa-solid fa-copy me-1"></i> Sao chép
                                            </button>
                                        </div>
                                        <div class="form-text small">Dán URL này vào <b>Cron-job.org</b> hoặc <b>EasyCron</b> để kích hoạt quét kho từ bên ngoài theo đúng số phút bạn muốn!</div>
                                    </div>

                                    <div id="fbSaveResult" class="mb-3" style="display:none;"></div>

                                    <div class="pt-2 border-top">
                                        <button type="submit" class="btn btn-primary fw-bold px-4">
                                            <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Cấu Hình Facebook Ngay
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>

                    <!-- Cột 2: Công cụ kiểm tra UID & Quản trị kho trực tiếp -->
                    <div class="col-lg-6">
                        <!-- Widget 1: Kiểm tra nhanh 1 UID -->
                        <div class="card shadow-sm mb-4">
                            <div class="card-header py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-magnifying-glass text-info me-2"></i>Kiểm Tra Nhanh 1 Tài Khoản Facebook</h5>
                            </div>
                            <div class="card-body">
                                <div class="mb-3">
                                    <label class="form-label small text-muted fw-bold">Nhập UID hoặc chuỗi Clone (UID|Pass|2FA...):</label>
                                    <div class="input-group">
                                        <input type="text" class="form-control font-monospace" id="quickUidInput" placeholder="VD: 100088912345678|Password|2FA...">
                                        <button class="btn btn-info text-white fw-bold" type="button" onclick="checkSingleUid()">
                                            <i class="fa-solid fa-circle-play me-1"></i> Kiểm Tra
                                        </button>
                                    </div>
                                </div>
                                <div id="quickUidResult" style="display:none;" class="p-3 bg-light rounded border"></div>
                            </div>
                        </div>

                        <!-- Widget 2: Quét & Dọn Dẹp Kho Hàng Facebook -->
                        <div class="card border-danger shadow-sm">
                            <div class="card-header bg-danger bg-opacity-10 py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-broom text-danger me-2"></i>Quét & Xóa Sạch Nick DIE Trong Kho</h5>
                            </div>
                            <div class="card-body">
                                <p class="small text-muted">Quét toàn bộ tài khoản clone Facebook đang tồn trong database để kiểm tra trạng thái sống/chết và dọn sạch nick DIE để đảm bảo uy tín shop.</p>
                                
                                <div class="d-flex flex-wrap gap-2 mb-3">
                                    <button class="btn btn-outline-primary fw-bold" type="button" onclick="scanFbStock()">
                                        <i class="fa-solid fa-magnifying-glass-chart me-1"></i> Quét Toàn Kho (Xem Trạng Thái)
                                    </button>
                                    <button class="btn btn-warning fw-bold text-dark" type="button" onclick="cleanFbDuplicateStock()">
                                        <i class="fa-solid fa-clone me-1"></i> Quét & XÓA Nick Trùng UID
                                    </button>
                                    <button class="btn btn-danger fw-bold" type="button" onclick="cleanFbDieStock()">
                                        <i class="fa-solid fa-trash-can me-1"></i> Quét & XÓA Nick DIE
                                    </button>
                                </div>

                                <div id="stockScanResult" style="display:none;" class="p-3 bg-light rounded border"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 5: KHUYẾN MÃI NẠP TIỀN (DEPOSIT BONUS) -->
            <div class="tab-pane fade" id="tab-bonus">
                <div class="row g-4">
                    <div class="col-lg-7">
                        <div class="card border-danger h-100 shadow-sm">
                            <div class="card-header bg-danger bg-opacity-10 py-3 d-flex justify-content-between align-items-center">
                                <h5 class="card-title mb-0 fw-bold text-dark">
                                    <i class="fa-solid fa-gift text-danger me-2"></i>Cấu Hình Khuyến Mãi Nạp Tiền (Deposit Bonus)
                                </h5>
                                {bonus_badge}
                            </div>
                            <div class="card-body">
                                <div class="alert alert-info py-2 small mb-3">
                                    <i class="fa-solid fa-circle-info me-1"></i>
                                    <b>Cơ chế hoạt động:</b><br>
                                    • Khi <b>TẮT</b>: Bot sẽ hoàn toàn ẩn thông tin thưởng nạp, chỉ hiển thị form nhập số tiền nạp bình thường và không cộng thêm tiền thưởng.<br>
                                    • Khi <b>BẬT</b>: Bot sẽ hiển thị danh sách thưởng nạp theo các mốc cấu hình bên dưới. Khi khách nạp tiền (qua Binance Pay, BIDV Bank hoặc On-chain), hệ thống sẽ <b>tự động tính % và cộng thêm tiền thưởng vào tài khoản khách</b>, đồng thời báo rõ trong thông báo Ting Ting.
                                </div>

                                <form id="bonusForm" onsubmit="event.preventDefault(); saveBonusSettings();">
                                    <div class="form-check form-switch mb-3 p-3 bg-light rounded border border-danger">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="deposit_bonus_enabled" {deposit_bonus_enabled_attr}>
                                        <label class="form-check-label fw-bold text-dark" for="deposit_bonus_enabled">
                                            <i class="fa-solid fa-power-off text-danger me-1"></i> Bật / Tắt Chương Trình Thưởng Nạp
                                        </label>
                                        <div class="small text-muted ms-4">Bật công tắc này nếu bạn muốn chạy chương trình khuyến mãi nạp tiền cho khách hàng.</div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">Các Mốc Thưởng Nạp (Mức USDT : % Thưởng):</label>
                                        <input type="text" class="form-control font-monospace fw-bold" id="deposit_bonus_tiers" value="{deposit_bonus_tiers}" placeholder="100:2,200:5,300:6,500:7,1000:8">
                                        <div class="form-text small">
                                            Định dạng: <code>SốTiền:PhầnTrăm</code> phân cách bởi dấu phẩy <code>,</code> hoặc xuống dòng.<br>
                                            <i>Ví dụ: <code>100:2, 200:5, 300:6, 500:7, 1000:8</code> có nghĩa là:<br>
                                            • Nạp từ 100 USDT trở lên: thưởng +2%<br>
                                            • Nạp từ 200 USDT trở lên: thưởng +5%<br>
                                            • Nạp từ 300 USDT trở lên: thưởng +6%<br>
                                            • Nạp từ 500 USDT trở lên: thưởng +7%<br>
                                            • Nạp từ 1.000 USDT trở lên: thưởng +8%</i>
                                        </div>
                                    </div>

                                    <div class="d-grid mt-4">
                                        <button type="submit" class="btn btn-danger py-2 fw-bold">
                                            <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Cấu Hình Khuyến Mãi
                                        </button>
                                    </div>
                                    <div id="bonusSaveResult" class="mt-3" style="display:none;"></div>
                                </form>
                            </div>
                        </div>
                    </div>

                    <div class="col-lg-5">
                        <div class="card border-info shadow-sm mb-4">
                            <div class="card-header bg-info bg-opacity-10 py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-eye me-2 text-info"></i>Xem Trước Hiển Thị Trên Bot</h5>
                            </div>
                            <div class="card-body">
                                <p class="small text-muted mb-2">Giao diện khách nhìn thấy trên Telegram khi bấm Nạp tiền:</p>
                                <div class="p-3 rounded bg-dark text-light font-monospace small" style="white-space: pre-wrap;">{preview_bonus_html}</div>
                            </div>
                        </div>

                        <div class="card border-warning shadow-sm">
                            <div class="card-header bg-warning bg-opacity-10 py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-lightbulb me-2 text-warning"></i>Gợi Ý Cấu Hình</h5>
                            </div>
                            <div class="card-body small text-muted">
                                <p class="mb-2"><b>Mẫu 1 (Khuyến mãi nhẹ):</b><br>
                                <code>50:1, 100:2, 500:5</code></p>
                                <p class="mb-2"><b>Mẫu 2 (Kích thích nạp số lượng lớn):</b><br>
                                <code>100:2, 200:5, 300:6, 500:7, 1000:8</code></p>
                                <p class="mb-0"><b>Mẫu 3 (Thưởng nạp lễ/tết):</b><br>
                                <code>10:5, 50:10, 100:15</code></p>
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
            if (!input) return;
            const icon = btn ? btn.querySelector('i') : null;
            if (input.type === 'password') {{
                input.type = 'text';
                if (icon) icon.className = 'fa-solid fa-eye-slash';
            }} else {{
                input.type = 'password';
                if (icon) icon.className = 'fa-solid fa-eye';
            }}
        }}

        function togglePasswordVisibility(id, btn) {{
            togglePass(id, btn);
        }}

        function showToast(msg, type) {{
            let container = document.getElementById('toastContainer');
            if (!container) {{
                container = document.createElement('div');
                container.id = 'toastContainer';
                container.style = 'position: fixed; top: 20px; right: 20px; z-index: 99999;';
                document.body.appendChild(container);
            }}
            const id = 'toast_' + Date.now();
            const bgClass = type === 'success' ? 'bg-success' : (type === 'danger' ? 'bg-danger' : (type === 'warning' ? 'bg-warning text-dark' : 'bg-info text-dark'));
            const toastHtml = `
                <div id="${{id}}" class="toast align-items-center text-white ${{bgClass}} border-0 show shadow mb-2" role="alert" style="min-width: 280px;">
                    <div class="d-flex">
                        <div class="toast-body fw-bold">${{msg}}</div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" onclick="document.getElementById('${{id}}').remove()"></button>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', toastHtml);
            setTimeout(() => {{
                const el = document.getElementById(id);
                if (el) el.remove();
            }}, 4000);
        }}

        async function saveSettingsPayload(payload, resultDivId) {{
            const resDiv = document.getElementById(resultDivId);
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang lưu cài đặt vào Database Supabase...</span>';

            try {{
                const res = await fetch("{api_settings_save}", {{
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-API-KEY': "{api_key}",
                        'Authorization': "Bearer {admin_token}"
                    }},
                    body: JSON.stringify({{ settings: payload }})
                }});
                const data = await res.json();
                if (res.ok) {{
                    resDiv.innerHTML = '<div class="alert alert-success py-2 mb-0"><i class="fa-solid fa-circle-check me-1"></i> <b>Lưu thành công!</b> ' + (data.message || 'Cấu hình đã được lưu vĩnh viễn vào Supabase và kích hoạt ngay lập tức.') + '</div>';
                    setTimeout(() => {{ location.reload(); }}, 1500);
                }} else {{
                    const errDetail = data.detail || data.message || ('Không thể lưu cài đặt (Mã lỗi: ' + res.status + ')');
                    resDiv.innerHTML = '<div class="alert alert-danger py-2 mb-0"><i class="fa-solid fa-circle-exclamation me-1"></i> Lỗi: ' + errDetail + '</div>';
                }}
            }} catch (err) {{
                resDiv.innerHTML = '<div class="alert alert-danger py-2 mb-0"><i class="fa-solid fa-circle-exclamation me-1"></i> Lỗi kết nối: ' + err.message + '</div>';
            }}
        }}

        function saveFacebookSettings() {{
            const payload = {{
                'FB_FILTER_DUPLICATE_UIDS': document.getElementById('fb_filter_duplicate_uids').checked ? 'true' : 'false',
                'FB_AUTO_CHECK_ON_UPLOAD': document.getElementById('fb_auto_check_on_upload').checked ? 'true' : 'false',
                'FB_AUTO_DELETE_DIE_ON_UPLOAD': document.getElementById('fb_auto_delete_die_on_upload').checked ? 'true' : 'false',
                'FB_CHECK_LIVE_BEFORE_DELIVERY': document.getElementById('fb_check_live_before_delivery').checked ? 'true' : 'false',
                'FB_AUTO_DELETE_DIE_ON_DELIVERY': document.getElementById('fb_auto_delete_die_on_delivery').checked ? 'true' : 'false',
                'FB_CATEGORY_KEYWORDS': document.getElementById('fb_category_keywords').value.trim(),
                'FB_CRON_CHECK_INTERVAL_MINUTES': document.getElementById('fb_cron_check_interval_minutes').value.trim() || '30',
                'FB_CRON_NOTIFY_ADMIN': document.getElementById('fb_cron_notify_admin').checked ? 'true' : 'false'
            }};
            saveSettingsPayload(payload, 'fbSaveResult');
        }}

        async function checkSingleUid() {{
            const val = document.getElementById('quickUidInput').value.trim();
            const resDiv = document.getElementById('quickUidResult');
            if (!val) {{ alert('Vui lòng nhập UID!'); return; }}
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang kiểm tra Facebook Graph API...</span>';

            try {{
                const res = await fetch("{api_fb_check_uid}", {{
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-API-KEY': "{api_key}",
                        'Authorization': "Bearer {admin_token}"
                    }},
                    body: JSON.stringify({{ data: val }})
                }});
                const data = await res.json();
                if (data.results && data.results.length > 0) {{
                    const r = data.results[0];
                    if (r.status === 'LIVE') {{
                        resDiv.innerHTML = '<div class="text-success fw-bold"><i class="fa-solid fa-circle-check me-1"></i> UID ' + r.uid + ' -> LIVE (Hoạt động tốt)</div>';
                    }} else {{
                        resDiv.innerHTML = '<div class="text-danger fw-bold"><i class="fa-solid fa-circle-xmark me-1"></i> UID ' + r.uid + ' -> DIE (Bị khóa / Checkpoint)</div>';
                    }}
                }} else {{
                    resDiv.innerHTML = '<div class="text-warning">Không tìm thấy UID hợp lệ trong chuỗi.</div>';
                }}
            }} catch(e) {{
                resDiv.innerHTML = '<div class="text-danger">Lỗi: ' + e.message + '</div>';
            }}
        }}

        async function scanFbStock() {{
            const resDiv = document.getElementById('stockScanResult');
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang quét toàn bộ kho clone...</span>';
            try {{
                const res = await fetch("{api_fb_scan_stock}", {{
                    credentials: 'same-origin',
                    headers: {{
                        'X-API-KEY': "{api_key}",
                        'Authorization': "Bearer {admin_token}"
                    }}
                }});
                const data = await res.json();
                resDiv.innerHTML = '<div class="alert alert-info py-2 mb-0"><b>Kết quả:</b> Quét ' + data.total_scanned + ' clone | Live: <span class="text-success fw-bold">' + data.live_count + '</span> | Die: <span class="text-danger fw-bold">' + data.die_count + '</span></div>';
            }} catch(e) {{
                resDiv.innerHTML = '<div class="text-danger">Lỗi: ' + e.message + '</div>';
            }}
        }}

                async function cleanFbDuplicateStock() {{
            if (!confirm('Bạn có chắc chắn muốn quét và XÓA các nick bị TRÙNG UID trong kho hàng không? (Hệ thống sẽ giữ lại 1 nick duy nhất)')) return;
            const resDiv = document.getElementById('stockScanResult');
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<span class="text-warning"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang quét và lọc nick trùng UID trong kho...</span>';
            try {{
                const res = await fetch("{api_fb_clean_dups}", {{
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {{
                        'X-API-KEY': "{api_key}",
                        'Authorization': "Bearer {admin_token}"
                    }}
                }});
                const data = await res.json();
                if (res.ok) {{
                    const delCount = data.deleted_duplicates || 0;
                    resDiv.innerHTML = '<div class="alert alert-success py-2 mb-0"><b>Hoàn tất:</b> Đã quét ' + data.total_scanned + ' clone. Độc nhất: ' + data.unique_uids + ' UID | Đã xóa: <span class="text-danger fw-bold">' + delCount + '</span> nick bị trùng UID khỏi kho!</div>';
                }} else {{
                    resDiv.innerHTML = '<div class="alert alert-danger py-2 mb-0">Lỗi: ' + (data.detail || JSON.stringify(data)) + '</div>';
                }}
            }} catch(e) {{
                resDiv.innerHTML = '<div class="text-danger">Lỗi: ' + e.message + '</div>';
            }}
        }}

        async function cleanFbDieStock() {{
            if (!confirm('Bạn có chắc chắn muốn quét và XÓA TOÀN BỘ clone DIE khỏi kho không?')) return;
            const resDiv = document.getElementById('stockScanResult');
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<span class="text-danger"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang quét và xóa nick DIE khỏi kho...</span>';
            try {{
                const res = await fetch("{api_fb_clean_die}", {{
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {{
                        'X-API-KEY': "{api_key}",
                        'Authorization': "Bearer {admin_token}"
                    }}
                }});
                const data = await res.json();
                resDiv.innerHTML = '<div class="alert alert-success py-2 mb-0"><b>Hoàn tất:</b> Đã quét ' + data.total_scanned + ' clone. Live: ' + data.live_count + ' | Đã xóa: <span class="text-danger fw-bold">' + data.deleted_count + '</span> nick DIE khỏi kho!</div>';
            }} catch(e) {{
                resDiv.innerHTML = '<div class="text-danger">Lỗi: ' + e.message + '</div>';
            }}
        }}

function saveBankSettings() {{
            const payload = {{
                'BANK_BIDV_TOKEN': document.getElementById('bank_token').value.trim(),
                'BANK_ACCOUNT_NUMBER': document.getElementById('bank_account_number').value.trim(),
                'BANK_ACCOUNT_NAME': document.getElementById('bank_account_name').value.trim(),
                'BANK_CODE': document.getElementById('bank_code').value.trim(),
                'BANK_EXCHANGE_RATE': parseFloat(document.getElementById('bank_exchange_rate').value) || 26000,
                'BANK_AUTO_CHECK': document.getElementById('bank_auto_check').checked
            }};
            saveSettingsPayload(payload, 'bankSaveResult');
        }}

        async function checkBankTransactionsNow() {{
            const resBox = document.getElementById('bankSaveResult');
            if (resBox) {{
                resBox.style.display = 'block';
                resBox.innerHTML = '<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang kết nối ThueApi.pro để quét giao dịch ngân hàng BIDV...</span>';
            }}
            showToast('Đang kết nối ThueApi.pro quét giao dịch...', 'info');

            try {{
                const res = await fetch('/api/bank/check-now', {{
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-API-KEY': '{api_key}',
                        'Authorization': 'Bearer {admin_token}'
                    }}
                }});
                const data = await res.json();
                if (res.ok && data.status === 'success') {{
                    if (data.credited_count > 0) {{
                        const msg = 'Thành công! Đã phát hiện và cộng tiền cho ' + data.credited_count + ' giao dịch mới!';
                        if (resBox) resBox.innerHTML = '<div class="alert alert-success py-2 mb-0"><i class="fa-solid fa-circle-check me-1"></i> <b>' + msg + '</b></div>';
                        showToast(msg, 'success');
                    }} else {{
                        const msg = 'Kết nối ThueApi.pro thành công! Hiện chưa có giao dịch chuyển khoản mới.';
                        if (resBox) resBox.innerHTML = '<div class="alert alert-info py-2 mb-0"><i class="fa-solid fa-check me-1"></i> ' + msg + '</div>';
                        showToast(msg, 'info');
                    }}
                }} else {{
                    const errMsg = data.detail || data.message || 'Không thể quét giao dịch';
                    if (resBox) resBox.innerHTML = '<div class="alert alert-danger py-2 mb-0"><i class="fa-solid fa-triangle-exclamation me-1"></i> <b>Lỗi:</b> ' + errMsg + '</div>';
                    showToast('Lỗi: ' + errMsg, 'danger');
                }}
            }} catch (err) {{
                if (resBox) resBox.innerHTML = '<div class="alert alert-danger py-2 mb-0"><i class="fa-solid fa-triangle-exclamation me-1"></i> <b>Lỗi kết nối:</b> ' + err.message + '</div>';
                showToast('Lỗi mạng: ' + err.message, 'danger');
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

        function saveBonusSettings() {{
            const payload = {{
                'DEPOSIT_BONUS_ENABLED': document.getElementById('deposit_bonus_enabled').checked ? 'true' : 'false',
                'DEPOSIT_BONUS_TIERS': document.getElementById('deposit_bonus_tiers').value.trim()
            }};
            saveSettingsPayload(payload, 'bonusSaveResult');
        }}

        function saveForwardingSettings() {{
            const payload = {{
                'CRYPTO_FORWARDING_MODE': document.getElementById('crypto_forwarding_mode').checked ? 'true' : 'false',
                'ONLY_USDT_MODE': document.getElementById('only_usdt_mode').checked ? 'true' : 'false',
                'BNB_FORWARDING_ADDRESS': document.getElementById('bnb_forwarding_address').value.trim(),
                'SOL_FORWARDING_ADDRESS': document.getElementById('sol_forwarding_address').value.trim(),
                'ETH_FORWARDING_ADDRESS': document.getElementById('eth_forwarding_address').value.trim(),
                'BTC_FORWARDING_ADDRESS': document.getElementById('btc_forwarding_address').value.trim(),
                'LTC_FORWARDING_ADDRESS': document.getElementById('ltc_forwarding_address').value.trim(),
                'DOGE_FORWARDING_ADDRESS': document.getElementById('doge_forwarding_address').value.trim()
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
                    credentials: 'same-origin',
                    headers: {{
                        'X-API-KEY': "{api_key}",
                        'Authorization': "Bearer {admin_token}"
                    }}
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
